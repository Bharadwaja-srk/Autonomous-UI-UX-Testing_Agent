"""
Console & Network Observability Engine for Autonomous UI/UX Testing.
Captures browser console messages, JS exceptions, and network failures
to correlate UI issues with underlying errors.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from playwright.async_api import Page, ConsoleMessage, Response, Request
from backend.schemas import ConsoleEntry, NetworkEntry, ObservabilitySnapshot
from backend.pii_redaction import PIIRedactionEngine

logger = logging.getLogger("autonomous_tester.observability")


class ObservabilityEngine:
    """Monitors browser console, JS exceptions, and network traffic."""

    def __init__(self):
        self._console_entries: List[ConsoleEntry] = []
        self._network_entries: List[NetworkEntry] = []
        self._js_exceptions: List[str] = []
        self._current_step: int = 0
        self._page: Optional[Page] = None

    def set_step(self, step: int):
        """Update the current step number for correlating events."""
        self._current_step = step

    async def attach(self, page: Page):
        """Register event listeners on the Playwright page."""
        self._page = page

        page.on("console", self._on_console)
        page.on("pageerror", self._on_page_error)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

        logger.info("Observability engine attached to browser page.")

    def _on_console(self, msg: ConsoleMessage):
        """Capture console.log/warn/error messages."""
        level = msg.type  # 'log', 'warning', 'error', 'info', 'debug'
        if level in ("error", "warning"):
            entry = ConsoleEntry(
                level=level,
                message=msg.text[:500],
                source=msg.location.get("url", "") if hasattr(msg, "location") and msg.location else None,
                line_number=msg.location.get("lineNumber") if hasattr(msg, "location") and msg.location else None,
                timestamp=datetime.now(timezone.utc).isoformat(),
                step_number=self._current_step,
            )
            self._console_entries.append(entry)
            if level == "error":
                logger.debug(f"Console error at step {self._current_step}: {msg.text[:100]}")

    def _on_page_error(self, error: Exception):
        """Capture uncaught JavaScript exceptions."""
        error_str = str(error)[:500]
        self._js_exceptions.append(error_str)
        self._console_entries.append(ConsoleEntry(
            level="error",
            message=f"Uncaught JS Exception: {error_str}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            step_number=self._current_step,
        ))
        logger.debug(f"JS exception at step {self._current_step}: {error_str[:100]}")

    def _on_request_failed(self, request: Request):
        """Capture failed network requests."""
        failure_text = request.failure
        entry = NetworkEntry(
            method=request.method,
            url=request.url[:300],
            failed=True,
            error_message=str(failure_text)[:200] if failure_text else "Request failed",
            timestamp=datetime.now(timezone.utc).isoformat(),
            step_number=self._current_step,
        )
        self._network_entries.append(entry)
        logger.debug(f"Network failure at step {self._current_step}: {request.method} {request.url[:80]}")

    def _on_response(self, response: Response):
        """Capture non-2xx HTTP responses."""
        status = response.status
        if status >= 400:
            entry = NetworkEntry(
                method=response.request.method,
                url=response.url[:300],
                status_code=status,
                failed=True,
                error_message=f"HTTP {status} response",
                timestamp=datetime.now(timezone.utc).isoformat(),
                step_number=self._current_step,
            )
            self._network_entries.append(entry)
            logger.debug(f"HTTP {status} at step {self._current_step}: {response.url[:80]}")

    def get_snapshot(self, enable_pii: bool = False) -> ObservabilitySnapshot:
        """Get observability data collected since last snapshot call."""
        
        console_entries = list(self._console_entries)
        network_entries = list(self._network_entries)
        js_exceptions = list(self._js_exceptions)
        
        if enable_pii:
            pii_engine = PIIRedactionEngine()
            console_entries = pii_engine.mask_console_entries(console_entries)
            network_entries = pii_engine.mask_network_entries(network_entries)
            js_exceptions = [pii_engine.mask_text(ex) for ex in js_exceptions]

        snapshot = ObservabilitySnapshot(
            console_entries=console_entries,
            network_entries=network_entries,
            js_exceptions=js_exceptions,
        )
        return snapshot

    def get_recent(self, since_step: int, enable_pii: bool = False) -> ObservabilitySnapshot:
        """Get entries from a specific step onwards."""
        console_entries = [e for e in self._console_entries if (e.step_number or 0) >= since_step]
        network_entries = [e for e in self._network_entries if (e.step_number or 0) >= since_step]
        
        if enable_pii:
            pii_engine = PIIRedactionEngine()
            console_entries = pii_engine.mask_console_entries(console_entries)
            network_entries = pii_engine.mask_network_entries(network_entries)
            
        return ObservabilitySnapshot(
            console_entries=console_entries,
            network_entries=network_entries,
            js_exceptions=[],
        )

    def get_error_summary(self, enable_pii: bool = False) -> str:
        """Generate a human-readable summary of observed errors."""
        console_errors = [e for e in self._console_entries if e.level == "error"]
        network_errors = [e for e in self._network_entries if e.failed]
        js_ex = list(self._js_exceptions)
        
        if enable_pii:
            pii_engine = PIIRedactionEngine()
            console_errors = pii_engine.mask_console_entries(console_errors)
            network_errors = pii_engine.mask_network_entries(network_errors)
            js_ex = [pii_engine.mask_text(ex) for ex in js_ex]

        parts = []
        if console_errors:
            parts.append(f"Console Errors ({len(console_errors)}):")
            for e in console_errors[-5:]:
                parts.append(f"  - [{e.level}] {e.message[:100]}")
        if network_errors:
            parts.append(f"Network Failures ({len(network_errors)}):")
            for e in network_errors[-5:]:
                parts.append(f"  - {e.method} {e.url[:60]} → {e.error_message}")
        if js_ex:
            parts.append(f"JS Exceptions ({len(js_ex)}):")
            for ex in js_ex[-3:]:
                parts.append(f"  - {ex[:100]}")

        return "\n".join(parts) if parts else "No console/network errors observed."

    def clear(self):
        """Reset all buffers."""
        self._console_entries.clear()
        self._network_entries.clear()
        self._js_exceptions.clear()
        self._current_step = 0
