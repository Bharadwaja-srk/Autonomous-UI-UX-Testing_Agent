import re
import logging
from pathlib import Path
from typing import List
from PIL import Image, ImageDraw
from backend.schemas import UIElement, NetworkEntry, ConsoleEntry

logger = logging.getLogger("autonomous_tester.pii_redaction")

class PIIRedactionEngine:
    """
    Enterprise-grade PII Redaction Engine.
    Scrubs sensitive data (emails, credit cards, SSNs) from text and visually blocks out
    sensitive fields (e.g. passwords, billing inputs) in screenshots.
    """

    def __init__(self):
        # Regex patterns for common PII
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        # Basic 16-digit CC matching with optional dashes/spaces
        self.cc_pattern = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
        # Basic SSN pattern (US)
        self.ssn_pattern = re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b')

        # Keywords in element name/id/placeholder that indicate sensitive data
        self.sensitive_keywords = ["password", "credit", "card", "ssn", "social security", "billing", "cvv", "secret"]

    def mask_text(self, text: str) -> str:
        """Redact PII from a given string."""
        if not text:
            return text
            
        masked = self.email_pattern.sub("[EMAIL_REDACTED]", text)
        masked = self.cc_pattern.sub("[CREDIT_CARD_REDACTED]", masked)
        masked = self.ssn_pattern.sub("[SSN_REDACTED]", masked)
        return masked

    def is_sensitive_element(self, element: UIElement) -> bool:
        """Determine heuristically if an element is likely to contain sensitive input."""
        if element.tag == "input":
            # Passwords are always sensitive
            if element.role == 'password':
                return True
                
        # Check name, placeholder, aria_label for sensitive keywords
        hints = [element.name, element.placeholder, element.aria_label, element.text]
        for hint in hints:
            if hint and any(keyword in hint.lower() for keyword in self.sensitive_keywords):
                return True
                
        return False

    def mask_screenshot(self, screenshot_path: Path, elements: List[UIElement]) -> bool:
        """
        Draw black rectangles over sensitive elements in the screenshot.
        Returns True if masking was applied.
        """
        if not screenshot_path.exists():
            return False

        sensitive_elements = [el for el in elements if self.is_sensitive_element(el)]
        
        if not sensitive_elements:
            return False

        try:
            with Image.open(screenshot_path) as img:
                draw = ImageDraw.Draw(img)
                for el in sensitive_elements:
                    # bounding_box: x, y, width, height
                    x = el.bounding_box.x
                    y = el.bounding_box.y
                    w = el.bounding_box.width
                    h = el.bounding_box.height
                    
                    if w > 0 and h > 0:
                        # Draw black solid rectangle over the element
                        draw.rectangle([x, y, x + w, y + h], fill="black")
                
                img.save(screenshot_path)
            logger.debug(f"Redacted {len(sensitive_elements)} sensitive areas in screenshot {screenshot_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to mask screenshot {screenshot_path.name}: {e}")
            return False

    def mask_network_entries(self, entries: List[NetworkEntry]) -> List[NetworkEntry]:
        """Redact sensitive URLs and completely wipe request payloads/headers if tracked."""
        for entry in entries:
            entry.url = self.mask_text(entry.url)
            if entry.error_message:
                entry.error_message = self.mask_text(entry.error_message)
        return entries
        
    def mask_console_entries(self, entries: List[ConsoleEntry]) -> List[ConsoleEntry]:
        """Redact PII from console messages."""
        for entry in entries:
            if entry.message:
                entry.message = self.mask_text(entry.message)
        return entries
