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
    FUNCTIONAL = "FUNCTIONAL"
    VISUAL = "VISUAL"
    CONSOLE = "CONSOLE"
    NETWORK = "NETWORK"
    RESPONSIVE = "RESPONSIVE"
    OTHER = "OTHER"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
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


class TestMode(str, Enum):
    GOAL_DIRECTED = "goal_directed"
    EXPLORATORY = "exploratory"
    VISUAL_REGRESSION = "visual_regression"


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BugCategory(str, Enum):
    FUNCTIONAL = "FUNCTIONAL"
    VISUAL = "VISUAL"
    ACCESSIBILITY = "ACCESSIBILITY"
    UX = "UX"
    CONSOLE = "CONSOLE"
    NETWORK = "NETWORK"
    RESPONSIVE = "RESPONSIVE"


class SessionEventType(str, Enum):
    NAVIGATION = "NAVIGATION"
    PERCEPTION = "PERCEPTION"
    AI_DECISION = "AI_DECISION"
    ACTION_EXECUTE = "ACTION_EXECUTE"
    ACTION_SUCCESS = "ACTION_SUCCESS"
    ACTION_FAILURE = "ACTION_FAILURE"
    RECOVERY_ATTEMPT = "RECOVERY_ATTEMPT"
    RECOVERY_SUCCESS = "RECOVERY_SUCCESS"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    BUG_DETECTED = "BUG_DETECTED"
    GOAL_COMPLETED = "GOAL_COMPLETED"
    GOAL_FAILED = "GOAL_FAILED"
    SAFETY_STOP = "SAFETY_STOP"
    A11Y_AUDIT = "A11Y_AUDIT"
    VISUAL_DIFF = "VISUAL_DIFF"


# ─── Device Profiles ──────────────────────────────────────────────

class DeviceProfile(BaseModel):
    name: str = "desktop"
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    device_scale_factor: int = 1
    is_mobile: bool = False
    has_touch: bool = False


# ─── Safety Configuration ─────────────────────────────────────────

class SafetyConfig(BaseModel):
    max_actions: int = 50
    max_retries: int = 3
    max_execution_time_s: int = 300
    max_navigation_depth: int = 10
    max_repeated_failures: int = 5
    confirm_destructive_actions: bool = True
    destructive_keywords: List[str] = Field(default_factory=lambda: [
        "delete", "remove", "cancel order", "deactivate",
        "close account", "unsubscribe", "purchase", "pay now",
        "confirm payment", "place order", "send message",
    ])


# ─── Core Models (Preserved) ──────────────────────────────────────

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
    decision_evidence: str = ""
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
    mode: TestMode = TestMode.GOAL_DIRECTED
    device_profile: DeviceProfile = Field(default_factory=DeviceProfile)
    start_time: str = Field(default_factory=get_utc_now_iso)
    end_time: Optional[str] = None
    actions: List[AgentAction] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    state_hashes: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


# ─── Observability Models ──────────────────────────────────────────

class ConsoleEntry(BaseModel):
    level: str = "error"  # error, warning, info, log
    message: str = ""
    source: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: str = Field(default_factory=get_utc_now_iso)
    step_number: Optional[int] = None


class NetworkEntry(BaseModel):
    method: str = "GET"
    url: str = ""
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    failed: bool = False
    error_message: Optional[str] = None
    timestamp: str = Field(default_factory=get_utc_now_iso)
    step_number: Optional[int] = None


class ObservabilitySnapshot(BaseModel):
    console_entries: List[ConsoleEntry] = Field(default_factory=list)
    network_entries: List[NetworkEntry] = Field(default_factory=list)
    js_exceptions: List[str] = Field(default_factory=list)


# ─── Recovery Models ──────────────────────────────────────────────

class RecoveryAction(BaseModel):
    step_number: int
    original_error: str
    recovery_strategy: str
    recovered_selector: Optional[str] = None
    success: bool = False
    explanation: str = ""
    timestamp: str = Field(default_factory=get_utc_now_iso)


# ─── Visual Regression Models ─────────────────────────────────────

class ChangedRegion(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    description: str = ""


class VisualDiffResult(BaseModel):
    step_number: int = 0
    baseline_path: str = ""
    current_path: str = ""
    diff_path: str = ""
    diff_percentage: float = 0.0
    changed_regions: List[ChangedRegion] = Field(default_factory=list)
    ai_explanation: str = ""
    is_significant: bool = False


# ─── Test Planner Models ──────────────────────────────────────────

class TestCase(BaseModel):
    case_id: str
    title: str
    description: str
    priority: int = 1  # 1=highest
    risk_level: RiskLevel = RiskLevel.MEDIUM
    category: str = "functional"  # positive, negative, edge_case, error_state, boundary
    steps: List[str] = Field(default_factory=list)
    expected_outcomes: List[str] = Field(default_factory=list)
    status: TestStatus = TestStatus.PENDING


class TestPlan(BaseModel):
    plan_id: str
    goal: str
    target_url: str = ""
    test_cases: List[TestCase] = Field(default_factory=list)
    risk_assessment: str = ""
    total_estimated_steps: int = 0
    timestamp: str = Field(default_factory=get_utc_now_iso)


# ─── Bug Report Models ────────────────────────────────────────────

class BugReport(BaseModel):
    bug_id: str
    title: str
    severity: FindingSeverity = FindingSeverity.MEDIUM
    category: BugCategory = BugCategory.FUNCTIONAL
    description: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    reproduction_steps: List[str] = Field(default_factory=list)
    screenshot_path: Optional[str] = None
    dom_snapshot: Optional[str] = None
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    environment_info: Dict[str, str] = Field(default_factory=dict)
    suggested_cause: str = ""
    suggested_fix: str = ""
    step_number: Optional[int] = None
    url: str = ""
    timestamp: str = Field(default_factory=get_utc_now_iso)


# ─── Session Recording Models ─────────────────────────────────────

class SessionEvent(BaseModel):
    event_type: SessionEventType
    timestamp: str = Field(default_factory=get_utc_now_iso)
    elapsed_ms: int = 0
    step_number: int = 0
    action_summary: str = ""
    reasoning: str = ""
    screenshot_ref: Optional[str] = None
    state_url: Optional[str] = None
    recovery: Optional[RecoveryAction] = None
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    bug_ids: List[str] = Field(default_factory=list)


class SessionRecording(BaseModel):
    run_id: str
    events: List[SessionEvent] = Field(default_factory=list)
    total_duration_ms: int = 0
    start_time: str = Field(default_factory=get_utc_now_iso)
    device_profile: DeviceProfile = Field(default_factory=DeviceProfile)


# ─── Evaluation Result (Extended) ─────────────────────────────────

class EvaluationResult(BaseModel):
    run_id: str
    goal: str
    target_url: str
    status: TestStatus
    mode: TestMode = TestMode.GOAL_DIRECTED
    total_steps: int
    friction_score: float
    accessibility_score: float
    findings: List[Finding] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    journey: List[Dict[str, Any]] = Field(default_factory=list)
    bug_reports: List[BugReport] = Field(default_factory=list)
    visual_diffs: List[VisualDiffResult] = Field(default_factory=list)
    console_errors: List[ConsoleEntry] = Field(default_factory=list)
    network_errors: List[NetworkEntry] = Field(default_factory=list)
    recovery_actions: List[RecoveryAction] = Field(default_factory=list)
    device_profile: DeviceProfile = Field(default_factory=DeviceProfile)
    test_plan: Optional[TestPlan] = None
    session_recording_ref: Optional[str] = None


# ─── API Request (Extended) ───────────────────────────────────────

class StartTestRequest(BaseModel):
    url: str
    goal: str
    max_steps: Optional[int] = None
    headless: Optional[bool] = None
    mode: TestMode = TestMode.GOAL_DIRECTED
    device: str = "desktop"
    enable_visual_regression: bool = False
    baseline_run_id: Optional[str] = None
    enable_github_issues: bool = False
    enable_pii_redaction: bool = False
    safety_config: Optional[SafetyConfig] = None
