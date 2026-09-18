"""
Evaluation Engine for Autonomous UI/UX & Accessibility Testing.
Analyzes test runs, computes transparent heuristic friction scores,
detects navigation loops, dead-ends, backtracking, and categorizes findings.
"""

import logging
from collections import Counter
from typing import List, Dict, Any, Tuple
from backend.schemas import TestRun, EvaluationResult, Finding, FindingCategory, FindingSeverity, ActionType, TestStatus

logger = logging.getLogger("autonomous_tester.evaluator")


class Evaluator:
    def __init__(self, loop_threshold: int = 3):
        self.loop_threshold = loop_threshold

    def evaluate(self, run: TestRun) -> EvaluationResult:
        """
        Perform a comprehensive post-run analysis on the recorded journey.
        """
        actions = run.actions
        state_hashes = run.state_hashes
        total_steps = len(actions)

        findings: List[Finding] = list(run.findings)

        # 1. Action success & failure metrics
        successful_actions = sum(1 for a in actions if a.success)
        failed_actions = sum(1 for a in actions if not a.success)

        # 2. Repeated Action Detection
        repeated_actions = 0
        for i in range(1, len(actions)):
            prev, curr = actions[i - 1], actions[i]
            if prev.action_type == curr.action_type and prev.target_id == curr.target_id and curr.target_id is not None:
                repeated_actions += 1
                findings.append(Finding(
                    finding_id=f"UX-REPEAT-{i+1}",
                    category=FindingCategory.UX,
                    severity=FindingSeverity.LOW if curr.success else FindingSeverity.MEDIUM,
                    title="Repeated consecutive action on same element",
                    description=f"Action '{curr.action_type.value}' was executed consecutively on target ID [{curr.target_id}] ('{curr.target_text or ''}').",
                    step_number=curr.step_number,
                    evidence=f"Step {prev.step_number} and Step {curr.step_number} both targeted element [{curr.target_id}].",
                    recommendation="Ensure interactive buttons provide clear loading or disabled feedback after user interaction to prevent repeated clicks."
                ))

        # 3. Failed Action Findings
        for a in actions:
            if not a.success:
                findings.append(Finding(
                    finding_id=f"UX-FAIL-{a.step_number}",
                    category=FindingCategory.UX,
                    severity=FindingSeverity.HIGH,
                    title=f"Failed interaction: {a.action_type.value}",
                    description=f"Action '{a.action_type.value}' on target [{a.target_id or a.target_selector or 'N/A'}] failed with error: {a.error or 'Unknown error'}",
                    step_number=a.step_number,
                    evidence=f"Reasoning: {a.reasoning}",
                    recommendation="Verify element visibility, clickable area, and prevent overlapping overlay elements from intercepting clicks."
                ))

        # 4. State Hash & Loop Analysis
        hash_counts = Counter(state_hashes)
        repeated_states = sum(count - 1 for count in hash_counts.values() if count > 1)
        
        # Check for cyclic loops (e.g. A -> B -> A -> B)
        loops_detected = 0
        for h, count in hash_counts.items():
            if count >= self.loop_threshold:
                loops_detected += 1
                findings.append(Finding(
                    finding_id=f"NAV-LOOP-{loops_detected}",
                    category=FindingCategory.NAVIGATION,
                    severity=FindingSeverity.HIGH,
                    title="Cyclic navigation loop detected",
                    description=f"The agent revisited state hash '{h[:8]}' {count} times without advancing towards the goal.",
                    step_number=None,
                    evidence=f"State hash {h[:8]} occurred {count} times in state history.",
                    recommendation="Review the navigation hierarchy. Ensure sub-pages have direct breadcrumb routes and clear call-to-action paths."
                ))

        # 5. Backtracking Analysis
        backtracks = sum(1 for a in actions if a.action_type == ActionType.BACK)
        if backtracks > 1:
            findings.append(Finding(
                finding_id="NAV-BACKTRACK",
                category=FindingCategory.NAVIGATION,
                severity=FindingSeverity.MEDIUM,
                title="Excessive user backtracking observed",
                description=f"The user journey required {backtracks} backward navigation steps to find the correct target path.",
                step_number=None,
                evidence=f"{backtracks} back navigations recorded in journey.",
                recommendation="Improve category discovery and search filtering so users can find items directly without needing browser back navigation."
            ))

        # 6. Dead-End Analysis
        dead_ends = 1 if run.status == TestStatus.FAILED and total_steps >= 5 else 0
        if dead_ends > 0:
            findings.append(Finding(
                finding_id="NAV-DEADEND",
                category=FindingCategory.NAVIGATION,
                severity=FindingSeverity.HIGH,
                title="Navigation dead end encountered",
                description="The autonomous agent reached a state where no further forward progression paths were available.",
                step_number=total_steps,
                evidence=run.error_message or "Agent reported failed/unreachable state.",
                recommendation="Ensure all empty search or error states provide fallback suggestions, related links, and primary navigation menus."
            ))

        # 7. Accessibility Summary & Score
        a11y_findings = [f for f in findings if f.category == FindingCategory.ACCESSIBILITY]
        a11y_deductions = 0
        for f in a11y_findings:
            if f.severity == FindingSeverity.HIGH:
                a11y_deductions += 15
            elif f.severity == FindingSeverity.MEDIUM:
                a11y_deductions += 10
            else:
                a11y_deductions += 5
        accessibility_score = max(0.0, min(100.0, 100.0 - a11y_deductions))

        # 8. Friction Score Calculation (Heuristic Transparent Formula)
        # Optimal path baseline is roughly 4-6 steps for standard e-commerce flows
        optimal_baseline = 4
        excess_steps = max(0, total_steps - optimal_baseline)
        
        friction_points = (
            (excess_steps * 3.0) +
            (failed_actions * 12.0) +
            (repeated_actions * 5.0) +
            (backtracks * 8.0) +
            (loops_detected * 25.0) +
            (dead_ends * 20.0) +
            (len(a11y_findings) * 4.0)
        )
        
        # If task failed completely, add failure penalty
        if run.status in [TestStatus.FAILED, TestStatus.STOPPED]:
            friction_points += 25.0

        friction_score = round(min(100.0, max(0.0, friction_points)), 1)

        # 9. Build Journey Summary
        journey: List[Dict[str, Any]] = []
        for i, a in enumerate(actions):
            journey.append({
                "step": a.step_number,
                "action": a.action_type.value,
                "target": a.target_text or (f"Element #{a.target_id}" if a.target_id else None) or a.navigate_url or "N/A",
                "input": a.text_input or a.key or None,
                "reasoning": a.reasoning,
                "success": a.success,
                "error": a.error,
                "screenshot": a.screenshot_before,
            })

        metrics = {
            "total_steps": total_steps,
            "successful_actions": successful_actions,
            "failed_actions": failed_actions,
            "repeated_actions": repeated_actions,
            "backtracks": backtracks,
            "repeated_states": repeated_states,
            "possible_loops": loops_detected,
            "dead_ends": dead_ends,
            "accessibility_issues_count": len(a11y_findings),
            "friction_score": friction_score,
            "accessibility_score": round(accessibility_score, 1),
            "completion_status": run.status.value,
        }

        return EvaluationResult(
            run_id=run.run_id,
            goal=run.goal,
            target_url=run.target_url,
            status=run.status,
            total_steps=total_steps,
            friction_score=friction_score,
            accessibility_score=accessibility_score,
            findings=findings,
            metrics=metrics,
            journey=journey,
        )
