"""
Multi-Agent 模块 - 重构后的 Supervisor 架构

重构目标：
- WritingSupervisor: 主调度者（SuperAgent）
- SubAgents: 4个检查型 + 1个评估型
- StoryBible: 世界观管理
"""
# 核心导出
from src.multi_agent.supervisor import WritingSupervisor
from src.multi_agent.storybible import StoryBible
from src.multi_agent.types import (
    ReviewResult,
    Suggestion,
    SubAgentReport,
    CheckCategory,
    Priority,
)

# SubAgents
from src.multi_agent.sub_agents import (
    BaseSubAgent,
    ConsistencyChecker,
    CharacterArcChecker,
    PlotThreadChecker,
    WorldStateChecker,
    ReflectionChecker,
)

__all__ = [
    # 核心类
    "WritingSupervisor",
    "StoryBible",
    "ReviewResult",
    "Suggestion",
    "SubAgentReport",
    "CheckCategory",
    "Priority",
    # SubAgents
    "BaseSubAgent",
    "ConsistencyChecker",
    "CharacterArcChecker",
    "PlotThreadChecker",
    "WorldStateChecker",
    "ReflectionChecker",
]