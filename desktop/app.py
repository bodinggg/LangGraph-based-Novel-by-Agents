"""
Desktop Application Entry Point
使用 pywebview 显示 Gradio UI，复用 app_gradio.py 的服务
"""
import os
import sys
import socket
import threading
import webview
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_free_port():
    """获取一个可用端口"""
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def create_app():
    """创建 FastAPI 应用（挂载 Gradio UI）"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from gradio import mount_gradio_app

    app = FastAPI(
        title="Novel by Agents - Desktop",
        description="AI Novel Generator Desktop Application",
        version="1.0.0"
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 创建 Gradio UI 并挂载到 /ui
    from ui_module.ui import NovelGeneratorUI
    ui = NovelGeneratorUI()
    gradio_app = ui.create_interface()
    app = mount_gradio_app(app, gradio_app, path="/ui")

    return app


def start_api_server(port, app):
    """启动 FastAPI 服务器"""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main():
    port = get_free_port()
    print(f"Starting server on port {port}...")

    # 创建并启动 API 服务器（包含 Gradio UI）
    app = create_app()
    server_thread = threading.Thread(target=start_api_server, args=(port, app), daemon=True)
    server_thread.start()

    # 等待服务器启动
    import time
    time.sleep(2)

    print(f"Server started, opening window...")
    print(f"UI available at: http://127.0.0.1:{port}/ui")

    # 创建 pywebview 窗口，加载 /ui 路径（Gradio UI）
    window = webview.create_window(
        title='Novel by Agents',
        url=f'http://127.0.0.1:{port}/ui',
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600),
        js_api=None
    )

    # 启动窗口
    webview.start(debug=False)

    print("Application closed.")


if __name__ == '__main__':
    main()
