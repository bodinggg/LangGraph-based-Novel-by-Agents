"""
状态管理器 - 工作流状态的持久化和恢复
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

from src.core.progress import WorkflowStatus
from pydantic import BaseModel


class WorkflowInfo(BaseModel):
    """工作流信息摘要"""
    workflow_id: str
    user_intent: str
    created_at: datetime
    updated_at: datetime
    status: WorkflowStatus
    current_node: Optional[str] = None
    progress: float = 0.0  # 0.0 ~ 1.0
    error: Optional[str] = None


class StateManager:
    """状态管理器 - 支持工作流中断和恢复"""

    def __init__(self, storage_dir: str = "result/workflows"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _workflow_path(self, workflow_id: str) -> Path:
        """获取工作流状态文件路径"""
        return self.storage_dir / f"{workflow_id}.json"

    def save_state(self, workflow_id: str, state_data: dict) -> None:
        """保存工作流状态到磁盘

        Args:
            workflow_id: 工作流ID
            state_data: 状态字典
        """
        with self._lock:
            path = self._workflow_path(workflow_id)
            # 添加时间戳
            state_data["_saved_at"] = datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2, default=str)

    def load_state(self, workflow_id: str) -> Optional[dict]:
        """从磁盘加载工作流状态

        Args:
            workflow_id: 工作流ID

        Returns:
            状态字典，如果不存在返回 None
        """
        with self._lock:
            path = self._workflow_path(workflow_id)
            if not path.exists():
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def delete_state(self, workflow_id: str) -> bool:
        """删除工作流状态文件

        Returns:
            是否成功删除
        """
        with self._lock:
            path = self._workflow_path(workflow_id)
            if path.exists():
                path.unlink()
                return True
            return False

    def list_workflows(self, status: Optional[WorkflowStatus] = None) -> list[WorkflowInfo]:
        """列出所有工作流

        Args:
            status: 如果指定，只返回该状态的工作流

        Returns:
            工作流信息列表
        """
        workflows = []
        with self._lock:
            for path in self.storage_dir.glob("*.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    info = WorkflowInfo(
                        workflow_id=path.stem,
                        user_intent=data.get("user_intent", ""),
                        created_at=datetime.fromisoformat(data.get("_created_at", datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(data.get("_saved_at", datetime.now().isoformat())),
                        status=WorkflowStatus(data.get("status", "pending")),
                        current_node=data.get("current_node"),
                        progress=data.get("progress", 0.0),
                        error=data.get("error")
                    )
                    if status is None or info.status == status:
                        workflows.append(info)
                except (json.JSONDecodeError, ValueError, OSError):
                    continue
        return sorted(workflows, key=lambda w: w.updated_at, reverse=True)

    def update_status(
        self,
        workflow_id: str,
        status: WorkflowStatus,
        current_node: Optional[str] = None,
        progress: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """更新工作流状态

        Args:
            workflow_id: 工作流ID
            status: 新状态
            current_node: 当前执行节点
            progress: 进度 0.0~1.0
            error: 错误信息
        """
        state = self.load_state(workflow_id) or {}
        state["status"] = status.value
        if current_node is not None:
            state["current_node"] = current_node
        if progress is not None:
            state["progress"] = progress
        if error is not None:
            state["error"] = error
        self.save_state(workflow_id, state)

    def create_workflow_record(
        self,
        workflow_id: str,
        user_intent: str,
        initial_state: dict
    ) -> None:
        """创建新的工作流记录

        Args:
            workflow_id: 工作流ID
            user_intent: 用户创作意图
            initial_state: 初始状态
        """
        state = initial_state.copy()
        state["_created_at"] = datetime.now().isoformat()
        state["status"] = WorkflowStatus.PENDING.value
        self.save_state(workflow_id, state)

