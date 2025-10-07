import argparse
from src.workflow import create_workflow
from src.show import print_save
from src.log_config import loggers


logger = loggers['main']

def get_parser():
    parser = argparse.ArgumentParser()
    
    parser.add_argument('--model-path',
                        required=True,
                        help="你的本地模型路径")
    return parser.parse_args()


def main():
    args = get_parser()
    model_path = args.model_path
    
    try:
        logger.info("开始小说生成流程")
        logger.info(f"使用模型路径：{model_path}")
        
        app = create_workflow(model_path)
        user_intent = input("请输入你的小说创作意图：")
        logger.info(f"用户创作意图: {user_intent}")
        result = app.invoke(
            {
                "user_intent":user_intent,
            },
            {
                "recursion_limit": 1000  # 限制最大循环次数
            }
        )
        logger.info("小说生成流程完成, 准备输出结果")
        print_save(result)
        
    except Exception as e:
        print(f"[main] 发生错误：{str(e)}")
        
if __name__ == "__main__":

    main()
