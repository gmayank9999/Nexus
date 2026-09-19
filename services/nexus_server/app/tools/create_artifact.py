from typing import Any

from pydantic import BaseModel

from app.storage.artifact_repository import Artifact, ArtifactInput, ArtifactRepository
from app.tools.base import PermissionLevel, Tool, ToolContext


class CreateArtifactTool(Tool):
    name = "create_artifact"
    description = (
        "Save a plan, checklist, note, report, study guide, architecture diagram, "
        "or code explanation for this mission. Content is plain text or Markdown."
    )
    permission_level = PermissionLevel.WRITE_LOCAL
    input_schema = ArtifactInput

    def __init__(self, repository: ArtifactRepository) -> None:
        self._repository = repository

    async def execute(
        self, arguments: BaseModel, context: ToolContext
    ) -> dict[str, Any]:
        parsed = ArtifactInput.model_validate(arguments)
        artifact = await self._repository.create(
            Artifact(
                **parsed.model_dump(), user_id=context.user_id, run_id=context.run_id
            )
        )
        return artifact.model_dump(mode="json")
