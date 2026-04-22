"""
Desktop Application Build Script
使用 PyInstaller 将桌面应用打包为单个 .exe 文件
"""
import os
import sys
import shutil
from pathlib import Path

def get_project_root():
    return Path(__file__).parent

def clean_build():
    """清理之前的构建"""
    root = get_project_root()
    for dir_name in ['dist', 'build']:
        dir_path = root / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"Cleaned {dir_path}")

def build_executable():
    """使用 PyInstaller 构建可执行文件"""
    root = get_project_root()

    # 桌面应用入口
    desktop_app = root / 'desktop' / 'app.py'

    # 复制桌面应用到根目录（PyInstaller 需要）
    temp_app = root / 'desktop_app_temp.py'
    with open(desktop_app, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(temp_app, 'w', encoding='utf-8') as f:
        f.write(content)

    try:
        print("Building executable with PyInstaller...")

        # PyInstaller 命令
        args = [
            '--name=Novel_by_Agents',
            '--onefile',
            '--windowed',  # Windows 无控制台窗口
            f'--add-data={root / "desktop" / "templates"};desktop/templates',
            f'--add-data={root / "desktop" / "static"};desktop/static',
            '--hidden-import=fastapi',
            '--hidden-import=uvicorn',
            '--hidden-import=uvicorn.logging',
            '--hidden-import=uvicorn.structures',
            '--hidden-import=webview',
            '--hidden-import=pydantic',
            '--hidden-import=dotenv',
            '--hidden-import=langgraph',
            '--hidden-import=transformers',
            '--hidden-import=torch',
            '--collect-all=transformers',
            '--collect-all=gradio',
            '--noconfirm',
            str(temp_app)
        ]

        import PyInstaller.__main__
        PyInstaller.__main__.run(args)

    finally:
        # 清理临时文件
        if temp_app.exists():
            temp_app.unlink()
        print("Build complete!")

def main():
    print("=" * 50)
    print("Novel by Agents - Build Script")
    print("=" * 50)
    print()

    clean_build()
    build_executable()

    root = get_project_root()
    exe_path = root / 'dist' / 'Novel_by_Agents.exe'

    if exe_path.exists():
        print()
        print("=" * 50)
        print(f"SUCCESS! Executable created:")
        print(f"  {exe_path}")
        print()
        print(f"Size: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
        print("=" * 50)
    else:
        print()
        print("ERROR: Executable not found!")
        sys.exit(1)

if __name__ == '__main__':
    main()
