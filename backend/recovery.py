"""
Intelligent Failure Recovery & Self-Healing Engine for Autonomous UI/UX Testing.
Attempts smart recovery when actions fail instead of immediately recording failure.
Logs every recovery action for transparency.
"""

import asyncio
import logging
from typing import Optional, Tuple, List

from backend.schemas import (
    AgentAction, ActionType, PerceptionState, RecoveryAction,
    SafetyConfig, UIElement,
)

logger = logging.getLogger("autonomous_tester.recovery")


class RecoveryEngine:
    """Attempts intelligent recovery from failed actions."""

    def __init__(self, max_retries: int = 3, driver=None, perception=None):
        self.max_retries = max_retries
        self.driver = driver
        self.perception = perception
        self._retry_count = 0
        self._total_recoveries = 0
        self._recovery_log: List[RecoveryAction] = []

    @property
    def recovery_log(self) -> List[RecoveryAction]:
        return self._recovery_log

    def reset(self):
        """Reset recovery state for a new run."""
        self._retry_count = 0
        self._total_recoveries = 0
        self._recovery_log.clear()

    async def attempt_recovery(
        self,
        failed_action: AgentAction,
        state: PerceptionState,
        error: str,
    ) -> Tuple[Optional[AgentAction], RecoveryAction]:
        """
        Attempt to recover from a failed action.
        Tries multiple strategies in order of likelihood.
        Returns (recovered_action_or_None, recovery_log_entry).
        """
        step = failed_action.step_number

        if self._retry_count >= self.max_retries:
            log = RecoveryAction(
                step_number=step,
                original_error=error,
                recovery_strategy="none (retry budget exhausted)",
                success=False,
                explanation=f"Recovery budget exhausted after {self._retry_count} retries.",
            )
            self._recovery_log.append(log)
            return None, log

        self._retry_count += 1
        logger.info(f"Recovery attempt {self._retry_count}/{self.max_retries} for step {step}: {error[:80]}")

        # Strategy 1: Dismiss blocking popup/modal
        if state.detected_popups:
            result = await self._try_dismiss_popup(failed_action, state, error)
            if result:
                return result

        # Strategy 2: Semantic element relocation (find equivalent element)
        if failed_action.target_id or failed_action.target_text:
            result = await self._try_semantic_relocation(failed_action, state, error)
            if result:
                return result

        # Strategy 3: Alternative selector strategies
        if failed_action.target_selector:
            result = await self._try_alternative_selectors(failed_action, state, error)
            if result:
                return result

        # Strategy 4: Scroll and retry
        result = await self._try_scroll_and_retry(failed_action, state, error)
        if result:
            return result

        # Strategy 5: Wait and retry (transient failure)
        result = await self._try_wait_and_retry(failed_action, error)
        if result:
            return result

        # All strategies failed
        log = RecoveryAction(
            step_number=step,
            original_error=error,
            recovery_strategy="all_strategies_exhausted",
            success=False,
            explanation="All recovery strategies were attempted but none succeeded.",
        )
        self._recovery_log.append(log)
        return None, log

    async def _try_dismiss_popup(
        self, action: AgentAction, state: PerceptionState, error: str
    ) -> Optional[Tuple[Optional[AgentAction], RecoveryAction]]:
        """Try to dismiss a blocking popup and retry the original action."""
        if not self.driver:
            return None

        dismiss_keywords = ["close", "dismiss", "x", "no thanks", "cancel", "continue", "got it", "ok", "accept"]

        for el in state.elements:
            text_label = f"{el.text or ''} {el.aria_label or ''}".lower()
            if any(k in text_label for k in dismiss_keywords):
                try:
                    if el.selector:
                        success, _ = await self.driver.click(selector=el.selector, timeout=3000)
                        if success:
                            await asyncio.sleep(0.5)

                            # Now retry original action
                            retry_success = await self._retry_original(action, state)
                            log = RecoveryAction(
                                step_number=action.step_number,
                                original_error=error,
                                recovery_strategy="dismiss_popup_then_retry",
                                recovered_selector=el.selector,
                                success=retry_success,
                                explanation=f"Dismissed popup via '{el.text or el.aria_label}' and {'successfully retried' if retry_success else 'retried but still failed'}.",
                            )
                            self._recovery_log.append(log)
                            if retry_success:
                                self._total_recoveries += 1
                                recovered_action = action.model_copy()
                                recovered_action.success = True
                                recovered_action.error = None
                                recovered_action.decision_evidence = f"Recovery: dismissed popup '{el.text}', then retried original action."
                                return recovered_action, log
                            return None, log
                except Exception as e:
                    logger.debug(f"Popup dismiss attempt failed: {e}")

        return None

    async def _try_semantic_relocation(
        self, action: AgentAction, state: PerceptionState, error: str
    ) -> Optional[Tuple[Optional[AgentAction], RecoveryAction]]:
        """Search for a semantically equivalent element when original target is missing."""
        if not self.driver:
            return None

        target_text = action.target_text or ""
        target_text_lower = target_text.lower()

        if not target_text_lower:
            return None

        # Score each visible element by semantic similarity to original target
        candidates = []
        for el in state.elements:
            if not el.visible or not el.enabled:
                continue
            el_text = f"{el.text or ''} {el.aria_label or ''}".lower()
            score = self._text_similarity(target_text_lower, el_text)
            if score > 0.4 and el.id != action.target_id:
                candidates.append((score, el))

        candidates.sort(key=lambda x: x[0], reverse=True)

        for score, el in candidates[:3]:
            try:
                if el.selector:
                    success, _ = await self.driver.click(selector=el.selector, timeout=3000)
                    if success:
                        log = RecoveryAction(
                            step_number=action.step_number,
                            original_error=error,
                            recovery_strategy="semantic_relocation",
                            recovered_selector=el.selector,
                            success=True,
                            explanation=f"Original target '{target_text}' not found. Located similar element '{el.text or el.aria_label}' (similarity: {score:.0%}).",
                        )
                        self._recovery_log.append(log)
                        self._total_recoveries += 1

                        recovered = action.model_copy()
                        recovered.success = True
                        recovered.error = None
                        recovered.target_id = el.id
                        recovered.target_text = el.text or el.aria_label
                        recovered.target_selector = el.selector
                        recovered.decision_evidence = f"Recovery: relocated element by semantic match ({score:.0%} similar to '{target_text}')."
                        return recovered, log
            except Exception:
                continue

        return None

    async def _try_alternative_selectors(
        self, action: AgentAction, state: PerceptionState, error: str
    ) -> Optional[Tuple[Optional[AgentAction], RecoveryAction]]:
        """Try alternative selector strategies: by text, by role, by coordinates."""
        if not self.driver:
            return None

        # Try clicking by text content
        if action.target_text:
            try:
                success, _ = await self.driver.click_by_text(action.target_text, timeout=3000)
                if success:
                    log = RecoveryAction(
                        step_number=action.step_number,
                        original_error=error,
                        recovery_strategy="click_by_text_fallback",
                        recovered_selector=f"text={action.target_text}",
                        success=True,
                        explanation=f"CSS selector failed. Recovered by clicking element with text '{action.target_text}'.",
                    )
                    self._recovery_log.append(log)
                    self._total_recoveries += 1

                    recovered = action.model_copy()
                    recovered.success = True
                    recovered.error = None
                    recovered.decision_evidence = f"Recovery: original CSS selector failed, used text-based selector '{action.target_text}'."
                    return recovered, log
            except Exception:
                pass

        # Try clicking by coordinates from bounding box
        if action.target_id:
            for el in state.elements:
                if el.id == action.target_id and el.bounding_box.width > 0:
                    coords = {
                        "x": el.bounding_box.x + el.bounding_box.width / 2,
                        "y": el.bounding_box.y + el.bounding_box.height / 2,
                    }
                    try:
                        success, _ = await self.driver.click(coordinates=coords, timeout=3000)
                        if success:
                            log = RecoveryAction(
                                step_number=action.step_number,
                                original_error=error,
                                recovery_strategy="coordinate_click_fallback",
                                recovered_selector=f"coords({coords['x']:.0f},{coords['y']:.0f})",
                                success=True,
                                explanation=f"CSS selector failed. Recovered by clicking at coordinates ({coords['x']:.0f}, {coords['y']:.0f}).",
                            )
                            self._recovery_log.append(log)
                            self._total_recoveries += 1

                            recovered = action.model_copy()
                            recovered.success = True
                            recovered.error = None
                            recovered.decision_evidence = f"Recovery: used coordinate-based click at ({coords['x']:.0f}, {coords['y']:.0f})."
                            return recovered, log
                    except Exception:
                        pass
                    break

        return None

    async def _try_scroll_and_retry(
        self, action: AgentAction, state: PerceptionState, error: str
    ) -> Optional[Tuple[Optional[AgentAction], RecoveryAction]]:
        """Scroll to reveal the element and retry."""
        if not self.driver:
            return None

        if "timeout" not in error.lower() and "visible" not in error.lower():
            return None  # Only applies to visibility-related failures

        try:
            await self.driver.scroll(direction="down", amount=300)
            await asyncio.sleep(0.5)

            retry_success = await self._retry_original(action, state)
            log = RecoveryAction(
                step_number=action.step_number,
                original_error=error,
                recovery_strategy="scroll_and_retry",
                success=retry_success,
                explanation=f"Scrolled down to reveal element and {'successfully retried' if retry_success else 'retry still failed'}.",
            )
            self._recovery_log.append(log)
            if retry_success:
                self._total_recoveries += 1
                recovered = action.model_copy()
                recovered.success = True
                recovered.error = None
                recovered.decision_evidence = "Recovery: scrolled to reveal element, then retried action."
                return recovered, log
        except Exception:
            pass

        return None

    async def _try_wait_and_retry(
        self, action: AgentAction, error: str
    ) -> Optional[Tuple[Optional[AgentAction], RecoveryAction]]:
        """Wait for transient issues to resolve and retry."""
        if not self.driver:
            return None

        try:
            await asyncio.sleep(1.5)
            retry_success = await self._retry_original(action, None)
            log = RecoveryAction(
                step_number=action.step_number,
                original_error=error,
                recovery_strategy="wait_and_retry",
                success=retry_success,
                explanation=f"Waited 1.5s for transient failure to resolve. {'Retry succeeded.' if retry_success else 'Retry failed.'}",
            )
            self._recovery_log.append(log)
            if retry_success:
                self._total_recoveries += 1
                recovered = action.model_copy()
                recovered.success = True
                recovered.error = None
                recovered.decision_evidence = "Recovery: waited for transient failure to resolve, then retried."
                return recovered, log
        except Exception:
            pass

        return None

    async def _retry_original(self, action: AgentAction, state: Optional[PerceptionState]) -> bool:
        """Retry the original action using its selector or coordinates."""
        if not self.driver:
            return False

        try:
            if action.action_type == ActionType.CLICK:
                if action.target_selector:
                    success, _ = await self.driver.click(selector=action.target_selector, timeout=3000)
                    return success
                elif action.target_id and state:
                    for el in state.elements:
                        if el.id == action.target_id and el.selector:
                            success, _ = await self.driver.click(selector=el.selector, timeout=3000)
                            return success

            elif action.action_type == ActionType.TYPE:
                if action.target_selector and action.text_input:
                    success, _ = await self.driver.type(
                        selector=action.target_selector,
                        text=action.text_input,
                        press_enter=action.key == "Enter",
                        timeout=3000,
                    )
                    return success
        except Exception:
            pass

        return False

    def _text_similarity(self, a: str, b: str) -> float:
        """Simple word-overlap similarity score between two strings."""
        if not a or not b:
            return 0.0
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    def is_critical_failure(self, action: AgentAction, error: str) -> bool:
        """
        Detect critical failures that should stop execution immediately.
        These include authentication, payment, security, and data destruction scenarios.
        """
        critical_keywords = [
            "authentication", "login failed", "unauthorized", "403",
            "payment", "credit card", "billing",
            "security", "certificate", "ssl",
            "delete", "permanently", "cannot be undone",
            "account deactivat", "account delet",
        ]
        error_lower = error.lower()
        action_text = f"{action.target_text or ''} {action.reasoning or ''}".lower()

        return any(k in error_lower or k in action_text for k in critical_keywords)

    def check_safety_limits(
        self,
        action_count: int,
        elapsed_time_s: float,
        safety_config: SafetyConfig,
        consecutive_failures: int = 0,
    ) -> Tuple[bool, str]:
        """
        Check if safety limits have been exceeded.
        Returns (is_safe, reason_if_not_safe).
        """
        if action_count >= safety_config.max_actions:
            return False, f"Maximum action limit ({safety_config.max_actions}) reached."

        if elapsed_time_s >= safety_config.max_execution_time_s:
            return False, f"Maximum execution time ({safety_config.max_execution_time_s}s) exceeded."

        if self._retry_count >= safety_config.max_retries:
            return False, f"Maximum retry budget ({safety_config.max_retries}) exhausted."

        if consecutive_failures >= safety_config.max_repeated_failures:
            return False, f"Too many consecutive failures ({consecutive_failures})."

        return True, ""
