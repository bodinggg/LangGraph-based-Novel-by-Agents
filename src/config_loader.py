 
import yaml
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any, Optional

class ModelConfig(BaseModel):
    model_type: str = "api"
    model_path: Optional[str] = None
    model_name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    max_retries: int=3  # 重试次数，可选
    retry_delay: int=1  # 等待延迟，可选


class BaseConfig(BaseModel):
    max_new_tokens: int=3000
    temperature: float=0.7
    top_p: float=0.9
    min_chapters: int=10
    volume: int=1
    master_outline: bool=True
    
class ConfigLoader:
    def __init__(self, config_path:str="config.yaml"):
        self.config_path = Path(config_path)
        self.config_data = self._load_config()
        
       
        self.outline_config = BaseConfig(** self.config_data["outline_config"])
        self.character_config = BaseConfig(**self.config_data["character_config"])
        self.writer_config = BaseConfig(** self.config_data["writer_config"])
        self.reflect_config = BaseConfig(**self.config_data["reflect_config"])
    
    def _load_config(self) -> Dict[str, Any]:
        """加载并解析YAML配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不在：{self.config_path}")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML配置文件解析错误: {str(e)}")

config = ConfigLoader()

OutlineConfig = config.outline_config
    
CharacterConfig = config.character_config

WriterConfig = config.writer_config

ReflectConfig = config.reflect_config

