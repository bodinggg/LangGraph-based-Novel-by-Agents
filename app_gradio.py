import argparse

from ui_module.ui import NovelGeneratorUI

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="端口号", default=7999)
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    ui = NovelGeneratorUI()
    app = ui.create_interface()
    # 自定义端口号
    app.launch(server_port=args.port)
