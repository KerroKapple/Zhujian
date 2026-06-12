"""项目管理 API：项目/任务/成本/安全 CRUD 与统计。

路由层仅做入参校验 + 调 service + 返回；
列表走 Page 契约；错误由 service 抛领域异常，统一处理器映射。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.common import OkResponse, Page
from app.schemas.project import (
    CostCreate,
    CostResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectStatistics,
    ProjectUpdate,
    SafetyRecordCreate,
    SafetyRecordResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from core.deps import (
    get_cost_service,
    get_project_service,
    get_safety_service,
    get_task_service,
)
from core.exceptions import NotFoundError
from services.project.project_service import (
    CostService,
    ProjectService,
    SafetyService,
    TaskService,
)

router = APIRouter()


# ============ 项目 ============

@router.post("/", response_model=ProjectResponse, summary="创建项目")
async def create_project(
    project: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
):
    return ProjectResponse.model_validate(service.create_project(project))


@router.get("/", response_model=Page[ProjectResponse], summary="获取项目列表")
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="项目状态筛选"),
    service: ProjectService = Depends(get_project_service),
):
    items, total = service.list_projects(skip=skip, limit=limit, status=status)
    return Page[ProjectResponse](
        items=[ProjectResponse.model_validate(p) for p in items],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get("/{project_id}", response_model=ProjectResponse, summary="获取项目详情")
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
):
    project = service.get_project(project_id)
    if not project:
        raise NotFoundError(f"项目 {project_id} 不存在")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse, summary="更新项目")
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
):
    return ProjectResponse.model_validate(
        service.update_project(project_id, project_update)
    )


@router.delete("/{project_id}", response_model=OkResponse, summary="删除项目")
async def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
):
    service.delete_project(project_id)
    return OkResponse(message="删除成功")


@router.get(
    "/{project_id}/statistics",
    response_model=ProjectStatistics,
    summary="获取项目统计",
)
async def get_project_statistics(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
):
    return service.get_project_statistics(project_id)


# ============ 任务 ============

@router.post(
    "/{project_id}/tasks", response_model=TaskResponse, summary="创建任务"
)
async def create_task(
    project_id: str,
    task: TaskCreate,
    service: TaskService = Depends(get_task_service),
):
    task.project_id = project_id
    return TaskResponse.model_validate(service.create_task(task))


@router.get(
    "/{project_id}/tasks",
    response_model=list[TaskResponse],
    summary="获取项目任务列表",
)
async def list_tasks(
    project_id: str,
    status: Optional[str] = Query(None, description="任务状态筛选"),
    service: TaskService = Depends(get_task_service),
):
    tasks = service.get_tasks_by_project(project_id, status=status)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.put("/tasks/{task_id}", response_model=TaskResponse, summary="更新任务")
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
):
    return TaskResponse.model_validate(service.update_task(task_id, task_update))


@router.get(
    "/{project_id}/tasks/critical",
    response_model=list[TaskResponse],
    summary="获取关键路径任务",
)
async def get_critical_tasks(
    project_id: str,
    service: TaskService = Depends(get_task_service),
):
    return [
        TaskResponse.model_validate(t)
        for t in service.get_critical_tasks(project_id)
    ]


@router.get(
    "/{project_id}/tasks/delayed",
    response_model=list[TaskResponse],
    summary="获取延期任务",
)
async def get_delayed_tasks(
    project_id: str,
    service: TaskService = Depends(get_task_service),
):
    return [
        TaskResponse.model_validate(t)
        for t in service.get_delayed_tasks(project_id)
    ]


# ============ 成本 ============

@router.post(
    "/{project_id}/costs", response_model=CostResponse, summary="创建成本记录"
)
async def create_cost(
    project_id: str,
    cost: CostCreate,
    service: CostService = Depends(get_cost_service),
):
    cost.project_id = project_id
    return CostResponse.model_validate(service.create_cost(cost))


@router.get(
    "/{project_id}/costs",
    response_model=list[CostResponse],
    summary="获取项目成本列表",
)
async def list_costs(
    project_id: str,
    category: Optional[str] = Query(None, description="成本类别筛选"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    service: CostService = Depends(get_cost_service),
):
    costs = service.get_costs_by_project(
        project_id, category=category, start_date=start_date, end_date=end_date
    )
    return [CostResponse.model_validate(c) for c in costs]


@router.get(
    "/{project_id}/costs/summary", summary="获取成本汇总"
)
async def get_cost_summary(
    project_id: str,
    service: CostService = Depends(get_cost_service),
):
    return service.get_cost_summary_by_category(project_id)


# ============ 安全记录 ============

@router.post(
    "/{project_id}/safety",
    response_model=SafetyRecordResponse,
    summary="创建安全记录",
)
async def create_safety_record(
    project_id: str,
    record: SafetyRecordCreate,
    service: SafetyService = Depends(get_safety_service),
):
    record.project_id = project_id
    return SafetyRecordResponse.model_validate(
        service.create_safety_record(record)
    )


@router.get(
    "/{project_id}/safety",
    response_model=list[SafetyRecordResponse],
    summary="获取安全记录列表",
)
async def list_safety_records(
    project_id: str,
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    defect_level: Optional[str] = Query(None, description="缺陷等级筛选"),
    service: SafetyService = Depends(get_safety_service),
):
    records = service.get_safety_records_by_project(
        project_id,
        start_date=start_date,
        end_date=end_date,
        defect_level=defect_level,
    )
    return [SafetyRecordResponse.model_validate(r) for r in records]


@router.get(
    "/{project_id}/safety/open-defects",
    response_model=list[SafetyRecordResponse],
    summary="获取未关闭的安全问题",
)
async def get_open_defects(
    project_id: str,
    service: SafetyService = Depends(get_safety_service),
):
    return [
        SafetyRecordResponse.model_validate(d)
        for d in service.get_open_defects(project_id)
    ]


@router.get(
    "/{project_id}/safety/statistics", summary="获取缺陷统计"
)
async def get_defect_statistics(
    project_id: str,
    service: SafetyService = Depends(get_safety_service),
):
    return service.get_defect_statistics(project_id)
