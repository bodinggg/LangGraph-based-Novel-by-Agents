"""
定义创作流程的状态，便于管理
"""

from typing import Optional, List
from src.model import * 
from src.storage import NovelStorage
from pydantic import BaseModel, ConfigDict

class NovelState(BaseModel):
    # 动态内存管理
    novel_storage: Optional[NovelStorage] = None
    
    # 用户意图
    user_intent: str

    # 重要参数控制
    min_chapters: int=10
    
    # 每个环节重试次数记录
    attempt: int=0
    evaluate_attempt: int=0 # 特殊在于评估有重试机制，写作-评估也有重试机制
    
    # 每个环节最大重试次数
    max_attempts: int= 10
    
    # 大纲生成控制
    raw_outline: Optional[str]=None
    validated_outline: Optional[NovelOutline]=None  # 分卷生成大纲需要用到，属于动态更新，先不拆成本地
    outline_validated_error: Optional[str]=None

    
    # 分卷支持更多章节数大纲
    raw_master_outline: Optional[str]=None
    current_volume_index: int=0
    raw_volume_chapters: Optional[str]=None
    validated_chapters: List[ChapterOutline]=[]
    
    
    
    # 角色档案生成控制
    row_characters : Optional[str] = None
    validated_characters: Optional[List[Character]] = None
    characters_validated_error: Optional[str] = None

    
    # 章节内容生成控制
    current_chapter_index: int=0
    raw_current_chapter: Optional[str] =None
    validated_chapter_draft: Optional[ChapterContent] = None
    current_chapter_validated_error: Optional[str] = None	
    
    
    # 评估内容反馈
    raw_chapter_evaluation: Optional[str] = None
    validated_evaluation : Optional[QualityEvaluation] = None
    evaluation_validated_error: Optional[str] = None
    
    # 实体生成控制
    raw_entities: Optional[str] = None
    entities_validated_error: Optional[str] = None
    
    # 反馈控制
    outline_feedback_request: Optional[dict] = None
    outline_feedback_id: Optional[str] = None
    feedback_action: Optional[str] = None
    outline_modified: Optional[bool] = None
    feedback_error: Optional[str] = None
    	
    # 结果
    result: Optional[str] = None
    final_outline: Optional[NovelOutline] = None
    final_characters: Optional[List[Character]] = None
    final_content: Optional[List[ChapterContent]] = None
    final_error: Optional[str] = None
    
    # Gradio
    gradio_mode: bool = False
    
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
