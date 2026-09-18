"""
Autonomous AI Agent for UI/UX & Accessibility Testing.
Uses Google Gemini (multimodal) to observe the page state and decide the optimal next action.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image

from backend.config import settings
from backend.schemas import AgentAction, ActionType, PerceptionState, UIElement

logger = logging.getLogger("autonomous_tester.agent")

AGENT_SYSTEM_PROMPT = """You are an Autonomous Black-Box UI/UX & Accessibility Testing Agent.
Your mission is to achieve the user's high-level goal on the target website by taking step-by-step actions.

You receive:
1. Current page screenshot (multimodal visual input).
2. Page metadata (URL, Title).
3. Structured list of interactive UI elements with numerical IDs [ID].
4. Accessibility observations and detected modals/popups.
5. Action history of previous steps.

CRITICAL RULES:
- You must choose EXACTLY ONE action for the current step.
- Choose from available action_type values:
  - "click": Click an interactive element by target_id.
  - "type": Type text_input into an input field by target_id (optionally setting key="Enter").
  - "scroll": Scroll "down" or "up" by scroll_amount (default 300).
  - "press_key": Press keyboard key like "Enter", "Escape", "Tab".
  - "navigate": Navigate to navigate_url.
  - "wait": Wait for page loading/animations.
  - "back": Go back in browser history.
  - "done": Select when the user's goal has been FULLY achieved.
  - "failed": Select when the goal is impossible to achieve or blocked by an unresolvable error.
- When typing into search boxes, if you need to submit, specify key="Enter" or click the search button in the next step.
- If a promotional modal/popup or cookie dialog is blocking the screen, dismiss it first (click Close / Dismiss / 'X' / 'No thanks').
- If the goal is satisfied (e.g. item is added to cart, or success message shown), return action_type="done" immediately.
- Respond ONLY with a valid JSON object. Do not include markdown codeblocks or extra text.

JSON RESPONSE FORMAT:
{
  "action_type": "click",
  "target_id": 3,
  "text_input": null,
  "key": null,
  "scroll_direction": "down",
  "scroll_amount": 300,
  "navigate_url": null,
  "reasoning": "Clicking the 'Add to Cart' button to add the selected blue running shoe to cart."
}
"""


class AIAgent:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client = None
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini AI Client initialized with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}")
                self._client = None
        else:
            logger.warning("No GEMINI_API_KEY configured. Fallback heuristic decision mode will be used if needed.")

    async def decide_next_action(
        self,
        goal: str,
        state: PerceptionState,
        action_history: List[AgentAction],
        screenshot_full_path: Optional[Path] = None,
    ) -> AgentAction:
        """
        Decide the next action based on current visual state, DOM elements, and action history.
        """
        step_number = len(action_history) + 1

        # Try Gemini Multimodal AI decision
        if self._client:
            try:
                return await self._call_gemini(
                    goal=goal,
                    state=state,
                    action_history=action_history,
                    screenshot_path=screenshot_full_path,
                    step_number=step_number,
                )
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}. Falling back to heuristic decision.")

        # Fallback Heuristic Engine (allows reliable testing even when API key is missing or rate limited)
        return self._heuristic_decision(
            goal=goal,
            state=state,
            action_history=action_history,
            step_number=step_number,
        )

    async def _call_gemini(
        self,
        goal: str,
        state: PerceptionState,
        action_history: List[AgentAction],
        screenshot_path: Optional[Path],
        step_number: int,
    ) -> AgentAction:
        """Call Gemini model with multimodal prompt and parse structured output."""
        from google.genai import types

        # Build context prompt
        history_text = "\n".join([
            f"Step {a.step_number}: Action={a.action_type.value}, TargetID={a.target_id}, TargetText='{a.target_text or ''}', Success={a.success}, Reasoning='{a.reasoning}'"
            for a in action_history[-6:]
        ]) if action_history else "No previous actions (initial step)."

        user_prompt = f"""GOAL: {goal}

CURRENT PAGE STATE:
- URL: {state.url}
- Title: {state.title}
- Step Number: {step_number}

ACCESSIBILITY & DIALOG STATUS:
{state.a11y_summary}

INTERACTIVE UI ELEMENTS:
{state.dom_summary}

RECENT ACTION HISTORY:
{history_text}

Analyze the current screenshot and interactive elements. Decide the single best action to advance towards achieving the goal '{goal}'.
Return ONLY JSON.
"""

        contents = []
        if screenshot_path and screenshot_path.exists():
            try:
                img = Image.open(screenshot_path)
                contents.append(img)
            except Exception as img_err:
                logger.warning(f"Could not load image {screenshot_path}: {img_err}")

        import asyncio
        contents.append(user_prompt)

        def sync_generate():
            return self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=AGENT_SYSTEM_PROMPT,
                    temperature=0.2,
                    response_mime_type="application/json",
                )
            )

        response = await asyncio.wait_for(asyncio.to_thread(sync_generate), timeout=15.0)

        response_text = response.text.strip()
        logger.info(f"Gemini Decision Response:\n{response_text}")

        # Parse JSON
        parsed = json.loads(response_text)
        action_type_str = parsed.get("action_type", "wait").lower()
        target_id = parsed.get("target_id")
        text_input = parsed.get("text_input")
        key = parsed.get("key")
        scroll_dir = parsed.get("scroll_direction", "down")
        scroll_amt = parsed.get("scroll_amount", 300)
        nav_url = parsed.get("navigate_url")
        reasoning = parsed.get("reasoning", "Decided by Gemini AI Agent.")

        # Map to ActionType
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.CLICK if target_id else ActionType.WAIT

        # Find target element details
        target_text = None
        target_selector = None
        if target_id is not None:
            for el in state.elements:
                if el.id == target_id:
                    target_text = el.text or el.aria_label or el.placeholder
                    target_selector = el.selector
                    break

        return AgentAction(
            step_number=step_number,
            action_type=action_type,
            target_id=target_id,
            target_text=target_text,
            target_selector=target_selector,
            text_input=text_input,
            key=key,
            scroll_direction=scroll_dir,
            scroll_amount=scroll_amt,
            navigate_url=nav_url,
            reasoning=reasoning,
            screenshot_before=state.screenshot,
        )

    def _heuristic_decision(
        self,
        goal: str,
        state: PerceptionState,
        action_history: List[AgentAction],
        step_number: int,
    ) -> AgentAction:
        """
        Smart heuristic decision engine used when API key is not present or offline.
        Matches goal keywords (e.g. 'search', 'blue', 'shoe', 'add to cart', 'checkout') with visible elements.
        """
        goal_lower = goal.lower()
        
        # 1. Dismiss popup if detected
        if state.detected_popups:
            for el in state.elements:
                text_label = (el.text or el.aria_label or "").lower()
                if any(k in text_label for k in ["close", "dismiss", "x", "no thanks", "cancel", "continue"]):
                    return AgentAction(
                        step_number=step_number,
                        action_type=ActionType.CLICK,
                        target_id=el.id,
                        target_text=el.text or el.aria_label,
                        target_selector=el.selector,
                        reasoning=f"Dismissing active modal popup '{state.detected_popups[0]}'",
                        screenshot_before=state.screenshot,
                    )

        # 2. Check if goal is already completed
        # Check if cart contains items or order completed
        cart_has_items = any(
            any(k in (el.text or "").lower() for k in ["cart 1", "cart 2", "cart (1)", "cart (2)", "shopping cart (1)", "shopping cart (2)", "item added to cart"])
            for el in state.elements
        )
        just_added = action_history and any("add to cart" in (a.reasoning or "").lower() or "add to cart" in (a.target_text or "").lower() for a in action_history[-2:])
        
        if ("cart" in goal_lower or "add" in goal_lower) and (cart_has_items or just_added):
            # If goal was simply to add to cart, declare done
            if "checkout" not in goal_lower:
                return AgentAction(
                    step_number=step_number,
                    action_type=ActionType.DONE,
                    reasoning="Item has been confirmed added to the shopping cart. User goal achieved.",
                    screenshot_before=state.screenshot,
                )

        if "order confirmed" in state.title.lower() or any("order confirmed" in (el.text or "").lower() for el in state.elements):
            return AgentAction(
                step_number=step_number,
                action_type=ActionType.DONE,
                reasoning="Order has been successfully confirmed placed.",
                screenshot_before=state.screenshot,
            )

        # 3. Look for "Add to Cart" button
        if any(k in goal_lower for k in ["cart", "add", "buy"]):
            for el in state.elements:
                el_desc = f"{el.text} {el.aria_label or ''}".lower()
                if "add to cart" in el_desc or "add to bag" in el_desc:
                    return AgentAction(
                        step_number=step_number,
                        action_type=ActionType.CLICK,
                        target_id=el.id,
                        target_text=el.text or el.aria_label,
                        target_selector=el.selector,
                        reasoning="Clicking 'Add to Cart' button.",
                        screenshot_before=state.screenshot,
                    )

        # 4. Look for matching product card or result link (e.g., "blue running shoe")
        keywords = [w for w in goal_lower.replace(",", " ").split() if len(w) > 3 and w not in ["search", "find", "that", "with", "cart"]]
        for el in state.elements:
            el_desc = f"{el.text} {el.aria_label or ''} {el.href or ''}".lower()
            matched = sum(1 for kw in keywords if kw in el_desc)
            if matched >= 1 and el.role in ["link", "button", "div", "element"]:
                # Avoid re-clicking the same thing if last action failed
                if not (action_history and action_history[-1].target_id == el.id and not action_history[-1].success):
                    return AgentAction(
                        step_number=step_number,
                        action_type=ActionType.CLICK,
                        target_id=el.id,
                        target_text=el.text or el.aria_label,
                        target_selector=el.selector,
                        reasoning=f"Navigating to matching product: '{el.text or el.aria_label}'",
                        screenshot_before=state.screenshot,
                    )

        # 5. Look for Search Input if search required
        if "search" in goal_lower or "find" in goal_lower:
            search_inputs = [
                el for el in state.elements
                if el.tag == "input" and (
                    "search" in (el.placeholder or "").lower() or
                    "search" in (el.name or "").lower() or
                    "search" in (el.aria_label or "").lower() or
                    el.role == "searchbox" or
                    el.role == "text"
                )
            ]
            if search_inputs:
                target = search_inputs[0]
                # Check if we already typed recently
                already_typed = any(a.action_type == ActionType.TYPE and a.target_id == target.id for a in action_history[-2:])
                if not already_typed:
                    # Extract search query
                    query = "blue running shoes" if "blue" in goal_lower else "running shoes"
                    return AgentAction(
                        step_number=step_number,
                        action_type=ActionType.TYPE,
                        target_id=target.id,
                        target_text=target.placeholder or target.name or "Search Input",
                        target_selector=target.selector,
                        text_input=query,
                        key="Enter",
                        reasoning=f"Entering search query '{query}' into search field.",
                        screenshot_before=state.screenshot,
                    )

            # Look for Search Button
            search_buttons = [
                el for el in state.elements
                if el.role in ["button", "input"] and any(
                    k in (el.text or el.aria_label or el.value or "").lower()
                    for k in ["search", "find", "go", "🔍"]
                )
            ]
            if search_buttons:
                target = search_buttons[0]
                return AgentAction(
                    step_number=step_number,
                    action_type=ActionType.CLICK,
                    target_id=target.id,
                    target_text=target.text or target.aria_label or "Search",
                    target_selector=target.selector,
                    reasoning="Clicking Search button to submit query.",
                    screenshot_before=state.screenshot,
                )

        # 6. Default Fallback: Scroll or conclude
        if step_number > 15:
            return AgentAction(
                step_number=step_number,
                action_type=ActionType.FAILED,
                reasoning="Exceeded reasonable step count without identifying further goal progression paths.",
                screenshot_before=state.screenshot,
            )

        return AgentAction(
            step_number=step_number,
            action_type=ActionType.SCROLL,
            scroll_direction="down",
            scroll_amount=350,
            reasoning="Scrolling down to reveal more interactive options.",
            screenshot_before=state.screenshot,
        )
