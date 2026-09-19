"""
Perception Engine for Autonomous UI/UX & Accessibility Testing.
Extracts DOM state, interactive elements, bounding boxes, accessibility flaws,
and computes deterministic state hashes without modifying the target application.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from backend.driver import BrowserDriver
from backend.schemas import UIElement, PerceptionState, BoundingBox
from backend.pii_redaction import PIIRedactionEngine

logger = logging.getLogger("autonomous_tester.perception")

# Browser-side JavaScript to extract interactive elements and a11y info
DOM_EXTRACTION_SCRIPT = r"""
() => {
    const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        // Check if inside document
        return (
            rect.top < window.innerHeight + 100 &&
            rect.bottom > -100 &&
            rect.left < window.innerWidth + 100 &&
            rect.right > -100
        );
    };

    const getAccessibleName = (el) => {
        if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
        if (el.getAttribute('aria-labelledby')) {
            const labelEl = document.getElementById(el.getAttribute('aria-labelledby'));
            if (labelEl) return labelEl.innerText.trim();
        }
        if (el.getAttribute('alt')) return el.getAttribute('alt').trim();
        if (el.getAttribute('placeholder')) return el.getAttribute('placeholder').trim();
        if (el.getAttribute('title')) return el.getAttribute('title').trim();
        if (el.labels && el.labels.length > 0) return el.labels[0].innerText.trim();
        
        // For inputs, check preceding or parent label
        if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
            const parentLabel = el.closest('label');
            if (parentLabel) return parentLabel.innerText.trim();
        }
        return '';
    };

    const generateSelector = (el) => {
        if (el.id) return `#${CSS.escape(el.id)}`;
        
        // Use testid or specific unique attributes if available
        if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
        if (el.getAttribute('name')) return `${el.tagName.toLowerCase()}[name="${el.getAttribute('name')}"]`;
        
        // Generate path
        const path = [];
        let current = el;
        while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body && current !== document.documentElement) {
            let selector = current.tagName.toLowerCase();
            if (current.className && typeof current.className === 'string') {
                const classes = current.className.trim().split(/\\s+/).filter(c => c && !c.includes(':') && !c.startsWith('js-') && !c.includes('{'));
                if (classes.length > 0) {
                    selector += '.' + CSS.escape(classes[0]);
                }
            }
            // Add nth-of-type if siblings exist
            let siblingIndex = 1;
            let sibling = current.previousElementSibling;
            while (sibling) {
                if (sibling.tagName === current.tagName) siblingIndex++;
                sibling = sibling.previousElementSibling;
            }
            selector += `:nth-of-type(${siblingIndex})`;
            path.unshift(selector);
            current = current.parentElement;
            if (path.length >= 4) break;
        }
        return path.join(' > ');
    };

    const interactiveQuery = 'button, a[href], input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="tab"], [role="menuitem"], [role="dialog"], [tabindex]:not([tabindex="-1"]), [onclick]';
    const rawElements = Array.from(document.querySelectorAll(interactiveQuery));
    
    // Also include elements styled as buttons or clickables
    const allElements = Array.from(document.querySelectorAll('div, span, p, i, svg, li, section')).filter(el => {
        if (!isVisible(el)) return false;
        const style = window.getComputedStyle(el);
        return style.cursor === 'pointer' && !rawElements.includes(el);
    });

    const candidates = [...rawElements, ...allElements];
    const elements = [];
    const detectedPopups = [];
    let idCounter = 1;

    // Check for open dialogs / modals
    const dialogs = document.querySelectorAll('[role="dialog"], dialog[open], .modal.show, .modal.active, .popup.active, .popup.open, .overlay:not(.hidden)');
    dialogs.forEach(d => {
        if (isVisible(d)) {
            const titleEl = d.querySelector('h1, h2, h3, h4, .modal-title, .popup-title');
            detectedPopups.push(titleEl ? titleEl.innerText.trim() : 'Modal / Dialog Banner');
        }
    });

    const seenRects = new Set();

    candidates.forEach(el => {
        if (!isVisible(el)) return;
        
        const rect = el.getBoundingClientRect();
        // Avoid duplicate overlapping captures for identical containers
        const rectKey = `${Math.round(rect.left)},${Math.round(rect.top)},${Math.round(rect.width)},${Math.round(rect.height)}`;
        if (seenRects.has(rectKey) && el.tagName === 'DIV') return;
        seenRects.add(rectKey);

        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'button' ? 'button' : tag === 'input' ? el.type || 'input' : tag);
        const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 100);
        const ariaLabel = getAccessibleName(el);
        const placeholder = el.getAttribute('placeholder') || '';
        const value = el.value || '';
        const name = el.getAttribute('name') || '';
        const href = el.getAttribute('href') || '';
        const enabled = !el.disabled && el.getAttribute('aria-disabled') !== 'true';
        const focusable = el.tabIndex !== -1;
        const selector = generateSelector(el);

        // A11y checks
        const a11yIssues = [];
        const isIconOnly = text && /^[\p{Emoji}\p{Symbol}\p{Punctuation}\s]+$/u.test(text);
        
        if (role === 'button' || tag === 'button') {
            if (!text && !ariaLabel) {
                a11yIssues.push('Unlabeled button: Button has no visible text or aria-label');
            } else if (isIconOnly && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby')) {
                a11yIssues.push(`Icon-only button without accessible label: Button uses symbol/emoji "${text}" without descriptive aria-label`);
            }
        }
        if (role === 'link' || tag === 'a') {
            if (!text && !ariaLabel) {
                a11yIssues.push('Unlabeled link: Link has no visible text or aria-label');
            } else if (isIconOnly && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby')) {
                a11yIssues.push(`Icon-only link without accessible label: Link uses symbol "${text}" without descriptive aria-label`);
            }
        }
        if (tag === 'input' && !['submit', 'button', 'hidden', 'reset'].includes(el.type)) {
            if (!ariaLabel && !placeholder) {
                a11yIssues.push('Unlabeled form input: Input field lacks accessible label or placeholder');
            }
        }
        if (el.getAttribute('aria-hidden') === 'true' && focusable) {
            a11yIssues.push('Focusable element marked aria-hidden="true"');
        }

        elements.push({
            id: idCounter++,
            role: role,
            tag: tag,
            text: text,
            aria_label: ariaLabel || null,
            placeholder: placeholder || null,
            value: value || null,
            name: name || null,
            bounding_box: {
                x: Math.round(rect.left),
                y: Math.round(rect.top),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            },
            visible: true,
            enabled: enabled,
            focusable: focusable,
            href: href || null,
            selector: selector,
            a11y_issues: a11yIssues
        });
    });

    return {
        url: window.location.href,
        title: document.title,
        detected_popups: detectedPopups,
        elements: elements.slice(0, 60) // Limit to top 60 relevant visible elements
    };
}
"""


class PerceptionEngine:
    def __init__(self, driver: BrowserDriver):
        self.driver = driver

    async def capture_state(self, step_number: int, screenshot_path: Path, enable_pii: bool = False) -> PerceptionState:
        """
        Capture the complete multimodal perception state:
        Screenshot, interactive elements, page metadata, a11y summary, and state hash.
        """
        # 1. Take Screenshot
        await self.driver.take_screenshot(screenshot_path)

        # 2. Extract DOM & Accessibility data
        raw_data = await self.driver.evaluate(DOM_EXTRACTION_SCRIPT)
        if not raw_data:
            url = self.driver.page.url if self.driver.page else ""
            title = await self.driver.page.title() if self.driver.page else ""
            raw_data = {"url": url, "title": title, "elements": [], "detected_popups": []}

        # 3. Build UIElement objects
        ui_elements: List[UIElement] = []
        all_a11y_issues: List[str] = []

        for item in raw_data.get("elements", []):
            bbox = BoundingBox(
                x=item.get("bounding_box", {}).get("x", 0),
                y=item.get("bounding_box", {}).get("y", 0),
                width=item.get("bounding_box", {}).get("width", 0),
                height=item.get("bounding_box", {}).get("height", 0),
            )
            element = UIElement(
                id=item.get("id"),
                role=item.get("role", "element"),
                tag=item.get("tag", "div"),
                text=item.get("text", ""),
                aria_label=item.get("aria_label"),
                placeholder=item.get("placeholder"),
                value=item.get("value"),
                name=item.get("name"),
                bounding_box=bbox,
                visible=item.get("visible", True),
                enabled=item.get("enabled", True),
                focusable=item.get("focusable", True),
                href=item.get("href"),
                selector=item.get("selector"),
                a11y_issues=item.get("a11y_issues", []),
            )
            ui_elements.append(element)
            for issue in element.a11y_issues:
                all_a11y_issues.append(f"Element [{element.id}] <{element.tag}>: {issue}")

        # 4. Generate State Hash for Navigation/Loop Detection
        state_hash = self._compute_state_hash(
            url=raw_data.get("url", ""),
            title=raw_data.get("title", ""),
            elements=ui_elements,
            popups=raw_data.get("detected_popups", [])
        )

        # 5. Build Human/LLM Readable DOM and A11y summaries
        dom_summary = self._build_dom_summary(ui_elements)
        a11y_summary = self._build_a11y_summary(all_a11y_issues, raw_data.get("detected_popups", []))

        # Optional PII Redaction
        if enable_pii:
            pii_engine = PIIRedactionEngine()
            
            # Mask text attributes in ui_elements
            for el in ui_elements:
                el.text = pii_engine.mask_text(el.text)
                el.placeholder = pii_engine.mask_text(el.placeholder)
                el.value = pii_engine.mask_text(el.value)
                
            # Rebuild summaries with masked elements
            dom_summary = self._build_dom_summary(ui_elements)
            
            # Mask page titles and popup names
            raw_data["title"] = pii_engine.mask_text(raw_data.get("title", ""))
            raw_data["detected_popups"] = [pii_engine.mask_text(p) for p in raw_data.get("detected_popups", [])]
            a11y_summary = self._build_a11y_summary(all_a11y_issues, raw_data.get("detected_popups", []))
            
            # Visually redact screenshot
            pii_engine.mask_screenshot(screenshot_path, ui_elements)

        return PerceptionState(
            step_number=step_number,
            url=raw_data.get("url", ""),
            title=raw_data.get("title", ""),
            screenshot=str(screenshot_path.name) if screenshot_path else None,
            elements=ui_elements,
            a11y_summary=a11y_summary,
            dom_summary=dom_summary,
            state_hash=state_hash,
            detected_popups=raw_data.get("detected_popups", []),
        )

    def _compute_state_hash(self, url: str, title: str, elements: List[UIElement], popups: List[str]) -> str:
        """
        Deterministic hash representation of current visual & navigational state.
        Normalizes URL queries and captures structural element signatures.
        """
        # Normalize URL (remove volatile query tokens or hashes if standard page)
        base_url = url.split("#")[0]
        
        # Take key element signatures (id, role, text snippets)
        elem_signatures = [
            f"{e.role}:{e.text[:20]}:{e.placeholder or ''}"
            for e in elements[:30]
        ]
        
        raw_repr = f"URL:{base_url}|TITLE:{title}|POPUPS:{','.join(popups)}|ELEMS:{','.join(elem_signatures)}"
        return hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()[:16]

    def _build_dom_summary(self, elements: List[UIElement]) -> str:
        """Create structured representation of interactive elements for the AI agent."""
        lines = []
        for el in elements:
            details = []
            if el.text:
                details.append(f'text="{el.text}"')
            if el.aria_label:
                details.append(f'aria-label="{el.aria_label}"')
            if el.placeholder:
                details.append(f'placeholder="{el.placeholder}"')
            if el.value:
                details.append(f'value="{el.value}"')
            if el.href:
                details.append(f'href="{el.href}"')
            if not el.enabled:
                details.append('[DISABLED]')
                
            desc = " ".join(details)
            lines.append(f"[{el.id}] <{el.tag} role=\"{el.role}\"> {desc}")
        return "\n".join(lines) if lines else "No interactive elements detected."

    def _build_a11y_summary(self, issues: List[str], popups: List[str]) -> str:
        """Create summary of accessibility and popup observations."""
        parts = []
        if popups:
            parts.append(f"Active Dialogs/Popups: {', '.join(popups)}")
        if issues:
            parts.append("Potential Accessibility Issues Detected:")
            for issue in issues[:10]:
                parts.append(f"- {issue}")
        else:
            parts.append("No immediate accessibility blockers detected on interactive controls.")
        return "\n".join(parts)
