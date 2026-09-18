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
    
    RUNS_DIR: Path = BASE_DIR / "runs"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    SCREENSHOTS_DIR: Path = BASE_DIR / "screenshots"
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    DEMO_APP_DIR: Path = BASE_DIR / "demo_app"


settings = Settings()

# Ensure required directories exist
for path in [settings.RUNS_DIR, settings.REPORTS_DIR, settings.SCREENSHOTS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
