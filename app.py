import os
from dotenv import load_dotenv
import argparse

from src.workflow import create_workflow
from src.show import print_save
from src.log_config import loggers
from src.config_loader import ModelConfig, OutlineConfig, BaseConfig
from src.core.state_manager import StateManager
from src.core.progress import WorkflowStatus

load_dotenv(override=True)
logger = loggers['main']

# CLI 模式使用的固定 workflow_id
CLI_WORKFLOW_ID = "cli_workflow"

def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--model_type", default='api',type=str, help="local or api")
    parser.add_argument("--hitl", default=False, type=bool, help="hitl or not")
    parser.add_argument("--force", action="store_true", help="强制开始新工作流，不询问断点续传")
    parser.add_argument("--min-chapters", type=int, default=None, help="最小章节数（默认从OutlineConfig读取）")
    parser.add_argument("--volume", type=int, default=None, help="分卷数量（默认从OutlineConfig读取）")
    parser.add_argument("--master-outline", type=lambda x: x.lower()=='true' or x=='1', default=None, help="是否开启分卷解析大纲功能（默认True）")
    parser.add_argument("--execution-mode", type=str, default='serial', choices=['serial', 'parallel'], help="执行模式：serial串行/parallel并行（默认serial）")
    return parser.parse_args()

api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")
api_type = os.getenv("API_TYPE", "openai")

def check_and_offer_resume(state_manager: StateManager):
    """检查是否存在可恢复的断点，如果存在则询问用户"""
    if not state_manager.has_checkpoint(CLI_WORKFLOW_ID):
        return None

    checkpoint = state_manager.load_checkpoint(CLI_WORKFLOW_ID)
    if not checkpoint:
        return None

    print("\n" + "="*50)
    print("发现未完成的工作流！")
    print(f"小说标题: {checkpoint.get('novel_title', '未知')}")
    print(f"上次进度: 第 {checkpoint.get('current_chapter_index', 0) + 1} 章")
    print(f"当前节点: {checkpoint.get('current_node', '未知')}")
    print("="*50)

    while True:
        choice = input("\n请选择操作：\n1. 继续上次进度（断点续传）\n2. 放弃并重新开始\n请输入选项 (1/2): ").strip()
        if choice == "1":
            return True
        elif choice == "2":
            state_manager.clear_checkpoint(CLI_WORKFLOW_ID)
            state_manager.delete_state(CLI_WORKFLOW_ID)
            return False
        else:
            print("无效选项，请重新输入")

def main():
    args = get_args()
    model_type = args.model_type

    # 初始化 StateManager
    state_manager = StateManager()

    # 检查断点续传（除非 --force 指定）
    should_resume = None
    if not args.force:
        should_resume = check_and_offer_resume(state_manager)

    # 如果选择断点续传，先加载检查点获取之前的意图
    checkpoint = None
    saved_user_intent = None
    if should_resume == True:
        checkpoint = state_manager.load_checkpoint(CLI_WORKFLOW_ID)
        if checkpoint:
            saved_user_intent = checkpoint.get("user_intent", "")

    if model_type == "api":
        model_name = input("请输入你的模型名字：")
        model_config = ModelConfig(
            model_type="api",
            api_key=api_key,
            api_url=base_url,
            model_name=model_name,
            api_type=api_type
        )
    elif model_type == "local":
        model_path = input("请输入你的模型路径：")
        model_config = ModelConfig(
            model_type="local",
            model_path=model_path
        )

    # 交互式选择执行模式
    print("\n请选择执行模式：")
    print("1. 串行模式（稳定，单章节依次生成）")
    print("2. 并行模式（快速，需要配置多 API Key 或启用多客户端）")
    while True:
        mode_choice = input("请输入选项 (1/2，默认1): ").strip()
        if mode_choice == "2":
            execution_mode = "parallel"
            break
        elif mode_choice in ("", "1"):
            execution_mode = "serial"
            break
        else:
            print("无效选项，请重新输入")

    # 交互式选择评估模式
    print("\n请选择评估模式：")
    print("1. 快速模式（ReflectAgent 简单评估，速度快）")
    print("2. 深度模式（5个 Specialists 并行深度分析，质量高）")
    while True:
        eval_choice = input("请输入选项 (1/2，默认2): ").strip()
        if eval_choice == "1":
            evaluation_mode = "fast"
            break
        elif eval_choice in ("", "2"):
            evaluation_mode = "deep"
            break
        else:
            print("无效选项，请重新输入")

    try:
        logger.info("开始小说生成流程")

        # 构建 agent_config（支持命令行参数覆盖）
        min_chapters = args.min_chapters if args.min_chapters is not None else OutlineConfig.min_chapters
        volume = args.volume if args.volume is not None else OutlineConfig.volume
        master_outline = args.master_outline if args.master_outline is not None else OutlineConfig.master_outline

        agent_config = BaseConfig(
            min_chapters=min_chapters,
            volume=volume,
            master_outline=master_outline
        )

        app = create_workflow(model_config, agent_config, execution_mode=execution_mode)

        # 如果有保存的意图，直接使用；否则要求输入
        if saved_user_intent:
            user_intent = saved_user_intent
            print(f"\n📖 创作意图: {user_intent}")
        else:
            user_intent = input("请输入你的小说创作意图：")

        logger.info(f"用户创作意图: {user_intent}")

        # 构建初始状态
        initial_state = {
            "user_intent": user_intent,
            "gradio_mode": True if not args.hitl else False,
            "min_chapters": min_chapters,
            "volume": volume,
            "master_outline": master_outline,
            "execution_mode": execution_mode,
            "evaluation_mode": evaluation_mode,
        }

        # 如果选择断点续传，加载检查点状态
        if should_resume == True and checkpoint:
            from src.storage import NovelStorage
            from src.model import Character, ChapterOutline

            print(f"\n正在恢复进度，从第 {checkpoint.get('current_chapter_index', 0) + 1} 章继续...\n")

            # 恢复 NovelStorage（优先从 storage 恢复，storage 是数据的最终来源）
            novel_title = checkpoint.get("novel_title", "")
            if novel_title:
                storage = NovelStorage(novel_title)
                initial_state["novel_storage"] = storage

                # 恢复已验证的大纲（从 storage 优先）
                validated_outline = storage.load_outline()
                if validated_outline:
                    initial_state["validated_outline"] = validated_outline
                    initial_state["validated_chapters"] = validated_outline.chapters

                # 恢复已验证的角色（从 storage 优先，而不是 checkpoint）
                stored_characters = storage.load_characters()
                if stored_characters:
                    initial_state["validated_characters"] = stored_characters
                else:
                    # Fallback: 从 checkpoint 恢复（兼容旧格式）
                    validated_characters = []
                    raw_chars = checkpoint.get("validated_characters") or []
                    for c in raw_chars:
                        try:
                            validated_characters.append(Character(**c))
                        except Exception:
                            pass
                    initial_state["validated_characters"] = validated_characters

                # 恢复大纲元数据（卷进度）
                outline_meta = storage.load_outline_metadata()
                initial_state["current_volume_index"] = outline_meta.get("current_volume_index", 0)

            # 恢复章节索引
            initial_state["current_chapter_index"] = checkpoint.get("current_chapter_index", 0)
            initial_state["completed_chapters"] = checkpoint.get("completed_chapters", [])

            # 恢复执行参数（如果 checkpoint 中有的话）
            if "volume" in checkpoint:
                initial_state["volume"] = checkpoint["volume"]
            if "master_outline" in checkpoint:
                initial_state["master_outline"] = checkpoint["master_outline"]
            if "execution_mode" in checkpoint:
                initial_state["execution_mode"] = checkpoint["execution_mode"]

        # 创建工作流记录（用于断点保存）
        state_manager.create_workflow_record(CLI_WORKFLOW_ID, user_intent, initial_state)

        # 执行工作流（使用 stream 以支持断点保存）
        from src.core.progress import get_progress_emitter

        progress_emitter = get_progress_emitter()

        # 每次节点执行后保存检查点
        def on_node_complete(node_name, node_state):
            # 记录节点执行信息
            chapter_idx = node_state.get("current_chapter_index", 0)
            elapsed = node_state.get("_node_elapsed", 0)

            # 构建日志信息
            log_parts = [f"📍 [Node] {node_name}"]
            if chapter_idx > 0:
                log_parts.append(f"章节 {chapter_idx + 1}")
            if elapsed > 0:
                log_parts.append(f"耗时 {elapsed:.1f}s")
            logger.info(" | ".join(log_parts))

            # 保存检查点
            node_state["workflow_id"] = CLI_WORKFLOW_ID
            node_state["current_node"] = node_name
            if "novel_storage" in node_state and hasattr(node_state["novel_storage"], "base_dir"):
                node_state["novel_title"] = node_state["novel_storage"].base_dir.name.replace("_storage", "")
            state_manager.save_checkpoint(CLI_WORKFLOW_ID, node_state)
            state_manager.save_state(CLI_WORKFLOW_ID, node_state)

        # 使用 stream 迭代执行
        import time
        final_state = initial_state
        node_start_time = time.time()

        for step in app.stream(initial_state, {"recursion_limit": OutlineConfig.min_chapters * 50}):
            for node_name, node_state in step.items():
                # 计算本节点耗时
                current_time = time.time()
                if "_node_start" in final_state:
                    node_state["_node_elapsed"] = current_time - final_state["_node_start"]
                node_state["_node_start"] = current_time

                on_node_complete(node_name, node_state)
                final_state = node_state

                # 打印当前进度（简洁行）
                chapter_idx = node_state.get("current_chapter_index", 0)
                if chapter_idx > 0:
                    print(f"\r  ✍️  当前: 第 {chapter_idx + 1} 章 | {node_name}", end="", flush=True)

        print()  # 换行
        total_time = time.time() - node_start_time
        logger.info(f"小说生成流程完成 (总耗时 {total_time:.1f}s)")
        print_save(final_state)

        # 清除检查点
        state_manager.clear_checkpoint(CLI_WORKFLOW_ID)
        state_manager.delete_state(CLI_WORKFLOW_ID)

    except KeyboardInterrupt:
        print("\n\n工作流已中断，进度已保存。可以下次运行并选择'继续上次进度'来恢复。")
    except Exception as e:
        print(f"[main] 发生错误：{str(e)}")

if __name__ == "__main__":

    main()

