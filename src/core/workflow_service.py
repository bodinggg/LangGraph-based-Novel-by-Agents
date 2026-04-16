"""
工作流服务 - 核心业务逻辑封装

将LangGraph工作流与UI层分离，提供统一的工作流管理接口。
"""
import uuid
import threading
import time
from typing import Optional, Callable, Iterator, Any
from datetime import datetime

from src.workflow import create_workflow
from src.config_loader import ModelConfig, BaseConfig
from src.core.state_manager import StateManager
from src.core.progress import ProgressEvent, ProgressEmitter, WorkflowStatus, get_progress_emitter, emit_progress


class WorkflowService:
    """工作流服务 - 管理小说生成工作流的完整生命周期"""

    def __init__(self):
        self.state_manager = StateManager()
        self._workers: dict[str, dict] = {}  # workflow_id -> worker info
        self._lock = threading.Lock()
        self._progress_emitter = get_progress_emitter()

    def create_novel(
        self,
        user_intent: str,
        model_config: ModelConfig,
        agent_config: Optional[BaseConfig] = None,
        min_chapters: int = 10,
        volume: int = 1,
        master_outline: bool = True
    ) -> str:
        """创建新的小说生成任务

        Args:
            user_intent: 用户创作意图
            model_config: 模型配置
            agent_config: Agent配置（可选）
            min_chapters: 最少章节数
            volume: 分卷数
            master_outline: 是否启用分卷模式

        Returns:
            workflow_id: 新工作流的唯一标识
        """
        workflow_id = str(uuid.uuid4())[:8]

        # 合并配置
        if agent_config is None:
            agent_config = BaseConfig(
                min_chapters=min_chapters,
                volume=volume,
                master_outline=master_outline
            )

        # 创建初始状态
        initial_state = {
            "user_intent": user_intent,
            "min_chapters": min_chapters,
            "gradio_mode": False,
            "_created_at": datetime.now().isoformat(),
        }

        # 创建工作流记录
        self.state_manager.create_workflow_record(workflow_id, user_intent, initial_state)

        # 保存配置
        config_data = model_config.model_dump()
        config_data["agent_config"] = agent_config.model_dump() if agent_config else None
        state = self.state_manager.load_state(workflow_id) or {}
        state["config"] = config_data
        self.state_manager.save_state(workflow_id, state)

        # 更新状态为运行中
        self.state_manager.update_status(
            workflow_id,
            WorkflowStatus.RUNNING,
            current_node="initializing",
            progress=0.0
        )

        return workflow_id

    def get_status(self, workflow_id: str) -> Optional[dict]:
        """获取工作流状态

        Args:
            workflow_id: 工作流ID

        Returns:
            状态字典，包含 status, progress, current_node 等
        """
        state = self.state_manager.load_state(workflow_id)
        if state is None:
            return None

        return {
            "workflow_id": workflow_id,
            "status": state.get("status", "unknown"),
            "current_node": state.get("current_node"),
            "progress": state.get("progress", 0.0),
            "user_intent": state.get("user_intent"),
            "error": state.get("error"),
            "created_at": state.get("_created_at"),
            "updated_at": state.get("_saved_at"),
        }

    def get_progress(self, workflow_id: str) -> Optional[ProgressEvent]:
        """获取工作流最新进度事件"""
        return self._progress_emitter.get_latest(workflow_id)

    def cancel(self, workflow_id: str) -> bool:
        """取消工作流

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功取消
        """
        with self._lock:
            if workflow_id in self._workers:
                self._workers[workflow_id]["cancelled"] = True
                self.state_manager.update_status(
                    workflow_id,
                    WorkflowStatus.CANCELLED,
                    error="用户取消"
                )
                return True
            return False

    def execute(
        self,
        workflow_id: str,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None
    ) -> Iterator[tuple[str, dict]]:
        """执行工作流（同步迭代器）

        Args:
            workflow_id: 工作流ID
            progress_callback: 进度回调函数

        Yields:
            (node_name, state_dict): 每个节点的名称和状态
        """
        # 加载配置
        state = self.state_manager.load_state(workflow_id)
        if state is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        config_data = state.get("config", {})
        model_config = ModelConfig(**{
            k: v for k, v in config_data.items()
            if k not in ["agent_config"]
        })
        agent_config_data = config_data.get("agent_config")
        agent_config = BaseConfig(**agent_config_data) if agent_config_data else None

        # 创建工作流
        workflow = create_workflow(model_config, agent_config)

        # 订阅进度
        if progress_callback:
            self._progress_emitter.subscribe(progress_callback)

        # 设置工作流元数据
        state["workflow_id"] = workflow_id

        # 构建初始状态（只包含必要字段）
        initial_state = {
            "user_intent": state["user_intent"],
            "min_chapters": state.get("min_chapters", 10),
            "gradio_mode": state.get("gradio_mode", False),
        }

        cancelled = False
        try:
            # 更新状态
            self.state_manager.update_status(
                workflow_id,
                WorkflowStatus.RUNNING,
                current_node="generate_outline",
                progress=0.05
            )

            emit_progress(
                workflow_id=workflow_id,
                node="generate_outline",
                status=WorkflowStatus.RUNNING,
                message="开始生成小说大纲...",
                progress=0.05
            )

            # 执行工作流
            for step in workflow.stream(
                initial_state,
                {"recursion_limit": agent_config.min_chapters * 50 if agent_config else 500}
            ):
                # 检查是否被取消
                with self._lock:
                    if self._workers.get(workflow_id, {}).get("cancelled"):
                        cancelled = True
                        break

                for node_name, node_state in step.items():
                    # 保存当前状态
                    node_state["workflow_id"] = workflow_id
                    node_state["status"] = WorkflowStatus.RUNNING.value
                    self.state_manager.save_state(workflow_id, node_state)

                    # 计算进度
                    progress = self._calculate_progress(node_name, node_state, agent_config)
                    self.state_manager.update_status(
                        workflow_id,
                        WorkflowStatus.RUNNING,
                        current_node=node_name,
                        progress=progress
                    )

                    # 发布进度事件
                    emit_progress(
                        workflow_id=workflow_id,
                        node=node_name,
                        status=WorkflowStatus.RUNNING,
                        message=self._get_node_message(node_name, node_state),
                        chapter_index=node_state.get("current_chapter_index"),
                        progress=progress
                    )

                    yield node_name, node_state

            if cancelled:
                self.state_manager.update_status(
                    workflow_id,
                    WorkflowStatus.CANCELLED,
                    error="用户取消"
                )
                emit_progress(
                    workflow_id=workflow_id,
                    node="",
                    status=WorkflowStatus.CANCELLED,
                    message="工作流已被用户取消"
                )
            else:
                # 工作流完成
                final_state = self.state_manager.load_state(workflow_id)
                self.state_manager.update_status(
                    workflow_id,
                    WorkflowStatus.COMPLETED,
                    current_node="success",
                    progress=1.0
                )
                emit_progress(
                    workflow_id=workflow_id,
                    node="success",
                    status=WorkflowStatus.COMPLETED,
                    message="小说生成完成！",
                    progress=1.0
                )

        except Exception as e:
            error_msg = str(e)
            self.state_manager.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error=error_msg
            )
            emit_progress(
                workflow_id=workflow_id,
                node="error",
                status=WorkflowStatus.FAILED,
                message=f"生成失败: {error_msg}"
            )
            raise

        finally:
            # 取消订阅
            if progress_callback:
                self._progress_emitter.unsubscribe(progress_callback)

    def _calculate_progress(self, node_name: str, state: dict, agent_config: Optional[BaseConfig]) -> float:
        """计算工作流进度"""
        total_chapters = agent_config.min_chapters if agent_config else 10

        # 阶段一：大纲生成 ~10%
        if node_name == "generate_outline":
            return 0.05
        elif node_name in ["validate_master_outline", "validate_outline"]:
            return 0.08
        elif node_name in ["outline_feedback", "process_outline_feedback"]:
            return 0.10

        # 阶段二：角色生成 ~15%
        elif node_name == "generate_characters":
            return 0.12
        elif node_name == "validate_characters":
            return 0.14
        elif node_name in ["character_feedback", "process_character_feedback"]:
            return 0.15

        # 阶段三：章节循环 ~75%
        elif node_name == "write_chapter":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight, 0.85)
        elif node_name == "validate_chapter":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight + chapter_weight * 0.1, 0.85)
        elif node_name == "chapter_feedback":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight + chapter_weight * 0.2, 0.85)
        elif node_name == "evaluate_chapter":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight + chapter_weight * 0.4, 0.85)
        elif node_name == "evaluate2wirte":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight + chapter_weight * 0.5, 0.85)
        elif node_name == "generate_entities":
            current = state.get("current_chapter_index", 0)
            base = 0.15
            chapter_weight = 0.70 / total_chapters
            return min(base + current * chapter_weight + chapter_weight * 0.6, 0.85)
        elif node_name in ["accpet_chapter", "evaluate_report"]:
            return 0.90

        # 完成
        elif node_name in ["success", "failure"]:
            return 1.0 if node_name == "success" else 0.0

        return 0.5

    def _get_node_message(self, node_name: str, state: dict) -> str:
        """获取节点描述消息"""
        messages = {
            "generate_outline": "正在生成小说大纲...",
            "validate_master_outline": "正在验证分卷大纲...",
            "validate_outline": "正在验证大纲...",
            "outline_feedback": "等待用户确认大纲",
            "generate_characters": "正在生成角色档案...",
            "validate_characters": "正在验证角色档案...",
            "character_feedback": "等待用户确认角色",
            "write_chapter": f"正在撰写第{state.get('current_chapter_index', 0) + 1}章...",
            "validate_chapter": "正在验证章节...",
            "chapter_feedback": "等待用户确认章节",
            "evaluate_chapter": "正在评估章节质量...",
            "evaluate2wirte": "正在处理评估结果...",
            "generate_entities": "正在提取章节实体...",
            "accpet_chapter": "正在接受章节...",
            "success": "小说生成完成！",
            "failure": "小说生成失败",
        }
        return messages.get(node_name, f"执行节点: {node_name}")


# 全局单例
_global_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    """获取全局工作流服务实例"""
    global _global_service
    if _global_service is None:
        _global_service = WorkflowService()
    return _global_service
