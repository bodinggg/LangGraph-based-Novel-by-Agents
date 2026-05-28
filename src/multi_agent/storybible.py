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
        """分层注入：按变化频率分三层获取章节写作上下文

        Layer 0: 静态约束（整部小说不变，永久缓存）
            - WorldRule（硬规则：角色不能做 X）
            - 世界观设定

        Layer 1: 慢变状态（章节间偶尔变化）
            - CharacterArc 当前阶段
            - 已解决的 PlotThread（归档）

        Layer 2: 快变状态（每章必变）
            - 当前 WorldState（地点、时间）
            - 活跃 PlotThread 状态
            - 本章具体约束

        利用 LLM 的 Primacy Bias，把最重要的硬约束放在 Layer 0，
        既缓存友好，又注意力友好。

        Args:
            chapter_index: 章节索引（0-based）

        Returns:
            Dict: 分层上下文，包含 layer0/layer1/layer2
        """
        return {
            "layer0": {
                "world_rules": self._world_rules.copy(),
            },
            "layer1": {
                "character_arcs": self._character_arcs.copy(),
                "resolved_threads": [t for t in self._plot_threads.values() if t.is_resolved()],
            },
            "layer2": {
                "world_state": self.get_latest_world_state(),
                "active_threads": self.get_active_plot_threads(),
                "unresolved_threads": self.get_unresolved_plot_threads(),
                "chapter_index": chapter_index,
            },
        }

    def format_layered_context(self, chapter_index: int) -> str:
        """将分层上下文格式化为可注入 prompt 的文本

        Args:
            chapter_index: 章节索引（0-based）

        Returns:
            格式化的文本，可直接注入到 WriterAgent 的 prompt 中
        """
        ctx = self.get_context_for_chapter(chapter_index)
        lines = []

        # Layer 0: 静态约束（最重要，放在最前面）
        lines.append("## 世界观规则（硬约束）")
        if ctx["layer0"]["world_rules"]:
            for rule in ctx["layer0"]["world_rules"]:
                severity_marker = "【严重】" if rule.severity == "error" else "【警告】"
                lines.append(f"- {severity_marker}{rule.description}")
        else:
            lines.append("- 无")
        lines.append("")

        # Layer 1: 慢变状态
        lines.append("## 角色状态")
        if ctx["layer1"]["character_arcs"]:
            for name, arc in ctx["layer1"]["character_arcs"].items():
                stage = arc.get_current_stage()
                stage_info = f"当前阶段：{stage.stage_name}" if stage else "无阶段信息"
                lines.append(f"- {name}：{arc.emotional_state} | {stage_info}")
        else:
            lines.append("- 无")

        lines.append("")
        lines.append("## 情节线/伏笔状态")
        if ctx["layer1"]["resolved_threads"]:
            lines.append("已解决：")
            for t in ctx["layer1"]["resolved_threads"]:
                lines.append(f"- [已回收] {t.name}")
        if ctx["layer2"]["active_threads"]:
            lines.append("进行中：")
            for t in ctx["layer2"]["active_threads"]:
                lines.append(f"- [进行] {t.name}")
        if ctx["layer2"]["unresolved_threads"]:
            lines.append("伏笔：")
            for t in ctx["layer2"]["unresolved_threads"]:
                lines.append(f"- [伏笔] {t.name}（预期在第{t.expected_payoff_range}章回收）")
        if not ctx["layer1"]["resolved_threads"] and not ctx["layer2"]["active_threads"] and not ctx["layer2"]["unresolved_threads"]:
            lines.append("- 无")
        lines.append("")

        # Layer 2: 快变状态
        lines.append("## 当前世界状态")
        ws = ctx["layer2"]["world_state"]
        if ws:
            lines.append(f"- 地点：{ws.location}")
            lines.append(f"- 时间：{ws.time}")
            lines.append(f"- 氛围：{ws.mood}")
            if ws.description:
                lines.append(f"- 描述：{ws.description}")
        else:
            lines.append("- 无")

        return "\n".join(lines)

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