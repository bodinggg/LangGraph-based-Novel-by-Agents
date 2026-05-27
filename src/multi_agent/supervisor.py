"""
WritingSupervisor - 主调度者（SuperAgent）

管理 4 个检查型 SubAgents + 1 个评估型 SubAgent：
- 并行调度所有 SubAgents
- 收集结果，调用 ReflectionChecker 做最终决策
- 返回 ReviewResult 给 WriterAgent
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from src.multi_agent.storybible import StoryBible
from src.multi_agent.sub_agents import (
    ConsistencyChecker,
    CharacterArcChecker,
    PlotThreadChecker,
    WorldStateChecker,
    ReflectionChecker,
)
from src.multi_agent.types import SubAgentReport, ReviewResult
from src.thinking_logger import get_logger

logger = logging.getLogger(__name__)


class WritingSupervisor:
    """主调度者（SuperAgent）- 管理所有 SubAgents"""

    def __init__(self, model_manager=None, novel_title: str = ""):
        # 初始化 thinking_logger，确保 SubAgent 的日志被正确记录
        self.thinking_logger = get_logger(novel_title=novel_title)

        # 世界观管理
        self.storybible = StoryBible()

        # 检查型 SubAgents（并行执行）
        self.check_agents = [
            ConsistencyChecker(model_manager),
            CharacterArcChecker(model_manager),
            PlotThreadChecker(model_manager),
            WorldStateChecker(model_manager),
        ]

        # 评估型 Sub-Agent（综合决策）
        self.reflection_agent = ReflectionChecker(model_manager)

        logger.info(
            f"[WritingSupervisor] 初始化完成: "
            f"{len(self.check_agents)} 个检查 Agent + 1 个评估 Agent"
        )

    def load_story_bible(self, story_bible_content) -> None:
        """加载 StoryBible 内容"""
        self.storybible.load_from_content(story_bible_content)
        logger.info(f"[WritingSupervisor] StoryBible 已加载: {self.storybible.summary()}")

    def build_story_bible_from_outline(self, outline) -> None:
        """从大纲构建 StoryBible"""
        self.storybible.load_from_outline(outline)
        logger.info(f"[WritingSupervisor] StoryBible 从大纲构建完成")

    def init_storybible(self, outline, characters=None) -> None:
        """初始化 StoryBible（只调用一次）

        从大纲和角色档案构建初始 StoryBible
        """
        # 防止重复初始化
        if self.storybible._character_arcs:
            logger.info("[WritingSupervisor] StoryBible 已初始化，跳过")
            return

        self.storybible.load_from_outline(outline)

        # 如果有详细角色档案，也加载角色弧线
        if characters:
            for char in characters:
                if hasattr(char, 'character_arc') and char.character_arc:
                    self.storybible.add_character_arc(char.character_arc)

        logger.info(f"[WritingSupervisor] StoryBible 初始化完成: {self.storybible.summary()}")

    async def review(self, chapter: str, chapter_index: int) -> ReviewResult:
        """审查章节，返回修改建议

        Args:
            chapter: 章节内容
            chapter_index: 章节索引

        Returns:
            ReviewResult: 包含质量评分、是否需要修订、具体修改建议
        """
        start_time = time.time()
        logger.info(f"[WritingSupervisor] 开始审查第 {chapter_index+1} 章")

        # 确保 thinking_logger 在 ContextVar 中已初始化
        # 这样 SubAgent 的 _call_llm 才能正确记录日志
        from src.thinking_logger import get_logger, _logger_var
        if _logger_var.get() is None:
            _logger_var.set(self.thinking_logger)
            logger.info(f"[WritingSupervisor] thinking_logger 已初始化，输出目录: {self.thinking_logger.output_dir}")

        # 1. 获取 StoryBible 上下文
        context_text = self.storybible.format_layered_context(chapter_index)

        # 2. 并行执行 4 个检查型 SubAgents
        try:
            check_results = await asyncio.gather(
                *[agent.check(chapter, context_text, chapter_index) for agent in self.check_agents],
                return_exceptions=True
            )

            # 处理异常结果
            valid_results = []
            for i, result in enumerate(check_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"[WritingSupervisor] {self.check_agents[i].agent_name} 执行失败: {result}"
                    )
                else:
                    valid_results.append(result)

            logger.info(
                f"[WritingSupervisor] 4 个检查 Agent 完成，{len(valid_results)} 个有效结果"
            )

        except Exception as e:
            logger.error(f"[WritingSupervisor] SubAgents 并行执行失败: {e}")
            valid_results = []

        # 3. ReflectionChecker 综合所有结果，给出最终评估
        try:
            final_result = await self.reflection_agent.evaluate(
                chapter=chapter,
                chapter_index=chapter_index,
                check_results=valid_results,
                context_text=context_text
            )
        except Exception as e:
            logger.error(f"[WritingSupervisor] ReflectionChecker 评估失败: {e}")
            final_result = ReviewResult(
                chapter_index=chapter_index,
                needs_revision=False,
                suggestions=[],
                reasoning=f"评估失败: {e}",
                execution_time=time.time() - start_time,
                quality_score=5.0
            )

        # 4. 无论是否需要修订，都更新 StoryBible（SubAgents 可能提取了新的世界状态/角色弧线/伏笔）
        if valid_results:
            self.storybible.update_from_sub_agent_reports(chapter_index, valid_results)
            logger.info(f"[WritingSupervisor] StoryBible 已更新（{len(valid_results)} 个报告）")

        elapsed = time.time() - start_time
        logger.info(
            f"[WritingSupervisor] 第 {chapter_index+1} 章审查完成: "
            f"质量评分={final_result.quality_score:.1f}, "
            f"需要修订={final_result.needs_revision}, "
            f"耗时={elapsed:.1f}s"
        )

        return final_result

    def get_story_bible(self) -> StoryBible:
        """获取 StoryBible 实例"""
        return self.storybible

    def get_revision_context(self, chapter_index: int) -> Dict[str, Any]:
        """获取用于修订的上下文

        Args:
            chapter_index: 章节索引

        Returns:
            Dict containing revision context with revision_requests
        """
        # 获取当前章节的未解决伏笔和逾期伏笔
        unresolved_threads = self.storybible.get_unresolved_plot_threads()
        overdue_threads = self.storybible.get_overdue_plot_threads(chapter_index)

        # 获取角色弧线状态
        character_arcs = {}
        for name, arc in self.storybible._character_arcs.items():
            character_arcs[name] = {
                "current_stage": arc.current_stage_index,
                "emotional_state": arc.emotional_state,
            }

        # 获取世界状态
        latest_world_state = self.storybible.get_latest_world_state()

        return {
            "chapter_index": chapter_index,
            "revision_requests": [
                {
                    "id": f"plot_thread_{t.id}",
                    "chapter_index": chapter_index,
                    "revision_type": "plot_thread",
                    "priority": "high" if t.is_overdue(chapter_index) else "medium",
                    "description": f"伏笔 '{t.name}' 逾期未回收",
                    "suggestions": [f"考虑在近期章节中回收该伏笔"]
                }
                for t in overdue_threads
            ] + [
                {
                    "id": f"arc_{name}",
                    "chapter_index": chapter_index,
                    "revision_type": "character_arc",
                    "priority": "medium",
                    "description": f"角色 '{name}' 当前处于第 {arc['current_stage']} 阶段",
                    "suggestions": [f"角色弧线进展需在近期推进"]
                }
                for name, arc in character_arcs.items()
            ],
            "unresolved_plot_threads_count": len(unresolved_threads),
            "overdue_plot_threads_count": len(overdue_threads),
            "character_arcs": character_arcs,
            "latest_world_state": latest_world_state,
        }