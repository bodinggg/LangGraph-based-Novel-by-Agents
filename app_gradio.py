"""
FastAPI + Gradio 统一入口

同时提供：
- /ui -> Gradio UI
- /docs -> FastAPI Swagger
- /api/v1/* -> REST API
"""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(override=True)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gradio import mount_gradio_app

from ui_module.ui import NovelGeneratorUI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("✅ Novel Generator 服务已启动")
    yield


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="AI Novel Generator",
        description="多代理小说生成系统",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 根路径 - 跳转到 UI
    @app.get("/")
    async def root():
        return {
            "service": "AI Novel Generator",
            "version": "1.0.0",
            "ui": "/ui",
            "api_docs": "/docs"
        }

    # 健康检查
    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "service": "novel-generator"}

    # 创建 Gradio UI 并挂载到 /ui
    ui = NovelGeneratorUI()
    gradio_app = ui.create_interface()

    # 挂载 Gradio 到 FastAPI
    app = mount_gradio_app(app, gradio_app, path="/ui")

    return app


app = create_app()


def main():
    """启动服务"""
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "7999"))

    print(f"🚀 启动服务")
    print(f"   UI: http://{host}:{port}/ui")
    print(f"   API: http://{host}:{port}/docs")

    uvicorn.run(
        "app_gradio:app",
        host=host,
        port=port,
        reload=False
    )


if __name__ == "__main__":
    main()
