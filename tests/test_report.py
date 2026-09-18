"""
Tests for Report Generator (HTML & JSON outputs).
"""

from pathlib import Path
from backend.evaluator import Evaluator
from backend.report import ReportGenerator
from backend.schemas import TestRun, TestStatus, AgentAction, ActionType


def test_report_generation(tmp_path):
    run = TestRun(
        run_id="test_report_run",
        goal="Search and checkout running shoes",
        target_url="http://127.0.0.1:8000/demo/",
        status=TestStatus.COMPLETED,
        actions=[
            AgentAction(step_number=1, action_type=ActionType.CLICK, target_id=1, target_text="Search", reasoning="Clicked search", success=True),
            AgentAction(step_number=2, action_type=ActionType.DONE, reasoning="Goal achieved", success=True),
        ],
        state_hashes=["hash1", "hash2"],
    )

    evaluator = Evaluator()
    result = evaluator.evaluate(run)

    reports_dir = tmp_path / "reports"
    screenshots_dir = tmp_path / "screenshots"
    generator = ReportGenerator(reports_dir=reports_dir, screenshots_dir=screenshots_dir)

    html_path, json_path = generator.generate(result, run)

    assert html_path.exists()
    assert json_path.exists()
    assert html_path.stat().st_size > 0
    assert json_path.stat().st_size > 0

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        assert "Autonomous UI/UX & Accessibility Audit" in html_content
        assert "Search and checkout running shoes" in html_content
        assert run.run_id in html_content
