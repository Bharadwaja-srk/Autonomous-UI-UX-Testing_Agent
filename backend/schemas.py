"""
Pydantic Schemas for the Autonomous Black-Box UI/UX & Accessibility Testing Framework.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    PRESS_KEY = "press_key"
    NAVIGATE = "navigate"
    WAIT = "wait"
    BACK = "back"
    DONE = "done"
    FAILED = "failed"


class FindingCategory(str, Enum):
    UX = "UX"
    ACCESSIBILITY = "ACCESSIBILITY"
    NAVIGATION = "NAVIGATION"
    PERFORMANCE = "PERFORMANCE"
    OTHER = "OTHER"


class FindingSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class BoundingBox(BaseModel):
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class UIElement(BaseModel):
    id: int
    role: str = "element"
    tag: str = "div"
    text: str = ""
    aria_label: Optional[str] = None
    placeholder: Optional[str] = None
    value: Optional[str] = None
    name: Optional[str] = None
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    visible: bool = True
    enabled: bool = True
    focusable: bool = True
    href: Optional[str] = None
    selector: Optional[str] = None
    a11y_issues: List[str] = Field(default_factory=list)


class AgentAction(BaseModel):
    step_number: int
    action_type: ActionType
    target_id: Optional[int] = None
    target_text: Optional[str] = None
    target_selector: Optional[str] = None
    text_input: Optional[str] = None
    key: Optional[str] = None
    scroll_direction: Optional[str] = "down"  # "down" or "up"
    scroll_amount: Optional[int] = 300
    navigate_url: Optional[str] = None
    reasoning: str = ""
    timestamp: str = Field(default_factory=get_utc_now_iso)
    success: bool = True
    error: Optional[str] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None


class PerceptionState(BaseModel):
    step_number: int
    url: str
    title: str
    screenshot: Optional[str] = None
    elements: List[UIElement] = Field(default_factory=list)
    a11y_summary: str = ""
    dom_summary: str = ""
    state_hash: str = ""
    detected_popups: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=get_utc_now_iso)


class Finding(BaseModel):
    finding_id: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    description: str
    step_number: Optional[int] = None
    evidence: Optional[str] = None
    recommendation: str


class TestRun(BaseModel):
    run_id: str
    goal: str
    target_url: str
    status: TestStatus = TestStatus.PENDING
    start_time: str = Field(default_factory=get_utc_now_iso)
    end_time: Optional[str] = None
    actions: List[AgentAction] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    state_hashes: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class EvaluationResult(BaseModel):
    run_id: str
    goal: str
    target_url: str
    status: TestStatus
    total_steps: int
    friction_score: float
    accessibility_score: float
    findings: List[Finding] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    journey: List[Dict[str, Any]] = Field(default_factory=list)


class StartTestRequest(BaseModel):
    url: str
    goal: str
    max_steps: Optional[int] = None
    headless: Optional[bool] = None
