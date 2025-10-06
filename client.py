from transformers import pipeline, AutoTokenizer

# 共享模型管理器 - 负责创建和管理单一模型实例
class SharedModelManager:
    _instance = None
    _pipeline = None
    _tokenizer = None
    
    @classmethod
    def get_instance(cls, model_name_or_path: str = "your-local-model-path") -> tuple[pipeline, AutoTokenizer]:
        """获取共享的模型管道和分词器实例（单例模式）"""
        if cls._instance is None:
            cls._instance = cls()
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
            cls._pipeline = pipeline(
                "text-generation",
                model=model_name_or_path,
                tokenizer=cls._tokenizer,
                device=0  # 如果有GPU，使用0；否则使用-1
            )
        return cls._pipeline, cls._tokenizer