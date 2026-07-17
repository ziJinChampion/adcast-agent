"""
长期记忆工厂 — 根据配置自动创建对应的向量记忆实现。

支持的后端:
- ``placeholder``: 内存字典（开发测试用）
- ``chroma``: ChromaDB（本地向量数据库，零配置）
- ``milvus``: Milvus（生产级分布式向量数据库）
"""

import logging
import os
import re
from typing import Any, Dict

from .long_term_memory import BaseLongTermMemory, set_long_term_memory
from .vector_memory import ChromaMemory, EmbeddingClient, MilvusMemory

logger = logging.getLogger(__name__)


def _resolve_env_vars(value: str) -> str:
    """解析 ${VAR} 或 $VAR 形式的环境变量。"""
    if not isinstance(value, str):
        return value  # type: ignore[return-value]
    pattern = re.compile(r"\$\{(\w+)\}|\$(\w+)")
    def replacer(m: "re.Match[str]") -> str:
        return os.environ.get(m.group(1) or m.group(2), m.group(0))
    return pattern.sub(replacer, value)


def _resolve_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """递归解析配置中的环境变量。"""
    result: Dict[str, Any] = {}
    for k, v in config.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_config(v)
        else:
            result[k] = v
    return result


def create_memory(config: Dict[str, Any]) -> BaseLongTermMemory:
    """根据配置创建长期记忆实例。

    Args:
        config: ``long_term_memory`` 配置字典。

    Returns:
        对应后端的长时记忆实例。
    """
    config = _resolve_config(config)
    backend = config.get("backend", "placeholder").lower().strip()

    if backend == "placeholder":
        logger.info("Using PlaceholderLongTermMemory")
        from .long_term_memory import PlaceholderLongTermMemory
        return PlaceholderLongTermMemory()

    # 创建 EmbeddingClient
    embedding_config = config.get("embedding", {})
    api_key = embedding_config.get("api_key", "")
    if not api_key:
        api_key = config.get("_llm_config", {}).get("api_key", "")
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")

    embedding = EmbeddingClient(
        api_key=api_key,
        model=embedding_config.get("model", "text-embedding-3-small"),
    )
    logger.info("EmbeddingClient: model=%s, dim=%d", embedding._model, embedding.dimensions)

    if backend == "chroma":
        chroma_cfg = config.get("chroma", {})
        return ChromaMemory(
            embedding=embedding,
            persist_dir=chroma_cfg.get("persist_dir", "./data/chroma"),
            collection_name=chroma_cfg.get("collection_name", "adcast_memory"),
        )

    if backend == "milvus":
        milvus_cfg = config.get("milvus", {})
        return MilvusMemory(
            embedding=embedding,
            host=milvus_cfg.get("host", "localhost"),
            port=milvus_cfg.get("port", 19530),
            user=milvus_cfg.get("user", ""),
            password=milvus_cfg.get("password", ""),
            collection_name=milvus_cfg.get("collection_name", "adcast_memory"),
        )

    raise ValueError(f"Unknown memory backend: {backend!r}")


def init_memory(config: Dict[str, Any]) -> BaseLongTermMemory:
    """初始化并注入全局长期记忆实例。"""
    memory = create_memory(config)
    set_long_term_memory(memory)
    logger.info("Memory initialized: %s", type(memory).__name__)
    return memory


__all__ = ["create_memory", "init_memory"]
