"""
可选入口：使用 WorkflowService 的小说生成器

这个入口展示了如何使用新的核心服务架构。
对于简单的使用场景，仍推荐使用 app.py（直接调用）。

Phase 1 目标：展示架构分离，保持向后兼容。
Phase 2 目标：FastAPI 服务化，多客户端共享。
"""
import os
from dotenv import load_dotenv
import argparse

from src.workflow import create_workflow
from src.show import print_save
from src.log_config import loggers
from src.config_loader import ModelConfig, OutlineConfig, BaseConfig
from src.core.workflow_service import get_workflow_service
from src.core.progress import get_progress_emitter

load_dotenv(override=True)
logger = loggers['main']


def get_args():
    parser = argparse.ArgumentParser(description="使用WorkflowService的小说生成器")
    parser.add_argument("--model_type", default='api', type=str, help="local or api")
    parser.add_argument("--hitl", default=False, type=bool, help="启用人机交互模式")
    parser.add_argument("--show-progress", action='store_true', help='显示详细进度')
    parser.add_argument("--force", action="store_true", help="强制开始新工作流，不询问断点续传")
    return parser.parse_args()


def check_and_offer_resume(service):
    """检查是否存在可恢复的断点，如果存在则询问用户"""
    # 获取所有中断的工作流
    interrupted = service.state_manager.get_interrupted_workflows()
    if not interrupted:
        return None

    # 显示中断的工作流
    print("\n" + "="*50)
    print("发现未完成的工作流：")
    for w in interrupted:
        print(f"  - 意图: {w.user_intent[:30]}...")
        print(f"    进度: {w.progress:.1%} | 状态: {w.status.value}")
        print(f"    当前节点: {w.current_node}")
        print()
    print("="*50)

    while True:
        choice = input("\n请选择操作：\n1. 恢复最近的工作流\n2. 放弃并重新开始\n请输入选项 (1/2): ").strip()
        if choice == "1":
            return interrupted[0].workflow_id
        elif choice == "2":
            # 清除所有检查点
            for w in interrupted:
                service.state_manager.clear_checkpoint(w.workflow_id)
                service.state_manager.delete_state(w.workflow_id)
            return None
        else:
            print("无效选项，请重新输入")


def progress_callback(event):
    """进度回调函数"""
    if event.status.value == "running":
        print(f"\r[{event.node}] {event.message} (进度: {event.progress:.1%})", end="", flush=True)
    elif event.status.value == "completed":
        print(f"\n🎉 {event.message}")
    elif event.status.value == "failed":
        print(f"\n❌ {event.message}")


def main():
    args = get_args()
    service = get_workflow_service()

    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")
    api_type = os.getenv("API_TYPE", "openai")

    if args.model_type == "api":
        model_name = input("请输入你的模型名字：")
        model_config = ModelConfig(
            api_key=api_key,
            api_url=base_url,
            model_name=model_name,
            api_type=api_type
        )
    else:
        model_path = input("请输入你的模型路径：")
        model_config = ModelConfig(
            model_path=model_path
        )

    # 检查断点续传（除非 --force 指定）
    resume_workflow_id = None
    if not args.force:
        resume_workflow_id = check_and_offer_resume(service)

    if resume_workflow_id:
        # 恢复已有工作流
        workflow_id = resume_workflow_id
        user_intent = service.get_status(workflow_id).get("user_intent", "")
        print(f"\n🚀 恢复工作流 (ID: {workflow_id})")
    else:
        # 创建新的工作流
        user_intent = input("请输入你的小说创作意图：")
        logger.info(f"用户创作意图: {user_intent}")

        print(f"\n📖 创作意图: {user_intent}")
        print(f"🔧 模型类型: {args.model_type}")

        # 使用 WorkflowService 创建工作流
        agent_config = BaseConfig(
            min_chapters=OutlineConfig.min_chapters,
            volume=OutlineConfig.volume,
            master_outline=OutlineConfig.master_outline
        )

        workflow_id = service.create_novel(
            user_intent=user_intent,
            model_config=model_config,
            agent_config=agent_config
        )

        print(f"\n🚀 工作流已创建 (ID: {workflow_id})")

    print("=" * 50)

    # 订阅进度事件（如果启用）
    if args.show_progress:
        emitter = get_progress_emitter()
        emitter.subscribe(progress_callback)

    try:
        # 执行工作流（传入 resume=True 如果是恢复）
        final_state = None
        should_resume = resume_workflow_id is not None
        for node_name, state_dict in service.execute(workflow_id, resume=should_resume):
            if args.show_progress:
                print(f"\n[{node_name}]")

            final_state = state_dict

        # 获取最终结果
        if final_state:
            result = final_state.get('result', '')
            if result == "生成失败":
                error = final_state.get('final_error', '未知错误')
                print(f"\n❌ 小说生成失败：{error}")
            else:
                print("\n🎉 小说生成完成！")
                # 使用原有方法保存
                print_save(final_state)
        else:
            print("\n❌ 未能获取最终状态")

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断，正在取消工作流...")
        service.cancel(workflow_id)
        print("✅ 工作流已取消")

    except Exception as e:
        print(f"\n❌ 发生错误：{str(e)}")
        logger.error(str(e))

    finally:
        if args.show_progress:
            # 显示最终状态
            status = service.get_status(workflow_id)
            if status:
                print(f"\n📊 最终状态: {status['status']}")
                print(f"📍 当前节点: {status.get('current_node', 'N/A')}")
                print(f"📈 进度: {status.get('progress', 0):.1%}")


if __name__ == "__main__":
    main()
