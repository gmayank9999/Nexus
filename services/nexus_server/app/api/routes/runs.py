from collections.abc import Awaitable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent.models import AgentRun
from app.agent.runtime import RunActionError
from app.api.schemas.runs import RunCreate
from app.dependencies import get_resources
from app.events.models import AgentEvent
from app.storage.resources import AppResources

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: RunCreate,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    run = await resources.agent_runtime.create(
        request.goal,
        user_id=request.user_id,
        max_iterations=(
            request.max_iterations or resources.settings.nexus_max_agent_iterations
        ),
    )
    resources.run_in_background(run)
    return run


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


@router.get("/{run_id}/events", response_model=list[AgentEvent])
async def list_run_events(
    run_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    after: Annotated[int, Query(ge=0)] = 0,
) -> list[AgentEvent]:
    await _require_run(run_id, resources)
    return await resources.event_bus.list_after(run_id, after)


@router.post("/{run_id}/approve", response_model=AgentRun)
async def approve_run(
    run_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    run = await _run_action(resources.agent_runtime.approve(run_id))
    resources.run_in_background(run)
    return run


@router.post("/{run_id}/reject", response_model=AgentRun)
async def reject_run(
    run_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    run = await _run_action(resources.agent_runtime.reject(run_id))
    resources.run_in_background(run)
    return run


@router.post("/{run_id}/cancel", response_model=AgentRun)
async def cancel_run(
    run_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AgentRun:
    return await _run_action(resources.agent_runtime.cancel(run_id))


async def _require_run(run_id: str, resources: AppResources) -> AgentRun:
    run = await resources.run_repository.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": "Agent run not found."},
        )
    return run


async def _run_action(action: Awaitable[AgentRun]) -> AgentRun:
    try:
        return await action
    except RunActionError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if error.code == "RUN_NOT_FOUND"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
