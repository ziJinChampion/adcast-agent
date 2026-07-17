"""
长期记忆模块 - 接口预留（占位实现）

设计目标：
- 存储Agent的长期知识（平台特性、历史表现、用户偏好）
- 跨Campaign经验复用
- 支持向量检索（类似RAG）

预留接口，暂不做完整实现。未来可接入：
- Vector DB (Pinecone, Milvus, Chroma)
- Graph DB (Neo4j) 
- 传统数据库 + embedding

当前提供基础KV存储能力。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("adcast.memory")


class BaseLongTermMemory(ABC):
    """长期记忆抽象基类"""

    @abstractmethod
    async def save(self, key: str, data: Dict[str, Any], tags: Optional[List[str]] = None) -> bool:
        """保存记忆"""
        pass

    @abstractmethod
    async def recall(self, key: str) -> Optional[Dict[str, Any]]:
        """精确回忆"""
        pass

    @abstractmethod
    async def search(self, query: str, tags: Optional[List[str]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """语义搜索（需向量DB支持）"""
        pass

    @abstractmethod
    async def list_keys(self, prefix: str = "", limit: int = 100) -> List[str]:
        """列出记忆键"""
        pass

    @abstractmethod
    async def forget(self, key: str) -> bool:
        """删除记忆"""
        pass


class PlaceholderLongTermMemory(BaseLongTermMemory):
    """
    占位实现 - 仅提供基础KV存储
    
    使用简单的内存字典，进程重启后丢失。
    未来替换为真正的向量数据库实现。
    
    TODO: 接入向量数据库实现语义搜索
    TODO: 添加embedding生成
    TODO: 支持时间衰减的记忆权重
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        logger.info("PlaceholderLongTermMemory initialized (placeholder mode)")

    async def save(self, key: str, data: Dict[str, Any], tags: Optional[List[str]] = None) -> bool:
        """保存记忆"""
        self._store[key] = {
            "data": data,
            "tags": tags or [],
            "created_at": datetime.utcnow().isoformat(),
            "access_count": 0,
        }
        logger.debug(f"Memory saved: {key} (tags: {tags})")
        return True

    async def recall(self, key: str) -> Optional[Dict[str, Any]]:
        """精确回忆"""
        entry = self._store.get(key)
        if entry:
            entry["access_count"] = entry.get("access_count", 0) + 1
            logger.debug(f"Memory recalled: {key} (access_count: {entry['access_count']})")
            return entry["data"]
        logger.debug(f"Memory miss: {key}")
        return None

    async def search(self, query: str, tags: Optional[List[str]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索 - 占位实现
        
        当前仅做关键词匹配。未来接入向量DB后实现真正的语义搜索。
        """
        results = []
        query_lower = query.lower()

        for key, entry in self._store.items():
            # 标签过滤
            if tags:
                if not any(t in entry.get("tags", []) for t in tags):
                    continue

            # 关键词匹配（临时方案）
            data_str = str(entry["data"]).lower()
            if query_lower in key.lower() or query_lower in data_str:
                results.append({
                    "key": key,
                    "data": entry["data"],
                    "score": 0.5,  # 临时分数
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"Memory search: '{query}' -> {len(results[:limit])} results (placeholder)")
        return results[:limit]

    async def list_keys(self, prefix: str = "", limit: int = 100) -> List[str]:
        """列出记忆键"""
        keys = [k for k in self._store.keys() if k.startswith(prefix)]
        return keys[:limit]

    async def forget(self, key: str) -> bool:
        """删除记忆"""
        if key in self._store:
            del self._store[key]
            logger.debug(f"Memory forgotten: {key}")
            return True
        return False

    # === 预定义的记忆类型 ===

    async def save_platform_experience(
        self,
        platform: str,
        objective: str,
        industry: str,
        roas: float,
        cpa: float,
        spend: float,
        notes: str = "",
    ) -> bool:
        """
        保存平台投放经验
        
        用于跨Campaign学习，未来决策时参考历史表现。
        """
        key = f"platform_exp:{platform}:{objective}:{industry}"
        return await self.save(key, {
            "platform": platform,
            "objective": objective,
            "industry": industry,
            "roas": roas,
            "cpa": cpa,
            "spend": spend,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        }, tags=["platform_experience", platform, objective, industry])

    async def get_platform_experience(
        self,
        platform: str,
        objective: str,
        industry: str,
    ) -> Optional[Dict[str, Any]]:
        """获取平台投放经验"""
        key = f"platform_exp:{platform}:{objective}:{industry}"
        return await self.recall(key)

    async def save_user_preference(self, key: str, value: Any) -> bool:
        """保存用户偏好"""
        return await self.save(f"user_pref:{key}", {
            "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }, tags=["user_preference"])

    async def get_user_preference(self, key: str) -> Optional[Any]:
        """获取用户偏好"""
        data = await self.recall(f"user_pref:{key}")
        return data.get("value") if data else None


# 全局记忆实例（单例）
_long_term_memory: Optional[BaseLongTermMemory] = None


def get_long_term_memory() -> BaseLongTermMemory:
    """获取长期记忆实例（单例）"""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = PlaceholderLongTermMemory()
    return _long_term_memory


def set_long_term_memory(memory: BaseLongTermMemory):
    """设置长期记忆实例（用于注入自定义实现）"""
    global _long_term_memory
    _long_term_memory = memory
    logger.info("Long-term memory implementation replaced")
