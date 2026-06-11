"""
========================================
知识图谱数据模型 - 施工图领域
========================================

📚 模块说明：
- 定义知识图谱的节点和关系类型
- 提供领域专用的数据类
- 支持序列化和验证

🏗️ 节点类型（Labels）：
1. Document - 文档节点
2. Drawing - 图纸节点
3. Component - 构件节点（梁、柱、板、墙等）
4. Material - 材料节点（混凝土、钢筋等）
5. Specification - 规范节点
6. Dimension - 尺寸节点
7. Location - 位置节点
8. Annotation - 标注节点

🔗 关系类型（Relationships）：
1. CONTAINS - 包含关系
2. USES_MATERIAL - 使用材料
3. REFERS_TO - 引用规范
4. HAS_DIMENSION - 具有尺寸
5. LOCATED_AT - 位于位置
6. CONNECTED_TO - 连接关系
7. BELONGS_TO - 属于关系

========================================
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid


# =========================================
# 枚举类型定义
# =========================================

class NodeLabel(str, Enum):
    """节点标签枚举"""
    DOCUMENT = "Document"
    DRAWING = "Drawing"
    COMPONENT = "Component"
    MATERIAL = "Material"
    SPECIFICATION = "Specification"
    DIMENSION = "Dimension"
    LOCATION = "Location"
    ANNOTATION = "Annotation"
    SYMBOL = "Symbol"


class RelationType(str, Enum):
    """关系类型枚举"""
    CONTAINS = "CONTAINS"
    USES_MATERIAL = "USES_MATERIAL"
    REFERS_TO = "REFERS_TO"
    HAS_DIMENSION = "HAS_DIMENSION"
    LOCATED_AT = "LOCATED_AT"
    CONNECTED_TO = "CONNECTED_TO"
    BELONGS_TO = "BELONGS_TO"
    DERIVED_FROM = "DERIVED_FROM"
    ANNOTATES = "ANNOTATES"
    SPECIFIES = "SPECIFIES"


class ComponentType(str, Enum):
    """构件类型枚举"""
    # 结构构件
    BEAM = "beam"               # 梁
    COLUMN = "column"           # 柱
    SLAB = "slab"               # 板
    WALL = "wall"               # 墙
    FOUNDATION = "foundation"   # 基础
    STAIR = "stair"             # 楼梯
    SHEAR_WALL = "shear_wall"   # 剪力墙

    # 建筑构件
    WINDOW = "window"           # 窗
    DOOR = "door"               # 门
    CURTAIN_WALL = "curtain_wall"  # 幕墙

    # 机电构件
    PIPE = "pipe"               # 管道
    DUCT = "duct"               # 风管
    CABLE_TRAY = "cable_tray"   # 电缆桥架
    EQUIPMENT = "equipment"     # 设备

    # 其他
    OTHER = "other"             # 其他


class MaterialType(str, Enum):
    """材料类型枚举"""
    # 混凝土类
    CONCRETE = "concrete"       # 混凝土

    # 钢材类
    STEEL = "steel"             # 钢材
    REBAR = "rebar"             # 钢筋

    # 砌体类
    BRICK = "brick"             # 砖
    BLOCK = "block"             # 砌块

    # 其他
    WOOD = "wood"               # 木材
    GLASS = "glass"             # 玻璃
    ALUMINUM = "aluminum"       # 铝材
    INSULATION = "insulation"   # 保温材料
    WATERPROOF = "waterproof"   # 防水材料
    OTHER = "other"             # 其他


class DrawingType(str, Enum):
    """图纸类型枚举"""
    # 结构图
    STRUCTURAL_PLAN = "structural_plan"          # 结构平面图
    STRUCTURAL_SECTION = "structural_section"    # 结构剖面图
    BEAM_SCHEDULE = "beam_schedule"              # 梁配筋图
    COLUMN_SCHEDULE = "column_schedule"          # 柱配筋图
    SLAB_SCHEDULE = "slab_schedule"              # 板配筋图
    FOUNDATION_PLAN = "foundation_plan"          # 基础平面图

    # 建筑图
    FLOOR_PLAN = "floor_plan"                    # 建筑平面图
    ELEVATION = "elevation"                      # 立面图
    SECTION = "section"                          # 剖面图
    DETAIL = "detail"                            # 大样图

    # 机电图
    MEP_PLAN = "mep_plan"                        # 机电平面图
    PLUMBING = "plumbing"                        # 给排水图
    HVAC = "hvac"                                # 暖通图
    ELECTRICAL = "electrical"                    # 电气图

    # 其他
    GENERAL = "general"                          # 总图
    OTHER = "other"                              # 其他


class DimensionType(str, Enum):
    """尺寸类型枚举"""
    LENGTH = "length"           # 长度
    WIDTH = "width"             # 宽度
    HEIGHT = "height"           # 高度
    THICKNESS = "thickness"     # 厚度
    DIAMETER = "diameter"       # 直径
    SPAN = "span"               # 跨度
    SPACING = "spacing"         # 间距
    COVER = "cover"             # 保护层厚度
    SECTION = "section"         # 截面（如 300x500）


# =========================================
# 数据类定义
# =========================================

@dataclass
class GraphNode:
    """图节点基类"""
    id: str
    label: NodeLabel = NodeLabel.DOCUMENT  # 默认值，由各子类 __post_init__ 覆写
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "label": self.label.value if isinstance(self.label, Enum) else self.label,
            "properties": self.properties,
            "created_at": self.created_at
        }

    @classmethod
    def generate_id(cls, prefix: str = "node") -> str:
        """生成唯一 ID"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class GraphRelationship:
    """图关系基类"""
    id: str
    from_node_id: str
    to_node_id: str
    rel_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "rel_type": self.rel_type.value if isinstance(self.rel_type, Enum) else self.rel_type,
            "properties": self.properties
        }

    @classmethod
    def generate_id(cls, prefix: str = "rel") -> str:
        """生成唯一 ID"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class DocumentNode(GraphNode):
    """文档节点"""
    name: str = ""
    doc_type: str = "construction_drawing"
    project_id: Optional[str] = None
    file_path: Optional[str] = None

    def __post_init__(self):
        self.label = NodeLabel.DOCUMENT
        self.properties.update({
            "name": self.name,
            "doc_type": self.doc_type,
        })
        if self.project_id:
            self.properties["project_id"] = self.project_id
        if self.file_path:
            self.properties["file_path"] = self.file_path


@dataclass
class DrawingNode(GraphNode):
    """图纸节点"""
    drawing_number: str = ""
    drawing_name: str = ""
    drawing_type: DrawingType = DrawingType.OTHER
    scale: str = ""
    page_num: int = 1

    def __post_init__(self):
        self.label = NodeLabel.DRAWING
        self.properties.update({
            "drawing_number": self.drawing_number,
            "drawing_name": self.drawing_name,
            "drawing_type": self.drawing_type.value if isinstance(self.drawing_type, Enum) else self.drawing_type,
            "scale": self.scale,
            "page_num": self.page_num,
        })


@dataclass
class ComponentNode(GraphNode):
    """构件节点"""
    code: str = ""              # 构件编号，如 KL-1, KZ-2
    component_type: ComponentType = ComponentType.OTHER
    name: str = ""
    floor: str = ""             # 所在楼层

    def __post_init__(self):
        self.label = NodeLabel.COMPONENT
        self.properties.update({
            "code": self.code,
            "component_type": self.component_type.value if isinstance(self.component_type, Enum) else self.component_type,
            "name": self.name,
        })
        if self.floor:
            self.properties["floor"] = self.floor


@dataclass
class MaterialNode(GraphNode):
    """材料节点"""
    material_type: MaterialType = MaterialType.OTHER
    grade: str = ""             # 材料等级，如 C30, HRB400
    unit: str = ""              # 单位

    def __post_init__(self):
        self.label = NodeLabel.MATERIAL
        self.properties.update({
            "material_type": self.material_type.value if isinstance(self.material_type, Enum) else self.material_type,
            "grade": self.grade,
        })
        if self.unit:
            self.properties["unit"] = self.unit


@dataclass
class SpecificationNode(GraphNode):
    """规范节点"""
    spec_code: str = ""         # 规范编号，如 GB50010-2010
    spec_name: str = ""         # 规范名称
    spec_version: str = ""      # 版本
    clause_number: str = ""     # 条款号

    def __post_init__(self):
        self.label = NodeLabel.SPECIFICATION
        self.properties.update({
            "spec_code": self.spec_code,
        })
        if self.spec_name:
            self.properties["spec_name"] = self.spec_name
        if self.spec_version:
            self.properties["spec_version"] = self.spec_version
        if self.clause_number:
            self.properties["clause_number"] = self.clause_number


@dataclass
class DimensionNode(GraphNode):
    """尺寸节点"""
    dimension_type: DimensionType = DimensionType.LENGTH
    value: float = 0.0
    value_str: str = ""         # 原始字符串值，如 "300x500"
    unit: str = "mm"

    def __post_init__(self):
        self.label = NodeLabel.DIMENSION
        self.properties.update({
            "dimension_type": self.dimension_type.value if isinstance(self.dimension_type, Enum) else self.dimension_type,
            "value": self.value,
            "unit": self.unit,
        })
        if self.value_str:
            self.properties["value_str"] = self.value_str


@dataclass
class LocationNode(GraphNode):
    """位置节点"""
    floor: str = ""             # 楼层
    axis_x: str = ""            # X轴编号
    axis_y: str = ""            # Y轴编号
    zone: str = ""              # 区域

    def __post_init__(self):
        self.label = NodeLabel.LOCATION
        if self.floor:
            self.properties["floor"] = self.floor
        if self.axis_x:
            self.properties["axis_x"] = self.axis_x
        if self.axis_y:
            self.properties["axis_y"] = self.axis_y
        if self.zone:
            self.properties["zone"] = self.zone


@dataclass
class AnnotationNode(GraphNode):
    """标注节点"""
    annotation_type: str = ""   # 标注类型
    content: str = ""           # 标注内容
    page_num: int = 1

    def __post_init__(self):
        self.label = NodeLabel.ANNOTATION
        self.properties.update({
            "annotation_type": self.annotation_type,
            "content": self.content,
            "page_num": self.page_num,
        })


# =========================================
# 工厂函数
# =========================================

def create_component_node(
    code: str,
    component_type: str = "other",
    doc_id: str = None,
    id: str = None,
    **kwargs
) -> ComponentNode:
    """
    创建构件节点的工厂函数

    参数：
        code: 构件编号
        component_type: 构件类型字符串
        doc_id: 文档 ID
        id: 节点 ID（缺省自动生成）
        **kwargs: 其他属性
    """
    # 映射构件类型
    type_mapping = {
        "beam": ComponentType.BEAM,
        "column": ComponentType.COLUMN,
        "slab": ComponentType.SLAB,
        "wall": ComponentType.WALL,
        "foundation": ComponentType.FOUNDATION,
        "stair": ComponentType.STAIR,
    }
    comp_type = type_mapping.get(component_type.lower(), ComponentType.OTHER)

    node = ComponentNode(
        id=id or GraphNode.generate_id("comp"),
        code=code,
        component_type=comp_type,
        **kwargs
    )
    if doc_id:
        node.properties["doc_id"] = doc_id

    return node


def create_material_node(
    material_type: str,
    grade: str,
    doc_id: str = None,
    **kwargs
) -> MaterialNode:
    """
    创建材料节点的工厂函数

    参数：
        material_type: 材料类型字符串
        grade: 材料等级
        doc_id: 文档 ID
        **kwargs: 其他属性
    """
    type_mapping = {
        "concrete": MaterialType.CONCRETE,
        "steel": MaterialType.STEEL,
        "rebar": MaterialType.REBAR,
        "brick": MaterialType.BRICK,
    }
    mat_type = type_mapping.get(material_type.lower(), MaterialType.OTHER)

    node = MaterialNode(
        id=GraphNode.generate_id("mat"),
        material_type=mat_type,
        grade=grade,
        **kwargs
    )
    if doc_id:
        node.properties["doc_id"] = doc_id

    return node


def create_specification_node(
    spec_code: str,
    spec_name: str = None,
    **kwargs
) -> SpecificationNode:
    """
    创建规范节点的工厂函数

    参数：
        spec_code: 规范编号
        spec_name: 规范名称
        **kwargs: 其他属性
    """
    return SpecificationNode(
        id=GraphNode.generate_id("spec"),
        spec_code=spec_code,
        spec_name=spec_name or "",
        **kwargs
    )


def create_dimension_node(
    dim_type: str,
    value: float,
    value_str: str = None,
    unit: str = "mm",
    **kwargs
) -> DimensionNode:
    """
    创建尺寸节点的工厂函数

    参数：
        dim_type: 尺寸类型字符串
        value: 数值
        value_str: 原始字符串
        unit: 单位
        **kwargs: 其他属性
    """
    type_mapping = {
        "length": DimensionType.LENGTH,
        "width": DimensionType.WIDTH,
        "height": DimensionType.HEIGHT,
        "thickness": DimensionType.THICKNESS,
        "span": DimensionType.SPAN,
        "section": DimensionType.SECTION,
    }
    dimension_type = type_mapping.get(dim_type.lower(), DimensionType.LENGTH)

    return DimensionNode(
        id=GraphNode.generate_id("dim"),
        dimension_type=dimension_type,
        value=value,
        value_str=value_str or str(value),
        unit=unit,
        **kwargs
    )


def create_relationship(
    from_node_id: str,
    to_node_id: str,
    rel_type: str,
    properties: Dict = None
) -> GraphRelationship:
    """
    创建关系的工厂函数

    参数：
        from_node_id: 起始节点 ID
        to_node_id: 目标节点 ID
        rel_type: 关系类型字符串
        properties: 关系属性
    """
    type_mapping = {
        "contains": RelationType.CONTAINS,
        "uses_material": RelationType.USES_MATERIAL,
        "refers_to": RelationType.REFERS_TO,
        "has_dimension": RelationType.HAS_DIMENSION,
        "located_at": RelationType.LOCATED_AT,
        "connected_to": RelationType.CONNECTED_TO,
        "belongs_to": RelationType.BELONGS_TO,
    }
    relationship_type = type_mapping.get(rel_type.lower(), RelationType.CONTAINS)

    return GraphRelationship(
        id=GraphRelationship.generate_id("rel"),
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        rel_type=relationship_type,
        properties=properties or {}
    )
