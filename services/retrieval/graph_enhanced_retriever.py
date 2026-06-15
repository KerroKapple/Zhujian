"""
========================================
图谱增强检索器 - Graph-Enhanced RAG
========================================

📚 模块说明：
- 整合向量检索、BM25 检索和图谱检索
- 实现三路召回 + 融合 + 重排序
- 提供图谱知识增强的 RAG 检索

🎯 核心功能：
1. 三路检索（向量 + BM25 + 图谱）
2. 智能融合（RRF + 图谱加权）
3. 上下文增强（图谱知识注入）
4. 实体链接（查询实体识别）

🔧 检索流程：
1. 查询分析 → 实体识别
2. 三路并行检索
3. 结果融合（考虑图谱权重）
4. Rerank 重排序
5. 图谱上下文增强

========================================
"""

from typing import List, Dict, Any, Optional, Literal
import asyncio
from loguru import logger

from core.config import settings


class GraphEnhancedRetriever:
    """
    图谱增强检索器

    🔧 特性：
    - 三路召回：向量 + BM25 + 知识图谱
    - 智能融合：RRF 算法 + 图谱权重提升
    - 上下文增强：将图谱知识注入检索结果
    - 实体感知：识别查询中的实体并关联图谱

    💡 优势：
    - 结合语义理解和结构化知识
    - 提高专业术语的检索准确率
    - 支持实体关系推理
    - 增强答案的可解释性
    """

    def __init__(
        self,
        bm25_retriever=None,
        vector_retriever=None,
        graph_retriever=None,
        reranker=None,
        fusion_method: Literal['rrf', 'weighted'] = 'rrf',
        graph_weight: float = 0.3,
        enable_context_enhancement: bool = True
    ):
        """
        初始化图谱增强检索器

        参数：
            bm25_retriever: BM25 检索器
            vector_retriever: 向量检索器
            graph_retriever: 图谱检索器
            reranker: 重排序器
            fusion_method: 融合方法 ('rrf' 或 'weighted')
            graph_weight: 图谱检索权重 (0-1)
            enable_context_enhancement: 是否启用上下文增强
        """
        self.bm25_retriever = bm25_retriever
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
        self.reranker = reranker
        self.fusion_method = fusion_method
        self.graph_weight = graph_weight
        self.enable_context_enhancement = enable_context_enhancement

        # 权重配置
        self.weights = {
            'bm25': settings.BM25_WEIGHT if hasattr(settings, 'BM25_WEIGHT') else 0.3,
            'vector': settings.VECTOR_WEIGHT if hasattr(settings, 'VECTOR_WEIGHT') else 0.4,
            'graph': graph_weight
        }

        # 延迟初始化标志
        self._initialized = False

        logger.info(
            f"图谱增强检索器初始化 | "
            f"BM25: {bm25_retriever is not None} | "
            f"Vector: {vector_retriever is not None} | "
            f"Graph: {graph_retriever is not None} | "
            f"融合方法: {fusion_method} | "
            f"图谱权重: {graph_weight}"
        )

    def _lazy_init(self):
        """懒加载初始化组件"""
        if self._initialized:
            return

        # 初始化图谱检索器（如果未提供）
        if self.graph_retriever is None:
            try:
                from services.retrieval.graph.graph_retriever import GraphRetriever
                self.graph_retriever = GraphRetriever(
                    enable_entity_extraction=True,
                    max_entities=5,
                    relation_depth=2
                )
                logger.info("图谱检索器已自动初始化")
            except Exception as e:
                logger.warning(f"图谱检索器初始化失败: {e}")
                self.graph_retriever = None

        self._initialized = True

    def search(
        self,
        query: str,
        top_k: int = 10,
        bm25_top_k: Optional[int] = None,
        vector_top_k: Optional[int] = None,
        graph_top_k: Optional[int] = None,
        use_rerank: bool = True,
        rerank_top_k: Optional[int] = None,
        filters: Optional[str] = None,
        document_id: Optional[str] = None,
        fusion_weights: Optional[Dict[str, float]] = None,
        enhance_with_graph: bool = True
    ) -> List[Dict[str, Any]]:
        """
        图谱增强混合检索

        参数：
            query: 查询文本
            top_k: 最终返回数量
            bm25_top_k: BM25 检索数量
            vector_top_k: 向量检索数量
            graph_top_k: 图谱检索数量
            use_rerank: 是否使用重排序
            rerank_top_k: 重排序候选数量
            filters: 向量检索过滤条件
            document_id: 限定文档 ID
            fusion_weights: 自定义融合权重
            enhance_with_graph: 是否用图谱知识增强结果

        返回：
            检索结果列表
        """
        self._lazy_init()

        logger.info(f"图谱增强检索 | 查询: {query[:50]}... | top_k: {top_k}")

        # 设置默认检索数量
        if bm25_top_k is None:
            bm25_top_k = top_k * 3
        if vector_top_k is None:
            vector_top_k = top_k * 3
        if graph_top_k is None:
            graph_top_k = top_k * 2

        # Step 1: 三路并行检索
        bm25_results = []
        vector_results = []
        graph_results = []

        # BM25 检索
        if self.bm25_retriever:
            try:
                bm25_results = self.bm25_retriever.search(
                    query=query,
                    top_k=bm25_top_k,
                    return_scores=True
                )
                logger.debug(f"BM25 检索完成 | 结果数: {len(bm25_results)}")
            except Exception as e:
                logger.warning(f"BM25 检索失败: {e}")

        # 向量检索
        if self.vector_retriever:
            try:
                vector_results = self.vector_retriever.search(
                    query=query,
                    top_k=vector_top_k,
                    filters=filters
                )
                logger.debug(f"向量检索完成 | 结果数: {len(vector_results)}")
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")

        # 图谱检索
        if self.graph_retriever and self.graph_retriever.is_available():
            try:
                graph_results = self.graph_retriever.search(
                    query=query,
                    top_k=graph_top_k,
                    document_id=document_id,
                    return_context=True
                )
                logger.debug(f"图谱检索完成 | 结果数: {len(graph_results)}")
            except Exception as e:
                logger.warning(f"图谱检索失败: {e}")

        # Step 2: 结果融合
        fused_results = self._fuse_three_way_results(
            bm25_results=bm25_results,
            vector_results=vector_results,
            graph_results=graph_results,
            fusion_weights=fusion_weights
        )

        # 限制候选数量
        if rerank_top_k is None:
            rerank_top_k = min(top_k * 3, len(fused_results))
        fused_results = fused_results[:rerank_top_k]

        # Step 3: 重排序
        if use_rerank and self.reranker and fused_results:
            logger.debug(f"重排序 | 候选数: {len(fused_results)}")
            try:
                fused_results = self.reranker.rerank(
                    query=query,
                    documents=fused_results,
                    text_key='text',
                    top_k=None,
                    return_scores=True
                )
            except Exception as e:
                logger.warning(f"重排序失败: {e}")

        # Step 4: 图谱上下文增强
        if enhance_with_graph and self.enable_context_enhancement and graph_results:
            fused_results = self._enhance_with_graph_context(
                results=fused_results,
                graph_results=graph_results,
                query=query
            )

        # Step 5: 返回 Top-K
        final_results = fused_results[:top_k]

        logger.info(
            f"图谱增强检索完成 | "
            f"BM25: {len(bm25_results)} | "
            f"Vector: {len(vector_results)} | "
            f"Graph: {len(graph_results)} | "
            f"最终: {len(final_results)}"
        )

        return final_results

    async def search_async(
        self,
        query: str,
        top_k: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        异步图谱增强检索

        并行执行三路检索以提高效率
        """
        self._lazy_init()

        logger.info(f"异步图谱增强检索 | 查询: {query[:50]}...")

        bm25_top_k = kwargs.get('bm25_top_k', top_k * 3)
        vector_top_k = kwargs.get('vector_top_k', top_k * 3)
        graph_top_k = kwargs.get('graph_top_k', top_k * 2)
        filters = kwargs.get('filters')
        document_id = kwargs.get('document_id')

        # 三路检索均为同步阻塞，用 asyncio.to_thread 包裹使其真正并发
        async def _bm25_search():
            if not self.bm25_retriever:
                return []
            try:
                return await asyncio.to_thread(
                    self.bm25_retriever.search, query=query, top_k=bm25_top_k, return_scores=True
                )
            except Exception as e:
                logger.warning(f"BM25 检索失败: {e}")
                return []

        async def _vector_search():
            if not self.vector_retriever:
                return []
            try:
                return await asyncio.to_thread(
                    self.vector_retriever.search, query=query, top_k=vector_top_k, filters=filters
                )
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")
                return []

        async def _graph_search():
            if not self.graph_retriever or not self.graph_retriever.is_available():
                return []
            try:
                return await asyncio.to_thread(
                    self.graph_retriever.search, query=query, top_k=graph_top_k, document_id=document_id
                )
            except Exception as e:
                logger.warning(f"图谱检索失败: {e}")
                return []

        # 并行执行
        bm25_results, vector_results, graph_results = await asyncio.gather(
            _bm25_search(),
            _vector_search(),
            _graph_search()
        )

        # 融合结果
        fused_results = self._fuse_three_way_results(
            bm25_results=bm25_results,
            vector_results=vector_results,
            graph_results=graph_results,
            fusion_weights=kwargs.get('fusion_weights')
        )

        # 重排序
        use_rerank = kwargs.get('use_rerank', True)
        rerank_top_k = kwargs.get('rerank_top_k', min(top_k * 3, len(fused_results)))
        fused_results = fused_results[:rerank_top_k]

        if use_rerank and self.reranker and fused_results:
            try:
                fused_results = self.reranker.rerank(
                    query=query,
                    documents=fused_results,
                    text_key='text',
                    top_k=None,
                    return_scores=True
                )
            except Exception as e:
                logger.warning(f"重排序失败: {e}")

        # 图谱上下文增强
        enhance_with_graph = kwargs.get('enhance_with_graph', True)
        if enhance_with_graph and self.enable_context_enhancement and graph_results:
            fused_results = self._enhance_with_graph_context(
                results=fused_results,
                graph_results=graph_results,
                query=query
            )

        return fused_results[:top_k]

    def _fuse_three_way_results(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        graph_results: List[Dict],
        fusion_weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        三路结果融合

        使用 RRF 算法融合三路检索结果，并对图谱结果进行加权提升
        """
        if fusion_weights is None:
            fusion_weights = self.weights

        if self.fusion_method == 'rrf':
            return self._rrf_three_way_fusion(
                bm25_results,
                vector_results,
                graph_results,
                fusion_weights
            )
        else:
            return self._weighted_three_way_fusion(
                bm25_results,
                vector_results,
                graph_results,
                fusion_weights
            )

    def _rrf_three_way_fusion(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        graph_results: List[Dict],
        fusion_weights: Dict[str, float],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        三路 RRF 融合

        公式：RRF_score = Σ (weight_i / (k + rank_i))
        """
        doc_scores = {}
        doc_data = {}

        # BM25 结果
        bm25_weight = fusion_weights.get('bm25', 0.3)
        for rank, doc in enumerate(bm25_results, 1):
            doc_id = self._get_doc_id(doc)
            rrf_score = bm25_weight / (k + rank)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0
                doc_data[doc_id] = doc.copy()

            doc_scores[doc_id] += rrf_score
            doc_data[doc_id]['bm25_rank'] = rank
            doc_data[doc_id]['bm25_score'] = doc.get('score', 0)

        # 向量结果
        vector_weight = fusion_weights.get('vector', 0.4)
        for rank, doc in enumerate(vector_results, 1):
            doc_id = self._get_doc_id(doc)
            rrf_score = vector_weight / (k + rank)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0
                doc_data[doc_id] = doc.copy()

            doc_scores[doc_id] += rrf_score
            doc_data[doc_id]['vector_rank'] = rank
            doc_data[doc_id]['vector_score'] = doc.get('score', 0)

        # 图谱结果（特殊处理）
        graph_weight = fusion_weights.get('graph', 0.3)
        for rank, doc in enumerate(graph_results, 1):
            doc_id = self._get_doc_id(doc)

            # 图谱结果使用更高的基础分数
            rrf_score = graph_weight / (k + rank)

            # 如果图谱结果包含上下文，额外加分
            if doc.get('context') or doc.get('relations'):
                rrf_score *= 1.2  # 图谱上下文加成

            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0
                doc_data[doc_id] = doc.copy()

            doc_scores[doc_id] += rrf_score
            doc_data[doc_id]['graph_rank'] = rank
            doc_data[doc_id]['graph_score'] = doc.get('score', 0)
            doc_data[doc_id]['has_graph_context'] = bool(doc.get('context'))

            # 保存图谱上下文
            if doc.get('context'):
                doc_data[doc_id]['graph_context'] = doc.get('context')
            if doc.get('relations'):
                doc_data[doc_id]['graph_relations'] = doc.get('relations')
            if doc.get('entity'):
                doc_data[doc_id]['graph_entity'] = doc.get('entity')

        # 按融合分数排序
        sorted_docs = sorted(
            doc_data.values(),
            key=lambda x: doc_scores.get(self._get_doc_id(x), 0),
            reverse=True
        )

        # 添加融合信息
        for rank, doc in enumerate(sorted_docs, 1):
            doc_id = self._get_doc_id(doc)
            doc['fusion_score'] = doc_scores.get(doc_id, 0)
            doc['fusion_rank'] = rank
            doc['retrieval_sources'] = self._get_retrieval_sources(doc)

        return sorted_docs

    def _weighted_three_way_fusion(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        graph_results: List[Dict],
        fusion_weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        三路加权融合
        """
        all_docs = {}

        # 归一化函数
        def normalize_scores(docs, score_key='score'):
            if not docs:
                return []
            scores = [d.get(score_key, 0) for d in docs]
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return [(d, 1.0) for d in docs]
            return [(d, (d.get(score_key, 0) - min_s) / (max_s - min_s)) for d in docs]

        # BM25 结果
        bm25_weight = fusion_weights.get('bm25', 0.3)
        for doc, norm_score in normalize_scores(bm25_results):
            doc_id = self._get_doc_id(doc)
            if doc_id not in all_docs:
                all_docs[doc_id] = doc.copy()
                all_docs[doc_id]['weighted_score'] = 0
            all_docs[doc_id]['weighted_score'] += norm_score * bm25_weight
            all_docs[doc_id]['bm25_score'] = doc.get('score', 0)

        # 向量结果
        vector_weight = fusion_weights.get('vector', 0.4)
        for doc, norm_score in normalize_scores(vector_results):
            doc_id = self._get_doc_id(doc)
            if doc_id not in all_docs:
                all_docs[doc_id] = doc.copy()
                all_docs[doc_id]['weighted_score'] = 0
            all_docs[doc_id]['weighted_score'] += norm_score * vector_weight
            all_docs[doc_id]['vector_score'] = doc.get('score', 0)

        # 图谱结果
        graph_weight = fusion_weights.get('graph', 0.3)
        for doc, norm_score in normalize_scores(graph_results):
            doc_id = self._get_doc_id(doc)

            # 图谱上下文加成
            context_bonus = 0.1 if doc.get('context') else 0

            if doc_id not in all_docs:
                all_docs[doc_id] = doc.copy()
                all_docs[doc_id]['weighted_score'] = 0
            all_docs[doc_id]['weighted_score'] += (norm_score + context_bonus) * graph_weight
            all_docs[doc_id]['graph_score'] = doc.get('score', 0)
            all_docs[doc_id]['has_graph_context'] = bool(doc.get('context'))

            if doc.get('context'):
                all_docs[doc_id]['graph_context'] = doc.get('context')

        # 排序
        docs_list = list(all_docs.values())
        docs_list.sort(key=lambda x: x.get('weighted_score', 0), reverse=True)

        for rank, doc in enumerate(docs_list, 1):
            doc['fusion_rank'] = rank
            doc['fusion_score'] = doc.get('weighted_score', 0)

        return docs_list

    def _enhance_with_graph_context(
        self,
        results: List[Dict],
        graph_results: List[Dict],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        使用图谱知识增强检索结果

        将图谱上下文注入到检索结果中，提供额外的结构化信息
        """
        # 构建图谱知识索引
        graph_knowledge = {}
        for gr in graph_results:
            entity = gr.get('entity', {})
            entity_id = entity.get('id', '')
            if entity_id:
                graph_knowledge[entity_id] = {
                    'context': gr.get('context', ''),
                    'relations': gr.get('relations', []),
                    'related_entities': gr.get('related_entities', [])
                }

        # 增强检索结果
        for result in results:
            # 如果结果已经有图谱上下文，跳过
            if result.get('has_graph_context'):
                continue

            # 尝试关联图谱知识
            doc_text = result.get('text', '')

            # 查找匹配的图谱实体
            matched_contexts = []
            for entity_id, knowledge in graph_knowledge.items():
                # 简单的文本匹配
                if entity_id in doc_text or any(
                    rel.get('target_id', '') in doc_text
                    for rel in knowledge.get('relations', [])
                ):
                    if knowledge.get('context'):
                        matched_contexts.append(knowledge['context'])

            # 添加图谱增强上下文
            if matched_contexts:
                result['graph_enhanced'] = True
                result['graph_context'] = ' '.join(matched_contexts[:2])  # 最多2个

        # 构建全局图谱摘要（添加到第一个结果）
        if results and graph_results:
            global_context = self._build_global_graph_summary(graph_results, query)
            if global_context:
                results[0]['global_graph_context'] = global_context

        return results

    def _build_global_graph_summary(
        self,
        graph_results: List[Dict],
        query: str
    ) -> str:
        """
        构建全局图谱摘要

        汇总所有图谱检索结果，生成简洁的知识摘要
        """
        summary_parts = []

        # 收集所有实体
        entities_by_type = {}
        for gr in graph_results[:5]:  # 最多5个
            entity = gr.get('entity', {})
            entity_type = entity.get('type', 'unknown')
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)

        # 生成摘要
        if 'component' in entities_by_type:
            components = entities_by_type['component']
            codes = [c.get('properties', {}).get('code', '') for c in components if c.get('properties', {}).get('code')]
            if codes:
                summary_parts.append(f"相关构件: {', '.join(codes[:5])}")

        if 'material' in entities_by_type:
            materials = entities_by_type['material']
            grades = [m.get('properties', {}).get('grade', '') for m in materials if m.get('properties', {}).get('grade')]
            if grades:
                summary_parts.append(f"相关材料: {', '.join(set(grades[:5]))}")

        if 'specification' in entities_by_type:
            specs = entities_by_type['specification']
            codes = [s.get('properties', {}).get('code', '') for s in specs if s.get('properties', {}).get('code')]
            if codes:
                summary_parts.append(f"相关规范: {', '.join(codes[:3])}")

        if summary_parts:
            return "【知识图谱摘要】" + "; ".join(summary_parts)

        return ""

    def _get_doc_id(self, doc: Dict) -> str:
        """获取文档唯一标识"""
        return doc.get('doc_id', doc.get('chunk_id', doc.get('id', str(id(doc)))))

    def _get_retrieval_sources(self, doc: Dict) -> List[str]:
        """获取检索来源"""
        sources = []
        if 'bm25_rank' in doc:
            sources.append('bm25')
        if 'vector_rank' in doc:
            sources.append('vector')
        if 'graph_rank' in doc:
            sources.append('graph')
        return sources

    def get_graph_context_for_prompt(
        self,
        results: List[Dict]
    ) -> str:
        """
        获取用于 Prompt 的图谱上下文

        从检索结果中提取图谱知识，格式化为 Prompt 可用的文本
        """
        context_parts = []

        # 全局图谱上下文
        for result in results:
            if result.get('global_graph_context'):
                context_parts.append(result['global_graph_context'])
                break

        # 单个结果的图谱上下文
        for result in results[:5]:
            if result.get('graph_context'):
                context_parts.append(result['graph_context'])

        if context_parts:
            return "\n".join(context_parts)

        return ""


# =========================================
# 💡 使用示例
# =========================================
"""
from services.retrieval.graph_enhanced_retriever import GraphEnhancedRetriever
from services.retrieval.bm25.bm25_engine import BM25Retriever
from services.retrieval.vector.vector_engine import VectorRetriever
from services.retrieval.graph.graph_retriever import GraphRetriever
from services.rerank.reranker import Reranker

# 1. 初始化各组件
bm25 = BM25Retriever()
vector = VectorRetriever(...)
graph = GraphRetriever()
reranker = Reranker()

# 2. 创建图谱增强检索器
retriever = GraphEnhancedRetriever(
    bm25_retriever=bm25,
    vector_retriever=vector,
    graph_retriever=graph,
    reranker=reranker,
    fusion_method='rrf',
    graph_weight=0.3
)

# 3. 检索
results = retriever.search(
    query="KL-1 梁的混凝土强度等级是多少？",
    top_k=5,
    use_rerank=True,
    enhance_with_graph=True
)

# 4. 查看结果
for result in results:
    print(f"排名: {result['fusion_rank']}")
    print(f"来源: {result.get('retrieval_sources', [])}")
    print(f"文本: {result['text'][:100]}...")
    if result.get('graph_context'):
        print(f"图谱上下文: {result['graph_context']}")
    print("---")

# 5. 获取用于 Prompt 的图谱上下文
graph_context = retriever.get_graph_context_for_prompt(results)
print(f"图谱上下文: {graph_context}")

# 6. 异步检索
import asyncio

async def main():
    results = await retriever.search_async(
        query="框架梁使用什么钢筋？",
        top_k=5
    )
    return results

results = asyncio.run(main())
"""
