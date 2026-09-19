from fastapi import APIRouter

from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.memories import router as memories_router
from app.api.routes.runs import router as runs_router
from app.api.routes.stream import router as stream_router
from app.api.routes.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(artifacts_router, prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(runs_router, prefix="/api/v1")
api_router.include_router(tasks_router, prefix="/api/v1")
api_router.include_router(documents_router, prefix="/api/v1")
api_router.include_router(memories_router, prefix="/api/v1")
api_router.include_router(stream_router)
