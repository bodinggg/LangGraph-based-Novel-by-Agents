"""
Base SubAgent - 所有检查型 SubAgent 的基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import time
import json

from src.multi_agent.types import SubAgentReport, CheckCategory
from src.thinking_logger import log_agent_thinking

logger = logging.getLogger(__name__)


class BaseSubAgent(ABC):
    """检查型 SubAgent 的基类"""

    def __init__(self, model_manager=None, agent_name: str = "BaseSubAgent"):
        self.model_manager = model_manager
        self.agent_name = agent_name

    @abstractmethod
    async def check(self, chapter: str, context: Dict[str, Any]) -> SubAgentReport:
        """检查章节内容"""
        pass

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        chapter_index: int,
        require_json: bool = False
    ) -> str:
        """调用 LLM 进行思考

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            chapter_index: 章节索引
            require_json: 是否需要 JSON 输出

        Returns:
            LLM 响应内容
        """
        messages = [{"role": "system", "content": system_prompt}]

        if require_json:
            user_prompt += "\n\n请以 JSON 格式输出，包含 issues 和 reasoning 字段。"

        messages.append({"role": "user", "content": user_prompt})

        # 获取配置（如果有的话）
        config = getattr(self, 'config', None)
        if config is None:
            # 使用默认配置
            from src.config_loader import BaseConfig
            config = BaseConfig()

        # 调用 LLM
        if hasattr(self.model_manager, 'generate'):
            response = self.model_manager.generate(messages, config)
        elif hasattr(self.model_manager, 'async_generate'):
            response = await self.model_manager.async_generate(messages, config)
        else:
            response = "No LLM available"

        # 记录到 thinking_log
        log_agent_thinking(
            agent_name=self.agent_name,
            node_name="check",
            prompt_content=f"【系统提示】\n{system_prompt}\n\n【用户提示】\n{user_prompt}",
            response_content=response,
            chapter_index=chapter_index
        )

        return response

    async def _log_thinking(
        self,
        prompt_content: str,
        response_content: str,
        chapter_index: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """记录思考日志到统一的 thinking_logs

        Args:
            prompt_content: 输入提示
            response_content: 输出响应
            chapter_index: 章节索引（用于文件命名）
            error: 错误信息（可选）
        """
        log_agent_thinking(
            agent_name=self.agent_name,
            node_name="check",
            prompt_content=prompt_content,
            response_content=response_content,
            chapter_index=chapter_index,
            error_message=error
        )

    def _create_report(
        self,
        category: CheckCategory,
        issues: list = None,
        updates: list = None,
        reasoning: str = "",
        confidence: float = 0.5
    ) -> SubAgentReport:
        """创建标准化的 SubAgentReport"""
        return SubAgentReport(
            agent_name=self.agent_name,
            category=category,
            issues=issues or [],
            updates=updates or [],
            reasoning=reasoning,
            confidence=confidence
        )


class ReflectionAgent(ABC):
    """评估型 SubAgent 的基类 - 综合所有检查结果做决策"""

    def __init__(self, model_manager=None, agent_name: str = "ReflectionAgent"):
        self.model_manager = model_manager
        self.agent_name = agent_name

    @abstractmethod
    async def evaluate(
        self,
        chapter: str,
        chapter_index: int,
        check_results: list,  # List[SubAgentReport]
        context: Dict[str, Any]
    ) -> "ReviewResult":
        """
        综合所有 SubAgent 的检查结果，给出最终评估

        Returns:
            ReviewResult: 包含是否需要修订、具体修改建议、决策理由
        """
        pass