import logging
import os
from datetime import datetime
from enum import Enum
from typing import Optional


class LogMode(Enum):
    """日志模式枚举"""
    USER = "user"       # 用户模式：INFO级别，简洁输出
    DEVELOPER = "developer"  # 开发模式：DEBUG级别，详细输出


# ============================================================
# 日志格式标准 - Emoji 前缀约定
# ============================================================
# | 前缀 | 级别   | 用途                          |
# |------|--------|------------------------------|
# | 📖   | INFO   | 开始操作                       |
# | ✅   | INFO   | 操作完成                       |
# | ⚠️   | WARNING| 潜在问题                       |
# | 🔴   | ERROR  | 操作失败                       |
# | 🔄   | INFO   | 状态转换/路由决策               |
# | 💡   | DEBUG  | 决策原因/关键判断               |
# | 📊   | DEBUG  | 统计数据                       |
# | 🤖   | DEBUG  | LLM调用详情                    |
# | ⏳   | INFO   | 操作进行中                     |
# | 📋   | INFO   | 汇总报告                       |
# | 🎯   | INFO   | 目标/计划设定                  |
# ============================================================

class LogFormat:
    """日志格式常量"""
    # INFO 级别 - 用户可见的关键进度
    START = "📖"      # 开始操作
    COMPLETE = "✅"   # 操作完成
    TRANSITION = "🔄" # 状态转换/路由
    IN_PROGRESS = "⏳" # 操作进行中
    SUMMARY = "📋"    # 汇总报告
    TARGET = "🎯"     # 目标/计划设定

    # WARNING 级别 - 潜在问题
    WARNING = "⚠️"    # 潜在问题

    # ERROR 级别 - 操作失败
    ERROR = "🔴"      # 操作失败

    # DEBUG 级别 - 开发调试详情
    REASON = "💡"     # 决策原因
    STATS = "📊"     # 统计数据
    LLM = "🤖"        # LLM调用

    @classmethod
    def info(cls, prefix: str, message: str) -> str:
        """INFO级别日志消息"""
        return f"{prefix} {message}"

    @classmethod
    def debug(cls, prefix: str, message: str) -> str:
        """DEBUG级别日志消息"""
        return f"{prefix} {message}"

    @classmethod
    def warn(cls, prefix: str, message: str) -> str:
        """WARNING级别日志消息"""
        return f"{prefix} {message}"

    @classmethod
    def error(cls, prefix: str, message: str) -> str:
        """ERROR级别日志消息"""
        return f"{prefix} {message}"


# 便捷函数
def log_start(message: str) -> str:
    """开始操作日志"""
    return f"{LogFormat.START} {message}"

def log_complete(message: str) -> str:
    """完成操作日志"""
    return f"{LogFormat.COMPLETE} {message}"

def log_transition(message: str) -> str:
    """状态转换日志"""
    return f"{LogFormat.TRANSITION} {message}"

def log_warning(message: str) -> str:
    """警告日志"""
    return f"{LogFormat.WARNING} {message}"

def log_error(message: str) -> str:
    """错误日志"""
    return f"{LogFormat.ERROR} {message}"

def log_reason(message: str) -> str:
    """决策原因日志 (DEBUG)"""
    return f"{LogFormat.REASON} {message}"

def log_stats(message: str) -> str:
    """统计数据日志 (DEBUG)"""
    return f"{LogFormat.STATS} {message}"

def log_llm(message: str) -> str:
    """LLM调用日志 (DEBUG)"""
    return f"{LogFormat.LLM} {message}"

def log_in_progress(message: str) -> str:
    """操作进行中日志 (INFO)"""
    return f"{LogFormat.IN_PROGRESS} {message}"

def log_summary(message: str) -> str:
    """汇总报告日志 (INFO)"""
    return f"{LogFormat.SUMMARY} {message}"

def log_target(message: str) -> str:
    """目标/计划设定日志 (INFO)"""
    return f"{LogFormat.TARGET} {message}"


# 全局日志模式
_log_mode: Optional[LogMode] = None


def _get_log_mode_from_env() -> str:
    """从环境变量获取日志模式"""
    mode = os.environ.get("LOG_MODE", "user").lower().strip()
    return mode if mode in ("user", "developer") else "user"


def get_log_mode() -> LogMode:
    """获取当前日志模式（全局）"""
    global _log_mode
    if _log_mode is None:
        # 懒加载：从环境变量读取
        mode_str = _get_log_mode_from_env()
        _log_mode = LogMode.DEVELOPER if mode_str == "developer" else LogMode.USER
    return _log_mode


def set_log_mode(mode: LogMode) -> None:
    """设置全局日志模式"""
    global _log_mode
    _log_mode = mode

    # 动态调整根日志器级别
    root_logger = logging.getLogger()
    if mode == LogMode.DEVELOPER:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)


def setup_logging(mode: Optional[LogMode] = None):
    """配置项目日志系统

    Args:
        mode: 日志模式，默认为USER。从环境变量LOG_MODE读取或使用USER。
    """
    # 确定模式
    if mode is None:
        mode = get_log_mode()

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

    # 根据模式设置日志级别
    log_level = logging.DEBUG if mode == LogMode.DEVELOPER else logging.INFO

    # 配置根日志器
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )

    # 过滤第三方库 verbose DEBUG 日志（保留 WARNING 及以上）
    verbose_loggers = [
        "urllib3.connectionpool",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.proxy",
        "httpx._client",
        "openai._base_client",
        "langsmith.client",
        "langsmith._internal._serde",
        "httpcore._backends",
    ]
    for logger_name in verbose_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 为不同模块创建专用日志器
    modules = ['workflow', 'node', 'main', 'gradio', 'feedback', 'specialist', 'api', 'multi_agent']
    return {module: logging.getLogger(module) for module in modules}


# Lazy initialization - loggers created on first access
_loggers = None


def get_loggers():
    """Get loggers, initializing on first call (lazy init)."""
    global _loggers
    if _loggers is None:
        _loggers = setup_logging()
    return _loggers


class _LazyLoggers:
    """Backward-compatible wrapper for module-level `loggers` import.

    Allows `from src.log_config import loggers; loggers['workflow']`
    to work with lazy initialization.
    """
    __slots__ = ()

    def __getitem__(self, key):
        return get_loggers()[key]

    def get(self, key, default=None):
        return get_loggers().get(key, default)

    def __iter__(self):
        return iter(get_loggers())

    def __len__(self):
        return len(get_loggers())

    def keys(self):
        return get_loggers().keys()

    def values(self):
        return get_loggers().values()

    def items(self):
        return get_loggers().items()


loggers = _LazyLoggers()
