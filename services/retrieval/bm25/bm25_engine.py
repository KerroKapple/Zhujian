"""
========================================
BM25关键词检索器
========================================

📚 模块说明：
- 基于BM25算法的关键词检索
- 稀疏检索，互补向量检索
- 适合精确匹配场景

🎯 核心功能：
1. BM25索引构建
2. 关键词检索
3. 增量索引更新
4. 结果排序

========================================
"""

import pickle
from typing import List, Dict, Tuple, Optional
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from loguru import logger

from utils.text_utils import TextProcessor


class BM25Retriever:
    """
    BM25检索器

    🔧 技术特点：
    - BM25Okapi算法（改进版BM25）
    - 中文分词支持
    - 支持索引持久化

    💡 适用场景：
    - 关键词精确匹配
    - 专业术语检索
    - 规范标准查询
    """

    def __init__(
            self,
            text_processor: Optional[TextProcessor] = None,
            k1: float = 1.5,
            b: float = 0.75
    ):
        """
        初始化BM25检索器

        参数：
            text_processor: 文本处理器实例
            k1: BM25参数k1（词频饱和度，推荐1.2-2.0）
            b: BM25参数b（文档长度归一化，推荐0.75）
        """
        self.text_processor = text_processor or TextProcessor()
        self.k1 = k1
        self.b = b

        # BM25模型
        self.bm25_model = None

        # 文档数据
        self.documents = []  # 原始文档
        self.tokenized_docs = []  # 分词后的文档
        self.doc_ids = []  # 文档ID

        logger.info(f"BM25检索器初始化 | k1={k1}, b={b}")

    def build_index(
            self,
            documents: List[Dict],
            text_key: str = 'text',
            id_key: str = 'id'
    ):
        """
        构建BM25索引

        参数：
            documents: 文档列表
                [
                    {'id': 'doc1', 'text': '文档内容', ...},
                    ...
                ]
            text_key: 文本字段的键名
            id_key: ID字段的键名
        """
        logger.info(f"开始构建BM25索引 | 文档数: {len(documents)}")

        # 重置数据
        self.documents = []
        self.tokenized_docs = []
        self.doc_ids = []

        # 处理文档
        for idx, doc in enumerate(documents):
            # 获取文本
            text = doc.get(text_key, '')
            if not text or not text.strip():
                logger.warning(f"文档{idx}文本为空，跳过")
                continue

            # 分词
            tokens = self.text_processor.tokenize(text, mode='search')
            if not tokens:
                logger.warning(f"文档{idx}分词后为空，跳过")
                continue

            # 保存
            self.documents.append(doc)
            self.tokenized_docs.append(tokens)

            # 获取ID（如果没有ID，使用索引）
            doc_id = doc.get(id_key, f"doc_{idx}")
            self.doc_ids.append(doc_id)

        # 构建BM25模型
        if self.tokenized_docs:
            self.bm25_model = BM25Okapi(
                self.tokenized_docs,
                k1=self.k1,
                b=self.b
            )

            logger.info(
                f"BM25索引构建完成 | "
                f"有效文档: {len(self.tokenized_docs)} | "
                f"平均词数: {np.mean([len(d) for d in self.tokenized_docs]):.1f}"
            )
        else:
            logger.warning("没有有效文档，索引为空")

    def search(
            self,
            query: str,
            top_k: int = 10,
            return_scores: bool = True
    ) -> List[Dict]:
        """
        检索文档

        参数：
            query: 查询文本
            top_k: 返回前K个结果
            return_scores: 是否返回分数

        返回：
            检索结果列表
            [
                {
                    'document': Dict,  # 原始文档
                    'score': float,    # BM25分数
                    'rank': int,       # 排名
                    'doc_id': str      # 文档ID
                },
                ...
            ]
        """
        if not self.bm25_model:
            logger.warning("BM25索引未构建，返回空结果")
            return []

        if not query or not query.strip():
            logger.warning("查询文本为空")
            return []

        logger.debug(f"BM25检索 | 查询: {query[:50]}... | top_k: {top_k}")

        # 查询分词
        query_tokens = self.text_processor.tokenize(query, mode='search')
        if not query_tokens:
            logger.warning("查询分词后为空")
            return []

        # 计算BM25分数
        scores = self.bm25_model.get_scores(query_tokens)

        # 获取Top-K索引
        top_k = min(top_k, len(scores))
        top_indices = np.argsort(scores)[::-1][:top_k]

        # 构建结果
        results = []
        for rank, idx in enumerate(top_indices, 1):
            score = float(scores[idx])

            # 过滤0分结果
            if score <= 0:
                break

            result = {
                'document': self.documents[idx],
                'doc_id': self.doc_ids[idx],
                'rank': rank
            }

            if return_scores:
                result['score'] = score

            results.append(result)

        logger.debug(f"BM25检索完成 | 返回: {len(results)} 个结果")

        return results

    def add_documents(
            self,
            new_documents: List[Dict],
            text_key: str = 'text',
            id_key: str = 'id'
    ):
        """
        增量添加文档（重建索引）

        参数：
            new_documents: 新文档列表
            text_key: 文本字段键名
            id_key: ID字段键名
        """
        logger.info(f"增量添加文档 | 新增: {len(new_documents)}")

        # 合并文档
        all_documents = self.documents + new_documents

        # 重建索引
        self.build_index(all_documents, text_key, id_key)

    def save(self, filepath: str):
        """
        保存索引到文件

        参数:
            filepath: 保存路径
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'documents': self.documents,
            'tokenized_docs': self.tokenized_docs,
            'doc_ids': self.doc_ids,
            'k1': self.k1,
            'b': self.b
        }

        with open(filepath, 'wb') as f:
            pickle.dump(data, f)

        logger.info(f"BM25索引已保存: {filepath}")

    def load(self, filepath: str):
        """
        从文件加载索引

        参数:
            filepath: 文件路径
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"索引文件不存在: {filepath}")

        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        self.documents = data['documents']
        self.tokenized_docs = data['tokenized_docs']
        self.doc_ids = data['doc_ids']
        self.k1 = data.get('k1', 1.5)
        self.b = data.get('b', 0.75)

        # 重建BM25模型
        if self.tokenized_docs:
            self.bm25_model = BM25Okapi(
                self.tokenized_docs,
                k1=self.k1,
                b=self.b
            )

        logger.info(
            f"BM25索引已加载: {filepath} | "
            f"文档数: {len(self.documents)}"
        )

    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        if not self.tokenized_docs:
            return {'total_docs': 0}

        token_counts = [len(doc) for doc in self.tokenized_docs]

        return {
            'total_docs': len(self.documents),
            'avg_doc_length': np.mean(token_counts),
            'min_doc_length': np.min(token_counts),
            'max_doc_length': np.max(token_counts),
            'k1': self.k1,
            'b': self.b
        }


# =========================================
# 💡 使用示例
# =========================================
"""
from services.retrieval.bm25_retriever import BM25Retriever

# 1. 构建索引
documents = [
    {
        'id': 'doc1',
        'text': '建筑结构荷载规范 GB50009-2012',
        'metadata': {'type': 'regulation'}
    },
    {
        'id': 'doc2',
        'text': '建筑抗震设计规范 GB50011-2010',
        'metadata': {'type': 'regulation'}
    },
    {
        'id': 'doc3',
        'text': '混凝土结构设计规范 GB50010-2010',
        'metadata': {'type': 'regulation'}
    }
]

retriever = BM25Retriever()
retriever.build_index(documents)


# 2. 检索
query = "建筑结构荷载如何计算？"
results = retriever.search(query, top_k=5)

for result in results:
    print(f"排名: {result['rank']}")
    print(f"分数: {result['score']:.4f}")
    print(f"文档: {result['document']['text']}")
    print("---")


# 3. 保存和加载索引
retriever.save("data/indexes/bm25_index.pkl")

new_retriever = BM25Retriever()
new_retriever.load("data/indexes/bm25_index.pkl")


# 4. 增量添加文档
new_docs = [
    {'id': 'doc4', 'text': '建筑地基基础设计规范'}
]
retriever.add_documents(new_docs)


# 5. 查看统计信息
stats = retriever.get_stats()
print(f"索引统计: {stats}")
"""