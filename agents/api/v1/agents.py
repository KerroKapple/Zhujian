"""智能分析 Agent 调度 API。

路由层仅做入参校验 + 调 AgentService + 返回；
保持端点路径、请求/响应模型与 success 语义不变；错误经 core.exceptions。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from core.deps import get_agent_service
from core.exceptions import ServiceUnavailableError
from core.logger import logger
from services.agent.agent_service import AgentService

# 报告格式枚举（沿用 agent 内定义，路由仅做入参映射）
from agents.weekly_report_agent import ReportFormat

router = APIRouter()


# =========================================
# 枚举和请求/响应模型
# =========================================

class AgentType(str, Enum):
    """Agent类型"""
    WEEKLY_REPORT = "weekly_report"
    RISK_ANALYSIS = "risk_analysis"
    COST_ANALYSIS = "cost_analysis"
    PROGRESS_ANALYSIS = "progress_analysis"
    SAFETY_ANALYSIS = "safety_analysis"


class ReportFormatEnum(str, Enum):
    """报告格式"""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class WeeklyReportRequest(BaseModel):
    """周报生成请求"""
    project_id: str = Field(..., description="项目ID")
    format: ReportFormatEnum = Field(ReportFormatEnum.MARKDOWN, description="输出格式")
    include_ai_suggestions: bool = Field(True, description="是否包含AI建议")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "P001",
                "format": "markdown",
                "include_ai_suggestions": True,
            }
        }
    )


class RiskAnalysisRequest(BaseModel):
    """风险分析请求"""
    project_id: str = Field(..., description="项目ID")
    include_ai_insights: bool = Field(True, description="是否包含AI洞察")
    historical_days: int = Field(30, ge=7, le=90, description="历史数据分析天数")


class CostAnalysisRequest(BaseModel):
    """成本分析请求"""
    project_id: str = Field(..., description="项目ID")
    analysis_months: int = Field(3, ge=1, le=12, description="分析月数")
    include_ai_insights: bool = Field(True, description="是否包含AI洞察")


class ProgressAnalysisRequest(BaseModel):
    """进度分析请求"""
    project_id: str = Field(..., description="项目ID")
    analysis_days: int = Field(30, ge=7, le=90, description="分析天数")
    include_ai_insights: bool = Field(True, description="是否包含AI洞察")


class SafetyAnalysisRequest(BaseModel):
    """安全分析请求"""
    project_id: str = Field(..., description="项目ID")
    analysis_days: int = Field(30, ge=7, le=90, description="分析天数")
    include_ai_insights: bool = Field(True, description="是否包含AI洞察")


class AgentResponse(BaseModel):
    """Agent响应"""
    success: bool = Field(..., description="是否成功")
    agent_type: str = Field(..., description="Agent类型")
    project_id: str = Field(..., description="项目ID")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")


class QuickScanResponse(BaseModel):
    """快速扫描响应"""
    success: bool
    project_id: str
    scan_time: str
    risk_levels: Dict[str, str]
    highest_risk_category: str
    highest_risk_level: str
    alerts: List[str]
    metrics: Dict[str, Any]


class WorkflowLogResponse(BaseModel):
    """工作流日志响应"""
    log_id: int
    project_id: Optional[str]
    workflow_type: Optional[str]
    status: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    error_message: Optional[str]


# 报告格式映射：API 枚举 -> agent 枚举
_REPORT_FORMAT_MAP = {
    ReportFormatEnum.MARKDOWN: ReportFormat.MARKDOWN,
    ReportFormatEnum.JSON: ReportFormat.JSON,
    ReportFormatEnum.HTML: ReportFormat.HTML,
}


# =========================================
# 周报生成接口
# =========================================

@router.post(
    "/weekly-report",
    response_model=AgentResponse,
    summary="生成项目周报",
    description="调用周报Agent生成项目周报，支持Markdown/JSON/HTML格式",
)
async def generate_weekly_report(
    request: WeeklyReportRequest,
    service: AgentService = Depends(get_agent_service),
):
    """生成项目周报"""
    start_time = datetime.now()
    try:
        logger.info(f"开始生成周报: project_id={request.project_id}")
        result = await service.generate_weekly_report(
            project_id=request.project_id,
            report_format=_REPORT_FORMAT_MAP.get(
                request.format, ReportFormat.MARKDOWN
            ),
            include_ai_suggestions=request.include_ai_suggestions,
        )
        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.WEEKLY_REPORT.value,
            project_id=request.project_id,
            result=result,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    except Exception as e:
        logger.error(f"生成周报失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.WEEKLY_REPORT.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds(),
        )


# =========================================
# 风险分析接口
# =========================================

@router.post(
    "/risk-analysis",
    response_model=AgentResponse,
    summary="执行风险分析",
    description="调用风险Agent进行多维度风险分析",
)
async def analyze_risks(
    request: RiskAnalysisRequest,
    service: AgentService = Depends(get_agent_service),
):
    """执行风险分析"""
    start_time = datetime.now()
    try:
        logger.info(f"开始风险分析: project_id={request.project_id}")
        result = await service.analyze_risks(
            project_id=request.project_id,
            include_ai_insights=request.include_ai_insights,
            historical_days=request.historical_days,
        )
        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.RISK_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    except Exception as e:
        logger.error(f"风险分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.RISK_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds(),
        )


@router.get(
    "/risk-analysis/{project_id}/quick-scan",
    response_model=QuickScanResponse,
    summary="快速风险扫描",
    description="轻量级风险扫描，快速获取风险概况",
)
async def quick_risk_scan(
    project_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """快速风险扫描"""
    result = await service.quick_risk_scan(project_id)
    if not result.get("success"):
        raise ServiceUnavailableError(result.get("error", "快速扫描失败"))
    return QuickScanResponse(**result)


# =========================================
# 成本分析接口
# =========================================

@router.post(
    "/cost-analysis",
    response_model=AgentResponse,
    summary="执行成本分析",
    description="调用成本Agent进行全面成本分析",
)
async def analyze_costs(
    request: CostAnalysisRequest,
    service: AgentService = Depends(get_agent_service),
):
    """执行成本分析"""
    start_time = datetime.now()
    try:
        logger.info(f"开始成本分析: project_id={request.project_id}")
        result = await service.analyze_costs(
            project_id=request.project_id,
            analysis_months=request.analysis_months,
            include_ai_insights=request.include_ai_insights,
        )
        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.COST_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    except Exception as e:
        logger.error(f"成本分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.COST_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds(),
        )


@router.get(
    "/cost-analysis/{project_id}/quick-check",
    summary="快速成本检查",
    description="轻量级成本检查，用于仪表盘展示",
)
async def quick_cost_check(
    project_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """快速成本检查"""
    result = await service.quick_cost_check(project_id)
    if not result.get("success", False):
        raise ServiceUnavailableError(result.get("error", "快速成本检查失败"))
    return result


# =========================================
# 进度分析接口
# =========================================

@router.post(
    "/progress-analysis",
    response_model=AgentResponse,
    summary="执行进度分析",
    description="调用进度Agent进行全面进度分析",
)
async def analyze_progress(
    request: ProgressAnalysisRequest,
    service: AgentService = Depends(get_agent_service),
):
    """执行进度分析"""
    start_time = datetime.now()
    try:
        logger.info(f"开始进度分析: project_id={request.project_id}")
        result = await service.analyze_progress(
            project_id=request.project_id,
            analysis_days=request.analysis_days,
            include_ai_insights=request.include_ai_insights,
        )
        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.PROGRESS_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    except Exception as e:
        logger.error(f"进度分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.PROGRESS_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds(),
        )


@router.get(
    "/progress-analysis/{project_id}/quick-check",
    summary="快速进度检查",
    description="轻量级进度检查，用于仪表盘展示",
)
async def quick_progress_check(
    project_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """快速进度检查"""
    result = await service.quick_progress_check(project_id)
    if not result.get("success", False):
        raise ServiceUnavailableError(result.get("error", "快速进度检查失败"))
    return result


# =========================================
# 安全分析接口
# =========================================

@router.post(
    "/safety-analysis",
    response_model=AgentResponse,
    summary="执行安全分析",
    description="调用安全Agent进行全面安全分析",
)
async def analyze_safety(
    request: SafetyAnalysisRequest,
    service: AgentService = Depends(get_agent_service),
):
    """执行安全分析"""
    start_time = datetime.now()
    try:
        logger.info(f"开始安全分析: project_id={request.project_id}")
        result = await service.analyze_safety(
            project_id=request.project_id,
            analysis_days=request.analysis_days,
            include_ai_insights=request.include_ai_insights,
        )
        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.SAFETY_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    except Exception as e:
        logger.error(f"安全分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.SAFETY_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds(),
        )


@router.get(
    "/safety-analysis/{project_id}/quick-check",
    summary="快速安全检查",
    description="轻量级安全检查，用于仪表盘展示",
)
async def quick_safety_check(
    project_id: str,
    days: int = Query(7, ge=1, le=30, description="分析天数"),
    service: AgentService = Depends(get_agent_service),
):
    """快速安全检查"""
    result = await service.quick_safety_check(project_id, days=days)
    if not result.get("success", False):
        raise ServiceUnavailableError(result.get("error", "快速安全检查失败"))
    return result


# =========================================
# 项目仪表盘接口
# =========================================

@router.get(
    "/dashboard/{project_id}",
    summary="获取项目仪表盘",
    description="聚合进度、成本、安全关键指标",
)
async def get_project_dashboard(
    project_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """获取项目仪表盘数据"""
    return service.get_dashboard(project_id)


# =========================================
# 工作流日志查询接口
# =========================================

@router.get(
    "/workflows",
    response_model=List[WorkflowLogResponse],
    summary="查询工作流日志",
    description="查询Agent工作流执行日志",
)
async def list_workflow_logs(
    project_id: Optional[str] = Query(None, description="项目ID筛选"),
    workflow_type: Optional[str] = Query(None, description="工作流类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    service: AgentService = Depends(get_agent_service),
):
    """查询工作流日志"""
    return [
        WorkflowLogResponse(**log)
        for log in service.list_workflow_logs(
            project_id=project_id,
            workflow_type=workflow_type,
            status=status,
            limit=limit,
        )
    ]


@router.get(
    "/workflows/{log_id}",
    response_model=WorkflowLogResponse,
    summary="获取工作流详情",
    description="获取单个工作流执行详情",
)
async def get_workflow_log(
    log_id: int,
    service: AgentService = Depends(get_agent_service),
):
    """获取工作流详情"""
    return WorkflowLogResponse(**service.get_workflow_log(log_id))
