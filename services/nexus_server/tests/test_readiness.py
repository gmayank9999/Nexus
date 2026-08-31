import pytest

from app.health import ReadinessService


@pytest.mark.asyncio
async def test_readiness_checks_all_components() -> None:
    async def healthy() -> None:
        return None

    async def unhealthy() -> None:
        raise ConnectionError("secret connection details must not leak")

    result = await ReadinessService({"postgres": healthy, "redis": unhealthy}).check()

    assert result.status == "not_ready"
    assert result.components["postgres"].status == "up"
    assert result.components["redis"].status == "down"
    assert result.components["redis"].detail == "ConnectionError"
