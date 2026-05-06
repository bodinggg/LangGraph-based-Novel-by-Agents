"""
Multi-Agent 模块类型定义

重构后的 Supervisor 架构：
- WritingSupervisor: 主调度者
- SubAgents: 4个检查型 + 1个评估型
- StoryBible: 世界观管理
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class CheckCategory(str, Enum):
    """检查类别"""
    CONSISTENCY = "consistency"
    CHARACTER_ARC = "character_arc"
    PLOT_THREAD = "plot_thread"
    WORLD_STATE = "world_state"
    QUALITY = "quality"


class Priority(str, Enum):
    """优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Suggestion:
    """修改建议"""
    category: CheckCategory
    priority: Priority
    issue: str                          # 问题描述
    location: str                      # 位置（如"第3段"）
    current_text: str                   # 当前文本（引用）
    suggested_change: str               # 具体修改建议


@dataclass
class SubAgentReport:
    """SubAgent 检查报告"""
    agent_name: str                     # Agent 名称
    category: CheckCategory            # 检查类别
    issues: List[Dict[str, Any]] = field(default_factory=list)  # 发现的问题
    updates: List[Dict[str, Any]] = field(default_factory=list)  # 更新的数据
    reasoning: str = ""                 # 检查推理过程
    confidence: float = 0.5            # 置信度 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "category": self.category.value,
            "issues": self.issues,
            "updates": self.updates,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass
class ReviewResult:
    """最终审查结果 - 返回给 WriterAgent"""
    chapter_index: int
    needs_revision: bool
    suggestions: List[Suggestion] = field(default_factory=list)  # 具体修改建议
    reasoning: str = ""                                          # 决策理由
    execution_time: float = 0.0
    quality_score: float = 0.0                                   # 质量评分 0-10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "needs_revision": self.needs_revision,
            "suggestions": [
                {
                    "category": s.category.value,
                    "priority": s.priority.value,
                    "issue": s.issue,
                    "location": s.location,
                    "current_text": s.current_text,
                    "suggested_change": s.suggested_change,
                }
                for s in self.suggestions
            ],
            "reasoning": self.reasoning,
            "execution_time": self.execution_time,
            "quality_score": self.quality_score,
        }