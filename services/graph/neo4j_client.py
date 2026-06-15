"""
========================================
Neo4j 图数据库客户端
========================================

📚 模块说明：
- 封装 Neo4j 的所有连接和操作
- 提供连接池管理
- 实现单例模式

🎯 核心功能：
1. Neo4j 连接池管理
2. 基本图操作（节点、关系的 CRUD）
3. Cypher 查询执行
4. 事务管理

🔧 使用方式：
    from services.graph import neo4j_client

    # 执行查询
    result = neo4j_client.execute_query("MATCH (n) RETURN n LIMIT 10")

    # 创建节点
    neo4j_client.create_node(["Component"], {"code": "KL-1", "type": "beam"})

========================================
"""
from typing import Optional, Any, List, Dict, Union, Callable
from contextlib import contextmanager

from core.config import settings
from core.logger import logger

# 延迟导入 neo4j，避免未安装时报错
try:
    from neo4j import GraphDatabase, Driver, Session, Result
    from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j 包未安装，Neo4j 功能将不可用。请运行: uv add neo4j")


class Neo4jClient:
    """
    Neo4j 图数据库客户端

    🎯 职责：
    - 管理 Neo4j 连接池
    - 提供图操作接口
    - 实现 Cypher 查询

    💡 设计理念：
    - 单例模式：全局共享一个连接池
    - 事务支持：保证数据一致性
    - 自动重连：处理连接异常
    """

    _instance = None
    _driver: Optional[Any] = None
    _initialized: bool = False

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化客户端"""
        if self._initialized:
            return
        self._initialized = True

        if not NEO4J_AVAILABLE:
            logger.warning("Neo4j 客户端初始化跳过：neo4j 包未安装")
            return

        if settings.NEO4J_PASSWORD:
            self._init_driver()
        else:
            logger.info("Neo4j 密码未配置，延迟初始化连接")

    def _init_driver(self):
        """初始化 Neo4j 驱动"""
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j 包未安装，请运行: uv add neo4j")

        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
                max_transaction_retry_time=settings.NEO4J_MAX_TRANSACTION_RETRY_TIME
            )
            # 验证连接
            self._driver.verify_connectivity()
            logger.info(f"Neo4j 连接初始化成功: {settings.NEO4J_URI}")
        except AuthError as e:
            logger.error(f"Neo4j 认证失败: {str(e)}")
            raise
        except ServiceUnavailable as e:
            logger.error(f"Neo4j 服务不可用: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Neo4j 连接失败: {str(e)}")
            raise

    def ensure_connected(self):
        """确保已连接"""
        if self._driver is None:
            if not settings.NEO4J_PASSWORD:
                raise RuntimeError("Neo4j 密码未配置，请在 .env 中设置 NEO4J_PASSWORD")
            self._init_driver()

    @contextmanager
    def get_session(self, database: str = None):
        """
        获取数据库会话（上下文管理器）

        用法：
            with neo4j_client.get_session() as session:
                result = session.run("MATCH (n) RETURN n")
        """
        self.ensure_connected()
        db = database or settings.NEO4J_DATABASE
        session = self._driver.session(database=db)
        try:
            yield session
        finally:
            session.close()

    def execute_query(
        self,
        query: str,
        parameters: Dict = None,
        database: str = None
    ) -> List[Dict]:
        """
        执行 Cypher 查询

        参数：
            query: Cypher 查询语句
            parameters: 查询参数
            database: 数据库名

        返回：
            List[Dict]: 查询结果列表

        示例：
            results = neo4j_client.execute_query(
                "MATCH (n:Component) WHERE n.type = $type RETURN n",
                {"type": "beam"}
            )
        """
        self.ensure_connected()
        with self.get_session(database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(
        self,
        query: str,
        parameters: Dict = None,
        database: str = None
    ) -> Dict:
        """
        执行写入操作（带事务）

        返回：
            Dict: 写入结果摘要
        """
        self.ensure_connected()

        def _write_tx(tx, query: str, parameters: Dict):
            result = tx.run(query, parameters or {})
            summary = result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
                "labels_added": summary.counters.labels_added,
            }

        with self.get_session(database) as session:
            return session.execute_write(_write_tx, query, parameters or {})

    def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any]
    ) -> Dict:
        """
        创建节点

        参数：
            labels: 节点标签列表，如 ["Component", "Beam"]
            properties: 节点属性字典

        返回：
            Dict: 创建结果

        示例：
            neo4j_client.create_node(
                ["Component"],
                {"code": "KL-1", "type": "beam", "name": "框架梁"}
            )
        """
        labels_str = ":".join(labels)
        query = f"CREATE (n:{labels_str} $props) RETURN n"
        return self.execute_write(query, {"props": properties})

    def create_relationship(
        self,
        from_node_match: Dict[str, Any],
        to_node_match: Dict[str, Any],
        rel_type: str,
        properties: Dict[str, Any] = None
    ) -> Dict:
        """
        创建关系

        参数：
            from_node_match: 起始节点匹配条件，如 {"label": "Component", "props": {"id": "xxx"}}
            to_node_match: 目标节点匹配条件
            rel_type: 关系类型，如 "USES_MATERIAL"
            properties: 关系属性

        返回：
            Dict: 创建结果
        """
        from_label = from_node_match.get("label", "")
        from_props = from_node_match.get("props", {})
        to_label = to_node_match.get("label", "")
        to_props = to_node_match.get("props", {})

        # 构建 WHERE 条件
        from_conditions = " AND ".join([f"a.{k} = $from_{k}" for k in from_props.keys()])
        to_conditions = " AND ".join([f"b.{k} = $to_{k}" for k in to_props.keys()])

        query = f"""
        MATCH (a:{from_label}), (b:{to_label})
        WHERE {from_conditions} AND {to_conditions}
        CREATE (a)-[r:{rel_type} $rel_props]->(b)
        RETURN r
        """

        params = {"rel_props": properties or {}}
        params.update({f"from_{k}": v for k, v in from_props.items()})
        params.update({f"to_{k}": v for k, v in to_props.items()})

        return self.execute_write(query, params)

    def find_nodes(
        self,
        label: str,
        properties: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查找节点

        参数：
            label: 节点标签
            properties: 过滤条件
            limit: 返回数量限制

        返回：
            List[Dict]: 节点列表
        """
        if properties:
            conditions = " AND ".join([f"n.{k} = ${k}" for k in properties.keys()])
            query = f"MATCH (n:{label}) WHERE {conditions} RETURN n LIMIT $limit"
            params = {**properties, "limit": limit}
        else:
            query = f"MATCH (n:{label}) RETURN n LIMIT $limit"
            params = {"limit": limit}

        return self.execute_query(query, params)

    def find_relationships(
        self,
        from_label: str = None,
        to_label: str = None,
        rel_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查找关系

        参数：
            from_label: 起始节点标签
            to_label: 目标节点标签
            rel_type: 关系类型
            limit: 返回数量限制

        返回：
            List[Dict]: 关系列表
        """
        from_part = f"(a:{from_label})" if from_label else "(a)"
        to_part = f"(b:{to_label})" if to_label else "(b)"
        rel_part = f"[r:{rel_type}]" if rel_type else "[r]"

        query = f"""
        MATCH {from_part}-{rel_part}->{to_part}
        RETURN a, r, b
        LIMIT $limit
        """

        return self.execute_query(query, {"limit": limit})

    def delete_node(self, label: str, properties: Dict[str, Any]) -> Dict:
        """
        删除节点（同时删除相关关系）

        参数：
            label: 节点标签
            properties: 匹配条件

        返回：
            Dict: 删除结果
        """
        conditions = " AND ".join([f"n.{k} = ${k}" for k in properties.keys()])
        query = f"MATCH (n:{label}) WHERE {conditions} DETACH DELETE n"
        return self.execute_write(query, properties)

    def delete_all_nodes(self, label: str = None) -> Dict:
        """
        删除所有节点（谨慎使用）

        参数：
            label: 可选，指定标签

        返回：
            Dict: 删除结果
        """
        if label:
            query = f"MATCH (n:{label}) DETACH DELETE n"
        else:
            query = "MATCH (n) DETACH DELETE n"
        return self.execute_write(query)

    def get_node_count(self, label: str = None) -> int:
        """获取节点数量"""
        if label:
            query = f"MATCH (n:{label}) RETURN count(n) as count"
        else:
            query = "MATCH (n) RETURN count(n) as count"

        result = self.execute_query(query)
        return result[0]["count"] if result else 0

    def get_relationship_count(self, rel_type: str = None) -> int:
        """获取关系数量"""
        if rel_type:
            query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
        else:
            query = "MATCH ()-[r]->() RETURN count(r) as count"

        result = self.execute_query(query)
        return result[0]["count"] if result else 0

    def get_statistics(self) -> Dict:
        """
        获取图数据库统计信息

        返回：
            Dict: 包含节点和关系的统计信息
        """
        stats = {
            "total_nodes": self.get_node_count(),
            "total_relationships": self.get_relationship_count(),
            "node_labels": {},
            "relationship_types": {},
        }

        # 获取各标签节点数
        labels_query = "CALL db.labels() YIELD label RETURN label"
        labels = self.execute_query(labels_query)
        for item in labels:
            label = item["label"]
            stats["node_labels"][label] = self.get_node_count(label)

        # 获取各类型关系数
        types_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        types = self.execute_query(types_query)
        for item in types:
            rel_type = item["relationshipType"]
            stats["relationship_types"][rel_type] = self.get_relationship_count(rel_type)

        return stats

    def ping(self) -> bool:
        """
        测试连接

        返回：
            bool: 连接是否正常
        """
        if not NEO4J_AVAILABLE:
            return False

        if self._driver is None:
            return False

        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._driver is not None and self.ping()

    def close(self):
        """关闭连接（仅由应用 shutdown 统一调用）"""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")


# =========================================
# 全局单例实例
# =========================================
neo4j_client = Neo4jClient()
