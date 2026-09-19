from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_resources
from app.storage.resources import AppResources
from app.storage.task_repository import TaskRecord, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRecord])
async def list_tasks(
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
    run_id: str | None = None,
) -> list[TaskRecord]:
    tasks = await resources.task_repository.list_for_user(user_id)
    return [task for task in tasks if run_id is None or task.run_id == run_id]


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TaskStatus


@router.patch("/{task_id}", response_model=TaskRecord)
async def update_task(
    task_id: str,
    request: TaskUpdate,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> TaskRecord:
    task = await resources.task_repository.update_status(
        task_id, user_id, request.status
    )
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND"})
    return task
