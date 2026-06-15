"""
进度分析Agent
==============

📚 模块说明：
- 项目进度多维度分析
- SPI/EVM指标计算与评估
- 延期任务识别与预警
- 进度预测与优化建议

🎯 核心功能：
1. 进度概览：项目整体进度状态
2. SPI分析：进度绩效指数计算
3. 延期识别：延期任务检测与分类
4. 关键路径：关键路径任务分析
5. 趋势分析：进度变化趋势
6. 完工预测：项目完工时间预测
7. 瓶颈识别：资源和进度瓶颈
8. 优化建议：基于RAG生成建议

💡 使用方式：
    from agents.progress_agent import ProgressAnalysisAgent, get_progress_agent

    agent = get_progress_agent(db)
    result = await agent.analyze_progress("P001")
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from sqlalchemy.orm import Session
from loguru import logger

# 导入工具模块
from tools.progress_tools import ProgressTools, get_progress_tools
from tools.rag_tool import run_rag

# 导入数据模型
from models.project import AgentWorkflowLog


class ProgressRiskLevel(str, Enum):
    """进度风险等级"""
    CRITICAL = "critical"  # 严重延期 (SPI < 0.75)
    HIGH = "high"  # 高风险 (SPI 0.75-0.85)
    MEDIUM = "medium"  # 中风险 (SPI 0.85-0.95)
    LOW = "low"  # 低风险 (SPI >= 0.95)


class TaskStatus(str, Enum):
    """任务状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    SUSPENDED = "suspended"


@dataclass
class ProgressOverview:
    """进度概览"""
    project_id: str = ""
    project_name: str = ""
    project_manager: str = ""
    start_date: str = ""
    planned_end_date: str = ""
    overall_progress: float = 0.0
    planned_progress: float = 0.0
    variance: float = 0.0
    total_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0
    delayed_tasks: int = 0
    not_started_tasks: int = 0


@dataclass
class SPIAnalysis:
    """SPI分析结果"""
    overall_spi: float = 1.0
    risk_level: str = "low"
    variance_days: int = 0
    earned_value: float = 0.0
    planned_value: float = 0.0
    schedule_status: str = "正常"


@dataclass
class DelayedTask:
    """延期任务"""
    task_id: str = ""
    task_name: str = ""
    planned_progress: float = 0.0
    actual_progress: float = 0.0
    spi: float = 1.0
    delay_days: int = 0
    planned_end: str = ""
    is_critical: bool = False
    responsible: str = ""
    delay_reason: str = ""


@dataclass
class CriticalPathTask:
    """关键路径任务"""
    task_id: str = ""
    task_name: str = ""
    planned_start: str = ""
    planned_end: str = ""
    actual_progress: float = 0.0
    spi: float = 1.0
    status: str = ""
    is_delayed: bool = False
    slack_days: int = 0


@dataclass
class ProgressTrend:
    """进度趋势"""
    date: str = ""
    planned_progress: float = 0.0
    actual_progress: float = 0.0
    spi: float = 1.0
    variance: float = 0.0


@dataclass
class CompletionPrediction:
    """完工预测"""
    predicted_end_date: str = ""
    original_end_date: str = ""
    delay_days: int = 0
    confidence: float = 0.0
    method: str = ""
    will_delay: bool = False


@dataclass
class Bottleneck:
    """瓶颈分析"""
    bottleneck_type: str = ""
    description: str = ""
    affected_tasks: List[str] = field(default_factory=list)
    impact_level: str = "medium"
    recommendation: str = ""


@dataclass
class ProgressAnalysisResult:
    """进度分析结果"""
    project_id: str = ""
    project_name: str = ""
    analysis_date: str = ""
    analysis_period: str = ""

    # 进度概览
    overview: ProgressOverview = field(default_factory=ProgressOverview)

    # SPI分析
    spi_analysis: SPIAnalysis = field(default_factory=SPIAnalysis)

    # 延期任务
    delayed_tasks: List[DelayedTask] = field(default_factory=list)
    delayed_count: int = 0
    critical_delayed_count: int = 0

    # 关键路径
    critical_path_tasks: List[CriticalPathTask] = field(default_factory=list)
    critical_path_status: str = "normal"

    # 进度趋势
    trends: List[ProgressTrend] = field(default_factory=list)
    trend_direction: str = "stable"

    # 完工预测
    prediction: CompletionPrediction = field(default_factory=CompletionPrediction)

    # 瓶颈分析
    bottlenecks: List[Bottleneck] = field(default_factory=list)

    # 资源配置
    resource_status: str = "normal"
    parallel_tasks: int = 0

    # 建议
    suggestions: List[str] = field(default_factory=list)
    ai_insights: List[str] = field(default_factory=list)

    # 执行信息
    success: bool = True
    execution_time: float = 0.0
    error: str = ""


class ProgressAnalysisAgent:
    """
    进度分析Agent

    职责：
    - 编排进度分析工具
    - 多维度进度评估
    - 生成预警和建议
    """

    THRESHOLDS = {
        "spi_critical": 0.75,
        "spi_high": 0.85,
        "spi_medium": 0.95,
        "delayed_tasks_critical": 10,
        "delayed_tasks_high": 5,
        "critical_delayed_warning": 2
    }

    def __init__(self, db: Session):
        """初始化Agent"""
        self.db = db
        self.progress_tools = get_progress_tools(db)
        logger.info("ProgressAnalysisAgent 初始化完成")

    async def analyze_progress(
            self,
            project_id: str,
            analysis_days: int = 30,
            include_ai_insights: bool = True
    ) -> Dict[str, Any]:
        """执行全面进度分析"""
        start_time = datetime.now()
        workflow_log = None

        try:
            workflow_log = self._start_workflow(project_id, "progress_analysis")
            logger.info(f"开始项目 {project_id} 进度分析")

            result = ProgressAnalysisResult(
                project_id=project_id,
                analysis_date=date.today().isoformat(),
                analysis_period=f"最近{analysis_days}天"
            )

            # Step 1: 获取项目概览
            overview_data = self.progress_tools.get_project_overview(project_id)
            result.overview = self._build_overview(overview_data)
            result.project_name = result.overview.project_name

            # Step 2: SPI分析
            status_data = self.progress_tools.get_progress_status(project_id)
            result.spi_analysis = self._build_spi_analysis(status_data)

            # Step 3: 延期任务
            delayed_data = self.progress_tools.get_delayed_tasks(project_id)
            result.delayed_tasks = self._build_delayed_tasks(delayed_data)
            result.delayed_count = len(result.delayed_tasks)
            result.critical_delayed_count = len([t for t in result.delayed_tasks if t.is_critical])

            # Step 4: 关键路径
            critical_data = self.progress_tools.get_critical_path_tasks(project_id)
            result.critical_path_tasks = self._build_critical_path(critical_data)
            result.critical_path_status = self._assess_critical_path_status(result.critical_path_tasks)

            # Step 5: 趋势分析（工具仅给出聚合趋势，无逐期序列）
            trend_data = self.progress_tools.analyze_progress_trend(project_id, days=analysis_days)
            result.trends = self._build_trends(trend_data)
            result.trend_direction = self._map_trend_direction(trend_data.get("trend", "平稳"))

            # Step 6: 完工预测
            prediction_data = self.progress_tools.predict_completion_time(project_id)
            result.prediction = self._build_prediction(prediction_data)

            # Step 7: 瓶颈识别
            bottleneck_data = self.progress_tools.identify_bottlenecks(project_id)
            result.bottlenecks = self._build_bottlenecks(bottleneck_data)

            # Step 8: 资源配置
            resource_data = self.progress_tools.get_resource_allocation(project_id)
            result.resource_status = resource_data.get("load_status", "normal")
            result.parallel_tasks = resource_data.get("parallel_tasks", 0)

            # Step 9: 生成建议
            result.suggestions = self._generate_suggestions(result)

            # Step 10: AI洞察
            if include_ai_insights:
                result.ai_insights = await self._generate_ai_insights(result)

            result.success = True
            result.execution_time = (datetime.now() - start_time).total_seconds()

            self._complete_workflow(workflow_log, result, start_time)
            logger.info(f"进度分析完成，耗时: {result.execution_time:.2f}秒")

            return asdict(result)

        except Exception as e:
            error_msg = f"进度分析失败: {str(e)}"
            logger.error(error_msg)
            self._fail_workflow(workflow_log, error_msg)
            return {
                "success": False,
                "project_id": project_id,
                "error": error_msg,
                "execution_time": (datetime.now() - start_time).total_seconds()
            }

    async def quick_progress_check(self, project_id: str) -> Dict[str, Any]:
        """快速进度检查"""
        try:
            overview = self.progress_tools.get_project_overview(project_id)
            status = self.progress_tools.get_progress_status(project_id)

            spi = status.get("overall_spi", 1)
            delayed_count = overview.get("delayed_tasks", 0)

            if spi < self.THRESHOLDS["spi_critical"] or delayed_count >= self.THRESHOLDS["delayed_tasks_critical"]:
                risk_level = "critical"
            elif spi < self.THRESHOLDS["spi_high"] or delayed_count >= self.THRESHOLDS["delayed_tasks_high"]:
                risk_level = "high"
            elif spi < self.THRESHOLDS["spi_medium"]:
                risk_level = "medium"
            else:
                risk_level = "low"

            alerts = []
            if spi < self.THRESHOLDS["spi_high"]:
                alerts.append(f"SPI偏低: {spi:.2f}")
            if delayed_count >= self.THRESHOLDS["delayed_tasks_high"]:
                alerts.append(f"延期任务: {delayed_count}个")

            return {
                "success": True,
                "project_id": project_id,
                "check_time": datetime.now().isoformat(),
                "overall_progress": overview.get("overall_progress", 0),
                "spi": spi,
                "delayed_tasks": delayed_count,
                "risk_level": risk_level,
                "alerts": alerts
            }

        except Exception as e:
            return {"success": False, "project_id": project_id, "error": str(e)}

    def _build_overview(self, data: Dict) -> ProgressOverview:
        """构建进度概览"""
        return ProgressOverview(
            project_id=data.get("project_id", ""),
            project_name=data.get("project_name", ""),
            project_manager=data.get("project_manager", ""),
            start_date=data.get("start_date", ""),
            planned_end_date=data.get("planned_end_date", ""),
            overall_progress=data.get("overall_progress", 0),
            planned_progress=data.get("planned_progress", 0),
            variance=data.get("overall_progress", 0) - data.get("planned_progress", 0),
            total_tasks=data.get("total_tasks", 0),
            completed_tasks=data.get("completed_tasks", 0),
            in_progress_tasks=data.get("in_progress_tasks", 0),
            delayed_tasks=data.get("delayed_tasks", 0),
            not_started_tasks=data.get("not_started_tasks", 0)
        )

    def _build_spi_analysis(self, data: Dict) -> SPIAnalysis:
        """构建SPI分析"""
        spi = data.get("overall_spi", 1)
        if spi < self.THRESHOLDS["spi_critical"]:
            risk_level = "critical"
            schedule_status = "严重滞后"
        elif spi < self.THRESHOLDS["spi_high"]:
            risk_level = "high"
            schedule_status = "明显滞后"
        elif spi < self.THRESHOLDS["spi_medium"]:
            risk_level = "medium"
            schedule_status = "轻微滞后"
        else:
            risk_level = "low"
            schedule_status = "正常" if spi <= 1.05 else "提前"

        return SPIAnalysis(
            overall_spi=spi,
            risk_level=risk_level,
            variance_days=data.get("variance_days", 0),
            earned_value=data.get("earned_value", 0),
            planned_value=data.get("planned_value", 0),
            schedule_status=schedule_status
        )

    def _build_delayed_tasks(self, data: List[Dict]) -> List[DelayedTask]:
        """构建延期任务列表（对齐 get_delayed_tasks 返回结构）"""
        return [DelayedTask(
            task_id=task.get("task_id", ""),
            task_name=task.get("task_name", ""),
            planned_progress=task.get("planned_progress", 0),
            actual_progress=task.get("actual_progress", 0),
            spi=task.get("spi") if task.get("spi") is not None else 1,
            delay_days=0,
            planned_end="",
            is_critical=task.get("is_critical_path", False),
            responsible="",
            delay_reason=task.get("reason", "")
        ) for task in data]

    def _build_critical_path(self, data: List[Dict]) -> List[CriticalPathTask]:
        """构建关键路径任务"""
        return [CriticalPathTask(
            task_id=task.get("task_id", ""),
            task_name=task.get("task_name", ""),
            planned_start=task.get("planned_start", ""),
            planned_end=task.get("planned_end", ""),
            actual_progress=task.get("actual_progress", 0),
            spi=task.get("spi", 1),
            status=task.get("status", ""),
            is_delayed=task.get("is_delayed", False),
            slack_days=task.get("slack_days", 0)
        ) for task in data]

    def _assess_critical_path_status(self, tasks: List[CriticalPathTask]) -> str:
        """评估关键路径状态"""
        delayed_count = len([t for t in tasks if t.is_delayed])
        if delayed_count >= 3:
            return "critical"
        elif delayed_count >= 1:
            return "warning"
        return "normal"

    def _build_trends(self, data: Dict) -> List[ProgressTrend]:
        """构建趋势数据（analyze_progress_trend 仅返回聚合指标，无逐期序列）"""
        return []

    def _map_trend_direction(self, trend: str) -> str:
        """将工具的中文趋势映射为方向标识"""
        mapping = {"恶化": "deteriorating", "好转": "improving", "改善": "improving", "平稳": "stable"}
        return mapping.get(trend, "stable")

    def _build_prediction(self, data: Dict) -> CompletionPrediction:
        """构建预测结果（对齐 predict_completion_time 返回结构）"""
        delay_days = data.get("predicted_delay_days", 0)
        confidence_map = {"高": 0.9, "中": 0.6, "低": 0.3}
        confidence = data.get("prediction_confidence", "")
        return CompletionPrediction(
            predicted_end_date="",
            original_end_date=data.get("planned_end_date", "") or "",
            delay_days=delay_days,
            confidence=confidence_map.get(confidence, 0.0),
            method="SPI",
            will_delay=delay_days > 0
        )

    def _build_bottlenecks(self, data: List[Dict]) -> List[Bottleneck]:
        """构建瓶颈分析（identify_bottlenecks 返回任务级列表）"""
        impact_map = {"高": "high", "中": "medium", "低": "low"}
        return [Bottleneck(
            bottleneck_type="关键路径任务",
            description=b.get("reason", ""),
            affected_tasks=[b.get("task_id", "")],
            impact_level=impact_map.get(b.get("impact", ""), "medium"),
            recommendation=b.get("recommendation", "")
        ) for b in data]

    def _generate_suggestions(self, result: ProgressAnalysisResult) -> List[str]:
        """生成进度建议"""
        suggestions = []

        # 基于SPI
        if result.spi_analysis.risk_level == "critical":
            suggestions.append("🔴 紧急：进度严重滞后，建议立即召开进度专项会议")
        elif result.spi_analysis.risk_level == "high":
            suggestions.append("🟡 警告：进度明显滞后，需要加强管控")

        # 基于关键路径
        if result.critical_path_status == "critical":
            suggestions.append("⚠️ 关键路径多任务延期，可能影响总工期")

        # 基于延期任务
        if result.critical_delayed_count > 0:
            suggestions.append(f"📌 关键任务延期{result.critical_delayed_count}个，需重点关注")

        # 基于资源
        if result.resource_status == "紧张":
            suggestions.append("👥 资源负荷较重，考虑增加人员或调整计划")

        if not suggestions:
            suggestions.append("✅ 项目进度正常，继续保持")

        return suggestions

    async def _generate_ai_insights(self, result: ProgressAnalysisResult) -> List[str]:
        """生成AI洞察"""
        try:
            context = f"""
            项目进度分析结果：
            - 整体进度: {result.overview.overall_progress}%
            - SPI: {result.spi_analysis.overall_spi}
            - 延期任务: {result.delayed_count}个
            - 关键任务延期: {result.critical_delayed_count}个
            - 趋势: {result.trend_direction}
            """
            query = "基于以上进度分析结果，请提供专业的进度管控建议"
            rag_result = await run_rag(query, extra_context=context)
            if rag_result and "answer" in rag_result:
                insights = rag_result["answer"].split("\n")
                return [i.strip() for i in insights if i.strip()]
            return ["建议持续监控进度执行情况"]
        except Exception as e:
            logger.warning(f"AI洞察生成失败: {e}")
            return []

    def _start_workflow(self, project_id: str, workflow_type: str) -> Optional[AgentWorkflowLog]:
        """开始工作流日志"""
        try:
            log = AgentWorkflowLog(
                project_id=project_id, workflow_type=workflow_type,
                start_time=datetime.now(), status="running",
                input_params=json.dumps({"project_id": project_id})
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return log
        except Exception as e:
            logger.warning(f"记录工作流开始失败: {e}")
            return None

    def _complete_workflow(self, log: Optional[AgentWorkflowLog], result: Any, start_time: datetime):
        """完成工作流日志"""
        if log:
            try:
                log.end_time = datetime.now()
                log.status = "completed"
                summary = {
                    "spi": result.spi_analysis.overall_spi if hasattr(result, 'spi_analysis') else 0,
                    "delayed_count": result.delayed_count if hasattr(result, 'delayed_count') else 0
                }
                log.output_result = json.dumps(summary)
                self.db.commit()
            except Exception as e:
                logger.warning(f"记录工作流完成失败: {e}")

    def _fail_workflow(self, log: Optional[AgentWorkflowLog], error: str):
        """记录工作流失败"""
        if log:
            try:
                log.end_time = datetime.now()
                log.status = "failed"
                log.error_message = error[:1000]
                self.db.commit()
            except Exception as e:
                logger.warning(f"记录工作流失败状态失败: {e}")


def get_progress_agent(db: Session) -> ProgressAnalysisAgent:
    """工厂函数：创建进度分析Agent实例"""
    return ProgressAnalysisAgent(db)