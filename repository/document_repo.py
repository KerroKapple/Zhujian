"""
========================================
文档数据访问层 (Repository)
========================================

📚 模块说明：
- 封装所有文档相关的数据库操作
- 提供简洁的CRUD接口
- 处理事务和异常

🎯 核心功能：
1. 文档的增删改查
2. 文档分块管理
3. 文档元数据管理
4. 复杂查询和统计

========================================
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from datetime import datetime

from models.document import Document, DocumentChunk, DocumentMetadata
from core.constants import DocumentType, DocumentStatus, PermissionLevel
from core.logger import logger


class DocumentRepository:
    """
    文档数据访问类

    🎯 职责：
    - 管理文档的CRUD操作
    - 提供复杂查询接口
    - 处理文档和分块的关联
    """

    def __init__(self, session: Session):
        """
        初始化Repository

        参数：
            session: SQLAlchemy数据库会话
        """
        self.session = session

    # =========================================
    # 文档基本操作
    # =========================================

    def create_document(
            self,
            name: str,
            doc_type: DocumentType,
            source_path: str,
            **kwargs
    ) -> Document:
        """
        创建文档记录

        参数：
            name: 文档名称
            doc_type: 文档类型
            source_path: 文件路径
            **kwargs: 其他文档属性

        返回：
            Document: 创建的文档对象

        示例：
            doc = repo.create_document(
                name="GB50009-2012.pdf",
                doc_type=DocumentType.STANDARD,
                source_path="/data/raw_docs/GB50009-2012.pdf",
                permission_level=PermissionLevel.PUBLIC
            )
        """
        try:
            document = Document(
                name=name,
                doc_type=doc_type,
                source_path=source_path,
                **kwargs
            )

            self.session.add(document)
            self.session.commit()
            self.session.refresh(document)

            logger.info(f"创建文档成功: {document.id} - {document.name}")
            return document

        except Exception as e:
            self.session.rollback()
            logger.error(f"创建文档失败: {str(e)}")
            raise

    def get_document_by_id(
            self,
            doc_id: str,
            include_chunks: bool = False,
            include_metadata: bool = False
    ) -> Optional[Document]:
        """
        根据ID获取文档

        参数：
            doc_id: 文档ID
            include_chunks: 是否包含文档分块
            include_metadata: 是否包含元数据

        返回：
            Document: 文档对象，不存在则返回None
        """
        try:
            query = self.session.query(Document)

            # 根据需要加载关联数据
            if include_chunks:
                query = query.options(joinedload(Document.chunks))
            if include_metadata:
                query = query.options(joinedload(Document.doc_metadata))

            document = query.filter(Document.id == doc_id).first()
            return document

        except Exception as e:
            logger.error(f"获取文档失败: {str(e)}")
            raise

    def get_documents_by_ids(
            self,
            doc_ids: List[str]
    ) -> List[Document]:
        """
        批量获取文档

        参数：
            doc_ids: 文档ID列表

        返回：
            List[Document]: 文档列表
        """
        try:
            documents = self.session.query(Document).filter(
                Document.id.in_(doc_ids)
            ).all()
            return documents
        except Exception as e:
            logger.error(f"批量获取文档失败: {str(e)}")
            raise

    def update_document(
            self,
            doc_id: str,
            **kwargs
    ) -> Optional[Document]:
        """
        更新文档信息

        参数：
            doc_id: 文档ID
            **kwargs: 要更新的字段

        返回：
            Document: 更新后的文档对象

        示例：
            doc = repo.update_document(
                doc_id="doc_123",
                status=DocumentStatus.COMPLETED,
                total_chunks=10
            )
        """
        try:
            document = self.get_document_by_id(doc_id)
            if not document:
                logger.warning(f"文档不存在: {doc_id}")
                return None

            # 更新字段
            for key, value in kwargs.items():
                if hasattr(document, key):
                    setattr(document, key, value)

            self.session.commit()
            self.session.refresh(document)

            logger.info(f"更新文档成功: {doc_id}")
            return document

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新文档失败: {str(e)}")
            raise

    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档（级联删除关联的chunks和metadata）

        参数：
            doc_id: 文档ID

        返回：
            bool: 删除成功返回True，文档不存在返回False
        """
        try:
            document = self.get_document_by_id(doc_id)
            if not document:
                logger.warning(f"文档不存在: {doc_id}")
                return False

            self.session.delete(document)
            self.session.commit()

            logger.info(f"删除文档成功: {doc_id}")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"删除文档失败: {str(e)}")
            raise

    # =========================================
    # 文档查询
    # =========================================

    def list_documents(
            self,
            doc_type: Optional[DocumentType] = None,
            status: Optional[DocumentStatus] = None,
            permission_level: Optional[PermissionLevel] = None,
            department: Optional[str] = None,
            project_id: Optional[str] = None,
            skip: int = 0,
            limit: int = 20,
            order_by: str = "created_at",
            descending: bool = True
    ) -> List[Document]:
        """
        列出文档（支持多种过滤条件）

        参数：
            doc_type: 文档类型过滤
            status: 状态过滤
            permission_level: 权限级别过滤
            department: 部门过滤
            project_id: 项目ID过滤
            skip: 跳过的记录数（分页）
            limit: 返回的最大记录数
            order_by: 排序字段
            descending: 是否降序

        返回：
            List[Document]: 文档列表
        """
        try:
            query = self.session.query(Document)

            # 应用过滤条件
            if doc_type:
                query = query.filter(Document.doc_type == doc_type)
            if status:
                query = query.filter(Document.status == status)
            if permission_level:
                query = query.filter(Document.permission_level == permission_level)
            if department:
                query = query.filter(Document.department == department)
            if project_id:
                query = query.filter(Document.project_id == project_id)

            # 排序
            order_column = getattr(Document, order_by, Document.created_at)
            if descending:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(order_column)

            # 分页
            documents = query.offset(skip).limit(limit).all()

            return documents

        except Exception as e:
            logger.error(f"列出文档失败: {str(e)}")
            raise

    def count_documents(
            self,
            doc_type: Optional[DocumentType] = None,
            status: Optional[DocumentStatus] = None
    ) -> int:
        """
        统计文档数量

        参数：
            doc_type: 文档类型过滤
            status: 状态过滤

        返回：
            int: 文档数量
        """
        try:
            query = self.session.query(func.count(Document.id))

            if doc_type:
                query = query.filter(Document.doc_type == doc_type)
            if status:
                query = query.filter(Document.status == status)

            count = query.scalar()
            return count or 0

        except Exception as e:
            logger.error(f"统计文档数量失败: {str(e)}")
            raise

    def search_documents(
            self,
            keyword: str,
            skip: int = 0,
            limit: int = 20
    ) -> List[Document]:
        """
        搜索文档（按名称或标题）

        参数：
            keyword: 搜索关键词
            skip: 跳过的记录数
            limit: 返回的最大记录数

        返回：
            List[Document]: 匹配的文档列表
        """
        try:
            search_pattern = f"%{keyword}%"

            documents = self.session.query(Document).filter(
                or_(
                    Document.name.like(search_pattern),
                    Document.title.like(search_pattern)
                )
            ).offset(skip).limit(limit).all()

            return documents

        except Exception as e:
            logger.error(f"搜索文档失败: {str(e)}")
            raise

    # =========================================
    # 文档分块操作
    # =========================================

    def add_chunks(
            self,
            doc_id: str,
            chunks: List[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """
        批量添加文档分块

        参数：
            doc_id: 文档ID
            chunks: 分块数据列表，每个元素包含content、chunk_index等

        返回：
            List[DocumentChunk]: 创建的分块对象列表

        示例：
            chunks = [
                {"content": "第一段文本...", "chunk_index": 0, "page_num": 1},
                {"content": "第二段文本...", "chunk_index": 1, "page_num": 1},
            ]
            created_chunks = repo.add_chunks("doc_123", chunks)
        """
        try:
            chunk_objects = []

            for chunk_data in chunks:
                chunk = DocumentChunk(
                    document_id=doc_id,
                    **chunk_data
                )
                chunk_objects.append(chunk)

            self.session.bulk_save_objects(chunk_objects)
            self.session.commit()

            # 更新文档的总分块数
            self.update_document(doc_id, total_chunks=len(chunks))

            logger.info(f"添加文档分块成功: {doc_id}, 数量: {len(chunks)}")
            return chunk_objects

        except Exception as e:
            self.session.rollback()
            logger.error(f"添加文档分块失败: {str(e)}")
            raise

    def get_chunks_by_document(
            self,
            doc_id: str
    ) -> List[DocumentChunk]:
        """
        获取文档的所有分块

        参数：
            doc_id: 文档ID

        返回：
            List[DocumentChunk]: 分块列表（按chunk_index排序）
        """
        try:
            chunks = self.session.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc_id
            ).order_by(DocumentChunk.chunk_index).all()

            return chunks

        except Exception as e:
            logger.error(f"获取文档分块失败: {str(e)}")
            raise

    def update_chunk_vector_id(
            self,
            chunk_id: str,
            vector_id: str,
            vector_collection: str
    ) -> Optional[DocumentChunk]:
        """
        更新分块的向量ID

        参数：
            chunk_id: 分块ID
            vector_id: Milvus中的向量ID
            vector_collection: 向量所在的集合名称

        返回：
            DocumentChunk: 更新后的分块对象
        """
        try:
            chunk = self.session.query(DocumentChunk).filter(
                DocumentChunk.id == chunk_id
            ).first()

            if not chunk:
                logger.warning(f"分块不存在: {chunk_id}")
                return None

            chunk.vector_id = vector_id
            chunk.vector_collection = vector_collection

            self.session.commit()
            self.session.refresh(chunk)

            return chunk

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新分块向量ID失败: {str(e)}")
            raise

    # =========================================
    # 文档元数据操作
    # =========================================

    def create_metadata(
            self,
            doc_id: str,
            **kwargs
    ) -> DocumentMetadata:
        """
        创建文档元数据

        参数：
            doc_id: 文档ID
            **kwargs: 元数据字段

        返回：
            DocumentMetadata: 创建的元数据对象
        """
        try:
            metadata = DocumentMetadata(
                document_id=doc_id,
                **kwargs
            )

            self.session.add(metadata)
            self.session.commit()
            self.session.refresh(metadata)

            logger.info(f"创建文档元数据成功: {doc_id}")
            return metadata

        except Exception as e:
            self.session.rollback()
            logger.error(f"创建文档元数据失败: {str(e)}")
            raise

    def update_metadata(
            self,
            doc_id: str,
            **kwargs
    ) -> Optional[DocumentMetadata]:
        """
        更新文档元数据

        参数：
            doc_id: 文档ID
            **kwargs: 要更新的字段

        返回：
            DocumentMetadata: 更新后的元数据对象
        """
        try:
            metadata = self.session.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc_id
            ).first()

            if not metadata:
                # 如果元数据不存在，创建新的
                return self.create_metadata(doc_id, **kwargs)

            # 更新字段
            for key, value in kwargs.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)

            self.session.commit()
            self.session.refresh(metadata)

            return metadata

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新文档元数据失败: {str(e)}")
            raise

    # =========================================
    # 统计分析
    # =========================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取文档统计信息

        返回：
            Dict: 统计数据
        """
        try:
            stats = {
                "total_documents": self.count_documents(),
                "by_type": {},
                "by_status": {},
                "total_chunks": self.session.query(
                    func.count(DocumentChunk.id)
                ).scalar() or 0
            }

            # 按类型统计
            for doc_type in DocumentType:
                count = self.count_documents(doc_type=doc_type)
                stats["by_type"][doc_type.value] = count

            # 按状态统计
            for status in DocumentStatus:
                count = self.count_documents(status=status)
                stats["by_status"][status.value] = count

            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            raise


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 创建Repository实例
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from repository.document_repo import DocumentRepository

engine = create_engine("postgresql://user:pass@localhost/db")
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

repo = DocumentRepository(session)


# 2. 创建文档
from core.constants import DocumentType, PermissionLevel

doc = repo.create_document(
    name="GB50009-2012.pdf",
    doc_type=DocumentType.STANDARD,
    source_path="/data/raw_docs/GB50009-2012.pdf",
    permission_level=PermissionLevel.PUBLIC,
    department="工程部"
)


# 3. 添加文档分块
chunks_data = [
    {"content": "第一段内容...", "chunk_index": 0, "page_num": 1},
    {"content": "第二段内容...", "chunk_index": 1, "page_num": 1},
]
chunks = repo.add_chunks(doc.id, chunks_data)


# 4. 查询文档
documents = repo.list_documents(
    doc_type=DocumentType.STANDARD,
    status=DocumentStatus.COMPLETED,
    skip=0,
    limit=10
)


# 5. 搜索文档
results = repo.search_documents(keyword="防水")


# 6. 获取统计信息
stats = repo.get_statistics()
print(f"总文档数: {stats['total_documents']}")
print(f"总分块数: {stats['total_chunks']}")


# 7. 关闭会话
session.close()
"""