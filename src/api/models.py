"""
API 请求/响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from enum import Enum


class ModelTypeEnum(str, Enum):
    """模型类型"""
    API = "api"
    LOCAL = "local"


class ApiTypeEnum(str, Enum):
    """API 格式类型"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class CreateNovelRequest(BaseModel):
    """创建小说请求"""
    user_intent: str = Field(..., description="用户创作意图")
    model_type: ModelTypeEnum = Field(default=ModelTypeEnum.API, description="模型类型")
    model_name: Optional[str] = Field(None, description="模型名称 (API模式必填)")
    api_type: ApiTypeEnum = Field(default=ApiTypeEnum.OPENAI, description="API格式类型")
    min_chapters: int = Field(default=10, description="最少章节数")
    volume: int = Field(default=1, description="分卷数")
    master_outline: bool = Field(default=True, description="是否启用分卷大纲")


class WorkflowStatusResponse(BaseModel):
    """工作流状态响应"""
    workflow_id: str
    status: str
    current_node: Optional[str] = None
    progress: float = 0.0
    user_intent: Optional[str] = None
    error: Optional[str] = None


class ProgressEventResponse(BaseModel):
    """进度事件响应"""
    workflow_id: str
    node: str
    status: str
    message: str
    progress: float
    chapter_index: Optional[int] = None
    timestamp: str


class NovelResultResponse(BaseModel):
    """小说生成结果响应"""
    workflow_id: str
    result: str
    status: str
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
