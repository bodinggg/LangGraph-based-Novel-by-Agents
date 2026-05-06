"""
Agent 插件初始化

注册所有内置 Agent。
"""
import logging

from src.agents.base import AgentConfig
from src.agents.registry import AgentRegistry
from src.agent import (
    OutlineGeneratorAgent,
    CharacterAgent,
    WriterAgent,
    ReflectAgent,
    EntityAgent,
)
from src.multi_agent import (
    ConsistencyChecker,
    CharacterArcChecker,
    PlotThreadChecker,
    WorldStateChecker,
)

logger = logging.getLogger(__name__)


def register_builtin_agents():
    """注册所有内置 Agent"""
    agents = [
        ("outline", OutlineGeneratorAgent, "大纲生成代理"),
        ("character", CharacterAgent, "角色档案生成代理"),
        ("writer", WriterAgent, "章节写作代理"),
        ("reflect", ReflectAgent, "章节评估代理"),
        ("entity", EntityAgent, "实体识别代理"),
    ]

    for name, agent_class, description in agents:
        config = AgentConfig(name=name, description=description)
        AgentRegistry.register(name, agent_class, config)
        logger.info(f"[AgentSetup] 注册内置 Agent: {name} ({description})")

    logger.info(f"[AgentSetup] 共注册 {len(agents)} 个内置 Agent")


def register_specialist_agents():
    """注册所有 Specialist Agents（用于可观测性日志）

    新架构中的 SubAgents 由 WritingSupervisor 直接管理，
    这里只是记录日志，表明系统知道有哪些 SubAgents。
    """
    from src.multi_agent import (
        ConsistencyChecker,
        CharacterArcChecker,
        PlotThreadChecker,
        WorldStateChecker,
    )

    # SubAgents 不继承 BaseAgent，不需要注册到 AgentRegistry
    # 只在 WritingSupervisor 初始化时实例化
    # 这里只是记录日志，表明系统知道有哪些 SubAgents
    specialists = [
        ("consistency", ConsistencyChecker, "一致性检查代理"),
        ("character_arc", CharacterArcChecker, "角色弧线跟踪代理"),
        ("plot_thread", PlotThreadChecker, "情节线跟踪代理"),
        ("world_state", WorldStateChecker, "世界状态更新代理"),
    ]

    logger.info("🎯 [AgentSetup] Deep模式注册 Specialist Agents:")
    for name, agent_class, description in specialists:
        logger.info(f"   📖 {name} ({description})")

    logger.info(f"✅ [AgentSetup] 共注册 {len(specialists)} 个 Specialist Agent")


def setup_agents():
    """初始化 Agent 系统（便捷入口）"""
    register_builtin_agents()
    return AgentRegistry
