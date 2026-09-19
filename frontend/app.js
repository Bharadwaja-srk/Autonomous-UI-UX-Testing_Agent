/**
 * Enterprise QA Testing Platform - Dashboard Logic
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
        const maxSteps = parseInt(document.getElementById('maxStepsInput').value, 10) || 30;
        const headless = document.getElementById('headlessCheckbox').checked;
        const visualReg = document.getElementById('visualCheckbox').checked;
        const github = document.getElementById('githubCheckbox').checked;
        const pii = document.getElementById('piiCheckbox').checked;
        const mode = document.getElementById('testModeSelect').value;
        const device = document.getElementById('deviceSelect').value;

        if (!url || !goal) {
            alert("Please enter both a target URL and a test goal.");
            return;
        }

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
                    headless: headless,
                    mode: mode,
                    device: device,
                    enable_visual_regression: visualReg,
                    enable_github_issues: github,
                    enable_pii_redaction: pii
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to start test run.");
            }

            const data = await response.json();
            this.activeRunId = data.run_id;
            this.updateActivity("Test run initialized. Booting browser and allocating device profile...");

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
        const maxSteps = parseInt(document.getElementById('maxStepsInput').value, 10) || 30;
        document.getElementById('stepCounterDisplay').innerText = `Step ${step} / ${maxSteps}`;
        document.getElementById('liveStatusBadge').innerText = data.current_status || "RUNNING";

        if (data.last_message) {
            this.updateActivity(data.last_message);
        }

        if (data.actions && data.actions.length > 0) {
            this.renderActionFeed(data.actions);
            
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
        
        // Flatten findings for dashboard UI filtering
        this.allFindings = [
            ...(evaluation.bug_reports || []).map(b => ({
                id: b.bug_id, type: 'BUG', category: b.category, severity: b.severity,
                title: b.title, desc: b.description, rec: b.suggested_fix
            })),
            ...(evaluation.findings || []).map(f => ({
                id: f.finding_id, type: 'UX', category: f.category, severity: f.severity,
                title: f.title, desc: f.description, rec: f.recommendation
            }))
        ];

        const evalCard = document.getElementById('evaluationResultsCard');
        evalCard.style.display = 'block';
        evalCard.scrollIntoView({ behavior: 'smooth' });

        document.getElementById('viewHtmlReportBtn').href = `/api/test/${evaluation.run_id}/report/html`;
        document.getElementById('downloadJsonBtn').href = `/api/test/${evaluation.run_id}/report`;

        const m = evaluation.metrics || {};
        document.getElementById('metricFrictionVal').innerText = `${evaluation.friction_score}/100`;
        document.getElementById('metricFrictionSub').innerText = evaluation.friction_score <= 25 ? 'Smooth Journey' : 'High Usability Friction';

        const bugCount = (evaluation.bug_reports || []).length;
        document.getElementById('metricBugsVal').innerText = bugCount;
        document.getElementById('metricBugsVal').className = `eval-metric-val ${bugCount > 0 ? 'color-red' : 'color-green'}`;

        const visualA11yCount = (evaluation.visual_diffs || []).length + (evaluation.findings || []).length;
        document.getElementById('metricA11yVal').innerText = visualA11yCount;

        const recoveries = (evaluation.recovery_actions || []).length;
        document.getElementById('metricRecoveriesVal').innerText = recoveries;

        document.getElementById('findingsTotalCount').innerText = this.allFindings.length;
        this.filterFindings('ALL');
    }

    filterFindings(viewType) {
        document.querySelectorAll('.findings-tab').forEach(t => t.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');

        const listContainer = document.getElementById('dashboardFindingsList');
        if (!listContainer) return;

        let filtered = [];
        if (viewType === 'ALL') filtered = this.allFindings;
        else if (viewType === 'BUGS') filtered = this.allFindings.filter(f => f.type === 'BUG');
        else if (viewType === 'UX') filtered = this.allFindings.filter(f => f.type === 'UX');

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">No issues detected for this category.</div>`;
            return;
        }

        listContainer.innerHTML = filtered.map(f => `
            <div class="dash-finding-card sev-${f.severity}">
                <div class="dash-finding-header">
                    <span class="dash-finding-title">[${f.type}] ${f.title}</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">${f.category} &bull; ${f.severity}</span>
                </div>
                <div class="dash-finding-desc">${f.desc}</div>
                <div class="dash-finding-rec"><strong>💡 Resolution:</strong> ${f.rec}</div>
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
                <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 2px; color: var(--info);">
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
        document.getElementById('actionFeedList').innerHTML = '<div class="empty-state">Waiting for first action step...</div>';
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
            text.innerText = "LAUNCH AUTONOMOUS RUN";
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
                container.innerHTML = `<div class="empty-state">No previous test runs found.</div>`;
                return;
            }

            container.innerHTML = runs.map(r => `
                <div class="past-run-item" onclick="window.open('/api/test/${r.run_id}/report/html', '_blank')">
                    <div class="past-run-header">
                        <span>${r.run_id}</span>
                        <span style="color: ${r.status === 'COMPLETED' ? 'var(--success)' : 'var(--danger)'}">${r.status}</span>
                    </div>
                    <div class="past-run-goal">${r.goal}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                        Mode: ${r.mode} &bull; Device: ${r.device_profile.name} &bull; Score: ${r.friction_score}/100
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
