"""
========================================
施工图处理 API 接口
========================================

📚 模块说明：
- 施工图上传和解析
- 实体提取和关系构建
- 知识图谱同步
- 处理状态查询

🎯 核心功能：
1. 施工图上传和处理
2. 实体提取结果查询
3. 处理进度跟踪
4. 批量处理支持

========================================
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import os
import uuid

from core.config import settings
from core.logger import logger

router = APIRouter()


# =========================================
# 枚举定义
# =========================================

class DrawingType(str, Enum):
    """图纸类型"""
    STRUCTURAL = "structural"       # 结构图
    ARCHITECTURAL = "architectural" # 建筑图
    MEP = "mep"                     # 机电图
    OTHER = "other"                 # 其他


class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"             # 等待处理
    PARSING = "parsing"             # 解析中
    EXTRACTING = "extracting"       # 实体提取中
    SYNCING = "syncing"             # 同步图谱中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败


# =========================================
# 请求/响应模型
# =========================================

class DrawingUploadRequest(BaseModel):
    """施工图上传请求"""
    project_id: Optional[str] = Field(None, description="关联项目ID")
    drawing_type: Optional[DrawingType] = Field(DrawingType.OTHER, description="图纸类型")
    enable_ocr: bool = Field(True, description="是否启用OCR")
    sync_to_neo4j: bool = Field(True, description="是否同步到知识图谱")


class DrawingUploadResponse(BaseModel):
    """施工图上传响应"""
    success: bool = Field(True, description="是否成功")
    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    message: str = Field(..., description="提示信息")
    processing_url: str = Field(..., description="处理状态查询URL")


class DrawingInfo(BaseModel):
    """图纸信息"""
    drawing_number: str = Field("", description="图纸编号")
    drawing_name: str = Field("", description="图纸名称")
    scale: str = Field("", description="比例")
    project_name: str = Field("", description="工程名称")
    designer: str = Field("", description="设计人")


class EntitySummary(BaseModel):
    """实体摘要"""
    components: int = Field(0, description="构件数量")
    materials: int = Field(0, description="材料数量")
    dimensions: int = Field(0, description="尺寸数量")
    specifications: int = Field(0, description="规范引用数量")
    annotations: int = Field(0, description="标注数量")


class ProcessingProgress(BaseModel):
    """处理进度"""
    document_id: str = Field(..., description="文档ID")
    status: ProcessingStatus = Field(..., description="处理状态")
    progress: float = Field(..., description="进度(0-100)")
    current_step: str = Field(..., description="当前步骤")
    steps: List[Dict] = Field(default=[], description="步骤详情")
    error_message: Optional[str] = Field(None, description="错误信息")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")


class ProcessingResult(BaseModel):
    """处理结果"""
    success: bool = Field(..., description="是否成功")
    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    drawing_info: Optional[DrawingInfo] = Field(None, description="图纸信息")
    entities: EntitySummary = Field(..., description="实体统计")
    relations_count: int = Field(0, description="关系数量")
    neo4j_synced: bool = Field(False, description="是否已同步图谱")
    processing_time_ms: int = Field(0, description="处理耗时(毫秒)")
    steps: List[Dict] = Field(default=[], description="处理步骤详情")


class ExtractedEntity(BaseModel):
    """提取的实体"""
    id: str = Field(..., description="实体ID")
    type: str = Field(..., description="实体类型")
    label: str = Field(..., description="实体标签")
    properties: Dict[str, Any] = Field(default={}, description="实体属性")
    confidence: float = Field(1.0, description="置信度")
    source: str = Field("rule", description="提取来源")


class ExtractedRelation(BaseModel):
    """提取的关系"""
    id: str = Field(..., description="关系ID")
    from_entity_id: str = Field(..., description="起始实体ID")
    to_entity_id: str = Field(..., description="目标实体ID")
    relation_type: str = Field(..., description="关系类型")
    properties: Dict[str, Any] = Field(default={}, description="关系属性")


class DrawingEntitiesResponse(BaseModel):
    """图纸实体响应"""
    success: bool = Field(True, description="是否成功")
    document_id: str = Field(..., description="文档ID")
    drawing_info: Optional[DrawingInfo] = Field(None, description="图纸信息")
    entities: Dict[str, List[ExtractedEntity]] = Field(..., description="实体列表")
    relations: List[ExtractedRelation] = Field(default=[], description="关系列表")
    summary: EntitySummary = Field(..., description="实体统计")


# =========================================
# 内存存储（临时，实际应使用数据库）
# =========================================

_processing_tasks: Dict[str, Dict] = {}
_processing_results: Dict[str, Dict] = {}


# =========================================
# 施工图上传接口
# =========================================

@router.post(
    "/upload",
    response_model=DrawingUploadResponse,
    summary="上传施工图",
    description="上传施工图PDF并触发解析处理"
)
async def upload_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="施工图PDF文件"),
    project_id: Optional[str] = Query(None, description="关联项目ID"),
    drawing_type: DrawingType = Query(DrawingType.OTHER, description="图纸类型"),
    enable_ocr: bool = Query(True, description="是否启用OCR"),
    sync_to_neo4j: bool = Query(True, description="是否同步到知识图谱")
):
    """
    上传施工图接口

    支持的格式：
    - PDF (.pdf)

    处理流程：
    1. 验证文件格式
    2. 保存文件
    3. 异步处理（解析、实体提取、关系构建、图谱同步）
    4. 返回文档ID和状态查询URL
    """
    try:
        logger.info(f"收到施工图上传: {file.filename}")

        # 验证文件格式
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext != '.pdf':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"施工图仅支持PDF格式，收到: {file_ext}"
            )

        # 验证文件大小（限制100MB）
        max_size = 100 * 1024 * 1024  # 100MB
        file_size = 0

        # 生成文档ID
        document_id = f"drawing_{uuid.uuid4().hex[:12]}"

        # 保存文件
        upload_dir = settings.DATA_DIR / "raw_docs" / "drawings"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / f"{document_id}_{file.filename}"

        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                file_size += len(chunk)
                if file_size > max_size:
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件过大，限制{max_size // 1024 // 1024}MB"
                    )
                f.write(chunk)

        logger.info(
            f"施工图保存成功: {file.filename} | "
            f"大小: {file_size / 1024:.2f}KB | "
            f"document_id: {document_id}"
        )

        # 初始化处理状态
        _processing_tasks[document_id] = {
            "status": ProcessingStatus.PENDING,
            "progress": 0,
            "current_step": "等待处理",
            "steps": [],
            "started_at": datetime.now().isoformat(),
            "file_path": str(file_path),
            "filename": file.filename,
            "project_id": project_id,
            "drawing_type": drawing_type,
            "enable_ocr": enable_ocr,
            "sync_to_neo4j": sync_to_neo4j,
        }

        # 添加后台处理任务
        background_tasks.add_task(
            process_drawing_task,
            document_id,
            str(file_path),
            project_id,
            enable_ocr,
            sync_to_neo4j
        )

        return DrawingUploadResponse(
            success=True,
            document_id=document_id,
            filename=file.filename,
            message="施工图上传成功，正在后台处理",
            processing_url=f"/api/v1/drawing/{document_id}/status"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"施工图上传失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"施工图上传失败: {str(e)}"
        )


async def process_drawing_task(
    document_id: str,
    file_path: str,
    project_id: str,
    enable_ocr: bool,
    sync_to_neo4j: bool
):
    """
    后台处理施工图任务

    步骤：
    1. PDF解析
    2. 实体提取
    3. 关系提取
    4. Neo4j同步
    """
    try:
        from services.document.construction_drawing.drawing_processor import DrawingProcessor

        # 更新状态为处理中
        _processing_tasks[document_id]["status"] = ProcessingStatus.PARSING
        _processing_tasks[document_id]["progress"] = 10
        _processing_tasks[document_id]["current_step"] = "解析PDF文件"

        # 创建处理器
        processor = DrawingProcessor(
            enable_ocr=enable_ocr,
            use_llm=False,  # 暂不启用LLM增强
            sync_to_neo4j=sync_to_neo4j
        )

        # 进度回调
        def progress_callback(progress: float, message: str):
            _processing_tasks[document_id]["progress"] = progress
            _processing_tasks[document_id]["current_step"] = message

            # 根据进度更新状态
            if progress < 30:
                _processing_tasks[document_id]["status"] = ProcessingStatus.PARSING
            elif progress < 70:
                _processing_tasks[document_id]["status"] = ProcessingStatus.EXTRACTING
            elif progress < 100:
                _processing_tasks[document_id]["status"] = ProcessingStatus.SYNCING

        # 执行处理
        result = await processor.process(
            file_path=file_path,
            document_id=document_id,
            project_id=project_id,
            progress_callback=progress_callback
        )

        # 保存结果
        _processing_results[document_id] = result.to_dict()

        # 更新状态
        if result.success:
            _processing_tasks[document_id]["status"] = ProcessingStatus.COMPLETED
            _processing_tasks[document_id]["progress"] = 100
            _processing_tasks[document_id]["current_step"] = "处理完成"
        else:
            _processing_tasks[document_id]["status"] = ProcessingStatus.FAILED
            _processing_tasks[document_id]["error_message"] = result.error_message

        _processing_tasks[document_id]["completed_at"] = datetime.now().isoformat()
        _processing_tasks[document_id]["steps"] = result.steps

        logger.info(f"施工图处理完成: {document_id} | 成功: {result.success}")

    except Exception as e:
        logger.error(f"施工图处理失败: {document_id} | {e}", exc_info=True)
        _processing_tasks[document_id]["status"] = ProcessingStatus.FAILED
        _processing_tasks[document_id]["error_message"] = str(e)
        _processing_tasks[document_id]["completed_at"] = datetime.now().isoformat()


# =========================================
# 处理状态查询接口
# =========================================

@router.get(
    "/{document_id}/status",
    response_model=ProcessingProgress,
    summary="查询处理状态",
    description="查询施工图处理进度和状态"
)
async def get_processing_status(document_id: str):
    """
    查询施工图处理状态

    状态说明：
    - pending: 等待处理
    - parsing: 解析PDF中
    - extracting: 提取实体中
    - syncing: 同步图谱中
    - completed: 处理完成
    - failed: 处理失败
    """
    if document_id not in _processing_tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}"
        )

    task = _processing_tasks[document_id]

    return ProcessingProgress(
        document_id=document_id,
        status=task["status"],
        progress=task["progress"],
        current_step=task["current_step"],
        steps=task.get("steps", []),
        error_message=task.get("error_message"),
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at")
    )


# =========================================
# 处理结果查询接口
# =========================================

@router.get(
    "/{document_id}/result",
    response_model=ProcessingResult,
    summary="获取处理结果",
    description="获取施工图处理的完整结果"
)
async def get_processing_result(document_id: str):
    """
    获取施工图处理结果

    包含：
    - 图纸基本信息
    - 提取的实体统计
    - 关系数量
    - 处理步骤详情
    """
    if document_id not in _processing_tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}"
        )

    task = _processing_tasks[document_id]

    if task["status"] != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文档尚未处理完成，当前状态: {task['status']}"
        )

    if document_id not in _processing_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="处理结果不存在"
        )

    result = _processing_results[document_id]

    # 构建响应
    drawing_info = None
    if result.get("drawing_info"):
        drawing_info = DrawingInfo(**result["drawing_info"])

    return ProcessingResult(
        success=result["success"],
        document_id=result["document_id"],
        filename=task.get("filename", ""),
        drawing_info=drawing_info,
        entities=EntitySummary(
            components=result.get("entities_count", 0),
            materials=0,
            dimensions=0,
            specifications=0,
            annotations=0
        ),
        relations_count=result.get("relations_count", 0),
        neo4j_synced=result.get("neo4j_synced", False),
        processing_time_ms=result.get("processing_time_ms", 0),
        steps=result.get("steps", [])
    )


# =========================================
# 实体查询接口
# =========================================

@router.get(
    "/{document_id}/entities",
    response_model=DrawingEntitiesResponse,
    summary="获取提取的实体",
    description="获取施工图中提取的所有实体和关系"
)
async def get_drawing_entities(
    document_id: str,
    entity_type: Optional[str] = Query(None, description="筛选实体类型: component, material, dimension, specification")
):
    """
    获取施工图中提取的实体

    实体类型：
    - component: 构件（梁、柱、板、墙等）
    - material: 材料（混凝土、钢筋等）
    - dimension: 尺寸
    - specification: 规范引用
    """
    if document_id not in _processing_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在或尚未处理完成: {document_id}"
        )

    # 从图数据库查询实体
    try:
        from repository.graph_repo import GraphRepository
        graph_repo = GraphRepository()

        # 获取文档图谱
        graph_data = graph_repo.get_document_graph(document_id)

        # 转换为响应格式
        entities = {
            "components": [],
            "materials": [],
            "dimensions": [],
            "specifications": []
        }
        relations = []

        # 解析 graph_data，按节点标签分类填充 entities，并组装 relations
        label_to_key = {
            "Component": "components",
            "Material": "materials",
            "Dimension": "dimensions",
            "Specification": "specifications",
        }
        for node in graph_data.get("nodes", []):
            if not node:
                continue
            key = label_to_key.get(node.get("label"))
            if not key:
                continue
            if entity_type and key != f"{entity_type}s" and key != entity_type:
                continue
            item = dict(node.get("properties", {}))
            item.setdefault("id", node.get("id"))
            entities[key].append(item)

        for rel in graph_data.get("relationships", []):
            if not rel:
                continue
            relations.append({
                "id": rel.get("id"),
                "type": rel.get("type"),
                "from_node_id": rel.get("from_node_id"),
                "to_node_id": rel.get("to_node_id"),
                "properties": rel.get("properties", {}),
            })

        # 统计
        summary = EntitySummary(
            components=len(entities.get("components", [])),
            materials=len(entities.get("materials", [])),
            dimensions=len(entities.get("dimensions", [])),
            specifications=len(entities.get("specifications", [])),
            annotations=0
        )

        result = _processing_results.get(document_id, {})
        drawing_info = None
        if result.get("drawing_info"):
            drawing_info = DrawingInfo(**result["drawing_info"])

        return DrawingEntitiesResponse(
            success=True,
            document_id=document_id,
            drawing_info=drawing_info,
            entities=entities,
            relations=relations,
            summary=summary
        )

    except Exception as e:
        logger.error(f"获取实体失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取实体失败: {str(e)}"
        )


# =========================================
# 重新处理接口
# =========================================

@router.post(
    "/{document_id}/reprocess",
    summary="重新处理",
    description="重新处理施工图"
)
async def reprocess_drawing(
    document_id: str,
    background_tasks: BackgroundTasks,
    enable_ocr: bool = Query(True, description="是否启用OCR"),
    sync_to_neo4j: bool = Query(True, description="是否同步到知识图谱")
):
    """
    重新处理施工图

    会清除之前的处理结果并重新处理
    """
    if document_id not in _processing_tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}"
        )

    task = _processing_tasks[document_id]

    # 检查是否正在处理中
    if task["status"] in [ProcessingStatus.PARSING, ProcessingStatus.EXTRACTING, ProcessingStatus.SYNCING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档正在处理中，请稍后再试"
        )

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始文件不存在，无法重新处理"
        )

    # 清除图谱数据
    if sync_to_neo4j:
        try:
            from repository.graph_repo import GraphRepository
            graph_repo = GraphRepository()
            graph_repo.clear_document_graph(document_id)
            logger.info(f"已清除文档图谱数据: {document_id}")
        except Exception as e:
            logger.warning(f"清除图谱数据失败: {e}")

    # 重置状态
    _processing_tasks[document_id]["status"] = ProcessingStatus.PENDING
    _processing_tasks[document_id]["progress"] = 0
    _processing_tasks[document_id]["current_step"] = "等待处理"
    _processing_tasks[document_id]["error_message"] = None
    _processing_tasks[document_id]["started_at"] = datetime.now().isoformat()
    _processing_tasks[document_id]["completed_at"] = None

    # 清除旧结果
    if document_id in _processing_results:
        del _processing_results[document_id]

    # 添加后台任务
    background_tasks.add_task(
        process_drawing_task,
        document_id,
        file_path,
        task.get("project_id"),
        enable_ocr,
        sync_to_neo4j
    )

    return {
        "success": True,
        "message": "已开始重新处理",
        "document_id": document_id,
        "status_url": f"/api/v1/drawing/{document_id}/status"
    }


# =========================================
# 删除接口
# =========================================

@router.delete(
    "/{document_id}",
    summary="删除施工图",
    description="删除施工图及其关联的知识图谱数据"
)
async def delete_drawing(document_id: str):
    """
    删除施工图

    会删除：
    - 原始PDF文件
    - 处理记录
    - Neo4j图谱数据
    """
    if document_id not in _processing_tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}"
        )

    task = _processing_tasks[document_id]

    # 删除原始文件
    file_path = task.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"已删除文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")

    # 删除图谱数据
    try:
        from repository.graph_repo import GraphRepository
        graph_repo = GraphRepository()
        graph_repo.clear_document_graph(document_id)
        logger.info(f"已删除图谱数据: {document_id}")
    except Exception as e:
        logger.warning(f"删除图谱数据失败: {e}")

    # 删除记录
    del _processing_tasks[document_id]
    if document_id in _processing_results:
        del _processing_results[document_id]

    return {
        "success": True,
        "message": "施工图删除成功",
        "document_id": document_id
    }


# =========================================
# 列表查询接口
# =========================================

@router.get(
    "/list",
    summary="施工图列表",
    description="获取施工图处理列表"
)
async def list_drawings(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="状态筛选"),
    project_id: Optional[str] = Query(None, description="项目ID筛选")
):
    """
    获取施工图列表
    """
    # 筛选
    filtered = []
    for doc_id, task in _processing_tasks.items():
        if status_filter and task["status"] != status_filter:
            continue
        if project_id and task.get("project_id") != project_id:
            continue
        filtered.append({
            "document_id": doc_id,
            "filename": task.get("filename", ""),
            "status": task["status"],
            "progress": task["progress"],
            "project_id": task.get("project_id"),
            "drawing_type": task.get("drawing_type"),
            "started_at": task.get("started_at"),
            "completed_at": task.get("completed_at")
        })

    # 分页
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered[start:end]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "drawings": paginated
    }


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 上传施工图
curl -X POST "http://localhost:8000/api/v1/drawing/upload" \
  -F "file=@结构施工图.pdf" \
  -F "project_id=P001" \
  -F "drawing_type=structural"

# 2. 查询处理状态
curl "http://localhost:8000/api/v1/drawing/drawing_xxx/status"

# 3. 获取处理结果
curl "http://localhost:8000/api/v1/drawing/drawing_xxx/result"

# 4. 获取提取的实体
curl "http://localhost:8000/api/v1/drawing/drawing_xxx/entities"

# 5. 重新处理
curl -X POST "http://localhost:8000/api/v1/drawing/drawing_xxx/reprocess"

# 6. 删除施工图
curl -X DELETE "http://localhost:8000/api/v1/drawing/drawing_xxx"

# 7. 施工图列表
curl "http://localhost:8000/api/v1/drawing/list?page=1&page_size=20"
"""
