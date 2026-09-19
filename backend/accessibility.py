"""
Deep Accessibility Testing Engine for Autonomous UI/UX Testing.
Integrates axe-core runtime injection for WCAG-level accessibility auditing,
layered on top of the existing perception-based a11y detection.
"""

import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import Page

from backend.schemas import Finding, FindingCategory, FindingSeverity

logger = logging.getLogger("autonomous_tester.accessibility")

AXE_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"

AXE_INJECT_AND_RUN = """
async () => {
    // Inject axe-core if not already loaded
    if (typeof axe === 'undefined') {
        await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = '""" + AXE_CDN_URL + """';
            script.onload = resolve;
            script.onerror = () => reject(new Error('Failed to load axe-core'));
            document.head.appendChild(script);
        });
    }

    // Run axe analysis
    const results = await axe.run(document, {
        runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
        resultTypes: ['violations', 'incomplete'],
    });

    return {
        violations: results.violations.map(v => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            help: v.help,
            helpUrl: v.helpUrl,
            tags: v.tags,
            nodes: v.nodes.slice(0, 5).map(n => ({
                html: n.html.substring(0, 200),
                target: n.target,
                failureSummary: n.failureSummary || '',
            }))
        })),
        incomplete: results.incomplete.map(v => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            help: v.help,
            nodes: v.nodes.slice(0, 3).map(n => ({
                html: n.html.substring(0, 200),
                target: n.target,
            }))
        })),
        passes: results.passes.length,
        violations_count: results.violations.length,
        incomplete_count: results.incomplete.length,
    };
}
"""

# Mapping from axe-core impact levels to our severity
IMPACT_TO_SEVERITY = {
    "critical": FindingSeverity.CRITICAL,
    "serious": FindingSeverity.HIGH,
    "moderate": FindingSeverity.MEDIUM,
    "minor": FindingSeverity.LOW,
}


class AccessibilityEngine:
    """Deep accessibility testing using axe-core and Playwright accessibility tree."""

    def __init__(self):
        self._axe_loaded = False

    async def run_axe_audit(self, page: Page, step_number: int = 0) -> List[Finding]:
        """
        Inject axe-core and run a full WCAG accessibility audit.
        Returns list of Finding objects for each violation.
        """
        findings: List[Finding] = []

        try:
            raw_results = await page.evaluate(AXE_INJECT_AND_RUN)
            self._axe_loaded = True
        except Exception as e:
            logger.warning(f"axe-core audit failed (CDN may be unreachable): {e}")
            # Return empty — perception-level a11y checks are still active
            return findings

        violations = raw_results.get("violations", [])
        logger.info(
            f"axe-core audit: {raw_results.get('violations_count', 0)} violations, "
            f"{raw_results.get('incomplete_count', 0)} incomplete, "
            f"{raw_results.get('passes', 0)} passes"
        )

        for i, violation in enumerate(violations):
            severity = IMPACT_TO_SEVERITY.get(violation.get("impact", "minor"), FindingSeverity.LOW)
            rule_id = violation.get("id", "unknown")
            nodes = violation.get("nodes", [])

            affected_elements = []
            for node in nodes[:3]:
                target = node.get("target", [])
                html_snippet = node.get("html", "")
                affected_elements.append(f"  Element: {target} → {html_snippet[:80]}")

            evidence = "\n".join(affected_elements) if affected_elements else None

            finding = Finding(
                finding_id=f"AXE-{rule_id}-{i+1}",
                category=FindingCategory.ACCESSIBILITY,
                severity=severity,
                title=violation.get("help", "Accessibility violation"),
                description=violation.get("description", ""),
                step_number=step_number,
                evidence=evidence,
                recommendation=f"WCAG Rule: {rule_id}. See: {violation.get('helpUrl', 'https://dequeuniversity.com/rules/axe/')}",
            )
            findings.append(finding)

        return findings

    async def capture_accessibility_tree(self, page: Page) -> Dict[str, Any]:
        """Capture the Playwright accessibility tree snapshot."""
        try:
            snapshot = await page.accessibility.snapshot()
            return snapshot or {}
        except Exception as e:
            logger.warning(f"Accessibility tree capture failed: {e}")
            return {}

    async def check_keyboard_navigation(self, page: Page, elements_count: int = 10) -> List[Finding]:
        """
        Test keyboard Tab navigation to detect focus order issues and keyboard traps.
        """
        findings: List[Finding] = []

        try:
            # Focus the body first
            await page.keyboard.press("Tab")

            focused_elements = []
            for i in range(min(elements_count, 20)):
                focused = await page.evaluate("""
                    () => {
                        const el = document.activeElement;
                        if (!el || el === document.body) return null;
                        return {
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.value || el.getAttribute('aria-label') || '').substring(0, 50),
                            visible: el.getBoundingClientRect().height > 0,
                            hasFocusStyle: window.getComputedStyle(el, ':focus').outlineStyle !== 'none' ||
                                           window.getComputedStyle(el).outlineStyle !== 'none',
                        };
                    }
                """)

                if focused:
                    focused_elements.append(focused)
                    if not focused.get("visible", True):
                        findings.append(Finding(
                            finding_id=f"A11Y-KB-HIDDEN-{i}",
                            category=FindingCategory.ACCESSIBILITY,
                            severity=FindingSeverity.MEDIUM,
                            title="Focus on hidden element during keyboard navigation",
                            description=f"Tab navigation focused on a non-visible element: <{focused['tag']}> '{focused['text']}'",
                            recommendation="Ensure only visible, interactive elements receive keyboard focus.",
                        ))

                await page.keyboard.press("Tab")

            # Check if we got stuck (keyboard trap)
            if len(focused_elements) >= 2:
                last_two = focused_elements[-2:]
                if last_two[0] == last_two[1]:
                    findings.append(Finding(
                        finding_id="A11Y-KB-TRAP",
                        category=FindingCategory.ACCESSIBILITY,
                        severity=FindingSeverity.HIGH,
                        title="Potential keyboard trap detected",
                        description="Tab key navigation appears stuck on the same element, preventing users from moving forward.",
                        recommendation="Ensure all interactive elements allow Tab key traversal without trapping focus.",
                    ))

        except Exception as e:
            logger.warning(f"Keyboard navigation check failed: {e}")

        return findings

    def merge_findings(self, axe_findings: List[Finding], perception_findings: List[Finding]) -> List[Finding]:
        """Merge axe-core findings with perception-based a11y findings, deduplicating by rule."""
        seen_ids = set()
        merged = []

        for f in axe_findings:
            if f.finding_id not in seen_ids:
                seen_ids.add(f.finding_id)
                merged.append(f)

        for f in perception_findings:
            if f.finding_id not in seen_ids:
                seen_ids.add(f.finding_id)
                merged.append(f)

        return merged
