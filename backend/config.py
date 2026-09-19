"""
Configuration management for the Autonomous UI/UX & Accessibility Testing Framework.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
    MAX_STEPS: int = int(os.getenv("MAX_STEPS", "30"))
    LOOP_THRESHOLD: int = int(os.getenv("LOOP_THRESHOLD", "3"))
    ACTION_DELAY_MS: int = int(os.getenv("ACTION_DELAY_MS", "600"))
    
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # GitHub Integration (optional)
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")  # format: "owner/repo"

    # Visual Regression
    ENABLE_VISUAL_REGRESSION: bool = os.getenv("ENABLE_VISUAL_REGRESSION", "false").lower() in ("true", "1", "yes")
    VISUAL_DIFF_THRESHOLD: float = float(os.getenv("VISUAL_DIFF_THRESHOLD", "0.5"))

    # Safety & Limits
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    MAX_EXECUTION_TIME_S: int = int(os.getenv("MAX_EXECUTION_TIME_S", "300"))
    MAX_NAVIGATION_DEPTH: int = int(os.getenv("MAX_NAVIGATION_DEPTH", "10"))
    CONFIRM_DESTRUCTIVE_ACTIONS: bool = os.getenv("CONFIRM_DESTRUCTIVE_ACTIONS", "true").lower() in ("true", "1", "yes")

    # Default Device
    DEFAULT_DEVICE: str = os.getenv("DEFAULT_DEVICE", "desktop")
    
    # Directories
    RUNS_DIR: Path = BASE_DIR / "runs"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    SCREENSHOTS_DIR: Path = BASE_DIR / "screenshots"
    BASELINES_DIR: Path = BASE_DIR / "baselines"
    SESSIONS_DIR: Path = BASE_DIR / "sessions"
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    DEMO_APP_DIR: Path = BASE_DIR / "demo_app"


settings = Settings()

# Ensure required directories exist
for path in [settings.RUNS_DIR, settings.REPORTS_DIR, settings.SCREENSHOTS_DIR,
             settings.BASELINES_DIR, settings.SESSIONS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
