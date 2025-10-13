import os
from dotenv import load_dotenv
import argparse

from src.workflow import create_workflow
from src.show import print_save
from src.log_config import loggers
from src.config_loader import ModelConfig, OutlineConfig

load_dotenv(override=True)
logger = loggers['main']

def get_args():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--model_type", default='api',type=str, help="local or api")

    return parser.parse_args()

api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")

def main():
    args = get_args()
    model_type = args.model_type
    if model_type == "api":
        model_name = input("请输入你的模型名字：")
        model_config = ModelConfig(
            api_key=api_key,
            api_url=base_url,
            model_name=model_name
        )
    elif model_type == "local":
        model_path = input("请输入你的模型路径：")
        model_config = ModelConfig(
            model_path=model_path
        )
    try:
        logger.info("开始小说生成流程")

        app = create_workflow(model_config)
        
        user_intent = input("请输入你的小说创作意图：")
        logger.info(f"用户创作意图: {user_intent}")
        result = app.invoke(
            {
                "user_intent":user_intent,
            },
            {
                "recursion_limit": OutlineConfig.min_chapters * 50  # 限制最大循环次数
            }
        )
        logger.info("小说生成流程完成, 准备输出结果")
        print_save(result)
        
    except Exception as e:
        print(f"[main] 发生错误：{str(e)}")
        
if __name__ == "__main__":

    main()
