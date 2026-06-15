"""智能分析 Agent 域服务：收口 5 类分析与仪表盘。

构造接收 DB 会话；内部惰性构造对应 agent 并调用其真实方法；
agent 已内置缺依赖（RAG/torch 等）的优雅降级，service 直接透传其 dict 结果。
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from agents.cost_agent import get_cost_agent
from agents.progress_agent import get_progress_agent
from agents.risk_agent import get_risk_agent
from agents.safety_agent import get_safety_agent
from agents.weekly_report_agent import ReportFormat, get_weekly_report_agent
from tools.cost_tools import get_cost_tools
from tools.progress_tools import get_progress_tools
from tools.safety_tools import get_safety_tools


class AgentService:
    """智能分析服务：封装 cost/progress/safety/risk/weekly 与 dashboard。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- 周报 ----
    async def generate_weekly_report(
        self,
        project_id: str,
        report_format: ReportFormat = ReportFormat.MARKDOWN,
        include_ai_suggestions: bool = True,
    ) -> dict[str, Any]:
        agent = get_weekly_report_agent(self.db)
        return await agent.generate_report(
            project_id=project_id,
            report_format=report_format,
            include_ai_suggestions=include_ai_suggestions,
        )

    # ---- 风险 ----
    async def analyze_risks(
        self,
        project_id: str,
        include_ai_insights: bool = True,
        historical_days: int = 30,
    ) -> dict[str, Any]:
        agent = get_risk_agent(self.db)
        return await agent.analyze_risks(
            project_id=project_id,
            include_ai_insights=include_ai_insights,
            historical_days=historical_days,
        )

    async def quick_risk_scan(self, project_id: str) -> dict[str, Any]:
        agent = get_risk_agent(self.db)
        return await agent.quick_scan(project_id)

    # ---- 成本 ----
    async def analyze_costs(
        self,
        project_id: str,
        analysis_months: int = 3,
        include_ai_insights: bool = True,
    ) -> dict[str, Any]:
        agent = get_cost_agent(self.db)
        return await agent.analyze_costs(
            project_id=project_id,
            analysis_months=analysis_months,
            include_ai_insights=include_ai_insights,
        )

    async def quick_cost_check(self, project_id: str) -> dict[str, Any]:
        agent = get_cost_agent(self.db)
        return await agent.quick_cost_check(project_id)

    # ---- 进度 ----
    async def analyze_progress(
        self,
        project_id: str,
        analysis_days: int = 30,
        include_ai_insights: bool = True,
    ) -> dict[str, Any]:
        agent = get_progress_agent(self.db)
        return await agent.analyze_progress(
            project_id=project_id,
            analysis_days=analysis_days,
            include_ai_insights=include_ai_insights,
        )

    async def quick_progress_check(self, project_id: str) -> dict[str, Any]:
        agent = get_progress_agent(self.db)
        return await agent.quick_progress_check(project_id)

    # ---- 安全 ----
    async def analyze_safety(
        self,
        project_id: str,
        analysis_days: int = 30,
        include_ai_insights: bool = True,
    ) -> dict[str, Any]:
        agent = get_safety_agent(self.db)
        return await agent.analyze_safety(
            project_id=project_id,
            analysis_days=analysis_days,
            include_ai_insights=include_ai_insights,
        )

    async def quick_safety_check(
        self, project_id: str, days: int = 7
    ) -> dict[str, Any]:
        agent = get_safety_agent(self.db)
        return await agent.quick_safety_check(project_id, days=days)

    # ---- 仪表盘 ----
    def get_dashboard(self, project_id: str) -> dict[str, Any]:
        """聚合进度/成本/安全关键指标，统一 green/yellow/red 三级取最劣。"""
        progress_tools = get_progress_tools(self.db)
        cost_tools = get_cost_tools(self.db)
        safety_tools = get_safety_tools(self.db)

        progress_overview = progress_tools.get_project_overview(project_id)
        progress_status = progress_tools.get_progress_status(project_id)
        cost_overview = cost_tools.get_cost_overview(project_id)
        safety_overview = safety_tools.get_safety_overview(project_id, days=7)

        risk_levels = {
            "progress": progress_status.get("risk_level", "green"),
            "cost": cost_overview.get("risk_level", "green"),
            "safety": safety_overview.get("risk_level", "green"),
        }
        level_priority = {"red": 0, "yellow": 1, "green": 2}
        overall_risk = min(
            risk_levels.values(), key=lambda x: level_priority.get(x, 2)
        )

        return {
            "project_id": project_id,
            "project_name": progress_overview.get("project_name", ""),
            "last_updated": datetime.now().isoformat(),
            "progress": {
                "overall_progress": progress_overview.get("overall_progress", 0),
                "spi": progress_status.get("overall_spi"),
                "delayed_tasks": progress_overview.get("delayed_tasks", 0),
                "risk_level": risk_levels["progress"],
            },
            "cost": {
                "budget_usage_rate": cost_overview.get("budget_usage_rate", 0),
                "cpi": cost_overview.get("cpi"),
                "variance_rate": cost_overview.get("variance_rate", 0),
                "risk_level": risk_levels["cost"],
            },
            "safety": {
                "pass_rate": safety_overview.get("pass_rate", 100),
                "open_defects": safety_overview.get("open_defects", 0),
                "high_defects": safety_overview.get("high_level_defects", 0),
                "risk_level": risk_levels["safety"],
            },
            "overall_risk_level": overall_risk,
            "risk_summary": risk_levels,
        }

    # ---- 工作流日志 ----
    def list_workflow_logs(
        self,
        project_id: Optional[str] = None,
        workflow_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        from models.project import AgentWorkflowLog

        query = self.db.query(AgentWorkflowLog)
        if project_id:
            query = query.filter(AgentWorkflowLog.project_id == project_id)
        if workflow_type:
            query = query.filter(AgentWorkflowLog.workflow_type == workflow_type)
        if status:
            query = query.filter(AgentWorkflowLog.status == status)
        logs = (
            query.order_by(AgentWorkflowLog.start_time.desc()).limit(limit).all()
        )
        return [self._log_to_dict(log) for log in logs]

    def get_workflow_log(self, log_id: int) -> dict[str, Any]:
        from core.exceptions import NotFoundError
        from models.project import AgentWorkflowLog

        log = (
            self.db.query(AgentWorkflowLog)
            .filter(AgentWorkflowLog.id == log_id)
            .first()
        )
        if not log:
            raise NotFoundError(f"工作流日志 {log_id} 不存在")
        return self._log_to_dict(log)

    @staticmethod
    def _log_to_dict(log: Any) -> dict[str, Any]:
        duration = (
            (log.end_time - log.start_time).total_seconds()
            if log.end_time and log.start_time
            else None
        )
        return {
            "log_id": log.id,
            "project_id": log.project_id,
            "workflow_type": log.workflow_type,
            "status": log.status,
            "start_time": log.start_time.isoformat() if log.start_time else None,
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "duration_seconds": duration,
            "error_message": log.error_message,
        }
