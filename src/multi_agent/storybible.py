"""
StoryBible - 清晰的世界观管理类

重构自 SharedBlackboard，分离世界观管理职责。
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.model import (
    PlotThread, CharacterArc, WorldState, WorldRule,
    EntityContent, StoryBibleContent, NovelOutline
)

logger = logging.getLogger(__name__)


class StoryBible:
    """清晰的世界观管理类"""

    def __init__(self):
        self._character_arcs: Dict[str, CharacterArc] = {}
        self._plot_threads: Dict[str, PlotThread] = {}
        self._world_states: List[WorldState] = []
        self._world_rules: List[WorldRule] = []
        self._entities: List[EntityContent] = []

    def load_from_outline(self, outline: NovelOutline) -> None:
        """从大纲初始化 StoryBible"""
        logger.info(f"[StoryBible] 从大纲初始化: {outline.title}")

        # 加载角色弧线
        if hasattr(outline, 'character_arcs') and outline.character_arcs:
            for arc in outline.character_arcs:
                self.add_character_arc(arc)
        elif hasattr(outline, 'characters') and outline.characters:
            # 如果没有角色弧线，从角色列表初始化
            for char_name in outline.characters:
                arc = CharacterArc(
                    name=char_name,
                    arc_stages=[],
                    current_stage_index=0,
                    emotional_state="",
                    key_moments=[],
                    relationships={}
                )
                self.add_character_arc(arc)

        # 加载情节线
        if hasattr(outline, 'plot_threads') and outline.plot_threads:
            for thread in outline.plot_threads:
                self.add_plot_thread(thread)
        elif hasattr(outline, 'chapters') and outline.chapters:
            # 从章节大纲中提取情节线
            for i, chapter in enumerate(outline.chapters):
                if hasattr(chapter, 'key_events') and chapter.key_events:
                    thread = PlotThread(
                        id=f"plot_thread_{i+1}",
                        name=f"情节线 {i+1}",
                        status="foreshadowed" if i < len(outline.chapters) // 2 else "active",
                        setup_chapter=i+1,
                        key_events=chapter.key_events,
                        description=chapter.summary if hasattr(chapter, 'summary') else ""
                    )
                    self.add_plot_thread(thread)

        logger.info(
            f"[StoryBible] 初始化完成: "
            f"{len(self._character_arcs)} 个角色弧线, "
            f"{len(self._plot_threads)} 个情节线"
        )

    def load_from_content(self, content: StoryBibleContent) -> None:
        """从 StoryBibleContent 加载"""
        # 角色弧线
        for arc in content.character_arcs:
            self._character_arcs[arc.name] = arc

        # 情节线
        for thread in content.plot_threads:
            self._plot_threads[thread.id] = thread

        # 世界状态
        self._world_states = content.world_states.copy()

        # 世界规则
        self._world_rules = content.world_rules.copy()

        # 实体
        self._entities = content.entities.copy()

    def to_content(self) -> StoryBibleContent:
        """导出为 StoryBibleContent"""
        return StoryBibleContent(
            plot_threads=list(self._plot_threads.values()),
            character_arcs=list(self._character_arcs.values()),
            world_states=self._world_states.copy(),
            world_rules=self._world_rules.copy(),
            entities=self._entities.copy(),
            last_updated=datetime.now()
        )

    # ==================== 角色弧线 ====================

    def add_character_arc(self, arc: CharacterArc) -> None:
        """添加角色弧线"""
        self._character_arcs[arc.name] = arc
        logger.debug(f"[StoryBible] 添加角色弧线: {arc.name}")

    def get_character_arc(self, name: str) -> Optional[CharacterArc]:
        """获取角色弧线"""
        return self._character_arcs.get(name)

    def update_character_arc(self, arc: CharacterArc) -> None:
        """更新角色弧线"""
        if arc.name in self._character_arcs:
            self._character_arcs[arc.name] = arc
            logger.debug(f"[StoryBible] 更新角色弧线: {arc.name}")

    def get_all_character_arcs(self) -> Dict[str, CharacterArc]:
        """获取所有角色弧线"""
        return self._character_arcs.copy()

    # ==================== 情节线/伏笔 ====================

    def add_plot_thread(self, thread: PlotThread) -> None:
        """添加情节线"""
        self._plot_threads[thread.id] = thread
        logger.debug(f"[StoryBible] 添加情节线: {thread.name}")

    def get_plot_thread(self, thread_id: str) -> Optional[PlotThread]:
        """获取情节线"""
        return self._plot_threads.get(thread_id)

    def get_active_plot_threads(self) -> List[PlotThread]:
        """获取活跃的情节线"""
        return [t for t in self._plot_threads.values() if t.is_active()]

    def get_unresolved_plot_threads(self) -> List[PlotThread]:
        """获取未解决的情节线（伏笔）"""
        return [t for t in self._plot_threads.values() if not t.is_resolved()]

    def get_overdue_plot_threads(self, current_chapter: int) -> List[PlotThread]:
        """获取逾期未回收的伏笔"""
        return [t for t in self._plot_threads.values() if t.is_overdue(current_chapter)]

    def resolve_plot_thread(self, thread_id: str, payoff_chapter: int) -> None:
        """标记伏笔为已回收"""
        thread = self._plot_threads.get(thread_id)
        if thread:
            thread.status = "resolved"
            thread.payoff_chapter = payoff_chapter
            thread.actual_payoff_chapter = payoff_chapter
            logger.info(f"[StoryBible] 伏笔已回收: {thread.name} (在第{payoff_chapter}章)")
        else:
            logger.warning(f"[StoryBible] 尝试回收未知伏笔: {thread_id}")

    # ==================== 世界状态 ====================

    def append_world_state(self, state: WorldState) -> None:
        """追加世界状态"""
        self._world_states.append(state)
        logger.debug(f"[StoryBible] 追加世界状态: 第{state.chapter_index}章")

    def get_latest_world_state(self) -> Optional[WorldState]:
        """获取最新的世界状态"""
        return self._world_states[-1] if self._world_states else None

    def get_world_states_in_range(self, start: int, end: int) -> List[WorldState]:
        """获取指定章节范围的世界状态"""
        return [s for s in self._world_states if start <= s.chapter_index <= end]

    # ==================== 世界规则 ====================

    def add_world_rule(self, rule: WorldRule) -> None:
        """添加世界规则"""
        self._world_rules.append(rule)

    def check_world_rule_violations(self, content: str, context: Dict = None) -> List[Dict]:
        """检查内容是否违反世界规则"""
        violations = []
        for rule in self._world_rules:
            if rule.check(content, context):
                violations.append({
                    "rule": rule,
                    "severity": rule.severity
                })
        return violations

    # ==================== 实体 ====================

    def append_entity(self, entity: EntityContent) -> None:
        """追加实体"""
        self._entities.append(entity)

    def get_all_entities(self) -> List[EntityContent]:
        """获取所有实体"""
        return self._entities.copy()

    def get_entities_for_chapter(self, chapter_index: int) -> List[EntityContent]:
        """获取指定章节的实体"""
        return [e for e in self._entities if e.chapter_index == chapter_index]

    # ==================== 上下文获取 ====================

    def get_context_for_chapter(self, chapter_index: int) -> Dict[str, Any]:
        """获取章节写作所需的上下文"""
        return {
            "character_arcs": self._character_arcs,
            "plot_threads": self._plot_threads,
            "latest_world_state": self.get_latest_world_state(),
            "world_states": self._world_states,
            "unresolved_plot_threads": self.get_unresolved_plot_threads(),
            "chapter_index": chapter_index
        }

    # ==================== 更新机制 ====================

    def update_from_sub_agent_reports(
        self,
        chapter_index: int,
        reports: List[Any]
    ) -> None:
        """根据 SubAgent 报告更新 StoryBible

        Args:
            chapter_index: 当前章节索引
            reports: SubAgentReport 列表
        """
        for report in reports:
            # 更新角色弧线
            if report.category.value == "character_arc":
                for update in report.updates:
                    if update.get("action") == "advance_arc":
                        char_name = update.get("character")
                        arc = self.get_character_arc(char_name)
                        if arc:
                            arc.advance_stage()
                            self.update_character_arc(arc)

            # 更新世界状态
            elif report.category.value == "world_state":
                for update in report.updates:
                    if update.get("type") == "world_state_update":
                        state = update.get("state")
                        if state:
                            self.append_world_state(state)

            # 更新伏笔/情节线
            elif report.category.value == "plot_thread":
                for update in report.updates:
                    if update.get("action") == "payoff":
                        # 伏笔已回收，标记为解决
                        thread_id = update.get("thread_id")
                        if thread_id:
                            self.resolve_plot_thread(thread_id, chapter_index)

    def summary(self) -> str:
        """获取 StoryBible 摘要"""
        return (
            f"StoryBible: "
            f"{len(self._character_arcs)} 个角色弧线, "
            f"{len(self._plot_threads)} 个情节线, "
            f"{len(self._world_states)} 个世界状态, "
            f"{len(self._world_rules)} 个世界规则, "
            f"{len(self._entities)} 个实体"
        )