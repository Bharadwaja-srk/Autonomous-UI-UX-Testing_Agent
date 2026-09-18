"""
Tests for schemas in the autonomous testing framework.
"""

from backend.schemas import (
    AgentAction,
    ActionType,
    UIElement,
    Finding,
    FindingCategory,
    FindingSeverity,
    TestRun,
    TestStatus,
    EvaluationResult,
    BoundingBox,
)


def test_agent_action_schema():
    action = AgentAction(
        step_number=1,
        action_type=ActionType.CLICK,
        target_id=5,
        target_text="Add to Cart",
        reasoning="Testing user intent to add product to cart",
    )
    assert action.step_number == 1
    assert action.action_type == ActionType.CLICK
    assert action.target_id == 5
    assert action.success is True
    assert action.error is None


def test_ui_element_schema():
    elem = UIElement(
        id=1,
        role="button",
        tag="button",
        text="Submit Order",
        aria_label="Submit Order",
        bounding_box=BoundingBox(x=10, y=20, width=100, height=40),
        visible=True,
        enabled=True,
    )
    assert elem.id == 1
    assert elem.bounding_box.width == 100
    assert elem.visible is True


def test_finding_schema():
    finding = Finding(
        finding_id="UX-1",
        category=FindingCategory.UX,
        severity=FindingSeverity.HIGH,
        title="Unlabeled button",
        description="Missing accessible name",
        recommendation="Add aria-label",
    )
    assert finding.category == FindingCategory.UX
    assert finding.severity == FindingSeverity.HIGH
