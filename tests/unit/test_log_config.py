"""
Unit tests for logging configuration
"""
import pytest
import logging
from src.log_config import loggers, get_loggers, _LazyLoggers, setup_logging


class TestLogConfig:
    """Tests for log_config module"""

    def test_setup_logging(self):
        """Test setup_logging creates loggers"""
        module_loggers = setup_logging()

        assert isinstance(module_loggers, dict)
        assert 'workflow' in module_loggers
        assert 'node' in module_loggers
        assert 'main' in module_loggers
        assert 'gradio' in module_loggers
        assert 'feedback' in module_loggers
        assert 'specialist' in module_loggers

        # All values should be logger instances
        for name, logger in module_loggers.items():
            assert isinstance(logger, logging.Logger)
            assert logger.name == name

    def test_get_loggers(self):
        """Test get_loggers returns dict"""
        result = get_loggers()

        assert isinstance(result, dict)
        assert len(result) > 0

    def test_loggers_is_lazy_loggers_instance(self):
        """Test that module-level loggers is _LazyLoggers instance"""
        from src.log_config import loggers as mod_loggers

        assert isinstance(mod_loggers, _LazyLoggers)

    def test_lazy_loggers_getitem(self):
        """Test _LazyLoggers __getitem__"""
        lg = _LazyLoggers()

        # Should get logger via lazy initialization
        workflow_logger = lg['workflow']
        assert isinstance(workflow_logger, logging.Logger)

    def test_lazy_loggers_get(self):
        """Test _LazyLoggers get method"""
        lg = _LazyLoggers()

        # Get existing
        logger = lg.get('workflow')
        assert isinstance(logger, logging.Logger)

        # Get non-existing with default
        default_logger = lg.get('nonexistent', logging.getLogger('default'))
        assert default_logger.name == 'default'

    def test_lazy_loggers_keys(self):
        """Test _LazyLoggers keys method"""
        lg = _LazyLoggers()

        keys = lg.keys()
        assert 'workflow' in keys
        assert 'node' in keys

    def test_lazy_loggers_iter(self):
        """Test _LazyLoggers iteration"""
        lg = _LazyLoggers()

        names = list(lg)
        assert 'workflow' in names

    def test_lazy_loggers_len(self):
        """Test _LazyLoggers length"""
        lg = _LazyLoggers()

        assert len(lg) > 0

    def test_lazy_loggers_values(self):
        """Test _LazyLoggers values method"""
        lg = _LazyLoggers()

        values = list(lg.values())
        assert len(values) > 0
        assert all(isinstance(v, logging.Logger) for v in values)

    def test_lazy_loggers_items(self):
        """Test _LazyLoggers items method"""
        lg = _LazyLoggers()

        items = list(lg.items())
        assert len(items) > 0
        assert all(isinstance(k, str) and isinstance(v, logging.Logger) for k, v in items)


class TestLogMode:
    """Tests for dual-mode logging system"""

    def test_log_mode_enum_exists(self):
        """Test LogMode enum is defined"""
        from src.log_config import LogMode
        assert hasattr(LogMode, 'USER')
        assert hasattr(LogMode, 'DEVELOPER')
        assert LogMode.USER.value == "user"
        assert LogMode.DEVELOPER.value == "developer"

    def test_set_log_mode(self):
        """Test set_log_mode changes log level"""
        from src.log_config import set_log_mode, LogMode, get_log_mode, _log_mode
        import src.log_config as log_config

        # Reset global state
        log_config._log_mode = None

        # Set to USER mode
        set_log_mode(LogMode.USER)
        assert get_log_mode() == LogMode.USER

        # Set to DEVELOPER mode
        set_log_mode(LogMode.DEVELOPER)
        assert get_log_mode() == LogMode.DEVELOPER

        # Reset for other tests
        log_config._log_mode = None

    def test_get_log_mode_default(self):
        """Test get_log_mode returns default when not set"""
        from src.log_config import get_log_mode, LogMode
        import src.log_config as log_config

        # Reset global state
        log_config._log_mode = None
        mode = get_log_mode()
        assert mode == LogMode.USER  # Default should be USER

    def test_setup_logging_accepts_mode(self):
        """Test setup_logging accepts mode parameter"""
        from src.log_config import setup_logging, LogMode, set_log_mode

        # Should accept USER mode
        loggers = setup_logging(mode=LogMode.USER)
        assert isinstance(loggers, dict)

        # Should accept DEVELOPER mode
        loggers = setup_logging(mode=LogMode.DEVELOPER)
        assert isinstance(loggers, dict)

    def test_developer_mode_sets_debug_level(self):
        """Test DEVELOPER mode sets root logger to DEBUG"""
        import logging
        from src.log_config import set_log_mode, LogMode
        import src.log_config as log_config

        # Reset global state
        log_config._log_mode = None
        # Ensure root logger level is at INFO first
        logging.getLogger().setLevel(logging.INFO)

        # Now switch to DEVELOPER mode
        set_log_mode(LogMode.DEVELOPER)
        root_logger = logging.getLogger()

        # In DEVELOPER mode, root should be DEBUG
        assert root_logger.level <= logging.DEBUG

    def test_user_mode_sets_info_level(self):
        """Test USER mode sets root logger to INFO"""
        import logging
        from src.log_config import set_log_mode, get_log_mode, LogMode
        import src.log_config as log_config

        # Reset global state
        log_config._log_mode = None
        # Ensure root logger level is at DEBUG first
        logging.getLogger().setLevel(logging.DEBUG)

        # Now switch to USER mode
        set_log_mode(LogMode.USER)
        root_logger = logging.getLogger()

        # In USER mode, root should be INFO
        assert root_logger.level == logging.INFO

    def test_log_mode_from_env_var(self, monkeypatch):
        """Test LOG_MODE environment variable is read"""
        import os
        from src.log_config import _get_log_mode_from_env

        # Test DEVELOPER env var
        monkeypatch.setenv("LOG_MODE", "developer")
        assert _get_log_mode_from_env() == "developer"

        # Test USER env var
        monkeypatch.setenv("LOG_MODE", "user")
        assert _get_log_mode_from_env() == "user"

    def test_invalid_env_var_defaults_to_user(self, monkeypatch):
        """Test invalid LOG_MODE value defaults to USER"""
        from src.log_config import _get_log_mode_from_env

        monkeypatch.setenv("LOG_MODE", "invalid")
        assert _get_log_mode_from_env() == "user"

    def test_all_entry_points_use_same_logger(self):
        """Test all registered modules get loggers"""
        from src.log_config import setup_logging, LogMode

        loggers = setup_logging(mode=LogMode.USER)

        # Should have all expected modules
        expected = ['workflow', 'node', 'main', 'gradio', 'feedback', 'specialist', 'api', 'multi_agent']
        for module in expected:
            assert module in loggers, f"Missing module: {module}"


class TestLogFormat:
    """Tests for LogFormat class and convenience functions"""

    def test_log_format_constants_exist(self):
        """Test LogFormat constants are defined"""
        from src.log_config import LogFormat

        assert LogFormat.START == "📖"
        assert LogFormat.COMPLETE == "✅"
        assert LogFormat.TRANSITION == "🔄"
        assert LogFormat.WARNING == "⚠️"
        assert LogFormat.ERROR == "🔴"
        assert LogFormat.REASON == "💡"
        assert LogFormat.STATS == "📊"
        assert LogFormat.LLM == "🤖"

    def test_log_format_info(self):
        """Test LogFormat.info method"""
        from src.log_config import LogFormat

        result = LogFormat.info("📖", "开始操作")
        assert result == "📖 开始操作"

    def test_log_format_debug(self):
        """Test LogFormat.debug method"""
        from src.log_config import LogFormat

        result = LogFormat.debug("💡", "决策原因")
        assert result == "💡 决策原因"

    def test_log_start_function(self):
        """Test log_start convenience function"""
        from src.log_config import log_start

        result = log_start("开始写章节")
        assert result == "📖 开始写章节"
        assert "📖" in result

    def test_log_complete_function(self):
        """Test log_complete convenience function"""
        from src.log_config import log_complete

        result = log_complete("章节已完成")
        assert result == "✅ 章节已完成"

    def test_log_transition_function(self):
        """Test log_transition convenience function"""
        from src.log_config import log_transition

        result = log_transition("进入下一章")
        assert result == "🔄 进入下一章"

    def test_log_warning_function(self):
        """Test log_warning convenience function"""
        from src.log_config import log_warning

        result = log_warning("潜在问题")
        assert result == "⚠️ 潜在问题"

    def test_log_error_function(self):
        """Test log_error convenience function"""
        from src.log_config import log_error

        result = log_error("操作失败")
        assert result == "🔴 操作失败"

    def test_log_reason_function(self):
        """Test log_reason convenience function"""
        from src.log_config import log_reason

        result = log_reason("选择分支A")
        assert result == "💡 选择分支A"

    def test_log_stats_function(self):
        """Test log_stats convenience function"""
        from src.log_config import log_stats

        result = log_stats("处理了10个请求")
        assert result == "📊 处理了10个请求"

    def test_log_llm_function(self):
        """Test log_llm convenience function"""
        from src.log_config import log_llm

        result = log_llm("调用LLM分析")
        assert result == "🤖 调用LLM分析"


class TestAgentLoggerDecorator:
    """Tests for log_agent_call decorator in agent.py"""

    def test_log_agent_call_decorator(self):
        """Test the log_agent_call decorator works correctly"""
        from src.agent import log_agent_call

        # Create a simple test function
        @log_agent_call("TestAgent", "test_method")
        def test_function():
            return "test result"

        # Should execute without error
        result = test_function()
        assert result == "test result"

    def test_log_agent_call_with_args(self):
        """Test log_agent_call with function that takes args"""
        from src.agent import log_agent_call

        @log_agent_call("TestAgent", "method_with_args")
        def add(a, b):
            return a + b

        result = add(3, 4)
        assert result == 7

    def test_log_agent_call_with_string_return(self):
        """Test log_agent_call handles string returns"""
        from src.agent import log_agent_call

        @log_agent_call("TestAgent", "string_return")
        def get_content():
            return "This is a test content"

        result = get_content()
        assert result == "This is a test content"

    def test_log_agent_call_with_long_string_return(self):
        """Test log_agent_call handles long string returns"""
        from src.agent import log_agent_call

        @log_agent_call("TestAgent", "long_string")
        def get_long_content():
            return "A" * 200  # Longer than 100 chars

        result = get_long_content()
        assert len(result) == 200

    def test_log_agent_call_with_non_string_return(self):
        """Test log_agent_call handles non-string returns"""
        from src.agent import log_agent_call

        @log_agent_call("TestAgent", "dict_return")
        def get_dict():
            return {"key": "value"}

        result = get_dict()
        assert result == {"key": "value"}

    def test_log_agent_call_with_exception(self):
        """Test log_agent_call properly propagates exceptions"""
        from src.agent import log_agent_call

        @log_agent_call("TestAgent", "raising_method")
        def raising_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            raising_function()
