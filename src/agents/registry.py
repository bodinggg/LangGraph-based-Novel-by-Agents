"""
Agent 注册表

提供 Agent 类的注册、获取、列表功能。
支持运行时动态注册和工厂模式。
"""
import logging
import threading
from typing import Dict, Type, List, Optional, Callable

from src.agents.base import BaseAgent, AgentConfig

_logger = logging.getLogger(__name__)


class AgentRegistry:
    """Agent 注册表（线程安全单例模式）

    管理 Agent 类的注册与获取，支持运行时动态注册。
    """

    _agents: Dict[str, Type[BaseAgent]] = {}
    _configs: Dict[str, AgentConfig] = {}
    _lock = threading.Lock()

    @classmethod
    def register(
        cls,
        name: str,
        agent_class: Type[BaseAgent],
        config: Optional[AgentConfig] = None
    ) -> None:
        """注册 Agent 类

        Args:
            name: Agent 名称（唯一标识）
            agent_class: Agent 类（必须继承 BaseAgent）
            config: Agent 配置（可选）
        """
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(f"{agent_class.__name__} must inherit from BaseAgent")

        with cls._lock:
            cls._agents[name] = agent_class
            if config:
                cls._configs[name] = config
            else:
                cls._configs[name] = AgentConfig(name=name)

        _logger.info(f"[AgentRegistry] 注册 Agent: {name} -> {agent_class.__name__}")

    @classmethod
    def get(cls, name: str, **kwargs) -> BaseAgent:
        """获取 Agent 实例

        Args:
            name: Agent 名称
            **kwargs: 传递给 Agent 构造函数的额外参数

        Returns:
            Agent 实例

        Raises:
            KeyError: 如果 Agent 未注册
        """
        with cls._lock:
            if name not in cls._agents:
                raise KeyError(f"Agent '{name}' not registered")
            agent_class = cls._agents[name]

        # 每次返回新实例
        return agent_class(**kwargs)

    @classmethod
    def list_agents(cls) -> List[str]:
        """列出所有已注册的 Agent 名称"""
        with cls._lock:
            return list(cls._agents.keys())

    @classmethod
    def get_config(cls, name: str) -> Optional[AgentConfig]:
        """获取 Agent 配置"""
        with cls._lock:
            return cls._configs.get(name)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """检查 Agent 是否已注册"""
        with cls._lock:
            return name in cls._agents

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）"""
        with cls._lock:
            cls._agents.clear()
            cls._configs.clear()


def register_agent(name: str, config: Optional[AgentConfig] = None) -> Callable:
    """装饰器：注册 Agent 类

    Usage:
        @register_agent("outline")
        class OutlineAgent(BaseAgent):
            ...
    """
    def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
        AgentRegistry.register(name, cls, config)
        return cls
    return decorator
