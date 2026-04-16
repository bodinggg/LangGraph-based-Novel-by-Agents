"""
WebSocket 管理器 - 处理实时进度推送
"""
import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket
from src.core.progress import ProgressEvent, WorkflowStatus, get_progress_emitter


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # workflow_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._progress_emitter = get_progress_emitter()
        self._subscriber_id = None

    def _on_progress(self, event: ProgressEvent):
        """进度事件回调 - 推送所有订阅者"""
        if event.workflow_id in self._connections:
            import copy
            event_dict = copy.deepcopy(event.to_dict())
            message = json.dumps(event_dict, ensure_ascii=False)

            for websocket in self._connections[event.workflow_id].copy():
                try:
                    # 创建新任务避免阻塞
                    asyncio.create_task(websocket.send_text(message))
                except Exception:
                    # 连接断开时移除
                    self._connections[event.workflow_id].discard(websocket)

    def subscribe(self, workflow_id: str, websocket: WebSocket):
        """订阅某个工作流的进度"""
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        self._connections[workflow_id].add(websocket)

        # 首次订阅时注册全局监听
        if len(self._connections[workflow_id]) == 1:
            self._progress_emitter.subscribe(self._on_progress)

    def unsubscribe(self, workflow_id: str, websocket: WebSocket):
        """取消订阅"""
        if workflow_id in self._connections:
            self._connections[workflow_id].discard(websocket)
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]

                # 如果没有订阅者了，移除全局监听
                if not self._connections:
                    try:
                        self._progress_emitter.unsubscribe(self._on_progress)
                    except ValueError:
                        pass

    async def send_progress(self, websocket: WebSocket, event: ProgressEvent):
        """发送进度到单个连接"""
        try:
            await websocket.send_text(json.dumps(event.to_dict(), ensure_ascii=False))
        except Exception:
            pass


# 全局单例
_ws_manager: WebSocketManager = None


def get_websocket_manager() -> WebSocketManager:
    """获取 WebSocket 管理器单例"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
