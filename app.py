from model import *
from workflow import *
from client import *
from node import *
from show import *
from state import *
from tool import *

def main():
    model_path = "your-local-model-path"
    
    try:
        app = create_workflow(model_path)
        user_intent = input("请输入你的小说创作意图：")

        result = app.invoke(
            {
                "user_intent":user_intent,
            },
            {
                "recursion_limit": 1000  # 限制最大循环次数
            }
        )
        print_save(result)
        
    except Exception as e:
        print(f"[main] 发生错误：{str(e)}")
        
if __name__ == "__main__":
    main()