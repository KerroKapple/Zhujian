"""
========================================
文档数据模型
========================================

📚 模块说明：
- 定义文档及其相关的数据库表结构
- 使用 SQLAlchemy ORM 进行数据库操作
- 包含文档、文档块、文档元数据等表

🎯 核心模型：
1. Document - 文档主表
2. DocumentChunk - 文档分块表
3. DocumentMetadata - 文档元数据表

========================================
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Text,
    Boolean, JSON, ForeignKey, Enum as SQLEnum, Float
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import uuid

from core.constants import DocumentType, DocumentStatus, PermissionLevel

# 创建基类
Base = declarative_base()


# =========================================
# 1. 文档主表
# =========================================
class Document(Base):
    """
    文档主表

    📋 存储内容：
    - 文档基本信息（ID、名称、类型）
    - 文档状态（处理中、已完成、失败）
    - 权限信息（权限级别、所属部门）
    - 文件信息（路径、大小、格式）

    🔗 关联关系：
    - 一对多：Document -> DocumentChunk（一个文档有多个文本块）
    - 一对一：Document -> DocumentMetadata（文档元数据）
    """
    __tablename__ = "documents"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="文档唯一ID"
    )

    # ===== 基本信息 =====
    name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="文档名称"
    )

    title = Column(
        String(500),
        nullable=True,
        comment="文档标题（从内容中提取）"
    )

    doc_type = Column(
        SQLEnum(DocumentType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=DocumentType.OTHER,
        index=True,
        comment="文档类型：standard/project/contract等"
    )

    # ===== 状态信息 =====
    status = Column(
        SQLEnum(DocumentStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
        comment="处理状态：pending/processing/completed/failed"
    )

    status_message = Column(
        Text,
        nullable=True,
        comment="状态说明（如失败原因）"
    )

    # ===== 文件信息 =====
    source_path = Column(
        String(500),
        nullable=False,
        comment="原始文件路径"
    )

    file_size = Column(
        Integer,
        nullable=True,
        comment="文件大小（字节）"
    )

    file_extension = Column(
        String(10),
        nullable=True,
        comment="文件扩展名（如.pdf, .docx）"
    )

    mime_type = Column(
        String(100),
        nullable=True,
        comment="MIME类型"
    )

    # ===== 权限信息 =====
    permission_level = Column(
        SQLEnum(PermissionLevel, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=PermissionLevel.INTERNAL,
        index=True,
        comment="权限级别：public/internal/confidential/restricted"
    )

    department = Column(
        String(100),
        nullable=True,
        index=True,
        comment="所属部门"
    )

    project_id = Column(
        String(50),
        nullable=True,
        index=True,
        comment="所属项目ID"
    )

    project_name = Column(
        String(200),
        nullable=True,
        comment="所属项目名称"
    )

    # ===== 处理信息 =====
    total_chunks = Column(
        Integer,
        default=0,
        comment="文本块总数"
    )

    total_pages = Column(
        Integer,
        nullable=True,
        comment="总页数"
    )

    processing_time = Column(
        Float,
        nullable=True,
        comment="处理耗时（秒）"
    )

    # ===== 向量信息 =====
    vector_collection = Column(
        String(100),
        nullable=True,
        index=True,
        comment="向量库集合名称（rag_standards/rag_projects/rag_contracts）"
    )

    embedding_model = Column(
        String(100),
        nullable=True,
        comment="使用的Embedding模型名称"
    )

    # ===== 元数据 =====
    author = Column(
        String(100),
        nullable=True,
        comment="作者"
    )

    version = Column(
        String(50),
        nullable=True,
        comment="版本号"
    )

    tags = Column(
        JSON,
        nullable=True,
        comment="标签列表（JSON数组）"
    )

    extra_metadata = Column(
        JSON,
        nullable=True,
        comment="额外的元数据（JSON格式）"
    )

    # ===== 时间信息 =====
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )

    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="处理完成时间"
    )

    # ===== 上传信息 =====
    uploaded_by = Column(
        String(36),
        nullable=True,
        index=True,
        comment="上传用户ID"
    )

    # ===== 关联关系 =====
    # 一对多：一个文档有多个文本块
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    # 一对一：文档元数据
    doc_metadata = relationship(
        "DocumentMetadata",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document(id={self.id}, name={self.name}, status={self.status})>"

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "doc_type": self.doc_type.value if self.doc_type else None,
            "status": self.status.value if self.status else None,
            "status_message": self.status_message,
            "file_size": self.file_size,
            "file_extension": self.file_extension,
            "permission_level": self.permission_level.value if self.permission_level else None,
            "department": self.department,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "total_chunks": self.total_chunks,
            "total_pages": self.total_pages,
            "vector_collection": self.vector_collection,
            "author": self.author,
            "version": self.version,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "uploaded_by": self.uploaded_by,
        }


# =========================================
# 2. 文档分块表
# =========================================
class DocumentChunk(Base):
    """
    文档分块表

    📋 存储内容：
    - 文本块的内容
    - 文本块在文档中的位置
    - 向量ID（关联Milvus中的向量）

    💡 为什么需要分块？
    - 文档太长无法直接处理
    - 提高检索精度
    - 保留上下文信息
    """
    __tablename__ = "document_chunks"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="文本块唯一ID"
    )

    # ===== 外键：关联文档 =====
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属文档ID"
    )

    # ===== 文本内容 =====
    content = Column(
        Text,
        nullable=False,
        comment="文本块内容"
    )

    # ===== 位置信息 =====
    chunk_index = Column(
        Integer,
        nullable=False,
        comment="文本块在文档中的顺序（从0开始）"
    )

    page_num = Column(
        Integer,
        nullable=True,
        comment="所在页码"
    )

    start_char = Column(
        Integer,
        nullable=True,
        comment="在原文中的起始字符位置"
    )

    end_char = Column(
        Integer,
        nullable=True,
        comment="在原文中的结束字符位置"
    )

    # ===== 向量信息 =====
    vector_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Milvus向量ID"
    )

    vector_collection = Column(
        String(100),
        nullable=True,
        comment="向量所在的集合"
    )

    # ===== 统计信息 =====
    char_count = Column(
        Integer,
        nullable=True,
        comment="字符数"
    )

    token_count = Column(
        Integer,
        nullable=True,
        comment="Token数（用于计费和限制）"
    )

    # ===== 元数据 =====
    chunk_metadata = Column(
        JSON,
        nullable=True,
        comment="额外的元数据（JSON格式）"
    )

    # ===== 时间信息 =====
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间"
    )

    # ===== 关联关系 =====
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "page_num": self.page_num,
            "vector_id": self.vector_id,
            "vector_collection": self.vector_collection,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =========================================
# 3. 文档元数据表
# =========================================
class DocumentMetadata(Base):
    """
    文档元数据表

    📋 存储内容：
    - 文档的详细元数据
    - OCR识别信息
    - 处理过程中的统计数据

    💡 为什么单独存储？
    - 元数据可能很大（JSON格式）
    - 不影响主表查询性能
    - 方便扩展新字段
    """
    __tablename__ = "document_metadata"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="元数据ID"
    )

    # ===== 外键：关联文档 =====
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="所属文档ID"
    )

    # ===== OCR信息 =====
    is_scanned = Column(
        Boolean,
        default=False,
        comment="是否为扫描件"
    )

    ocr_confidence = Column(
        Float,
        nullable=True,
        comment="OCR识别置信度（0-1）"
    )

    ocr_language = Column(
        String(10),
        nullable=True,
        comment="OCR识别语言"
    )

    # ===== 提取的元数据 =====
    extracted_title = Column(
        String(500),
        nullable=True,
        comment="从文档中提取的标题"
    )

    extracted_author = Column(
        String(200),
        nullable=True,
        comment="从文档中提取的作者"
    )

    extracted_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="从文档中提取的日期"
    )

    extracted_keywords = Column(
        JSON,
        nullable=True,
        comment="提取的关键词列表"
    )

    # ===== 文档结构 =====
    has_table = Column(
        Boolean,
        default=False,
        comment="是否包含表格"
    )

    table_count = Column(
        Integer,
        default=0,
        comment="表格数量"
    )

    has_image = Column(
        Boolean,
        default=False,
        comment="是否包含图片"
    )

    image_count = Column(
        Integer,
        default=0,
        comment="图片数量"
    )

    # ===== 统计信息 =====
    word_count = Column(
        Integer,
        nullable=True,
        comment="总字数"
    )

    paragraph_count = Column(
        Integer,
        nullable=True,
        comment="段落数"
    )

    # ===== 完整元数据（JSON） =====
    raw_metadata = Column(
        JSON,
        nullable=True,
        comment="原始元数据（从文件中提取的所有元数据）"
    )

    processing_log = Column(
        JSON,
        nullable=True,
        comment="处理日志（记录处理过程）"
    )

    # ===== 时间信息 =====
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )

    # ===== 关联关系 =====
    document = relationship("Document", back_populates="doc_metadata")

    def __repr__(self):
        return f"<DocumentMetadata(id={self.id}, doc_id={self.document_id})>"

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "is_scanned": self.is_scanned,
            "ocr_confidence": self.ocr_confidence,
            "extracted_title": self.extracted_title,
            "extracted_author": self.extracted_author,
            "has_table": self.has_table,
            "table_count": self.table_count,
            "has_image": self.has_image,
            "image_count": self.image_count,
            "word_count": self.word_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 创建文档
from models.document import Document, DocumentChunk, DocumentMetadata
from core.constants import DocumentType, DocumentStatus, PermissionLevel

# 创建文档记录
doc = Document(
    name="GB50009-2012.pdf",
    title="建筑结构荷载规范",
    doc_type=DocumentType.STANDARD,
    status=DocumentStatus.PENDING,
    permission_level=PermissionLevel.PUBLIC,
    source_path="/data/raw_docs/GB50009-2012.pdf",
    file_size=2048000,
    file_extension=".pdf"
)

# 2. 添加文本块
chunk = DocumentChunk(
    document_id=doc.id,
    content="1.0.1 为了统一建筑结构荷载的取值...",
    chunk_index=0,
    page_num=1,
    char_count=150
)

# 3. 添加元数据
metadata = DocumentMetadata(
    document_id=doc.id,
    is_scanned=False,
    extracted_title="建筑结构荷载规范",
    word_count=50000
)

# 4. 保存到数据库
session.add(doc)
session.add(chunk)
session.add(metadata)
session.commit()
"""