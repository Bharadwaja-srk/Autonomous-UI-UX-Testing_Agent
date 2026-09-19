"""
Risk Assessment Engine.
Analyzes pages and forms to categorize the risk level of automated interactions,
ensuring safety limits are applied to destructive or payment-related actions.
"""

import logging
import re
from typing import List, Tuple

from backend.schemas import RiskLevel, PerceptionState, UIElement, SafetyConfig, AgentAction

logger = logging.getLogger("autonomous_tester.risk")


class RiskAnalyzer:
    """Evaluates the risk of interacting with specific pages or elements."""

    def __init__(self):
        self.critical_url_patterns = [
            r"/checkout", r"/payment", r"/billing", r"/credit-card",
            r"/admin", r"/settings/security", r"/delete", r"/deactivate"
        ]
        self.medium_url_patterns = [
            r"/cart", r"/login", r"/register", r"/signup", r"/profile"
        ]
        
        self.critical_element_keywords = [
            "credit card", "cvv", "social security", "ssn", "password",
            "delete account", "permanently delete", "cannot be undone",
            "confirm payment", "pay now", "place order"
        ]
        self.medium_element_keywords = [
            "add to cart", "buy now", "checkout", "submit", "save changes", "login"
        ]

    def assess_page_risk(self, url: str, elements: List[UIElement]) -> Tuple[RiskLevel, str]:
        """
        Assess the overall risk level of a page based on URL and contents.
        Returns (RiskLevel, explanation_string)
        """
        url_lower = url.lower()
        signals = []

        # 1. URL Pattern matching
        for pattern in self.critical_url_patterns:
            if re.search(pattern, url_lower):
                signals.append(f"Critical URL pattern matched: {pattern}")
                
        for pattern in self.medium_url_patterns:
            if re.search(pattern, url_lower):
                signals.append(f"Medium risk URL pattern matched: {pattern}")

        # 2. Element scanning
        critical_elements = 0
        medium_elements = 0
        
        for el in elements:
            if not el.visible:
                continue
                
            text = f"{el.text or ''} {el.aria_label or ''} {el.placeholder or ''} {el.name or ''}".lower()
            
            # Form field types (password, email, tel, etc)
            if el.tag == "input":
                # Password fields are high risk (security)
                if el.placeholder and "password" in el.placeholder.lower():
                    critical_elements += 1
                    signals.append("Password input detected")

            # Keyword matching
            if any(k in text for k in self.critical_element_keywords):
                critical_elements += 1
                if critical_elements <= 3:  # Limit log spam
                    signals.append(f"Critical action keyword detected in element: '{text[:30]}...'")
                    
            elif any(k in text for k in self.medium_element_keywords):
                medium_elements += 1

        # Calculate final risk
        if signals and any("Critical" in s or "Password" in s for s in signals):
            return RiskLevel.HIGH, f"Page classified as HIGH risk. Signals: {', '.join(signals[:3])}"
        
        if signals:
            return RiskLevel.MEDIUM, f"Page classified as MEDIUM risk. Signals: {', '.join(signals[:3])}"
            
        return RiskLevel.LOW, "Page classified as LOW risk. No state-mutating or sensitive signals detected."

    def should_confirm_action(self, action: AgentAction, safety_config: SafetyConfig) -> bool:
        """
        Determine if an action is potentially destructive and requires safety confirmation.
        """
        if not safety_config.confirm_destructive_actions:
            return False
            
        if action.action_type not in ["click", "type", "press_key"]:
            return False

        action_text = f"{action.target_text or ''} {action.reasoning or ''}".lower()
        
        return any(k in action_text for k in safety_config.destructive_keywords)
