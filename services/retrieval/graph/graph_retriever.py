"""
========================================
图谱检索器 - 基于 Neo4j 的知识检索
========================================

📚 模块说明：
- 从知识图谱中检索相关实体和关系
- 支持实体识别和关系路径查询
- 为 RAG 提供结构化知识增强

🎯 核心功能：
1. 实体检索 - 根据查询识别相关实体
2. 关系检索 - 获取实体间的关系
3. 子图检索 - 获取实体的局部子图
4. 路径检索 - 查找实体间的路径

========================================
"""

from typing import List, Dict, Any, Optional, Tuple
import re
from loguru import logger

from core.config import settings


class GraphRetriever:
    """
    图谱检索器

    🔧 检索策略：
    1. 实体识别：从查询中提取实体关键词
    2. 实体检索：在图谱中查找匹配的实体
    3. 关系扩展：获取实体的关联关系
    4. 上下文构建：将图谱知识转换为文本上下文

    💡 优势：
    - 提供结构化知识
    - 增强实体关系理解
    - 支持多跳推理
    """

    # 实体类型映射
    ENTITY_TYPES = {
        "component": ["构件", "梁", "柱", "板", "墙", "基础", "楼梯", "KL", "KZ", "LB", "Q"],
        "material": ["材料", "混凝土", "钢筋", "钢材", "C30", "C35", "HRB400", "Q235"],
        "specification": ["规范", "标准", "GB", "JGJ", "DBJ"],
        "dimension": ["尺寸", "厚度", "高度", "宽度", "跨度", "截面"],
    }

    # 构件编号正则
    COMPONENT_PATTERNS = [
        r"[KDL]+[-\s]?\d+[a-zA-Z]?",  # 梁：KL-1, DL-2
        r"[KZ]+[-\s]?\d+[a-zA-Z]?",    # 柱：KZ-1
        r"[LB]+[-\s]?\d+[a-zA-Z]?",    # 板：LB-1
        r"[QZ]+[-\s]?\d+[a-zA-Z]?",    # 墙：QZ-1
    ]

    # 规范编号正则
    SPEC_PATTERNS = [
        r"GB\s*\d{4,6}[-–]\d{4}",
        r"GB/T\s*\d{4,6}[-–]\d{4}",
        r"JGJ\s*\d{2,4}[-–]\d{4}",
    ]

    # 材料等级正则
    MATERIAL_PATTERNS = [
        r"C\d{2,3}",           # 混凝土：C30
        r"HRB\d{3}[E]?",       # 钢筋：HRB400
        r"Q\d{3}[A-Z]?",       # 钢材：Q235B
    ]

    def __init__(
        self,
        enable_entity_extraction: bool = True,
        max_entities: int = 5,
        relation_depth: int = 2,
        include_related_docs: bool = True
    ):
        """
        初始化图谱检索器

        参数：
            enable_entity_extraction: 是否启用实体提取
            max_entities: 最大检索实体数
            relation_depth: 关系遍历深度
            include_related_docs: 是否包含关联文档
        """
        self.enable_entity_extraction = enable_entity_extraction
        self.max_entities = max_entities
        self.relation_depth = relation_depth
        self.include_related_docs = include_related_docs

        self._neo4j_client = None
        self._graph_repo = None

        logger.info(
            f"图谱检索器初始化 | "
            f"实体提取: {enable_entity_extraction} | "
            f"最大实体数: {max_entities} | "
            f"关系深度: {relation_depth}"
        )

    @property
    def neo4j_client(self):
        """延迟加载 Neo4j 客户端"""
        if self._neo4j_client is None:
            try:
                from services.graph.neo4j_client import neo4j_client
                self._neo4j_client = neo4j_client
            except Exception as e:
                logger.warning(f"Neo4j 客户端加载失败: {e}")
        return self._neo4j_client

    @property
    def graph_repo(self):
        """延迟加载图数据库 Repository"""
        if self._graph_repo is None:
            try:
                from repository.graph_repo import GraphRepository
                self._graph_repo = GraphRepository()
            except Exception as e:
                logger.warning(f"GraphRepository 加载失败: {e}")
        return self._graph_repo

    def is_available(self) -> bool:
        """检查图谱服务是否可用"""
        try:
            return self.neo4j_client is not None and self.neo4j_client.ping()
        except Exception:
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        return_context: bool = True
    ) -> List[Dict[str, Any]]:
        """
        图谱检索

        参数：
            query: 查询文本
            top_k: 返回结果数量
            document_id: 限定文档范围
            entity_types: 限定实体类型
            return_context: 是否返回上下文文本

        返回：
            检索结果列表，包含：
            - entity: 实体信息
            - relations: 关联关系
            - context: 上下文文本（可选）
            - score: 相关性分数
        """
        if not self.is_available():
            logger.warning("图谱服务不可用，跳过图谱检索")
            return []

        logger.info(f"图谱检索 | 查询: {query[:50]}... | top_k: {top_k}")

        results = []

        try:
            # Step 1: 从查询中提取实体
            extracted_entities = self._extract_entities_from_query(query)
            logger.debug(f"提取到实体: {extracted_entities}")

            # Step 2: 在图谱中检索匹配的实体
            matched_entities = self._search_entities(
                extracted_entities,
                document_id=document_id,
                entity_types=entity_types,
                limit=self.max_entities
            )

            # Step 3: 获取实体的关联关系
            for entity in matched_entities[:top_k]:
                entity_result = {
                    "entity": entity,
                    "relations": [],
                    "related_entities": [],
                    "score": entity.get("score", 0.8),
                    "source": "graph"
                }

                # 获取关联关系
                relations = self._get_entity_relations(
                    entity_id=entity.get("id"),
                    depth=self.relation_depth
                )
                entity_result["relations"] = relations

                # 获取关联实体
                related = self._get_related_entities(
                    entity_id=entity.get("id"),
                    limit=5
                )
                entity_result["related_entities"] = related

                # 构建上下文文本
                if return_context:
                    context = self._build_context(entity, relations, related)
                    entity_result["text"] = context
                    entity_result["context"] = context

                results.append(entity_result)

            # Step 4: 如果启用关联文档检索
            if self.include_related_docs and matched_entities:
                doc_results = self._get_related_documents(
                    entities=matched_entities,
                    limit=top_k
                )
                for doc in doc_results:
                    if doc not in results:
                        results.append(doc)

            logger.info(f"图谱检索完成 | 结果数: {len(results)}")

        except Exception as e:
            logger.error(f"图谱检索失败: {e}", exc_info=True)

        return results[:top_k]

    def _extract_entities_from_query(self, query: str) -> List[Dict[str, Any]]:
        """
        从查询中提取实体

        使用规则和模式匹配提取可能的实体
        """
        entities = []

        # 1. 提取构件编号
        for pattern in self.COMPONENT_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "value": match.upper().replace(" ", ""),
                    "type": "component",
                    "field": "code",
                    "source": "pattern"
                })

        # 2. 提取规范编号
        for pattern in self.SPEC_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "value": match.replace(" ", ""),
                    "type": "specification",
                    "field": "code",
                    "source": "pattern"
                })

        # 3. 提取材料等级
        for pattern in self.MATERIAL_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "value": match.upper(),
                    "type": "material",
                    "field": "grade",
                    "source": "pattern"
                })

        # 4. 关键词匹配
        for entity_type, keywords in self.ENTITY_TYPES.items():
            for keyword in keywords:
                if keyword in query:
                    entities.append({
                        "value": keyword,
                        "type": entity_type,
                        "field": "keyword",
                        "source": "keyword"
                    })

        # 去重
        seen = set()
        unique_entities = []
        for entity in entities:
            key = f"{entity['type']}:{entity['value']}"
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def _search_entities(
        self,
        extracted_entities: List[Dict],
        document_id: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        在图谱中搜索实体
        """
        results = []

        if not self.neo4j_client:
            return results

        for extracted in extracted_entities:
            entity_type = extracted.get("type")
            value = extracted.get("value")
            field = extracted.get("field")

            # 过滤类型
            if entity_types and entity_type not in entity_types:
                continue

            # 构建查询
            label = self._get_label_for_type(entity_type)
            if not label:
                continue

            try:
                # value 用参数 $value 传入防注入；正则模式在 Cypher 内拼接，避免转义负担
                # label 来自 _get_label_for_type 白名单，安全
                doc_id_clause = " AND n.doc_id = $doc_id" if document_id else ""

                if field == "code":
                    query = f"""
                        MATCH (n:{label})
                        WHERE (n.code =~ ('(?i).*' + $value + '.*')
                               OR n.id =~ ('(?i).*' + $value + '.*')){doc_id_clause}
                        RETURN n
                        LIMIT $limit
                    """
                elif field == "grade":
                    query = f"""
                        MATCH (n:{label})
                        WHERE n.grade =~ ('(?i).*' + $value + '.*'){doc_id_clause}
                        RETURN n
                        LIMIT $limit
                    """
                else:
                    # 通用搜索
                    query = f"""
                        MATCH (n:{label})
                        WHERE any(key in keys(n) WHERE toString(n[key]) =~ ('(?i).*' + $value + '.*')){doc_id_clause}
                        RETURN n
                        LIMIT $limit
                    """

                params = {"limit": limit, "value": value}
                if document_id:
                    params["doc_id"] = document_id

                query_results = self.neo4j_client.execute_query(query, params)

                for item in query_results:
                    node = item.get("n", {})
                    if node:
                        results.append({
                            "id": node.get("id", ""),
                            "type": entity_type,
                            "label": label,
                            "properties": dict(node),
                            "matched_value": value,
                            "score": 0.9 if field in ["code", "grade"] else 0.7
                        })

            except Exception as e:
                logger.warning(f"实体搜索失败: {e}")

        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results[:limit]

    def _get_label_for_type(self, entity_type: str) -> Optional[str]:
        """获取实体类型对应的 Neo4j 标签"""
        type_to_label = {
            "component": "Component",
            "material": "Material",
            "specification": "Specification",
            "dimension": "Dimension",
            "document": "Document",
        }
        return type_to_label.get(entity_type)

    def _get_entity_relations(
        self,
        entity_id: str,
        depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        获取实体的关联关系
        """
        relations = []

        if not self.neo4j_client or not entity_id:
            return relations

        try:
            query = f"""
                MATCH (n {{id: $entity_id}})-[r]->(m)
                RETURN type(r) as rel_type, m as target, properties(r) as rel_props
                LIMIT 20
            """

            results = self.neo4j_client.execute_query(
                query,
                {"entity_id": entity_id}
            )

            for item in results:
                target = item.get("target", {})
                relations.append({
                    "type": item.get("rel_type", ""),
                    "target_id": target.get("id", ""),
                    "target_type": self._infer_type_from_node(target),
                    "target_properties": dict(target) if target else {},
                    "relation_properties": item.get("rel_props", {})
                })

            # 如果深度 > 1，递归获取
            if depth > 1:
                for rel in relations[:5]:  # 限制递归数量
                    target_id = rel.get("target_id")
                    if target_id:
                        sub_relations = self._get_entity_relations(
                            target_id,
                            depth=depth - 1
                        )
                        rel["sub_relations"] = sub_relations

        except Exception as e:
            logger.warning(f"获取关系失败: {e}")

        return relations

    def _get_related_entities(
        self,
        entity_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取关联实体
        """
        related = []

        if not self.neo4j_client or not entity_id:
            return related

        try:
            query = """
                MATCH (n {id: $entity_id})-[r]-(m)
                RETURN DISTINCT m as related, type(r) as rel_type
                LIMIT $limit
            """

            results = self.neo4j_client.execute_query(
                query,
                {"entity_id": entity_id, "limit": limit}
            )

            for item in results:
                node = item.get("related", {})
                if node:
                    related.append({
                        "id": node.get("id", ""),
                        "type": self._infer_type_from_node(node),
                        "relation": item.get("rel_type", ""),
                        "properties": dict(node)
                    })

        except Exception as e:
            logger.warning(f"获取关联实体失败: {e}")

        return related

    def _infer_type_from_node(self, node: Dict) -> str:
        """从节点属性推断类型"""
        if not node:
            return "unknown"

        if "code" in node and any(p in str(node.get("code", "")).upper() for p in ["KL", "KZ", "LB"]):
            return "component"
        if "grade" in node:
            return "material"
        if "spec_code" in node or "code" in node and "GB" in str(node.get("code", "")):
            return "specification"
        if "dimension_type" in node or "value" in node:
            return "dimension"
        if "doc_type" in node:
            return "document"

        return "unknown"

    def _get_related_documents(
        self,
        entities: List[Dict],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取与实体关联的文档
        """
        documents = []

        if not self.neo4j_client:
            return documents

        entity_ids = [e.get("id") for e in entities if e.get("id")]
        if not entity_ids:
            return documents

        try:
            query = """
                MATCH (n)-[:BELONGS_TO]->(d:Document)
                WHERE n.id IN $entity_ids
                RETURN DISTINCT d as document, count(n) as relevance
                ORDER BY relevance DESC
                LIMIT $limit
            """

            results = self.neo4j_client.execute_query(
                query,
                {"entity_ids": entity_ids, "limit": limit}
            )

            for item in results:
                doc = item.get("document", {})
                if doc:
                    documents.append({
                        "id": doc.get("id", ""),
                        "type": "document",
                        "properties": dict(doc),
                        "relevance": item.get("relevance", 1),
                        "source": "graph_document"
                    })

        except Exception as e:
            logger.warning(f"获取关联文档失败: {e}")

        return documents

    def _build_context(
        self,
        entity: Dict,
        relations: List[Dict],
        related_entities: List[Dict]
    ) -> str:
        """
        构建上下文文本

        将图谱知识转换为自然语言描述
        """
        context_parts = []

        # 实体描述
        entity_type = entity.get("type", "")
        props = entity.get("properties", {})

        if entity_type == "component":
            code = props.get("code", "")
            comp_type = props.get("type", "构件")
            context_parts.append(f"【构件信息】{code} 是一个{comp_type}类型的构件。")

        elif entity_type == "material":
            grade = props.get("grade", "")
            mat_type = props.get("type", "材料")
            context_parts.append(f"【材料信息】{grade} 是{mat_type}材料。")

        elif entity_type == "specification":
            code = props.get("code", "")
            name = props.get("name", "")
            context_parts.append(f"【规范信息】{code} {name}。")

        # 关系描述
        relation_descriptions = []
        for rel in relations[:5]:
            rel_type = rel.get("type", "")
            target_props = rel.get("target_properties", {})

            if rel_type == "USES_MATERIAL":
                grade = target_props.get("grade", "")
                relation_descriptions.append(f"使用材料 {grade}")

            elif rel_type == "HAS_DIMENSION":
                dim_type = target_props.get("type", "")
                value = target_props.get("value", "")
                unit = target_props.get("unit", "mm")
                relation_descriptions.append(f"{dim_type}为 {value}{unit}")

            elif rel_type == "REFERS_TO":
                code = target_props.get("code", "")
                relation_descriptions.append(f"引用规范 {code}")

            elif rel_type == "CONNECTED_TO":
                code = target_props.get("code", "")
                relation_descriptions.append(f"连接构件 {code}")

        if relation_descriptions:
            context_parts.append(f"【关联关系】{'; '.join(relation_descriptions)}。")

        # 关联实体描述
        if related_entities:
            related_desc = []
            for rel in related_entities[:3]:
                rel_type = rel.get("type", "")
                rel_props = rel.get("properties", {})

                if rel_type == "component":
                    related_desc.append(f"构件 {rel_props.get('code', '')}")
                elif rel_type == "material":
                    related_desc.append(f"材料 {rel_props.get('grade', '')}")

            if related_desc:
                context_parts.append(f"【关联项】{', '.join(related_desc)}。")

        return " ".join(context_parts)

    def get_entity_subgraph(
        self,
        entity_id: str,
        depth: int = 2,
        max_nodes: int = 50
    ) -> Dict[str, Any]:
        """
        获取实体的局部子图

        参数：
            entity_id: 实体 ID
            depth: 遍历深度
            max_nodes: 最大节点数

        返回：
            {
                "center_node": {...},
                "nodes": [...],
                "edges": [...]
            }
        """
        if not self.neo4j_client:
            return {"center_node": None, "nodes": [], "edges": []}

        try:
            query = f"""
                MATCH path = (n {{id: $entity_id}})-[*1..{depth}]-(m)
                WITH n, collect(DISTINCT m)[0..{max_nodes}] as neighbors,
                     collect(DISTINCT relationships(path)) as all_rels
                UNWIND all_rels as rels
                UNWIND rels as r
                WITH n, neighbors, collect(DISTINCT r) as edges
                RETURN n as center, neighbors, edges
            """

            results = self.neo4j_client.execute_query(
                query,
                {"entity_id": entity_id}
            )

            if results:
                result = results[0]
                center = result.get("center", {})
                neighbors = result.get("neighbors", [])
                edges = result.get("edges", [])

                return {
                    "center_node": dict(center) if center else None,
                    "nodes": [dict(n) for n in neighbors if n],
                    "edges": [
                        {
                            "from": str(e.start_node.get("id", "")) if hasattr(e, 'start_node') else "",
                            "to": str(e.end_node.get("id", "")) if hasattr(e, 'end_node') else "",
                            "type": e.type if hasattr(e, 'type') else str(e)
                        }
                        for e in edges if e
                    ]
                }

        except Exception as e:
            logger.error(f"获取子图失败: {e}")

        return {"center_node": None, "nodes": [], "edges": []}

    def find_path(
        self,
        from_entity_id: str,
        to_entity_id: str,
        max_depth: int = 4
    ) -> List[Dict[str, Any]]:
        """
        查找两个实体之间的路径

        参数：
            from_entity_id: 起始实体 ID
            to_entity_id: 目标实体 ID
            max_depth: 最大路径长度

        返回：
            路径列表，每条路径包含节点和关系
        """
        paths = []

        if not self.neo4j_client:
            return paths

        try:
            query = f"""
                MATCH path = shortestPath(
                    (a {{id: $from_id}})-[*1..{max_depth}]-(b {{id: $to_id}})
                )
                RETURN nodes(path) as nodes, relationships(path) as rels
                LIMIT 3
            """

            results = self.neo4j_client.execute_query(
                query,
                {"from_id": from_entity_id, "to_id": to_entity_id}
            )

            for result in results:
                nodes = result.get("nodes", [])
                rels = result.get("rels", [])

                paths.append({
                    "nodes": [dict(n) for n in nodes if n],
                    "relationships": [
                        {
                            "type": r.type if hasattr(r, 'type') else str(r),
                            "properties": dict(r) if hasattr(r, '__iter__') else {}
                        }
                        for r in rels if r
                    ],
                    "length": len(nodes) - 1
                })

        except Exception as e:
            logger.warning(f"路径查找失败: {e}")

        return paths


# =========================================
# 💡 使用示例
# =========================================
"""
from services.retrieval.graph.graph_retriever import GraphRetriever

# 1. 初始化
graph_retriever = GraphRetriever(
    enable_entity_extraction=True,
    max_entities=5,
    relation_depth=2
)

# 2. 图谱检索
results = graph_retriever.search(
    query="KL-1 梁使用什么材料？",
    top_k=5
)

for result in results:
    print(f"实体: {result['entity']}")
    print(f"关系: {result['relations']}")
    print(f"上下文: {result.get('context', '')}")
    print("---")

# 3. 获取子图
subgraph = graph_retriever.get_entity_subgraph(
    entity_id="comp_xxx",
    depth=2
)
print(f"中心节点: {subgraph['center_node']}")
print(f"关联节点数: {len(subgraph['nodes'])}")

# 4. 查找路径
paths = graph_retriever.find_path(
    from_entity_id="comp_001",
    to_entity_id="mat_001"
)
for path in paths:
    print(f"路径长度: {path['length']}")
"""
