"""
Session Recording & Replay Engine for Autonomous UI/UX Testing.
Records every agent decision, action, and state transition for exact reproducibility.
"""

import logging
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from backend.schemas import (
    SessionRecording, SessionEvent, SessionEventType,
    DeviceProfile, RecoveryAction
)
from backend.config import settings

logger = logging.getLogger("autonomous_tester.session")


class SessionRecorder:
    """Records the entire autonomous execution session."""

    def __init__(self, sessions_dir: Path = settings.SESSIONS_DIR):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.run_id: str = ""
        self.device_profile: DeviceProfile = DeviceProfile()
        self.events: List[SessionEvent] = []
        self.start_time: float = 0.0

    def start(self, run_id: str, device_profile: DeviceProfile):
        """Initialize recording for a new run."""
        self.run_id = run_id
        self.device_profile = device_profile
        self.events = []
        self.start_time = datetime.now(timezone.utc).timestamp()
        logger.info(f"Session recording started for run {run_id}")

    def record_event(
        self,
        event_type: SessionEventType,
        step_number: int = 0,
        action_summary: str = "",
        reasoning: str = "",
        screenshot_ref: Optional[str] = None,
        state_url: Optional[str] = None,
        recovery: Optional[RecoveryAction] = None,
        console_errors: List[str] = None,
        network_errors: List[str] = None,
        bug_ids: List[str] = None,
    ):
        """Append an event to the session timeline."""
        now = datetime.now(timezone.utc).timestamp()
        elapsed_ms = int((now - self.start_time) * 1000)

        event = SessionEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            elapsed_ms=elapsed_ms,
            step_number=step_number,
            action_summary=action_summary,
            reasoning=reasoning,
            screenshot_ref=screenshot_ref,
            state_url=state_url,
            recovery=recovery,
            console_errors=console_errors or [],
            network_errors=network_errors or [],
            bug_ids=bug_ids or [],
        )
        self.events.append(event)
        
        # Log critical events for debugging
        if event_type in [SessionEventType.ACTION_FAILURE, SessionEventType.BUG_DETECTED, SessionEventType.RECOVERY_ATTEMPT]:
            logger.debug(f"Session Event [{event_type.value}]: {action_summary}")

    def finish(self) -> SessionRecording:
        """Finalize the recording and save to disk."""
        now = datetime.now(timezone.utc).timestamp()
        total_duration_ms = int((now - self.start_time) * 1000)

        recording = SessionRecording(
            run_id=self.run_id,
            events=self.events,
            total_duration_ms=total_duration_ms,
            device_profile=self.device_profile,
            start_time=datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        )

        output_path = self.sessions_dir / f"{self.run_id}.json"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(recording.model_dump(), f, default=str, indent=2)
            logger.info(f"Session recording saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save session recording: {e}")

        return recording

    @classmethod
    def load(cls, run_id: str, sessions_dir: Path = settings.SESSIONS_DIR) -> Optional[SessionRecording]:
        """Load a previous session recording from disk."""
        file_path = sessions_dir / f"{run_id}.json"
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionRecording(**data)
        except Exception as e:
            logger.error(f"Failed to load session recording {run_id}: {e}")
            return None
