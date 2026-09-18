"""
FastAPI Server for Autonomous Black-Box UI/UX & Accessibility Testing Framework.
Exposes REST APIs, mounts the dashboard, demo store, and serves reports and screenshots.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.orchestrator import TestOrchestrator
from backend.schemas import StartTestRequest, TestRun, TestStatus

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autonomous_tester.api")

app = FastAPI(
    title="Autonomous UI/UX & A11y Testing Framework",
    description="Agentic, framework-agnostic black-box UI/UX and accessibility testing engine",
    version="1.0.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active run status & logs
active_runs: Dict[str, Dict[str, Any]] = {}
orchestrators: Dict[str, TestOrchestrator] = {}


def on_step_update(payload: Dict[str, Any]):
    """Callback triggered by orchestrator on each step transition."""
    run_id = payload.get("run_id")
    if run_id in active_runs:
        active_runs[run_id]["logs"].append(payload)
        active_runs[run_id]["current_status"] = payload.get("status")
        active_runs[run_id]["current_step"] = payload.get("step")
        active_runs[run_id]["last_message"] = payload.get("message")
        if payload.get("action"):
            active_runs[run_id]["actions"].append(payload["action"])


async def run_test_task(run_id: str, goal: str, url: str, max_steps: Optional[int], headless: Optional[bool]):
    """Background task executing the test orchestrator."""
    orchestrator = TestOrchestrator(
        headless=headless,
        max_steps=max_steps,
        on_step_callback=on_step_update,
    )
    orchestrators[run_id] = orchestrator
    try:
        evaluation = await orchestrator.execute_test(goal=goal, target_url=url)
        active_runs[run_id]["evaluation"] = evaluation.model_dump()
        active_runs[run_id]["completed"] = True
    except Exception as e:
        logger.error(f"Error in background test execution: {e}", exc_info=True)
        active_runs[run_id]["error"] = str(e)
        active_runs[run_id]["current_status"] = "FAILED"
    finally:
        active_runs[run_id]["is_running"] = False


@app.post("/api/test")
async def start_test(request: StartTestRequest, background_tasks: BackgroundTasks):
    """
    Initiate an autonomous black-box test run.
    """
    if not request.url or not request.goal:
        raise HTTPException(status_code=400, detail="Target URL and natural-language goal are required.")

    # Create placeholder run ID
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    active_runs[run_id] = {
        "run_id": run_id,
        "goal": request.goal,
        "url": request.url,
        "current_status": "STARTING",
        "current_step": 0,
        "last_message": "Initializing browser runner...",
        "actions": [],
        "logs": [],
        "is_running": True,
        "completed": False,
        "evaluation": None,
        "start_time": now.isoformat(),
    }

    # Start background execution
    background_tasks.add_task(
        run_test_task,
        run_id=run_id,
        goal=request.goal,
        url=request.url,
        max_steps=request.max_steps,
        headless=request.headless,
    )

    return {
        "run_id": run_id,
        "status": "RUNNING",
        "message": f"Autonomous test initiated for goal: '{request.goal}'",
        "target_url": request.url,
    }


@app.get("/api/test/{run_id}")
async def get_test_status(run_id: str):
    """
    Get live progress, logs, actions, and evaluation result for a test run.
    """
    # Check active runs
    if run_id in active_runs:
        return active_runs[run_id]

    # Check saved runs on disk
    saved_file = settings.RUNS_DIR / f"{run_id}.json"
    if saved_file.exists():
        with open(saved_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "run_id": run_id,
                "goal": data.get("goal"),
                "url": data.get("target_url"),
                "current_status": data.get("status"),
                "current_step": len(data.get("actions", [])),
                "actions": data.get("actions", []),
                "logs": [],
                "is_running": False,
                "completed": True,
                "metrics": data.get("metrics", {}),
            }

    raise HTTPException(status_code=404, detail="Test run not found.")


@app.get("/api/test/{run_id}/report")
async def get_json_report(run_id: str):
    """Return JSON evaluation report."""
    report_file = settings.REPORTS_DIR / f"{run_id}.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not ready or run not found.")
    return FileResponse(report_file, media_type="application/json")


@app.get("/api/test/{run_id}/report/html")
async def get_html_report(run_id: str):
    """Return standalone rendered HTML audit report."""
    html_file = settings.REPORTS_DIR / f"{run_id}.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="HTML report not ready or run not found.")
    return FileResponse(html_file, media_type="text/html")


@app.get("/api/runs")
async def list_runs():
    """List all previous test runs."""
    runs = []
    for f in sorted(settings.RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as rf:
                data = json.load(rf)
                runs.append({
                    "run_id": data.get("run_id", f.stem),
                    "goal": data.get("goal", ""),
                    "target_url": data.get("target_url", ""),
                    "status": data.get("status", "UNKNOWN"),
                    "start_time": data.get("start_time", ""),
                    "total_steps": len(data.get("actions", [])),
                    "friction_score": data.get("metrics", {}).get("friction_score", 0),
                    "a11y_score": data.get("metrics", {}).get("accessibility_score", 100),
                })
        except Exception as e:
            logger.warning(f"Error reading run file {f}: {e}")
    return {"runs": runs}


@app.get("/api/screenshots/{run_id}/{filename}")
async def get_screenshot(run_id: str, filename: str):
    """Serve screenshot image file."""
    img_path = settings.SCREENSHOTS_DIR / run_id / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found.")
    return FileResponse(img_path, media_type="image/png")


# Mount Demo Store at /demo
if settings.DEMO_APP_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(settings.DEMO_APP_DIR), html=True), name="demo_app")

# Mount Frontend Dashboard at /
if settings.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
