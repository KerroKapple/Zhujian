"""知识图谱 API：仅做入参校验 + 调 GraphService + 返回；错误经 core.exceptions。"""
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from core.deps import get_graph_service

router = APIRouter()


# =========================================
# 枚举
# =========================================

class NodeType(str, Enum):
    DOCUMENT = "Document"
    DRAWING = "Drawing"
    COMPONENT = "Component"
    MATERIAL = "Material"
    SPECIFICATION = "Specification"
    DIMENSION = "Dimension"
    LOCATION = "Location"
    ANNOTATION = "Annotation"


class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    USES_MATERIAL = "USES_MATERIAL"
    REFERS_TO = "REFERS_TO"
    HAS_DIMENSION = "HAS_DIMENSION"
    LOCATED_AT = "LOCATED_AT"
    CONNECTED_TO = "CONNECTED_TO"
    BELONGS_TO = "BELONGS_TO"


class ComponentType(str, Enum):
    BEAM = "beam"
    COLUMN = "column"
    SLAB = "slab"
    WALL = "wall"
    FOUNDATION = "foundation"
    STAIR = "stair"
    OTHER = "other"


# =========================================
# 请求模型
# =========================================

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    node_types: Optional[list[NodeType]] = Field(None, description="限定节点类型")
    limit: int = Field(20, ge=1, le=100, description="返回数量限制")


# =========================================
# 统计
# =========================================

@router.get("/statistics", summary="图谱统计", description="知识图谱整体统计信息")
async def get_graph_statistics(service=Depends(get_graph_service)) -> dict:
    return service.get_statistics()


# =========================================
# 文档子图
# =========================================

@router.get("/document/{document_id}", summary="文档图谱", description="指定文档的知识子图")
async def get_document_graph(document_id: str, service=Depends(get_graph_service)) -> dict:
    return service.get_document_graph(document_id)


@router.get("/document/{document_id}/statistics", summary="文档图谱统计")
async def get_document_statistics(document_id: str, service=Depends(get_graph_service)) -> dict:
    return service.get_statistics(doc_id=document_id)


@router.delete("/document/{document_id}", summary="删除文档图谱")
async def delete_document_graph(document_id: str, service=Depends(get_graph_service)) -> dict:
    result = service.delete_document_graph(document_id)
    return {"success": True, "message": "文档图谱删除成功", **result}


@router.get("/visualization/{document_id}", summary="可视化数据", description="ECharts 关系图数据")
async def get_visualization_data(
    document_id: str,
    max_nodes: int = Query(100, ge=10, le=500, description="最大节点数"),
    service=Depends(get_graph_service),
) -> dict:
    return service.get_visualization_data(document_id, max_nodes=max_nodes)


# =========================================
# 构件
# =========================================

@router.get("/components", summary="查询构件列表")
async def list_components(
    component_type: Optional[ComponentType] = Query(None, description="构件类型"),
    document_id: Optional[str] = Query(None, description="文档ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service=Depends(get_graph_service),
) -> dict:
    return service.list_components(
        component_type=component_type.value if component_type else None,
        document_id=document_id,
        page=page,
        page_size=page_size,
    )


@router.get("/component/{component_id}", summary="构件详情")
async def get_component_detail(component_id: str, service=Depends(get_graph_service)) -> dict:
    return service.get_component_detail(component_id)


@router.get("/component/code/{code}", summary="按编号查询构件")
async def get_component_by_code(
    code: str,
    document_id: Optional[str] = Query(None, description="文档ID"),
    service=Depends(get_graph_service),
) -> dict:
    return service.get_component_by_code(code, document_id=document_id)


# =========================================
# 材料 / 规范
# =========================================

@router.get("/materials", summary="查询材料列表")
async def list_materials(
    grade: Optional[str] = Query(None, description="材料等级，如 C30, HRB400"),
    document_id: Optional[str] = Query(None, description="文档ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service=Depends(get_graph_service),
) -> dict:
    return service.list_materials(
        grade=grade, document_id=document_id, page=page, page_size=page_size
    )


@router.get("/specifications", summary="查询规范列表")
async def list_specifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service=Depends(get_graph_service),
) -> dict:
    return service.list_specifications(page=page, page_size=page_size)


@router.get("/specification/{spec_code}/documents", summary="规范关联文档")
async def get_documents_by_specification(spec_code: str, service=Depends(get_graph_service)) -> dict:
    return service.get_documents_by_specification(spec_code)


# =========================================
# 关系 / 连接
# =========================================

@router.get("/relations", summary="查询关系")
async def list_relations(
    from_label: Optional[str] = Query(None, description="起始节点类型"),
    to_label: Optional[str] = Query(None, description="目标节点类型"),
    rel_type: Optional[RelationType] = Query(None, description="关系类型"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    service=Depends(get_graph_service),
) -> dict:
    return service.list_relations(
        from_label=from_label,
        to_label=to_label,
        rel_type=rel_type.value if rel_type else None,
        limit=limit,
    )


@router.get("/connected/{node_id}", summary="关联构件查询")
async def get_connected_nodes(
    node_id: str,
    depth: int = Query(2, ge=1, le=5, description="遍历深度"),
    service=Depends(get_graph_service),
) -> dict:
    return service.get_connected_nodes(node_id, depth=depth)


# =========================================
# 搜索
# =========================================

@router.post("/search", summary="图谱搜索")
async def search_graph(request: SearchRequest = Body(...), service=Depends(get_graph_service)) -> dict:
    node_types = [nt.value for nt in request.node_types] if request.node_types else None
    return service.search(request.query, node_types=node_types, limit=request.limit)


# =========================================
# 健康
# =========================================

@router.get("/health", summary="图数据库健康检查")
async def check_graph_health(service=Depends(get_graph_service)) -> dict:
    return service.health()
