"""
ClientPool 单元测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.client_pool import ClientPool, ClientStats


def async_test(coro):
    """Decorator to run async coroutines in sync test context"""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


class TestClientStats:
    """ClientStats 数据类测试"""

    def test_avg_latency_zero_requests(self):
        stats = ClientStats(client_id="client_0")
        assert stats.avg_latency == 0.0

    def test_avg_latency_with_requests(self):
        stats = ClientStats(client_id="client_0", request_count=5, total_latency=50.0)
        assert stats.avg_latency == 10.0


class TestClientPoolInit:
    """ClientPool 初始化测试"""

    def test_init_creates_correct_number_of_clients(self):
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model",
            num_clients=4,
            max_concurrent_per_client=3
        )
        assert pool.num_clients == 4
        assert len(pool._clients) == 4
        assert len(pool._semaphores) == 4

    def test_init_stats_created(self):
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )
        assert len(pool._stats) == pool.num_clients
        for client_id in pool._stats:
            assert client_id.startswith("client_")


class TestClientPoolExecute:
    """ClientPool.execute 测试"""

    @async_test
    async def test_execute_assigns_different_clients(self):
        """测试轮询分配不同客户端"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model",
            num_clients=3,
            max_concurrent_per_client=1
        )

        assigned_clients = []

        async def mock_coro(client, client_id):
            assigned_clients.append(client_id)
            await asyncio.sleep(0.01)
            return "done"

        # 执行 6 次，应该轮询分配
        for _ in range(6):
            await pool.execute(mock_coro)

        # client_0, client_1, client_2, client_0, client_1, client_2
        assert assigned_clients == ["client_0", "client_1", "client_2", "client_0", "client_1", "client_2"]

    @async_test
    async def test_execute_respects_semaphore_limit(self):
        """测试信号量限制并发"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model",
            num_clients=1,
            max_concurrent_per_client=2  # 限制为 2
        )

        concurrent_count = 0
        max_concurrent = 0

        async def mock_coro(client, client_id):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return "done"

        # 启动 4 个任务，受 max_concurrent_per_client=2 限制
        tasks = [pool.execute(mock_coro) for _ in range(4)]
        await asyncio.gather(*tasks)

        # 最大并发数应该 <= 2
        assert max_concurrent <= 2

    @async_test
    async def test_execute_updates_stats(self):
        """测试统计信息更新"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model",
            num_clients=2,
            max_concurrent_per_client=1
        )

        async def mock_coro(client, client_id):
            await asyncio.sleep(0.01)
            return "done"

        await pool.execute(mock_coro)
        await pool.execute(mock_coro)

        stats = pool.get_stats()
        total_requests = sum(s.request_count for s in stats.values())
        assert total_requests == 2

    @async_test
    async def test_execute_propagates_exception(self):
        """测试异常传播"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )

        async def mock_coro(client, client_id):
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await pool.execute(mock_coro)


class TestClientPoolExecuteBatch:
    """ClientPool.execute_batch 测试"""

    @async_test
    async def test_execute_batch_returns_results(self):
        """测试批量执行返回结果"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )

        async def mock_coro(client, client_id):
            await asyncio.sleep(0.01)
            return f"result_{client_id}"

        results = await pool.execute_batch(mock_coro, 3)
        assert len(results) == 3
        # 结果应该是 (result, result, result) 或 (exception, ...)
        assert any("client_" in str(r) for r in results if not isinstance(r, Exception))

    @async_test
    async def test_execute_batch_with_exceptions(self):
        """测试批量执行中的异常处理"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )

        call_count = 0

        async def mock_coro(client, client_id):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("error on second call")
            return "ok"

        results = await pool.execute_batch(mock_coro, 3)
        assert len(results) == 3
        # return_exceptions=True 应该捕获异常
        assert any(isinstance(r, ValueError) for r in results)


class TestClientPoolLogStats:
    """ClientPool.log_stats 测试"""

    def test_log_stats_runs_without_error(self):
        """测试日志打印不报错"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )
        # 不应抛出异常
        pool.log_stats()


class TestClientPoolClose:
    """ClientPool.close 测试"""

    def test_close_runs_without_error(self):
        """测试关闭不报错"""
        pool = ClientPool(
            api_key="test-key",
            base_url="https://api.test.com",
            model_name="test-model"
        )
        pool.close()
