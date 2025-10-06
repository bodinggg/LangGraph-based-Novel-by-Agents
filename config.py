

class OutlineConfig:
    max_new_tokens = 3000
    temperature = 0.9
    top_p = 0.9
    
class CharacterConfig:
    max_new_tokens = 3000
    temperature = 0.4
    top_p = 0.9

class WriterConfig:
    max_new_tokens = 4096
    temperature = 0.4
    top_p = 0.9
    
    # 写作参数
    min_word_length = 1000

class ReflectConfig:
    max_new_tokens = 3000
    temperature = 0.4
    top_p = 0.9