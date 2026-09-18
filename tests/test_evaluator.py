"""
Tests for the Evaluator and Friction Scoring Engine.
"""

from backend.evaluator import Evaluator
from backend.schemas import (
    TestRun,
    TestStatus,
    AgentAction,
    ActionType,
    Finding,
    FindingCategory,
    FindingSeverity,
)


def test_evaluator_smooth_journey():
    run = TestRun(
        run_id="test_smooth_1",
        goal="Search and buy shoes",
        target_url="http://example.com",
        status=TestStatus.COMPLETED,
        actions=[
            AgentAction(step_number=1, action_type=ActionType.TYPE, target_id=1, text_input="shoes", success=True),
            AgentAction(step_number=2, action_type=ActionType.CLICK, target_id=2, target_text="Search", success=True),
            AgentAction(step_number=3, action_type=ActionType.CLICK, target_id=3, target_text="Product 1", success=True),
            AgentAction(step_number=4, action_type=ActionType.CLICK, target_id=4, target_text="Add to Cart", success=True),
            AgentAction(step_number=5, action_type=ActionType.DONE, success=True),
        ],
        state_hashes=["hash_a", "hash_b", "hash_c", "hash_d", "hash_e"],
    )

    evaluator = Evaluator(loop_threshold=3)
    result = evaluator.evaluate(run)

    assert result.total_steps == 5
    assert result.status == TestStatus.COMPLETED
    assert result.metrics["successful_actions"] == 5
    assert result.metrics["failed_actions"] == 0
    assert result.metrics["possible_loops"] == 0
    assert result.friction_score < 15.0  # Smooth journey should have very low friction


def test_evaluator_loop_and_failures():
    run = TestRun(
        run_id="test_loop_1",
        goal="Search shoes",
        target_url="http://example.com",
        status=TestStatus.FAILED,
        actions=[
            AgentAction(step_number=1, action_type=ActionType.CLICK, target_id=1, success=False, error="Element detached"),
            AgentAction(step_number=2, action_type=ActionType.CLICK, target_id=2, success=True),
            AgentAction(step_number=3, action_type=ActionType.BACK, success=True),
            AgentAction(step_number=4, action_type=ActionType.BACK, success=True),
            AgentAction(step_number=5, action_type=ActionType.FAILED, success=False),
        ],
        # Repeating hash 3 times
        state_hashes=["hash_a", "hash_b", "hash_a", "hash_b", "hash_a"],
    )

    evaluator = Evaluator(loop_threshold=3)
    result = evaluator.evaluate(run)

    assert result.metrics["possible_loops"] == 1
    assert result.metrics["failed_actions"] == 2
    assert result.metrics["backtracks"] == 2
    assert result.friction_score > 50.0  # Significant friction penalty
    assert any(f.category == FindingCategory.NAVIGATION and "loop" in f.title.lower() for f in result.findings)
