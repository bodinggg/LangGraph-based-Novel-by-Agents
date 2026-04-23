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
    novel_title: Optional[str] = None
    current_chapter_index: int = 0


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
                        error=data.get("error"),
                        novel_title=data.get("novel_title"),
                        current_chapter_index=data.get("current_chapter_index", 0)
                    )
                    if status is None or info.status == status:
                        workflows.append(info)
                except (json.JSONDecodeError, ValueError, OSError):
                    continue
        return sorted(workflows, key=lambda w: w.updated_at, reverse=True)

    def list_existing_novels(self) -> list[dict]:
        """扫描 result/ 目录，列出所有已存在的小说（可用于断点恢复）

        Returns:
            已存在小说的信息列表
        """
        from src.storage import NovelStorage

        novels = []
        result_path = Path("result")

        if not result_path.exists():
            return novels

        for storage_path in result_path.glob("*_storage"):
            try:
                title = storage_path.name.replace("_storage", "")
                storage = NovelStorage(title)
                novels.append(storage.get_storage_info())
            except Exception:
                continue

        return sorted(novels, key=lambda x: x.get("title", ""))

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

    def _checkpoint_path(self, workflow_id: str) -> Path:
        """获取检查点文件路径"""
        return self.storage_dir / f"{workflow_id}_checkpoint.json"

    def save_checkpoint(self, workflow_id: str, state_data: dict) -> None:
        """保存工作流检查点 - 包含完整的 NovelState 可序列化字段

        Args:
            workflow_id: 工作流ID
            state_data: 状态字典（包含可序列化的检查点数据）
        """
        import copy

        def serialize_value(v):
            """序列化值，支持 Pydantic 模型和 datetime"""
            if hasattr(v, 'model_dump'):
                return v.model_dump()
            elif isinstance(v, datetime):
                return v.isoformat()
            elif isinstance(v, list):
                return [serialize_value(item) for item in v]
            elif isinstance(v, dict):
                return {k: serialize_value(val) for k, val in v.items()}
            else:
                return v

        # 从 state_data 中提取完整检查点字段
        checkpoint_data = {
            "workflow_id": workflow_id,
            "saved_at": datetime.now().isoformat(),

            # 用户与配置
            "user_intent": state_data.get("user_intent", ""),
            "min_chapters": state_data.get("min_chapters", 10),
            "max_attempts": state_data.get("max_attempts", 10),
            "gradio_mode": state_data.get("gradio_mode", False),

            # 大纲生成
            "raw_outline": state_data.get("raw_outline"),
            "validated_outline": serialize_value(state_data.get("validated_outline")),
            "outline_validated_error": state_data.get("outline_validated_error"),

            # 分卷大纲
            "raw_master_outline": state_data.get("raw_master_outline"),
            "current_volume_index": state_data.get("current_volume_index", 0),
            "raw_volume_chapters": state_data.get("raw_volume_chapters"),
            "validated_chapters": serialize_value(state_data.get("validated_chapters", [])),

            # 角色档案
            "row_characters": state_data.get("row_characters"),
            "validated_characters": serialize_value(state_data.get("validated_characters")),
            "characters_validated_error": state_data.get("characters_validated_error"),

            # 章节内容
            "current_chapter_index": state_data.get("current_chapter_index", 0),
            "completed_chapters": state_data.get("completed_chapters", []),
            "raw_current_chapter": state_data.get("raw_current_chapter"),
            "validated_chapter_draft": serialize_value(state_data.get("validated_chapter_draft")),
            "current_chapter_validated_error": state_data.get("current_chapter_validated_error"),

            # 评估反馈
            "evaluate_attempt": state_data.get("evaluate_attempt", 0),
            "raw_chapter_evaluation": state_data.get("raw_chapter_evaluation"),
            "validated_evaluation": serialize_value(state_data.get("validated_evaluation")),
            "evaluation_validated_error": state_data.get("evaluation_validated_error"),

            # 实体生成
            "raw_entities": state_data.get("raw_entities"),
            "entities_validated_error": state_data.get("entities_validated_error"),

            # 反馈控制
            "outline_feedback_request": state_data.get("outline_feedback_request"),
            "outline_feedback_id": state_data.get("outline_feedback_id"),
            "outline_feedback_action": state_data.get("outline_feedback_action"),
            "outline_modified": state_data.get("outline_modified"),
            "outline_feedback_error": state_data.get("outline_feedback_error"),

            "character_feedback_request": state_data.get("character_feedback_request"),
            "character_feedback_id": state_data.get("character_feedback_id"),
            "character_feedback_action": state_data.get("character_feedback_action"),
            "character_modified": state_data.get("character_modified"),
            "character_feedback_error": state_data.get("character_feedback_error"),

            "chapter_feedback_request": state_data.get("chapter_feedback_request"),
            "chapter_feedback_id": state_data.get("chapter_feedback_id"),
            "chapter_feedback_action": state_data.get("chapter_feedback_action"),
            "chapter_modified": state_data.get("chapter_modified"),
            "chapter_feedback_error": state_data.get("chapter_feedback_error"),

            # 重试计数
            "attempt": state_data.get("attempt", 0),

            # 当前节点
            "current_node": state_data.get("current_node", ""),
        }

        # 获取小说标题（从 novel_storage 或 state）
        if "novel_storage" in state_data and state_data["novel_storage"]:
            checkpoint_data["novel_title"] = state_data["novel_storage"].base_dir.name.replace("_storage", "")
        elif "novel_title" in state_data:
            checkpoint_data["novel_title"] = state_data["novel_title"]

        with self._lock:
            path = self._checkpoint_path(workflow_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2, default=str)

    def load_checkpoint(self, workflow_id: str) -> Optional[dict]:
        """加载工作流检查点

        Args:
            workflow_id: 工作流ID

        Returns:
            检查点字典，如果不存在返回 None
        """
        with self._lock:
            path = self._checkpoint_path(workflow_id)
            if not path.exists():
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def has_checkpoint(self, workflow_id: str) -> bool:
        """检查是否存在可恢复的检查点

        Args:
            workflow_id: 工作流ID

        Returns:
            是否存在检查点
        """
        return self._checkpoint_path(workflow_id).exists()

    def clear_checkpoint(self, workflow_id: str) -> bool:
        """清除工作流检查点（工作流正常完成后调用）

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功删除
        """
        with self._lock:
            path = self._checkpoint_path(workflow_id)
            if path.exists():
                path.unlink()
                return True
            return False

    def get_interrupted_workflows(self) -> list["WorkflowInfo"]:
        """获取所有可恢复的工作流（存在检查点的中断工作流）

        Returns:
            可恢复工作流列表
        """
        workflows = []
        with self._lock:
            for path in self.storage_dir.glob("*_checkpoint.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 从检查点获取基本信息和状态
                    workflow_id = data.get("workflow_id", path.stem.replace("_checkpoint", ""))
                    state_path = self._workflow_path(workflow_id)

                    # 加载工作流状态文件获取最新信息
                    if state_path.exists():
                        with open(state_path, "r", encoding="utf-8") as sf:
                            state = json.load(sf)
                        created_at = datetime.fromisoformat(state.get("_created_at", datetime.now().isoformat()))
                        updated_at = datetime.fromisoformat(state.get("_saved_at", datetime.now().isoformat()))
                        user_intent = state.get("user_intent", "")
                        current_node = data.get("current_node", "")
                        progress = state.get("progress", 0.0)
                        status = WorkflowStatus(data.get("status", "running"))
                    else:
                        created_at = datetime.fromisoformat(data.get("saved_at", datetime.now().isoformat()))
                        updated_at = datetime.fromisoformat(data.get("saved_at", datetime.now().isoformat()))
                        user_intent = data.get("user_intent", "")
                        current_node = data.get("current_node", "")
                        progress = 0.0
                        status = WorkflowStatus.RUNNING

                    info = WorkflowInfo(
                        workflow_id=workflow_id,
                        user_intent=user_intent,
                        created_at=created_at,
                        updated_at=updated_at,
                        status=status,
                        current_node=current_node,
                        progress=progress,
                        error=None,
                        novel_title=data.get("novel_title"),
                        current_chapter_index=data.get("current_chapter_index", 0)
                    )
                    workflows.append(info)
                except (json.JSONDecodeError, ValueError, OSError):
                    continue

        return sorted(workflows, key=lambda w: w.updated_at, reverse=True)

