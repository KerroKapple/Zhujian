"""
周报生成Agent
==============

📚 模块说明：
- 自动化生成项目周报
- 编排进度、成本、安全三大工具模块
- 结合RAG检索相关文档内容
- 输出结构化周报（支持Markdown/JSON）

🎯 核心功能：
1. 数据采集：调用各工具获取指标数据
2. 智能分析：识别关键问题和风险
3. 建议生成：基于RAG生成改进建议
4. 报告输出：生成结构化周报文档

💡 使用方式：
    from agents.weekly_report_agent import WeeklyReportAgent

    agent = WeeklyReportAgent(db)
    report = await agent.generate_report("P001")
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from sqlalchemy.orm import Session
from loguru import logger

# 导入工具模块
from tools.progress_tools import ProgressTools, get_progress_tools
from tools.cost_tools import CostTools, get_cost_tools
from tools.safety_tools import SafetyTools, get_safety_tools
from tools.rag_tool import run_rag

# 导入数据模型
from models.project import AgentWorkflowLog


class ReportFormat(str, Enum):
    """报告输出格式"""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class RiskLevel(str, Enum):
    """风险等级"""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class ProgressSection:
    """进度板块数据"""
    overall_progress: float = 0.0
    planned_progress: float = 0.0
    variance: float = 0.0
    spi: float = 1.0
    risk_level: str = "green"
    total_tasks: int = 0
    completed_tasks: int = 0
    delayed_tasks: int = 0
    critical_delayed: int = 0
    trend: str = "平稳"
    delayed_task_list: List[Dict] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


@dataclass
class CostSection:
    """成本板块数据"""
    total_budget: float = 0.0
    total_actual: float = 0.0
    variance: float = 0.0
    variance_rate: float = 0.0
    cpi: float = 1.0
    risk_level: str = "green"
    budget_usage_rate: float = 0.0
    category_breakdown: Dict[str, Dict] = field(default_factory=dict)
    overrun_items: List[Dict] = field(default_factory=list)
    trend: str = "平稳"
    highlights: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


@dataclass
class SafetySection:
    """安全板块数据"""
    total_checks: int = 0
    total_defects: int = 0
    high_level_defects: int = 0
    open_defects: int = 0
    closure_rate: float = 100.0
    pass_rate: float = 100.0
    risk_level: str = "green"
    frequent_issues: List[Dict] = field(default_factory=list)
    open_defect_list: List[Dict] = field(default_factory=list)
    trend: str = "平稳"
    highlights: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """周报数据结构"""
    # 基本信息
    project_id: str = ""
    project_name: str = ""
    report_date: str = ""
    report_period: str = ""
    generated_at: str = ""

    # 三大板块
    progress: ProgressSection = field(default_factory=ProgressSection)
    cost: CostSection = field(default_factory=CostSection)
    safety: SafetySection = field(default_factory=SafetySection)

    # 综合评估
    overall_risk_level: str = "green"
    overall_score: float = 100.0

    # 重点关注事项
    key_risks: List[Dict] = field(default_factory=list)
    action_items: List[Dict] = field(default_factory=list)

    # 下周计划
    next_week_plans: List[str] = field(default_factory=list)

    # RAG生成的建议
    ai_suggestions: List[str] = field(default_factory=list)


class WeeklyReportAgent:
    """
    周报生成Agent

    职责：
    - 编排多个工具模块
    - 聚合分析数据
    - 生成结构化周报

    工作流程：
    1. 初始化工具实例
    2. 并行采集各模块数据
    3. 综合分析风险等级
    4. 调用RAG生成建议
    5. 组装最终报告
    """

    def __init__(self, db: Session):
        """
        初始化Agent

        参数:
            db: 数据库会话
        """
        self.db = db

        # 初始化三大工具模块
        self.progress_tools = get_progress_tools(db)
        self.cost_tools = get_cost_tools(db)
        self.safety_tools = get_safety_tools(db)

        logger.info("WeeklyReportAgent 初始化完成")

    async def generate_report(
            self,
            project_id: str,
            report_format: ReportFormat = ReportFormat.MARKDOWN,
            include_ai_suggestions: bool = True
    ) -> Dict[str, Any]:
        """
        生成项目周报

        参数:
            project_id: 项目ID
            report_format: 输出格式（markdown/json/html）
            include_ai_suggestions: 是否包含AI建议

        返回:
            包含报告内容和元数据的字典
        """
        start_time = datetime.now()
        workflow_log = None

        try:
            # 记录工作流开始
            workflow_log = self._start_workflow(project_id)

            logger.info(f"开始生成项目 {project_id} 的周报")

            # Step 1: 采集各模块数据
            report = WeeklyReport(
                project_id=project_id,
                report_date=date.today().isoformat(),
                report_period=self._get_report_period(),
                generated_at=datetime.now().isoformat()
            )

            # Step 2: 采集进度数据
            report.progress = await self._collect_progress_data(project_id)

            # Step 3: 采集成本数据
            report.cost = await self._collect_cost_data(project_id)

            # Step 4: 采集安全数据
            report.safety = await self._collect_safety_data(project_id)

            # Step 5: 获取项目基本信息
            overview = self.progress_tools.get_project_overview(project_id)
            report.project_name = overview.get("project_name", "未知项目")

            # Step 6: 综合风险评估
            report.overall_risk_level, report.overall_score = self._evaluate_overall_risk(report)

            # Step 7: 汇总关键风险
            report.key_risks = self._collect_key_risks(report)

            # Step 8: 生成行动项
            report.action_items = self._generate_action_items(report)

            # Step 9: 生成下周计划
            report.next_week_plans = self._generate_next_week_plans(report)

            # Step 10: AI建议（可选）
            if include_ai_suggestions:
                report.ai_suggestions = await self._generate_ai_suggestions(project_id, report)

            # Step 11: 格式化输出
            if report_format == ReportFormat.MARKDOWN:
                output = self._format_markdown(report)
            elif report_format == ReportFormat.HTML:
                output = self._format_html(report)
            else:
                output = asdict(report)

            # 记录工作流成功
            self._complete_workflow(workflow_log, output, start_time)

            logger.info(f"项目 {project_id} 周报生成完成")

            return {
                "success": True,
                "project_id": project_id,
                "format": report_format.value,
                "report": output,
                "metadata": {
                    "generated_at": report.generated_at,
                    "overall_risk": report.overall_risk_level,
                    "overall_score": report.overall_score,
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            }

        except Exception as e:
            logger.error(f"生成周报失败: {str(e)}")
            self._fail_workflow(workflow_log, str(e))
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e)
            }

    # =========================================
    # 数据采集方法
    # =========================================

    async def _collect_progress_data(self, project_id: str) -> ProgressSection:
        """采集进度数据"""
        section = ProgressSection()

        try:
            # 获取进度概览
            overview = self.progress_tools.get_project_overview(project_id)
            section.total_tasks = overview.get("total_tasks", 0)
            section.completed_tasks = overview.get("completed_tasks", 0)
            section.delayed_tasks = overview.get("delayed_tasks", 0)
            section.overall_progress = overview.get("overall_progress", 0)

            # 获取进度状态
            status = self.progress_tools.get_progress_status(project_id)
            section.spi = status.get("overall_spi", 1.0) or 1.0
            section.variance = status.get("variance", 0)
            section.risk_level = status.get("risk_level", "green")
            section.planned_progress = status.get("avg_planned_progress", 0)

            # 获取延期任务
            delayed = self.progress_tools.get_delayed_tasks(project_id)
            section.delayed_task_list = delayed[:5]  # 取前5个

            # 获取关键路径延期
            critical = self.progress_tools.get_critical_path_tasks(project_id)
            section.critical_delayed = len([t for t in critical if t.get("is_delayed", False)])

            # 获取趋势
            trend = self.progress_tools.analyze_progress_trend(project_id, days=14)
            section.trend = trend.get("trend", "平稳")

            # 生成亮点和问题
            section.highlights, section.issues = self._analyze_progress_highlights(section)

        except Exception as e:
            logger.warning(f"采集进度数据异常: {e}")

        return section

    async def _collect_cost_data(self, project_id: str) -> CostSection:
        """采集成本数据"""
        section = CostSection()

        try:
            # 获取成本概览
            overview = self.cost_tools.get_cost_overview(project_id)
            section.total_budget = overview.get("total_budget", 0)
            section.total_actual = overview.get("total_actual", 0)
            section.variance = overview.get("variance", 0)
            section.variance_rate = overview.get("variance_rate", 0)
            section.cpi = overview.get("cpi", 1.0) or 1.0
            section.risk_level = overview.get("risk_level", "green")
            section.budget_usage_rate = overview.get("budget_usage_rate", 0)

            # 获取分类统计（get_cost_by_category 在 categories 键下返回各类别 dict）
            by_category = self.cost_tools.get_cost_by_category(project_id)
            section.category_breakdown = {
                k: v for k, v in by_category.get("categories", {}).items()
                if isinstance(v, dict)
            }

            # 获取超支项
            overruns = self.cost_tools.identify_cost_overruns(project_id)
            section.overrun_items = overruns[:5]  # 取前5个

            # 获取趋势
            trend = self.cost_tools.analyze_cost_trend(project_id, months=1)
            section.trend = trend.get("trend", "平稳")

            # 生成亮点和问题
            section.highlights, section.issues = self._analyze_cost_highlights(section)

        except Exception as e:
            logger.warning(f"采集成本数据异常: {e}")

        return section

    async def _collect_safety_data(self, project_id: str) -> SafetySection:
        """采集安全数据"""
        section = SafetySection()

        try:
            # 获取安全概览
            overview = self.safety_tools.get_safety_overview(project_id, days=7)
            section.total_checks = overview.get("total_checks", 0)
            section.total_defects = overview.get("total_defects", 0)
            section.high_level_defects = overview.get("high_level_defects", 0)
            section.open_defects = overview.get("open_defects", 0)
            section.closure_rate = overview.get("closure_rate", 100)
            section.pass_rate = overview.get("pass_rate", 100)
            section.risk_level = overview.get("risk_level", "green")

            # 获取频发问题
            frequent = self.safety_tools.identify_frequent_issues(project_id, days=30)
            section.frequent_issues = frequent[:3]  # 取前3个

            # 获取未关闭问题
            open_defects = self.safety_tools.get_open_defects(project_id)
            section.open_defect_list = open_defects[:5]  # 取前5个

            # 获取趋势（analyze_safety_trend 返回 monthly_stats）
            trend = self.safety_tools.analyze_safety_trend(project_id, months=1)
            monthly_stats = trend.get("monthly_stats", {})
            if monthly_stats:
                ordered = [monthly_stats[m] for m in sorted(monthly_stats.keys())]
                if len(ordered) >= 2:
                    if ordered[-1].get("total", 0) > ordered[0].get("total", 0) * 1.2:
                        section.trend = "恶化"
                    elif ordered[-1].get("total", 0) < ordered[0].get("total", 0) * 0.8:
                        section.trend = "好转"
                    else:
                        section.trend = "平稳"

            # 生成亮点和问题
            section.highlights, section.issues = self._analyze_safety_highlights(section)

        except Exception as e:
            logger.warning(f"采集安全数据异常: {e}")

        return section

    # =========================================
    # 分析方法
    # =========================================

    def _analyze_progress_highlights(self, section: ProgressSection) -> tuple:
        """分析进度亮点和问题"""
        highlights = []
        issues = []

        # 亮点
        if section.spi >= 1.05:
            highlights.append(f"进度超前，SPI={section.spi:.2f}")
        if section.completed_tasks > 0:
            completion_rate = section.completed_tasks / section.total_tasks * 100 if section.total_tasks > 0 else 0
            if completion_rate >= 80:
                highlights.append(f"任务完成率高达{completion_rate:.1f}%")

        # 问题
        if section.delayed_tasks > 0:
            issues.append(f"存在{section.delayed_tasks}个延期任务")
        if section.critical_delayed > 0:
            issues.append(f"关键路径有{section.critical_delayed}个任务延期，影响整体工期")
        if section.spi < 0.85:
            issues.append(f"进度严重滞后，SPI={section.spi:.2f}")

        return highlights, issues

    def _analyze_cost_highlights(self, section: CostSection) -> tuple:
        """分析成本亮点和问题"""
        highlights = []
        issues = []

        # 亮点
        if section.cpi >= 1.05:
            highlights.append(f"成本控制良好，CPI={section.cpi:.2f}")
        if section.variance < 0:
            highlights.append(f"实际支出低于计划{abs(section.variance_rate):.1f}%")

        # 问题
        if section.cpi < 0.85:
            issues.append(f"成本严重超支，CPI={section.cpi:.2f}")
        if section.variance_rate > 10:
            issues.append(f"成本偏差率{section.variance_rate:.1f}%，超出预警线")
        if section.overrun_items:
            top_overrun = section.overrun_items[0] if section.overrun_items else None
            if top_overrun:
                issues.append(f"{top_overrun.get('item', '未知项目')}超支严重")

        return highlights, issues

    def _analyze_safety_highlights(self, section: SafetySection) -> tuple:
        """分析安全亮点和问题"""
        highlights = []
        issues = []

        # 亮点
        if section.pass_rate >= 95:
            highlights.append(f"安全检查合格率{section.pass_rate:.1f}%")
        if section.closure_rate >= 90:
            highlights.append(f"问题整改及时，关闭率{section.closure_rate:.1f}%")
        if section.high_level_defects == 0:
            highlights.append("本周无高级别安全隐患")

        # 问题
        if section.high_level_defects > 0:
            issues.append(f"发现{section.high_level_defects}个高级别安全隐患")
        if section.open_defects > 5:
            issues.append(f"存在{section.open_defects}个未关闭问题")
        if section.frequent_issues:
            top_issue = section.frequent_issues[0]
            issues.append(f"'{top_issue.get('defect_type', '未知')}' 问题频发")

        return highlights, issues

    def _evaluate_overall_risk(self, report: WeeklyReport) -> tuple:
        """
        综合风险评估

        返回: (风险等级, 综合评分)
        """
        # 各模块权重
        weights = {"progress": 0.4, "cost": 0.35, "safety": 0.25}

        # 风险等级映射分数
        level_scores = {"green": 100, "yellow": 70, "red": 40}

        # 计算加权分数
        progress_score = level_scores.get(report.progress.risk_level, 70)
        cost_score = level_scores.get(report.cost.risk_level, 70)
        safety_score = level_scores.get(report.safety.risk_level, 70)

        overall_score = (
                progress_score * weights["progress"] +
                cost_score * weights["cost"] +
                safety_score * weights["safety"]
        )

        # 确定综合风险等级
        if overall_score >= 85:
            overall_level = "green"
        elif overall_score >= 60:
            overall_level = "yellow"
        else:
            overall_level = "red"

        # 特殊情况：任一模块为红色，整体至少为黄色
        if any([
            report.progress.risk_level == "red",
            report.cost.risk_level == "red",
            report.safety.risk_level == "red"
        ]):
            if overall_level == "green":
                overall_level = "yellow"

        return overall_level, round(overall_score, 1)

    def _collect_key_risks(self, report: WeeklyReport) -> List[Dict]:
        """汇总关键风险"""
        risks = []

        # 进度风险
        if report.progress.risk_level != "green":
            risks.append({
                "category": "进度",
                "level": report.progress.risk_level,
                "description": f"SPI={report.progress.spi:.2f}，存在{report.progress.delayed_tasks}个延期任务",
                "impact": "可能影响项目整体工期"
            })

        # 成本风险
        if report.cost.risk_level != "green":
            risks.append({
                "category": "成本",
                "level": report.cost.risk_level,
                "description": f"CPI={report.cost.cpi:.2f}，成本偏差{report.cost.variance_rate:.1f}%",
                "impact": "可能导致预算超支"
            })

        # 安全风险
        if report.safety.risk_level != "green":
            risks.append({
                "category": "安全",
                "level": report.safety.risk_level,
                "description": f"存在{report.safety.high_level_defects}个高级别隐患，{report.safety.open_defects}个未关闭问题",
                "impact": "可能引发安全事故"
            })

        # 按风险等级排序
        level_order = {"red": 0, "yellow": 1, "green": 2}
        risks.sort(key=lambda x: level_order.get(x["level"], 2))

        return risks

    def _generate_action_items(self, report: WeeklyReport) -> List[Dict]:
        """生成行动项"""
        items = []

        # 进度相关行动项
        if report.progress.delayed_tasks > 0:
            items.append({
                "category": "进度",
                "priority": "高" if report.progress.risk_level == "red" else "中",
                "action": "召开进度协调会，分析延期原因并制定赶工计划",
                "owner": "项目经理",
                "deadline": "本周内"
            })

        if report.progress.critical_delayed > 0:
            items.append({
                "category": "进度",
                "priority": "高",
                "action": "重点关注关键路径任务，增加资源投入",
                "owner": "项目经理",
                "deadline": "立即"
            })

        # 成本相关行动项
        if report.cost.variance_rate > 5:
            items.append({
                "category": "成本",
                "priority": "高" if report.cost.risk_level == "red" else "中",
                "action": "组织成本分析会，审查超支原因",
                "owner": "商务经理",
                "deadline": "本周内"
            })

        # 安全相关行动项
        if report.safety.high_level_defects > 0:
            items.append({
                "category": "安全",
                "priority": "高",
                "action": "立即整改高级别安全隐患，暂停相关作业",
                "owner": "安全主管",
                "deadline": "立即"
            })

        if report.safety.open_defects > 5:
            items.append({
                "category": "安全",
                "priority": "中",
                "action": "制定整改计划，限期关闭未处理问题",
                "owner": "安全主管",
                "deadline": "3天内"
            })

        return items

    def _generate_next_week_plans(self, report: WeeklyReport) -> List[str]:
        """生成下周计划"""
        plans = []

        # 基础计划
        plans.append("继续推进各项施工任务")

        # 根据风险生成针对性计划
        if report.progress.delayed_tasks > 0:
            plans.append(f"重点赶工{report.progress.delayed_tasks}个延期任务")

        if report.cost.risk_level != "green":
            plans.append("加强成本管控，控制非必要支出")

        if report.safety.open_defects > 0:
            plans.append(f"完成{min(report.safety.open_defects, 5)}项安全整改")

        plans.append("做好安全检查，确保施工安全")

        return plans

    async def _generate_ai_suggestions(
            self,
            project_id: str,
            report: WeeklyReport
    ) -> List[str]:
        """
        调用RAG生成AI建议

        基于当前项目状态，检索相关文档生成改进建议
        """
        suggestions = []

        try:
            # 构建查询上下文
            context = f"""
            项目当前状态：
            - 进度：SPI={report.progress.spi:.2f}，{report.progress.delayed_tasks}个延期任务
            - 成本：CPI={report.cost.cpi:.2f}，偏差率{report.cost.variance_rate:.1f}%
            - 安全：{report.safety.high_level_defects}个高级别隐患，{report.safety.open_defects}个未关闭问题

            请基于以上情况，给出改进建议。
            """

            # 进度建议
            if report.progress.risk_level != "green":
                rag_result = await run_rag(
                    query="项目进度延期如何赶工和加速",
                    top_k=3,
                    project_id=project_id,
                    extra_context=context
                )
                if rag_result.get("answer"):
                    suggestions.append(f"【进度建议】{rag_result['answer'][:200]}")

            # 成本建议
            if report.cost.risk_level != "green":
                rag_result = await run_rag(
                    query="项目成本超支控制措施",
                    top_k=3,
                    project_id=project_id,
                    extra_context=context
                )
                if rag_result.get("answer"):
                    suggestions.append(f"【成本建议】{rag_result['answer'][:200]}")

            # 安全建议
            if report.safety.risk_level != "green":
                rag_result = await run_rag(
                    query="施工安全隐患整改措施",
                    top_k=3,
                    project_id=project_id,
                    extra_context=context
                )
                if rag_result.get("answer"):
                    suggestions.append(f"【安全建议】{rag_result['answer'][:200]}")

        except Exception as e:
            logger.warning(f"生成AI建议失败: {e}")
            suggestions.append("（AI建议生成失败，请稍后重试）")

        return suggestions

    # =========================================
    # 格式化输出方法
    # =========================================

    def _format_markdown(self, report: WeeklyReport) -> str:
        """格式化为Markdown"""
        md = []

        # 标题
        md.append(f"# {report.project_name} 项目周报")
        md.append(f"\n**报告日期**：{report.report_date}")
        md.append(f"\n**报告周期**：{report.report_period}")
        md.append(f"\n**综合评分**：{report.overall_score}分 | 风险等级：{self._risk_badge(report.overall_risk_level)}")

        # 进度板块
        md.append("\n\n---\n## 一、进度管理")
        md.append(f"\n**风险等级**：{self._risk_badge(report.progress.risk_level)}")
        md.append(f"\n- 整体进度：{report.progress.overall_progress:.1f}%")
        md.append(f"- SPI（进度绩效指数）：{report.progress.spi:.2f}")
        md.append(
            f"- 任务统计：总{report.progress.total_tasks}个，完成{report.progress.completed_tasks}个，延期{report.progress.delayed_tasks}个")
        md.append(f"- 趋势：{report.progress.trend}")

        if report.progress.highlights:
            md.append("\n**亮点**：")
            for h in report.progress.highlights:
                md.append(f"- ✅ {h}")

        if report.progress.issues:
            md.append("\n**问题**：")
            for i in report.progress.issues:
                md.append(f"- ⚠️ {i}")

        # 成本板块
        md.append("\n\n---\n## 二、成本管理")
        md.append(f"\n**风险等级**：{self._risk_badge(report.cost.risk_level)}")
        md.append(f"\n- 总预算：{report.cost.total_budget:,.0f}元")
        md.append(f"- 实际支出：{report.cost.total_actual:,.0f}元")
        md.append(f"- 偏差率：{report.cost.variance_rate:+.1f}%")
        md.append(f"- CPI（成本绩效指数）：{report.cost.cpi:.2f}")
        md.append(f"- 预算消耗率：{report.cost.budget_usage_rate:.1f}%")

        if report.cost.highlights:
            md.append("\n**亮点**：")
            for h in report.cost.highlights:
                md.append(f"- ✅ {h}")

        if report.cost.issues:
            md.append("\n**问题**：")
            for i in report.cost.issues:
                md.append(f"- ⚠️ {i}")

        # 安全板块
        md.append("\n\n---\n## 三、安全管理")
        md.append(f"\n**风险等级**：{self._risk_badge(report.safety.risk_level)}")
        md.append(f"\n- 检查次数：{report.safety.total_checks}次")
        md.append(f"- 发现问题：{report.safety.total_defects}个（高级别{report.safety.high_level_defects}个）")
        md.append(f"- 未关闭问题：{report.safety.open_defects}个")
        md.append(f"- 合格率：{report.safety.pass_rate:.1f}%")
        md.append(f"- 整改关闭率：{report.safety.closure_rate:.1f}%")

        if report.safety.highlights:
            md.append("\n**亮点**：")
            for h in report.safety.highlights:
                md.append(f"- ✅ {h}")

        if report.safety.issues:
            md.append("\n**问题**：")
            for i in report.safety.issues:
                md.append(f"- ⚠️ {i}")

        # 关键风险
        if report.key_risks:
            md.append("\n\n---\n## 四、关键风险")
            for risk in report.key_risks:
                md.append(f"\n### {self._risk_badge(risk['level'])} {risk['category']}风险")
                md.append(f"- **描述**：{risk['description']}")
                md.append(f"- **影响**：{risk['impact']}")

        # 行动项
        if report.action_items:
            md.append("\n\n---\n## 五、行动项")
            md.append("\n| 类别 | 优先级 | 行动 | 责任人 | 期限 |")
            md.append("|------|--------|------|--------|------|")
            for item in report.action_items:
                md.append(
                    f"| {item['category']} | {item['priority']} | {item['action']} | {item['owner']} | {item['deadline']} |")

        # 下周计划
        md.append("\n\n---\n## 六、下周计划")
        for i, plan in enumerate(report.next_week_plans, 1):
            md.append(f"{i}. {plan}")

        # AI建议
        if report.ai_suggestions:
            md.append("\n\n---\n## 七、AI智能建议")
            for suggestion in report.ai_suggestions:
                md.append(f"\n{suggestion}")

        # 页脚
        md.append(f"\n\n---\n*报告生成时间：{report.generated_at}*")

        return "\n".join(md)

    def _format_html(self, report: WeeklyReport) -> str:
        """格式化为HTML"""
        # 简化版HTML输出
        md_content = self._format_markdown(report)
        # 这里可以使用markdown库转换，暂时返回简单HTML
        return f"<html><body><pre>{md_content}</pre></body></html>"

    def _risk_badge(self, level: str) -> str:
        """风险等级徽章"""
        badges = {
            "green": "🟢 正常",
            "yellow": "🟡 关注",
            "red": "🔴 预警"
        }
        return badges.get(level, "⚪ 未知")

    def _get_report_period(self) -> str:
        """获取报告周期"""
        from datetime import timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return f"{week_start.isoformat()} 至 {week_end.isoformat()}"

    # =========================================
    # 工作流日志方法
    # =========================================

    def _start_workflow(self, project_id: str) -> AgentWorkflowLog:
        """开始工作流日志"""
        try:
            log = AgentWorkflowLog(
                project_id=project_id,
                workflow_type="weekly_report",
                start_time=datetime.now(),
                status="running",
                input_params=json.dumps({"project_id": project_id})
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return log
        except Exception as e:
            logger.warning(f"记录工作流开始失败: {e}")
            return None

    def _complete_workflow(
            self,
            log: Optional[AgentWorkflowLog],
            output: Any,
            start_time: datetime
    ):
        """完成工作流日志"""
        if log:
            try:
                log.end_time = datetime.now()
                log.status = "completed"
                # 输出太大时只存储摘要
                if isinstance(output, str) and len(output) > 10000:
                    log.output_result = json.dumps({"summary": "报告生成成功", "length": len(output)})
                else:
                    log.output_result = json.dumps(output) if not isinstance(output, str) else output[:5000]
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


# =========================================
# 工厂函数
# =========================================

def get_weekly_report_agent(db: Session) -> WeeklyReportAgent:
    """工厂函数：创建周报Agent实例"""
    return WeeklyReportAgent(db)