"""
成本分析Agent
==============

📚 模块说明：
- 多维度成本分析与评估
- 预算执行监控与预测
- 成本风险识别与预警
- 成本控制建议生成

🎯 核心功能：
1. 成本概览：预算执行情况、CPI分析
2. 分类统计：按成本类别分析
3. 超支识别：识别超支项目和原因
4. 趋势分析：成本变化趋势
5. 预测分析：最终成本预测
6. 风险预警：成本风险识别
7. 建议生成：基于RAG生成控制建议

💡 使用方式：
    from agents.cost_agent import CostAnalysisAgent, get_cost_agent

    agent = get_cost_agent(db)
    result = await agent.analyze_costs("P001")
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
from tools.cost_tools import CostTools, get_cost_tools
from tools.progress_tools import ProgressTools, get_progress_tools
from tools.rag_tool import run_rag

# 导入数据模型
from models.project import AgentWorkflowLog


class CostRiskLevel(str, Enum):
    """成本风险等级"""
    CRITICAL = "critical"  # 严重超支 (>15%)
    HIGH = "high"  # 高风险 (10-15%)
    MEDIUM = "medium"  # 中风险 (5-10%)
    LOW = "low"  # 低风险 (<5%)


class CostCategory(str, Enum):
    """成本类别"""
    MATERIAL = "material"  # 材料费
    LABOR = "labor"  # 人工费
    EQUIPMENT = "equipment"  # 机械费
    SUBCONTRACT = "subcontract"  # 分包费
    MANAGEMENT = "management"  # 管理费
    OTHER = "other"  # 其他费用


@dataclass
class CostOverview:
    """成本概览"""
    project_id: str = ""
    project_name: str = ""
    total_budget: float = 0.0
    total_actual: float = 0.0
    variance: float = 0.0
    variance_rate: float = 0.0
    cpi: float = 1.0
    budget_usage_rate: float = 0.0
    risk_level: str = "low"


@dataclass
class CategoryCost:
    """分类成本"""
    category: str = ""
    category_name: str = ""
    budget: float = 0.0
    actual: float = 0.0
    variance: float = 0.0
    variance_rate: float = 0.0
    percentage: float = 0.0


@dataclass
class CostOverrun:
    """超支项"""
    item_id: str = ""
    item_name: str = ""
    category: str = ""
    budget: float = 0.0
    actual: float = 0.0
    overrun: float = 0.0
    overrun_rate: float = 0.0
    reason: str = ""
    severity: str = "medium"


@dataclass
class CostTrend:
    """成本趋势"""
    period: str = ""
    budget: float = 0.0
    actual: float = 0.0
    cumulative_budget: float = 0.0
    cumulative_actual: float = 0.0
    cpi: float = 1.0


@dataclass
class CostPrediction:
    """成本预测"""
    predicted_total: float = 0.0
    predicted_variance: float = 0.0
    predicted_variance_rate: float = 0.0
    will_exceed_budget: bool = False
    confidence: float = 0.0
    method: str = ""


@dataclass
class CostRisk:
    """成本风险"""
    risk_id: str = ""
    risk_type: str = ""
    severity: str = ""
    description: str = ""
    impact: float = 0.0
    probability: float = 0.0
    recommendation: str = ""


@dataclass
class CostAnalysisResult:
    """成本分析结果"""
    project_id: str = ""
    project_name: str = ""
    analysis_date: str = ""
    analysis_period: str = ""
    overview: CostOverview = field(default_factory=CostOverview)
    category_costs: List[CategoryCost] = field(default_factory=list)
    overruns: List[CostOverrun] = field(default_factory=list)
    total_overrun: float = 0.0
    overrun_count: int = 0
    trends: List[CostTrend] = field(default_factory=list)
    trend_direction: str = "stable"
    prediction: CostPrediction = field(default_factory=CostPrediction)
    risks: List[CostRisk] = field(default_factory=list)
    risk_count: int = 0
    highest_risk_level: str = "low"
    suggestions: List[str] = field(default_factory=list)
    ai_insights: List[str] = field(default_factory=list)
    success: bool = True
    execution_time: float = 0.0
    error: str = ""


class CostAnalysisAgent:
    """
    成本分析Agent

    职责：
    - 编排成本分析工具
    - 多维度成本评估
    - 生成预警和建议
    """

    THRESHOLDS = {
        "cpi_critical": 0.75,
        "cpi_high": 0.85,
        "cpi_medium": 0.95,
        "variance_rate_critical": 15,
        "variance_rate_high": 10,
        "variance_rate_medium": 5,
        "budget_usage_warning": 80,
        "budget_usage_critical": 95
    }

    def __init__(self, db: Session):
        """初始化Agent"""
        self.db = db
        self.cost_tools = get_cost_tools(db)
        self.progress_tools = get_progress_tools(db)
        logger.info("CostAnalysisAgent 初始化完成")

    async def analyze_costs(
            self,
            project_id: str,
            analysis_months: int = 3,
            include_ai_insights: bool = True
    ) -> Dict[str, Any]:
        """执行全面成本分析"""
        start_time = datetime.now()
        workflow_log = None

        try:
            workflow_log = self._start_workflow(project_id, "cost_analysis")
            logger.info(f"开始项目 {project_id} 成本分析")

            result = CostAnalysisResult(
                project_id=project_id,
                analysis_date=date.today().isoformat(),
                analysis_period=f"最近{analysis_months}个月"
            )

            # Step 1: 获取项目信息
            project_overview = self.progress_tools.get_project_overview(project_id)
            result.project_name = project_overview.get("project_name", "未知项目")

            # Step 2: 成本概览
            overview_data = self.cost_tools.get_cost_overview(project_id)
            result.overview = self._build_cost_overview(project_id, overview_data)

            # Step 3: 分类成本统计
            category_data = self.cost_tools.get_cost_by_category(project_id)
            result.category_costs = self._build_category_costs(category_data)

            # Step 4: 超支识别
            overruns_data = self.cost_tools.identify_cost_overruns(project_id)
            result.overruns = self._build_overruns(overruns_data)
            result.overrun_count = len(result.overruns)
            result.total_overrun = sum(o.overrun for o in result.overruns)

            # Step 5: 趋势分析
            trend_data = self.cost_tools.analyze_cost_trend(project_id, months=analysis_months)
            result.trends = self._build_trends(trend_data)
            result.trend_direction = self._determine_trend_direction(result.trends)

            # Step 6: 成本预测
            prediction_data = self.cost_tools.predict_final_cost(project_id)
            result.prediction = self._build_prediction(prediction_data)

            # Step 7: 风险评估
            risks_data = self.cost_tools.identify_cost_risks(project_id)
            result.risks = self._build_risks(risks_data)
            result.risk_count = len(result.risks)
            result.highest_risk_level = self._get_highest_risk_level(result.risks)

            # Step 8: 控制建议
            result.suggestions = self.cost_tools.get_cost_control_suggestions(project_id)

            # Step 9: AI洞察
            if include_ai_insights:
                result.ai_insights = await self._generate_ai_insights(result)

            result.success = True
            result.execution_time = (datetime.now() - start_time).total_seconds()

            self._complete_workflow(workflow_log, result, start_time)
            logger.info(f"成本分析完成，耗时: {result.execution_time:.2f}秒")

            return asdict(result)

        except Exception as e:
            error_msg = f"成本分析失败: {str(e)}"
            logger.error(error_msg)
            self._fail_workflow(workflow_log, error_msg)
            return {
                "success": False,
                "project_id": project_id,
                "error": error_msg,
                "execution_time": (datetime.now() - start_time).total_seconds()
            }

    async def quick_cost_check(self, project_id: str) -> Dict[str, Any]:
        """快速成本检查"""
        try:
            overview = self.cost_tools.get_cost_overview(project_id)
            cpi = overview.get("cpi", 1)
            variance_rate = abs(overview.get("variance_rate", 0))

            if cpi < self.THRESHOLDS["cpi_critical"] or variance_rate > self.THRESHOLDS["variance_rate_critical"]:
                risk_level = "critical"
            elif cpi < self.THRESHOLDS["cpi_high"] or variance_rate > self.THRESHOLDS["variance_rate_high"]:
                risk_level = "high"
            elif cpi < self.THRESHOLDS["cpi_medium"] or variance_rate > self.THRESHOLDS["variance_rate_medium"]:
                risk_level = "medium"
            else:
                risk_level = "low"

            alerts = []
            if cpi < self.THRESHOLDS["cpi_high"]:
                alerts.append(f"CPI偏低: {cpi:.2f}")
            if variance_rate > self.THRESHOLDS["variance_rate_high"]:
                alerts.append(f"成本偏差: {variance_rate:.1f}%")

            return {
                "success": True,
                "project_id": project_id,
                "check_time": datetime.now().isoformat(),
                "cpi": cpi,
                "variance_rate": variance_rate,
                "budget_usage_rate": overview.get("budget_usage_rate", 0),
                "risk_level": risk_level,
                "alerts": alerts
            }

        except Exception as e:
            return {"success": False, "project_id": project_id, "error": str(e)}

    def _build_cost_overview(self, project_id: str, data: Dict) -> CostOverview:
        """构建成本概览"""
        return CostOverview(
            project_id=project_id,
            project_name=data.get("project_name", ""),
            total_budget=data.get("total_budget", 0),
            total_actual=data.get("total_actual", 0),
            variance=data.get("variance", 0),
            variance_rate=data.get("variance_rate", 0),
            cpi=data.get("cpi", 1),
            budget_usage_rate=data.get("budget_usage_rate", 0),
            risk_level=data.get("risk_level", "low")
        )

    def _build_category_costs(self, data: Dict) -> List[CategoryCost]:
        """构建分类成本列表（对齐 get_cost_by_category：键为中文类别，金额键为 planned）"""
        categories = data.get("categories", {})
        result = []
        for cat_key, cat_data in categories.items():
            planned = cat_data.get("planned", 0)
            actual = cat_data.get("actual", 0)
            result.append(CategoryCost(
                category=cat_key,
                category_name=cat_key,
                budget=planned,
                actual=actual,
                variance=cat_data.get("variance", 0),
                variance_rate=cat_data.get("variance_rate", 0),
                percentage=round(actual / planned * 100, 2) if planned > 0 else 0
            ))
        return result

    def _build_overruns(self, data: List[Dict]) -> List[CostOverrun]:
        """构建超支项列表（对齐 identify_cost_overruns 返回结构）"""
        result = []
        for item in data:
            overrun_rate = item.get("variance_rate", 0)
            severity = "critical" if overrun_rate > 15 else "high" if overrun_rate > 10 else "medium" if overrun_rate > 5 else "low"
            result.append(CostOverrun(
                item_id=str(item.get("cost_id", "")),
                item_name=item.get("item", ""),
                category=item.get("category", ""),
                budget=item.get("planned", 0),
                actual=item.get("actual", 0),
                overrun=item.get("variance", 0),
                overrun_rate=overrun_rate,
                reason=item.get("severity", ""),
                severity=severity
            ))
        return result

    def _build_trends(self, data: Dict) -> List[CostTrend]:
        """构建趋势数据（analyze_cost_trend 的 monthly_data 是按月键控的 dict）"""
        monthly_data = data.get("monthly_data", {})
        trends = []
        cumulative_budget = 0.0
        cumulative_actual = 0.0
        for period in sorted(monthly_data.keys()):
            stats = monthly_data[period]
            planned = stats.get("planned", 0)
            actual = stats.get("actual", 0)
            cumulative_budget += planned
            cumulative_actual += actual
            cpi = round(planned / actual, 3) if actual > 0 else 1.0
            trends.append(CostTrend(
                period=period,
                budget=planned,
                actual=actual,
                cumulative_budget=cumulative_budget,
                cumulative_actual=cumulative_actual,
                cpi=cpi
            ))
        return trends

    def _determine_trend_direction(self, trends: List[CostTrend]) -> str:
        """判断趋势方向"""
        if len(trends) < 2:
            return "stable"
        recent_cpis = [t.cpi for t in trends[-3:]]
        if len(recent_cpis) >= 2:
            if recent_cpis[-1] > recent_cpis[0] + 0.05:
                return "improving"
            elif recent_cpis[-1] < recent_cpis[0] - 0.05:
                return "deteriorating"
        return "stable"

    def _build_prediction(self, data: Dict) -> CostPrediction:
        """构建预测结果（对齐 predict_final_cost 返回结构）"""
        confidence = data.get("confidence", 0)
        confidence_map = {"高": 0.9, "中等": 0.6, "低": 0.3}
        return CostPrediction(
            predicted_total=data.get("predicted_final_cost", 0),
            predicted_variance=data.get("predicted_overrun", 0),
            predicted_variance_rate=data.get("predicted_overrun_rate", 0),
            will_exceed_budget=data.get("will_exceed_budget", False),
            confidence=confidence_map.get(confidence, 0.0) if isinstance(confidence, str) else confidence,
            method="EAC"
        )

    def _build_risks(self, data: List[Dict]) -> List[CostRisk]:
        """构建风险列表"""
        return [CostRisk(
            risk_id=f"CR{i + 1:03d}",
            risk_type=risk.get("risk_type", ""),
            severity=risk.get("severity", "medium"),
            description=risk.get("description", ""),
            impact=risk.get("impact", 0),
            probability=risk.get("probability", 0.5),
            recommendation=risk.get("recommendation", "")
        ) for i, risk in enumerate(data)]

    def _get_highest_risk_level(self, risks: List[CostRisk]) -> str:
        """获取最高风险等级"""
        level_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        if not risks:
            return "low"
        return min([r.severity for r in risks], key=lambda x: level_priority.get(x, 3))

    async def _generate_ai_insights(self, result: CostAnalysisResult) -> List[str]:
        """生成AI洞察"""
        try:
            context = f"""
            项目成本分析结果：
            - CPI: {result.overview.cpi}
            - 成本偏差率: {result.overview.variance_rate}%
            - 预算使用率: {result.overview.budget_usage_rate}%
            - 超支项数量: {result.overrun_count}
            - 风险数量: {result.risk_count}
            - 趋势: {result.trend_direction}
            """
            query = "基于以上成本分析结果，请提供专业的成本控制建议"
            rag_result = await run_rag(query, extra_context=context)
            if rag_result and "answer" in rag_result:
                insights = rag_result["answer"].split("\n")
                return [i.strip() for i in insights if i.strip()]
            return ["建议持续监控成本执行情况", "关注超支项的整改进度"]
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
                    "cpi": result.overview.cpi if hasattr(result, 'overview') else 0,
                    "risk_level": result.highest_risk_level if hasattr(result, 'highest_risk_level') else "unknown",
                    "overrun_count": result.overrun_count if hasattr(result, 'overrun_count') else 0
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


def get_cost_agent(db: Session) -> CostAnalysisAgent:
    """工厂函数：创建成本分析Agent实例"""
    return CostAnalysisAgent(db)