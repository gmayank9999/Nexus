import json
from typing import Any

from pydantic import BaseModel

from app.providers.errors import ProviderError


def parse_structured_content(
    content: str,
    response_schema: type[BaseModel] | None,
) -> dict[str, Any] | None:
    if response_schema is None:
        return None
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError as error:
        raise ProviderError(
            "INVALID_PROVIDER_RESPONSE",
            "The provider did not return valid structured JSON.",
            retryable=True,
        ) from error
    if not isinstance(decoded, dict):
        raise ProviderError(
            "INVALID_PROVIDER_RESPONSE",
            "The provider returned a non-object structured response.",
            retryable=True,
        )
    validated = response_schema.model_validate(decoded)
    return validated.model_dump(mode="json")
