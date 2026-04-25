"""
多 Key 路由管理器

支持多 API Key 轮询，实现真正的并行请求
"""
import asyncio
import logging
import time
from typing import List, Callable, Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KeyStats:
    """记录每个 Key 的使用统计"""
    key: str
    request_count: int = 0
    error_count: int = 0
    total_latency: float = 0.0

    @property
    def avg_latency(self) -> float:
        return self.total_latency / self.request_count if self.request_count > 0 else 0.0


class KeyRouter:
    """多 Key 轮询路由器

    特性：
    - 轮询策略分配 Key
    - Per-key Semaphore 限流
    - 统计每个 Key 的使用情况
    - Failover 机制（某个 Key 失败时自动切换）
    """

    def __init__(
        self,
        keys: List[str],
        max_concurrent_per_key: int = 3,
        enable_stats: bool = True
    ):
        """
        Args:
            keys: API Key 列表
            max_concurrent_per_key: 每个 Key 的最大并发数
            enable_stats: 是否启用统计
        """
        if not keys:
            raise ValueError("API keys list cannot be empty")

        self.keys = keys
        self.max_concurrent_per_key = max_concurrent_per_key
        self.enable_stats = enable_stats

        # 轮询索引
        self._round_robin_index = 0
        self._index_lock = asyncio.Lock()

        # Per-key Semaphore
        self._semaphores: Dict[str, asyncio.Semaphore] = {
            key: asyncio.Semaphore(max_concurrent_per_key) for key in keys
        }

        # Per-key 统计
        self._stats: Dict[str, KeyStats] = {
            key: KeyStats(key=key) for key in keys
        }

        # 失败的 Key 集合（临时降级）
        self._failed_keys: set = set()
        self._failed_keys_lock = asyncio.Lock()

        logger.info(f"[KeyRouter] 初始化完成，共 {len(keys)} 个 Key，每个 Key 最大并发 {max_concurrent_per_key}")

    def _get_available_keys(self) -> List[str]:
        """获取可用 Key 列表（排除失败的）"""
        return [k for k in self.keys if k not in self._failed_keys]

    async def _get_next_key(self) -> str:
        """获取下一个可用的 Key（轮询策略）"""
        async with self._index_lock:
            available_keys = self._get_available_keys()
            if not available_keys:
                # 所有 Key 都失败了，重置并使用所有 Key
                logger.warning("[KeyRouter] 所有 Key 都标记为失败，重置并使用所有 Key")
                self._failed_keys.clear()
                available_keys = self.keys

            # 轮询
            key = available_keys[self._round_robin_index % len(available_keys)]
            self._round_robin_index += 1
            return key

    async def mark_key_failed(self, key: str):
        """标记某个 Key 失败（临时降级）"""
        async with self._failed_keys_lock:
            if key not in self._failed_keys:
                self._failed_keys.add(key)
                logger.warning(f"[KeyRouter] Key {key[:8]}... 标记为失败，剩余可用 Key: {len(self._get_available_keys())}")

    async def mark_key_success(self, key: str, latency: float):
        """标记某个 Key 成功（恢复统计）"""
        async with self._failed_keys_lock:
            if key in self._failed_keys:
                self._failed_keys.discard(key)
                logger.info(f"[KeyRouter] Key {key[:8]}... 恢复成功")

    async def execute(
        self,
        coro_func: Callable[[str], Any],
        *args,
        **kwargs
    ) -> Any:
        """
        使用轮询策略执行协程

        Args:
            coro_func: 协程函数，签名为 async def func(key: str, *args, **kwargs)
            *args, **kwargs: 传递给 coro_func 的其他参数

        Returns:
            coro_func 的返回值
        """
        key = await self._get_next_key()
        start_time = time.time()

        async with self._semaphores[key]:
            try:
                result = await coro_func(key, *args, **kwargs)

                # 统计
                if self.enable_stats:
                    latency = time.time() - start_time
                    self._stats[key].request_count += 1
                    self._stats[key].total_latency += latency

                await self.mark_key_success(key, latency)
                return result

            except Exception as e:
                # 统计错误
                if self.enable_stats:
                    self._stats[key].error_count += 1

                await self.mark_key_failed(key)
                raise

    def get_stats(self) -> Dict[str, KeyStats]:
        """获取所有 Key 的统计信息"""
        return self._stats.copy()

    def log_stats(self):
        """打印统计信息"""
        logger.info("[KeyRouter] === Key 使用统计 ===")
        for key, stats in self._stats.items():
            logger.info(
                f"  Key {key[:8]}...: "
                f"请求={stats.request_count}, "
                f"错误={stats.error_count}, "
                f"平均延迟={stats.avg_latency:.2f}s"
            )


class KeyRouterPool:
    """KeyRouter 池，用于管理多个 KeyRouter 实例"""

    def __init__(self):
        self._routers: Dict[str, KeyRouter] = {}
        self._lock = asyncio.Lock()

    async def get_router(
        self,
        name: str,
        keys: List[str],
        max_concurrent_per_key: int = 3
    ) -> KeyRouter:
        """获取或创建 KeyRouter"""
        async with self._lock:
            if name not in self._routers:
                self._routers[name] = KeyRouter(
                    keys=keys,
                    max_concurrent_per_key=max_concurrent_per_key
                )
            return self._routers[name]

    async def remove_router(self, name: str):
        """移除 KeyRouter"""
        async with self._lock:
            if name in self._routers:
                self._routers[name].log_stats()
                del self._routers[name]


# 全局单例
_global_router_pool: Optional[KeyRouterPool] = None


def get_global_router_pool() -> KeyRouterPool:
    """获取全局 KeyRouter 池"""
    global _global_router_pool
    if _global_router_pool is None:
        _global_router_pool = KeyRouterPool()
    return _global_router_pool
