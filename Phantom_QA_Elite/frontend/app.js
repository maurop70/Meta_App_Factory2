/* ═══════════════════════════════════════════════════════════
   Phantom QA Elite — Frontend Application Logic
   Antigravity-AI | app.js
   ═══════════════════════════════════════════════════════════ */

const API = '/api';
let _progressInterval = null;
let _progressStartTime = null;
let _lastTestResult = null;

// ══════════════════════════════════════════════════════════
//  INITIALIZATION
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadDashboard();
    setInterval(checkHealth, 15000);
});

async function checkHealth() {
    try {
        const r = await fetch(`${API}/health`);
        const data = await r.json();
        const dot = document.getElementById('statusDot');
        const label = document.getElementById('statusLabel');
        if (data.status === 'online') {
            dot.classList.add('online');
            label.textContent = 'Phantom QA Online';
        }
    } catch { /* offline */ }
}

async function loadDashboard() {
    try {
        const r = await fetch(`${API}/dashboard`);
        const data = await r.json();
        const s = data.stats || {};

        document.getElementById('kpiRuns').textContent = s.total_runs || '0';
        document.getElementById('kpiPassRate').textContent = (s.pass_rate || 0) + '%';
        document.getElementById('kpiApps').textContent = s.total_apps || '0';
        document.getElementById('kpiScore').textContent = (s.avg_score || 0) + '/100';

        // Recent runs
        const recent = s.recent_runs || [];
        const container = document.getElementById('recentRuns');
        if (recent.length === 0) {
            container.innerHTML = '<div class="empty-state">No test runs yet. Launch your first test!</div>';
        } else {
            container.innerHTML = recent.map(r => `
                <div class="recent-item" onclick="loadReport(${r.id})">
                    <span class="verdict-badge verdict-${r.verdict}">${r.verdict}</span>
                    <span class="recent-app">${r.app_name}</span>
                    <span class="recent-score">${r.score}/100</span>
                    <span class="recent-time">${formatTime(r.timestamp)}</span>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('Dashboard load failed:', e);
    }
}

// ══════════════════════════════════════════════════════════
//  PANEL NAVIGATION
// ══════════════════════════════════════════════════════════

function showPanel(panelId) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById(`panel-${panelId}`).classList.add('active');
    document.querySelector(`[data-panel="${panelId}"]`).classList.add('active');

    // Auto-load data for certain panels
    if (panelId === 'history') loadHistory();
    if (panelId === 'pulse') runPulse();
    if (panelId === 'repairs') loadRepairs();
    if (panelId === 'ghost-stream') connectGhostStream();
}

// ══════════════════════════════════════════════════════════
//  PROGRESS BAR
// ══════════════════════════════════════════════════════════

const TEST_STAGES = [
    { label: 'Connecting to target application', pct: 5 },
    { label: '🏗️ Architect: Scanning endpoints (OpenAPI)', pct: 15 },
    { label: '🏗️ Architect: Generating test plan via Gemini', pct: 25 },
    { label: '👻 Ghost User: Launching Playwright browser', pct: 35 },
    { label: '👻 Ghost User: Testing page load & navigation', pct: 45 },
    { label: '👻 Ghost User: Testing forms & responsive layout', pct: 55 },
    { label: '🔍 Skeptic: Attacking with empty payloads', pct: 65 },
    { label: '🔍 Skeptic: Malformed JSON & method mismatch', pct: 75 },
    { label: '🔍 Skeptic: Stress testing under load', pct: 85 },
    { label: 'Compiling composite verdict', pct: 95 },
];

function showProgress(title) {
    const overlay = document.getElementById('loadingOverlay');
    const titleEl = document.getElementById('loadingTitle');
    const subEl = document.getElementById('loadingSub');
    const fillEl = document.getElementById('progressBarFill');
    const stagesEl = document.getElementById('progressStages');
    const timerEl = document.getElementById('progressTimer');

    titleEl.textContent = title;
    subEl.textContent = 'Initializing test bench...';
    fillEl.style.width = '0%';
    overlay.classList.remove('hidden');

    stagesEl.innerHTML = TEST_STAGES.map((s, i) =>
        `<div class="progress-stage" id="pstage-${i}">
            <span class="progress-stage-icon">○</span>
            <span>${s.label}</span>
        </div>`
    ).join('');

    _progressStartTime = Date.now();
    if (_progressInterval) clearInterval(_progressInterval);
    _progressInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - _progressStartTime) / 1000);
        timerEl.textContent = `Elapsed: ${elapsed}s`;
    }, 500);

    let stageIdx = 0;
    const advanceStage = () => {
        if (stageIdx >= TEST_STAGES.length) return;
        const stage = TEST_STAGES[stageIdx];
        fillEl.style.width = stage.pct + '%';
        subEl.textContent = stage.label;

        for (let j = 0; j < stageIdx; j++) {
            const el = document.getElementById(`pstage-${j}`);
            if (el) { el.classList.remove('active'); el.classList.add('done');
                       el.querySelector('.progress-stage-icon').textContent = '✓'; }
        }
        const cur = document.getElementById(`pstage-${stageIdx}`);
        if (cur) { cur.classList.add('active');
                    cur.querySelector('.progress-stage-icon').textContent = '◎'; }

        stageIdx++;
        if (stageIdx < TEST_STAGES.length) {
            const delay = stageIdx <= 3 ? 1500 : 4000 + Math.random() * 3000;
            setTimeout(advanceStage, delay);
        }
    };
    setTimeout(advanceStage, 400);
}

function hideProgress(success = true) {
    const fillEl = document.getElementById('progressBarFill');
    const subEl = document.getElementById('loadingSub');
    const stagesEl = document.getElementById('progressStages');

    if (fillEl) fillEl.style.width = '100%';
    if (subEl) subEl.textContent = success ? 'Test complete!' : 'Error occurred';

    if (stagesEl) {
        stagesEl.querySelectorAll('.progress-stage').forEach(el => {
            el.classList.remove('active'); el.classList.add('done');
            el.querySelector('.progress-stage-icon').textContent = '✓';
        });
    }

    if (_progressInterval) clearInterval(_progressInterval);
    setTimeout(() => {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }, success ? 600 : 1200);
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ══════════════════════════════════════════════════════════
//  FULL TEST BENCH
// ══════════════════════════════════════════════════════════

async function runFullTest() {
    const targetUrl = document.getElementById('targetUrl').value.trim();
    if (!targetUrl) { showToast('Enter a target URL', 'error'); return; }

    const appName = document.getElementById('appName').value.trim() || undefined;
    const description = document.getElementById('appDescription').value.trim() || undefined;
    const skipGhost = document.getElementById('skipGhost').checked;

    showProgress('👻 Phantom QA Elite — Full Test Bench');

    // Auto-connect Ghost Stream during test
    connectGhostStream();

    try {
        const r = await fetch(`${API}/test/full`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_url: targetUrl, app_name: appName,
                                   description, skip_ghost: skipGhost }),
        });
        const data = await r.json();

        if (data.error) {
            hideProgress(false);
            showToast(`Error: ${data.error}`, 'error');
            return;
        }

        hideProgress(true);
        _lastTestResult = data;
        const elapsed = Math.floor((Date.now() - _progressStartTime) / 1000);
        showToast(`Test complete in ${elapsed}s — ${data.verdict}`, data.verdict === 'PASS' ? 'success' : 'error');

        renderFullResults(data);
        loadDashboard();
    } catch (e) {
        hideProgress(false);
        showToast(`Connection failed: ${e.message}`, 'error');
    }
}

// ══════════════════════════════════════════════════════════
//  RENDER RESULTS
// ══════════════════════════════════════════════════════════

function renderFullResults(data) {
    const container = document.getElementById('testResults');
    container.style.display = 'block';

    const p = data.phases || {};
    const verdictClass = data.score >= 80 ? 'pass' : data.score >= 50 ? 'warn' : 'fail';
    const repairs = data.fix_required || [];

    container.innerHTML = `
        <div class="verdict-banner ${data.verdict}">
            <div class="verdict-left">
                <span class="verdict-icon">${data.verdict === 'PASS' ? '✅' : data.verdict === 'WARN' ? '⚠️' : '❌'}</span>
                <div class="verdict-text">
                    <h2>${data.verdict}</h2>
                    <p>${data.app_name} — ${data.duration_seconds}s — Run #${data.run_id}</p>
                </div>
            </div>
            <div class="verdict-score ${verdictClass}">${data.score}</div>
        </div>

        ${renderAgentCard('🏗️ The Architect', p.architect, 'architect')}
        ${renderAgentCard('👻 The Ghost User', p.ghost_user, 'ghost')}
        ${renderAgentCard('🔍 The Skeptic', p.skeptic, 'skeptic')}
        ${renderRepairs(repairs)}
        ${repairs.length > 0 ? `
            <div class="repair-actions">
                <button class="primary-btn" onclick="dispatchRepairs(${data.run_id})">
                    <span>🔧</span> Dispatch Repairs to Atomizer V2
                </button>
                <button class="secondary-btn" onclick="retestRun(${data.run_id})">
                    <span>🔁</span> Re-test Now
                </button>
            </div>
        ` : ''}
    `;

    // Also populate the individual panels
    renderArchitectPanel(p.architect, data);
    renderGhostPanel(p.ghost_user);
    renderSkepticPanel(p.skeptic, repairs);
}

function renderAgentCard(title, phase, type) {
    if (!phase) return '';
    if (phase.status === 'skipped') {
        return `<div class="result-card">
            <h3>${title} <span style="color:var(--skip);font-size:12px">— SKIPPED</span></h3>
            <p style="color:var(--text-muted);font-size:12px">${phase.reason || 'Skipped'}</p>
        </div>`;
    }

    const results = phase.results || [];
    return `
        <div class="result-card">
            <h3>${title}</h3>
            <div class="result-summary">
                <div class="summary-item">
                    <div class="summary-value" style="color:${phase.score >= 80 ? 'var(--pass)' : phase.score >= 50 ? 'var(--warn)' : 'var(--fail)'}">${phase.score || 0}</div>
                    <div class="summary-label">Score</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${phase.total || 0}</div>
                    <div class="summary-label">Tests</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" style="color:var(--pass)">${phase.passed || 0}</div>
                    <div class="summary-label">Passed</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" style="color:var(--fail)">${phase.failed || 0}</div>
                    <div class="summary-label">Failed</div>
                </div>
            </div>
            <div class="test-list">
                ${results.slice(0, 15).map(r => `
                    <div class="test-item">
                        <span class="test-icon">${r.passed ? '✅' : '❌'}</span>
                        <span class="test-name">${esc(r.test_name)}</span>
                        <span class="test-detail">${esc(r.details || '')}</span>
                        <span class="test-time">${r.duration_ms ? r.duration_ms.toFixed(0) + 'ms' : ''}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function renderRepairs(repairs) {
    if (!repairs || repairs.length === 0) return '';
    return `
        <div class="result-card">
            <h3>🔧 Repair Payloads (${repairs.length})</h3>
            ${repairs.map(r => `
                <div class="repair-card">
                    <div class="repair-title">❌ ${esc(r.test_id || r.issue || 'Unknown')}</div>
                    <div class="repair-detail">${esc(r.issue || '')}</div>
                    <div class="repair-code">Fix: ${esc(r.repair_instruction || '')}</div>
                </div>
            `).join('')}
        </div>
    `;
}

// ══════════════════════════════════════════════════════════
//  REPAIR DISPATCH & RETEST
// ══════════════════════════════════════════════════════════

async function dispatchRepairs(runId) {
    showToast('Dispatching repairs to Atomizer V2...', 'info');
    try {
        const r = await fetch(`${API}/repair/dispatch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: runId }),
        });
        const data = await r.json();
        if (data.status === 'dispatched') {
            showToast(`✅ ${data.repair_count} repairs dispatched (Dispatch #${data.dispatch_id})`, 'success');
        } else if (data.status === 'atomizer_unreachable') {
            showToast(`⚠️ Atomizer V2 unreachable — dispatch saved for retry`, 'error');
        } else {
            showToast(`Dispatch status: ${data.status}`, 'info');
        }
    } catch (e) {
        showToast(`Dispatch failed: ${e.message}`, 'error');
    }
}

async function retestRun(runId) {
    showProgress('🔁 Re-testing after repair...');
    connectGhostStream();
    try {
        const r = await fetch(`${API}/repair/retest/${runId}`, { method: 'POST' });
        const data = await r.json();
        hideProgress(true);
        showToast(`Re-test complete: ${data.verdict} (Score: ${data.score})`, data.verdict === 'PASS' ? 'success' : 'error');
        loadDashboard();
        loadHistory();
    } catch (e) {
        hideProgress(false);
        showToast(`Re-test failed: ${e.message}`, 'error');
    }
}

async function loadRepairs() {
    const el = document.getElementById('repairContent');
    try {
        const r = await fetch(`${API}/repairs`);
        const data = await r.json();
        const repairs = data.repairs || [];
        if (repairs.length === 0) {
            el.innerHTML = '<div class="empty-state">No repair dispatches yet. Run tests to generate fix payloads.</div>';
            return;
        }
        el.innerHTML = `
            <div class="result-card">
                <h3>🔧 Repair Dispatches (${repairs.length})</h3>
                <div style="margin-bottom:12px;color:var(--text-secondary);font-size:13px">
                    <strong style="color:var(--accent-light)">${data.pending_count}</strong> pending
                </div>
                <div class="test-list">
                    ${repairs.map(r => `
                        <div class="test-item">
                            <span class="test-icon">${r.status === 'complete' ? '✅' : r.status === 'failed' ? '❌' : '⏳'}</span>
                            <span class="test-name">Dispatch #${r.id}</span>
                            <span class="test-detail">Run #${r.run_id} → ${esc(r.target_webhook || 'Atomizer')}</span>
                            <span class="test-time">${r.status.toUpperCase()}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Failed to load repairs: ${e.message}</div>`;
    }
}

// ══════════════════════════════════════════════════════════
//  GHOST STREAM (SSE)
// ══════════════════════════════════════════════════════════

let _ghostStreamSource = null;

const STREAM_ICONS = {
    'CONNECTED': '🟢', 'HEARTBEAT': '💓', 'SUITE_START': '🚀',
    'SUITE_END': '🏁', 'PAGE_LOAD': '🌐', 'CLICK': '👆',
    'TYPE': '⌨️', 'SCREENSHOT': '📸', 'VIEWPORT': '📐',
    'TEST_PASS': '✅', 'TEST_FAIL': '❌', 'CONSOLE_ERROR': '🚨',
};

function connectGhostStream() {
    if (_ghostStreamSource && _ghostStreamSource.readyState !== EventSource.CLOSED) return;

    const dot = document.getElementById('streamDot');
    const label = document.getElementById('streamLabel');
    const feed = document.getElementById('ghostStreamFeed');

    _ghostStreamSource = new EventSource(`${API}/ghost-stream`);

    _ghostStreamSource.onopen = () => {
        dot.classList.add('connected');
        label.textContent = 'Connected — Listening...';
    };

    _ghostStreamSource.onmessage = (e) => {
        try {
            const evt = JSON.parse(e.data);
            if (evt.type === 'HEARTBEAT') return; // Silent heartbeats

            const icon = STREAM_ICONS[evt.type] || '⚙️';
            const time = new Date(evt.timestamp).toLocaleTimeString();
            const detail = evt.action || evt.test_name || evt.url || evt.element || evt.field || evt.viewport || '';

            // Clear empty state
            const emptyState = feed.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            const card = document.createElement('div');
            card.className = `stream-event stream-${evt.type.toLowerCase()}`;
            card.innerHTML = `
                <span class="stream-event-icon">${icon}</span>
                <span class="stream-event-type">${evt.type}</span>
                <span class="stream-event-detail">${esc(String(detail).substring(0, 120))}</span>
                ${evt.persona ? `<span class="stream-event-persona">${esc(evt.persona)}</span>` : ''}
                <span class="stream-event-time">${time}</span>
            `;
            feed.appendChild(card);
            feed.scrollTop = feed.scrollHeight;

            // Cap at 200 events
            while (feed.children.length > 200) feed.removeChild(feed.firstChild);
        } catch { /* ignore parse errors */ }
    };

    _ghostStreamSource.onerror = () => {
        dot.classList.remove('connected');
        label.textContent = 'Disconnected — Reconnecting...';
    };
}

function clearGhostStream() {
    const feed = document.getElementById('ghostStreamFeed');
    feed.innerHTML = '<div class="empty-state">Stream cleared. Events will appear during the next test run.</div>';
}

// ══════════════════════════════════════════════════════════
//  INDIVIDUAL PANEL RENDERERS
// ══════════════════════════════════════════════════════════

function renderArchitectPanel(architect, data) {
    if (!architect) return;
    const el = document.getElementById('architectContent');
    const profile = architect.app_profile || {};
    const persona = architect.persona || {};

    el.innerHTML = `
        <div class="result-card">
            <h3>📋 App Profile</h3>
            <div class="result-summary">
                <div class="summary-item"><div class="summary-value">${esc(profile.type || '?')}</div><div class="summary-label">Type</div></div>
                <div class="summary-item"><div class="summary-value">${esc(profile.domain || '?')}</div><div class="summary-label">Domain</div></div>
                <div class="summary-item"><div class="summary-value">${esc(profile.risk_level || '?')}</div><div class="summary-label">Risk</div></div>
                <div class="summary-item"><div class="summary-value">${esc(profile.complexity || '?')}</div><div class="summary-label">Complexity</div></div>
            </div>
        </div>
        <div class="result-card">
            <h3>🎭 Test Persona</h3>
            <div style="font-size:13px;line-height:1.7;color:var(--text-secondary)">
                <strong style="color:var(--text-primary)">${esc(persona.name || 'Default')}</strong>
                — ${esc(persona.role || '')}
                <br>Behavior: <em>${esc(persona.behavior || '')}</em>
                <br>Expertise: ${esc(persona.expertise || '')}
            </div>
        </div>
        <div class="result-card">
            <h3>📊 Test Plan Summary</h3>
            <div class="result-summary">
                <div class="summary-item"><div class="summary-value">${architect.endpoints_found || 0}</div><div class="summary-label">Endpoints</div></div>
                <div class="summary-item"><div class="summary-value">${architect.ui_tests_planned || 0}</div><div class="summary-label">UI Tests</div></div>
                <div class="summary-item"><div class="summary-value">${architect.api_tests_planned || 0}</div><div class="summary-label">API Tests</div></div>
                <div class="summary-item"><div class="summary-value">${architect.edge_cases_planned || 0}</div><div class="summary-label">Edge Cases</div></div>
            </div>
        </div>
    `;
}

function renderGhostPanel(ghost) {
    const el = document.getElementById('ghostContent');
    if (!ghost || ghost.status === 'skipped') {
        el.innerHTML = '<div class="empty-state">Ghost User was skipped (no frontend detected or disabled)</div>';
        return;
    }
    el.innerHTML = renderAgentCard('👻 Ghost User — Full Report', ghost, 'ghost');
    if (ghost.console_errors && ghost.console_errors.length > 0) {
        el.innerHTML += `
            <div class="result-card">
                <h3>🚨 Console Errors</h3>
                <div class="test-list">
                    ${ghost.console_errors.map(e => `
                        <div class="test-item"><span class="test-icon">❌</span>
                        <span class="test-detail" style="font-family:var(--font-mono);font-size:11px">${esc(e)}</span></div>
                    `).join('')}
                </div>
            </div>
        `;
    }
}

function renderSkepticPanel(skeptic, repairs) {
    const el = document.getElementById('skepticContent');
    if (!skeptic) { el.innerHTML = '<div class="empty-state">Run a test first</div>'; return; }
    el.innerHTML = renderAgentCard('🔍 Skeptic — Full Report', skeptic, 'skeptic');
    el.innerHTML += renderRepairs(repairs);
}

// ══════════════════════════════════════════════════════════
//  HISTORY
// ══════════════════════════════════════════════════════════

async function loadHistory() {
    const el = document.getElementById('historyContent');
    try {
        const r = await fetch(`${API}/reports`);
        const data = await r.json();
        const reports = data.reports || [];

        if (reports.length === 0) {
            el.innerHTML = '<div class="empty-state">No test history yet</div>';
            return;
        }

        el.innerHTML = `
            <div class="recent-list">
                ${reports.map(r => `
                    <div class="recent-item" onclick="loadReport(${r.id})">
                        <span class="verdict-badge verdict-${r.verdict}">${r.verdict}</span>
                        <span class="recent-app">${esc(r.app_name)}</span>
                        <span class="recent-score">${r.score}/100</span>
                        <span class="recent-time">${formatTime(r.timestamp)} · ${r.duration_seconds || '?'}s</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Failed to load history: ${e.message}</div>`;
    }
}

async function loadReport(runId) {
    try {
        const r = await fetch(`${API}/reports/${runId}`);
        const data = await r.json();
        const report = data.report;
        if (!report) { showToast('Report not found', 'error'); return; }

        // Reconstruct the phases for rendering
        const fakeResult = {
            verdict: report.verdict,
            score: report.score,
            app_name: report.app_name,
            duration_seconds: report.duration_seconds,
            run_id: report.id,
            phases: {
                architect: report.architect_plan ? { status: 'complete', ...report.architect_plan.app_profile ? { app_profile: report.architect_plan.app_profile } : {} } : null,
                ghost_user: report.ghost_summary || { status: 'skipped', reason: 'Not available' },
                skeptic: report.skeptic_summary || { status: 'skipped', reason: 'Not available' },
            },
            fix_required: report.fix_required || [],
        };

        showPanel('test-runner');
        renderFullResults(fakeResult);
    } catch (e) {
        showToast(`Failed to load report: ${e.message}`, 'error');
    }
}

// ══════════════════════════════════════════════════════════
//  PULSE (System Health)
// ══════════════════════════════════════════════════════════

async function runPulse() {
    const el = document.getElementById('pulseContent');
    el.innerHTML = '<div class="empty-state">Scanning all C-Suite ports...</div>';

    try {
        const r = await fetch(`${API}/pulse`);
        const data = await r.json();
        const apps = data.apps || {};

        el.innerHTML = `
            <div style="margin-bottom:16px;color:var(--text-secondary);font-size:13px">
                <strong style="color:var(--text-primary)">${data.online}/${data.total_apps}</strong> applications online
                · Scanned at ${formatTime(data.timestamp)}
            </div>
            <div class="pulse-grid">
                ${Object.entries(apps).map(([name, info]) => `
                    <div class="pulse-card">
                        <div class="pulse-dot ${info.status}"></div>
                        <div>
                            <div class="pulse-name">${esc(name)}</div>
                            <div class="pulse-url">${esc(info.url)} · ${info.status.toUpperCase()}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        if (data.online === data.total_apps) {
            showToast(`All ${data.total_apps} systems operational ✓`, 'success');
        } else {
            showToast(`${data.total_apps - data.online} system(s) offline`, 'error');
        }
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Pulse scan failed: ${e.message}</div>`;
    }
}

// ══════════════════════════════════════════════════════════
//  UTILITIES
// ══════════════════════════════════════════════════════════

function esc(str) {
    if (!str) return '';
    const el = document.createElement('span');
    el.textContent = String(str).substring(0, 300);
    return el.innerHTML;
}

function formatTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(ts);
        return d.toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch { return ts; }
}
