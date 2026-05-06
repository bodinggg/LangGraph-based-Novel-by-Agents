"""
思考过程日志记录器
"""
import os
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Optional
import threading


class _NoOpThinkingLogger:
    """No-op logger for testing - does nothing"""
    def log_thinking(self, **kwargs):
        pass


class ThinkingLogger:
    """思考过程日志记录

    改进：文件名包含 agent_name、chapter_index，便于区分不同 Agent 的思考过程
    """

    def __init__(self, output_dir: str = "thinking_logs", novel_title: str = ""):
        self.output_dir = output_dir
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.novel_title = novel_title

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 日志文件路径字典 {agent_name: log_file_path}
        self._log_files: dict[str, str] = {}
        self._last_agent: Optional[str] = None  # 追踪上一个 agent
        self._lock = threading.Lock()

    def _make_log_path(self, agent_name: str, chapter_index: Optional[int] = None) -> str:
        """生成日志文件路径

        格式: {小说标题_}Agent名称_章节{index}_{timestamp}.log
        示例:
          - OutlineGeneratorAgent_20260505_093648.log
          - 暗影之刃_WriterAgent_ch01_20260505_094050.log
          - ConsistencyAgent_ch01_20260505_094050.log
        """
        parts = []
        if self.novel_title:
            parts.append(self.novel_title)
        parts.append(agent_name)
        if chapter_index is not None:
            parts.append(f"ch{chapter_index+1:02d}")
        parts.append(self.current_session_id)

        filename = "_".join(parts) + ".log"
        return os.path.join(self.output_dir, filename)

    def _init_log_file(self, log_path: str, agent_name: str):
        """初始化日志文件"""
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"AI思考过程日志 - Agent: {agent_name}\n")
            f.write(f"会话ID: {self.current_session_id}\n")
            f.write(f"小说: {self.novel_title or '(未指定)'}\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    def log_thinking(self,
                     agent_name: str,
                     node_name: str,
                     prompt_content: Any,
                     response_content: str,
                     chapter_index: Optional[int] = None,
                     error_message: Optional[str] = None):
        """记录一次思考过程到日志文件

        Args:
            agent_name: Agent 名称（如 WriterAgent, ConsistencyAgent）
            node_name: 节点名称（如 write_chapter）
            prompt_content: 输入提示
            response_content: 输出响应
            chapter_index: 章节索引（用于区分同一 Agent 的不同章节）
            error_message: 错误信息
        """

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            # 每个 agent + chapter 组合一个独立的文件
            log_file = self._make_log_path(agent_name, chapter_index)

            # 首次写入该 agent 时初始化文件
            if log_file not in self._log_files.values():
                self._init_log_file(log_file, agent_name)

            # 记录所有活跃的 log_file
            if log_file not in self._log_files:
                self._log_files[agent_name] = log_file

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {agent_name} -> {node_name}")
                if chapter_index is not None:
                    f.write(f" [第{chapter_index+1}章]")
                f.write("\n")

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
        chapter_hint = f" 第{chapter_index+1}章" if chapter_index is not None else ""
        print(f"[LOG] {agent_name} -> {node_name}{chapter_hint} ({timestamp})")

    @property
    def log_file(self) -> Optional[str]:
        """返回当前（最后写入的）日志文件路径"""
        if self._log_files:
            return list(self._log_files.values())[-1]
        return None


# 线程/协程安全的上下文变量
_logger_var: ContextVar[Optional[ThinkingLogger]] = ContextVar('logger', default=None)


def get_logger(novel_title: str = "") -> ThinkingLogger:
    """获取当前上下文的 logger 实例（线程/协程安全）

    Args:
        novel_title: 小说标题（用于日志文件名区分）
    """
    logger = _logger_var.get()
    if logger is None:
        logger = ThinkingLogger(novel_title=novel_title)
        _logger_var.set(logger)
    elif novel_title and not logger.novel_title:
        # 首次设置小说标题
        logger.novel_title = novel_title
    return logger


def get_simple_logger() -> ThinkingLogger:
    """获取全局简单日志记录器实例（向后兼容）"""
    return get_logger()


def create_disabled_logger() -> ThinkingLogger:
    """Create a disabled no-op logger for testing"""
    return _NoOpThinkingLogger()


def log_agent_thinking(agent_name: str,
                       node_name: str,
                       prompt_content: Any,
                       response_content: str,
                       chapter_index: Optional[int] = None,
                       error_message: Optional[str] = None):
    """便捷函数：记录Agent思考过程到日志文件

    Args:
        agent_name: Agent 名称
        node_name: 节点名称
        prompt_content: 输入提示
        response_content: 输出响应
        chapter_index: 章节索引（用于文件命名区分）
        error_message: 错误信息
    """
    logger = get_logger()
    logger.log_thinking(
        agent_name=agent_name,
        node_name=node_name,
        prompt_content=prompt_content,
        response_content=response_content,
        chapter_index=chapter_index,
        error_message=error_message
    )
