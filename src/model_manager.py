from abc import ABC, abstractmethod
from transformers import pipeline, AutoTokenizer
from typing import Dict, Any, Optional, List
import time
from openai import (
    OpenAI,
    APIError,
    APIConnectionError,
    Timeout
)

from src.config_loader import BaseConfig

# 抽象基类
class ModelManager(ABC):
    @abstractmethod
    def generate(self, prompt:str, params: Dict[str, Any]) -> str:
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
    
    def generate(self, prompt:str, params: BaseConfig) -> str:
        result = self.pipeline(
            prompt,
            max_new_tokens=params.max_new_tokens,
            temperature=params.temperature,
            top_p=params.top_p,
            do_sample=True 
        )
        return result[0]["generated_text"][len(prompt):].strip()

# API调用管理
class APIModelManager(ModelManager):
    
    def __init__(self, api_url:str, api_key: Optional[str]=None, model_name:Optional[str]=None, max_retries:int=3, retry_delay=1):
        self.model_name = model_name
        self.client = OpenAI(
            api_key=api_key,
            base_url = api_url
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def generate(self, messages:List[Dict[str, Any]], params: BaseConfig) -> str:
        
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
            except (APIError, APIConnectionError, Timeout) as e:
                # 捕获常见的API错误
                print(f"API 调用失败 （尝试 {attempt+1}/{self.max_retries}: {str(e)}")
                if attempt+1 < self.max_retries:
                    print(f"将在 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        raise Exception(f"经过 {self.max_retries} 次重试后，API请求仍失败，服务器可能繁忙！")
    

