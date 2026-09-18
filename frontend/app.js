/**
 * Autonomous UI/UX & A11y Testing Dashboard Logic
 */

class DashboardApp {
    constructor() {
        this.activeRunId = null;
        this.pollingInterval = null;
        this.currentEvaluation = null;
        this.allFindings = [];
        this.init();
    }

    init() {
        this.loadPastRuns();
    }

    setTemplate(goalText) {
        document.getElementById('goalInput').value = goalText;
    }

    async startTest() {
        const url = document.getElementById('targetUrl').value.trim();
        const goal = document.getElementById('goalInput').value.trim();
        const maxSteps = parseInt(document.getElementById('maxStepsInput').value, 10) || 25;
        const headless = document.getElementById('headlessCheckbox').checked;

        if (!url || !goal) {
            alert("Please enter both a target URL and a test goal.");
            return;
        }

        // Set UI to running state
        this.setRunningState(true);
        this.resetMonitor();

        try {
            const response = await fetch('/api/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    goal: goal,
                    max_steps: maxSteps,
                    headless: headless
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to start test run.");
            }

            const data = await response.json();
            this.activeRunId = data.run_id;
            this.updateActivity("Test run initialized. Connecting to browser engine...");

            // Start status polling
            this.startPolling();

        } catch (error) {
            console.error("Test start error:", error);
            alert(`Error launching test: ${error.message}`);
            this.setRunningState(false);
        }
    }

    startPolling() {
        if (this.pollingInterval) clearInterval(this.pollingInterval);

        this.pollingInterval = setInterval(async () => {
            if (!this.activeRunId) return;

            try {
                const response = await fetch(`/api/test/${this.activeRunId}`);
                if (!response.ok) return;

                const data = await response.json();
                this.handlePollUpdate(data);

                if (data.completed || data.current_status === 'COMPLETED' || data.current_status === 'FAILED' || data.current_status === 'STOPPED') {
                    clearInterval(this.pollingInterval);
                    this.handleTestCompletion(data);
                }
            } catch (err) {
                console.warn("Polling error:", err);
            }
        }, 1200);
    }

    handlePollUpdate(data) {
        const step = data.current_step || 0;
        const maxSteps = parseInt(document.getElementById('maxStepsInput').value, 10) || 25;
        document.getElementById('stepCounterDisplay').innerText = `Step ${step} / ${maxSteps}`;
        document.getElementById('liveStatusBadge').innerText = data.current_status || "RUNNING";

        if (data.last_message) {
            this.updateActivity(data.last_message);
        }

        // Render Action Feed
        if (data.actions && data.actions.length > 0) {
            this.renderActionFeed(data.actions);
            
            // Update latest screenshot
            const latestAction = data.actions[data.actions.length - 1];
            if (latestAction && latestAction.screenshot_before) {
                this.updateScreenshot(this.activeRunId, latestAction.screenshot_before);
            }
        }
    }

    handleTestCompletion(data) {
        this.setRunningState(false);
        this.updateActivity(`✅ Test Finished: ${data.current_status}`);
        document.getElementById('liveStatusBadge').innerText = data.current_status;

        // Fetch and display evaluation report
        if (data.evaluation) {
            this.renderEvaluationSummary(data.evaluation);
        } else {
            this.fetchEvaluation(this.activeRunId);
        }

        this.loadPastRuns();
    }

    async fetchEvaluation(runId) {
        try {
            const response = await fetch(`/api/test/${runId}/report`);
            if (response.ok) {
                const evalData = await response.json();
                this.renderEvaluationSummary(evalData);
            }
        } catch (e) {
            console.error("Could not fetch evaluation:", e);
        }
    }

    renderEvaluationSummary(evaluation) {
        this.currentEvaluation = evaluation;
        this.allFindings = evaluation.findings || [];

        const evalCard = document.getElementById('evaluationResultsCard');
        evalCard.style.display = 'block';
        evalCard.scrollIntoView({ behavior: 'smooth' });

        // Update Report Links
        document.getElementById('viewHtmlReportBtn').href = `/api/test/${evaluation.run_id}/report/html`;
        document.getElementById('downloadJsonBtn').href = `/api/test/${evaluation.run_id}/report`;

        // Update Metrics
        const m = evaluation.metrics || {};
        document.getElementById('metricFrictionVal').innerText = `${evaluation.friction_score}/100`;
        document.getElementById('metricFrictionSub').innerText = evaluation.friction_score <= 25 ? 'Low Friction' : evaluation.friction_score <= 55 ? 'Moderate Friction' : 'High Usability Friction';

        document.getElementById('metricA11yVal').innerText = `${evaluation.accessibility_score}/100`;
        document.getElementById('metricA11ySub').innerText = `${m.accessibility_issues_count || 0} issues detected`;

        document.getElementById('metricStepsVal').innerText = evaluation.total_steps;
        document.getElementById('metricStepsSub').innerText = `${m.successful_actions || 0} success / ${m.failed_actions || 0} fail`;

        document.getElementById('metricLoopsVal').innerText = `${m.possible_loops || 0} / ${m.backtracks || 0}`;

        document.getElementById('findingsTotalCount').innerText = this.allFindings.length;
        this.filterFindings('ALL');
    }

    filterFindings(category) {
        document.querySelectorAll('.findings-tab').forEach(t => t.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');

        const listContainer = document.getElementById('dashboardFindingsList');
        if (!listContainer) return;

        const filtered = category === 'ALL' 
            ? this.allFindings 
            : this.allFindings.filter(f => f.category === category);

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">No ${category} findings detected.</div>`;
            return;
        }

        listContainer.innerHTML = filtered.map(f => `
            <div class="dash-finding-card sev-${f.severity}">
                <div class="dash-finding-header">
                    <span class="dash-finding-title">${f.title}</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">[${f.category}] &bull; ${f.severity}</span>
                </div>
                <div class="dash-finding-desc">${f.description}</div>
                <div class="dash-finding-rec"><strong>💡 Recommendation:</strong> ${f.recommendation}</div>
            </div>
        `).join('');
    }

    renderActionFeed(actions) {
        const feedList = document.getElementById('actionFeedList');
        feedList.innerHTML = actions.map(a => `
            <div class="step-card">
                <div class="step-card-head">
                    <span class="step-card-type">Step ${a.step_number}: ${a.action_type}</span>
                    <span>${a.success ? '✅' : '❌'}</span>
                </div>
                <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 2px;">
                    ${a.target_text || (a.target_id ? `Target [${a.target_id}]` : '') || a.text_input || ''}
                </div>
                <div class="step-card-reason">${a.reasoning || ''}</div>
            </div>
        `).join('');
        feedList.scrollTop = feedList.scrollHeight;
    }

    updateScreenshot(runId, filename) {
        const img = document.getElementById('liveScreenshotImg');
        const empty = document.getElementById('emptyScreenshot');
        img.src = `/api/screenshots/${runId}/${filename}`;
        img.style.display = 'block';
        empty.style.display = 'none';
    }

    updateActivity(text) {
        document.getElementById('currentActivityText').innerText = text;
    }

    resetMonitor() {
        document.getElementById('actionFeedList').innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 20px; text-align: center;">Waiting for first action step...</div>';
        document.getElementById('emptyScreenshot').style.display = 'block';
        document.getElementById('liveScreenshotImg').style.display = 'none';
        document.getElementById('evaluationResultsCard').style.display = 'none';
    }

    setRunningState(isRunning) {
        const btn = document.getElementById('startTestBtn');
        const icon = document.getElementById('btnIcon');
        const text = document.getElementById('btnText');

        if (isRunning) {
            btn.disabled = true;
            icon.innerText = "⏳";
            text.innerText = "RUNNING AUTONOMOUS AUDIT...";
            document.getElementById('liveStatusBadge').innerText = "RUNNING";
        } else {
            btn.disabled = false;
            icon.innerText = "⚡";
            text.innerText = "LAUNCH AUTONOMOUS TEST";
        }
    }

    async loadPastRuns() {
        const container = document.getElementById('pastRunsList');
        try {
            const response = await fetch('/api/runs');
            if (!response.ok) return;

            const data = await response.json();
            const runs = data.runs || [];

            if (runs.length === 0) {
                container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 20px;">No previous test runs found.</div>`;
                return;
            }

            container.innerHTML = runs.map(r => `
                <div class="past-run-item" onclick="window.open('/api/test/${r.run_id}/report/html', '_blank')">
                    <div class="past-run-header">
                        <span>${r.run_id}</span>
                        <span>${r.status}</span>
                    </div>
                    <div class="past-run-goal">${r.goal}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                        Steps: ${r.total_steps} &bull; Friction: ${r.friction_score}/100 &bull; 📄 View Report
                    </div>
                </div>
            `).join('');
        } catch (e) {
            console.warn("Could not load past runs:", e);
        }
    }
}

const app = new DashboardApp();
window.app = app;
