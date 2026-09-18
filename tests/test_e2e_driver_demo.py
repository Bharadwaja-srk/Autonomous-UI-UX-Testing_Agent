"""
End-to-end integration test with Playwright driver, Perception engine, and local Demo App.
"""

import asyncio
import os
import pytest
from pathlib import Path
from backend.driver import BrowserDriver
from backend.perception import PerceptionEngine
from backend.evaluator import Evaluator
from backend.report import ReportGenerator
from backend.schemas import TestRun, TestStatus, AgentAction, ActionType


@pytest.mark.asyncio
async def test_driver_and_perception(tmp_path):
    demo_index = Path(__file__).resolve().parent.parent / "demo_app" / "index.html"
    assert demo_index.exists()

    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        # Navigate using file:// protocol
        file_url = demo_index.as_uri()
        nav_ok, nav_err = await driver.navigate(file_url)
        assert nav_ok is True
        assert nav_err is None

        # Perception extraction
        perception = PerceptionEngine(driver)
        screenshot_path = tmp_path / "test_step1.png"
        state = await perception.capture_state(1, screenshot_path)

        assert state.url.startswith("file://")
        assert len(state.elements) > 0
        assert screenshot_path.exists()
        assert len(state.state_hash) > 0

        # Check that interactive elements were detected
        button_elements = [e for e in state.elements if e.role in ["button", "input"]]
        assert len(button_elements) >= 2

        # Check intentional A11y detection on search icon button
        unlabeled_buttons = [e for e in state.elements if any("Unlabeled" in issue or "Icon-only" in issue for issue in e.a11y_issues)]
        assert len(unlabeled_buttons) >= 1

        # Test typing into search input
        search_input = next((e for e in state.elements if e.tag == "input" and "search" in (e.placeholder or "").lower()), None)
        assert search_input is not None

        type_ok, type_err = await driver.type(selector=search_input.selector, text="blue running shoes", press_enter=True)
        assert type_ok is True

        # Test click on a product card button
        await asyncio.sleep(0.5)
        state_after_search = await perception.capture_state(2, tmp_path / "test_step2.png")
        assert len(state_after_search.elements) > 0

    finally:
        await driver.close()
