"""
Supervisor Node - 集成 WritingSupervisor 到 LangGraph workflow

重构后的 Supervisor：
- WritingSupervisor 作为主调度者
- 4 个检查型 SubAgents 并行执行
- ReflectionChecker 综合决策

不再需要 CouncilAgent。
"""
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any

from src.state import NovelState
from src.model import QualityEvaluation
from src.multi_agent import (
    WritingSupervisor,
    StoryBible,
)

logger = logging.getLogger(__name__)

# 全局实例（由 workflow 初始化时注入）
_writing_supervisor: WritingSupervisor = None
_storybible: StoryBible = None


def init_supervisor_node(model_manager=None):
    """初始化 supervisor node

    Args:
        model_manager: 模型管理器（可选），为 SubAgents 提供 LLM 支持
    """
    global _writing_supervisor, _storybible

    _writing_supervisor = WritingSupervisor(model_manager)
    # 复用 WritingSupervisor 的 StoryBible 实例，而不是创建新实例
    _storybible = _writing_supervisor.storybible

    logger.info("📖 [SupervisorNode] WritingSupervisor 初始化完成")


def supervisor_node(state: NovelState) -> Dict[str, Any]:
    """Supervisor 节点 - 调用 WritingSupervisor 审查章节

    重构后：
    - 直接调用 WritingSupervisor.review()
    - 返回 ReviewResult（包含具体修改建议）
    - 不再依赖 CouncilAgent
    """
    global _writing_supervisor, _storybible

    if _writing_supervisor is None:
        logger.warning("📖 [SupervisorNode] WritingSupervisor 未初始化，跳过")
        return {
            "supervisor_result": None,
            "revision_needed": False,
            "revision_priority": "none",
            "revision_notes": ""
        }

    current_index = state.current_chapter_index
    chapter_content = state.raw_current_chapter

    if not chapter_content:
        logger.info(f"📖 [SupervisorNode] 章节 {current_index+1} 无内容，跳过")
        return {
            "supervisor_result": None,
            "revision_needed": False,
            "revision_priority": "none",
            "revision_notes": ""
        }

    logger.info(f"📖 [SupervisorNode] 开始审查第 {current_index+1} 章")

    # 1. 从存储加载 StoryBible 或从大纲初始化
    if state.novel_storage:
        try:
            # 尝试从存储加载已存在的 StoryBible
            story_bible_content = state.novel_storage.load_story_bible()
            if story_bible_content:
                _writing_supervisor.load_story_bible(story_bible_content)
                logger.info(f"📖 [SupervisorNode] StoryBible 已从存储加载")
            # 如果 StoryBible 为空（首次运行），从大纲初始化
            elif not _writing_supervisor.storybible._character_arcs:
                outline = state.novel_storage.load_outline()
                characters = state.novel_storage.load_characters()
                if outline:
                    _writing_supervisor.init_storybible(outline, characters)
                    logger.info(f"📖 [SupervisorNode] StoryBible 已从大纲初始化")
        except Exception as e:
            logger.warning(f"📖 [SupervisorNode] StoryBible 初始化失败: {e}")

    # 2. 调用 WritingSupervisor.review() 审查章节
    try:
        def run_in_new_loop():
            """在独立线程中创建新事件循环并执行异步函数"""
            return asyncio.run(
                _writing_supervisor.review(chapter_content, current_index)
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_in_new_loop)
            review_result = future.result()

    except Exception as e:
        logger.error(f"🔴 [SupervisorNode] 审查失败: {e}")
        return {
            "supervisor_result": None,
            "revision_needed": False,
            "revision_priority": "none",
            "revision_notes": f"审查错误: {e}"
        }

    # 3. 验证 review_result 类型
    from src.multi_agent.types import ReviewResult
    if not isinstance(review_result, ReviewResult):
        # 如果是 dict，尝试转换
        if isinstance(review_result, dict):
            logger.warning(f"🔴 [SupervisorNode] review_result 是 dict，尝试转换: {str(review_result)[:200]}")
            # 检查是否是包含 chapter_index 的 dict
            if 'chapter_index' in review_result:
                try:
                    review_result = ReviewResult(
                        chapter_index=review_result.get('chapter_index', 0),
                        needs_revision=review_result.get('needs_revision', False),
                        suggestions=review_result.get('suggestions', []),
                        reasoning=review_result.get('reasoning', ''),
                        execution_time=review_result.get('execution_time', 0.0),
                        quality_score=review_result.get('quality_score', 5.0)
                    )
                    logger.info(f"🔴 [SupervisorNode] review_result dict 转换成功")
                except Exception as convert_err:
                    logger.error(f"🔴 [SupervisorNode] review_result dict 转换失败: {convert_err}")
                    return {
                        "supervisor_result": None,
                        "revision_needed": False,
                        "revision_priority": "none",
                        "revision_notes": f"审查结果转换失败: {convert_err}"
                    }
            else:
                logger.error(f"🔴 [SupervisorNode] review_result 是 dict 但没有 chapter_index 键")
                return {
                    "supervisor_result": None,
                    "revision_needed": False,
                    "revision_priority": "none",
                    "revision_notes": f"审查结果类型错误: {type(review_result)}"
                }
        else:
            logger.error(f"🔴 [SupervisorNode] review_result 类型错误: {type(review_result)}, 值: {str(review_result)[:200]}")
            return {
                "supervisor_result": None,
                "revision_needed": False,
                "revision_priority": "none",
                "revision_notes": f"审查结果类型错误: {type(review_result)}"
            }

    # 4. 转换为 workflow 兼容的输出格式
    needs_revision = review_result.needs_revision
    priority = "high" if (review_result.suggestions and
                          any(s.priority.value == "high" for s in review_result.suggestions)) else "medium"

    # 生成 revision_notes（具体修改建议）
    if review_result.suggestions:
        notes_parts = []
        for i, sug in enumerate(review_result.suggestions[:3], 1):
            notes_parts.append(f"{i}. [{sug.category.value}] {sug.issue}: {sug.suggested_change}")
        revision_notes = "; ".join(notes_parts)
    else:
        revision_notes = review_result.reasoning or "无需修订"

    logger.info(
        f"📖 [SupervisorNode] 第 {current_index+1} 章审查完成: "
        f"质量评分={review_result.quality_score:.1f}, "
        f"需要修订={needs_revision}, "
        f"建议数={len(review_result.suggestions)}"
    )

    return {
        "supervisor_result": review_result.to_dict(),
        "validated_evaluation": QualityEvaluation.from_review_result(review_result),
        "revision_needed": needs_revision,
        "revision_priority": priority,
        "revision_notes": revision_notes,
    }


def check_revision_node(state: NovelState) -> str:
    """检查是否需要修订

    重构后：直接基于 revision_needed 判断，不再经过 Council
    """
    revision_needed = getattr(state, 'revision_needed', False)

    if not revision_needed:
        logger.info("🔄 [CheckRevision] 无需修订，接受章节")
        return "accept_chapter"

    logger.info("🔄 [CheckRevision] 需要修订，进入修订流程")
    return "revise"


def get_writing_supervisor() -> WritingSupervisor:
    """获取 WritingSupervisor 实例"""
    return _writing_supervisor


# 向后兼容别名
def get_supervisor_writer() -> WritingSupervisor:
    """获取 WritingSupervisor 实例（向后兼容别名）"""
    return _writing_supervisor


def get_storybible() -> StoryBible:
    """获取 StoryBible 实例"""
    return _storybible