from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent.models import AgentRun
from app.api.schemas.runs import RunCreate
from app.dependencies import get_resources
from app.storage.resources import AppResources

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: RunCreate,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    return await resources.agent_runtime.start(
        request.goal,
        user_id=request.user_id,
        max_iterations=(
            request.max_iterations or resources.settings.nexus_max_agent_iterations
        ),
    )


@router.get("", response_model=list[AgentRun])
async def list_runs(
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> list[AgentRun]:
    return await resources.run_repository.list_for_user(user_id)


@router.get("/{run_id}", response_model=AgentRun)
async def get_run(
    run_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    run = await resources.run_repository.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": "Agent run not found."},
        )
    return run
