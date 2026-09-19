"""
Main Orchestrator for Autonomous UI/UX & Accessibility Testing.
Coordinates perception, AI agent reasoning, browser driver execution, loop detection,
and evaluation reporting. Integrates observability, recovery, and visual engines.
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
from backend.observability import ObservabilityEngine
from backend.accessibility import AccessibilityEngine
from backend.visual import VisualRegressionEngine
from backend.recovery import RecoveryEngine
from backend.session import SessionRecorder, SessionEventType
from backend.devices import get_device_profile, ResponsiveAnalyzer
from backend.risk import RiskAnalyzer
from backend.planner import TestPlanner, ExploratoryEngine
from backend.bug_detector import BugDetector

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
    TestMode,
    SafetyConfig,
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

        # Initialize core engines
        self.agent = AIAgent()
        self.evaluator = Evaluator(loop_threshold=self.loop_threshold)
        self.reporter = ReportGenerator()
        
        # Initialize new extended engines
        self.observability = ObservabilityEngine()
        self.accessibility = AccessibilityEngine()
        self.visual = VisualRegressionEngine()
        self.session = SessionRecorder()
        self.bug_detector = BugDetector(ai_client=self.agent.client)
        self.risk = RiskAnalyzer()
        self.responsive = ResponsiveAnalyzer()
        self.planner = TestPlanner(ai_client=self.agent.client)
        
        # Driver and Recovery will be initialized per-run with device profile
        self.driver: Optional[BrowserDriver] = None
        self.perception: Optional[PerceptionEngine] = None
        self.recovery: Optional[RecoveryEngine] = None
        self.exploratory: Optional[ExploratoryEngine] = None

        self.current_run: Optional[TestRun] = None
        self.is_running = False

    async def execute_test(
        self, 
        goal: str, 
        target_url: str,
        mode: TestMode = TestMode.GOAL_DIRECTED,
        device_name: str = "desktop",
        enable_visual_regression: bool = False,
        baseline_run_id: Optional[str] = None,
        enable_pii_redaction: bool = False,
        safety_config: Optional[SafetyConfig] = None
    ) -> EvaluationResult:
        """
        Execute an end-to-end autonomous test run.
        """
        now = datetime.now(timezone.utc)
        run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = settings.RUNS_DIR / run_id
        run_screenshots_dir = settings.SCREENSHOTS_DIR / run_id
        run_screenshots_dir.mkdir(parents=True, exist_ok=True)

        device_profile = get_device_profile(device_name)
        safety = safety_config or SafetyConfig()

        self.current_run = TestRun(
            run_id=run_id,
            goal=goal,
            target_url=target_url,
            status=TestStatus.RUNNING,
            mode=mode,
            device_profile=device_profile,
            start_time=now.isoformat(),
        )
        self.is_running = True
        
        # Initialize run-specific engines
        self.driver = BrowserDriver(headless=self.headless, device_profile=device_profile)
        self.perception = PerceptionEngine(self.driver)
        self.recovery = RecoveryEngine(max_retries=safety.max_retries, driver=self.driver, perception=self.perception)
        self.exploratory = ExploratoryEngine(self.driver, self.perception, max_depth=safety.max_navigation_depth)

        logger.info(f"Starting test [{run_id}] | Mode: {mode.value} | Device: {device_profile.name} | URL: {target_url}")
        self._notify_status("Test started. Launching browser...", 0)

        # 1. Start session recording
        self.session.start(run_id, device_profile)

        try:
            # 2. Start browser & attach observability
            await self.driver.start()
            if self.driver.page:
                await self.observability.attach(self.driver.page)
                
            nav_success, nav_err = await self.driver.navigate(target_url)
            if not nav_success:
                raise RuntimeError(f"Initial navigation failed: {nav_err}")
                
            self.session.record_event(SessionEventType.NAVIGATION, 0, f"Navigated to {target_url}")

            # 3. Generate Test Plan (if goal directed)
            test_plan = None
            if mode == TestMode.GOAL_DIRECTED:
                self._notify_status("Generating AI Test Plan...", 0)
                # Need initial state for planner context
                initial_state = await self.perception.capture_state(0, None, enable_pii=enable_pii_redaction)
                test_plan = await self.planner.generate_test_plan(goal, target_url, initial_state)
                logger.info(f"Generated test plan with {len(test_plan.test_cases)} cases. Risk: {test_plan.risk_assessment}")

            step = 1
            consecutive_failures = 0
            
            # Main Execution Loop
            while self.is_running and step <= safety.max_actions:
                self.observability.set_step(step)
                screenshot_filename = f"step_{step}.png"
                screenshot_full_path = run_screenshots_dir / screenshot_filename
                
                # Check safety elapsed time limit
                elapsed_s = (datetime.now(timezone.utc) - now).total_seconds()
                is_safe, safety_reason = self.recovery.check_safety_limits(step, elapsed_s, safety, consecutive_failures)
                if not is_safe:
                    logger.warning(f"Safety limit reached: {safety_reason}")
                    self.session.record_event(SessionEventType.SAFETY_STOP, step, safety_reason)
                    self.current_run.status = TestStatus.STOPPED
                    self.current_run.error_message = safety_reason
                    break

                # a. Perception phase
                self._notify_status(f"Observing page state (Step {step}/{safety.max_actions})...", step)
                state: PerceptionState = await self.perception.capture_state(step, screenshot_full_path, enable_pii=enable_pii_redaction)
                self.current_run.screenshots.append(screenshot_filename)
                self.current_run.state_hashes.append(state.state_hash)
                
                self.session.record_event(
                    SessionEventType.PERCEPTION, step, f"Captured state: {state.url}", 
                    screenshot_ref=screenshot_filename, state_url=state.url
                )

                # b. A11y & Responsive Analysis
                if step == 1 or step % 5 == 0:
                    self._notify_status("Running accessibility & responsive analysis...", step)
                    a11y_violations = await self.accessibility.run_axe_audit(self.driver.page, step)
                    responsive_issues = self.responsive.detect_responsive_issues(state, device_profile)
                    
                    for finding in a11y_violations + responsive_issues:
                        if not any(f.finding_id == finding.finding_id for f in self.current_run.findings):
                            self.current_run.findings.append(finding)
                            
                    if a11y_violations:
                        self.session.record_event(SessionEventType.A11Y_AUDIT, step, f"Found {len(a11y_violations)} a11y issues")

                # c. Visual Regression Check
                if enable_visual_regression and baseline_run_id:
                    baseline_path = self.visual.get_baseline(baseline_run_id, step)
                    if baseline_path:
                        diff_path = run_screenshots_dir / f"step_{step}_diff.png"
                        diff_result = self.visual.compare(baseline_path, screenshot_full_path, diff_path, step)
                        if diff_result.is_significant:
                            self.session.record_event(SessionEventType.VISUAL_DIFF, step, f"Visual regression: {diff_result.diff_percentage}% changed")
                    else:
                        self.visual.save_baseline(run_id, step, screenshot_full_path)
                elif enable_visual_regression:
                    self.visual.save_baseline(run_id, step, screenshot_full_path)

                # d. Loop detection
                hash_occurrences = self.current_run.state_hashes.count(state.state_hash)
                if hash_occurrences >= self.loop_threshold:
                    self._notify_status("Loop detected: Repeated state visited.", step)

                # e. AI Agent Decision
                self._notify_status("AI Agent analyzing state...", step)
                action: AgentAction = None
                
                if mode == TestMode.EXPLORATORY:
                    target_info = self.exploratory.get_next_exploration_target(state)
                    if target_info:
                        action = AgentAction(
                            step_number=step, action_type=ActionType.CLICK,
                            target_id=target_info["id"], target_selector=target_info["selector"],
                            target_text=target_info["text"], reasoning=f"Exploring new unvisited element: {target_info['text']}",
                            decision_evidence="Exploratory mode heuristic selection."
                        )
                    else:
                        action = AgentAction(step_number=step, action_type=ActionType.DONE, reasoning="Exploration complete. No more unvisited targets.")
                else:
                    action = await self.agent.decide_next_action(
                        goal=goal, state=state, action_history=self.current_run.actions, screenshot_full_path=screenshot_full_path
                    )

                logger.info(f"Step {step} Action: {action.action_type.value} on [{action.target_id or action.target_text}] - {action.reasoning}")
                self.session.record_event(SessionEventType.AI_DECISION, step, action.action_type.value, action.reasoning)

                # f. Termination checks
                if action.action_type == ActionType.DONE:
                    action.success = True
                    self.current_run.actions.append(action)
                    self.current_run.status = TestStatus.COMPLETED
                    self.session.record_event(SessionEventType.GOAL_COMPLETED, step, "Agent declared goal completed.")
                    break

                if action.action_type == ActionType.FAILED:
                    action.success = False
                    self.current_run.actions.append(action)
                    self.current_run.status = TestStatus.FAILED
                    self.current_run.error_message = action.reasoning
                    self.session.record_event(SessionEventType.GOAL_FAILED, step, f"Agent declared goal failed: {action.reasoning}")
                    break

                # g. Risk & Safety check
                risk_level, risk_explanation = self.risk.assess_page_risk(state.url, state.elements)
                if self.risk.should_confirm_action(action, safety):
                    logger.warning(f"Safety restriction: Action targets a destructive element in a {risk_level.value} risk page.")
                    # In a real UI, this would pause and ask for WebSocket confirmation. 
                    # For automation, if confirm is true, we block it to be safe.
                    action.success = False
                    action.error = f"Blocked by safety configuration. Destructive action detected on {risk_level.value} risk page."
                    self.current_run.actions.append(action)
                    self.session.record_event(SessionEventType.SAFETY_STOP, step, action.error)
                    break

                # h. Execute Action
                self._notify_status(f"Executing: {action.action_type.value}...", step, action)
                exec_success, exec_err = await self._execute_action(action, state)
                action.success = exec_success
                action.error = exec_err

                # i. Recovery on Failure
                if not exec_success:
                    self.session.record_event(SessionEventType.ACTION_FAILURE, step, f"Execution failed: {exec_err}")
                    consecutive_failures += 1
                    
                    if self.recovery.is_critical_failure(action, exec_err):
                        logger.warning(f"Critical failure detected. Halting. {exec_err}")
                        self.current_run.status = TestStatus.FAILED
                        self.current_run.error_message = f"Critical failure: {exec_err}"
                        self.current_run.actions.append(action)
                        break
                        
                    self._notify_status("Action failed. Attempting intelligent recovery...", step, action)
                    self.session.record_event(SessionEventType.RECOVERY_ATTEMPT, step, "Attempting recovery strategies")
                    
                    recovered_action, recovery_log = await self.recovery.attempt_recovery(action, state, exec_err)
                    
                    if recovered_action:
                        action = recovered_action  # Replace with the successful recovered action
                        consecutive_failures = 0
                        self._notify_status("Recovery successful!", step, action)
                        self.session.record_event(SessionEventType.RECOVERY_SUCCESS, step, recovery_log.explanation, recovery=recovery_log)
                    else:
                        self.session.record_event(SessionEventType.RECOVERY_FAILED, step, recovery_log.explanation, recovery=recovery_log)
                else:
                    consecutive_failures = 0
                    self.session.record_event(SessionEventType.ACTION_SUCCESS, step, f"Executed {action.action_type.value}")

                self.current_run.actions.append(action)
                
                # Retrieve step observability data
                obs_snapshot = self.observability.get_recent(step, enable_pii=enable_pii_redaction)
                if obs_snapshot.console_entries or obs_snapshot.network_entries:
                    self.session.events[-1].console_errors = [e.message for e in obs_snapshot.console_entries if e.level == "error"]
                    self.session.events[-1].network_errors = [e.error_message for e in obs_snapshot.network_entries if e.failed]

                await asyncio.sleep(settings.ACTION_DELAY_MS / 1000.0)
                step += 1

            # End of step loop
            if step > safety.max_actions and self.current_run.status == TestStatus.RUNNING:
                self.current_run.status = TestStatus.STOPPED
                self.current_run.error_message = f"Maximum action limit ({safety.max_actions}) reached."
                logger.info(f"Max actions ({safety.max_actions}) reached.")

        except Exception as e:
            logger.error(f"Test run execution crashed: {str(e)}", exc_info=True)
            self.current_run.status = TestStatus.FAILED
            self.current_run.error_message = str(e)
            self.session.record_event(SessionEventType.GOAL_FAILED, step if 'step' in locals() else 0, f"System crash: {str(e)}")
        finally:
            self.is_running = False
            self.current_run.end_time = datetime.now(timezone.utc).isoformat()
            if self.driver:
                await self.driver.close()
            
            # Stop session recording
            recording = self.session.finish()

        # 6. Post-Run Evaluation, Bug Detection & Reporting
        self._notify_status("Evaluating journey & generating bug reports...", len(self.current_run.actions))
        
        # Core evaluation
        evaluation = self.evaluator.evaluate(self.current_run)
        
        # Bug detection correlating all telemetry
        obs_data = self.observability.get_snapshot(enable_pii=enable_pii_redaction)
        bugs = self.bug_detector.detect_bugs(self.current_run, self.current_run.actions, obs_data, [])
        if bugs:
            self.session.record_event(SessionEventType.BUG_DETECTED, len(self.current_run.actions), f"Detected {len(bugs)} bugs during analysis")
        
        # Attach new data to evaluation
        evaluation.test_plan = test_plan
        evaluation.bug_reports = bugs
        evaluation.console_errors = [e for e in obs_data.console_entries if e.level == "error"]
        evaluation.network_errors = [e for e in obs_data.network_entries if e.failed]
        evaluation.recovery_actions = list(self.recovery.recovery_log) if self.recovery else []
        evaluation.session_recording_ref = recording.run_id
        evaluation.device_profile = self.current_run.device_profile
        
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
        if not self.driver:
            return False, "Driver not initialized"
            
        action_type = action.action_type
        
        if action_type == ActionType.CLICK:
            selector = action.target_selector
            if not selector and action.target_id:
                for el in state.elements:
                    if el.id == action.target_id:
                        selector = el.selector
                        break
            if selector:
                return await self.driver.click(selector=selector)
            elif action.target_id:
                for el in state.elements:
                    if el.id == action.target_id:
                        coords = {
                            "x": el.bounding_box.x + el.bounding_box.width / 2,
                            "y": el.bounding_box.y + el.bounding_box.height / 2
                        }
                        return await self.driver.click(coordinates=coords)
            elif action.target_text:
                return await self.driver.click_by_text(action.target_text)
                
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                self.on_step_callback(payload)
            except Exception as e:
                logger.warning(f"Error in status callback: {e}")
