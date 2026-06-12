"""知识图谱域服务：经 GraphRepository 收口图查询，Neo4j 不可用统一降级为 503。"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ServiceUnavailableError
from core.logger import logger
from repository.graph_repo import GraphRepository
from services.graph.neo4j_client import NEO4J_AVAILABLE, neo4j_client

# 可视化节点分类（标签 → 索引/颜色），消费方按 category 着色
_VIZ_CATEGORIES = [
    {"name": "Document", "itemStyle": {"color": "#1f6feb"}},
    {"name": "Component", "itemStyle": {"color": "#2da44e"}},
    {"name": "Material", "itemStyle": {"color": "#d29922"}},
    {"name": "Specification", "itemStyle": {"color": "#cf222e"}},
    {"name": "Dimension", "itemStyle": {"color": "#2dd4bf"}},
]
_LABEL_TO_CATEGORY = {c["name"]: i for i, c in enumerate(_VIZ_CATEGORIES)}


class GraphService:
    """图谱业务编排：构造注入 db，内部惰性持有 GraphRepository。

    降级策略：Neo4j 包缺失或连接不可用 → 抛 ServiceUnavailableError；
    资源不存在 → NotFoundError；绝不返回假数据。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = GraphRepository()

    # =========================================
    # 可用性守卫
    # =========================================

    def _ensure_available(self) -> None:
        """连接前置校验：包未装或 ping 失败即降级。"""
        if not NEO4J_AVAILABLE:
            raise ServiceUnavailableError("Neo4j 驱动未安装，图谱服务不可用")
        if not neo4j_client.ping():
            raise ServiceUnavailableError("Neo4j 连接不可用，图谱服务降级")

    def _guard(self, action: str, fn, *args, **kwargs):
        """执行图操作，连接类异常统一翻译为 503。"""
        self._ensure_available()
        try:
            return fn(*args, **kwargs)
        except (ServiceUnavailableError, NotFoundError):
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"图谱操作失败[{action}]: {e}", exc_info=True)
            raise ServiceUnavailableError(f"图谱操作失败: {action}", detail=str(e))

    # =========================================
    # 统计
    # =========================================

    def get_statistics(self, doc_id: Optional[str] = None) -> dict:
        """全局或单文档图谱统计。"""
        stats = self._guard("statistics", self.repo.get_graph_statistics, doc_id)
        if doc_id:
            return stats or {"doc_id": doc_id}
        return {
            "total_nodes": stats.get("total_nodes", 0),
            "total_relationships": stats.get("total_relationships", 0),
            "node_labels": stats.get("node_labels", {}),
            "relationship_types": stats.get("relationship_types", {}),
        }

    # =========================================
    # 文档子图
    # =========================================

    def get_document_graph(self, document_id: str) -> dict:
        """文档完整子图（节点 + 关系 + 计数）。"""
        data = self._guard("document_graph", self.repo.get_document_graph, document_id)
        nodes = [n for n in data.get("nodes", []) if n]
        rels = [r for r in data.get("relationships", []) if r]
        relationships = [
            {
                "id": r.get("id", ""),
                "from_node_id": r.get("from_node_id", ""),
                "to_node_id": r.get("to_node_id", ""),
                "rel_type": r.get("type", ""),
                "properties": r.get("properties", {}),
            }
            for r in rels
        ]
        normalized_nodes = [
            {
                "id": n.get("id", ""),
                "label": n.get("label", "Unknown"),
                "properties": n.get("properties", {}),
            }
            for n in nodes
        ]
        return {
            "document_id": document_id,
            "nodes": normalized_nodes,
            "relationships": relationships,
            "statistics": {"nodes": len(normalized_nodes), "relationships": len(relationships)},
        }

    def get_visualization_data(self, document_id: str, max_nodes: int = 100) -> dict:
        """ECharts 关系图数据（nodes/edges/categories）。"""
        data = self._guard("visualization", self.repo.get_document_graph, document_id)

        nodes: list[dict] = []
        node_ids: set = set()

        doc = data.get("document")
        if doc:
            doc_props = doc.get("properties", {})
            doc_id_val = doc.get("id") or document_id
            nodes.append({
                "id": doc_id_val,
                "name": doc_props.get("name", document_id),
                "category": 0,
                "symbolSize": 40,
                "value": doc_id_val,
            })
            node_ids.add(doc_id_val)

        for node in [n for n in data.get("nodes", []) if n][:max_nodes]:
            node_id_val = node.get("id", "")
            if not node_id_val or node_id_val in node_ids:
                continue
            label = node.get("label", "Unknown")
            props = node.get("properties", {})
            nodes.append({
                "id": node_id_val,
                "name": props.get("code", props.get("name", str(node_id_val)[:8])),
                "category": _LABEL_TO_CATEGORY.get(label, 1),
                "symbolSize": 20,
                "value": str(node_id_val),
            })
            node_ids.add(node_id_val)

        edges = []
        for rel in [r for r in data.get("relationships", []) if r]:
            source = rel.get("from_node_id", "")
            target = rel.get("to_node_id", "")
            if source in node_ids and target in node_ids:
                edges.append({"source": source, "target": target, "value": rel.get("type", "")})

        return {"nodes": nodes, "edges": edges, "categories": _VIZ_CATEGORIES}

    def delete_document_graph(self, document_id: str) -> dict:
        """删除文档子图全部节点与关系。"""
        result = self._guard("delete_document_graph", self.repo.clear_document_graph, document_id)
        return {"document_id": document_id, "deleted": result}

    # =========================================
    # 构件
    # =========================================

    def list_components(
        self,
        component_type: Optional[str] = None,
        document_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """构件分页列表（按类型/文档过滤）。"""
        limit = page_size * page
        if component_type:
            rows = self._guard(
                "list_components",
                self.repo.find_components_by_type,
                component_type,
                document_id,
                limit,
            )
        else:
            rows = self._guard(
                "list_components",
                self._find_all_components,
                document_id,
                limit,
            )

        start = (page - 1) * page_size
        items = [self._node_to_component(row.get("c", {})) for row in rows[start:start + page_size]]
        return {"items": items, "total": len(rows), "page": page, "page_size": page_size}

    def _find_all_components(self, document_id: Optional[str], limit: int) -> list:
        """无类型限定的全量构件查询。"""
        query = "MATCH (c:Component) "
        params: dict[str, Any] = {"limit": limit}
        if document_id:
            query += "WHERE c.doc_id = $doc_id "
            params["doc_id"] = document_id
        query += "RETURN c LIMIT $limit"
        return self.repo.client.execute_query(query, params)

    @staticmethod
    def _node_to_component(node: dict) -> dict:
        return {
            "id": node.get("id", ""),
            "code": node.get("code", ""),
            "type": node.get("type", ""),
            "properties": dict(node),
        }

    def get_component_detail(self, component_id: str) -> dict:
        """构件详情：材料/尺寸/规范/连接构件。"""
        data = self._guard("component_detail", self.repo.get_component_with_relations, component_id)
        component = data.get("component") if data else None
        if not component:
            raise NotFoundError(f"构件不存在: {component_id}")

        def _nodes(key: str, label: str) -> list:
            return [
                {"id": n.get("id", ""), "label": label, "properties": dict(n)}
                for n in data.get(key, []) if n
            ]

        return {
            "component": {"id": component.get("id", ""), "label": "Component", "properties": dict(component)},
            "materials": _nodes("materials", "Material"),
            "dimensions": _nodes("dimensions", "Dimension"),
            "specifications": _nodes("specifications", "Specification"),
            "connected_components": _nodes("connected_components", "Component"),
        }

    def get_component_by_code(self, code: str, document_id: Optional[str] = None) -> dict:
        """按编号查询单个构件。"""
        component = self._guard("component_by_code", self.repo.find_component_by_code, code, document_id)
        if not component:
            raise NotFoundError(f"构件不存在: {code}")
        return self._node_to_component(component)

    # =========================================
    # 材料 / 规范
    # =========================================

    def list_materials(
        self,
        grade: Optional[str] = None,
        document_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """材料分页列表（按等级过滤）。"""
        limit = page_size * page
        if grade:
            rows = self._guard("list_materials", self.repo.find_materials_by_grade, grade, limit)
        else:
            rows = self._guard("list_materials", self._find_all_materials, document_id, limit)

        start = (page - 1) * page_size
        items = []
        for row in rows[start:start + page_size]:
            node = row.get("m", row.get("n", {}))
            items.append({
                "id": node.get("id", ""),
                "type": node.get("type", ""),
                "grade": node.get("grade", ""),
                "properties": dict(node),
            })
        return {"items": items, "total": len(rows), "page": page, "page_size": page_size}

    def _find_all_materials(self, document_id: Optional[str], limit: int) -> list:
        query = "MATCH (m:Material) "
        params: dict[str, Any] = {"limit": limit}
        if document_id:
            query += "WHERE m.doc_id = $doc_id "
            params["doc_id"] = document_id
        query += "RETURN m LIMIT $limit"
        return self.repo.client.execute_query(query, params)

    def list_specifications(self, page: int = 1, page_size: int = 20) -> dict:
        """规范分页列表。"""
        limit = page_size * page
        rows = self._guard("list_specifications", self._find_specifications, limit)
        start = (page - 1) * page_size
        items = []
        for row in rows[start:start + page_size]:
            node = row.get("s", {})
            items.append({
                "id": node.get("id", ""),
                "code": node.get("code", ""),
                "name": node.get("name", ""),
                "properties": dict(node),
            })
        return {"items": items, "total": len(rows), "page": page, "page_size": page_size}

    def _find_specifications(self, limit: int) -> list:
        return self.repo.client.execute_query(
            "MATCH (s:Specification) RETURN s LIMIT $limit", {"limit": limit}
        )

    def get_documents_by_specification(self, spec_code: str) -> dict:
        """查引用指定规范的文档及其构件数。"""
        results = self._guard("docs_by_spec", self.repo.search_by_specification, spec_code)
        documents = []
        for item in results:
            doc = item.get("document", {}) or {}
            components = item.get("components", []) or []
            documents.append({
                "document": {
                    "id": doc.get("id", ""),
                    "name": doc.get("name", ""),
                    "properties": dict(doc) if doc else {},
                },
                "components_count": len([c for c in components if c]),
            })
        return {"spec_code": spec_code, "items": documents, "total": len(documents)}

    # =========================================
    # 关系 / 连接
    # =========================================

    def list_relations(
        self,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
        rel_type: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """关系列表（起止标签 + 类型过滤）。"""
        rows = self._guard(
            "list_relations",
            self.repo.client.find_relationships,
            from_label,
            to_label,
            rel_type,
            limit,
        )
        items = [
            {
                "from_node": dict(row.get("a", {})) if row.get("a") else None,
                "relation": dict(row.get("r", {})) if row.get("r") else None,
                "to_node": dict(row.get("b", {})) if row.get("b") else None,
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

    def get_connected_nodes(self, node_id: str, depth: int = 2) -> dict:
        """多层连接构件遍历。"""
        rows = self._guard("connected_nodes", self.repo.find_related_components, node_id, depth)
        items = []
        for item in rows:
            node = item.get("related", {})
            if node:
                items.append(self._node_to_component(node))
        return {
            "source_node_id": node_id,
            "depth": depth,
            "connected_count": len(items),
            "items": items,
        }

    # =========================================
    # 搜索
    # =========================================

    def search(self, query: str, node_types: Optional[list[str]] = None, limit: int = 20) -> dict:
        """关键词图谱搜索（属性正则匹配）。"""
        rows = self._guard("search", self._run_search, query, node_types, limit)
        nodes = []
        for item in rows:
            node = item.get("n", {})
            labels = item.get("labels", [])
            nodes.append({
                "id": node.get("id", ""),
                "label": labels[0] if labels else "Unknown",
                "properties": dict(node),
            })
        return {"query": query, "items": nodes, "total": len(nodes)}

    def _run_search(self, keyword: str, node_types: Optional[list[str]], limit: int) -> list:
        params = {"keyword": f".*{keyword}.*", "limit": limit}
        if node_types:
            parts = [
                f"""
                MATCH (n:{nt})
                WHERE any(key in keys(n) WHERE toString(n[key]) =~ $keyword)
                RETURN n, labels(n) as labels
                """
                for nt in node_types
            ]
            cypher = " UNION ".join(parts) + " LIMIT $limit"
        else:
            cypher = """
                MATCH (n)
                WHERE any(key in keys(n) WHERE toString(n[key]) =~ $keyword)
                RETURN n, labels(n) as labels
                LIMIT $limit
            """
        return self.repo.client.execute_query(cypher, params)

    # =========================================
    # 健康
    # =========================================

    def health(self) -> dict:
        """图数据库连接探测（不抛异常，供前端展示）。"""
        connected = NEO4J_AVAILABLE and neo4j_client.ping()
        return {
            "connected": connected,
            "database": "Neo4j",
            "status": "healthy" if connected else "disconnected",
        }
