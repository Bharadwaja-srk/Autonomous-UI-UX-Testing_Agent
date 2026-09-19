"""
Bug Detection Engine for Autonomous UI/UX Testing.
Correlates UI friction, console errors, network failures, and visual regressions
to automatically generate developer-ready bug reports.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.schemas import (
    BugReport, BugCategory, FindingSeverity, AgentAction,
    PerceptionState, ObservabilitySnapshot, TestRun, VisualDiffResult,
    FindingCategory, ConsoleEntry, NetworkEntry
)
from backend.config import settings

logger = logging.getLogger("autonomous_tester.bug_detector")


class BugDetector:
    """Correlates telemetry to detect and report bugs."""

    def __init__(self, ai_client=None):
        self.ai = ai_client
        self._bug_counter = 0

    def detect_bugs(
        self,
        run: TestRun,
        actions: List[AgentAction],
        observability_data: ObservabilitySnapshot,
        visual_diffs: List[VisualDiffResult],
    ) -> List[BugReport]:
        """
        Analyze the full run telemetry to detect unique bugs.
        """
        bugs: List[BugReport] = []

        # 1. Detect Functional Bugs (Action failures)
        for action in actions:
            if not action.success:
                bug = self._create_functional_bug(action, run, observability_data)
                if bug:
                    bugs.append(bug)

        # 2. Detect Network Bugs (Failed API calls correlated with actions)
        for net_err in observability_data.network_entries:
            if net_err.failed and net_err.status_code != 404:  # Ignore random 404s for favicon etc
                bug = self._create_network_bug(net_err, actions, run)
                if bug:
                    bugs.append(bug)

        # 3. Detect Console/JS Bugs (Uncaught exceptions)
        for js_err in observability_data.js_exceptions:
            bug = self._create_console_bug(js_err, actions, run)
            if bug:
                bugs.append(bug)
                
        # 4. Detect UX Friction Bugs (from Evaluator findings)
        for finding in run.findings:
            if finding.category == FindingCategory.UX and finding.severity in [FindingSeverity.HIGH, FindingSeverity.CRITICAL]:
                bug = self._create_ux_bug(finding, run)
                if bug:
                    bugs.append(bug)
                    
        # 5. Detect Accessibility Bugs (from Axe-core/Perception)
        for finding in run.findings:
            if finding.category == FindingCategory.ACCESSIBILITY and finding.severity in [FindingSeverity.HIGH, FindingSeverity.CRITICAL]:
                bug = self._create_a11y_bug(finding, run)
                if bug:
                    bugs.append(bug)

        # 6. Detect Visual Bugs
        for diff in visual_diffs:
            if diff.is_significant:
                bug = self._create_visual_bug(diff, run)
                if bug:
                    bugs.append(bug)

        return self._deduplicate(bugs)

    def _assign_id(self, category: BugCategory) -> str:
        self._bug_counter += 1
        prefix = category.name[:4].upper()
        return f"BUG-{prefix}-{self._bug_counter:03d}"

    def _get_reproduction_steps(self, actions: List[AgentAction], up_to_step: int) -> List[str]:
        """Extract a clean list of steps leading up to the bug."""
        steps = []
        for a in actions:
            if a.step_number > up_to_step:
                break
            
            target = f"'{a.target_text}'" if a.target_text else f"element [ID:{a.target_id}]"
            
            if a.action_type == "navigate":
                steps.append(f"Navigate to {a.navigate_url}")
            elif a.action_type == "click":
                steps.append(f"Click on {target}")
            elif a.action_type == "type":
                steps.append(f"Type '{a.text_input}' into {target}")
            elif a.action_type == "scroll":
                steps.append(f"Scroll {a.scroll_direction}")
        
        return steps[-5:]  # Return only the last 5 steps for brevity

    def _get_env_info(self, run: TestRun) -> Dict[str, str]:
        return {
            "OS": "Windows/Linux/Mac",  # Simulated
            "Browser": "Chromium (Playwright)",
            "Viewport": f"{run.device_profile.viewport_width}x{run.device_profile.viewport_height}",
            "Device": run.device_profile.name,
            "URL": run.target_url,
            "Timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _create_functional_bug(self, action: AgentAction, run: TestRun, obs: ObservabilitySnapshot) -> Optional[BugReport]:
        target = action.target_text or action.target_selector or f"element {action.target_id}"
        
        # Correlate with console errors at this step
        step_console = [e.message for e in obs.console_entries if e.step_number == action.step_number]
        step_network = [f"{e.method} {e.url} - {e.error_message}" for e in obs.network_entries if e.step_number == action.step_number]
        
        cause = "The element was not interactable, covered by another element, or removed from the DOM."
        if step_network:
            cause = "The action likely failed due to an underlying network request failure."
        elif step_console:
            cause = "The action likely failed due to a JavaScript error on the page."

        return BugReport(
            bug_id=self._assign_id(BugCategory.FUNCTIONAL),
            title=f"Interaction Failure: Cannot {action.action_type} {target}",
            severity=FindingSeverity.HIGH,
            category=BugCategory.FUNCTIONAL,
            description=f"The agent attempted to {action.action_type} {target} but the action failed: {action.error}",
            expected_behavior=f"The {action.action_type} action should complete successfully and update the UI state.",
            actual_behavior=f"Action failed with error: {action.error}",
            reproduction_steps=self._get_reproduction_steps(run.actions, action.step_number),
            screenshot_path=action.screenshot_before,
            console_errors=step_console,
            network_errors=step_network,
            environment_info=self._get_env_info(run),
            suggested_cause=cause,
            suggested_fix="Verify element visibility, z-index, and ensure it is not blocked by popups. Check for JS errors attached to the event listener.",
            step_number=action.step_number
        )

    def _create_network_bug(self, entry: NetworkEntry, actions: List[AgentAction], run: TestRun) -> Optional[BugReport]:
        # Filter out tracking/analytics failures which aren't usually product bugs
        if any(x in entry.url for x in ["analytics", "tracker", "telemetry", "google-analytics"]):
            return None
            
        step = entry.step_number or 0
        
        return BugReport(
            bug_id=self._assign_id(BugCategory.NETWORK),
            title=f"API Failure: {entry.status_code or 'Failed'} on {entry.method} {entry.url.split('?')[0][-30:]}",
            severity=FindingSeverity.HIGH if entry.status_code and entry.status_code >= 500 else FindingSeverity.MEDIUM,
            category=BugCategory.NETWORK,
            description=f"A network request failed during the user journey. URL: {entry.url}",
            expected_behavior="The API request should return a 2xx success status code.",
            actual_behavior=f"Request failed: {entry.error_message}",
            reproduction_steps=self._get_reproduction_steps(actions, step),
            network_errors=[f"{entry.method} {entry.url} - {entry.error_message}"],
            environment_info=self._get_env_info(run),
            suggested_cause="Backend service unavailable, CORS issue, or invalid request payload payload.",
            suggested_fix="Check server logs for the corresponding endpoint. Verify request payload format and CORS headers.",
            step_number=step
        )

    def _create_console_bug(self, exception_msg: str, actions: List[AgentAction], run: TestRun) -> Optional[BugReport]:
        # Extract first line of exception for title
        title = exception_msg.split('\n')[0][:80]
        
        return BugReport(
            bug_id=self._assign_id(BugCategory.CONSOLE),
            title=f"JS Exception: {title}",
            severity=FindingSeverity.HIGH,
            category=BugCategory.CONSOLE,
            description=f"An uncaught JavaScript exception occurred during execution.",
            expected_behavior="The application should handle state changes without throwing uncaught exceptions.",
            actual_behavior=f"Exception thrown: {exception_msg[:300]}...",
            reproduction_steps=self._get_reproduction_steps(actions, len(actions)),
            console_errors=[exception_msg],
            environment_info=self._get_env_info(run),
            suggested_cause="Null reference, undefined variable, or unhandled promise rejection in frontend code.",
            suggested_fix="Add null checks and try-catch blocks around the affected component logic.",
            step_number=None
        )

    def _create_ux_bug(self, finding, run: TestRun) -> Optional[BugReport]:
        return BugReport(
            bug_id=self._assign_id(BugCategory.UX),
            title=f"UX Issue: {finding.title}",
            severity=finding.severity,
            category=BugCategory.UX,
            description=finding.description,
            expected_behavior="Smooth user journey without repeated clicks, dead-ends, or loops.",
            actual_behavior=finding.evidence or "Friction detected in user flow.",
            reproduction_steps=self._get_reproduction_steps(run.actions, finding.step_number or len(run.actions)),
            environment_info=self._get_env_info(run),
            suggested_cause="Poor loading state feedback, confusing navigation, or missing validation messages.",
            suggested_fix=finding.recommendation,
            step_number=finding.step_number
        )

    def _create_a11y_bug(self, finding, run: TestRun) -> Optional[BugReport]:
        return BugReport(
            bug_id=self._assign_id(BugCategory.ACCESSIBILITY),
            title=f"A11y Violation: {finding.title}",
            severity=finding.severity,
            category=BugCategory.ACCESSIBILITY,
            description=finding.description,
            expected_behavior="The element should comply with WCAG accessibility standards.",
            actual_behavior=finding.evidence or "Element violates a11y rules.",
            reproduction_steps=self._get_reproduction_steps(run.actions, finding.step_number or len(run.actions)),
            environment_info=self._get_env_info(run),
            suggested_cause="Missing ARIA attributes, poor color contrast, or incorrect HTML semantics.",
            suggested_fix=finding.recommendation,
            step_number=finding.step_number
        )

    def _create_visual_bug(self, diff: VisualDiffResult, run: TestRun) -> Optional[BugReport]:
        return BugReport(
            bug_id=self._assign_id(BugCategory.VISUAL),
            title=f"Visual Regression: {diff.diff_percentage}% change detected",
            severity=FindingSeverity.MEDIUM,
            category=BugCategory.VISUAL,
            description=f"A significant visual change was detected compared to the baseline. {diff.ai_explanation}",
            expected_behavior="The UI should match the baseline design.",
            actual_behavior=f"{len(diff.changed_regions)} regions visually altered.",
            reproduction_steps=self._get_reproduction_steps(run.actions, diff.step_number),
            screenshot_path=diff.diff_path,
            environment_info=self._get_env_info(run),
            suggested_cause="CSS changes, unstyled content flash, or dynamic content rendering issues.",
            suggested_fix="Review the diff image to confirm if changes are intentional. If not, revert recent CSS/layout changes affecting this view.",
            step_number=diff.step_number
        )

    def _deduplicate(self, bugs: List[BugReport]) -> List[BugReport]:
        """Remove duplicate bugs based on category and title similarity."""
        unique_bugs = []
        seen_signatures = set()

        for bug in bugs:
            # Create a signature based on category and first 40 chars of title
            sig = f"{bug.category.name}_{bug.title[:40].lower()}"
            
            # For network bugs, use the endpoint URL as signature
            if bug.category == BugCategory.NETWORK and bug.network_errors:
                url_part = bug.network_errors[0].split('?')[0][-40:]
                sig = f"NET_{url_part}"
                
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_bugs.append(bug)

        return unique_bugs
