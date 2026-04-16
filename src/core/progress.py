"""
进度事件 - 用于实时推送工作流执行进度
"""
from datetime import datetime
from typing import Optional, Literal, Any
from pydantic import BaseModel
from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressEvent(BaseModel):
    """进度事件模型"""
    workflow_id: str
    node: str  # e.g., "write_chapter", "validate_outline"
    chapter_index: Optional[int] = None
    total_chapters: Optional[int] = None
    status: WorkflowStatus = WorkflowStatus.RUNNING
    message: str = ""
    timestamp: datetime = None
    data: Optional[dict] = None  # 额外数据

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now()
        super().__init__(**data)

    def to_dict(self) -> dict:
        """转换为字典格式，便于JSON序列化"""
        d = self.model_dump()
        d["status"] = self.status.value
        d["timestamp"] = self.timestamp.isoformat()
        return d


class ProgressEmitter:
    """进度事件发布器 - 订阅/发布模式"""

    def __init__(self):
        self._subscribers: list = []
        self._latest_events: dict[str, ProgressEvent] = {}

    def subscribe(self, callback):
        """订阅进度事件

        Args:
            callback: 回调函数，接收 ProgressEvent 参数
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, event: ProgressEvent):
        """发布进度事件"""
        self._latest_events[event.workflow_id] = event
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                pass  # 不让订阅者异常影响发布者

    def get_latest(self, workflow_id: str) -> Optional[ProgressEvent]:
        """获取最新的进度事件"""
        return self._latest_events.get(workflow_id)

    def clear(self, workflow_id: str):
        """清除某个工作流的最新事件"""
        self._latest_events.pop(workflow_id, None)


# 全局进度发布器实例
_global_emitter: Optional[ProgressEmitter] = None


def get_progress_emitter() -> ProgressEmitter:
    """获取全局进度发布器实例"""
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = ProgressEmitter()
    return _global_emitter


def emit_progress(
    workflow_id: str,
    node: str,
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    message: str = "",
    chapter_index: Optional[int] = None,
    total_chapters: Optional[int] = None,
    **kwargs
):
    """便捷函数：发布进度事件"""
    event = ProgressEvent(
        workflow_id=workflow_id,
        node=node,
        status=status,
        message=message,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        **kwargs
    )
    get_progress_emitter().emit(event)
