"""项目域服务：项目/任务/成本/安全的业务编排。

构造接收 DB 会话；方法返回 ORM 对象/DTO/dict；真实分页 count；
资源不存在抛 NotFoundError。
"""
from datetime import date
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.schemas.project import (
    CostCreate,
    ProjectCreate,
    ProjectStatistics,
    ProjectUpdate,
    SafetyRecordCreate,
    TaskCreate,
    TaskUpdate,
)
from core.exceptions import NotFoundError
from models.project import (
    CostDetail,
    ProjectBasic,
    SafetyRecord,
    TaskSchedule,
)


class ProjectService:
    """项目服务：CRUD、分页、统计。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_project(self, project_id: str) -> Optional[ProjectBasic]:
        """读取单个项目；不存在返回 None（供工具层判空）。"""
        return (
            self.db.query(ProjectBasic)
            .filter(ProjectBasic.project_id == project_id)
            .first()
        )

    def _require_project(self, project_id: str) -> ProjectBasic:
        """读取项目，不存在抛领域异常（供路由层映射 404）。"""
        project = self.get_project(project_id)
        if not project:
            raise NotFoundError(f"项目 {project_id} 不存在")
        return project

    def list_projects(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> tuple[list[ProjectBasic], int]:
        """返回 (当前页列表, 满足条件的总数)。"""
        query = self.db.query(ProjectBasic)
        if status:
            query = query.filter(ProjectBasic.status == status)

        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def create_project(self, project: ProjectCreate) -> ProjectBasic:
        db_project = ProjectBasic(**project.model_dump())
        self.db.add(db_project)
        self.db.commit()
        self.db.refresh(db_project)
        return db_project

    def update_project(
        self, project_id: str, project_update: ProjectUpdate
    ) -> ProjectBasic:
        db_project = self._require_project(project_id)
        for field, value in project_update.model_dump(exclude_unset=True).items():
            setattr(db_project, field, value)
        self.db.commit()
        self.db.refresh(db_project)
        return db_project

    def delete_project(self, project_id: str) -> None:
        db_project = self._require_project(project_id)
        self.db.delete(db_project)
        self.db.commit()

    def get_project_statistics(self, project_id: str) -> ProjectStatistics:
        project = self._require_project(project_id)

        tasks = (
            self.db.query(TaskSchedule)
            .filter(TaskSchedule.project_id == project_id)
            .all()
        )
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == "completed"])
        delayed_tasks = len([t for t in tasks if t.status == "delayed"])
        spi_values = [t.spi for t in tasks if t.spi is not None]
        average_spi = sum(spi_values) / len(spi_values) if spi_values else None

        costs = (
            self.db.query(CostDetail)
            .filter(CostDetail.project_id == project_id)
            .all()
        )
        total_actual_cost = sum(c.actual_amount or 0 for c in costs)
        cost_variance = total_actual_cost - (project.total_budget or 0)
        cost_variance_rate = (
            float(cost_variance / project.total_budget)
            if project.total_budget and project.total_budget > 0
            else 0.0
        )

        def _category_sum(name: str):
            return sum(c.actual_amount or 0 for c in costs if c.cost_category == name)

        safety_records = (
            self.db.query(SafetyRecord)
            .filter(SafetyRecord.project_id == project_id)
            .all()
        )
        total_safety_checks = len({r.check_date for r in safety_records})
        total_defects = len(safety_records)
        high_level_defects = len(
            [r for r in safety_records if r.defect_level == "high"]
        )
        open_defects = len([r for r in safety_records if r.status == "open"])

        return ProjectStatistics(
            project_id=project.project_id,
            project_name=project.project_name,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            delayed_tasks=delayed_tasks,
            overall_progress=project.progress_rate,
            average_spi=average_spi,
            total_budget=project.total_budget or 0,
            total_actual_cost=total_actual_cost,
            cost_variance=cost_variance,
            cost_variance_rate=cost_variance_rate,
            material_cost=_category_sum("材料"),
            labor_cost=_category_sum("人工"),
            equipment_cost=_category_sum("机械"),
            subcontract_cost=_category_sum("分包"),
            total_safety_checks=total_safety_checks,
            total_defects=total_defects,
            high_level_defects=high_level_defects,
            open_defects=open_defects,
        )


class TaskService:
    """任务服务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_tasks_by_project(
        self, project_id: str, status: Optional[str] = None
    ) -> list[TaskSchedule]:
        query = self.db.query(TaskSchedule).filter(
            TaskSchedule.project_id == project_id
        )
        if status:
            query = query.filter(TaskSchedule.status == status)
        return query.all()

    def create_task(self, task: TaskCreate) -> TaskSchedule:
        db_task = TaskSchedule(**task.model_dump())
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def update_task(self, task_id: int, task_update: TaskUpdate) -> TaskSchedule:
        db_task = (
            self.db.query(TaskSchedule)
            .filter(TaskSchedule.task_id == task_id)
            .first()
        )
        if not db_task:
            raise NotFoundError(f"任务 {task_id} 不存在")
        for field, value in task_update.model_dump(exclude_unset=True).items():
            setattr(db_task, field, value)
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def get_critical_tasks(self, project_id: str) -> list[TaskSchedule]:
        return (
            self.db.query(TaskSchedule)
            .filter(
                and_(
                    TaskSchedule.project_id == project_id,
                    TaskSchedule.is_critical_path == True,  # noqa: E712
                )
            )
            .all()
        )

    def get_delayed_tasks(self, project_id: str) -> list[TaskSchedule]:
        return (
            self.db.query(TaskSchedule)
            .filter(
                and_(
                    TaskSchedule.project_id == project_id,
                    TaskSchedule.status == "delayed",
                )
            )
            .all()
        )


class CostService:
    """成本服务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_costs_by_project(
        self,
        project_id: str,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[CostDetail]:
        query = self.db.query(CostDetail).filter(
            CostDetail.project_id == project_id
        )
        if category:
            query = query.filter(CostDetail.cost_category == category)
        if start_date:
            query = query.filter(CostDetail.cost_date >= start_date)
        if end_date:
            query = query.filter(CostDetail.cost_date <= end_date)
        return query.all()

    def create_cost(self, cost: CostCreate) -> CostDetail:
        db_cost = CostDetail(**cost.model_dump())
        self.db.add(db_cost)
        self.db.commit()
        self.db.refresh(db_cost)
        return db_cost

    def get_cost_summary_by_category(self, project_id: str) -> dict:
        rows = (
            self.db.query(
                CostDetail.cost_category,
                func.sum(CostDetail.planned_amount).label("total_planned"),
                func.sum(CostDetail.actual_amount).label("total_actual"),
            )
            .filter(CostDetail.project_id == project_id)
            .group_by(CostDetail.cost_category)
            .all()
        )
        return {
            row.cost_category: {
                "planned": float(row.total_planned or 0),
                "actual": float(row.total_actual or 0),
            }
            for row in rows
        }


class SafetyService:
    """安全服务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_safety_records_by_project(
        self,
        project_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        defect_level: Optional[str] = None,
    ) -> list[SafetyRecord]:
        query = self.db.query(SafetyRecord).filter(
            SafetyRecord.project_id == project_id
        )
        if start_date:
            query = query.filter(SafetyRecord.check_date >= start_date)
        if end_date:
            query = query.filter(SafetyRecord.check_date <= end_date)
        if defect_level:
            query = query.filter(SafetyRecord.defect_level == defect_level)
        return query.all()

    def create_safety_record(self, record: SafetyRecordCreate) -> SafetyRecord:
        db_record = SafetyRecord(**record.model_dump())
        self.db.add(db_record)
        self.db.commit()
        self.db.refresh(db_record)
        return db_record

    def get_open_defects(self, project_id: str) -> list[SafetyRecord]:
        return (
            self.db.query(SafetyRecord)
            .filter(
                and_(
                    SafetyRecord.project_id == project_id,
                    SafetyRecord.status == "open",
                )
            )
            .all()
        )

    def get_defect_statistics(self, project_id: str) -> dict:
        rows = (
            self.db.query(
                SafetyRecord.defect_type,
                SafetyRecord.defect_level,
                func.count(SafetyRecord.record_id).label("count"),
            )
            .filter(SafetyRecord.project_id == project_id)
            .group_by(SafetyRecord.defect_type, SafetyRecord.defect_level)
            .all()
        )
        stats: dict = {}
        for row in rows:
            stats.setdefault(row.defect_type, {})[row.defect_level] = row.count
        return stats
