"""
Agent 基类和配置定义

定义 Agent 的标准接口，支持同步/异步两种生成方式。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from src.model_manager import ModelManager
from src.config_loader import BaseConfig


class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    description: str = ""
    enabled: bool = True


class BaseAgent(ABC):
    """Agent 抽象基类

    所有 Agent 必须继承此类。
    子类应实现 generate 和 async_generate 方法（如果适用）。
    """

    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        """
        Args:
            model_manager: 模型管理器实例
            config: Agent 配置
        """
        self.model_manager = model_manager
        self.config = config

    def generate(self, *args, **kwargs) -> str:
        """同步生成（默认实现调用 async_generate）"""
        import asyncio
        return asyncio.run(self.async_generate(*args, **kwargs))

    async def async_generate(self, *args, **kwargs) -> str:
        """异步生成（默认实现）"""
        raise NotImplementedError(f"{self.__class__.__name__} must implement async_generate")

    @property
    def name(self) -> str:
        """Agent 名称"""
        return self.__class__.__name__
