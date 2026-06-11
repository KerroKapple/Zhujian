"""
========================================
Agent 调度 API 接口 (修复版)
========================================

📚 模块说明：
- Agent 触发和调度接口
- 支持周报生成、风险分析、成本分析等
- 异步执行和状态查询

🎯 核心功能：
1. 周报生成接口
2. 风险分析接口
3. 成本分析接口
4. 进度分析接口
5. 安全分析接口
6. 快速风险扫描
7. 项目仪表盘
8. 工作流状态查询

========================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum

from loguru import logger
from core.database import get_db

# 导入 Agents (使用工厂函数)
from agents.weekly_report_agent import WeeklyReportAgent, ReportFormat, get_weekly_report_agent
from agents.risk_agent import RiskAnalysisAgent, get_risk_agent
from agents.cost_agent import CostAnalysisAgent, get_cost_agent
from agents.progress_agent import ProgressAnalysisAgent, get_progress_agent
from agents.safety_agent import SafetyAnalysisAgent, get_safety_agent

# 导入 Tools
from tools.progress_tools import get_progress_tools
from tools.cost_tools import get_cost_tools
from tools.safety_tools import get_safety_tools

# 导入模型
from models.project import AgentWorkflowLog

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
                "include_ai_suggestions": True
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


# =========================================
# 周报生成接口
# =========================================

@router.post(
    "/weekly-report",
    response_model=AgentResponse,
    summary="生成项目周报",
    description="调用周报Agent生成项目周报，支持Markdown/JSON/HTML格式"
)
async def generate_weekly_report(
        request: WeeklyReportRequest,
        db: Session = Depends(get_db)
):
    """生成项目周报"""
    start_time = datetime.now()

    try:
        logger.info(f"开始生成周报: project_id={request.project_id}")

        agent = get_weekly_report_agent(db)

        format_map = {
            ReportFormatEnum.MARKDOWN: ReportFormat.MARKDOWN,
            ReportFormatEnum.JSON: ReportFormat.JSON,
            ReportFormatEnum.HTML: ReportFormat.HTML
        }
        report_format = format_map.get(request.format, ReportFormat.MARKDOWN)

        result = await agent.generate_report(
            project_id=request.project_id,
            report_format=report_format,
            include_ai_suggestions=request.include_ai_suggestions
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.WEEKLY_REPORT.value,
            project_id=request.project_id,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"生成周报失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.WEEKLY_REPORT.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds()
        )


# =========================================
# 风险分析接口
# =========================================

@router.post(
    "/risk-analysis",
    response_model=AgentResponse,
    summary="执行风险分析",
    description="调用风险Agent进行多维度风险分析"
)
async def analyze_risks(
        request: RiskAnalysisRequest,
        db: Session = Depends(get_db)
):
    """执行风险分析"""
    start_time = datetime.now()

    try:
        logger.info(f"开始风险分析: project_id={request.project_id}")

        agent = get_risk_agent(db)

        result = await agent.analyze_risks(
            project_id=request.project_id,
            include_ai_insights=request.include_ai_insights,
            historical_days=request.historical_days
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.RISK_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"风险分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.RISK_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds()
        )


@router.get(
    "/risk-analysis/{project_id}/quick-scan",
    response_model=QuickScanResponse,
    summary="快速风险扫描",
    description="轻量级风险扫描，快速获取风险概况"
)
async def quick_risk_scan(
        project_id: str,
        db: Session = Depends(get_db)
):
    """快速风险扫描"""
    try:
        agent = get_risk_agent(db)
        result = await agent.quick_scan(project_id)

        if result.get("success"):
            return QuickScanResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "快速扫描失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"快速扫描失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =========================================
# 成本分析接口
# =========================================

@router.post(
    "/cost-analysis",
    response_model=AgentResponse,
    summary="执行成本分析",
    description="调用成本Agent进行全面成本分析"
)
async def analyze_costs(
        request: CostAnalysisRequest,
        db: Session = Depends(get_db)
):
    """执行成本分析"""
    start_time = datetime.now()

    try:
        logger.info(f"开始成本分析: project_id={request.project_id}")

        agent = get_cost_agent(db)

        result = await agent.analyze_costs(
            project_id=request.project_id,
            analysis_months=request.analysis_months,
            include_ai_insights=request.include_ai_insights
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.COST_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"成本分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.COST_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds()
        )


@router.get(
    "/cost-analysis/{project_id}/quick-check",
    summary="快速成本检查",
    description="轻量级成本检查，用于仪表盘展示"
)
async def quick_cost_check(
        project_id: str,
        db: Session = Depends(get_db)
):
    """快速成本检查"""
    try:
        agent = get_cost_agent(db)
        result = await agent.quick_cost_check(project_id)
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "快速成本检查失败")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"快速成本检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =========================================
# 进度分析接口
# =========================================

@router.post(
    "/progress-analysis",
    response_model=AgentResponse,
    summary="执行进度分析",
    description="调用进度Agent进行全面进度分析"
)
async def analyze_progress(
        request: ProgressAnalysisRequest,
        db: Session = Depends(get_db)
):
    """执行进度分析"""
    start_time = datetime.now()

    try:
        logger.info(f"开始进度分析: project_id={request.project_id}")

        agent = get_progress_agent(db)

        result = await agent.analyze_progress(
            project_id=request.project_id,
            analysis_days=request.analysis_days,
            include_ai_insights=request.include_ai_insights
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.PROGRESS_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"进度分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.PROGRESS_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds()
        )


@router.get(
    "/progress-analysis/{project_id}/quick-check",
    summary="快速进度检查",
    description="轻量级进度检查，用于仪表盘展示"
)
async def quick_progress_check(
        project_id: str,
        db: Session = Depends(get_db)
):
    """快速进度检查"""
    try:
        agent = get_progress_agent(db)
        result = await agent.quick_progress_check(project_id)
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "快速进度检查失败")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"快速进度检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =========================================
# 安全分析接口
# =========================================

@router.post(
    "/safety-analysis",
    response_model=AgentResponse,
    summary="执行安全分析",
    description="调用安全Agent进行全面安全分析"
)
async def analyze_safety(
        request: SafetyAnalysisRequest,
        db: Session = Depends(get_db)
):
    """执行安全分析"""
    start_time = datetime.now()

    try:
        logger.info(f"开始安全分析: project_id={request.project_id}")

        agent = get_safety_agent(db)

        result = await agent.analyze_safety(
            project_id=request.project_id,
            analysis_days=request.analysis_days,
            include_ai_insights=request.include_ai_insights
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return AgentResponse(
            success=result.get("success", False),
            agent_type=AgentType.SAFETY_ANALYSIS.value,
            project_id=request.project_id,
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"安全分析失败: {e}")
        return AgentResponse(
            success=False,
            agent_type=AgentType.SAFETY_ANALYSIS.value,
            project_id=request.project_id,
            error=str(e),
            execution_time=(datetime.now() - start_time).total_seconds()
        )


@router.get(
    "/safety-analysis/{project_id}/quick-check",
    summary="快速安全检查",
    description="轻量级安全检查，用于仪表盘展示"
)
async def quick_safety_check(
        project_id: str,
        days: int = Query(7, ge=1, le=30, description="分析天数"),
        db: Session = Depends(get_db)
):
    """快速安全检查"""
    try:
        agent = get_safety_agent(db)
        result = await agent.quick_safety_check(project_id, days=days)
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "快速安全检查失败")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"快速安全检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =========================================
# 项目仪表盘接口
# =========================================

@router.get(
    "/dashboard/{project_id}",
    summary="获取项目仪表盘",
    description="聚合进度、成本、安全关键指标"
)
async def get_project_dashboard(
        project_id: str,
        db: Session = Depends(get_db)
):
    """获取项目仪表盘数据"""
    try:
        progress_tools = get_progress_tools(db)
        cost_tools = get_cost_tools(db)
        safety_tools = get_safety_tools(db)

        progress_overview = progress_tools.get_project_overview(project_id)
        progress_status = progress_tools.get_progress_status(project_id)
        cost_overview = cost_tools.get_cost_overview(project_id)
        safety_overview = safety_tools.get_safety_overview(project_id, days=7)

        risk_levels = {
            "progress": progress_status.get("risk_level", "green"),
            "cost": cost_overview.get("risk_level", "green"),
            "safety": safety_overview.get("risk_level", "green")
        }

        # 各工具统一返回 green/yellow/red 三级体系
        level_priority = {"red": 0, "yellow": 1, "green": 2}
        overall_risk = min(risk_levels.values(), key=lambda x: level_priority.get(x, 2))

        return {
            "project_id": project_id,
            "project_name": progress_overview.get("project_name", ""),
            "last_updated": datetime.now().isoformat(),
            "progress": {
                "overall_progress": progress_overview.get("overall_progress", 0),
                "spi": progress_status.get("overall_spi"),
                "delayed_tasks": progress_overview.get("delayed_tasks", 0),
                "risk_level": risk_levels["progress"]
            },
            "cost": {
                "budget_usage_rate": cost_overview.get("budget_usage_rate", 0),
                "cpi": cost_overview.get("cpi"),
                "variance_rate": cost_overview.get("variance_rate", 0),
                "risk_level": risk_levels["cost"]
            },
            "safety": {
                "pass_rate": safety_overview.get("pass_rate", 100),
                "open_defects": safety_overview.get("open_defects", 0),
                "high_defects": safety_overview.get("high_level_defects", 0),
                "risk_level": risk_levels["safety"]
            },
            "overall_risk_level": overall_risk,
            "risk_summary": risk_levels
        }

    except Exception as e:
        logger.error(f"获取仪表盘数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =========================================
# 工作流日志查询接口
# =========================================

@router.get(
    "/workflows",
    response_model=List[WorkflowLogResponse],
    summary="查询工作流日志",
    description="查询Agent工作流执行日志"
)
async def list_workflow_logs(
        project_id: Optional[str] = Query(None, description="项目ID筛选"),
        workflow_type: Optional[str] = Query(None, description="工作流类型筛选"),
        status: Optional[str] = Query(None, description="状态筛选"),
        limit: int = Query(20, ge=1, le=100, description="返回条数"),
        db: Session = Depends(get_db)
):
    """查询工作流日志"""
    try:
        query = db.query(AgentWorkflowLog)

        if project_id:
            query = query.filter(AgentWorkflowLog.project_id == project_id)
        if workflow_type:
            query = query.filter(AgentWorkflowLog.workflow_type == workflow_type)
        if status:
            query = query.filter(AgentWorkflowLog.status == status)

        logs = query.order_by(AgentWorkflowLog.start_time.desc()).limit(limit).all()

        return [
            WorkflowLogResponse(
                log_id=log.id,
                project_id=log.project_id,
                workflow_type=log.workflow_type,
                status=log.status,
                start_time=log.start_time.isoformat() if log.start_time else None,
                end_time=log.end_time.isoformat() if log.end_time else None,
                duration_seconds=(log.end_time - log.start_time).total_seconds() if log.end_time and log.start_time else None,
                error_message=log.error_message
            )
            for log in logs
        ]

    except Exception as e:
        logger.error(f"查询工作流日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/workflows/{log_id}",
    response_model=WorkflowLogResponse,
    summary="获取工作流详情",
    description="获取单个工作流执行详情"
)
async def get_workflow_log(
        log_id: int,
        db: Session = Depends(get_db)
):
    """获取工作流详情"""
    try:
        log = db.query(AgentWorkflowLog).filter(AgentWorkflowLog.id == log_id).first()

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"工作流日志 {log_id} 不存在"
            )

        return WorkflowLogResponse(
            log_id=log.id,
            project_id=log.project_id,
            workflow_type=log.workflow_type,
            status=log.status,
            start_time=log.start_time.isoformat() if log.start_time else None,
            end_time=log.end_time.isoformat() if log.end_time else None,
            duration_seconds=(log.end_time - log.start_time).total_seconds() if log.end_time and log.start_time else None,
            error_message=log.error_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )