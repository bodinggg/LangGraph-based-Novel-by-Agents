
from pydantic import BaseModel
from typing import List, Optional, Any, Literal, Dict
from datetime import datetime

# 角色关系模型
class CharacterRelationship(BaseModel):
    """角色关系模型"""
    source: str  # 源角色名
    target: str  # 目标角色名
    relationship_type: str  # 关系类型：如"父子"、"兄弟"、"恋人"、"敌对"、"朋友"、"师生"等
    description: str  # 关系描述
    events: List[str] = []  # 体现关系的事件列表

# 定义角色数据模型，继承BaseModel实现数据验证功能
class Character(BaseModel):
    name: str               # 角色的姓名
    background: str         # 角色的背景故事（如出身、经历等）
    personality: str        # 角色的性格特点（如外向、谨慎等）
    goals: List[str]        # 角色的目标列表（如追求正义、寻找真相等）
    conflicts: List[str]    # 角色面临的冲突列表（如内心矛盾、外部对抗等）
    arc: str                # 角色的成长弧线（故事中角色的变化与发展轨迹）
    relationships: List[CharacterRelationship] = []  # 与其他角色的关系列表

# 工作流检查点模型
class WorkflowCheckpoint(BaseModel):
    """工作流检查点模型 - 用于断点续传"""
    workflow_id: str
    novel_title: str  # 用于恢复时加载 NovelStorage
    saved_at: datetime
    current_chapter_index: int = 0
    completed_chapters: List[int] = []  # 已完成章节索引列表
    current_node: str = ""  # 当前执行到的节点名
    # 可序列化的状态字段
    user_intent: str = ""
    min_chapters: int = 10
    raw_outline: Optional[str] = None
    raw_master_outline: Optional[str] = None
    validated_chapters: List[Any] = []  # ChapterOutline 列表
    row_characters: Optional[str] = None
    validated_characters: List[Any] = []  # Character 列表

# 定义章节大纲数据模型，用于结构化章节的核心要素
class ChapterOutline(BaseModel):
    title: str              # 章节的标题
    summary: str            # 章节的内容摘要
    key_events: List[str]   # 章节中的关键事件列表
    characters_involved: List[str]  # 章节中涉及的角色名称列表
    setting: str            # 章节发生的场景设定（如地点、时间等）

# 卷册数据模型
class VolumeOutline(BaseModel):
    title: str                      # 卷册标题
    chapters_range: str             # 章节范围（如"1-30"）
    theme: str                      # 卷册主题
    key_turning_points: List[str]   # 卷内关键转折点

# 定义小说大纲数据模型，用于整体规划小说的核心要素
class NovelOutline(BaseModel):
    title: str              # 小说的标题
    genre: str              # 小说的类型（如科幻、悬疑、爱情等）
    theme: str              # 小说的核心主题（如人性、自由、成长等）
    setting: str            # 小说的整体场景设定（如时代背景、世界架构等）
    plot_summary: str       # 小说的情节概要
    master_outline: Optional[List[VolumeOutline]]=None  # 总纲（卷册划分）
    chapters: List[Optional[ChapterOutline]]  # 小说包含的所有章节大纲列表
    characters: List[str]  # 小说中所有角色的名称列表


    


# 定义章节内容数据模型，用于结构化章节的具体内容
class ChapterContent(BaseModel):
    title: str              # 章节的标题
    content: str            # 章节的具体文本内容
    notes: str = ""  # 可选的章节注释，用于记录写作思路或后续修改建议（默认值为空字符串）

# 结构化反馈项模型
class FeedbackItem(BaseModel):
    category: Literal['plot', 'character', 'style', 'dialogue', 'pacing', 'description', 'logic']  # 反馈类别：plot/character/style/dialogue/pacing/description/logic
    priority: str                   # 优先级：high/medium/low
    issue: str                      # 具体问题描述
    suggestion: str                 # 改进建议
    location: Optional[str] = None  # 问题位置（段落或句子描述）

# 章节质量评估模型，用于量化和描述章节内容的质量
class QualityEvaluation(BaseModel):
    score: int              # 章节质量评分（范围1-10分）
    passes: bool            # 章节质量是否达标（True为达标，False为不达标）
    length_check: bool      # 章节长度是否符合要求（True为符合，False为不符合）
    
    # 结构化反馈内容
    feedback_items: List[FeedbackItem] = []  # 具体的反馈项列表
    overall_feedback: str = ""               # 整体评价总结
    
    # 各维度评分（用于更细粒度的评估）
    plot_score: Optional[int] = None         # 情节评分（1-10）
    character_score: Optional[int] = None    # 角色评分（1-10）
    style_score: Optional[int] = None        # 文笔评分（1-10）
    pacing_score: Optional[int] = None       # 节奏评分（1-10）

    @classmethod
    def from_supervisor_result(cls, supervisor_result: "SupervisorResult") -> "QualityEvaluation":
        """Create QualityEvaluation from SupervisorResult (from multi_agent/supervisor.py)"""
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from src.multi_agent.supervisor import SupervisorResult

        feedback_items = []

        # Convert consistency_issues → FeedbackItem(category='logic')
        for issue in supervisor_result.consistency_issues:
            if isinstance(issue, dict):
                feedback_items.append(FeedbackItem(
                    category='logic',
                    priority='high',
                    issue=issue.get('description', str(issue)),
                    suggestion=issue.get('suggestion', '请修正一致性问题'),
                    location=issue.get('location')
                ))
            else:
                feedback_items.append(FeedbackItem(
                    category='logic',
                    priority='high',
                    issue=str(issue),
                    suggestion='请修正一致性问题'
                ))

        # Convert character_updates → FeedbackItem(category='character')
        for update in supervisor_result.character_updates:
            if isinstance(update, dict):
                feedback_items.append(FeedbackItem(
                    category='character',
                    priority='medium',
                    issue=str(update.get('description', update)),
                    suggestion='更新角色弧线'
                ))
            else:
                feedback_items.append(FeedbackItem(
                    category='character',
                    priority='medium',
                    issue=str(update),
                    suggestion='更新角色弧线'
                ))

        # Convert plot_thread_updates → FeedbackItem(category='plot')
        for update in supervisor_result.plot_thread_updates:
            if isinstance(update, dict):
                feedback_items.append(FeedbackItem(
                    category='plot',
                    priority='medium',
                    issue=str(update.get('description', update)),
                    suggestion='更新情节线'
                ))

        # Determine passes based on revision_needed
        passes = not supervisor_result.revision_needed
        score = 8 if passes else 5

        return cls(
            score=score,
            passes=passes,
            length_check=True,
            feedback_items=feedback_items,
            overall_feedback=supervisor_result.revision_notes or ""
        )

    @classmethod
    def from_feedback_items(cls, items: List[FeedbackItem], score: int = 7,
                           passes: bool = True, length_check: bool = True) -> "QualityEvaluation":
        """Create QualityEvaluation from a list of FeedbackItems"""
        return cls(
            score=score,
            passes=passes,
            length_check=length_check,
            feedback_items=items,
            overall_feedback=""
        )

    @classmethod
    def from_review_result(cls, review_result: "ReviewResult") -> "QualityEvaluation":
        """Create QualityEvaluation from ReviewResult (from multi_agent/types.py)"""
        from src.multi_agent.types import CheckCategory

        # 映射 CheckCategory 到 FeedbackItem category
        def map_to_feedback_category(cat: CheckCategory) -> str:
            mapping = {
                CheckCategory.CONSISTENCY: "logic",      # 一致性问题映射到 logic
                CheckCategory.CHARACTER_ARC: "character", # 角色弧线映射到 character
                CheckCategory.PLOT_THREAD: "plot",        # 伏笔映射到 plot
                CheckCategory.WORLD_STATE: "description", # 世界状态映射到 description
                CheckCategory.QUALITY: "style",          # 质量问题映射到 style
            }
            return mapping.get(cat, "logic")

        feedback_items = []
        for sug in review_result.suggestions:
            feedback_items.append(FeedbackItem(
                category=map_to_feedback_category(sug.category),
                priority=sug.priority.value,
                issue=sug.issue,
                suggestion=sug.suggested_change,
                location=sug.location
            ))

        return cls(
            score=int(review_result.quality_score),
            passes=not review_result.needs_revision,
            length_check=True,
            feedback_items=feedback_items,
            overall_feedback=review_result.reasoning or ("无需修订" if not review_result.needs_revision else "需要修订")
        )

    @classmethod
    def from_council_decision(cls, decision: "CouncilDecision") -> "QualityEvaluation":
        """Create QualityEvaluation from CouncilDecision (from multi_agent/council.py)"""
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from src.multi_agent.council import CouncilDecision

        feedback_items = []

        if decision.decision == "revise":
            feedback_items.append(FeedbackItem(
                category='logic',
                priority='high',
                issue=f"需要修订: {decision.reasoning}",
                suggestion='; '.join(decision.follow_up_actions) if decision.follow_up_actions else '根据各方意见修订'
            ))
        elif decision.decision == "reject":
            feedback_items.append(FeedbackItem(
                category='logic',
                priority='high',
                issue=f"拒绝: {decision.reasoning}",
                suggestion='返回写作节点重新构思'
            ))

        return cls(
            score=9 if decision.decision == "approve" else 5,
            passes=decision.decision == "approve",
            length_check=True,
            feedback_items=feedback_items,
            overall_feedback=decision.reasoning
        )


class EntityContent(BaseModel):
    """当前章节实体信息"""
    characters : Any    # 角色相关内容
    organizations : Any # 组织相关内容
    locations : Any     # 地点相关内容
    events : Any        # 事件相关内容
    entities: Any       # 其他实体相关内容


# ============== StoryBible Models ==============

class PlotThread(BaseModel):
    """情节线跟踪模型"""
    id: str                          # 唯一标识
    name: str                        # 情节线名称（如"主情节线A"、"支线B"）
    status: str                      # 状态: "active" | "resolved" | "foreshadowed"
    setup_chapter: int              # 首次出现章节
    payoff_chapter: Optional[int] = None  # 回收章节（如果已回收）
    key_events: List[str] = []      # 关键事件列表
    description: str = ""            # 描述
    # 伏笔跟踪增强
    introduced_chapter: int = 0      # 首次出现章节（与 setup_chapter 重复但更明确）
    expected_payoff_range: str = ""  # 预期回收章节范围，如 "5-10"
    actual_payoff_chapter: Optional[int] = None  # 实际回收章节，None=未回收
    foreshadow_keywords: List[str] = []  # 伏笔关键词列表

    def is_active(self) -> bool:
        return self.status == "active"

    def is_resolved(self) -> bool:
        return self.status == "resolved"

    def is_foreshadowed(self) -> bool:
        return self.status == "foreshadowed"

    def is_overdue(self, current_chapter: int) -> bool:
        """检查伏笔是否逾期未回收"""
        if not self.is_foreshadowed() or not self.expected_payoff_range:
            return False
        try:
            # 解析范围 "5-10" -> 取最大值
            parts = self.expected_payoff_range.split("-")
            if len(parts) == 2:
                max_expected = int(parts[1].strip())
                return current_chapter > max_expected
        except (ValueError, IndexError):
            pass
        return False


class CharacterArcStage(BaseModel):
    """角色弧线阶段"""
    stage_name: str                 # 阶段名称（如"迷茫"、"觉醒"、"成长"）
    chapter_range: str              # 章节范围（如"1-5"）
    emotional_state: str            # 该阶段情感状态
    key_moment: str                 # 关键转折时刻


class CharacterArc(BaseModel):
    """角色成长弧线模型"""
    name: str                        # 角色名
    arc_stages: List[CharacterArcStage] = []  # 弧线阶段列表
    current_stage_index: int = 0     # 当前阶段索引
    emotional_state: str = ""         # 当前情感状态
    key_moments: List[str] = []      # 关键时刻列表
    relationships: Dict[str, str] = {}  # 关系变化 {角色名: 关系描述}

    def get_current_stage(self) -> Optional[CharacterArcStage]:
        if 0 <= self.current_stage_index < len(self.arc_stages):
            return self.arc_stages[self.current_stage_index]
        return None

    def advance_stage(self):
        """推进到下一阶段"""
        if self.current_stage_index < len(self.arc_stages) - 1:
            self.current_stage_index += 1


class WorldState(BaseModel):
    """世界状态模型"""
    chapter_index: int              # 对应章节
    location: str                   # 当前地点
    time: str                       # 时间线描述
    active_factions: List[str] = [] # 活跃势力
    weather: str = ""               # 天气
    mood: str = ""                  # 氛围
    description: str = ""           # 描述


class WorldRule(BaseModel):
    """世界规则定义 - 用于验证小说内容是否符合世界观设定"""
    rule_type: str  # 规则类型:
                    # - "ability_constraint": 能力约束（如平衡者不能穿越时间）
                    # - "geographic_limit": 地理限制（如某地不能到达）
                    # - "faction_relationship": 势力关系（如某两势力是敌对）
                    # - "character_limit": 角色能力边界
                    # - "world_fact": 世界事实（如埃拉西亚有2个月亮）
    subject: str     # 规则主体（如"平衡者"、"埃拉西亚"、"长老会"）
    predicate: str   # 谓词: "不能" | "只能" | "必须" | "是"
    object: str      # 规则对象（如"穿越时间"、"去现实世界"）
    description: str  # 规则描述
    severity: str = "error"  # 严重程度: "error" | "warning"
    source_chapter: int = 0  # 规则首次出现的章节（用于追溯）

    def check(self, content: str, current_context: dict = None) -> bool:
        """
        检查内容是否违反此规则

        Args:
            content: 要检查的内容
            current_context: 当前上下文，包含 location、character 等信息

        Returns:
            True 如果违反规则
        """
        content_lower = content.lower()
        subject_lower = self.subject.lower()
        object_lower = self.object.lower()

        # 如果 subject 不在内容中，直接返回 False
        if subject_lower not in content_lower:
            return False

        # 能力约束检查
        if self.rule_type == "ability_constraint":
            # 检查是否有能力相关的违反表述
            # 关键词：穿越、能够、可以、试图、决定、尝试
            ability_keywords = ["穿越", "时间旅行", "回到过去", "前往未来"]
            ability_found = any(kw in content_lower for kw in ability_keywords)

            if ability_found and object_lower in content_lower:
                # subject 出现在能体现某种"能力"的内容中
                return True

        # 地理限制检查
        elif self.rule_type == "geographic_limit":
            # 检查 subject 是否在被禁止的地点
            forbidden_keywords = ["进入", "抵达", "来到", "试图"]
            location_found = object_lower in content_lower
            access_attempt = any(kw in content_lower for kw in forbidden_keywords)

            if location_found and access_attempt:
                return True

        # 世界事实检查
        elif self.rule_type == "world_fact":
            # 检查是否出现与事实矛盾的描述
            if self.predicate == "有":
                # 提取 object 中的核心名词（去掉数量词）
                # object_lower = "2个月亮" -> "月亮"
                # 尝试提取核心词
                object_core = object_lower
                for num_word in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "个", "颗"]:
                    object_core = object_core.replace(num_word, "")

                # 检查内容中是否有"只有一"或"唯一"等暗示只有一个的描述
                # 且同时提到了 subject
                if subject_lower in content_lower:
                    if "只有一" in content_lower or "唯一" in content_lower or "仅有一" in content_lower:
                        # 检查核心名词是否匹配（月亮 vs 明月）
                        if "月亮" in object_lower and ("月亮" in content_lower or "明月" in content_lower):
                            return True
                    # 检查是否有"没有"等否定
                    for neg in ["没有", "不存在"]:
                        if neg in content_lower and ("月亮" in object_lower or "月" in content_lower):
                            return True

        # 势力关系检查
        elif self.rule_type == "faction_relationship":
            # 检查是否有矛盾的势力关系描述
            if object_lower in content_lower:
                return True

        return False


class WorldRuleSet(BaseModel):
    """世界规则集合 - 存储一部小说的所有规则"""
    novel_title: str = ""
    rules: List[WorldRule] = []

    def add_rule(self, rule: WorldRule) -> None:
        """添加规则，自动检测冲突"""
        # 简单的冲突检测：同类型、同主体的规则
        conflicts = self.find_conflicts(rule)
        if conflicts:
            # 返回冲突信息但不阻止添加
            return conflicts
        self.rules.append(rule)
        return None

    def find_conflicts(self, rule: WorldRule) -> List[str]:
        """查找与新规则冲突的现有规则"""
        conflicts = []
        for existing in self.rules:
            if (existing.subject == rule.subject and
                existing.rule_type == rule.rule_type and
                existing.predicate != rule.predicate):
                conflicts.append(
                    f"潜在冲突: {existing.description} vs {rule.description}"
                )
        return conflicts

    def check_violation(self, content: str, context: dict = None) -> List[dict]:
        """检查内容是否违反任何规则"""
        violations = []
        for rule in self.rules:
            if rule.check(content, context):
                violations.append({
                    "rule": rule,
                    "severity": rule.severity,
                    "description": f"违反世界规则: {rule.description}"
                })
        return violations

    def get_rules_for_subject(self, subject: str) -> List[WorldRule]:
        """获取指定主体的所有规则"""
        return [r for r in self.rules if r.subject == subject]

    def get_rules_by_type(self, rule_type: str) -> List[WorldRule]:
        """获取指定类型的所有规则"""
        return [r for r in self.rules if r.rule_type == rule_type]


class StoryBibleEntry(BaseModel):
    """StoryBible条目模型"""
    id: str                          # 唯一标识
    chapter_index: int               # 章节索引
    entry_type: str                 # 类型: "entity" | "plot_thread" | "character_arc" | "world_state"
    data: Any                       # 对应数据（PlotThread | CharacterArc | WorldState | EntityContent）
    created_at: datetime             # 创建时间
    updated_at: datetime             # 更新时间

    def get_type(self) -> str:
        return self.entry_type


class ConsistencyNote(BaseModel):
    """一致性备注"""
    id: str                          # 唯一标识
    issue_type: str                  # 问题类型: "contradiction" | "warning" | "info"
    description: str                 # 描述
    related_chapters: List[int] = []  # 涉及章节
    resolved: bool = False           # 是否已解决
    created_at: Optional[datetime] = None


class StoryBibleContent(BaseModel):
    """StoryBible内容模型 - 多Agent共享知识库"""
    novel_title: str = ""           # 小说标题

    # 情节线
    plot_threads: List[PlotThread] = []

    # 角色弧线
    character_arcs: List[CharacterArc] = []

    # 世界状态历史
    world_states: List[WorldState] = []

    # 世界规则
    world_rules: List[WorldRule] = []

    # 实体信息
    entities: List[EntityContent] = []

    # 一致性备注
    consistency_notes: List[ConsistencyNote] = []

    # 未解伏笔
    unresolved_threads: List[str] = []  # PlotThread.id 列表

    # 最后更新时间
    last_updated: datetime = None

    def get_active_plot_threads(self) -> List[PlotThread]:
        """获取活跃情节线"""
        return [t for t in self.plot_threads if t.is_active()]

    def get_unresolved_plot_threads(self) -> List[PlotThread]:
        """获取未解伏笔"""
        return [t for t in self.plot_threads if t.status == "foreshadowed"]

    def get_character_arc(self, name: str) -> Optional[CharacterArc]:
        """获取指定角色弧线"""
        for arc in self.character_arcs:
            if arc.name == name:
                return arc
        return None

    def get_latest_world_state(self) -> Optional[WorldState]:
        """获取最新世界状态"""
        if self.world_states:
            return self.world_states[-1]
        return None

    def add_consistency_note(self, note: ConsistencyNote):
        """添加一致性备注"""
        self.consistency_notes.append(note)

    def resolve_consistency_note(self, note_id: str):
        """标记一致性备注为已解决"""
        for note in self.consistency_notes:
            if note.id == note_id:
                note.resolved = True
                break

    def add_world_rule(self, rule: WorldRule) -> None:
        """添加世界规则"""
        self.world_rules.append(rule)

    def get_world_rules(self) -> List[WorldRule]:
        """获取所有世界规则"""
        return self.world_rules

    def get_rules_for_subject(self, subject: str) -> List[WorldRule]:
        """获取指定主体的规则"""
        return [r for r in self.world_rules if r.subject == subject]

    def check_world_rule_violations(self, content: str, context: dict = None) -> List[dict]:
        """检查内容是否违反世界规则"""
        violations = []
        for rule in self.world_rules:
            if rule.check(content, context):
                violations.append({
                    "rule": rule,
                    "severity": rule.severity,
                    "description": f"违反世界规则: {rule.description}"
                })
        return violations

    def get_overdue_foreshadows(self, current_chapter: int) -> List[PlotThread]:
        """获取逾期未回收的伏笔"""
        overdue = []
        for thread in self.plot_threads:
            if thread.is_overdue(current_chapter):
                overdue.append(thread)
        return overdue
