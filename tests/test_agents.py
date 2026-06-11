"""
========================================
Agent 模块单元测试
========================================

📚 测试说明：
- 测试所有Agent的核心功能
- 使用Mock模拟数据库和工具模块
- 覆盖正常流程和异常处理

🎯 测试范围：
1. CostAnalysisAgent
2. ProgressAnalysisAgent
3. SafetyAnalysisAgent
4. API接口测试

💡 运行方式：
    pytest tests/test_agents.py -v
    pytest tests/test_agents.py -v -k "test_cost"

========================================
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import date, datetime
from dataclasses import asdict

# 异步测试由 pytest.ini 的 asyncio_mode=auto 自动识别，无需模块级 pytestmark


# =========================================
# Fixtures
# =========================================

@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_progress_tools():
    """模拟进度工具"""
    tools = Mock()
    tools.get_project_overview.return_value = {
        "project_id": "P001",
        "project_name": "测试项目",
        "project_manager": "张三",
        "overall_progress": 65.0,
        "planned_progress": 70.0,
        "total_tasks": 100,
        "completed_tasks": 60,
        "in_progress_tasks": 25,
        "delayed_tasks": 5,
        "not_started_tasks": 10
    }
    tools.get_progress_status.return_value = {
        "total_tasks": 100,
        "avg_planned_progress": 70.0,
        "avg_actual_progress": 64.4,
        "variance": -5.6,
        "variance_rate": -8.0,
        "overall_spi": 0.92,
        "risk_level": "yellow",
        "risk_description": "进度略有延期，需要关注并采取措施"
    }
    tools.get_delayed_tasks.return_value = [
        {
            "task_id": "T001",
            "task_name": "基础施工",
            "planned_progress": 80,
            "actual_progress": 65,
            "variance": -15.0,
            "spi": 0.81,
            "severity": "中等",
            "reason": "SPI=0.81，进度落后于计划",
            "is_critical_path": True
        }
    ]
    tools.get_critical_path_tasks.return_value = [
        {
            "task_id": "T001",
            "task_name": "基础施工",
            "planned_progress": 80,
            "actual_progress": 65,
            "spi": 0.81,
            "status": "in_progress",
            "planned_start": "2024-01-01",
            "planned_end": "2024-03-01",
            "is_delayed": True
        }
    ]
    tools.analyze_progress_trend.return_value = {
        "analysis_period": "最近30天",
        "updated_tasks": 12,
        "high_risk_tasks": 1,
        "medium_risk_tasks": 3,
        "trend": "平稳"
    }
    tools.predict_completion_time.return_value = {
        "current_progress": 65.0,
        "remaining_progress": 35.0,
        "average_spi": 0.92,
        "planned_end_date": "2024-06-15",
        "predicted_delay_days": 15,
        "prediction_confidence": "中"
    }
    tools.identify_bottlenecks.return_value = [
        {
            "task_id": "T001",
            "task_name": "基础施工",
            "spi": 0.81,
            "actual_progress": 65.0,
            "impact": "高",
            "reason": "关键路径任务，当前SPI=0.81，进度落后",
            "recommendation": "立即增加资源投入"
        }
    ]
    tools.get_resource_allocation.return_value = {
        "load_status": "normal",
        "parallel_tasks": 8
    }
    return tools


@pytest.fixture
def mock_cost_tools():
    """模拟成本工具"""
    tools = Mock()
    tools.get_cost_overview.return_value = {
        "project_name": "测试项目",
        "total_budget": 1000000,
        "total_actual": 650000,
        "variance": -50000,
        "variance_rate": -5.0,
        "cpi": 0.95,
        "budget_usage_rate": 65.0,
        "risk_level": "yellow"
    }
    tools.get_cost_by_category.return_value = {
        "categories": {
            "材料": {"planned": 500000, "actual": 520000, "variance": 20000,
                     "variance_rate": 4.0, "count": 3, "status": "超支"},
            "人工": {"planned": 300000, "actual": 280000, "variance": -20000,
                     "variance_rate": -6.7, "count": 2, "status": "正常"}
        },
        "max_overrun_category": "材料",
        "max_overrun_rate": 4.0
    }
    tools.identify_cost_overruns.return_value = [
        {
            "cost_id": "C001",
            "category": "材料",
            "item": "钢材采购",
            "planned": 250000,
            "actual": 270000,
            "variance": 20000,
            "variance_rate": 8.0,
            "severity": "轻微"
        }
    ]
    tools.analyze_cost_trend.return_value = {
        "analysis_period": "2024-01-01 至 2024-03-31",
        "monthly_data": {
            "2024-01": {"planned": 320000, "actual": 340000, "count": 2},
            "2024-02": {"planned": 300000, "actual": 310000, "count": 2}
        },
        "trend": "上升",
        "growth_rate": 5.0
    }
    tools.predict_final_cost.return_value = {
        "current_budget": 1000000,
        "cpi": 0.95,
        "progress_rate": 65.0,
        "predicted_final_cost": 1050000,
        "predicted_overrun": 50000,
        "predicted_overrun_rate": 5.0,
        "will_exceed_budget": True,
        "confidence": "中等"
    }
    tools.identify_cost_risks.return_value = [
        {"risk_type": "材料超支", "severity": "medium",
         "description": "材料成本超支", "recommendation": "优化采购"}
    ]
    tools.get_cost_control_suggestions.return_value = [
        "加强材料采购管理",
        "优化施工组织"
    ]
    return tools


@pytest.fixture
def mock_safety_tools():
    """模拟安全工具"""
    tools = Mock()
    tools.get_safety_overview.return_value = {
        "project_name": "测试项目",
        "total_checks": 50,
        "passed_checks": 47,
        "pass_rate": 94.0,
        "total_defects": 15,
        "high_level_defects": 2,
        "open_defects": 5,
        "closure_rate": 66.7,
        "risk_level": "yellow"
    }
    tools.analyze_defect_distribution.return_value = {
        "has_data": True,
        "total_records": 15,
        "distribution_by_level": {"high": 2, "medium": 8, "low": 5},
        "distribution_by_status": {"open": 5, "closed": 10},
        "distribution_by_type": {"脚手架": 5, "临边防护": 4}
    }
    tools.identify_frequent_issues.return_value = [
        {
            "defect_type": "脚手架问题",
            "total_count": 5,
            "high_level_count": 1,
            "trend": "上升",
            "frequency": 2.5,
            "severity": "中等"
        }
    ]
    tools.get_open_defects.return_value = [
        {
            "record_id": "D001",
            "defect_type": "脚手架",
            "defect_level": "high",
            "description": "脚手架未按规范搭设",
            "check_date": "2026-06-08",
            "days_open": 3,
            "urgency": "紧急",
            "checker": "李四"
        }
    ]
    tools.analyze_safety_trend.return_value = {
        "analysis_period": "2026-03-13 至 2026-06-11",
        "monthly_stats": {
            "2026-04": {"total": 6, "high": 1, "medium": 3, "low": 2, "checks": 4},
            "2026-05": {"total": 5, "high": 2, "medium": 2, "low": 1, "checks": 4}
        },
        "trend": "恶化",
        "trend_description": "高级别问题增加"
    }
    tools.get_rectification_plan.return_value = {
        "has_plan": True,
        "total_items": 1,
        "urgent_items": 1,
        "important_items": 0,
        "normal_items": 0,
        "phases": [
            {"phase": "第一阶段（3天内）", "priority": "紧急", "items": [],
             "deadline": "2026-06-14"}
        ]
    }
    tools.get_improvement_suggestions.return_value = [
        "加强安全巡查",
        "完善防护设施"
    ]
    return tools


# =========================================
# CostAnalysisAgent 测试
# =========================================

class TestCostAnalysisAgent:
    """成本分析Agent测试"""

    @pytest.mark.asyncio
    async def test_analyze_costs_success(self, mock_db, mock_cost_tools, mock_progress_tools):
        """测试成本分析成功场景"""
        with patch('agents.cost_agent.get_cost_tools', return_value=mock_cost_tools), \
                patch('agents.cost_agent.get_progress_tools', return_value=mock_progress_tools), \
                patch('agents.cost_agent.run_rag', new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = {"answer": "建议1\n建议2"}

            from agents.cost_agent import CostAnalysisAgent
            agent = CostAnalysisAgent(mock_db)

            result = await agent.analyze_costs("P001", analysis_months=3)

            assert result["success"] is True
            assert result["project_id"] == "P001"
            assert "overview" in result
            assert result["overview"]["cpi"] == 0.95

    @pytest.mark.asyncio
    async def test_analyze_costs_without_ai(self, mock_db, mock_cost_tools, mock_progress_tools):
        """测试不包含AI洞察的成本分析"""
        with patch('agents.cost_agent.get_cost_tools', return_value=mock_cost_tools), \
                patch('agents.cost_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.cost_agent import CostAnalysisAgent
            agent = CostAnalysisAgent(mock_db)

            result = await agent.analyze_costs("P001", include_ai_insights=False)

            assert result["success"] is True
            assert result["ai_insights"] == []

    @pytest.mark.asyncio
    async def test_quick_cost_check(self, mock_db, mock_cost_tools, mock_progress_tools):
        """测试快速成本检查"""
        with patch('agents.cost_agent.get_cost_tools', return_value=mock_cost_tools), \
                patch('agents.cost_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.cost_agent import CostAnalysisAgent
            agent = CostAnalysisAgent(mock_db)

            result = await agent.quick_cost_check("P001")

            assert result["success"] is True
            assert "cpi" in result
            assert "risk_level" in result

    @pytest.mark.asyncio
    async def test_analyze_costs_exception(self, mock_db, mock_cost_tools, mock_progress_tools):
        """测试成本分析异常处理"""
        mock_cost_tools.get_cost_overview.side_effect = Exception("数据库错误")

        with patch('agents.cost_agent.get_cost_tools', return_value=mock_cost_tools), \
                patch('agents.cost_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.cost_agent import CostAnalysisAgent
            agent = CostAnalysisAgent(mock_db)

            result = await agent.analyze_costs("P001")

            assert result["success"] is False
            assert "error" in result


# =========================================
# ProgressAnalysisAgent 测试
# =========================================

class TestProgressAnalysisAgent:
    """进度分析Agent测试"""

    @pytest.mark.asyncio
    async def test_analyze_progress_success(self, mock_db, mock_progress_tools):
        """测试进度分析成功场景"""
        with patch('agents.progress_agent.get_progress_tools', return_value=mock_progress_tools), \
                patch('agents.progress_agent.run_rag', new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = {"answer": "建议1\n建议2"}

            from agents.progress_agent import ProgressAnalysisAgent
            agent = ProgressAnalysisAgent(mock_db)

            result = await agent.analyze_progress("P001", analysis_days=30)

            assert result["success"] is True
            assert result["project_id"] == "P001"
            assert "overview" in result
            assert "spi_analysis" in result

    @pytest.mark.asyncio
    async def test_quick_progress_check(self, mock_db, mock_progress_tools):
        """测试快速进度检查"""
        with patch('agents.progress_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.progress_agent import ProgressAnalysisAgent
            agent = ProgressAnalysisAgent(mock_db)

            result = await agent.quick_progress_check("P001")

            assert result["success"] is True
            assert "spi" in result
            assert "delayed_tasks" in result

    @pytest.mark.asyncio
    async def test_delayed_tasks_detection(self, mock_db, mock_progress_tools):
        """测试延期任务检测"""
        with patch('agents.progress_agent.get_progress_tools', return_value=mock_progress_tools), \
                patch('agents.progress_agent.run_rag', new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = None

            from agents.progress_agent import ProgressAnalysisAgent
            agent = ProgressAnalysisAgent(mock_db)

            result = await agent.analyze_progress("P001", include_ai_insights=False)

            assert result["delayed_count"] == 1
            assert result["critical_delayed_count"] == 1


# =========================================
# SafetyAnalysisAgent 测试
# =========================================

class TestSafetyAnalysisAgent:
    """安全分析Agent测试"""

    @pytest.mark.asyncio
    async def test_analyze_safety_success(self, mock_db, mock_safety_tools, mock_progress_tools):
        """测试安全分析成功场景"""
        with patch('agents.safety_agent.get_safety_tools', return_value=mock_safety_tools), \
                patch('agents.safety_agent.get_progress_tools', return_value=mock_progress_tools), \
                patch('agents.safety_agent.run_rag', new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = {"answer": "建议1"}

            from agents.safety_agent import SafetyAnalysisAgent
            agent = SafetyAnalysisAgent(mock_db)

            result = await agent.analyze_safety("P001", analysis_days=30)

            assert result["success"] is True
            assert "overview" in result
            assert result["overview"]["pass_rate"] == 94.0

    @pytest.mark.asyncio
    async def test_quick_safety_check(self, mock_db, mock_safety_tools, mock_progress_tools):
        """测试快速安全检查"""
        with patch('agents.safety_agent.get_safety_tools', return_value=mock_safety_tools), \
                patch('agents.safety_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.safety_agent import SafetyAnalysisAgent
            agent = SafetyAnalysisAgent(mock_db)

            result = await agent.quick_safety_check("P001", days=7)

            assert result["success"] is True
            assert "pass_rate" in result
            assert "risk_level" in result

    @pytest.mark.asyncio
    async def test_safety_alerts_generation(self, mock_db, mock_safety_tools, mock_progress_tools):
        """测试安全预警生成"""
        # 设置低合格率触发预警
        mock_safety_tools.get_safety_overview.return_value["pass_rate"] = 85.0
        mock_safety_tools.get_safety_overview.return_value["high_level_defects"] = 4

        with patch('agents.safety_agent.get_safety_tools', return_value=mock_safety_tools), \
                patch('agents.safety_agent.get_progress_tools', return_value=mock_progress_tools), \
                patch('agents.safety_agent.run_rag', new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = None

            from agents.safety_agent import SafetyAnalysisAgent
            agent = SafetyAnalysisAgent(mock_db)

            result = await agent.analyze_safety("P001", include_ai_insights=False)

            assert len(result["alerts"]) > 0


# =========================================
# 数据结构测试
# =========================================

class TestDataStructures:
    """数据结构测试"""

    def test_cost_overview_dataclass(self):
        """测试CostOverview数据结构"""
        from agents.cost_agent import CostOverview

        overview = CostOverview(
            project_id="P001",
            total_budget=1000000,
            cpi=0.95
        )

        assert overview.project_id == "P001"
        assert overview.cpi == 0.95

        data = asdict(overview)
        assert isinstance(data, dict)

    def test_progress_overview_dataclass(self):
        """测试ProgressOverview数据结构"""
        from agents.progress_agent import ProgressOverview

        overview = ProgressOverview(
            project_id="P001",
            overall_progress=65.0
        )

        assert overview.overall_progress == 65.0

    def test_safety_overview_dataclass(self):
        """测试SafetyOverview数据结构"""
        from agents.safety_agent import SafetyOverview

        overview = SafetyOverview(
            project_id="P001",
            pass_rate=95.0
        )

        assert overview.pass_rate == 95.0


# =========================================
# 阈值判断测试
# =========================================

class TestThresholds:
    """阈值判断测试"""

    @pytest.mark.asyncio
    async def test_cost_risk_level_critical(self, mock_db, mock_cost_tools, mock_progress_tools):
        """测试成本风险等级-严重"""
        mock_cost_tools.get_cost_overview.return_value["cpi"] = 0.70

        with patch('agents.cost_agent.get_cost_tools', return_value=mock_cost_tools), \
                patch('agents.cost_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.cost_agent import CostAnalysisAgent
            agent = CostAnalysisAgent(mock_db)

            result = await agent.quick_cost_check("P001")

            assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_progress_risk_level_high(self, mock_db, mock_progress_tools):
        """测试进度风险等级-高"""
        mock_progress_tools.get_progress_status.return_value["overall_spi"] = 0.80

        with patch('agents.progress_agent.get_progress_tools', return_value=mock_progress_tools):
            from agents.progress_agent import ProgressAnalysisAgent
            agent = ProgressAnalysisAgent(mock_db)

            result = await agent.quick_progress_check("P001")

            assert result["risk_level"] == "high"


# =========================================
# 运行测试
# =========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])