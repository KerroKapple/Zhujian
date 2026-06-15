"""
========================================
施工图专用解析器
========================================

📚 模块说明：
- 针对施工图 PDF 的专用解析器
- 提取图框、标注、表格等专业信息
- 支持结构、建筑、机电图纸

🎯 核心功能：
1. 图框信息提取
2. 标注文字识别
3. 构件编号提取
4. 材料信息提取
5. 规范引用识别
6. 表格数据提取

========================================
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import re

from core.logger import logger
from core.config import settings


@dataclass
class DrawingInfo:
    """图纸基本信息"""
    drawing_number: str = ""      # 图纸编号
    drawing_name: str = ""        # 图纸名称
    scale: str = ""               # 比例
    designer: str = ""            # 设计人
    checker: str = ""             # 校对人
    reviewer: str = ""            # 审核人
    project_name: str = ""        # 项目名称
    drawing_date: str = ""        # 出图日期
    version: str = ""             # 版本


@dataclass
class ExtractedElement:
    """提取的元素"""
    element_type: str             # 元素类型
    content: str                  # 内容
    page_num: int = 1             # 所在页码
    position: Tuple[float, float] = (0, 0)  # 位置
    confidence: float = 1.0       # 置信度
    properties: Dict = field(default_factory=dict)


class ConstructionDrawingParser:
    """
    施工图解析器

    🔧 专业功能：
    - 识别施工图图框
    - 提取标注文字
    - 解析尺寸标注
    - 识别图例和符号
    - 提取材料表
    """

    # 构件编号正则模式（精确前缀分组，避免误抽与梁柱重叠）
    # \b 前缀边界 + 固定前缀枚举，按编号长度从长到短排列
    COMPONENT_PATTERNS = {
        # 梁：WKL/JKL/KL/LL/XL/DL(地梁)/L 等
        "beam": [
            r"\b(?:WKL|JKL|KZL|KL|LL|XL|DL|L)[-\s]?\d+[a-zA-Z]?\b",
        ],
        # 柱：KZZ/KZ/GZ/AZ/Z 等
        "column": [
            r"\b(?:KZZ|KZ|GZ|AZ|Z)[-\s]?\d+[a-zA-Z]?\b",
        ],
        # 板：YB/LB/B 等
        "slab": [
            r"\b(?:YB|LB|B)[-\s]?\d+[a-zA-Z]?\b",
        ],
        # 墙：QZ/JLQ/Q 等
        "wall": [
            r"\b(?:QZ|JLQ|Q)[-\s]?\d+[a-zA-Z]?\b",
        ],
        # 基础：DJ/JC/ZJ/CT 等
        "foundation": [
            r"\b(?:DJ|JC|ZJ|CT)[-\s]?\d+[a-zA-Z]?\b",
        ],
        # 楼梯：LT
        "stair": [
            r"\bLT[-\s]?\d+[a-zA-Z]?\b",
        ],
    }

    # 材料等级正则模式
    MATERIAL_PATTERNS = {
        "concrete": [
            r"C\d{2,3}",                             # 混凝土：C30, C35, C40
            r"LC\d{2}",                              # 轻骨料混凝土
        ],
        "rebar": [
            r"HRB\d{3}[E]?",                         # 热轧带肋钢筋：HRB400, HRB400E
            r"HPB\d{3}",                             # 热轧光圆钢筋：HPB300
            r"HRBF\d{3}",                            # 细晶粒钢筋
        ],
        "steel": [
            r"Q\d{3}[A-Z]?",                         # 钢材：Q235B, Q345
        ],
    }

    # 尺寸正则模式
    DIMENSION_PATTERNS = [
        (r"(\d+)\s*[×xX]\s*(\d+)", "section"),       # 截面尺寸：300x500
        (r"厚[度]?\s*[:：]?\s*(\d+)(?:mm)?", "thickness"),
        (r"高[度]?\s*[:：]?\s*(\d+)(?:mm)?", "height"),
        (r"宽[度]?\s*[:：]?\s*(\d+)(?:mm)?", "width"),
        (r"跨[度]?\s*[:：]?\s*(\d+)(?:mm|m)?", "span"),
        (r"间距\s*[:：]?\s*(\d+)(?:mm)?", "spacing"),
        (r"@(\d+)", "spacing"),                      # 钢筋间距：@200
    ]

    # 规范引用模式
    SPEC_PATTERNS = [
        r"GB\s*\d{4,6}[-–]\d{4}",                    # GB50010-2010
        r"GB/T\s*\d{4,6}[-–]\d{4}",                  # GB/T xxxxx-xxxx
        r"JGJ\s*\d{2,4}[-–]\d{4}",                   # JGJ xxx-xxxx
        r"JG\s*\d{2,4}[-–]\d{4}",                    # JG xxx-xxxx
        r"DBJ\s*\d{2}[-–]\d{2,4}[-–]\d{4}",         # 地方标准
    ]

    def __init__(self, enable_ocr: bool = True):
        """
        初始化解析器

        参数：
            enable_ocr: 是否启用 OCR（用于扫描件）
        """
        self.enable_ocr = enable_ocr
        self._pdf_parser = None
        self._ocr_parser = None

    @property
    def pdf_parser(self):
        """延迟加载 PDF 解析器"""
        if self._pdf_parser is None:
            try:
                from services.document.pdf_parser import PDFParser
                self._pdf_parser = PDFParser()
            except ImportError:
                logger.warning("PDFParser 未找到，使用基础解析")
        return self._pdf_parser

    @property
    def ocr_parser(self):
        """延迟加载 OCR 解析器"""
        if self._ocr_parser is None and self.enable_ocr:
            try:
                from services.document.ocr_parser import OCRParser
                self._ocr_parser = OCRParser()
            except ImportError:
                logger.warning("OCRParser 未找到，OCR 功能不可用")
        return self._ocr_parser

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析施工图 PDF

        参数：
            file_path: PDF 文件路径

        返回：
            {
                "drawing_info": DrawingInfo,
                "text": str,
                "pages": List[Dict],
                "tables": List[Dict],
                "components": List[Dict],
                "materials": List[Dict],
                "dimensions": List[Dict],
                "specifications": List[Dict],
                "annotations": List[Dict],
                "is_scanned": bool,
            }
        """
        logger.info(f"开始解析施工图: {file_path}")

        result = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "drawing_info": None,
            "text": "",
            "pages": [],
            "tables": [],
            "components": [],
            "materials": [],
            "dimensions": [],
            "specifications": [],
            "annotations": [],
            "is_scanned": False,
            "total_pages": 0,
        }

        try:
            # 基础 PDF 解析
            base_result = self._parse_pdf(file_path)
            result.update(base_result)

            # 提取施工图特有信息
            text = result.get("text", "")

            # 提取图纸基本信息
            result["drawing_info"] = self._extract_drawing_info(text)

            # 提取构件（按页携带页码，便于后续共现连接推断）
            result["components"] = self._extract_components(
                text, result.get("pages", [])
            )

            # 提取材料
            result["materials"] = self._extract_materials(text)

            # 提取尺寸
            result["dimensions"] = self._extract_dimensions(text)

            # 提取规范引用
            result["specifications"] = self._extract_specifications(text)

            # 提取标注
            result["annotations"] = self._extract_annotations(text)

            logger.info(
                f"施工图解析完成 | "
                f"构件: {len(result['components'])} | "
                f"材料: {len(result['materials'])} | "
                f"尺寸: {len(result['dimensions'])} | "
                f"规范: {len(result['specifications'])}"
            )

        except Exception as e:
            logger.error(f"施工图解析失败: {str(e)}")
            raise

        return result

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """基础 PDF 解析"""
        result = {
            "text": "",
            "pages": [],
            "tables": [],
            "is_scanned": False,
            "total_pages": 0,
        }

        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                result["total_pages"] = len(pdf.pages)
                all_text = []

                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    all_text.append(page_text)

                    # 提取表格
                    tables = page.extract_tables()
                    for j, table in enumerate(tables):
                        if table:
                            result["tables"].append({
                                "page_num": i + 1,
                                "table_index": j,
                                "data": table,
                            })

                    result["pages"].append({
                        "page_num": i + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    })

                result["text"] = "\n".join(all_text)

                # 检测是否为扫描件
                avg_chars = len(result["text"]) / max(result["total_pages"], 1)
                if avg_chars < 100:
                    result["is_scanned"] = True
                    logger.info("检测到扫描件，尝试 OCR")
                    if self.ocr_parser:
                        ocr_result = self._ocr_parse(file_path)
                        result["text"] = ocr_result.get("text", result["text"])

        except Exception as e:
            logger.error(f"PDF 解析错误: {str(e)}")
            raise

        return result

    def _ocr_parse(self, file_path: str) -> Dict[str, Any]:
        """OCR 解析扫描件"""
        if not self.ocr_parser:
            return {"text": ""}

        try:
            return self.ocr_parser.parse_pdf(file_path)
        except Exception as e:
            logger.warning(f"OCR 解析失败: {str(e)}")
            return {"text": ""}

    def _extract_drawing_info(self, text: str) -> DrawingInfo:
        """提取图纸基本信息"""
        info = DrawingInfo()

        # 图纸编号
        patterns = [
            r"图号\s*[:：]\s*([\w\-\.]+)",
            r"图纸编号\s*[:：]\s*([\w\-\.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                info.drawing_number = match.group(1).strip()
                break

        # 图纸名称
        patterns = [
            r"图名\s*[:：]\s*(.+?)(?:\n|$)",
            r"图纸名称\s*[:：]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                info.drawing_name = match.group(1).strip()
                break

        # 比例
        match = re.search(r"比例\s*[:：]\s*1\s*[:：／/]\s*(\d+)", text)
        if match:
            info.scale = f"1:{match.group(1)}"

        # 项目名称
        patterns = [
            r"工程名称\s*[:：]\s*(.+?)(?:\n|$)",
            r"项目名称\s*[:：]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                info.project_name = match.group(1).strip()
                break

        # 设计人
        match = re.search(r"设计[人]?\s*[:：]\s*(\S+)", text)
        if match:
            info.designer = match.group(1).strip()

        return info

    def _extract_components(
        self, text: str, pages: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """提取构件信息（携带页码，全局去重）"""
        components = []
        seen = set()

        # 有分页文本则逐页提取并记录页码，否则退化为整篇（page=0）
        page_texts = (
            [(p.get("page_num", 0), p.get("text", "")) for p in pages]
            if pages else [(0, text)]
        )

        for page_num, page_text in page_texts:
            for comp_type, patterns in self.COMPONENT_PATTERNS.items():
                for pattern in patterns:
                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                    for match in matches:
                        code = match.upper().replace(" ", "")
                        if code not in seen:
                            seen.add(code)
                            components.append({
                                "type": comp_type,
                                "code": code,
                                "page": page_num,
                                "source": "pattern_match",
                                "confidence": 0.9,
                            })

        return components

    def _extract_materials(self, text: str) -> List[Dict]:
        """提取材料信息"""
        materials = []
        seen = set()

        for mat_type, patterns in self.MATERIAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    grade = match.upper()
                    if grade not in seen:
                        seen.add(grade)
                        materials.append({
                            "type": mat_type,
                            "grade": grade,
                            "source": "pattern_match",
                            "confidence": 0.9,
                        })

        return materials

    def _extract_dimensions(self, text: str) -> List[Dict]:
        """提取尺寸信息"""
        dimensions = []

        for pattern, dim_type in self.DIMENSION_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    value = "x".join(match)
                else:
                    value = match

                dimensions.append({
                    "type": dim_type,
                    "value": value,
                    "unit": "mm",
                    "source": "pattern_match",
                })

        return dimensions

    def _extract_specifications(self, text: str) -> List[Dict]:
        """提取规范引用"""
        specifications = []
        seen = set()

        for pattern in self.SPEC_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                code = match.replace(" ", "").upper()
                if code not in seen:
                    seen.add(code)
                    specifications.append({
                        "code": code,
                        "source": "drawing",
                        "confidence": 0.95,
                    })

        return specifications

    def _extract_annotations(self, text: str) -> List[Dict]:
        """提取标注信息"""
        annotations = []

        patterns = [
            (r"注\s*[:：]\s*(.+?)(?:\n|$)", "general_note"),
            (r"说明\s*[:：]\s*(.+?)(?:\n|$)", "description"),
            (r"备注\s*[:：]\s*(.+?)(?:\n|$)", "remark"),
            (r"技术要求\s*[:：]\s*(.+?)(?:\n|$)", "technical_requirement"),
        ]

        for pattern, note_type in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                content = match.strip()
                if len(content) > 5:  # 过滤过短的内容
                    annotations.append({
                        "type": note_type,
                        "content": content,
                        "source": "pattern_match",
                    })

        return annotations
