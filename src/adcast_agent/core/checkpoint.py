"""
Checkpoint 管理模块 - 支持 in-memory 和 PostgreSQL 双后端

用于 LangGraph 的 StateGraph 持久化，支持：
1. In-Memory: 快速开发/测试，重启后丢失
2. PostgreSQL: 生产环境持久化，支持分布式

配置方式（settings.yaml）：
    checkpoint:
      backend: "memory"  # 或 "postgres"
      postgres:
        host: "localhost"
        port: 5432
        database: "adcast"
        user: "adcast"
        password: "***"
        table_name: "checkpoints"
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("adcast.checkpoint")


class BaseCheckpoint(ABC):
    """Checkpoint 抽象基类"""

    @abstractmethod
    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取指定线程的checkpoint"""
        pass

    @abstractmethod
    def put(self, thread_id: str, state: Dict[str, Any]) -> bool:
        """保存checkpoint"""
        pass

    @abstractmethod
    def list_threads(self, limit: int = 100) -> List[str]:
        """列出所有线程ID"""
        pass

    @abstractmethod
    def delete(self, thread_id: str) -> bool:
        """删除checkpoint"""
        pass


class MemoryCheckpoint(BaseCheckpoint):
    """
    In-Memory Checkpoint
    
    适用于开发和测试环境。数据存储在内存中，进程重启后丢失。
    零依赖，开箱即用。
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        logger.info("MemoryCheckpoint initialized")

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        checkpoint = self._store.get(thread_id)
        if checkpoint:
            logger.debug(f"MemoryCheckpoint GET {thread_id}: found")
            return checkpoint.get("state")
        logger.debug(f"MemoryCheckpoint GET {thread_id}: not found")
        return None

    def put(self, thread_id: str, state: Dict[str, Any]) -> bool:
        self._store[thread_id] = {
            "thread_id": thread_id,
            "state": state,
            "updated_at": datetime.utcnow().isoformat(),
        }
        logger.debug(f"MemoryCheckpoint PUT {thread_id}: saved")
        return True

    def list_threads(self, limit: int = 100) -> List[str]:
        return list(self._store.keys())[:limit]

    def delete(self, thread_id: str) -> bool:
        if thread_id in self._store:
            del self._store[thread_id]
            logger.debug(f"MemoryCheckpoint DELETE {thread_id}")
            return True
        return False

    def clear(self):
        """清空所有数据（仅用于测试）"""
        self._store.clear()
        logger.info("MemoryCheckpoint cleared")

    @property
    def count(self) -> int:
        return len(self._store)


class PostgresCheckpoint(BaseCheckpoint):
    """
    PostgreSQL Checkpoint
    
    适用于生产环境。数据持久化到PostgreSQL，支持：
    - 进程重启后状态恢复
    - 多进程共享状态
    - 分布式部署
    
    依赖: pip install psycopg2-binary 或 psycopg
    
    建表SQL:
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id VARCHAR(255) PRIMARY KEY,
            state JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_updated 
        ON checkpoints(updated_at DESC);
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "adcast",
        user: str = "adcast",
        password: str = "",
        table_name: str = "checkpoints",
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.table_name = table_name
        self._pool = None
        self._initialized = False

    async def initialize(self):
        """初始化数据库连接池和表结构"""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=2,
                max_size=10,
            )

            # 创建表
            async with self._pool.acquire() as conn:
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        thread_id VARCHAR(255) PRIMARY KEY,
                        state JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_updated 
                    ON {self.table_name}(updated_at DESC)
                """)

            self._initialized = True
            logger.info(f"PostgresCheckpoint initialized: {self.host}:{self.port}/{self.database}")

        except ImportError:
            logger.error("asyncpg is required for PostgreSQL checkpoint. Install: pip install asyncpg")
            raise
        except Exception as e:
            logger.error(f"PostgresCheckpoint init failed: {e}")
            raise

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """同步获取（fallback，建议使用async_get）"""
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(self.async_get(thread_id))
        except Exception as e:
            logger.error(f"PostgresCheckpoint sync GET failed: {e}")
            return None

    async def async_get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """异步获取checkpoint"""
        if not self._initialized:
            await self.initialize()

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT state FROM {self.table_name} WHERE thread_id = $1",
                thread_id,
            )
            if row:
                logger.debug(f"PostgresCheckpoint GET {thread_id}: found")
                return json.loads(row["state"])
            logger.debug(f"PostgresCheckpoint GET {thread_id}: not found")
            return None

    def put(self, thread_id: str, state: Dict[str, Any]) -> bool:
        """同步保存（fallback，建议使用async_put）"""
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(self.async_put(thread_id, state))
        except Exception as e:
            logger.error(f"PostgresCheckpoint sync PUT failed: {e}")
            return False

    async def async_put(self, thread_id: str, state: Dict[str, Any]) -> bool:
        """异步保存checkpoint"""
        if not self._initialized:
            await self.initialize()

        state_json = json.dumps(state, ensure_ascii=False, default=str)

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self.table_name} (thread_id, state, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (thread_id)
                DO UPDATE SET state = $2, updated_at = CURRENT_TIMESTAMP
                """,
                thread_id,
                state_json,
            )
            logger.debug(f"PostgresCheckpoint PUT {thread_id}: saved")
            return True

    def list_threads(self, limit: int = 100) -> List[str]:
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(self.async_list_threads(limit))
        except Exception:
            return []

    async def async_list_threads(self, limit: int = 100) -> List[str]:
        if not self._initialized:
            await self.initialize()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT thread_id FROM {self.table_name} ORDER BY updated_at DESC LIMIT $1",
                limit,
            )
            return [row["thread_id"] for row in rows]

    def delete(self, thread_id: str) -> bool:
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(self.async_delete(thread_id))
        except Exception:
            return False

    async def async_delete(self, thread_id: str) -> bool:
        if not self._initialized:
            await self.initialize()

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table_name} WHERE thread_id = $1",
                thread_id,
            )
            return "DELETE 1" in result

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            logger.info("PostgresCheckpoint pool closed")


class CheckpointManager:
    """
    Checkpoint 管理器
    
    统一入口，根据配置自动选择后端。
    兼容 LangGraph 的 BaseCheckpointSaver 接口。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.backend = self.config.get("backend", "memory").lower()
        self._checkpoint: Optional[BaseCheckpoint] = None
        self._init_checkpoint()

    def _init_checkpoint(self):
        """根据配置初始化checkpoint后端"""
        if self.backend == "postgres":
            pg_config = self.config.get("postgres", {})
            self._checkpoint = PostgresCheckpoint(
                host=pg_config.get("host", "localhost"),
                port=pg_config.get("port", 5432),
                database=pg_config.get("database", "adcast"),
                user=pg_config.get("user", "adcast"),
                password=pg_config.get("password", ""),
                table_name=pg_config.get("table_name", "checkpoints"),
            )
        else:
            self._checkpoint = MemoryCheckpoint()

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._checkpoint.get(thread_id)

    def put(self, thread_id: str, state: Dict[str, Any]) -> bool:
        return self._checkpoint.put(thread_id, state)

    def list_threads(self, limit: int = 100) -> List[str]:
        return self._checkpoint.list_threads(limit)

    def delete(self, thread_id: str) -> bool:
        return self._checkpoint.delete(thread_id)

    @property
    def checkpoint(self) -> BaseCheckpoint:
        return self._checkpoint

    # === LangGraph 兼容接口 ===

    def get_tuple(self, config: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], str]]:
        """
        LangGraph 兼容: 获取 (checkpoint, thread_id) 元组
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        state = self.get(thread_id)
        if state is not None:
            return (state, thread_id)
        return None

    def put_tuple(self, config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 兼容: 保存 checkpoint
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self.put(thread_id, state)
        return config

    def list(self, config: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """
        LangGraph 兼容: 列出所有线程
        """
        threads = self.list_threads(limit)
        return [{"configurable": {"thread_id": t}} for t in threads]
