"""
FastAPI 路由定义
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Optional

from src.api.models import (
    CreateNovelRequest, WorkflowStatusResponse,
    ProgressEventResponse, NovelResultResponse, ErrorResponse,
    CharacterRelationshipResponse, CharacterGraphData, CharacterGraphNode, CharacterGraphLink
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


@router.get("/novels/interrupted")
async def list_interrupted_workflows():
    """列出所有可恢复的工作流（存在检查点的中断工作流）"""
    service = get_workflow_service()
    workflows = service.state_manager.get_interrupted_workflows()

    return {
        "workflows": [
            {
                "workflow_id": w.workflow_id,
                "user_intent": w.user_intent,
                "status": w.status.value,
                "progress": w.progress,
                "current_node": w.current_node,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat()
            }
            for w in workflows
        ]
    }


@router.get("/novels/existing")
async def list_existing_novels():
    """列出所有已存在的小说（基于存储目录，可用于断点恢复）"""
    service = get_workflow_service()
    novels = service.state_manager.list_existing_novels()

    return {
        "novels": novels
    }


@router.post("/novels/{novel_title}/resume")
async def resume_novel_from_storage(novel_title: str):
    """从存储目录恢复小说继续创作

    基于 result/{title}_storage/ 目录中的已有数据进行断点恢复
    """
    from src.storage import NovelStorage

    # 检查存储目录是否存在
    storage = NovelStorage(novel_title)
    if not storage.has_outline():
        raise HTTPException(status_code=404, detail="小说不存在或无大纲")

    # 获取存储信息
    storage_info = storage.get_storage_info()

    return {
        "message": "小说存在，可恢复创作",
        "novel_title": novel_title,
        "chapter_count": storage_info.get("chapter_count", 0),
        "has_outline": storage_info.get("has_outline", False),
        "has_characters": storage_info.get("has_characters", False),
        "next_chapter_index": storage_info.get("chapter_count", 0) + 1
    }


@router.post("/novels/{workflow_id}/resume")
async def resume_novel(workflow_id: str):
    """恢复中断的工作流继续执行"""
    service = get_workflow_service()

    # 检查工作流是否存在
    status = service.get_status(workflow_id)
    if status is None:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 检查是否有检查点
    if not service.state_manager.has_checkpoint(workflow_id):
        raise HTTPException(status_code=400, detail="没有可恢复的检查点")

    # 后台执行工作流（从检查点恢复）
    async def run_workflow():
        try:
            for node_name, state_dict in service.execute(workflow_id, resume=True):
                # 进度通过 WebSocket 推送
                pass
        except Exception as e:
            # 错误会在状态中反映
            pass

    asyncio.create_task(run_workflow())

    return {
        "message": "工作流已恢复",
        "workflow_id": workflow_id
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


@router.get("/novels/{workflow_id}/characters/relationships")
async def get_character_relationships(workflow_id: str):
    """获取角色关系列表"""
    service = get_workflow_service()
    state = service.state_manager.load_state(workflow_id)

    if state is None:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 获取小说标题
    novel_title = state.get("novel_title", "")
    if not novel_title:
        raise HTTPException(status_code=400, detail="工作流尚未开始，无法获取角色关系")

    from src.storage import NovelStorage

    storage = NovelStorage(novel_title)
    characters = storage.load_characters()

    if characters is None:
        raise HTTPException(status_code=404, detail="角色档案不存在")

    # 提取所有关系
    relationships = []
    for char in characters:
        for rel in char.relationships:
            relationships.append(CharacterRelationshipResponse(
                source=rel.source,
                target=rel.target,
                relationship_type=rel.relationship_type,
                description=rel.description,
                events=rel.events
            ))

    return {"relationships": relationships}


@router.get("/novels/{workflow_id}/characters/graph")
async def get_character_graph(workflow_id: str):
    """获取角色关系图数据（D3.js 格式）"""
    service = get_workflow_service()
    state = service.state_manager.load_state(workflow_id)

    if state is None:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 获取小说标题
    novel_title = state.get("novel_title", "")
    if not novel_title:
        raise HTTPException(status_code=400, detail="工作流尚未开始，无法获取角色关系图")

    from src.storage import NovelStorage

    storage = NovelStorage(novel_title)
    characters = storage.load_characters()

    if characters is None:
        raise HTTPException(status_code=404, detail="角色档案不存在")

    # 构建图数据
    nodes = []
    links = []
    seen_nodes = set()

    for char in characters:
        # 添加节点
        if char.name not in seen_nodes:
            nodes.append(CharacterGraphNode(id=char.name, name=char.name))
            seen_nodes.add(char.name)

        # 添加关系边
        for rel in char.relationships:
            # 确保目标节点存在
            if rel.target not in seen_nodes:
                nodes.append(CharacterGraphNode(id=rel.target, name=rel.target))
                seen_nodes.add(rel.target)

            links.append(CharacterGraphLink(
                source=rel.source,
                target=rel.target,
                type=rel.relationship_type
            ))

    return CharacterGraphData(nodes=nodes, links=links)


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
