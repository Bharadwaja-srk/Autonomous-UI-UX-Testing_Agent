"""
Report Generator for Autonomous UI/UX & Accessibility Testing Framework.
Generates an executive-ready standalone HTML audit report and structured JSON output.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from backend.config import settings
from backend.schemas import EvaluationResult, TestRun

logger = logging.getLogger("autonomous_tester.report")

HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI/UX & A11y Audit Report - {{ run_id }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0b0f19;
            --bg-card: #131b2e;
            --bg-card-subtle: rgba(255, 255, 255, 0.03);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.15);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #38bdf8;
            --radius-lg: 16px;
            --radius-md: 10px;
            --radius-sm: 6px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 40px 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        /* Header */
        .report-header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 36px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
        }

        .report-header::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
            pointer-events: none;
        }

        .badge-bar {
            display: flex;
            gap: 12px;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .badge {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 6px 12px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .badge-status-completed { background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-status-failed { background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-status-stopped { background: rgba(245, 158, 11, 0.15); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-id { background: var(--bg-card-subtle); color: var(--text-secondary); border: 1px solid var(--border-subtle); font-family: 'JetBrains Mono', monospace; }

        h1 {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .goal-banner {
            background: rgba(99, 102, 241, 0.08);
            border-left: 4px solid var(--accent-primary);
            padding: 16px 20px;
            border-radius: 0 var(--radius-md) var(--radius-md) 0;
            margin-top: 20px;
        }

        .goal-banner span {
            font-size: 0.8rem;
            text-transform: uppercase;
            color: var(--accent-primary);
            font-weight: 700;
            letter-spacing: 0.05em;
            display: block;
            margin-bottom: 4px;
        }

        .goal-text {
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .meta-info {
            display: flex;
            gap: 24px;
            margin-top: 16px;
            font-size: 0.875rem;
            color: var(--text-secondary);
            flex-wrap: wrap;
        }

        .meta-item strong {
            color: var(--text-primary);
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 24px;
            position: relative;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .metric-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1;
            font-family: 'JetBrains Mono', monospace;
        }

        .metric-sub {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 8px;
        }

        .color-green { color: var(--success); }
        .color-yellow { color: var(--warning); }
        .color-red { color: var(--danger); }
        .color-blue { color: var(--info); }
        .color-purple { color: var(--accent-primary); }

        /* Section Layout */
        .section {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 32px;
            margin-bottom: 30px;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-subtle);
        }

        .section-title {
            font-size: 1.4rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Journey Timeline */
        .journey-timeline {
            display: flex;
            flex-direction: column;
            gap: 20px;
            position: relative;
        }

        .journey-item {
            display: grid;
            grid-template-columns: 60px 1fr auto;
            gap: 20px;
            align-items: start;
            padding: 18px 20px;
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            transition: background 0.2s ease;
        }

        .journey-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        .step-num {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1rem;
            color: var(--accent-primary);
            background: rgba(99, 102, 241, 0.12);
            padding: 8px 12px;
            border-radius: var(--radius-sm);
            text-align: center;
            height: fit-content;
        }

        .step-body {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .step-action-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .step-action-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-secondary);
            text-transform: uppercase;
        }

        .step-reasoning {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .step-thumb {
            width: 140px;
            height: 85px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-subtle);
            object-fit: cover;
            cursor: pointer;
            transition: transform 0.2s ease;
        }

        .step-thumb:hover {
            transform: scale(1.05);
        }

        /* Findings Table / Cards */
        .findings-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .finding-card {
            padding: 20px;
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .finding-card.severity-HIGH { border-left: 4px solid var(--danger); }
        .finding-card.severity-MEDIUM { border-left: 4px solid var(--warning); }
        .finding-card.severity-LOW { border-left: 4px solid var(--info); }
        .finding-card.severity-INFO { border-left: 4px solid var(--text-muted); }

        .finding-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }

        .finding-title-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .finding-title {
            font-size: 1.05rem;
            font-weight: 700;
        }

        .severity-badge {
            font-size: 0.7rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .sev-HIGH { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .sev-MEDIUM { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .sev-LOW { background: rgba(56, 189, 248, 0.2); color: var(--info); }
        .sev-INFO { background: rgba(148, 163, 184, 0.2); color: var(--text-secondary); }

        .finding-category-tag {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 600;
        }

        .finding-desc {
            font-size: 0.92rem;
            color: var(--text-secondary);
        }

        .finding-rec {
            background: rgba(99, 102, 241, 0.06);
            border: 1px dashed rgba(99, 102, 241, 0.3);
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            font-size: 0.88rem;
            color: #c7d2fe;
        }

        .finding-rec strong {
            color: #818cf8;
        }

        /* Scoring Formula Explainer */
        .explainer-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 20px;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }

        .explainer-box ul {
            margin-left: 20px;
            margin-top: 10px;
        }

        .footer {
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-subtle);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="report-header">
            <div class="badge-bar">
                <span class="badge badge-status-{{ status_class }}">{{ status }}</span>
                <span class="badge badge-id">RUN ID: {{ run_id }}</span>
                <span class="badge badge-id">MODEL: {{ model_used }}</span>
            </div>
            <h1>Autonomous UI/UX & Accessibility Audit</h1>
            
            <div class="goal-banner">
                <span>Natural Language Test Intent</span>
                <div class="goal-text">"{{ goal }}"</div>
            </div>

            <div class="meta-info">
                <div class="meta-item"><strong>Target URL:</strong> <a href="{{ target_url }}" target="_blank" style="color: var(--info); text-decoration: none;">{{ target_url }}</a></div>
                <div class="meta-item"><strong>Timestamp:</strong> {{ timestamp }}</div>
                <div class="meta-item"><strong>Duration Steps:</strong> {{ total_steps }} steps</div>
            </div>
        </header>

        <!-- Executive Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">UX Friction Score</div>
                <div class="metric-value {{ friction_color }}">{{ friction_score }}/100</div>
                <div class="metric-sub">{{ friction_label }}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Accessibility Score</div>
                <div class="metric-value {{ a11y_color }}">{{ accessibility_score }}/100</div>
                <div class="metric-sub">{{ a11y_count }} Potential A11y Issues</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Total Journey Steps</div>
                <div class="metric-value color-blue">{{ total_steps }}</div>
                <div class="metric-sub">{{ successful_actions }} Success / {{ failed_actions }} Failures</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Navigation Loops & Backtracks</div>
                <div class="metric-value {{ loops_color }}">{{ loops_count }} / {{ backtracks_count }}</div>
                <div class="metric-sub">Loops / Backtracks Detected</div>
            </div>
        </div>

        <!-- Discovered User Journey -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">🧭 Discovered User Journey</h2>
                <span style="font-size: 0.85rem; color: var(--text-muted);">Autonomous black-box execution trace</span>
            </div>
            
            <div class="journey-timeline">
                {{ journey_html }}
            </div>
        </section>

        <!-- Audit Findings -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">🔍 Detected UX & Accessibility Findings ({{ findings_count }})</h2>
                <span style="font-size: 0.85rem; color: var(--text-muted);">Heuristically identified friction points</span>
            </div>

            <div class="findings-list">
                {{ findings_html }}
            </div>
        </section>

        <!-- Scoring Methodology Documentation -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">📐 Friction Scoring Methodology</h2>
            </div>
            <div class="explainer-box">
                <p>The UX Friction Score is an automated heuristic measure (0–100) representing user effort, confusion, and resistance experienced during goal completion:</p>
                <ul>
                    <li><strong>Excess Steps Penalty:</strong> +3 points per step exceeding the baseline direct path (4 steps).</li>
                    <li><strong>Action Failures:</strong> +12 points per failed button click or unhandled interaction.</li>
                    <li><strong>Repeated Actions:</strong> +5 points per consecutive click on the same control (indicates missing loading feedback).</li>
                    <li><strong>Cyclic Navigation Loops:</strong> +25 points when the same UI state is revisited multiple times without progress.</li>
                    <li><strong>Backtracking:</strong> +8 points per browser back navigation.</li>
                    <li><strong>Accessibility Deductions:</strong> +4 to +15 points depending on severity of missing labels or keyboard traps.</li>
                </ul>
                <p style="margin-top: 12px; font-size: 0.8rem; color: var(--text-muted);">* Note: This score is a heuristic benchmark developed for black-box autonomous testing and is not an official WCAG compliance certification.</p>
            </div>
        </section>

        <footer class="footer">
            Autonomous Agentic Black-Box UI/UX Testing Engine &bull; Powered by Google Gemini & Playwright
        </footer>
    </div>
</body>
</html>
"""


class ReportGenerator:
    def __init__(self, reports_dir: Path = settings.REPORTS_DIR, screenshots_dir: Path = settings.SCREENSHOTS_DIR):
        self.reports_dir = reports_dir
        self.screenshots_dir = screenshots_dir

    def generate(self, evaluation: EvaluationResult, run: TestRun) -> Tuple[Path, Path]:
        """
        Generate both HTML audit report and structured JSON output.
        Returns paths to (html_file, json_file).
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        html_path = self.reports_dir / f"{run.run_id}.html"
        json_path = self.reports_dir / f"{run.run_id}.json"

        # 1. Generate JSON Report
        json_data = evaluation.model_dump()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, default=str)
        logger.info(f"JSON Report written to: {json_path}")

        # 2. Generate HTML Report
        html_content = self._render_html(evaluation, run)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML Report written to: {html_path}")

        return html_path, json_path

    def _render_html(self, evaluation: EvaluationResult, run: TestRun) -> str:
        """Render the complete HTML document from evaluation data."""
        metrics = evaluation.metrics
        status = evaluation.status.value
        status_class = status.lower()

        # Friction score color & label
        f_score = evaluation.friction_score
        if f_score <= 25:
            friction_color = "color-green"
            friction_label = "Low Friction - Smooth Journey"
        elif f_score <= 55:
            friction_color = "color-yellow"
            friction_label = "Moderate Friction Detected"
        else:
            friction_color = "color-red"
            friction_label = "High Friction & Usability Issues"

        # A11y score color
        a_score = evaluation.accessibility_score
        if a_score >= 85:
            a11y_color = "color-green"
        elif a_score >= 60:
            a11y_color = "color-yellow"
        else:
            a11y_color = "color-red"

        loops_count = metrics.get("possible_loops", 0)
        loops_color = "color-red" if loops_count > 0 else "color-green"

        # Render Journey HTML
        journey_items = []
        for item in evaluation.journey:
            step = item.get("step")
            action = item.get("action", "")
            target = item.get("target", "N/A")
            input_val = item.get("input")
            reasoning = item.get("reasoning", "")
            success = item.get("success", True)
            screenshot_name = item.get("screenshot")

            input_html = f'<div style="font-family: JetBrains Mono; font-size: 0.85rem; color: #38bdf8;">Input: &quot;{input_val}&quot;</div>' if input_val else ""
            status_icon = "✅" if success else "❌"
            
            thumb_html = ""
            if screenshot_name:
                thumb_html = f'<img class="step-thumb" src="/api/screenshots/{run.run_id}/{screenshot_name}" alt="Step {step}" onclick="window.open(this.src)">'

            journey_items.append(f"""
            <div class="journey-item">
                <div class="step-num">#{step}</div>
                <div class="step-body">
                    <div class="step-action-title">
                        <span>{status_icon}</span>
                        <span class="step-action-tag">{action}</span>
                        <span>{target or ''}</span>
                    </div>
                    {input_html}
                    <div class="step-reasoning">{reasoning}</div>
                </div>
                {thumb_html}
            </div>
            """)

        journey_html = "\n".join(journey_items) if journey_items else "<p style='color: var(--text-muted);'>No journey steps recorded.</p>"

        # Render Findings HTML
        findings_items = []
        for f in evaluation.findings:
            sev = f.severity.value
            cat = f.category.value
            step_badge = f'<span style="font-size: 0.75rem; color: var(--text-muted);">Step #{f.step_number}</span>' if f.step_number else ""
            
            findings_items.append(f"""
            <div class="finding-card severity-{sev}">
                <div class="finding-header">
                    <div class="finding-title-group">
                        <span class="severity-badge sev-{sev}">{sev}</span>
                        <span class="finding-category-tag">[{cat}]</span>
                        <span class="finding-title">{f.title}</span>
                    </div>
                    {step_badge}
                </div>
                <div class="finding-desc">{f.description}</div>
                {f'<div style="font-size: 0.8rem; color: var(--text-muted); font-family: JetBrains Mono;">Evidence: {f.evidence}</div>' if f.evidence else ''}
                <div class="finding-rec"><strong>Recommendation:</strong> {f.recommendation}</div>
            </div>
            """)

        findings_html = "\n".join(findings_items) if findings_items else "<p style='color: var(--success);'>🎉 No major UX friction or accessibility flaws detected!</p>"

        # Replace in template
        rendered = HTML_REPORT_TEMPLATE
        rendered = rendered.replace("{{ run_id }}", run.run_id)
        rendered = rendered.replace("{{ status }}", status)
        rendered = rendered.replace("{{ status_class }}", status_class)
        rendered = rendered.replace("{{ model_used }}", settings.GEMINI_MODEL)
        rendered = rendered.replace("{{ goal }}", run.goal)
        rendered = rendered.replace("{{ target_url }}", run.target_url)
        rendered = rendered.replace("{{ timestamp }}", run.start_time[:19].replace("T", " "))
        rendered = rendered.replace("{{ total_steps }}", str(evaluation.total_steps))
        rendered = rendered.replace("{{ friction_score }}", str(evaluation.friction_score))
        rendered = rendered.replace("{{ friction_color }}", friction_color)
        rendered = rendered.replace("{{ friction_label }}", friction_label)
        rendered = rendered.replace("{{ accessibility_score }}", str(evaluation.accessibility_score))
        rendered = rendered.replace("{{ a11y_color }}", a11y_color)
        rendered = rendered.replace("{{ a11y_count }}", str(metrics.get("accessibility_issues_count", 0)))
        rendered = rendered.replace("{{ successful_actions }}", str(metrics.get("successful_actions", 0)))
        rendered = rendered.replace("{{ failed_actions }}", str(metrics.get("failed_actions", 0)))
        rendered = rendered.replace("{{ loops_count }}", str(loops_count))
        rendered = rendered.replace("{{ backtracks_count }}", str(metrics.get("backtracks", 0)))
        rendered = rendered.replace("{{ loops_color }}", loops_color)
        rendered = rendered.replace("{{ journey_html }}", journey_html)
        rendered = rendered.replace("{{ findings_count }}", str(len(evaluation.findings)))
        rendered = rendered.replace("{{ findings_html }}", findings_html)

        return rendered
