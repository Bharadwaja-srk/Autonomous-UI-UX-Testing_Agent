# Autonomous UI/UX & Accessibility Testing Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-1.42%2B-2EAD33.svg)](https://playwright.dev/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%20AI-8E75FF.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agentic, framework-agnostic **Autonomous Black-Box UI/UX & Accessibility Testing Engine**. Driven by **Google Gemini** multimodal vision and **Playwright** browser automation, this framework accepts natural-language user goals (e.g., *"Search for blue running shoes and add one to the cart"*), autonomously navigates target web applications, detects usability friction points and accessibility violations, and compiles executive-ready visual audit reports.

---

##  Key Features

- ** Multimodal AI Reasoning**: Leverages Google Gemini (`gemini-3.7-flash` / `gemini-2.5-flash`) to visually analyze page screenshots alongside structured DOM interactive element snapshots to decide optimal next actions.
- ** Hybrid Dual Engine**: Features a smart fallback heuristic decision engine that allows reliable offline operation and deterministic execution even without an active API key.
- ** Black-Box Browser Automation**: Built on Playwright to execute out-of-band mouse clicks, text typing, keyboard interaction, scrolling, and navigation without modifying or invading target codebase source code.
- ** Automated Accessibility (A11y) Audit**: Real-time detection of unlabeled buttons, missing input labels, icon-only controls, and keyboard accessibility flaws during navigation.
- ** Quantitative UX Friction Scoring**: Transparent heuristic model evaluating user effort (0–100 score) penalizing excess steps, action failures, repeated clicks, cyclic navigation loops, and backtracks.
- ** Standalone Executive HTML Reports**: Renders self-contained dark-mode audit reports complete with step-by-step reasoning timelines, screenshot thumbnails, severity ratings, and actionable UI recommendations.
- ** Live Interactive Dashboard**: Web UI for monitoring real-time agent perception feeds, action logs, screenshot previews, intent templates, and run history.
- ** Built-in Demo E-Commerce Store**: Includes an integrated mock store (`/demo`) for instant out-of-the-box testing and verification.

---

##  System Architecture

```mermaid
flowchart TD
    User([User / QA Engineer]) -->|Natural Language Goal & Target URL| Dashboard[Web Dashboard / REST API]
    Dashboard --> Orchestrator[Test Orchestrator]
    
    subgraph Engine [Autonomous Agentic Engine]
        Orchestrator -->|1. Capture Screenshot & DOM| Perception[Perception Engine]
        Perception -->|2. Multimodal State Snapshot| Agent[Gemini AI Agent / Heuristic Fallback]
        Agent -->|3. Decision: Click / Type / Scroll / Done| Driver[Playwright Browser Driver]
        Driver -->|4. Execute Out-of-Band Action| TargetApp[Target Web Application / Demo Store]
    end
    
    Orchestrator -->|5. Evaluate Journey & Detect Loops| Evaluator[Evaluation Engine]
    Evaluator -->|6. Compute Friction & A11y Scores| Reporter[Report Generator]
    Reporter -->|7. Render Standalone Audit Reports| Reports[(HTML & JSON Audit Reports)]
```

---

##  Repository Structure

```
Autonomous-UI-UX-Testing-Agent/
├── backend/                  # Python FastAPI Backend Engine
│   ├── main.py               # REST API Server & static mount endpoints
│   ├── orchestrator.py       # Master controller managing test lifecycles
│   ├── perception.py         # DOM extraction & state hashing engine
│   ├── agent.py              # Gemini multimodal AI & heuristic decision engine
│   ├── driver.py             # Playwright async browser automation driver
│   ├── evaluator.py          # Journey friction calculator & loop detector
│   ├── report.py             # HTML & JSON report rendering engine
│   ├── schemas.py            # Pydantic data models & enums
│   └── config.py             # Central environment configuration settings
├── frontend/                 # Web Dashboard UI
│   ├── index.html            # Main dashboard HTML template
│   ├── style.css             # Dark-mode styling system
│   └── app.js                # Real-time state polling & frontend logic
├── demo_app/                 # Embedded Demo E-Commerce Store
│   ├── index.html            # Mock shoe store UI
│   ├── style.css             # Product grid & cart styles
│   └── store.js              # Interactive store behavior & popups
├── tests/                    # Automated Test Suite (pytest)
│   ├── test_api.py           # API endpoint integration tests
│   ├── test_driver.py        # Driver automation tests
│   ├── test_evaluator.py     # Evaluation & scoring unit tests
│   ├── test_orchestrator.py  # End-to-end orchestration tests
│   ├── test_report.py        # Report generation unit tests
│   └── test_schemas.py       # Schema validation unit tests
├── reports/                  # Generated HTML & JSON Audit Reports
├── runs/                     # Saved test run logs & state history
├── screenshots/              # Step-by-step perception screenshots
├── .env.example              # Environment variables template
├── pytest.ini                # Pytest configuration file
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: Version `3.10` or higher
- **Node.js / Chromium**: Required for Playwright browser execution

### 1. Clone the Repository

```bash
git clone https://github.com/Bharadwaja-srk/Autonomous-UI-UX-Testing_Agent.git
cd Autonomous-UI-UX-Testing-Agent
```

### 2. Set Up Virtual Environment & Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory by copying `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```env
# Gemini API Key (Required for AI visual reasoning)
GEMINI_API_KEY=your_gemini_api_key_here

# Recommended model: gemini-3.7-flash or gemini-2.5-flash
GEMINI_MODEL=gemini-3.7-flash

# Execution Settings
BROWSER_HEADLESS=false
MAX_STEPS=30
LOOP_THRESHOLD=3
ACTION_DELAY_MS=600

# Server Settings
HOST=127.0.0.1
PORT=8000
```

> **Note**: If `GEMINI_API_KEY` is omitted, the framework automatically uses the internal **Smart Heuristic Engine**, allowing full testing capability without API credentials.

---

## 💻 Running the Application

Start the FastAPI application server:

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, open your browser to access:

- **Web Dashboard**: [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/)
- **Demo E-Commerce Store**: [`http://127.0.0.1:8000/demo/`](http://127.0.0.1:8000/demo/)
- **API Documentation**: [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)

---

## 🎮 How to Use the Dashboard

1. Open [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/) in your browser.
2. Enter the **Target Web URL** (e.g. `http://127.0.0.1:8000/demo/`).
3. Type a **Natural Language Goal** or select a **Quick Intent Template**:
   - 👟 *"Search for blue running shoes and add one to the cart."*
   - 🥾 *"Explore trail category, select Apex Trail Pro, and proceed to checkout."*
   - 🏋️ *"Find black gym trainer shoes and verify size selection."*
4. Click **LAUNCH AUTONOMOUS TEST**.
5. Watch real-time perception screenshots, reasoning step feeds, and live execution status.
6. Upon run completion, review executive metrics, UX friction breakdown, accessibility findings, and click **View Full HTML Report**.

---

## 📐 Friction & Accessibility Scoring Model

The **UX Friction Score** is an automated metric (scale 0–100) quantifying user resistance and cognitive effort:

$$\text{Friction Score} = \min\Big(100,\, (3 \times E) + (12 \times F) + (5 \times R) + (8 \times B) + (25 \times L) + (20 \times D) + (4 \times A) + P\Big)$$

| Metric Factor | Deduction Weight | Description |
| :--- | :--- | :--- |
| **Excess Steps ($E$)** | +3 pts / step | Steps taken beyond the optimal direct path baseline (4 steps) |
| **Failed Interactions ($F$)** | +12 pts / failure | Unresponsive button clicks or failed input operations |
| **Repeated Clicks ($R$)** | +5 pts / repeat | Consecutive clicks on the same element (missing loading UI) |
| **Backtracks ($B$)** | +8 pts / backtrack | Browser back navigations needed to correct path |
| **Navigation Loops ($L$)** | +25 pts / loop | Cyclic state re-visitation without goal progression |
| **Dead Ends ($D$)** | +20 pts / dead-end | Terminal state without forward navigation options |
| **A11y Violations ($A$)** | +4 to +15 pts | Missing labels, low contrast, or keyboard navigation blocks |
| **Uncompleted Penalty ($P$)** | +25 pts penalty | Applied when max steps limit is reached or task fails |

---

## 🧪 Running Automated Tests

Run the complete backend test suite using `pytest`:

```bash
python -m pytest
```

---

## 🔌 API Reference

### `POST /api/test`
Initiates an autonomous test run.

**Request Body:**
```json
{
  "url": "http://127.0.0.1:8000/demo/",
  "goal": "Search for blue running shoes and add one to the cart.",
  "max_steps": 25,
  "headless": false
}
```

### `GET /api/test/{run_id}`
Retrieves live progress, action logs, and metrics for a run.

### `GET /api/test/{run_id}/report/html`
Serves the standalone rendered HTML audit report.

### `GET /api/test/{run_id}/report`
Returns structured JSON evaluation metrics.

### `GET /api/runs`
Lists all historical test runs with summary metrics.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
