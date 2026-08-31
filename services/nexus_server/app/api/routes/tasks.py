from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_resources
from app.storage.resources import AppResources
from app.storage.task_repository import TaskRecord

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRecord])
async def list_tasks(
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> list[TaskRecord]:
    return await resources.task_repository.list_for_user(user_id)
