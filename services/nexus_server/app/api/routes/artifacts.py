from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_resources
from app.storage.artifact_repository import Artifact
from app.storage.resources import AppResources

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("", response_model=list[Artifact])
async def list_artifacts(
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
    run_id: str | None = None,
) -> list[Artifact]:
    return await resources.artifact_repository.list_for_user(user_id, run_id)


@router.get("/{artifact_id}", response_model=Artifact)
async def get_artifact(
    artifact_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> Artifact:
    artifact = await resources.artifact_repository.get(artifact_id, user_id)
    if artifact is None:
        raise HTTPException(404, detail={"code": "ARTIFACT_NOT_FOUND"})
    return artifact
