from abc import ABC, abstractmethod
from transformers import pipeline, AutoTokenizer
from typing import Dict, Any, Optional, List
import time
import anthropic
from openai import OpenAI
from src.config_loader import BaseConfig

# 抽象基类
class ModelManager(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        """Generate response from messages list.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            params: Generation parameters (temperature, max_new_tokens, top_p).

        Returns:
            Generated text string.
        """
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
                 max_retries: int = 3, retry_delay: int = 1, api_type: str = "openai"):
        """
        初始化 API 模型管理器

        Args:
            api_url: API 基础地址
            api_key: API 密钥
            model_name: 模型名称
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
            api_type: API 类型，"openai" 或 "anthropic"
        """
        self.model_name = model_name
        self.api_type = api_type.lower()
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if self.api_type == "anthropic":
            self.client = anthropic.Anthropic(api_key=api_key, base_url=api_url)
        else:
            self.client = OpenAI(api_key=api_key, base_url=api_url)

    def generate(self, messages: List[Dict[str, Any]], params: BaseConfig) -> str:
        if self.api_type == "anthropic":
            return self._generate_anthropic(messages, params)
        else:
            return self._generate_openai(messages, params)

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
                return response.choices[0].message.content
            except Exception as e:
                print(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt + 1 < self.max_retries:
                    print(f"将在 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")

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
                result_text = ""
                for block in response.content:
                    if block.type == "text":
                        result_text += block.text
                    elif block.type == "thinking":
                        # 跳过 thinking block (MiniMax 扩展思考)
                        pass
                return result_text.strip()
            except Exception as e:
                print(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt + 1 < self.max_retries:
                    print(f"将在 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")


