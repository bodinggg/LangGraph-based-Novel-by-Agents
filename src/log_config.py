import logging
import os
from datetime import datetime

def setup_logging():
    """配置项目日志系统"""
    # 创建日志目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志文件名（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"novel_generator_{timestamp}.log")
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 配置根日志器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    # 为不同模块创建专用日志器
    modules = ['workflow', 'node', 'main', 'gradio','feedback']
    loggers = {module: logging.getLogger(module) for module in modules}
    
    return loggers

# 初始化日志器
loggers = setup_logging()
