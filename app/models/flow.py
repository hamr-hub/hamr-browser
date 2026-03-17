from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional, Union


class FlowParameter(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean"] = "string"
    required: bool = True
    description: Optional[str] = None
    example: Optional[Any] = None
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


class AuthCheck(BaseModel):
    type: Literal["navigate_and_check", "cookie_exists", "url_contains", "url_not_contains"]
    url: Optional[str] = None
    domain: Optional[str] = None
    cookie_name: Optional[str] = None
    logged_in_indicator: Optional[Dict[str, str]] = None


class AuthConfig(BaseModel):
    check: AuthCheck
    login: Optional[Dict[str, Any]] = None
    secrets_key: Optional[str] = None


class Step(BaseModel):
    type: Literal[
        "navigate",
        "click",
        "fill",
        "select",
        "wait_for_selector",
        "wait_for_url",
        "wait_for_response",
        "wait",
        "new_tab",
        "close_tab",
        "evaluate",
        "screenshot",
        "try_selectors",
        "scroll_to",
        "press_key",
    ]
    url: Optional[str] = None
    selector: Optional[str] = None
    selectors: Optional[List[str]] = None
    value: Optional[str] = None
    url_pattern: Optional[str] = None
    script: Optional[str] = None
    timeout: Optional[int] = None
    wait_until: Optional[Literal["load", "domcontentloaded", "networkidle"]] = None
    milliseconds: Optional[int] = None
    key: Optional[str] = None


class CaptureExtract(BaseModel):
    type: Literal["jsonpath", "full"] = "full"
    path: str = "$"


class CaptureConfig(BaseModel):
    type: Literal["wait_for_response", "page_evaluate"]
    url_pattern: Optional[str] = None
    method: Optional[str] = None
    script: Optional[str] = None
    timeout: int = 30000
    extract: Optional[CaptureExtract] = None
    on_timeout: Literal["error", "return_null"] = "error"


class FlowConfig(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    parameters: List[FlowParameter] = Field(default_factory=list)
    auth: Optional[AuthConfig] = None
    steps: List[Step] = Field(default_factory=list)
    capture: CaptureConfig

    class Config:
        extra = "allow"
