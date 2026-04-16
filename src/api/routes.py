"""
FastAPI 路由定义
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Optional

from src.api.models import (
    CreateNovelRequest, WorkflowStatusResponse,
    ProgressEventResponse, NovelResultResponse, ErrorResponse
)
from src.api.websocket_manager import get_websocket_manager
from src.core.workflow_service import get_workflow_service
from src.core.progress import WorkflowStatus
from src.config_loader import ModelConfig

router = APIRouter(prefix="/api/v1")


@router.post("/novels", response_model=WorkflowStatusResponse)
async def create_novel(request: CreateNovelRequest):
    """创建新的小说生成任务"""
    service = get_workflow_service()

    # 构建模型配置
    if request.model_type == "api":
        if not request.model_name:
            raise HTTPException(status_code=400, detail="API 模式需要提供 model_name")

        model_config = ModelConfig(
            model_type="api",
            api_key=None,  # 从环境变量读取
            api_url=None,   # 从环境变量读取
            model_name=request.model_name,
            api_type=request.api_type.value
        )
    else:
        raise HTTPException(status_code=400, detail="本地模型暂不支持")

    # 创建工作流
    workflow_id = service.create_novel(
        user_intent=request.user_intent,
        model_config=model_config,
        min_chapters=request.min_chapters,
        volume=request.volume,
        master_outline=request.master_outline
    )

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status="pending",
        progress=0.0,
        user_intent=request.user_intent
    )


@router.get("/novels/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_novel_status(workflow_id: str):
    """获取小说生成状态"""
    service = get_workflow_service()
    status = service.get_status(workflow_id)

    if status is None:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return WorkflowStatusResponse(**status)


@router.delete("/novels/{workflow_id}")
async def cancel_novel(workflow_id: str):
    """取消小说生成"""
    service = get_workflow_service()
    success = service.cancel(workflow_id)

    if not success:
        raise HTTPException(status_code=404, detail="工作流不存在或已取消")

    return {"message": "工作流已取消", "workflow_id": workflow_id}


@router.get("/novels")
async def list_novels():
    """列出所有工作流"""
    service = get_workflow_service()
    state_manager = service.state_manager
    workflows = state_manager.list_workflows()

    return {
        "workflows": [
            {
                "workflow_id": w.workflow_id,
                "user_intent": w.user_intent,
                "status": w.status.value,
                "progress": w.progress,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat()
            }
            for w in workflows
        ]
    }


@router.post("/novels/{workflow_id}/execute", response_model=WorkflowStatusResponse)
async def execute_novel(workflow_id: str):
    """
    启动工作流执行（异步）
    返回后工作流在后台运行，可通过 WebSocket 监听进度
    """
    service = get_workflow_service()
    status = service.get_status(workflow_id)

    if status is None:
        raise HTTPException(status_code=404, detail="工作流不存在")

    if status["status"] not in ["pending", "paused"]:
        raise HTTPException(status_code=400, detail=f"工作流状态为 {status['status']}，无法启动")

    # 后台执行工作流
    async def run_workflow():
        try:
            for node_name, state_dict in service.execute(workflow_id):
                # 进度通过 WebSocket 推送
                pass
        except Exception as e:
            # 错误会在状态中反映
            pass

    asyncio.create_task(run_workflow())

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status="running",
        progress=0.0,
        user_intent=status.get("user_intent")
    )


@router.websocket("/novels/{workflow_id}/ws")
async def websocket_progress(websocket: WebSocket, workflow_id: str):
    """WebSocket 端点 - 实时接收工作流进度"""
    ws_manager = get_websocket_manager()
    await websocket.accept()
    ws_manager.subscribe(workflow_id, websocket)

    try:
        # 保持连接直到客户端断开
        while True:
            # 接收客户端消息（心跳等）
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 心跳响应
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 发送心跳
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unsubscribe(workflow_id, websocket)


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "novel-generator-api"}


@router.get("/")
async def root():
    """API 欢迎页面"""
    return {
        "service": "AI Novel Generator API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "create_novel": "POST /api/v1/novels",
            "list_novels": "GET /api/v1/novels",
            "get_status": "GET /api/v1/novels/{workflow_id}",
            "cancel": "DELETE /api/v1/novels/{workflow_id}",
            "execute": "POST /api/v1/novels/{workflow_id}/execute",
            "websocket": "WS /api/v1/novels/{workflow_id}/ws",
            "health": "GET /api/v1/health"
        }
    }
