"""
向量长期记忆模块 — AdCast Agent

提供基于 Embedding + 向量数据库的长期记忆能力：
- 跨 Campaign 经验复用
- 平台历史画像
- 用户偏好学习
- LLM RAG 增强

架构:
    文本内容 → Embedding (1536维) → 存入向量数据库
    结构化元数据 → 附带存储，支持 where 过滤
    查询时: query → Embedding → vector_search → 返回 top-k 结果

支持的向量数据库后端:
- ChromaDB: 本地运行，零配置，适合开发和小规模生产
- Milvus: 分布式、高性能，适合大规模生产（预留框架）
"""

import json
import logging
import uuid
from abc import abstractmethod
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .long_term_memory import BaseLongTermMemory

logger = logging.getLogger(__name__)


# ============================================================================
# Embedding 客户端
# ============================================================================


class EmbeddingClient:
    """OpenAI Embedding 异步客户端。

    负责将文本转换为高维向量嵌入，用于语义搜索。
    失败时自动降级返回零向量，不打断主流程。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._client: Any = None  # 懒加载

    def _get_client(self) -> Any:
        """懒加载 OpenAI 异步客户端。"""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                logger.error("openai package not installed. Install: pip install openai")
                raise
        return self._client

    async def embed(
        self, texts: Union[str, List[str]]
    ) -> Union[List[float], List[List[float]]]:
        """将文本转换为向量嵌入。单条返回 List[float]，列表返回 List[List[float]]。"""
        is_single = isinstance(texts, str)
        text_list: List[str] = [texts] if is_single else texts  # type: ignore[list-item]

        # 防御：过滤空字符串
        sanitized: List[str] = [t if t.strip() else "<empty>" for t in text_list]

        try:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self._model,
                input=sanitized,
                dimensions=self._dimensions,
            )
            vectors = [item.embedding for item in response.data]
            logger.debug(
                "Embedding generated: %d texts, model=%s, dim=%d",
                len(vectors), self._model, self._dimensions,
            )
            return vectors[0] if is_single else vectors

        except Exception as exc:
            logger.warning("Embedding failed (returning zero vectors): %s", exc)
            zero_vector: List[float] = [0.0] * self._dimensions
            return zero_vector if is_single else [zero_vector for _ in text_list]

    @property
    def dimensions(self) -> int:
        return self._dimensions


# ============================================================================
# 文档序列化工具
# ============================================================================


def _serialize_data_to_text(data: Dict[str, Any]) -> str:
    """将结构化数据字典序列化为可读文本，用于 Embedding。"""
    lines: List[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            nested = _serialize_data_to_text(value)
            lines.append(f"{key}:")
            for nl in nested.split("\n"):
                lines.append(f"  {nl}")
        elif isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _build_campaign_experience_text(campaign_result: Dict[str, Any]) -> str:
    """将 Campaign 结果构建为用于 Embedding 的文本摘要。"""
    lines: List[str] = []
    name = campaign_result.get("campaign_name") or campaign_result.get("name", "Unknown")
    lines.append(f"Campaign: {name}")

    for field in ["platform", "objective", "industry"]:
        val = campaign_result.get(field, "")
        if val:
            lines.append(f"{field.title()}: {val}")

    metrics: List[str] = []
    for metric, label in [("roas", "ROAS"), ("cpa", "CPA"), ("spend", "Spend"),
                          ("cpc", "CPC"), ("ctr", "CTR"), ("conversions", "Conversions")]:
        val = campaign_result.get(metric)
        if val is not None:
            metrics.append(f"{label} {val}")
    if metrics:
        lines.append(f"Result: {', '.join(metrics)}")

    notes = campaign_result.get("notes") or campaign_result.get("insights", "")
    if notes:
        lines.append(f"Notes: {notes}")

    return "\n".join(lines)


def _build_campaign_request_text(campaign_request: Dict[str, Any]) -> str:
    """将 Campaign 请求构建为查询文本，用于相似 Campaign 搜索。"""
    parts: List[str] = ["Looking for similar campaign experiences:"]
    for field in ["platform", "objective", "industry", "budget", "target_audience", "product_type"]:
        val = campaign_request.get(field)
        if val:
            parts.append(f"{field.replace('_', ' ').title()}: {val}")
    return "\n".join(parts)


# ============================================================================
# 向量长期记忆 — 抽象基类
# ============================================================================


class VectorLongTermMemory(BaseLongTermMemory):
    """向量长期记忆基类。

    子类只需实现: _upsert, _query, _get_by_key, _delete, _list_keys
    """

    _CONTEXT_TYPE_MAP: Dict[str, Optional[str]] = {
        "all": None,
        "campaign_experience": "campaign_experience",
        "campaign_history": "campaign_experience",
        "platform_experience": "platform_experience",
        "user_preference": "user_preference",
    }

    def __init__(self, embedding: EmbeddingClient, cache_size: int = 100) -> None:
        self.embedding = embedding
        self._cache_size = cache_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    # --- LRU 缓存 ---

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_set(self, key: str, value: Dict[str, Any]) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _cache_delete(self, key: str) -> None:
        self._cache.pop(key, None)

    # --- metadata 工具 ---

    @staticmethod
    def _build_metadata(
        data: Dict[str, Any],
        tags: Optional[List[str]] = None,
        memory_type: str = "general",
    ) -> Dict[str, Any]:
        """构建 ChromaDB 兼容的标量 metadata。"""
        ts = datetime.now(timezone.utc).isoformat()
        meta: Dict[str, Any] = {"memory_type": memory_type, "timestamp": ts}
        for field in ["platform", "objective", "industry", "campaign_id", "campaign_name"]:
            if field in data:
                meta[field] = str(data[field])
        meta["tags"] = ", ".join(tags or [])
        meta["_json_data"] = json.dumps(data, ensure_ascii=False, default=str)
        return meta

    @staticmethod
    def _metadata_to_where_filter(
        tags: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """构建向量数据库 where 过滤条件。"""
        clauses: List[Dict[str, Any]] = []
        if memory_type:
            clauses.append({"memory_type": {"$eq": memory_type}})
        if tags:
            if len(tags) == 1:
                clauses.append({"tags": {"$contains": tags[0]}})
            else:
                clauses.append({"$or": [{"tags": {"$contains": t}} for t in tags]})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    # --- 子类必须实现 ---

    @abstractmethod
    async def _upsert(self, key: str, document: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        ...

    @abstractmethod
    async def _query(self, embedding: List[float], where: Optional[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def _get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    async def _delete(self, key: str) -> bool:
        ...

    @abstractmethod
    async def _list_keys(self, prefix: str, limit: int) -> List[str]:
        ...

    # --- 公共接口 ---

    async def save(self, key: str, data: Dict[str, Any], tags: Optional[List[str]] = None) -> bool:
        try:
            document = _serialize_data_to_text(data)
            vector = await self.embedding.embed(document)

            memory_type = "general"
            if any(k in key.lower() for k in ["campaign", "roas", "cpa"]):
                memory_type = "campaign_experience"
            elif "platform" in key.lower():
                memory_type = "platform_experience"
            elif "user" in key.lower() or "preference" in key.lower():
                memory_type = "user_preference"

            metadata = self._build_metadata(data, tags, memory_type)
            success = await self._upsert(key, document, vector, metadata)
            if success:
                self._cache_set(key, {"data": data, "metadata": metadata})
            return success
        except Exception as exc:
            logger.error("Failed to save memory (key=%s): %s", key, exc)
            return False

    async def recall(self, key: str) -> Optional[Dict[str, Any]]:
        cached = self._cache_get(key)
        if cached is not None:
            return cached.get("data")
        try:
            result = await self._get_by_key(key)
            if result is None:
                return None
            metadata = result.get("metadata", {})
            try:
                data: Dict[str, Any] = json.loads(metadata.get("_json_data", "{}"))
            except json.JSONDecodeError:
                data = {"_raw": result.get("document", "")}
            self._cache_set(key, {"data": data, "metadata": metadata})
            return data
        except Exception as exc:
            logger.error("Failed to recall (key=%s): %s", key, exc)
            return None

    async def search(self, query: str, tags: Optional[List[str]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            query_vector = await self.embedding.embed(query)
            where = self._metadata_to_where_filter(tags=tags)
            results = await self._query(query_vector, where, limit)
            parsed: List[Dict[str, Any]] = []
            for item in results:
                metadata = item.get("metadata", {})
                try:
                    data: Dict[str, Any] = json.loads(metadata.get("_json_data", "{}"))
                except json.JSONDecodeError:
                    data = {"_raw": item.get("document", "")}
                parsed.append({
                    "key": item.get("key", ""),
                    "score": item.get("score", 0.0),
                    "data": data,
                    "metadata": {k: v for k, v in metadata.items() if not k.startswith("_")},
                })
            return parsed
        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return []

    async def list_keys(self, prefix: str = "", limit: int = 100) -> List[str]:
        try:
            return await self._list_keys(prefix, limit)
        except Exception as exc:
            logger.error("list_keys failed: %s", exc)
            return []

    async def forget(self, key: str) -> bool:
        try:
            success = await self._delete(key)
            if success:
                self._cache_delete(key)
            return success
        except Exception as exc:
            logger.error("Failed to forget (key=%s): %s", key, exc)
            return False

    # --- RAG 查询 ---

    async def rag_query(self, query: str, context_type: str = "all", limit: int = 5) -> str:
        """RAG 查询 — 返回格式化的上下文文本，可直接拼接到 LLM prompt。"""
        try:
            memory_type = self._CONTEXT_TYPE_MAP.get(context_type)
            query_vector = await self.embedding.embed(query)
            where = self._metadata_to_where_filter(memory_type=memory_type)
            results = await self._query(query_vector, where, limit)
            if not results:
                return ""

            sections: List[str] = []
            for idx, item in enumerate(results, 1):
                metadata = item.get("metadata", {})
                document = item.get("document", "")
                score = item.get("score", 0.0)

                header_parts: List[str] = []
                for f in ["platform", "industry", "objective"]:
                    v = metadata.get(f, "")
                    if v:
                        header_parts.append(f"{f}: {v}")

                lines = [f"[历史经验 {idx}]"]
                if header_parts:
                    lines.append(", ".join(header_parts))
                if document:
                    lines.append(document)
                lines.append(f"(similarity: {score:.3f})")
                sections.append("\n".join(lines))

            return "\n\n".join(sections)
        except Exception as exc:
            logger.error("RAG query failed: %s", exc)
            return ""

    # --- Campaign 专用 ---

    async def save_campaign_experience(self, campaign_result: Dict[str, Any]) -> bool:
        """保存 Campaign 执行经验（reflect 节点调用）。"""
        try:
            cid = campaign_result.get("campaign_id") or campaign_result.get("id", str(uuid.uuid4())[:8])
            cname = campaign_result.get("campaign_name") or campaign_result.get("name", "unknown")
            key = f"campaign_exp_{cid}_{cname}"
            document = _build_campaign_experience_text(campaign_result)
            vector = await self.embedding.embed(document)

            platform = campaign_result.get("platform", "")
            tags: List[str] = ["campaign", "experience"]
            if platform:
                tags.append(platform.lower().replace(" ", "_"))
            industry = campaign_result.get("industry", "")
            if industry:
                tags.append(industry.lower())

            metadata = self._build_metadata(campaign_result, tags, "campaign_experience")
            success = await self._upsert(key, document, vector, metadata)
            if success:
                self._cache_set(key, {"data": campaign_result, "metadata": metadata})
                logger.info("Campaign experience saved: %s", key)
            return success
        except Exception as exc:
            logger.error("Failed to save campaign experience: %s", exc)
            return False

    async def find_similar_campaigns(self, campaign_request: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
        """查找相似 Campaign 历史（observe 节点调用）。"""
        try:
            query = _build_campaign_request_text(campaign_request)
            where = self._metadata_to_where_filter(memory_type="campaign_experience")
            query_vector = await self.embedding.embed(query)
            results = await self._query(query_vector, where, limit)
            parsed: List[Dict[str, Any]] = []
            for item in results:
                metadata = item.get("metadata", {})
                try:
                    data: Dict[str, Any] = json.loads(metadata.get("_json_data", "{}"))
                except json.JSONDecodeError:
                    data = {"_raw": item.get("document", "")}
                parsed.append({
                    "key": item.get("key", ""),
                    "score": item.get("score", 0.0),
                    "data": data,
                    "metadata": {k: v for k, v in metadata.items() if not k.startswith("_")},
                })
            return parsed
        except Exception as exc:
            logger.error("find_similar_campaigns failed: %s", exc)
            return []


# ============================================================================
# ChromaDB 实现
# ============================================================================


class ChromaMemory(VectorLongTermMemory):
    """ChromaDB 向量记忆实现。本地运行，零配置，适合开发和小规模生产。"""

    def __init__(
        self,
        embedding: EmbeddingClient,
        persist_dir: str = "./data/chroma",
        collection_name: str = "adcast_memory",
    ) -> None:
        super().__init__(embedding)
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None
        self._init_collection()

    def _init_collection(self) -> None:
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialized: %s/%s", self._persist_dir, self._collection_name)
        except ImportError:
            logger.error("chromadb not installed. pip install chromadb")
            raise

    async def _upsert(self, key: str, document: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        try:
            # Chroma 只接受标量 metadata
            safe_meta: Dict[str, Any] = {}
            for k, v in metadata.items():
                safe_meta[k] = v if isinstance(v, (str, int, float, bool)) else json.dumps(v, ensure_ascii=False, default=str)
            self._collection.upsert(
                ids=[key], documents=[document], embeddings=[embedding], metadatas=[safe_meta]
            )
            return True
        except Exception as exc:
            logger.error("ChromaDB upsert failed: %s", exc)
            return False

    async def _query(self, embedding: List[float], where: Optional[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        try:
            kwargs: Dict[str, Any] = {
                "query_embeddings": [embedding],
                "n_results": limit,
                "include": ["metadatas", "documents", "distances"],
            }
            if where:
                kwargs["where"] = where
            raw = self._collection.query(**kwargs)
            results: List[Dict[str, Any]] = []
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            metas = raw.get("metadatas", [[]])[0]
            distances = raw.get("distances", [[]])[0]
            for i, doc_id in enumerate(ids):
                dist = distances[i] if i < len(distances) else 0.0
                results.append({
                    "key": doc_id,
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": float(1.0 - dist),  # 距离转相似度
                })
            return results
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []

    async def _get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            raw = self._collection.get(ids=[key], include=["metadatas", "documents"])
            ids = raw.get("ids", [])
            if not ids:
                return None
            return {
                "key": ids[0],
                "document": raw.get("documents", [""])[0],
                "metadata": raw.get("metadatas", [{}])[0],
            }
        except Exception as exc:
            logger.error("ChromaDB get failed: %s", exc)
            return None

    async def _delete(self, key: str) -> bool:
        try:
            self._collection.delete(ids=[key])
            return True
        except Exception as exc:
            logger.error("ChromaDB delete failed: %s", exc)
            return False

    async def _list_keys(self, prefix: str, limit: int) -> List[str]:
        try:
            raw = self._collection.peek(limit=limit * 2)
            all_ids: List[str] = raw.get("ids", [])
            if prefix:
                return [k for k in all_ids if k.startswith(prefix)][:limit]
            return all_ids[:limit]
        except Exception as exc:
            logger.error("ChromaDB list_keys failed: %s", exc)
            return []


# ============================================================================
# Milvus 实现（生产级）
# ============================================================================


class MilvusMemory(VectorLongTermMemory):
    """Milvus 向量记忆实现。分布式、高性能，支持大规模数据。"""

    def __init__(
        self,
        embedding: EmbeddingClient,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "adcast_memory",
        user: str = "",
        password: str = "",
    ) -> None:
        super().__init__(embedding)
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._user = user
        self._password = password
        self._client: Any = None
        self._connection_alias = ""
        self._init_collection()

    def _init_collection(self) -> None:
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections

            alias = f"adcast_milvus_{id(self)}"
            connections.connect(
                alias=alias, host=self._host, port=self._port,
                user=self._user or "", password=self._password or "",
            )
            self._connection_alias = alias

            dim = self.embedding.dimensions
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="document", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="memory_type", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="platform", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="objective", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="industry", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="_json_data", dtype=DataType.VARCHAR, max_length=8192),
            ]
            schema = CollectionSchema(fields=fields, description="AdCast Long-Term Memory")

            if Collection.has_collection(name=self._collection_name, using=alias):
                self._client = Collection(name=self._collection_name, using=alias)
                logger.info("Milvus collection loaded: %s", self._collection_name)
            else:
                self._client = Collection(name=self._collection_name, schema=schema, using=alias)
                logger.info("Milvus collection created: %s", self._collection_name)

            if not self._client.has_index():
                self._client.create_index(
                    field_name="embedding",
                    index_params={"metric_type": "COSINE", "index_type": "HNSW",
                                  "params": {"M": 16, "efConstruction": 200}},
                )
                self._client.load()
                logger.info("Milvus HNSW index created")
            else:
                self._client.load()

        except ImportError:
            logger.error("pymilvus not installed. pip install pymilvus")
            raise

    async def _upsert(self, key: str, document: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        try:
            entities = [
                [key], [embedding], [document],
                [metadata.get("memory_type", "")],
                [metadata.get("platform", "")],
                [metadata.get("objective", "")],
                [metadata.get("industry", "")],
                [metadata.get("timestamp", "")],
                [metadata.get("tags", "")],
                [metadata.get("_json_data", "")],
            ]
            self._client.insert(entities)
            self._client.flush()
            return True
        except Exception as exc:
            logger.error("Milvus upsert failed: %s", exc)
            return False

    async def _query(self, embedding: List[float], where: Optional[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        try:
            expr = self._where_to_milvus_expr(where) if where else ""
            results = self._client.search(
                data=[embedding], anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=limit, expr=expr if expr else None,
                output_fields=["id", "document", "memory_type", "platform", "objective",
                               "industry", "timestamp", "tags", "_json_data"],
            )
            parsed: List[Dict[str, Any]] = []
            for hits in results:
                for hit in hits:
                    ent = hit.entity
                    parsed.append({
                        "key": ent.get("id"),
                        "document": ent.get("document", ""),
                        "metadata": {
                            "memory_type": ent.get("memory_type", ""),
                            "platform": ent.get("platform", ""),
                            "objective": ent.get("objective", ""),
                            "industry": ent.get("industry", ""),
                            "timestamp": ent.get("timestamp", ""),
                            "tags": ent.get("tags", ""),
                            "_json_data": ent.get("_json_data", "{}"),
                        },
                        "score": float(hit.distance),
                    })
            return parsed
        except Exception as exc:
            logger.error("Milvus query failed: %s", exc)
            return []

    async def _get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            results = self._client.query(
                expr=f'id == "{key}"',
                output_fields=["id", "document", "memory_type", "platform", "objective",
                               "industry", "timestamp", "tags", "_json_data"],
            )
            if not results:
                return None
            item = results[0]
            return {
                "key": item.get("id", key),
                "document": item.get("document", ""),
                "metadata": {k: item.get(k, "") for k in
                             ["memory_type", "platform", "objective", "industry", "timestamp", "tags", "_json_data"]},
            }
        except Exception as exc:
            logger.error("Milvus get_by_key failed: %s", exc)
            return None

    async def _delete(self, key: str) -> bool:
        try:
            self._client.delete(expr=f'id == "{key}"')
            self._client.flush()
            return True
        except Exception as exc:
            logger.error("Milvus delete failed: %s", exc)
            return False

    async def _list_keys(self, prefix: str, limit: int) -> List[str]:
        try:
            expr = f'id like "{prefix}%"' if prefix else ""
            results = self._client.query(
                expr=expr if expr else None,
                output_fields=["id"], limit=limit,
            )
            return [r["id"] for r in results if "id" in r]
        except Exception as exc:
            logger.error("Milvus list_keys failed: %s", exc)
            return []

    @staticmethod
    def _where_to_milvus_expr(where: Dict[str, Any]) -> str:
        """将 Chroma 风格 where 转为 Milvus expr。"""
        parts: List[str] = []
        for key, cond in where.items():
            if key == "$and":
                sub = [MilvusMemory._where_to_milvus_expr(c) for c in cond]
                parts.append(f"({' and '.join(sub)})")
            elif key == "$or":
                sub = [MilvusMemory._where_to_milvus_expr(c) for c in cond]
                parts.append(f"({' or '.join(sub)})")
            elif isinstance(cond, dict):
                op = list(cond.keys())[0]
                val = cond[op]
                mapping = {"$eq": "==", "$ne": "!=", "$gt": ">", "$gte": ">=",
                           "$lt": "<", "$lte": "<=", "$contains": "like"}
                milvus_op = mapping.get(op, "==")
                if milvus_op == "like":
                    parts.append(f'{key} like "%{val}%"')
                else:
                    parts.append(f'{key} {milvus_op} "{val}"')
            else:
                parts.append(f'{key} == "{cond}"')
        return " and ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


__all__ = [
    "EmbeddingClient",
    "VectorLongTermMemory",
    "ChromaMemory",
    "MilvusMemory",
]
