"""
思考过程日志记录器
"""
import os
from datetime import datetime
from typing import Any, Optional

class ThinkingLogger:
    """思考过程日志记录"""
    
    def __init__(self, output_dir: str = "thinking_logs"):
        self.output_dir = output_dir
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 日志文件路径
        self.log_file = os.path.join(output_dir, f"过程记录_{self.current_session_id}.log")
        
        # 初始化日志文件
        self._init_log_file()
        
    def _init_log_file(self):
        """初始化日志文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"AI思考过程日志 - 会话ID: {self.current_session_id}\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
    
    def log_thinking(self,
                    agent_name: str,
                    node_name: str,
                    prompt_content: Any,
                    response_content: str,
                    error_message: Optional[str] = None):
        """记录一次思考过程到日志文件"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {agent_name} -> {node_name}\n")
                
            if error_message:
                f.write(f"ERROR: {error_message}\n")
                
            if not isinstance(prompt_content, str):
                prompt_content = str(prompt_content)
                
            f.write("="*100 + "\n")
            f.write(f"INPUT: \n")
            f.write(prompt_content)
            f.write("-"*100 + "\n")
            f.write(f"OUTPUT: \n")
            f.write(response_content)
            f.write("\n" + "="*100 + "\n\n")
        
        # 控制台简单提示
        print(f"[LOG] {agent_name} -> {node_name} ({timestamp})")

# 全局日志记录器实例
_global_logger = None

def get_simple_logger() -> ThinkingLogger:
    """获取全局简单日志记录器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = ThinkingLogger()
    return _global_logger

def log_agent_thinking(agent_name: str, 
                      node_name: str,
                      prompt_content: Any,
                      response_content: str,
                      error_message: Optional[str] = None):
    """便捷函数：记录Agent思考过程到日志文件"""
    logger = get_simple_logger()
    logger.log_thinking(
        agent_name=agent_name,
        node_name=node_name,
        prompt_content=prompt_content,
        response_content=response_content,
        error_message=error_message
    )
