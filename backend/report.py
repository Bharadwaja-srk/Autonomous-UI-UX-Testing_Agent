"""
Report Generator for Autonomous UI/UX & Accessibility Testing Framework.
Generates an executive-ready standalone HTML audit report and structured JSON output.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from backend.config import settings
from backend.schemas import EvaluationResult, TestRun, TestMode

logger = logging.getLogger("autonomous_tester.report")

HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise QA Audit Report - {{ run_id }}</title>
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

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-primary); color: var(--text-primary); line-height: 1.6; padding: 40px 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }

        /* Header */
        .report-header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 36px; margin-bottom: 30px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5); position: relative; overflow: hidden;
        }
        .badge-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
        .badge { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; padding: 6px 12px; border-radius: 999px; }
        .badge-status-completed { background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-status-failed { background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-status-stopped { background: rgba(245, 158, 11, 0.15); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-id { background: var(--bg-card-subtle); color: var(--text-secondary); border: 1px solid var(--border-subtle); font-family: 'JetBrains Mono', monospace; }

        h1 { font-size: 2.2rem; font-weight: 800; margin-bottom: 12px; }
        .goal-banner { background: rgba(99, 102, 241, 0.08); border-left: 4px solid var(--accent-primary); padding: 16px 20px; border-radius: 0 var(--radius-md) var(--radius-md) 0; margin-top: 20px; }
        .meta-info { display: flex; gap: 24px; margin-top: 16px; font-size: 0.875rem; color: var(--text-secondary); }

        /* Metrics */
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 24px; }
        .metric-title { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px; }
        .metric-value { font-size: 2.2rem; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
        
        /* Section Layout */
        .section { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 32px; margin-bottom: 30px; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-subtle); }
        .section-title { font-size: 1.4rem; font-weight: 700; }

        /* Journey & Bugs */
        .journey-item, .bug-card { background: var(--bg-card-subtle); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 18px 20px; margin-bottom: 16px; }
        .bug-card.high { border-left: 4px solid var(--danger); }
        .bug-card.medium { border-left: 4px solid var(--warning); }
        .bug-title { font-size: 1.1rem; font-weight: bold; margin-bottom: 10px; }
        
        .step-thumb, .diff-thumb { max-width: 250px; border-radius: 4px; border: 1px solid #444; margin-top: 10px; }
        .step-thumb:hover, .diff-thumb:hover { transform: scale(1.05); }

        .color-green { color: var(--success); }
        .color-yellow { color: var(--warning); }
        .color-red { color: var(--danger); }
        .color-blue { color: var(--info); }
        
        pre { background: #000; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 0.8rem; color: #ff8b8b; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="report-header">
            <div class="badge-bar">
                <span class="badge badge-status-{{ status_class }}">{{ status }}</span>
                <span class="badge badge-id">RUN: {{ run_id }}</span>
                <span class="badge badge-id">MODE: {{ mode }}</span>
                <span class="badge badge-id">DEVICE: {{ device }}</span>
            </div>
            <h1>Enterprise QA Audit Report</h1>
            <div class="goal-banner">
                <span style="font-size:0.8rem; color:var(--accent-primary); font-weight:bold; text-transform:uppercase;">Test Goal / Scope</span>
                <div style="font-size:1.15rem; font-weight:600; color:var(--text-primary);">"{{ goal }}"</div>
            </div>
            <div class="meta-info">
                <div><strong>Target URL:</strong> <a href="{{ target_url }}" target="_blank" style="color:var(--info);">{{ target_url }}</a></div>
                <div><strong>Time:</strong> {{ timestamp }}</div>
            </div>
        </header>

        <!-- Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">UX Friction Score</div>
                <div class="metric-value {{ friction_color }}">{{ friction_score }}/100</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">{{ friction_label }}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Auto-Detected Bugs</div>
                <div class="metric-value {{ bugs_color }}">{{ bugs_count }}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">Network, Console, UI, Visual</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Visual & A11y Issues</div>
                <div class="metric-value {{ a11y_color }}">{{ visual_a11y_count }}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">Regressions & Violations</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Self-Healing Recoveries</div>
                <div class="metric-value color-blue">{{ recoveries_count }}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">Successful AI fallbacks</div>
            </div>
        </div>

        <!-- AI Test Plan -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">📝 Generated AI Test Plan</h2>
            </div>
            {{ test_plan_html }}
        </section>

        <!-- Bug Reports -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">🐞 Detected Bug Reports ({{ bugs_count }})</h2>
            </div>
            {{ bugs_html }}
        </section>
        
        <!-- Visual Regressions -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">👁️ Visual Regression Analysis</h2>
            </div>
            {{ visual_html }}
        </section>

        <!-- Journey -->
        <section class="section">
            <div class="section-header">
                <h2 class="section-title">🧭 Autonomous Execution Journey</h2>
                <span style="font-size: 0.85rem; color: var(--text-muted);">Session File: {{ session_file }}</span>
            </div>
            <div>
                {{ journey_html }}
            </div>
        </section>
        
    </div>
</body>
</html>
"""


class ReportGenerator:
    def __init__(self, reports_dir: Path = settings.REPORTS_DIR, screenshots_dir: Path = settings.SCREENSHOTS_DIR):
        self.reports_dir = reports_dir
        self.screenshots_dir = screenshots_dir

    def generate(self, evaluation: EvaluationResult, run: TestRun) -> Tuple[Path, Path]:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        html_path = self.reports_dir / f"{run.run_id}.html"
        json_path = self.reports_dir / f"{run.run_id}.json"

        # JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(evaluation.model_dump(), f, indent=2, default=str)
        logger.info(f"JSON Report written to: {json_path}")

        # HTML
        html_content = self._render_html(evaluation, run)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML Report written to: {html_path}")

        return html_path, json_path

    def _render_html(self, evaluation: EvaluationResult, run: TestRun) -> str:
        metrics = evaluation.metrics
        status = evaluation.status.value
        status_class = status.lower()

        # Metrics Formatting
        f_score = evaluation.friction_score
        friction_color = "color-green" if f_score <= 25 else "color-yellow" if f_score <= 55 else "color-red"
        friction_label = "Smooth Journey" if f_score <= 25 else "Moderate Friction" if f_score <= 55 else "High Friction"

        bugs_count = len(evaluation.bug_reports)
        bugs_color = "color-red" if bugs_count > 0 else "color-green"
        
        visual_a11y_count = len(evaluation.visual_diffs) + len(evaluation.findings)
        a11y_color = "color-yellow" if visual_a11y_count > 0 else "color-green"

        # Test Plan HTML
        test_plan_html = "<p style='color: var(--text-muted);'>No test plan generated.</p>"
        if evaluation.test_plan:
            cases = []
            for tc in evaluation.test_plan.test_cases:
                cases.append(f"""
                <div style="background: var(--bg-card-subtle); padding: 15px; margin-bottom: 10px; border-radius: 8px;">
                    <div style="font-weight: bold; color: var(--info);">[{tc.case_id}] {tc.title} ({tc.risk_level.value})</div>
                    <div style="font-size: 0.9rem; margin-top: 5px;">{tc.description}</div>
                </div>
                """)
            test_plan_html = "\n".join(cases)

        # Bugs HTML
        bugs_html = "<p style='color: var(--success);'>No bugs automatically detected during this run.</p>"
        if evaluation.bug_reports:
            bug_items = []
            for bug in evaluation.bug_reports:
                cls = "high" if bug.severity.value in ["HIGH", "CRITICAL"] else "medium"
                console_text = f"<pre>Console Errors:\n{chr(10).join(bug.console_errors)}</pre>" if bug.console_errors else ""
                net_text = f"<pre>Network Errors:\n{chr(10).join(bug.network_errors)}</pre>" if bug.network_errors else ""
                
                bug_items.append(f"""
                <div class="bug-card {cls}">
                    <div class="bug-title">[{bug.category.value}] {bug.title}</div>
                    <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px;">{bug.description}</div>
                    <div style="font-size: 0.85rem; color: var(--warning); margin-bottom: 10px;"><strong>Expected:</strong> {bug.expected_behavior}</div>
                    {console_text}
                    {net_text}
                    <div style="background: rgba(99, 102, 241, 0.1); padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 0.85rem;">
                        <strong>AI Suggested Fix:</strong> {bug.suggested_fix}
                    </div>
                </div>
                """)
            bugs_html = "\n".join(bug_items)

        # Visual Diffs HTML
        visual_html = "<p style='color: var(--text-muted);'>No significant visual regressions detected, or feature disabled.</p>"
        significant_diffs = [d for d in evaluation.visual_diffs if d.is_significant]
        if significant_diffs:
            v_items = []
            for d in significant_diffs:
                v_items.append(f"""
                <div class="journey-item">
                    <div style="font-weight:bold; color:var(--danger);">Step {d.step_number}: {d.diff_percentage}% Visual Change</div>
                    <div style="font-size:0.9rem; margin-top:5px;">{d.ai_explanation}</div>
                    <img class="diff-thumb" src="/api/screenshots/{run.run_id}/{Path(d.diff_path).name}" alt="Visual Diff">
                </div>
                """)
            visual_html = "\n".join(v_items)

        # Journey HTML
        journey_items = []
        for action in evaluation.recovery_actions:
            journey_items.append(f"""
            <div class="journey-item" style="border-left: 3px solid var(--info);">
                <div style="color: var(--info); font-weight: bold;">[Self-Healing Recovery] Step {action.step_number}</div>
                <div style="font-size: 0.9rem; margin-top: 5px;">Strategy: {action.recovery_strategy}</div>
                <div style="font-size: 0.9rem; color: var(--text-secondary);">{action.explanation}</div>
            </div>
            """)
            
        for item in evaluation.journey:
            step = item.get("step")
            action = item.get("action", "")
            target = item.get("target", "N/A")
            success = item.get("success", True)
            screenshot_name = item.get("screenshot")
            
            icon = "✅" if success else "❌"
            thumb = f'<img class="step-thumb" src="/api/screenshots/{run.run_id}/{screenshot_name}">' if screenshot_name else ""
            
            journey_items.append(f"""
            <div class="journey-item">
                <div style="font-weight:bold; margin-bottom:8px;">{icon} Step {step}: {action} {target}</div>
                <div style="font-size: 0.9rem; color: var(--text-secondary);">{item.get('reasoning')}</div>
                {thumb}
            </div>
            """)

        journey_html = "\n".join(journey_items)

        # Render template
        rendered = HTML_REPORT_TEMPLATE
        rendered = rendered.replace("{{ run_id }}", run.run_id)
        rendered = rendered.replace("{{ status }}", status)
        rendered = rendered.replace("{{ status_class }}", status_class)
        rendered = rendered.replace("{{ mode }}", run.mode.value)
        rendered = rendered.replace("{{ device }}", f"{evaluation.device_profile.name} ({evaluation.device_profile.viewport_width}x{evaluation.device_profile.viewport_height})")
        rendered = rendered.replace("{{ goal }}", run.goal)
        rendered = rendered.replace("{{ target_url }}", run.target_url)
        rendered = rendered.replace("{{ timestamp }}", run.start_time[:19].replace("T", " "))
        
        rendered = rendered.replace("{{ friction_score }}", str(evaluation.friction_score))
        rendered = rendered.replace("{{ friction_color }}", friction_color)
        rendered = rendered.replace("{{ friction_label }}", friction_label)
        
        rendered = rendered.replace("{{ bugs_count }}", str(bugs_count))
        rendered = rendered.replace("{{ bugs_color }}", bugs_color)
        
        rendered = rendered.replace("{{ visual_a11y_count }}", str(visual_a11y_count))
        rendered = rendered.replace("{{ a11y_color }}", a11y_color)
        
        rendered = rendered.replace("{{ recoveries_count }}", str(len(evaluation.recovery_actions)))
        
        rendered = rendered.replace("{{ test_plan_html }}", test_plan_html)
        rendered = rendered.replace("{{ bugs_html }}", bugs_html)
        rendered = rendered.replace("{{ visual_html }}", visual_html)
        rendered = rendered.replace("{{ journey_html }}", journey_html)
        rendered = rendered.replace("{{ session_file }}", f"{evaluation.session_recording_ref}.json" if evaluation.session_recording_ref else "None")

        return rendered
