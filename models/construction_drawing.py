"""
========================================
施工图数据模型 (SQLAlchemy ORM)
========================================

📚 模块说明：
- 定义施工图相关的数据库表
- 存储施工图处理状态和结果
- 记录实体提取日志

🗃️ 表结构：
1. ConstructionDrawing - 施工图主表
2. DrawingEntity - 提取的实体记录
3. DrawingRelation - 提取的关系记录
4. DrawingProcessLog - 处理日志

========================================
"""
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean,
    ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from models.document import Base


class ProcessingStatus(enum.Enum):
    """处理状态枚举"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    PARTIAL = "partial"           # 部分完成


class DrawingCategory(enum.Enum):
    """图纸类别枚举"""
    STRUCTURAL = "structural"     # 结构图
    ARCHITECTURAL = "architectural"  # 建筑图
    MEP = "mep"                   # 机电图
    GENERAL = "general"           # 综合图
    OTHER = "other"               # 其他


class ConstructionDrawing(Base):
    """
    施工图主表

    📋 存储内容：
    - 施工图基本信息
    - 处理状态和进度
    - 提取结果统计
    """

    __tablename__ = "construction_drawings"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")

    # 关联文档 ID（可选，如果已在 documents 表中）
    document_id = Column(String(64), nullable=True, index=True, comment="关联文档ID")

    # 基本信息
    name = Column(String(255), nullable=False, comment="图纸名称")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")

    # 图纸信息
    drawing_number = Column(String(100), nullable=True, comment="图纸编号")
    category = Column(
        SQLEnum(DrawingCategory),
        default=DrawingCategory.OTHER,
        comment="图纸类别"
    )
    scale = Column(String(50), nullable=True, comment="比例")
    project_name = Column(String(255), nullable=True, comment="项目名称")
    project_id = Column(String(64), nullable=True, index=True, comment="项目ID")

    # 处理状态
    status = Column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        comment="处理状态"
    )
    progress = Column(Float, default=0.0, comment="处理进度(0-100)")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 提取统计
    total_pages = Column(Integer, default=0, comment="总页数")
    entities_count = Column(Integer, default=0, comment="提取的实体数量")
    relations_count = Column(Integer, default=0, comment="提取的关系数量")

    # Neo4j 同步状态
    neo4j_synced = Column(Boolean, default=False, comment="是否已同步到Neo4j")
    neo4j_doc_id = Column(String(64), nullable=True, comment="Neo4j中的文档节点ID")

    # 提取结果（JSON 格式存储）
    extracted_info = Column(JSON, nullable=True, comment="提取的图纸信息")
    extraction_config = Column(JSON, nullable=True, comment="提取配置")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    processed_at = Column(DateTime, nullable=True, comment="处理完成时间")

    # 关联关系
    entities = relationship("DrawingEntity", back_populates="drawing", cascade="all, delete-orphan")
    relations = relationship("DrawingRelation", back_populates="drawing", cascade="all, delete-orphan")
    process_logs = relationship("DrawingProcessLog", back_populates="drawing", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ConstructionDrawing(id={self.id}, name={self.name}, status={self.status})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "name": self.name,
            "file_path": self.file_path,
            "drawing_number": self.drawing_number,
            "category": self.category.value if self.category else None,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "total_pages": self.total_pages,
            "entities_count": self.entities_count,
            "relations_count": self.relations_count,
            "neo4j_synced": self.neo4j_synced,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class DrawingEntity(Base):
    """
    图纸实体表

    📋 存储内容：
    - 从图纸中提取的实体
    - 实体属性和位置信息
    """

    __tablename__ = "drawing_entities"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")

    # 关联图纸
    drawing_id = Column(Integer, ForeignKey("construction_drawings.id"), nullable=False, index=True)

    # 实体信息
    entity_id = Column(String(64), nullable=False, index=True, comment="实体唯一ID")
    entity_type = Column(String(50), nullable=False, index=True, comment="实体类型")
    entity_label = Column(String(100), nullable=True, comment="实体标签")

    # 实体内容
    code = Column(String(100), nullable=True, comment="编号(如KL-1)")
    name = Column(String(255), nullable=True, comment="名称")
    value = Column(String(255), nullable=True, comment="值")

    # 位置信息
    page_num = Column(Integer, default=1, comment="所在页码")
    position_x = Column(Float, nullable=True, comment="X坐标")
    position_y = Column(Float, nullable=True, comment="Y坐标")

    # 扩展属性
    properties = Column(JSON, nullable=True, comment="其他属性")

    # Neo4j 节点 ID
    neo4j_node_id = Column(String(64), nullable=True, comment="Neo4j节点ID")

    # 提取信息
    confidence = Column(Float, default=1.0, comment="提取置信度")
    source = Column(String(50), default="rule", comment="提取来源(rule/llm)")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    drawing = relationship("ConstructionDrawing", back_populates="entities")

    def __repr__(self):
        return f"<DrawingEntity(id={self.id}, type={self.entity_type}, code={self.code})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_label": self.entity_label,
            "code": self.code,
            "name": self.name,
            "value": self.value,
            "page_num": self.page_num,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source,
        }


class DrawingRelation(Base):
    """
    图纸关系表

    📋 存储内容：
    - 实体之间的关系
    - 关系属性
    """

    __tablename__ = "drawing_relations"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")

    # 关联图纸
    drawing_id = Column(Integer, ForeignKey("construction_drawings.id"), nullable=False, index=True)

    # 关系信息
    relation_id = Column(String(64), nullable=False, index=True, comment="关系唯一ID")
    relation_type = Column(String(50), nullable=False, index=True, comment="关系类型")

    # 关联实体
    from_entity_id = Column(String(64), nullable=False, comment="起始实体ID")
    to_entity_id = Column(String(64), nullable=False, comment="目标实体ID")

    # 扩展属性
    properties = Column(JSON, nullable=True, comment="关系属性")

    # 提取信息
    confidence = Column(Float, default=1.0, comment="提取置信度")
    source = Column(String(50), default="rule", comment="提取来源(rule/llm)")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    drawing = relationship("ConstructionDrawing", back_populates="relations")

    def __repr__(self):
        return f"<DrawingRelation(id={self.id}, type={self.relation_type})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source,
        }


class DrawingProcessLog(Base):
    """
    处理日志表

    📋 存储内容：
    - 处理过程日志
    - 错误记录
    """

    __tablename__ = "drawing_process_logs"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")

    # 关联图纸
    drawing_id = Column(Integer, ForeignKey("construction_drawings.id"), nullable=False, index=True)

    # 日志信息
    step = Column(String(50), nullable=False, comment="处理步骤")
    status = Column(String(20), nullable=False, comment="步骤状态")
    message = Column(Text, nullable=True, comment="日志消息")

    # 统计信息
    duration_ms = Column(Integer, nullable=True, comment="耗时(毫秒)")
    items_processed = Column(Integer, default=0, comment="处理项数")

    # 详细信息
    details = Column(JSON, nullable=True, comment="详细信息")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    drawing = relationship("ConstructionDrawing", back_populates="process_logs")

    def __repr__(self):
        return f"<DrawingProcessLog(id={self.id}, step={self.step}, status={self.status})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "items_processed": self.items_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
