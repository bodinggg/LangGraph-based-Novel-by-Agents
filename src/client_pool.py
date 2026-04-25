"""
单 Key 多客户端连接池

使用同一个 API Key 创建多个客户端实例，实现真正的并行请求。
每个客户端独立连接池，可同时发起请求，共享模型的 RPM/TPM 限额。
"""
import asyncio
import logging
from typing import List, Callable, Any, Optional, Dict
from dataclasses import dataclass
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class ClientStats:
    """客户端统计信息"""
    client_id: str
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency: float = 0.0

    @property
    def avg_latency(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_latency / self.request_count


class ClientPool:
    """单 Key 多客户端连接池

    使用同一个 API Key 创建多个客户端实例，
    实现真正的并行请求（受 API 限流约束）
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        num_clients: int = 4,
        max_concurrent_per_client: int = 3,
        api_type: str = "openai"
    ):
        """
        Args:
            api_key: API 密钥
            base_url: API 基础地址
            model_name: 模型名称
            num_clients: 客户端实例数量
            max_concurrent_per_client: 每个客户端的最大并发数
            api_type: API 类型 ("openai" 或 "anthropic")
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.num_clients = num_clients
        self.max_concurrent_per_client = max_concurrent_per_client
        self.api_type = api_type.lower()

        # 创建多个客户端实例
        self._clients: List[AsyncOpenAI] = []
        for i in range(num_clients):
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            self._clients.append(client)

        # 每个客户端独立的信号量（控制该客户端的并发数）
        self._semaphores = [
            asyncio.Semaphore(max_concurrent_per_client)
            for _ in range(num_clients)
        ]

        # 轮询索引
        self._index = 0
        self._lock = asyncio.Lock()

        # 客户端统计
        self._stats: Dict[str, ClientStats] = {
            f"client_{i}": ClientStats(client_id=f"client_{i}")
            for i in range(num_clients)
        }

        logger.info(
            f"[ClientPool] 初始化完成: {num_clients} 个客户端, "
            f"每客户端最大并发 {max_concurrent_per_client}"
        )

    async def execute(self, coro_func: Callable[[AsyncOpenAI, str], Any]) -> Any:
        """执行协程，自动分配客户端（轮询）

        Args:
            coro_func: 协程函数，签名 (client, client_id) -> result

        Returns:
            协程函数的结果
        """
        # 获取下一个客户端（线程安全轮询）
        async with self._lock:
            client_idx = self._index % self.num_clients
            self._index += 1

        client = self._clients[client_idx]
        client_id = f"client_{client_idx}"
        semaphore = self._semaphores[client_idx]
        stats = self._stats[client_id]

        async with semaphore:
            stats.request_count += 1
            logger.debug(f"[{client_id}] 开始执行")
            try:
                import time
                start_time = time.time()
                result = await coro_func(client, client_id)
                latency = time.time() - start_time
                stats.success_count += 1
                stats.total_latency += latency
                logger.debug(f"[{client_id}] 完成，耗时 {latency:.2f}s")
                return result
            except Exception as e:
                stats.failure_count += 1
                logger.warning(f"[{client_id}] 失败: {str(e)[:80]}")
                raise

    async def execute_batch(
        self,
        coro_func: Callable[[AsyncOpenAI, str], Any],
        num_tasks: int
    ) -> List[Any]:
        """批量执行多个任务（自动分配客户端）

        Args:
            coro_func: 协程函数，签名 (client, client_id) -> result
            num_tasks: 任务数量

        Returns:
            结果列表
        """
        tasks = [self.execute(coro_func) for _ in range(num_tasks)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict[str, ClientStats]:
        """获取所有客户端的统计信息"""
        return self._stats.copy()

    def log_stats(self):
        """打印客户端统计信息"""
        logger.info("=" * 50)
        logger.info("[ClientPool] 客户端统计:")
        for client_id, stats in self._stats.items():
            logger.info(
                f"  {client_id}: "
                f"请求 {stats.request_count}, "
                f"成功 {stats.success_count}, "
                f"失败 {stats.failure_count}, "
                f"平均延迟 {stats.avg_latency:.2f}s"
            )
        logger.info("=" * 50)

    def close(self):
        """关闭所有客户端（清理资源）"""
        # AsyncOpenAI 没有 close 方法，此处预留扩展
        logger.info("[ClientPool] 资源清理完成")
