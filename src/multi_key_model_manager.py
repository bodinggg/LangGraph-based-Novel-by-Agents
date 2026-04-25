"""
多 Key API 模型管理器

支持多 API Key 并行调用，通过 KeyRouter 实现负载均衡
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import time
import logging
import asyncio
import anthropic
from openai import OpenAI, AsyncOpenAI
from src.config_loader import BaseConfig
from src.multi_key_manager import KeyRouter

logger = logging.getLogger(__name__)


class ModelManager(ABC):
    """模型管理器抽象基类"""

    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """同步生成（兼容现有代码）"""
        pass

    @abstractmethod
    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步生成（用于并行场景）"""
        pass


class LocalModelManager(ModelManager):
    """本地模型管理器"""

    def __init__(self, model_path):
        from transformers import pipeline, AutoTokenizer
        self.tokenzier = AutoTokenizer.from_pretrained(model_path)
        self.pipeline = pipeline(
            "text-generation",
            model=model_path,
            tokenizer=self.tokenzier,
            device=0
        )

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        prompt = self._messages_to_prompt(messages)
        result = self.pipeline(
            prompt,
            max_new_tokens=params.max_new_tokens,
            temperature=params.temperature,
            top_p=params.top_p,
            do_sample=True
        )
        return result[0]["generated_text"][len(prompt):].strip()

    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        return self.generate(messages, params)

    def _messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            else:
                parts.append(f"{role}: {content}")
        return "\n\n".join(parts)


class MultiKeyAPIModelManager(ModelManager):
    """多 Key API 模型管理器

    使用 KeyRouter 实现多 Key 轮询，支持真正的并行请求
    """

    def __init__(
        self,
        api_url: str,
        api_keys: List[str],
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 1,
        api_type: str = "openai",
        max_concurrent_per_key: int = 3
    ):
        """
        Args:
            api_url: API 基础地址
            api_keys: API Key 列表（支持多 Key）
            model_name: 模型名称
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
            api_type: API 类型，"openai" 或 "anthropic"
            max_concurrent_per_key: 每个 Key 的最大并发数
        """
        self.model_name = model_name
        self.api_type = api_type.lower()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.api_url = api_url

        # 创建 KeyRouter
        self.key_router = KeyRouter(
            keys=api_keys,
            max_concurrent_per_key=max_concurrent_per_key,
            enable_stats=True
        )

        # 为每个 key 创建独立的客户端
        self._clients: Dict[str, Any] = {}
        self._async_clients: Dict[str, Any] = {}

        for key in api_keys:
            if self.api_type == "anthropic":
                self._clients[key] = anthropic.Anthropic(api_key=key, base_url=api_url)
                self._async_clients[key] = anthropic.AsyncAnthropic(api_key=key, base_url=api_url)
            else:
                self._clients[key] = OpenAI(api_key=key, base_url=api_url)
                self._async_clients[key] = AsyncOpenAI(api_key=key, base_url=api_url)

        logger.info(f"[MultiKeyAPI] 初始化完成，共 {len(api_keys)} 个 Key，每个 Key 最大并发 {max_concurrent_per_key}")

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """同步生成（使用第一个 Key，兼容现有代码）"""
        key = list(self._clients.keys())[0]
        if self.api_type == "anthropic":
            return self._generate_anthropic_with_key(key, messages, params)
        else:
            return self._generate_openai_with_key(key, messages, params)

    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步生成，通过 KeyRouter 分配 Key"""
        async def _execute_with_key(key: str) -> str:
            return await self._async_generate_with_key(key, messages, params)

        return await self.key_router.execute(_execute_with_key)

    async def _async_generate_with_key(
        self,
        key: str,
        messages: List[Dict[str, Any]],
        params: BaseConfig
    ) -> str:
        """使用指定 Key 异步生成"""
        for attempt in range(self.max_retries):
            try:
                if self.api_type == "anthropic":
                    return await self._async_generate_anthropic_with_key(key, messages, params)
                else:
                    return await self._async_generate_openai_with_key(key, messages, params)
            except Exception as e:
                logger.warning(f"[MultiKeyAPI] Key {key[:8]}... 失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:80]}")
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.info(f"将在 {backoff} 秒后重试...")
                    await asyncio.sleep(backoff)
                else:
                    raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败")

    async def _async_generate_openai_with_key(
        self,
        key: str,
        messages: List[Dict[str, Any]],
        params: BaseConfig
    ) -> str:
        """使用指定 Key 的异步 OpenAI 生成"""
        client = self._async_clients[key]
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_new_tokens
        )

        if not response.choices:
            raise Exception(f"API 返回空 choices")
        if not response.choices[0] or not hasattr(response.choices[0], 'message') or response.choices[0].message is None:
            raise Exception(f"API 返回的 message 为 None")
        content = response.choices[0].message.content
        if content is None:
            raise Exception(f"API 返回的 content 为 None")
        return content

    async def _async_generate_anthropic_with_key(
        self,
        key: str,
        messages: List[Dict[str, Any]],
        params: BaseConfig
    ) -> str:
        """使用指定 Key 的异步 Anthropic 生成"""
        client = self._async_clients[key]

        anthropic_messages = []
        system_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})

        response = await client.messages.create(
            model=self.model_name,
            system=system_prompt,
            messages=anthropic_messages,
            temperature=params.temperature,
            max_tokens=params.max_new_tokens
        )

        if not response.content:
            raise Exception(f"API 返回空 content")

        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text
            elif block.type == "thinking":
                pass
        return result_text.strip()

    def _generate_openai_with_key(self, key: str, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用指定 Key 的同步 OpenAI 生成"""
        client = self._clients[key]
        for attempt in range(self.max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_tokens=params.max_new_tokens
                )
                if not response.choices or not response.choices[0].message:
                    raise Exception(f"API 返回空响应")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败")

    def _generate_anthropic_with_key(self, key: str, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用指定 Key 的同步 Anthropic 生成"""
        client = self._clients[key]
        anthropic_messages = []
        system_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})

        for attempt in range(self.max_retries):
            try:
                response = client.messages.create(
                    model=self.model_name,
                    system=system_prompt,
                    messages=anthropic_messages,
                    temperature=params.temperature,
                    max_tokens=params.max_new_tokens
                )
                if not response.content:
                    raise Exception(f"API 返回空 content")
                result_text = ""
                for block in response.content:
                    if block.type == "text":
                        result_text += block.text
                    elif block.type == "thinking":
                        pass
                return result_text.strip()
            except Exception as e:
                logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败")

    def log_stats(self):
        """打印 Key 使用统计"""
        self.key_router.log_stats()
