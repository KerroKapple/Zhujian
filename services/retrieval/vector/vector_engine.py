"""
========================================
向量检索器 (Milvus)
========================================

📚 模块说明：
- 基于Milvus的向量检索
- 语义相似度搜索
- 支持分层存储

🎯 核心功能：
1. 向量索引构建
2. 语义检索
3. 混合过滤
4. 批量检索

========================================
"""

from typing import List, Dict, Optional, Tuple
import numpy as np

from pymilvus import (
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)
from loguru import logger

from services.embedding.embedder import Embedder
from services.retrieval.vector.milvus_client import milvus_client


class VectorRetriever:
    """
    向量检索器（基于Milvus）

    🔧 技术特点：
    - Milvus向量数据库
    - HNSW索引（高性能）
    - 支持过滤条件

    💡 适用场景：
    - 语义相似检索
    - 模糊匹配
    - 跨语言检索
    """

    def __init__(
            self,
            collection_name: str,
            embedder: Embedder,
            host: str = 'localhost',
            port: str = '19530',
            dim: int = 1024
    ):
        """
        初始化向量检索器

        参数：
            collection_name: 集合名称（相当于表名）
            embedder: 向量化服务实例
            host: Milvus服务器地址
            port: Milvus端口
            dim: 向量维度
        """
        self.collection_name = collection_name
        self.embedder = embedder
        self.host = host
        self.port = port
        self.dim = dim

        # 集合句柄延迟初始化，不在 __init__ 主动建连
        self.collection = None
        # 标记集合是否已 load 到内存，避免每次 search 重复 load
        self._loaded = False

        logger.info(
            f"向量检索器初始化 | "
            f"集合: {collection_name} | "
            f"维度: {dim}"
        )

    def create_collection(
            self,
            drop_if_exists: bool = False
    ):
        """
        创建集合

        参数：
            drop_if_exists: 如果集合存在是否删除
        """
        milvus_client.ensure_connected()

        # 检查集合是否存在
        if utility.has_collection(self.collection_name):
            if drop_if_exists:
                logger.warning(f"删除已存在的集合: {self.collection_name}")
                utility.drop_collection(self.collection_name)
            else:
                logger.info(f"集合已存在: {self.collection_name}")
                self.collection = Collection(self.collection_name)
                return

        # 定义字段
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.INT64,
                is_primary=True,
                auto_id=True
            ),
            FieldSchema(
                name="doc_id",
                dtype=DataType.VARCHAR,
                max_length=200
            ),
            FieldSchema(
                name="text",
                dtype=DataType.VARCHAR,
                max_length=65535
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.dim
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON
            )
        ]

        # 创建Schema
        schema = CollectionSchema(
            fields=fields,
            description=f"Vector collection for {self.collection_name}"
        )

        # 创建集合
        self.collection = Collection(
            name=self.collection_name,
            schema=schema
        )

        logger.info(f"集合创建成功: {self.collection_name}")

    def create_index(
            self,
            index_type: str = "HNSW",
            metric_type: str = "IP",  # IP (内积) 或 L2 (欧氏距离)
            params: Optional[Dict] = None
    ):
        """
        创建向量索引

        参数：
            index_type: 索引类型
                - 'HNSW': 高性能（推荐）
                - 'IVF_FLAT': 精确检索
                - 'IVF_SQ8': 内存优化
            metric_type: 距离度量
                - 'IP': 内积（适合归一化向量）
                - 'L2': 欧氏距离
                - 'COSINE': 余弦相似度
            params: 索引参数
        """
        if not self.collection:
            raise RuntimeError("集合未创建，请先调用create_collection()")

        # 默认索引参数
        if params is None:
            if index_type == "HNSW":
                params = {
                    "M": 16,  # 每个节点的最大连接数
                    "efConstruction": 256  # 构建时的候选数
                }
            elif index_type == "IVF_FLAT":
                params = {
                    "nlist": 1024  # 聚类中心数
                }
            elif index_type == "IVF_SQ8":
                params = {
                    "nlist": 1024
                }

        # 创建索引
        index_params = {
            "index_type": index_type,
            "metric_type": metric_type,
            "params": params
        }

        logger.info(f"开始创建索引 | 类型: {index_type} | 度量: {metric_type}")

        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )

        logger.info("索引创建完成")

    def insert(
            self,
            documents: List[Dict],
            batch_size: int = 100
    ) -> int:
        """
        插入文档

        参数：
            documents: 文档列表
                [
                    {
                        'doc_id': 'doc1',
                        'text': '文档内容',
                        'embedding': np.ndarray,  # 可选，如没有会自动生成
                        'metadata': {...}
                    },
                    ...
                ]
            batch_size: 批处理大小

        返回：
            插入的文档数量
        """
        if not self.collection:
            raise RuntimeError("集合未创建")

        milvus_client.ensure_connected()

        logger.info(f"开始插入文档 | 数量: {len(documents)}")

        total_inserted = 0

        # 分批插入
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # 准备数据
            doc_ids = []
            texts = []
            embeddings = []
            metadatas = []

            for doc in batch:
                doc_ids.append(doc.get('doc_id', f"doc_{i}"))
                texts.append(doc.get('text', ''))

                # 如果没有embedding，自动生成；兼容 list/ndarray
                if 'embedding' in doc:
                    embeddings.append(np.asarray(doc['embedding']).tolist())
                else:
                    emb = self.embedder.embed_query(doc.get('text', ''))
                    embeddings.append(np.asarray(emb).tolist())

                metadatas.append(doc.get('metadata', {}))

            # 插入
            entities = [
                doc_ids,
                texts,
                embeddings,
                metadatas
            ]

            insert_result = self.collection.insert(entities)
            total_inserted += len(insert_result.primary_keys)

            logger.debug(f"批次 {i // batch_size + 1} 插入完成: {len(batch)} 条")

        # 刷新
        self.collection.flush()

        logger.info(f"文档插入完成 | 总计: {total_inserted} 条")

        return total_inserted

    def search(
            self,
            query: str,
            top_k: int = 10,
            filters: Optional[str] = None,
            search_params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        检索文档

        参数：
            query: 查询文本
            top_k: 返回前K个结果
            filters: 过滤表达式（Milvus语法）
                例如: "metadata['type'] == 'regulation'"
            search_params: 检索参数
                例如: {"ef": 64} for HNSW

        返回：
            检索结果列表
        """
        if not self.collection:
            raise RuntimeError("集合未创建")

        milvus_client.ensure_connected()

        logger.debug(f"向量检索 | 查询: {query[:50]}... | top_k: {top_k}")

        # 仅首次加载集合到内存
        if not self._loaded:
            self.collection.load()
            self._loaded = True

        # 查询向量化
        query_embedding = self.embedder.embed_query(query)

        # 默认检索参数
        if search_params is None:
            search_params = {"ef": 64}  # HNSW参数

        # 执行检索
        search_results = self.collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filters,
            output_fields=["doc_id", "text", "metadata"]
        )

        # 解析结果
        results = []
        for rank, hit in enumerate(search_results[0], 1):
            result = {
                'doc_id': hit.entity.get('doc_id'),
                'text': hit.entity.get('text'),
                'metadata': hit.entity.get('metadata'),
                'score': float(hit.score),  # 距离/相似度分数
                'rank': rank
            }
            results.append(result)

        logger.debug(f"向量检索完成 | 返回: {len(results)} 个结果")

        return results

    def delete(self, expr: str) -> int:
        """
        删除文档

        参数：
            expr: 删除条件表达式
                例如: "doc_id in ['doc1', 'doc2']"

        返回：
            删除的文档数量
        """
        if not self.collection:
            raise RuntimeError("集合未创建")

        milvus_client.ensure_connected()

        delete_result = self.collection.delete(expr)

        logger.info(f"删除文档: {delete_result.delete_count} 条")

        return delete_result.delete_count

    def get_stats(self) -> Dict:
        """获取集合统计信息"""
        if not self.collection:
            return {}

        stats = self.collection.num_entities

        return {
            'collection_name': self.collection_name,
            'total_docs': stats,
            'dimension': self.dim
        }

    def drop_collection(self):
        """删除集合"""
        milvus_client.ensure_connected()

        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            logger.info(f"集合已删除: {self.collection_name}")
        else:
            logger.warning(f"集合不存在: {self.collection_name}")


# =========================================
# 💡 使用示例
# =========================================
"""
from services.retrieval.vector_retriever import VectorRetriever
from services.embedding.embedder import Embedder
from services.embedding.embedding_model import EmbeddingModel

# 1. 初始化
model = EmbeddingModel(model_name='BAAI/bge-large-zh-v1.5')
embedder = Embedder(embedding_model=model)

retriever = VectorRetriever(
    collection_name='documents',
    embedder=embedder,
    host='localhost',
    port='19530',
    dim=1024
)

# 2. 创建集合和索引
retriever.create_collection(drop_if_exists=True)
retriever.create_index(index_type='HNSW', metric_type='IP')

# 3. 插入文档
documents = [
    {
        'doc_id': 'doc1',
        'text': '建筑结构荷载规范 GB50009-2012',
        'metadata': {'type': 'regulation', 'year': 2012}
    },
    {
        'doc_id': 'doc2',
        'text': '建筑抗震设计规范 GB50011-2010',
        'metadata': {'type': 'regulation', 'year': 2010}
    }
]

retriever.insert(documents)

# 4. 检索
query = "建筑结构荷载如何计算？"
results = retriever.search(query, top_k=5)

for result in results:
    print(f"排名: {result['rank']}")
    print(f"相似度: {result['score']:.4f}")
    print(f"文档: {result['text']}")
    print("---")

# 5. 带过滤条件的检索
results = retriever.search(
    query="建筑规范",
    top_k=5,
    filters="metadata['year'] >= 2010"
)

# 6. 查看统计
stats = retriever.get_stats()
print(f"集合统计: {stats}")
"""