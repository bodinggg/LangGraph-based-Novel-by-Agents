 
import yaml
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any

class BaseConfig(BaseModel):
    max_new_tokens: int
    temperature: float
    top_p: float

class WriterConfig(BaseConfig):
    min_word_length: int
    
class ConfigLoader:
    def __init__(self, config_path:str="config.yaml"):
        self.config_path = Path(config_path)
        self.config_data = self._load_config()
       
        self.outline_config = BaseConfig(** self.config_data["outline_config"])
        self.character_config = BaseConfig(**self.config_data["character_config"])
        self.writer_config = WriterConfig(** self.config_data["writer_config"])
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
