"""
AI Test Planner & Exploratory Testing Engine.
Converts natural language goals into structured test plans with AI or heuristics.
Explores target applications autonomously without predefined goals.
"""

import logging
import json
import uuid
import re
from typing import List, Dict, Any, Set
from pydantic import ValidationError

from backend.schemas import TestCase, TestPlan, RiskLevel, TestStatus, PerceptionState
from backend.config import settings

logger = logging.getLogger("autonomous_tester.planner")


class TestPlanner:
    """Generates structured test plans from natural language goals."""

    def __init__(self, ai_client=None):
        self.ai = ai_client

    async def generate_test_plan(self, goal: str, target_url: str, initial_state: PerceptionState) -> TestPlan:
        """
        Generate a comprehensive test plan for the given goal.
        Uses Gemini if available, otherwise falls back to keyword-based heuristics.
        """
        logger.info(f"Generating test plan for goal: '{goal}'")
        
        test_cases = []
        if self.ai:
            test_cases = await self._generate_with_ai(goal, target_url, initial_state)
            
        if not test_cases:
            logger.info("Falling back to heuristic test plan generation")
            test_cases = self._generate_heuristically(goal, target_url)

        # Prioritize test cases (High risk / Priority 1 first)
        test_cases.sort(key=lambda x: (
            0 if x.risk_level == RiskLevel.CRITICAL else
            1 if x.risk_level == RiskLevel.HIGH else
            2 if x.risk_level == RiskLevel.MEDIUM else 3,
            x.priority
        ))

        total_steps = sum(len(tc.steps) for tc in test_cases)
        
        # Simple risk assessment heuristic based on keywords in goal
        risk_text = "LOW: General navigation"
        goal_lower = goal.lower()
        if any(w in goal_lower for w in ["checkout", "pay", "credit", "delete", "remove"]):
            risk_text = "HIGH: Contains destructive or payment-related keywords"
        elif any(w in goal_lower for w in ["add", "cart", "login", "register"]):
            risk_text = "MEDIUM: Contains state-mutating keywords"

        return TestPlan(
            plan_id=f"PLAN-{uuid.uuid4().hex[:6].upper()}",
            goal=goal,
            target_url=target_url,
            test_cases=test_cases,
            risk_assessment=risk_text,
            total_estimated_steps=total_steps
        )

    async def _generate_with_ai(self, goal: str, url: str, state: PerceptionState) -> List[TestCase]:
        """Use Gemini to generate a structured test plan."""
        # Only implemented if google-genai client is passed and configured
        if not self.ai:
            return []
            
        prompt = f"""
        You are an expert QA Engineer. Generate a comprehensive test plan for this goal:
        GOAL: "{goal}"
        TARGET URL: {url}
        
        Generate 3-5 specific test cases covering:
        1. Positive (Happy Path)
        2. Negative (Invalid input, missing fields)
        3. Edge Cases or Error States
        
        Respond with ONLY a JSON array of objects with keys:
        - title (string)
        - description (string)
        - category (string: positive, negative, edge_case, boundary)
        - priority (int: 1-3)
        - risk_level (string: HIGH, MEDIUM, LOW)
        - steps (array of strings)
        - expected_outcomes (array of strings)
        """
        
        try:
            response = self.ai.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            
            data = json.loads(response.text)
            cases = []
            for i, item in enumerate(data):
                cases.append(TestCase(
                    case_id=f"TC-{i+1:03d}",
                    title=item.get("title", f"Test Case {i+1}"),
                    description=item.get("description", ""),
                    category=item.get("category", "functional"),
                    priority=item.get("priority", 2),
                    risk_level=RiskLevel(item.get("risk_level", "MEDIUM").upper()),
                    steps=item.get("steps", []),
                    expected_outcomes=item.get("expected_outcomes", [])
                ))
            return cases
        except Exception as e:
            logger.error(f"AI Test Plan generation failed: {e}")
            return []

    def _generate_heuristically(self, goal: str, url: str) -> List[TestCase]:
        """Generate a test plan based on keyword analysis of the goal."""
        goal_lower = goal.lower()
        cases = []
        
        # Base happy path (always included)
        cases.append(TestCase(
            case_id="TC-001",
            title="Happy Path: End-to-End Goal Execution",
            description=f"Attempt to complete the exact goal: '{goal}'",
            category="positive",
            priority=1,
            risk_level=RiskLevel.HIGH if any(w in goal_lower for w in ["checkout", "pay", "delete"]) else RiskLevel.MEDIUM,
            steps=["Navigate to target URL", "Execute actions to fulfill goal"],
            expected_outcomes=["Goal is achieved successfully without errors"]
        ))
        
        # Search-related tests
        if "search" in goal_lower or "find" in goal_lower:
            match = re.search(r'search (?:for )?([a-zA-Z0-9\s]+)', goal_lower)
            term = match.group(1).strip() if match else "items"
            
            cases.append(TestCase(
                case_id="TC-002",
                title="Negative: Search for non-existent item",
                description="Verify system handles empty search results gracefully.",
                category="negative",
                priority=2,
                risk_level=RiskLevel.LOW,
                steps=["Navigate to search", "Enter random gibberish (e.g. 'xyz123999')", "Submit search"],
                expected_outcomes=["'No results found' message displayed", "No application crash"]
            ))
            
            cases.append(TestCase(
                case_id="TC-003",
                title="Edge Case: Special characters in search",
                description="Verify SQLi/XSS resilience and basic special char handling.",
                category="edge_case",
                priority=3,
                risk_level=RiskLevel.MEDIUM,
                steps=["Navigate to search", "Enter '%$#@!'", "Submit search"],
                expected_outcomes=["Results filtered safely", "No 500 server errors"]
            ))
            
        # Cart/Checkout related tests
        if any(w in goal_lower for w in ["cart", "buy", "checkout", "add to"]):
            cases.append(TestCase(
                case_id="TC-004",
                title="Negative: Empty Checkout",
                description="Verify user cannot proceed to checkout with an empty cart.",
                category="negative",
                priority=2,
                risk_level=RiskLevel.MEDIUM,
                steps=["Navigate to cart", "Ensure cart is empty", "Attempt to click checkout"],
                expected_outcomes=["Checkout button disabled or error message shown"]
            ))
            
            cases.append(TestCase(
                case_id="TC-005",
                title="Negative: Form Validation",
                description="Verify checkout form requires mandatory fields.",
                category="negative",
                priority=1,
                risk_level=RiskLevel.HIGH,
                steps=["Add item to cart", "Proceed to checkout", "Submit form empty"],
                expected_outcomes=["Validation errors displayed for required fields"]
            ))
            
        # If no specific patterns matched, add a generic resilience test
        if len(cases) == 1:
            cases.append(TestCase(
                case_id="TC-002",
                title="Resilience: Rapid Navigation",
                description="Verify application stability during rapid state changes.",
                category="edge_case",
                priority=3,
                risk_level=RiskLevel.LOW,
                steps=["Click randomly on interactive elements", "Use browser back button quickly"],
                expected_outcomes=["UI remains stable", "No console errors"]
            ))
            
        return cases


class ExploratoryEngine:
    """Explores the application autonomously to discover pages and features."""
    
    def __init__(self, driver, perception, max_depth: int = 5):
        self.driver = driver
        self.perception = perception
        self.max_depth = max_depth
        self.visited_states: Set[str] = set()
        self.navigation_graph: Dict[str, List[str]] = {}
        self.discovered_urls: Set[str] = set()

    def get_next_exploration_target(self, state: PerceptionState) -> Optional[Dict[str, Any]]:
        """
        Analyze current state and pick the best unexplored interactive element.
        Returns a dict with 'id', 'selector', 'text' or None if dead end.
        """
        self.visited_states.add(state.state_hash)
        self.discovered_urls.add(state.url)
        
        # Strategy: Prefer links and buttons we haven't clicked yet
        # Since we don't maintain a cross-page element history in this simple implementation,
        # we prioritize elements that look like navigation (nav, header, aside links)
        # and ignore footer links to avoid getting stuck in legal/privacy loops.
        
        candidates = []
        for el in state.elements:
            if not el.visible or not el.enabled:
                continue
                
            text = (el.text or el.aria_label or "").lower()
            
            # Skip obvious dead ends or external links
            if any(k in text for k in ["privacy", "terms", "facebook", "twitter", "instagram"]):
                continue
                
            score = 10
            if el.tag == "a":
                score += 5
            if el.tag == "button":
                score += 3
            if el.role in ["menuitem", "tab"]:
                score += 8
                
            # Prefer elements higher up on the page (usually primary navigation)
            if el.bounding_box.y < 300:
                score += 5
                
            candidates.append((score, el))
            
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        if candidates:
            best_el = candidates[0][1]
            return {
                "id": best_el.id,
                "selector": best_el.selector,
                "text": best_el.text or best_el.aria_label,
                "tag": best_el.tag,
                "role": best_el.role
            }
            
        return None
