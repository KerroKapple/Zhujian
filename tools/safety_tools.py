"""
安全分析工具库（完整注释版）
位置: F:\\LLM\\Enterprise_RAG\\tools\\safety_tools.py

📚 模块说明：
- 提供9个专业的安全分析工具
- 供SafetyAnalysisAgent调用
- 支持安全检查统计、隐患识别、整改计划

🔧 工具列表：
1. get_safety_overview        - 安全概览（检查次数、缺陷统计）
2. identify_frequent_issues   - 识别频发问题
3. analyze_defect_distribution - 缺陷分布分析
4. get_open_defects           - 获取未关闭问题
5. analyze_safety_trend       - 安全趋势分析
6. compare_with_standard      - 对标行业标准
7. identify_safety_risks      - 识别安全风险
8. get_improvement_suggestions - 生成改进建议
9. get_rectification_plan     - 生成整改计划

💡 关键概念：
- 缺陷等级: high(高)/medium(中)/low(低)
- 检查类型: 日检/周检/月检/专项检查
- 合格率 = (总检查次数 - 有缺陷检查次数) / 总检查次数
"""

from typing import Dict, List, Optional, Any
from datetime import date, timedelta
from collections import Counter
from sqlalchemy.orm import Session

from models.project import SafetyRecord
from services.project.project_service import SafetyService


class SafetyTools:
    """安全分析工具集"""

    def __init__(self, db: Session):
        """初始化工具实例"""
        self.db = db
        self.safety_service = SafetyService(db)

    def get_safety_overview(self, project_id: str, days: int = 30) -> Dict[str, Any]:
        """
        工具1: 获取安全概览

        功能:
            - 统计最近N天的安全检查次数
            - 统计缺陷数量和等级分布
            - 计算合格率
            - 判定风险等级

        参数:
            project_id: 项目ID
            days: 分析时间窗口（默认30天）

        返回:
            - total_checks: 检查次数
            - total_defects: 缺陷总数
            - high_level_defects: 高级别缺陷数
            - open_defects: 未关闭问题数
            - pass_rate: 合格率（%）
            - risk_level: green/yellow/red

        风险等级判定:
            - Red: 高级别缺陷>5 或 未关闭问题>10
            - Yellow: 高级别缺陷>2 或 未关闭问题>5
            - Green: 其他情况
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取指定时间段内的安全记录
        records = self.safety_service.get_safety_records_by_project(
            project_id,
            start_date=start_date,
            end_date=end_date
        )

        # 统计检查次数（按检查日期去重）
        check_dates = set(r.check_date for r in records if r.check_date)
        total_checks = len(check_dates)

        # 统计缺陷数量
        total_defects = len(records)
        high_defects = len([r for r in records if r.defect_level == 'high'])
        medium_defects = len([r for r in records if r.defect_level == 'medium'])
        low_defects = len([r for r in records if r.defect_level == 'low'])

        # 统计问题状态
        open_defects = len([r for r in records if r.status == 'open'])
        closed_defects = len([r for r in records if r.status == 'closed'])

        # 计算关闭率
        closure_rate = (closed_defects / total_defects * 100) if total_defects > 0 else 100

        # 计算合格率（简化：有缺陷的检查日为不合格）
        defect_days = len(set(r.check_date for r in records))
        pass_rate = ((total_checks - defect_days) / total_checks * 100) if total_checks > 0 else 100

        # 风险等级判定
        if high_defects > 5 or open_defects > 10:
            risk_level = "red"
            risk_description = "存在多个高级别隐患或大量未关闭问题"
        elif high_defects > 2 or open_defects > 5:
            risk_level = "yellow"
            risk_description = "存在安全隐患，需要关注"
        else:
            risk_level = "green"
            risk_description = "安全状况良好"

        return {
            "project_id": project_id,
            "analysis_period": f"{start_date} 至 {end_date}",
            "total_checks": total_checks,
            "total_defects": total_defects,
            "high_level_defects": high_defects,
            "medium_level_defects": medium_defects,
            "low_level_defects": low_defects,
            "open_defects": open_defects,
            "closed_defects": closed_defects,
            "closure_rate": round(closure_rate, 2),
            "pass_rate": round(pass_rate, 2),
            "risk_level": risk_level,
            "risk_description": risk_description
        }

    def identify_frequent_issues(self, project_id: str, days: int = 60) -> List[Dict[str, Any]]:
        """
        工具2: 识别频发问题

        功能:
            - 统计各类问题的出现频率
            - 分析问题趋势（上升/下降/平稳）
            - 识别高级别问题占比

        参数:
            project_id: 项目ID
            days: 分析时间窗口（默认60天）

        返回:
            频发问题列表（按出现次数降序），每项包含:
            - defect_type: 问题类型
            - total_count: 总出现次数
            - high_level_count: 高级别次数
            - trend: 趋势（上升/下降/平稳）
            - frequency: 月均频率
            - severity: 严重程度（严重/中等/轻微）

        趋势判定（对比前后两个时段）:
            - 上升: 后半段 > 前半段 × 1.2
            - 下降: 后半段 < 前半段 × 0.8
            - 平稳: 其他情况
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取时间段内的安全记录
        records = self.safety_service.get_safety_records_by_project(
            project_id,
            start_date=start_date,
            end_date=end_date
        )

        # 统计各类型问题的出现次数
        defect_counts = Counter(r.defect_type for r in records if r.defect_type)

        # 计算时间段中点（用于趋势分析）
        mid_date = start_date + timedelta(days=days // 2)

        frequent_issues = []

        # 遍历最常见的10个问题
        for defect_type, count in defect_counts.most_common(10):
            # 计算前后两个时段的出现次数
            first_half = len([r for r in records
                              if r.defect_type == defect_type
                              and r.check_date
                              and start_date <= r.check_date < mid_date])

            second_half = len([r for r in records
                               if r.defect_type == defect_type
                               and r.check_date
                               and mid_date <= r.check_date <= end_date])

            # 判断趋势
            if second_half > first_half * 1.2:
                trend = "上升"  # 后半段明显增加
            elif second_half < first_half * 0.8:
                trend = "下降"  # 后半段明显减少
            else:
                trend = "平稳"  # 变化不大

            # 统计该类型的高级别问题数量
            type_records = [r for r in records if r.defect_type == defect_type]
            high_count = len([r for r in type_records if r.defect_level == 'high'])

            # 判断严重程度（基于高级别问题占比）
            high_ratio = high_count / count if count > 0 else 0
            if high_ratio > 0.3:
                severity = "严重"  # 30%以上是高级别
            elif high_count > 0:
                severity = "中等"  # 有高级别问题
            else:
                severity = "轻微"  # 没有高级别问题

            frequent_issues.append({
                "defect_type": defect_type,
                "total_count": count,
                "high_level_count": high_count,
                "trend": trend,
                "frequency": round(count / days * 30, 1),  # 月均频率
                "severity": severity
            })

        return frequent_issues

    def analyze_defect_distribution(self, project_id: str) -> Dict[str, Any]:
        """
        工具3: 分析缺陷分布

        按多个维度分析缺陷分布情况
        """
        records = self.safety_service.get_safety_records_by_project(project_id)

        if not records:
            return {"message": "没有安全检查记录", "has_data": False}

        # 按等级分布
        by_level = {
            "high": len([r for r in records if r.defect_level == 'high']),
            "medium": len([r for r in records if r.defect_level == 'medium']),
            "low": len([r for r in records if r.defect_level == 'low'])
        }

        # 按状态分布
        by_status = {
            "open": len([r for r in records if r.status == 'open']),
            "closed": len([r for r in records if r.status == 'closed'])
        }

        # 按类型分布（Top 5）
        type_counts = Counter(r.defect_type for r in records if r.defect_type)
        by_type = dict(type_counts.most_common(5))

        return {
            "has_data": True,
            "total_records": len(records),
            "distribution_by_level": by_level,
            "distribution_by_status": by_status,
            "distribution_by_type": by_type
        }

    def get_open_defects(self, project_id: str) -> List[Dict[str, Any]]:
        """
        工具4: 获取未关闭的缺陷

        列出所有待整改的安全问题，按紧急程度排序

        紧急程度判定:
            - 紧急: 高级别问题且存在>7天
            - 重要: 高级别问题 或 存在>14天
            - 一般: 其他情况
        """
        records = self.safety_service.get_open_defects(project_id)

        open_defects = []
        today = date.today()

        for record in records:
            # 计算问题存在时长
            days_open = (today - record.check_date).days if record.check_date else 0

            # 判断紧急程度
            if record.defect_level == 'high' and days_open > 7:
                urgency = "紧急"
            elif record.defect_level == 'high' or days_open > 14:
                urgency = "重要"
            else:
                urgency = "一般"

            open_defects.append({
                "record_id": record.record_id,
                "defect_type": record.defect_type,
                "defect_level": record.defect_level,
                "description": record.defect_description,
                "check_date": record.check_date.isoformat() if record.check_date else None,
                "days_open": days_open,
                "urgency": urgency,
                "checker": record.checker_name
            })

        # 按紧急程度和存在时长排序
        urgency_order = {"紧急": 0, "重要": 1, "一般": 2}
        open_defects.sort(key=lambda x: (urgency_order.get(x['urgency'], 3), -x['days_open']))

        return open_defects

    def analyze_safety_trend(self, project_id: str, months: int = 3) -> Dict[str, Any]:
        """
        工具5: 分析安全趋势（最近N个月）
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)

        records = self.safety_service.get_safety_records_by_project(
            project_id,
            start_date=start_date,
            end_date=end_date
        )

        # 按月统计
        monthly_stats = {}
        for record in records:
            if record.check_date:
                month_key = record.check_date.strftime('%Y-%m')
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {
                        "total": 0, "high": 0, "medium": 0, "low": 0, "checks": set()
                    }
                monthly_stats[month_key]["total"] += 1
                monthly_stats[month_key]["checks"].add(record.check_date)
                if record.defect_level == 'high':
                    monthly_stats[month_key]["high"] += 1
                elif record.defect_level == 'medium':
                    monthly_stats[month_key]["medium"] += 1
                elif record.defect_level == 'low':
                    monthly_stats[month_key]["low"] += 1

        # 转换set为count
        for month in monthly_stats:
            monthly_stats[month]["checks"] = len(monthly_stats[month]["checks"])

        # 计算趋势
        sorted_months = sorted(monthly_stats.keys())
        if len(sorted_months) >= 2:
            first_high = monthly_stats[sorted_months[0]]["high"]
            last_high = monthly_stats[sorted_months[-1]]["high"]

            if last_high > first_high * 1.2:
                trend = "恶化"
                trend_description = "高级别问题增加"
            elif last_high < first_high * 0.8:
                trend = "改善"
                trend_description = "高级别问题减少"
            else:
                trend = "平稳"
                trend_description = "安全状况基本稳定"
        else:
            trend = "数据不足"
            trend_description = "需要更多数据"

        return {
            "analysis_period": f"{start_date} 至 {end_date}",
            "monthly_stats": monthly_stats,
            "trend": trend,
            "trend_description": trend_description
        }

    def compare_with_standard(self, project_id: str) -> Dict[str, Any]:
        """
        工具6: 与行业标准对标
        """
        overview = self.get_safety_overview(project_id, days=30)

        # 行业标准（示例值）
        standards = {
            "pass_rate": 98.0,
            "high_defect_rate": 2.0,
            "closure_rate": 95.0
        }

        # 计算项目指标
        total_checks = overview.get("total_checks", 0)
        high_defects = overview.get("high_level_defects", 0)
        pass_rate = overview.get("pass_rate", 0)
        closure_rate = overview.get("closure_rate", 0)

        high_defect_rate = (high_defects / total_checks * 100) if total_checks > 0 else 0

        # 对比分析
        comparisons = {
            "pass_rate": {
                "project": pass_rate,
                "standard": standards["pass_rate"],
                "gap": round(pass_rate - standards["pass_rate"], 2),
                "status": "达标" if pass_rate >= standards["pass_rate"] else "未达标"
            },
            "high_defect_rate": {
                "project": round(high_defect_rate, 2),
                "standard": standards["high_defect_rate"],
                "gap": round(high_defect_rate - standards["high_defect_rate"], 2),
                "status": "达标" if high_defect_rate <= standards["high_defect_rate"] else "未达标"
            }
        }

        达标项数 = sum(1 for c in comparisons.values() if c["status"] == "达标")
        overall_status = "优秀" if 达标项数 == 2 else "良好" if 达标项数 == 1 else "需改进"

        return {
            "comparisons": comparisons,
            "overall_status": overall_status,
            "达标项数": 达标项数
        }

    def identify_safety_risks(self, project_id: str) -> List[Dict[str, Any]]:
        """
        工具7: 识别安全风险
        """
        risks = []

        overview = self.get_safety_overview(project_id, days=30)
        frequent = self.identify_frequent_issues(project_id, days=60)
        open_defects = self.get_open_defects(project_id)

        # 风险1: 高级别问题过多
        high_defects = overview.get("high_level_defects", 0)
        if high_defects > 5:
            risks.append({
                "risk_type": "高级别隐患过多",
                "severity": "high",
                "description": f"近30天发现{high_defects}个高级别安全隐患",
                "recommendation": "立即组织专项整改，加强现场安全管理"
            })

        # 风险2: 未关闭问题过多
        open_count = overview.get("open_defects", 0)
        if open_count > 10:
            risks.append({
                "risk_type": "未关闭问题积压",
                "severity": "high",
                "description": f"当前有{open_count}个未关闭的安全问题",
                "recommendation": "建立问题跟踪机制，限期完成整改"
            })

        # 风险3: 频发问题未解决
        if frequent:
            top_issue = frequent[0]
            if top_issue["total_count"] > 5 and top_issue["trend"] == "上升":
                risks.append({
                    "risk_type": "频发问题未解决",
                    "severity": "high",
                    "description": f"{top_issue['defect_type']}问题频繁出现且呈上升趋势",
                    "recommendation": "分析根本原因，采取系统性改进措施"
                })

        return risks

    def get_improvement_suggestions(self, project_id: str) -> List[str]:
        """
        工具8: 生成改进建议
        """
        suggestions = []

        overview = self.get_safety_overview(project_id)
        frequent = self.identify_frequent_issues(project_id)
        risks = self.identify_safety_risks(project_id)

        risk_level = overview.get("risk_level", "green")

        if risk_level == "red":
            suggestions.append("🔴 优先级1：安全状况严峻，建议：")
            suggestions.append("   - 暂停高风险作业，开展安全大检查")
            suggestions.append("   - 召开安全专项会议")
        elif risk_level == "yellow":
            suggestions.append("🟡 优先级1：安全状况需要改进")

        # 针对频发问题
        if frequent:
            top_issues = frequent[:3]
            suggestions.append(f"\n🔧 优先级2：针对频发问题的改进")
            for issue in top_issues:
                defect_type = issue["defect_type"]
                if "模板" in defect_type:
                    suggestions.append(f"   - {defect_type}: 加强模板支撑系统验收")
                elif "防护" in defect_type:
                    suggestions.append(f"   - {defect_type}: 完善临边防护设施")

        if not suggestions:
            suggestions.append("✅ 当前安全状况良好")

        return suggestions

    def get_rectification_plan(self, project_id: str) -> Dict[str, Any]:
        """
        工具9: 生成整改计划

        为未关闭问题生成分阶段整改计划
        """
        open_defects = self.get_open_defects(project_id)

        if not open_defects:
            return {"message": "没有待整改问题", "has_plan": False}

        # 按紧急程度分组
        urgent = [d for d in open_defects if d["urgency"] == "紧急"]
        important = [d for d in open_defects if d["urgency"] == "重要"]
        normal = [d for d in open_defects if d["urgency"] == "一般"]

        plan = {
            "has_plan": True,
            "total_items": len(open_defects),
            "urgent_items": len(urgent),
            "important_items": len(important),
            "normal_items": len(normal),
            "phases": []
        }

        # 三个阶段的整改计划
        if urgent:
            plan["phases"].append({
                "phase": "第一阶段（3天内）",
                "priority": "紧急",
                "items": urgent,
                "deadline": (date.today() + timedelta(days=3)).isoformat()
            })

        if important:
            plan["phases"].append({
                "phase": "第二阶段（1周内）",
                "priority": "重要",
                "items": important,
                "deadline": (date.today() + timedelta(days=7)).isoformat()
            })

        if normal:
            plan["phases"].append({
                "phase": "第三阶段（2周内）",
                "priority": "一般",
                "items": normal,
                "deadline": (date.today() + timedelta(days=14)).isoformat()
            })

        return plan


def get_safety_tools(db: Session) -> SafetyTools:
    """工厂函数：创建安全工具实例"""
    return SafetyTools(db)