from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(default="local", min_length=1, max_length=100)
    max_iterations: int | None = Field(default=None, ge=1, le=100)
