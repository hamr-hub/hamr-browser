from pydantic import BaseModel
from typing import Any, Dict, Literal, Optional


class FlowRunResult(BaseModel):
    flow_id: str
    status: Literal["success", "error"]
    duration_ms: int
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class FlowSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    parameter_count: int
    has_auth: bool
