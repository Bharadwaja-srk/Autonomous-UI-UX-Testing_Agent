"""
Multi-Device & Responsive Analysis Engine.
Provides standard device profiles and detects responsive UI issues like
overlapping elements, horizontal scrolling, and touch target sizes.
"""

import logging
from typing import Dict, List

from backend.schemas import DeviceProfile, PerceptionState, Finding, FindingCategory, FindingSeverity

logger = logging.getLogger("autonomous_tester.devices")

# Standard presets mapping common devices
DEVICE_PRESETS: Dict[str, DeviceProfile] = {
    "desktop": DeviceProfile(
        name="desktop",
        viewport_width=1280,
        viewport_height=800,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False
    ),
    "tablet": DeviceProfile(
        name="tablet",
        viewport_width=768,
        viewport_height=1024,
        user_agent="Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    ),
    "mobile": DeviceProfile(
        name="mobile",
        viewport_width=375,
        viewport_height=812,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True
    ),
    "mobile_landscape": DeviceProfile(
        name="mobile_landscape",
        viewport_width=812,
        viewport_height=375,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True
    )
}

def get_device_profile(name: str) -> DeviceProfile:
    """Get a device profile by name, defaulting to desktop."""
    return DEVICE_PRESETS.get(name.lower(), DEVICE_PRESETS["desktop"])


class ResponsiveAnalyzer:
    """Analyzes DOM state for responsive design issues."""

    def detect_responsive_issues(self, state: PerceptionState, device: DeviceProfile) -> List[Finding]:
        """
        Analyze the current state for responsive issues based on the device profile.
        """
        findings: List[Finding] = []
        
        if not state.elements:
            return findings

        viewport_width = device.viewport_width
        is_touch = device.has_touch

        # 1. Detect horizontal overflow
        max_element_width = 0
        overflowing_elements = []
        
        for el in state.elements:
            if not el.visible:
                continue
                
            right_edge = el.bounding_box.x + el.bounding_box.width
            if right_edge > max_element_width:
                max_element_width = right_edge
                
            if right_edge > viewport_width + 10:  # Allow 10px margin of error
                if el.bounding_box.width > viewport_width:
                    overflowing_elements.append(el)

        if max_element_width > viewport_width + 20:
            findings.append(Finding(
                finding_id=f"RESP-OVERFLOW-{state.step_number}",
                category=FindingCategory.RESPONSIVE,
                severity=FindingSeverity.HIGH,
                title="Horizontal scroll detected",
                description=f"Page content extends to {max_element_width}px, exceeding the viewport width of {viewport_width}px.",
                step_number=state.step_number,
                evidence=f"{len(overflowing_elements)} elements overflow the viewport bounds.",
                recommendation="Ensure all container widths use responsive units (%, vw) or max-width: 100%. Check for unbroken text strings or absolute positioned elements."
            ))

        # 2. Touch target sizing (if on a touch device)
        if is_touch:
            small_targets = []
            for el in state.elements:
                if not el.visible or not el.enabled:
                    continue
                    
                # Only check interactive elements
                if el.tag in ["button", "a", "input", "select"] or el.role in ["button", "link", "menuitem"]:
                    w, h = el.bounding_box.width, el.bounding_box.height
                    # WCAG 2.5.5 Target Size requires 44x44 CSS pixels
                    if (w > 0 and w < 44) or (h > 0 and h < 44):
                        small_targets.append(el)

            if small_targets:
                samples = [f"<{e.tag}> '{e.text or e.aria_label}' ({e.bounding_box.width}x{e.bounding_box.height}px)" for e in small_targets[:3]]
                findings.append(Finding(
                    finding_id=f"RESP-TOUCH-{state.step_number}",
                    category=FindingCategory.RESPONSIVE,
                    severity=FindingSeverity.MEDIUM,
                    title="Touch targets too small",
                    description=f"Detected {len(small_targets)} interactive elements smaller than the recommended 44x44px touch target size.",
                    step_number=state.step_number,
                    evidence="\n".join(samples),
                    recommendation="Increase padding on interactive elements to ensure they are at least 44x44px for easy tapping on mobile devices."
                ))

        # 3. Element overlapping (basic heuristic)
        # Check if interactive elements significantly overlap with other interactive elements
        interactive_elements = [e for e in state.elements if e.visible and e.enabled and 
                              (e.tag in ["button", "a", "input"] or e.role in ["button", "link"])]
                              
        # O(N^2) comparison, but list is usually small
        overlaps_found = 0
        for i in range(len(interactive_elements)):
            for j in range(i + 1, len(interactive_elements)):
                el1 = interactive_elements[i]
                el2 = interactive_elements[j]
                
                # If one is a parent of another in DOM, bounding boxes will overlap - ignore
                if el1.id == el2.id:
                    continue
                    
                b1, b2 = el1.bounding_box, el2.bounding_box
                
                # Check intersection
                x_overlap = max(0, min(b1.x + b1.width, b2.x + b2.width) - max(b1.x, b2.x))
                y_overlap = max(0, min(b1.y + b1.height, b2.y + b2.height) - max(b1.y, b2.y))
                
                if x_overlap > 0 and y_overlap > 0:
                    overlap_area = x_overlap * y_overlap
                    area1 = b1.width * b1.height
                    area2 = b2.width * b2.height
                    
                    # If overlap is more than 30% of the smaller element
                    if area1 > 0 and area2 > 0:
                        min_area = min(area1, area2)
                        if overlap_area > min_area * 0.3:
                            overlaps_found += 1
                            
        if overlaps_found > 2:  # Threshold to avoid false positives with complex nested UI
            findings.append(Finding(
                finding_id=f"RESP-OVERLAP-{state.step_number}",
                category=FindingCategory.RESPONSIVE,
                severity=FindingSeverity.MEDIUM,
                title="Overlapping interactive elements",
                description=f"Detected {overlaps_found} instances where interactive elements overlap each other significantly.",
                step_number=state.step_number,
                recommendation="Check z-index stacking context and CSS grid/flex layouts to ensure elements don't collapse on top of each other on smaller viewports."
            ))

        return findings
