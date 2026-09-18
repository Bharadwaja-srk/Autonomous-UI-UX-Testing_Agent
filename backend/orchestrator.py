"""
Main Orchestrator for Autonomous UI/UX & Accessibility Testing.
Coordinates perception, AI agent reasoning, browser driver execution, loop detection,
and evaluation reporting.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.config import settings
from backend.driver import BrowserDriver
from backend.perception import PerceptionEngine
from backend.agent import AIAgent
from backend.evaluator import Evaluator
from backend.report import ReportGenerator
from backend.schemas import (
    TestRun,
    TestStatus,
    AgentAction,
    ActionType,
    Finding,
    FindingCategory,
    FindingSeverity,
    PerceptionState,
    EvaluationResult,
)

logger = logging.getLogger("autonomous_tester.orchestrator")


class TestOrchestrator:
    def __init__(
        self,
        headless: Optional[bool] = None,
        max_steps: Optional[int] = None,
        loop_threshold: Optional[int] = None,
        on_step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.headless = headless if headless is not None else settings.BROWSER_HEADLESS
        self.max_steps = max_steps or settings.MAX_STEPS
        self.loop_threshold = loop_threshold or settings.LOOP_THRESHOLD
        self.on_step_callback = on_step_callback

        self.driver = BrowserDriver(headless=self.headless)
        self.perception = PerceptionEngine(self.driver)
        self.agent = AIAgent()
        self.evaluator = Evaluator(loop_threshold=self.loop_threshold)
        self.reporter = ReportGenerator()

        self.current_run: Optional[TestRun] = None
        self.is_running = False

    async def execute_test(self, goal: str, target_url: str) -> EvaluationResult:
        """
        Execute an end-to-end autonomous test run.
        """
        now = datetime.now(timezone.utc)
        run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = settings.RUNS_DIR / run_id
        run_screenshots_dir = settings.SCREENSHOTS_DIR / run_id
        run_screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.current_run = TestRun(
            run_id=run_id,
            goal=goal,
            target_url=target_url,
            status=TestStatus.RUNNING,
            start_time=now.isoformat(),
        )
        self.is_running = True

        logger.info(f"Starting test run [{run_id}] | Goal: '{goal}' | URL: {target_url}")
        self._notify_status("Test started. Launching browser...", 0)

        try:
            # 1. Start browser & navigate
            await self.driver.start()
            nav_success, nav_err = await self.driver.navigate(target_url)
            if not nav_success:
                raise RuntimeError(f"Initial navigation failed: {nav_err}")

            step = 1
            while self.is_running and step <= self.max_steps:
                screenshot_filename = f"step_{step}_before.png"
                screenshot_full_path = run_screenshots_dir / screenshot_filename

                # 2. Perception phase
                self._notify_status(f"Observing page state (Step {step}/{self.max_steps})...", step)
                state: PerceptionState = await self.perception.capture_state(step, screenshot_full_path)
                self.current_run.screenshots.append(screenshot_filename)
                self.current_run.state_hashes.append(state.state_hash)

                # Collect a11y issues found by perception
                for elem in state.elements:
                    for issue_str in elem.a11y_issues:
                        # Avoid duplicate finding IDs for the same element
                        finding_id = f"A11Y-ELEM-{elem.id}"
                        if not any(f.finding_id == finding_id for f in self.current_run.findings):
                            self.current_run.findings.append(Finding(
                                finding_id=finding_id,
                                category=FindingCategory.ACCESSIBILITY,
                                severity=FindingSeverity.MEDIUM if "Unlabeled" in issue_str else FindingSeverity.LOW,
                                title="Accessibility Issue on Interactive Control",
                                description=issue_str,
                                step_number=step,
                                evidence=f"Tag: <{elem.tag}>, Role: {elem.role}, Text: '{elem.text}'",
                                recommendation="Provide descriptive aria-label, visible label element, or placeholder text."
                            ))

                # Check for active popup friction
                if state.detected_popups:
                    for popup_title in state.detected_popups:
                        finding_id = f"UX-POPUP-{step}"
                        if not any(f.finding_id == finding_id for f in self.current_run.findings):
                            self.current_run.findings.append(Finding(
                                finding_id=finding_id,
                                category=FindingCategory.UX,
                                severity=FindingSeverity.LOW,
                                title="Intercepting promotional modal or dialog",
                                description=f"An overlay modal ('{popup_title}') appeared and intercepted the primary user path.",
                                step_number=step,
                                evidence=f"Active modal: {popup_title}",
                                recommendation="Avoid intrusive modal overlays that interrupt high-intent user flows."
                            ))

                # Check for loop threshold breach
                hash_occurrences = self.current_run.state_hashes.count(state.state_hash)
                if hash_occurrences >= self.loop_threshold:
                    logger.warning(f"Loop detected: State hash {state.state_hash[:8]} occurred {hash_occurrences} times.")
                    self._notify_status("Loop detected: Repeated state visited multiple times.", step)

                # 3. AI Agent Decision phase
                self._notify_status("AI Agent analyzing state & selecting action...", step)
                action: AgentAction = await self.agent.decide_next_action(
                    goal=goal,
                    state=state,
                    action_history=self.current_run.actions,
                    screenshot_full_path=screenshot_full_path,
                )

                logger.info(f"Step {step} Action: {action.action_type.value} on [{action.target_id or action.target_text}] - {action.reasoning}")

                # 4. Check Termination conditions
                if action.action_type == ActionType.DONE:
                    logger.info("Agent declared GOAL COMPLETED.")
                    action.success = True
                    self.current_run.actions.append(action)
                    self.current_run.status = TestStatus.COMPLETED
                    self._notify_status("Goal successfully achieved!", step, action)
                    break

                if action.action_type == ActionType.FAILED:
                    logger.warning("Agent declared GOAL FAILED/IMPOSSIBLE.")
                    action.success = False
                    self.current_run.actions.append(action)
                    self.current_run.status = TestStatus.FAILED
                    self.current_run.error_message = action.reasoning
                    self._notify_status(f"Goal failed: {action.reasoning}", step, action)
                    break

                # 5. Execute Action via Browser Driver
                self._notify_status(f"Executing: {action.action_type.value}...", step, action)
                exec_success, exec_err = await self._execute_action(action, state)
                action.success = exec_success
                action.error = exec_err
                self.current_run.actions.append(action)

                # Brief stabilization
                await asyncio.sleep(settings.ACTION_DELAY_MS / 1000.0)

                step += 1

            if step > self.max_steps and self.current_run.status == TestStatus.RUNNING:
                self.current_run.status = TestStatus.STOPPED
                self.current_run.error_message = f"Maximum step limit ({self.max_steps}) reached."
                logger.info(f"Max steps ({self.max_steps}) reached.")

        except Exception as e:
            logger.error(f"Test run execution crashed: {str(e)}", exc_info=True)
            self.current_run.status = TestStatus.FAILED
            self.current_run.error_message = str(e)
        finally:
            self.is_running = False
            self.current_run.end_time = datetime.now(timezone.utc).isoformat()
            await self.driver.close()

        # 6. Post-Run Evaluation & Report Generation
        self._notify_status("Evaluating journey & generating audit report...", len(self.current_run.actions))
        evaluation = self.evaluator.evaluate(self.current_run)
        self.current_run.metrics = evaluation.metrics
        
        # Write HTML and JSON reports
        html_path, json_path = self.reporter.generate(evaluation, self.current_run)
        
        # Save run data
        with open(settings.RUNS_DIR / f"{run_id}.json", "w", encoding="utf-8") as f:
            json.dump(self.current_run.model_dump(), f, indent=2, default=str)

        self._notify_status("Audit completed successfully!", len(self.current_run.actions))
        return evaluation

    async def _execute_action(self, action: AgentAction, state: PerceptionState) -> tuple[bool, Optional[str]]:
        """Dispatch action execution to Playwright driver."""
        action_type = action.action_type
        
        if action_type == ActionType.CLICK:
            # Find selector or coordinates
            selector = action.target_selector
            if not selector and action.target_id:
                for el in state.elements:
                    if el.id == action.target_id:
                        selector = el.selector
                        break
            if selector:
                return await self.driver.click(selector=selector)
            elif action.target_id:
                # Coordinate click fallback
                for el in state.elements:
                    if el.id == action.target_id:
                        coords = {
                            "x": el.bounding_box.x + el.bounding_box.width / 2,
                            "y": el.bounding_box.y + el.bounding_box.height / 2
                        }
                        return await self.driver.click(coordinates=coords)
            return False, f"Could not resolve target selector for click: {action.target_id}"

        elif action_type == ActionType.TYPE:
            selector = action.target_selector
            if not selector and action.target_id:
                for el in state.elements:
                    if el.id == action.target_id:
                        selector = el.selector
                        break
            if selector and action.text_input:
                press_enter = action.key == "Enter"
                return await self.driver.type(selector=selector, text=action.text_input, press_enter=press_enter)
            return False, f"Missing input text or selector for type action on element {action.target_id}"

        elif action_type == ActionType.SCROLL:
            direction = action.scroll_direction or "down"
            amount = action.scroll_amount or 350
            return await self.driver.scroll(direction=direction, amount=amount)

        elif action_type == ActionType.PRESS_KEY:
            if action.key:
                return await self.driver.press_key(action.key)
            return False, "No key specified for press_key"

        elif action_type == ActionType.NAVIGATE:
            if action.navigate_url:
                return await self.driver.navigate(action.navigate_url)
            return False, "No URL specified for navigate"

        elif action_type == ActionType.BACK:
            return await self.driver.go_back()

        elif action_type == ActionType.WAIT:
            return await self.driver.wait(1.5)

        return True, None

    def _notify_status(self, message: str, step: int, action: Optional[AgentAction] = None):
        """Invoke optional real-time callback."""
        if self.on_step_callback and self.current_run:
            payload = {
                "run_id": self.current_run.run_id,
                "status": self.current_run.status.value,
                "step": step,
                "message": message,
                "action": action.model_dump() if action else None,
                "timestamp": datetime.utcnow().isoformat(),
            }
            try:
                self.on_step_callback(payload)
            except Exception as e:
                logger.warning(f"Error in status callback: {e}")
