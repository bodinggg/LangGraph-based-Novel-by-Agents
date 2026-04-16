"""
FastAPI 服务入口 - 多客户端支持

提供 REST API 和 WebSocket 接口，支持 CLI、Web、Desktop App 等多种客户端。
"""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(override=True)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.workflow_service import get_workflow_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化服务
    _ = get_workflow_service()
    print("✅ AI Novel Generator API 已启动")
    yield
    # 关闭时清理


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="AI Novel Generator API",
        description="多代理小说生成系统 API",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS 配置 - 允许所有来源（开发环境）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 根路径
    @app.get("/")
    async def root():
        return {
            "service": "AI Novel Generator API",
            "version": "1.0.0",
            "docs": "/docs",
            "message": "欢迎使用 AI 小说生成系统 API"
        }

    # 注册路由
    app.include_router(router)

    return app


app = create_app()


def main():
    """启动 API 服务"""
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8001"))

    print(f"🚀 启动 API 服务: http://{host}:{port}")
    print(f"📚 API 文档: http://{host}:{port}/docs")
    print(f"📊 WebSocket: ws://{host}:{port}/api/v1/novels/{{workflow_id}}/ws")

    uvicorn.run(
        "app_api:app",
        host=host,
        port=port,
        reload=False
    )


if __name__ == "__main__":
    main()
