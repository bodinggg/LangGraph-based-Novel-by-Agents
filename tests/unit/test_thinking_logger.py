"""
Unit tests for src/thinking_logger.py
"""
import pytest
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.thinking_logger import (
    ThinkingLogger,
    get_logger,
    _logger_var,
    create_disabled_logger,
    log_agent_thinking
)


class TestThinkingLogger:
    """Tests for ThinkingLogger class"""

    def test_init_creates_log_file(self, tmp_path):
        """Test that logger creates log file"""
        logger = ThinkingLogger(output_dir=str(tmp_path))
        assert logger.log_file.endswith('.log')
        assert tmp_path.exists()

    def test_log_thinking_writes_to_file(self, tmp_path):
        """Test that log_thinking writes content"""
        logger = ThinkingLogger(output_dir=str(tmp_path))
        logger.log_thinking(
            agent_name="TestAgent",
            node_name="test_node",
            prompt_content="Test prompt",
            response_content="Test response"
        )

        with open(logger.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "TestAgent" in content
            assert "test_node" in content
            assert "Test prompt" in content
            assert "Test response" in content

    def test_disabled_logger_does_nothing(self):
        """Test that disabled logger does nothing"""
        logger = create_disabled_logger()
        # Should not raise
        logger.log_thinking(
            agent_name="Test",
            node_name="test",
            prompt_content="prompt",
            response_content="response"
        )


class TestContextVarThreading:
    """Tests for ContextVar threading safety"""

    def test_get_logger_returns_same_instance_in_context(self):
        """Test that get_logger returns same instance within same context"""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_different_threads_get_different_loggers(self):
        """Test that different threads get different logger instances"""
        results = {}

        def thread_task(thread_id):
            logger = get_logger()
            results[thread_id] = logger

        threads = [threading.Thread(target=thread_task, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have its own logger instance
        loggers = list(results.values())
        assert len(set(id(l) for l in loggers)) == 3, "Each thread should have its own logger"

    def test_asyncio_tasks_share_logger_in_same_thread(self):
        """Test that asyncio tasks in same thread share logger (expected ContextVar behavior)"""
        results = {}

        async def task(task_id):
            # ContextVar is thread-level, not task-level
            # asyncio tasks run in same thread, so they share the logger
            logger = get_logger()
            results[task_id] = logger

        async def main():
            await asyncio.gather(
                task(1),
                task(2),
                task(3)
            )

        asyncio.run(main())

        # All tasks in same thread should share same logger
        loggers = list(results.values())
        assert len(set(id(l) for l in loggers)) == 1, "Asyncio tasks in same thread share logger"

    def test_explicit_set_per_request(self):
        """Test that setting logger explicitly per request works correctly"""
        results = {}

        async def task_with_isolation(task_id):
            # Simulate per-request isolation by explicitly setting
            _logger_var.set(ThinkingLogger(output_dir=f"thinking_logs_{task_id}"))
            logger = get_logger()
            results[task_id] = logger

        async def main():
            await asyncio.gather(
                task_with_isolation(1),
                task_with_isolation(2),
                task_with_isolation(3)
            )

        asyncio.run(main())

        # Each task should have its own logger when explicitly set
        loggers = list(results.values())
        assert len(set(id(l) for l in loggers)) == 3, "Each task with explicit set has its own logger"

    def test_thread_pool_creates_one_logger_per_thread(self):
        """Test that ThreadPoolExecutor creates one logger per worker thread"""
        loggers_in_tasks = []

        def task():
            logger = get_logger()
            loggers_in_tasks.append(logger)

        # Run 4 tasks in pool with 2 workers = 2 threads
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(task) for _ in range(4)]
            for f in futures:
                f.result()

        # Should have 2 loggers (one per thread)
        assert len(set(id(l) for l in loggers_in_tasks)) == 2, "One logger per thread"


class TestLogAgentThinking:
    """Tests for log_agent_thinking convenience function"""

    def test_log_agent_thinking_works(self, tmp_path, monkeypatch):
        """Test that log_agent_thinking calls logger"""
        # Create logger with tmp path
        logger = ThinkingLogger(output_dir=str(tmp_path))

        # Set the context var to our logger
        _logger_var.set(logger)

        # Should not raise
        log_agent_thinking(
            agent_name="TestAgent",
            node_name="test_node",
            prompt_content="Test prompt",
            response_content="Test response"
        )

        # Verify content was written
        with open(logger.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "TestAgent" in content
