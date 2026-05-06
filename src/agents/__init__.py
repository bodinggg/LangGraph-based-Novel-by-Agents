"""
Agent 插件系统

提供 Agent 的抽象基类和注册表，支持运行时动态注册。
"""
from src.agents.base import BaseAgent, AgentConfig
from src.agents.registry import AgentRegistry, register_agent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentRegistry",
    "register_agent",
]


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name in ("register_builtin_agents", "setup_agents"):
        from src.agents import setup
        return getattr(setup, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
