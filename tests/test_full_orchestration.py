"""
Full Orchestrator integration test simulating complete autonomous journey.
"""

import pytest
from pathlib import Path
from backend.orchestrator import TestOrchestrator
from backend.schemas import TestStatus


@pytest.mark.asyncio
async def test_full_autonomous_orchestration():
    demo_index = Path(__file__).resolve().parent.parent / "demo_app" / "index.html"
    file_url = demo_index.as_uri()

    orchestrator = TestOrchestrator(
        headless=True,
        max_steps=12,
        loop_threshold=3,
    )

    result = await orchestrator.execute_test(
        goal="Search for blue running shoes and add one to the cart.",
        target_url=file_url,
    )

    assert result is not None
    assert result.total_steps >= 2
    assert result.status in [TestStatus.COMPLETED, TestStatus.STOPPED]
    assert result.friction_score >= 0.0
    assert len(result.journey) >= 2
    assert len(result.findings) >= 1  # Should catch the intentional unlabeled search icon or promo modal

    # Check generated files
    report_html = Path("reports") / f"{result.run_id}.html"
    report_json = Path("reports") / f"{result.run_id}.json"
    assert report_html.exists()
    assert report_json.exists()
