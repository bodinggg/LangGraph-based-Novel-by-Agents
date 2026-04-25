from abc import ABC, abstractmethod
from transformers import pipeline, AutoTokenizer
from typing import Dict, Any, Optional, List
import time
import logging
import asyncio
import anthropic
from openai import OpenAI, AsyncOpenAI
from src.config_loader import BaseConfig

logger = logging.getLogger(__name__)

# 抽象基类
class ModelManager(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """同步生成（兼容现有代码）"""
        pass

    @abstractmethod
    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步生成（用于并行场景）"""
        pass

# 本地模型管理
class LocalModelManager(ModelManager):

    def __init__(self, model_path):
        self.tokenzier = AutoTokenizer.from_pretrained(model_path)
        self.pipeline = pipeline(
            "text-generation",
            model=model_path,
            tokenizer=self.tokenzier,
            device=0
        )

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        # Convert messages list to a single prompt string for local models
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
        """本地模型的同步转异步实现（无并行收益）"""
        return self.generate(messages, params)

    def _messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Convert a messages list to a single prompt string."""
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

# API调用管理 (支持 OpenAI 和 Anthropic 两种格式)
class APIModelManager(ModelManager):

    def __init__(self, api_url: str, api_key: Optional[str] = None, model_name: Optional[str] = None,
                 max_retries: int = 3, retry_delay: int = 1, api_type: str = "openai",
                 max_concurrent: int = 3):
        """
        初始化 API 模型管理器

        Args:
            api_url: API 基础地址
            api_key: API 密钥
            model_name: 模型名称
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
            api_type: API 类型，"openai" 或 "anthropic"
            max_concurrent: 最大并发数（用于异步并行控制）
        """
        self.model_name = model_name
        self.api_type = api_type.lower()
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 同步客户端（保留用于向后兼容）
        if self.api_type == "anthropic":
            self.client = anthropic.Anthropic(api_key=api_key, base_url=api_url)
        else:
            self.client = OpenAI(api_key=api_key, base_url=api_url)

        # 异步客户端（用于并行场景）
        if self.api_type == "anthropic":
            self.async_client = anthropic.AsyncAnthropic(api_key=api_key, base_url=api_url)
        else:
            self.async_client = AsyncOpenAI(api_key=api_key, base_url=api_url)

        # 信号量控制并发数
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        if self.api_type == "anthropic":
            return self._generate_anthropic(messages, params)
        else:
            return self._generate_openai(messages, params)

    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步生成，带并发控制与指数退避重试"""
        async with self.semaphore:
            return await self._call_api_with_retry(messages, params)

    async def _call_api_with_retry(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """带指数退避的异步重试"""
        for attempt in range(self.max_retries):
            try:
                if self.api_type == "anthropic":
                    return await self._async_generate_anthropic(messages, params)
                else:
                    return await self._async_generate_openai(messages, params)
            except Exception as e:
                logger.warning(f"异步 API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt < self.max_retries - 1:
                    # 指数退避：2^attempt 秒
                    backoff = 2 ** attempt
                    logger.info(f"将在 {backoff} 秒后重试...")
                    await asyncio.sleep(backoff)
                else:
                    raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")

    def _generate_openai(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用 OpenAI SDK 生成内容"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_tokens=params.max_new_tokens
                )
                if not response.choices or not response.choices[0].message:
                    raise Exception(f"API 返回空响应: {response}")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt + 1 < self.max_retries:
                    logger.info(f"将在 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")

    async def _async_generate_openai(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步使用 OpenAI SDK 生成内容"""
        response = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_new_tokens
        )
        if not response.choices:
            raise Exception(f"API 返回空 choices: {response}")
        if not response.choices[0]:
            raise Exception(f"API 返回的 choices[0] 为 None: {response}")
        if not hasattr(response.choices[0], 'message') or response.choices[0].message is None:
            raise Exception(f"API 返回的 message 为 None: {response}")
        content = response.choices[0].message.content
        if content is None:
            raise Exception(f"API 返回的 content 为 None: {response}")
        return content

    def _generate_anthropic(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用 Anthropic SDK 生成内容"""
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
                response = self.client.messages.create(
                    model=self.model_name,
                    system=system_prompt,
                    messages=anthropic_messages,
                    temperature=params.temperature,
                    max_tokens=params.max_new_tokens
                )
                # 处理多种类型的 content block
                if not response.content:
                    raise Exception(f"API 返回空 content: {response}")
                result_text = ""
                for block in response.content:
                    if block.type == "text":
                        result_text += block.text
                    elif block.type == "thinking":
                        # 跳过 thinking block (MiniMax 扩展思考)
                        pass
                return result_text.strip()
            except Exception as e:
                logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt + 1 < self.max_retries:
                    logger.info(f"将在 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")

    async def _async_generate_anthropic(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步使用 Anthropic SDK 生成内容"""
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

        response = await self.async_client.messages.create(
            model=self.model_name,
            system=system_prompt,
            messages=anthropic_messages,
            temperature=params.temperature,
            max_tokens=params.max_new_tokens
        )
        # 处理多种类型的 content block
        if not response.content:
            raise Exception(f"API 返回空 content: {response}")
        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text
            elif block.type == "thinking":
                # 跳过 thinking block (MiniMax 扩展思考)
                pass
        return result_text.strip()


class ClientPoolModelManager(ModelManager):
    """单 Key 多客户端并行管理器

    使用同一个 API Key 的多个客户端实例实现并行请求，
    通过 ClientPool 实现负载均衡和并发控制。
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 1,
        api_type: str = "openai",
        num_clients: int = 4,
        max_concurrent_per_client: int = 3
    ):
        """
        Args:
            api_url: API 基础地址
            api_key: API 密钥（单 Key，多客户端共享）
            model_name: 模型名称
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            api_type: API 类型，"openai" 或 "anthropic"
            num_clients: 客户端实例数量
            max_concurrent_per_client: 每个客户端的最大并发数
        """
        from src.client_pool import ClientPool

        self.model_name = model_name
        self.api_type = api_type.lower()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.api_url = api_url

        # 创建客户端池
        self.client_pool = ClientPool(
            api_key=api_key,
            base_url=api_url,
            model_name=model_name,
            num_clients=num_clients,
            max_concurrent_per_client=max_concurrent_per_client,
            api_type=api_type
        )

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """同步生成（使用 client_0，兼容模式）

        注意：ClientPoolModelManager 只有 AsyncOpenAI 客户端，
        因此需要通过 asyncio.run() 执行异步生成。
        对于高频调用场景，建议使用 async_generate()。
        """
        return asyncio.run(self.async_generate(messages, params))

    async def async_generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """异步生成，通过客户端池分配"""
        async def _execute(client, client_id):
            if self.api_type == "anthropic":
                return await self._async_generate_anthropic_with_client(client, messages, params)
            else:
                return await self._async_generate_openai_with_client(client, messages, params)

        return await self.client_pool.execute(_execute)

    def _generate_openai_with_messages(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用同步客户端生成（第一个客户端）"""
        # 使用 client_pool 中的第一个客户端
        client = self.client_pool._clients[0]
        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_new_tokens
        )
        return self._extract_content(response)

    def _generate_anthropic_with_messages(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """使用同步客户端生成（第一个客户端）"""
        client = self.client_pool._clients[0]
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

        response = client.messages.create(
            model=self.model_name,
            system=system_prompt,
            messages=anthropic_messages,
            temperature=params.temperature,
            max_tokens=params.max_new_tokens
        )
        return self._extract_anthropic_content(response)

    async def _async_generate_openai_with_client(
        self,
        client: AsyncOpenAI,
        messages: List[Dict[str, Any]],
        params: BaseConfig
    ) -> str:
        """使用指定客户端异步生成 OpenAI"""
        for attempt in range(self.max_retries):
            try:
                response = await client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_tokens=params.max_new_tokens
                )
                return self._extract_content(response)
            except Exception as e:
                logger.warning(f"[ClientPool] API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
                else:
                    raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败")

    async def _async_generate_anthropic_with_client(
        self,
        client: Any,
        messages: List[Dict[str, Any]],
        params: BaseConfig
    ) -> str:
        """使用指定客户端异步生成 Anthropic"""
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
                response = await client.messages.create(
                    model=self.model_name,
                    system=system_prompt,
                    messages=anthropic_messages,
                    temperature=params.temperature,
                    max_tokens=params.max_new_tokens
                )
                return self._extract_anthropic_content(response)
            except Exception as e:
                logger.warning(f"[ClientPool] API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
                else:
                    raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败")

    def _extract_content(self, response) -> str:
        """从 OpenAI 响应中提取内容"""
        if not response.choices:
            raise Exception(f"API 返回空 choices: {response}")
        if not response.choices[0]:
            raise Exception(f"API 返回的 choices[0] 为 None")
        if not hasattr(response.choices[0], 'message') or response.choices[0].message is None:
            raise Exception(f"API 返回的 message 为 None")
        content = response.choices[0].message.content
        if content is None:
            raise Exception(f"API 返回的 content 为 None")
        return content

    def _extract_anthropic_content(self, response) -> str:
        """从 Anthropic 响应中提取内容"""
        if not response.content:
            raise Exception(f"API 返回空 content")
        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text
            elif block.type == "thinking":
                pass
        return result_text.strip()

    def log_stats(self):
        """打印客户端统计信息"""
        self.client_pool.log_stats()
