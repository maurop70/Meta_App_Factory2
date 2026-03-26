/**
 * CMO Agent — Main Application
 * ═══════════════════════════════════════════════════════════
 * SPA Router + Panel Renderer + API Integration
 * Antigravity-AI | CMO_Elite v1.0.0
 * ═══════════════════════════════════════════════════════════
 */

const API = 'http://localhost:5020/api';

// ══════════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════════

const state = {
    activePanel: 'dashboard',
    loading: false,
    results: {},
    dashboardStats: null,
    projectName: 'default',
    lastQuery: '',         // The original user query
    sessionIntel: {},      // Accumulated intelligence from all engines this session
    brandVisual: null,     // Current brand visual generation result
    brandCritique: null,   // Current Marcus Vane critique
};

// ══════════════════════════════════════════════════════════
//  CROSS-ENGINE INTELLIGENCE
// ══════════════════════════════════════════════════════════

/**
 * Build a context summary from all previous engine results.
 * This gets passed as 'context' to the backend API so each
 * engine builds on the others' findings.
 */
function buildSessionContext() {
    const parts = [];
    const r = state.results;

    if (r.market) {
        const m = r.market;
        parts.push(`[MARKET RESEARCH] Company: ${m.company_name || 'N/A'}. Industry: ${m.industry || 'N/A'}.`);
        parts.push(`Executive Summary: ${m.executive_summary || ''}`);
        if (m.market_sizing?.tam) parts.push(`TAM: ${m.market_sizing.tam.value}. SAM: ${m.market_sizing?.sam?.value || 'N/A'}. SOM: ${m.market_sizing?.som?.value || 'N/A'}.`);
        if (m.competitive_landscape?.length) {
            parts.push(`Key Competitors: ${m.competitive_landscape.map(c => c.competitor).join(', ')}`);
        }
        if (m.recommendation) parts.push(`Strategic Recommendation: ${m.recommendation}`);
    }

    if (r.brand) {
        const b = r.brand;
        parts.push(`[BRAND IDENTITY] Name: ${b.company_name || 'N/A'}. Tagline: "${b.tagline || ''}".`);
        parts.push(`Archetype: ${b.brand_personality?.archetype || 'N/A'}. Positioning: ${b.positioning_statement || ''}`);
        if (b.visual_identity?.color_palette) {
            const c = b.visual_identity.color_palette;
            parts.push(`Brand Colors: Primary ${c.primary}, Secondary ${c.secondary}, Accent ${c.accent}`);
        }
        if (b.tone_of_voice?.summary) parts.push(`Brand Voice: ${b.tone_of_voice.summary}`);
    }

    if (r.personas) {
        const p = r.personas;
        if (p.personas?.length) {
            parts.push(`[PERSONAS] ${p.personas.length} personas identified:`);
            p.personas.forEach(persona => {
                parts.push(`  - ${persona.name} (${persona.title}): Age ${persona.demographics?.age_range}, Income ${persona.demographics?.income_range}`);
            });
            if (p.segment_prioritization) parts.push(`Priority: ${p.segment_prioritization}`);
        }
    }

    if (r.competitive) {
        const c = r.competitive;
        parts.push(`[COMPETITIVE INTEL] ${c.analysis_summary || ''}`);
        if (c.moat_analysis) parts.push(`Moat: ${c.moat_analysis.moat_type} (${c.moat_analysis.moat_strength})`);
    }

    if (r.gtm) {
        parts.push(`[GTM PLAN] ${r.gtm.gtm_summary || ''}`);
        if (r.gtm.pricing_architecture?.model) parts.push(`Pricing Model: ${r.gtm.pricing_architecture.model}`);
    }

    if (r.campaign) {
        parts.push(`[CAMPAIGN] ${r.campaign.campaign_name || ''}: ${r.campaign.campaign_summary || ''}`);
    }

    return parts.join('\n');
}

/**
 * Generate a context banner HTML showing what intelligence is available
 * from previous engines.
 */
function renderContextBanner(currentEngine) {
    const r = state.results;
    const available = [];

    if (r.market && currentEngine !== 'market') {
        available.push({ icon: '🔍', label: 'Market Research', detail: r.market.company_name || r.market.industry || 'completed', key: 'market' });
    }
    if (r.brand && currentEngine !== 'brand') {
        available.push({ icon: '🎨', label: 'Brand Identity', detail: r.brand.company_name || 'completed', key: 'brand' });
    }
    if (r.personas && currentEngine !== 'personas') {
        available.push({ icon: '👥', label: `${r.personas.personas?.length || 0} Personas`, detail: 'profiled', key: 'personas' });
    }
    if (r.competitive && currentEngine !== 'competitive') {
        available.push({ icon: '⚔️', label: 'Competitive Intel', detail: 'analyzed', key: 'competitive' });
    }
    if (r.gtm && currentEngine !== 'gtm') {
        available.push({ icon: '🚀', label: 'GTM Playbook', detail: 'built', key: 'gtm' });
    }
    if (r.campaign && currentEngine !== 'campaign') {
        available.push({ icon: '📣', label: 'Campaign Plan', detail: r.campaign.campaign_name || 'created', key: 'campaign' });
    }

    if (available.length === 0) return '';

    const chips = available.map(a =>
        `<span class="context-chip">${a.icon} ${a.label} <span class="text-dim">(${a.detail})</span></span>`
    ).join('');

    return `
        <div class="context-banner">
            <div class="context-banner-header">
                <span class="context-banner-icon">🧠</span>
                <strong>Building on previous intelligence</strong>
            </div>
            <div class="context-chips">${chips}</div>
            <p class="context-banner-hint">This engine will automatically use insights from your previous analyses.</p>
        </div>
    `;
}

/** Get the suggested input text based on previous research */
function getSuggestedInput(currentEngine) {
    if (!state.lastQuery) return '';
    return state.lastQuery;
}

// ══════════════════════════════════════════════════════════
//  BOOT
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    checkHealth();
    loadProjectSwitcher();
    renderPanel('dashboard');
    setInterval(checkHealth, 15000);
});

// ══════════════════════════════════════════════════════════
//  HEALTH CHECK
// ══════════════════════════════════════════════════════════

async function checkHealth() {
    const dot = document.querySelector('.status-dot');
    const txt = document.querySelector('.status-text');
    try {
        const r = await fetch(`${API}/health`);
        const d = await r.json();
        dot.className = 'status-dot online';
        txt.textContent = d.gemini_configured ? 'CMO_Elite Online' : 'No API Key';
    } catch {
        dot.className = 'status-dot offline';
        txt.textContent = 'Offline';
    }
}

// ══════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const panel = btn.dataset.panel;
            document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activePanel = panel;
            renderPanel(panel);
        });
    });
}

function navigateTo(panel) {
    document.querySelectorAll('.nav-item').forEach(b => {
        b.classList.toggle('active', b.dataset.panel === panel);
    });
    state.activePanel = panel;
    renderPanel(panel);
}

// ══════════════════════════════════════════════════════════
//  PANEL ROUTER
// ══════════════════════════════════════════════════════════

function renderPanel(panelId) {
    const container = document.getElementById('panel-container');
    const renderers = {
        'dashboard': renderDashboard,
        'projects': renderProjects,
        'market-research': renderMarketResearch,
        'brand-studio': renderBrandStudio,
        'gtm-planner': renderGTMPlanner,
        'persona-builder': renderPersonaBuilder,
        'campaign-hub': renderCampaignHub,
        'competitive-intel': renderCompetitiveIntel,
    };
    const renderer = renderers[panelId];
    if (renderer) {
        container.innerHTML = '';
        const panel = document.createElement('div');
        panel.className = 'panel active';
        panel.id = `panel-${panelId}`;
        panel.innerHTML = renderer();
        container.appendChild(panel);
        // Post-render hooks
        if (panelId === 'dashboard') loadDashboard();
        if (panelId === 'projects') loadProjects();
    }
}

// ══════════════════════════════════════════════════════════
//  PROGRESS BAR SYSTEM
// ══════════════════════════════════════════════════════════

let _progressInterval = null;
let _progressStartTime = null;

const ENGINE_STAGES = {
    'market-research': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending market brief to Gemini Flash', pct: 25 },
        { label: 'Analyzing TAM/SAM/SOM...', pct: 45 },
        { label: 'Mapping competitive landscape', pct: 65 },
        { label: 'Identifying market gaps & trends', pct: 80 },
        { label: 'Compiling intelligence report', pct: 95 },
    ],
    'brand-studio': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending brief to Gemini Pro', pct: 20 },
        { label: 'Architecting brand identity...', pct: 40 },
        { label: 'Generating color palette & typography', pct: 60 },
        { label: 'Crafting tone of voice & positioning', pct: 75 },
        { label: 'Finalizing brand kit', pct: 95 },
    ],
    'gtm-plan': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending strategy brief to Gemini Pro', pct: 20 },
        { label: 'Building launch phases...', pct: 40 },
        { label: 'Designing channel strategy', pct: 55 },
        { label: 'Modeling pricing architecture', pct: 70 },
        { label: 'Identifying growth levers', pct: 85 },
        { label: 'Compiling GTM playbook', pct: 95 },
    ],
    'personas': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending audience brief to Gemini Flash', pct: 20 },
        { label: 'Profiling buyer personas...', pct: 40 },
        { label: 'Mapping psychographics & pain points', pct: 55 },
        { label: 'Dr. Aris: Cognitive bias audit...', pct: 70 },
        { label: 'Dr. Aris: Emotional trigger analysis', pct: 85 },
        { label: 'Generating persuasion architecture', pct: 95 },
    ],
    'campaigns': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending campaign objectives', pct: 20 },
        { label: 'Building messaging framework...', pct: 40 },
        { label: 'Designing channel plan', pct: 55 },
        { label: 'Building content calendar', pct: 70 },
        { label: 'Writing creative brief', pct: 85 },
        { label: 'Compiling campaign plan', pct: 95 },
    ],
    'competitive-analysis': [
        { label: 'Connecting to CMO_Elite', pct: 10 },
        { label: 'Sending competitive context', pct: 20 },
        { label: 'Running SWOT analysis...', pct: 40 },
        { label: 'Building competitive matrix', pct: 55 },
        { label: 'Assessing strategic moat', pct: 70 },
        { label: 'Generating positioning map', pct: 85 },
        { label: 'Compiling intel report', pct: 95 },
    ],
};

function showProgress(title, engineKey) {
    const overlay = document.getElementById('loadingOverlay');
    const titleEl = document.getElementById('loadingTitle');
    const subEl = document.getElementById('loadingSub');
    const fillEl = document.getElementById('progressBarFill');
    const stagesEl = document.getElementById('progressStages');
    const timerEl = document.getElementById('progressTimer');

    titleEl.textContent = title;
    subEl.textContent = 'Initializing engine...';
    fillEl.style.width = '0%';
    overlay.classList.remove('hidden');

    const stages = ENGINE_STAGES[engineKey] || ENGINE_STAGES['market-research'];

    // Render stage list
    stagesEl.innerHTML = stages.map((s, i) =>
        `<div class="progress-stage" id="pstage-${i}">
            <span class="progress-stage-icon">○</span>
            <span>${s.label}</span>
        </div>`
    ).join('');

    // Start timer
    _progressStartTime = Date.now();
    if (_progressInterval) clearInterval(_progressInterval);
    _progressInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - _progressStartTime) / 1000);
        timerEl.textContent = `Elapsed: ${elapsed}s`;
    }, 500);

    // Animate through stages
    let stageIdx = 0;
    const advanceStage = () => {
        if (stageIdx >= stages.length) return;

        const stage = stages[stageIdx];
        fillEl.style.width = stage.pct + '%';
        subEl.textContent = stage.label;

        // Mark previous stages done
        for (let j = 0; j < stageIdx; j++) {
            const el = document.getElementById(`pstage-${j}`);
            if (el) {
                el.classList.remove('active');
                el.classList.add('done');
                el.querySelector('.progress-stage-icon').textContent = '✓';
            }
        }

        // Mark current stage active
        const currentEl = document.getElementById(`pstage-${stageIdx}`);
        if (currentEl) {
            currentEl.classList.add('active');
            currentEl.querySelector('.progress-stage-icon').textContent = '◎';
        }

        stageIdx++;
        if (stageIdx < stages.length) {
            // Longer delay for AI stages, shorter for connecting
            const delay = stageIdx <= 2 ? 1200 : 3500 + Math.random() * 2500;
            setTimeout(advanceStage, delay);
        }
    };

    setTimeout(advanceStage, 300);
}

function hideProgress(success = true) {
    const fillEl = document.getElementById('progressBarFill');
    const subEl = document.getElementById('loadingSub');
    const stagesEl = document.getElementById('progressStages');

    if (fillEl) fillEl.style.width = '100%';
    if (subEl) subEl.textContent = success ? 'Analysis complete!' : 'Error occurred';

    // Mark all stages done
    if (stagesEl) {
        stagesEl.querySelectorAll('.progress-stage').forEach(el => {
            el.classList.remove('active');
            el.classList.add('done');
            el.querySelector('.progress-stage-icon').textContent = '✓';
        });
    }

    if (_progressInterval) clearInterval(_progressInterval);

    // Brief delay so user sees 100% before closing
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

async function apiCall(endpoint, input, loadingMsg = 'Analyzing...') {
    showProgress(loadingMsg, endpoint);
    try {
        const sessionContext = buildSessionContext();
        const r = await fetch(`${API}/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input,
                project_name: state.projectName,
                context: sessionContext,
            })
        });
        const data = await r.json();
        if (data.error) {
            hideProgress(false);
            showToast(`Error: ${data.error}`, 'error');
            return null;
        }
        hideProgress(true);
        const elapsed = Math.floor((Date.now() - _progressStartTime) / 1000);
        showToast(`Analysis complete in ${elapsed}s ✓`, 'success');
        return data;
    } catch (e) {
        hideProgress(false);
        showToast(`Connection failed: ${e.message}`, 'error');
        console.error('API call failed:', e);
        return null;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function severityTag(severity) {
    const map = { 'CRITICAL': 'red', 'HIGH': 'rose', 'SIGNIFICANT': 'rose', 'MEDIUM': 'yellow', 'MODERATE': 'yellow', 'LOW': 'green' };
    return `<span class="tag tag-${map[severity] || 'blue'}">${escapeHtml(severity)}</span>`;
}

// ══════════════════════════════════════════════════════════
//  DASHBOARD PANEL
// ══════════════════════════════════════════════════════════

function renderDashboard() {
    return `
        <div class="panel-header">
            <div class="panel-badge">Command Center</div>
            <h1 class="panel-title">CMO_Elite Dashboard</h1>
            <p class="panel-subtitle">Your marketing intelligence command center. Every analysis builds the CMO's institutional memory.</p>
        </div>

        <!-- Project Context Card (populated by loadDashboard) -->
        <div id="dashProjectContext"></div>

        <div class="grid-4 mb-24" id="dashKpis">
            <div class="card kpi-card"><div class="kpi-value rose" id="kpiAnalyses">—</div><div class="kpi-label">Total Analyses</div></div>
            <div class="card kpi-card"><div class="kpi-value purple" id="kpiBrands">—</div><div class="kpi-label">Brand Identities</div></div>
            <div class="card kpi-card"><div class="kpi-value cyan" id="kpiPersonas">—</div><div class="kpi-label">Personas Built</div></div>
            <div class="card kpi-card"><div class="kpi-value green" id="kpiCampaigns">—</div><div class="kpi-label">Campaigns</div></div>
        </div>

        <!-- Recent Activity (populated by loadDashboard) -->
        <div id="dashRecentActivity"></div>

        <div class="result-section-title mb-16"><span class="section-icon">⚡</span> Quick Actions</div>
        <div class="grid-3 mb-24">
            <div class="quick-action" onclick="navigateTo('market-research')">
                <div class="quick-action-icon">🔍</div>
                <div class="quick-action-title">Market Research</div>
                <div class="quick-action-desc">TAM/SAM/SOM, trends, competitive landscape</div>
            </div>
            <div class="quick-action" onclick="navigateTo('brand-studio')">
                <div class="quick-action-icon">🎨</div>
                <div class="quick-action-title">Brand Studio</div>
                <div class="quick-action-desc">Generate complete brand identities with AI</div>
            </div>
            <div class="quick-action" onclick="navigateTo('gtm-planner')">
                <div class="quick-action-icon">🚀</div>
                <div class="quick-action-title">GTM Planner</div>
                <div class="quick-action-desc">Launch playbooks, pricing, growth levers</div>
            </div>
            <div class="quick-action" onclick="navigateTo('persona-builder')">
                <div class="quick-action-icon">👥</div>
                <div class="quick-action-title">Persona Builder</div>
                <div class="quick-action-desc">Psychographic profiles + Dr. Aris audit</div>
            </div>
            <div class="quick-action" onclick="navigateTo('campaign-hub')">
                <div class="quick-action-icon">📣</div>
                <div class="quick-action-title">Campaign Hub</div>
                <div class="quick-action-desc">Campaign briefs, content calendars, messaging</div>
            </div>
            <div class="quick-action" onclick="navigateTo('competitive-intel')">
                <div class="quick-action-icon">⚔️</div>
                <div class="quick-action-title">Competitive Intel</div>
                <div class="quick-action-desc">SWOT, moat analysis, positioning matrix</div>
            </div>
        </div>

        <div class="callout">
            <div class="callout-title">🧠 Persistent Memory Active</div>
            Every analysis is saved to the CMO's institutional memory. Brand identities flow into campaigns,
            personas inform GTM strategies, and competitive insights sharpen market research — automatically.
        </div>
    `;
}

async function loadDashboard() {
    try {
        const r = await fetch(`${API}/dashboard?project_name=${encodeURIComponent(state.projectName)}`);
        const d = await r.json();
        const s = d.stats || {};
        const proj = d.project;

        // KPIs — show project-specific counts if project data is available
        if (proj) {
            const hist = proj.history || [];
            const brandCount = proj.brand ? 1 : 0;
            const personaCount = (proj.personas || []).length;
            const campaignCount = (proj.campaigns || []).length;
            document.getElementById('kpiAnalyses').textContent = hist.length;
            document.getElementById('kpiBrands').textContent = brandCount;
            document.getElementById('kpiPersonas').textContent = personaCount;
            document.getElementById('kpiCampaigns').textContent = campaignCount;
        } else {
            document.getElementById('kpiAnalyses').textContent = s.total_analyses || 0;
            document.getElementById('kpiBrands').textContent = s.total_brands || 0;
            document.getElementById('kpiPersonas').textContent = s.total_personas || 0;
            document.getElementById('kpiCampaigns').textContent = s.total_campaigns || 0;
        }

        // Project Context Card
        const ctxEl = document.getElementById('dashProjectContext');
        if (proj && ctxEl) {
            const brand = proj.brand;
            const bi = brand?.full_identity;
            const history = proj.history || [];
            const engines = [...new Set(history.map(h => h.module))];
            const enginePills = engines.map(e => {
                const info = ENGINE_LABELS[e] || { icon: '⚙️', label: e };
                return `<span class="engine-pill" title="${info.label}">${info.icon}</span>`;
            }).join('');

            let brandHtml = '';
            if (bi) {
                const rawColors = bi.visual_identity?.color_palette || {};
                // Handle both array and object color palettes
                let colorList = [];
                if (Array.isArray(rawColors)) {
                    colorList = rawColors.map(c => ({ hex: c.hex || c.value || '#888', name: c.name || '' }));
                } else if (typeof rawColors === 'object') {
                    colorList = Object.entries(rawColors).map(([name, hex]) => ({ hex: hex || '#888', name }));
                }
                const colorSwatches = colorList.slice(0, 5).map(c =>
                    `<div class="color-swatch-mini" style="background:${c.hex}" title="${c.name || c.hex}"></div>`
                ).join('');

                brandHtml = `
                    <div class="dash-brand-card">
                        <div class="dash-brand-header">
                            <div>
                                <h3 class="dash-brand-name">🏷️ ${escapeHtml(bi.company_name || 'Brand')}</h3>
                                <p class="dash-brand-tagline">"${escapeHtml(bi.tagline || '')}"</p>
                            </div>
                            <div class="dash-brand-colors">${colorSwatches}</div>
                        </div>
                        ${bi.brand_personality?.archetype ? `<p class="text-sm text-dim mt-8">Archetype: <strong>${escapeHtml(bi.brand_personality.archetype)}</strong></p>` : ''}
                        ${bi.positioning_statement ? `<p class="text-sm text-dim mt-4" style="max-width:600px">${escapeHtml(bi.positioning_statement.substring(0, 200))}${bi.positioning_statement.length > 200 ? '...' : ''}</p>` : ''}
                    </div>
                `;
            }

            ctxEl.innerHTML = `
                <div class="dash-project-banner mb-24">
                    <div class="dash-project-top">
                        <div>
                            <div class="dash-project-label">ACTIVE PROJECT</div>
                            <h2 class="dash-project-name">${escapeHtml(proj.display_name || proj.name)}</h2>
                            ${proj.description ? `<p class="text-dim text-sm mt-4">${escapeHtml(proj.description)}</p>` : ''}
                        </div>
                        <div class="dash-project-engines">${enginePills}</div>
                    </div>
                    ${brandHtml}
                </div>
            `;
        }

        // Recent Activity
        const activityEl = document.getElementById('dashRecentActivity');
        const recentItems = d.recent_activity || [];
        if (activityEl && recentItems.length > 0) {
            const items = recentItems.slice(0, 5).map(item => {
                const info = ENGINE_LABELS[item.module] || { icon: '⚙️', label: item.module };
                const time = item.created_at ? new Date(item.created_at + 'Z').toLocaleString() : '';
                const summary = item.input_summary || '';
                return `
                    <div class="dash-activity-item">
                        <span class="dash-activity-icon">${info.icon}</span>
                        <div class="dash-activity-content">
                            <strong>${info.label}</strong>
                            <span class="text-sm text-dim">${escapeHtml(summary).substring(0, 80)}</span>
                        </div>
                        <span class="text-sm text-dim">${time}</span>
                    </div>
                `;
            }).join('');

            activityEl.innerHTML = `
                <div class="result-section-title mb-16"><span class="section-icon">📜</span> Recent Activity</div>
                <div class="dash-activity-list mb-24">${items}</div>
            `;
        }
    } catch { /* silent */ }
}

// ══════════════════════════════════════════════════════════
//  MARKET RESEARCH PANEL
// ══════════════════════════════════════════════════════════

function renderMarketResearch() {
    const prev = state.results.market;
    return `
        <div class="panel-header">
            <div class="panel-badge">Market Intelligence</div>
            <h1 class="panel-title">Market Research</h1>
            <p class="panel-subtitle">TAM/SAM/SOM calculations, competitive intelligence, trend analysis, and market gap identification.</p>
        </div>

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Company, Product, or Market to Analyze</label>
                <textarea class="input-field" id="marketInput" rows="4" placeholder="Example: An AI-powered options trading analytics platform for retail traders with $25K-$500K accounts. The platform uses proprietary MMM calculations and a strategy chat interface.">${prev ? '' : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runMarketResearch()">🔍 Run Market Analysis</button>
        </div>

        <div id="marketResults">${prev ? renderMarketResults(prev) : ''}</div>
    `;
}

async function runMarketResearch() {
    const input = document.getElementById('marketInput').value;
    if (!input.trim()) return showToast('Please describe a market to analyze', 'error');
    state.lastQuery = input.trim();
    const data = await apiCall('market-research', input, '🔍 Researching Market...');
    if (data) {
        state.results.market = data;
        document.getElementById('marketResults').innerHTML = renderMarketResults(data);
    }
}

function renderMarketResults(d) {
    const tam = d.market_sizing?.tam;
    const sam = d.market_sizing?.sam;
    const som = d.market_sizing?.som;

    let html = `<div class="result-section">`;

    // Executive Summary
    html += `<div class="callout success"><div class="callout-title">📊 Executive Summary</div>${escapeHtml(d.executive_summary || '')}</div>`;

    // Market Sizing
    if (tam) {
        html += `<div class="result-section-title mt-24"><span class="section-icon">📈</span> Market Sizing</div>`;
        html += `<div class="grid-3">`;
        html += renderMarketSizeCard('TAM', tam, 'rose', '100%');
        html += renderMarketSizeCard('SAM', sam, 'purple', '60%');
        html += renderMarketSizeCard('SOM', som, 'green', '25%');
        html += `</div>`;
    }

    // Trends
    if (d.market_trends?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">📡</span> Market Trends</div>`;
        html += `<table class="data-table"><thead><tr><th>Trend</th><th>Impact</th><th>Opportunity</th></tr></thead><tbody>`;
        d.market_trends.forEach(t => {
            html += `<tr><td><strong>${escapeHtml(t.trend)}</strong><br><span class="text-sm text-dim">${escapeHtml(t.description)}</span></td><td>${severityTag(t.impact)}</td><td class="text-sm">${escapeHtml(t.opportunity)}</td></tr>`;
        });
        html += `</tbody></table>`;
    }

    // Competitors
    if (d.competitive_landscape?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">⚔️</span> Competitive Landscape</div>`;
        html += `<table class="data-table"><thead><tr><th>Competitor</th><th>Position</th><th>Strengths</th><th>Weaknesses</th></tr></thead><tbody>`;
        d.competitive_landscape.forEach(c => {
            html += `<tr><td><strong>${escapeHtml(c.competitor)}</strong></td><td><span class="tag tag-blue">${escapeHtml(c.market_position)}</span></td><td class="text-sm">${(c.strengths||[]).map(s=>'• '+escapeHtml(s)).join('<br>')}</td><td class="text-sm">${(c.weaknesses||[]).map(w=>'• '+escapeHtml(w)).join('<br>')}</td></tr>`;
        });
        html += `</tbody></table>`;
    }

    // Market Gaps
    if (d.market_gaps?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">🎯</span> Market Gaps</div><div class="grid-2">`;
        d.market_gaps.forEach(g => {
            html += `<div class="card"><div class="flex justify-between items-center mb-16"><strong>${escapeHtml(g.gap)}</strong>${severityTag(g.severity)}</div><p class="text-sm text-dim">${escapeHtml(g.entry_strategy)}</p></div>`;
        });
        html += `</div>`;
    }

    // Recommendation
    if (d.recommendation) {
        html += `<div class="callout insight mt-24"><div class="callout-title">💡 Strategic Recommendation</div>${escapeHtml(d.recommendation)}</div>`;
    }

    html += `</div>`;
    return html;
}

function renderMarketSizeCard(label, data, color, width) {
    if (!data) return '';
    return `<div class="card"><div class="kpi-value ${color}" style="margin-bottom:8px">${escapeHtml(data.value)}</div><div class="kpi-label">${label}</div><div class="market-bar mt-8"><div class="market-bar-track"><div class="market-bar-fill" style="width:${width};background:var(--${color === 'rose' ? 'accent-primary' : color})"></div></div></div><p class="text-xs text-muted mt-8">${escapeHtml(data.description)}</p><p class="text-xs text-muted" style="font-style:italic">Source: ${escapeHtml(data.source)}</p></div>`;
}

// ══════════════════════════════════════════════════════════
//  BRAND STUDIO PANEL
// ══════════════════════════════════════════════════════════

function renderBrandStudio() {
    const prev = state.results.brand;
    const suggested = getSuggestedInput('brand');
    const banner = renderContextBanner('brand');
    return `
        <div class="panel-header">
            <div class="panel-badge">Brand Architect — Gemini Pro</div>
            <h1 class="panel-title">Brand Studio</h1>
            <p class="panel-subtitle">AI-powered brand identity generation. Colors, typography, tone of voice, positioning — the complete brand kit.</p>
        </div>

        ${banner}

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Company or Product for Brand Identity</label>
                <textarea class="input-field" id="brandInput" rows="4" placeholder="Example: A B2B SaaS platform for small law firms that automates agreement management with AI-powered contract review and vault-grade encryption. Target: solo practitioners and 2-10 person firms.">${suggested ? escapeHtml(suggested) : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runBrandStudio()">🎨 Generate Brand Identity</button>
        </div>

        <div id="brandResults">${prev ? renderBrandResults(prev) : ''}</div>
    `;
}

async function runBrandStudio() {
    const input = document.getElementById('brandInput').value;
    if (!input.trim()) return showToast('Please describe a product for brand creation', 'error');
    if (!state.lastQuery) state.lastQuery = input.trim();
    const data = await apiCall('brand-studio', input, '🎨 Crafting Brand Identity...');
    if (data) {
        state.results.brand = data;
        document.getElementById('brandResults').innerHTML = renderBrandResults(data);
    }
}

function renderBrandResults(d) {
    let html = `<div class="result-section">`;

    // Header
    html += `<div class="card card-glow mb-24" style="text-align:center;padding:40px">`;
    html += `<div style="font-size:14px;color:var(--accent-primary);font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">${escapeHtml(d.brand_personality?.archetype || '')}</div>`;
    html += `<h2 style="font-family:'Outfit',sans-serif;font-size:36px;font-weight:800;color:var(--text-primary);margin-bottom:8px">${escapeHtml(d.company_name || '')}</h2>`;
    html += `<p style="font-size:18px;color:var(--text-dim);font-style:italic;margin-bottom:16px">"${escapeHtml(d.tagline || '')}"</p>`;
    html += `<p style="font-size:14px;color:var(--text-dim);max-width:600px;margin:0 auto">${escapeHtml(d.mission_statement || '')}</p>`;
    html += `</div>`;

    // Color Palette
    const colors = d.visual_identity?.color_palette;
    if (colors) {
        html += `<div class="result-section-title"><span class="section-icon">🎨</span> Color Palette</div>`;
        html += `<div class="card mb-24"><div class="color-palette">`;
        Object.entries(colors).forEach(([name, hex]) => {
            html += `<div style="text-align:center"><div class="color-swatch" style="background:${hex}" title="${name}: ${hex}" onclick="navigator.clipboard.writeText('${hex}');showToast('Copied ${hex}','success')"></div><div class="color-swatch-label">${name.replace(/_/g, ' ')}<br>${hex}</div></div>`;
        });
        html += `</div><p class="text-sm text-dim mt-16">${escapeHtml(d.visual_identity?.color_rationale || '')}</p></div>`;
    }

    // Typography
    const typo = d.visual_identity?.typography;
    if (typo) {
        html += `<div class="result-section-title"><span class="section-icon">🔤</span> Typography</div>`;
        html += `<div class="grid-3 mb-24">`;
        html += `<div class="card text-center"><div class="kpi-label mb-16">Heading Font</div><div style="font-size:24px;font-weight:700;color:var(--text-primary)">${escapeHtml(typo.heading_font)}</div></div>`;
        html += `<div class="card text-center"><div class="kpi-label mb-16">Body Font</div><div style="font-size:24px;font-weight:400;color:var(--text-primary)">${escapeHtml(typo.body_font)}</div></div>`;
        html += `<div class="card text-center"><div class="kpi-label mb-16">Mono Font</div><div style="font-size:20px;font-family:monospace;color:var(--text-primary)">${escapeHtml(typo.mono_font)}</div></div>`;
        html += `</div>`;
    }

    // Tone of Voice
    const tone = d.tone_of_voice;
    if (tone) {
        html += `<div class="result-section-title"><span class="section-icon">🗣️</span> Tone of Voice</div>`;
        html += `<div class="card mb-24"><p class="mb-16" style="font-size:16px;font-weight:600;color:var(--text-primary)">${escapeHtml(tone.summary)}</p>`;
        html += `<div class="grid-2"><div><h4 class="text-sm text-dim mb-16" style="text-transform:uppercase;letter-spacing:1px">✅ Do</h4>${(tone.dos||[]).map(d=>`<p class="text-sm mb-8" style="color:var(--green)">• ${escapeHtml(d)}</p>`).join('')}</div>`;
        html += `<div><h4 class="text-sm text-dim mb-16" style="text-transform:uppercase;letter-spacing:1px">❌ Don't</h4>${(tone.donts||[]).map(d=>`<p class="text-sm mb-8" style="color:var(--red)">• ${escapeHtml(d)}</p>`).join('')}</div></div>`;
        if (tone.example_headlines?.length) {
            html += `<div class="mt-24"><h4 class="text-sm text-dim mb-16" style="text-transform:uppercase;letter-spacing:1px">Example Headlines</h4>`;
            tone.example_headlines.forEach(h => { html += `<div class="callout mb-16" style="font-size:15px;font-weight:600;font-style:italic">"${escapeHtml(h)}"</div>`; });
            html += `</div>`;
        }
        html += `</div>`;
    }

    // Positioning
    if (d.positioning_statement) {
        html += `<div class="callout insight mt-24"><div class="callout-title">📍 Positioning Statement</div>${escapeHtml(d.positioning_statement)}</div>`;
    }

    // Brand Story
    if (d.brand_story) {
        html += `<div class="callout mt-16"><div class="callout-title">📖 Brand Story</div>${escapeHtml(d.brand_story)}</div>`;
    }

    // ══════════════════════════════════════════════════════════
    //  VISUAL STUDIO — Image Generation + Critic + Feedback
    // ══════════════════════════════════════════════════════════

    html += `<div class="visual-studio-section mt-32">`;
    html += `<div class="result-section-title"><span class="section-icon">🖼️</span> Visual Studio</div>`;

    // Mockup Type Selector + Generate Button
    html += `<div class="card mb-24">`;
    html += `<div class="visual-studio-controls">`;
    html += `<div class="input-group" style="margin-bottom:0;flex:1">`;
    html += `<label class="input-label">Mockup Type</label>`;
    html += `<select class="input-field" id="mockupTypeSelect" style="padding:12px 16px;cursor:pointer">`;
    html += `<option value="brand_board">🎯 Brand Board (Complete Overview)</option>`;
    html += `<option value="logo_concept">✨ Logo Concept</option>`;
    html += `<option value="product_packaging">📦 Product Packaging</option>`;
    html += `</select></div>`;
    html += `<button class="btn btn-primary" onclick="runBrandVisualize()" style="white-space:nowrap;margin-top:24px">🖼️ Visualize Brand</button>`;
    html += `</div></div>`;

    // Visual Preview Container
    html += `<div id="brandVisualPreview"></div>`;

    // Critic Container
    html += `<div id="brandCritiquePanel"></div>`;

    // Feedback / Refinement Section
    html += `<div id="brandFeedbackSection" style="display:none">`;
    html += `<div class="result-section-title mt-24"><span class="section-icon">💬</span> Refine Your Brand</div>`;
    html += `<div class="card">`;
    html += `<div class="input-group"><label class="input-label">Your Feedback — Tell Marcus what to change</label>`;
    html += `<textarea class="input-field" id="brandFeedbackInput" rows="3" placeholder="Example: Make the colors more premium and darker. I want a serif font for the logo. The packaging should feel more artisanal."></textarea></div>`;
    html += `<div style="display:flex;gap:12px">`;
    html += `<button class="btn btn-primary" onclick="runBrandRefine()">🔄 Refine Brand Identity</button>`;
    html += `<button class="btn" onclick="runBrandVisualizeWithFeedback()" style="background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.3);color:var(--purple)">🖼️ Regenerate Visual Only</button>`;
    html += `</div></div></div>`;

    html += `</div>`; // end visual-studio-section
    html += `</div>`;
    return html;
}

// ── Brand Visual Generation ─────────────────────────────────

async function runBrandVisualize() {
    const identity = state.results.brand;
    if (!identity) return showToast('Generate a brand identity first', 'error');

    const mockupType = document.getElementById('mockupTypeSelect')?.value || 'brand_board';
    const previewEl = document.getElementById('brandVisualPreview');

    // Show loading state
    previewEl.innerHTML = `
        <div class="card card-glow mb-24" style="text-align:center;padding:60px">
            <div class="brand-visual-loading">
                <div class="visual-spinner"></div>
                <p style="margin-top:20px;font-size:16px;color:var(--text-primary);font-weight:600">🎨 Generating brand concept...</p>
                <p class="text-sm text-dim mt-8">This may take 15-30 seconds as Gemini creates your visual</p>
            </div>
        </div>`;

    try {
        const r = await fetch(`${API}/brand-studio/visualize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                identity,
                mockup_type: mockupType,
                project_name: state.projectName,
            })
        });
        const data = await r.json();

        if (data.error) {
            previewEl.innerHTML = `<div class="callout mt-16" style="border-color:var(--red)"><div class="callout-title">⚠️ Visual Generation Error</div>${escapeHtml(data.error)}</div>`;
            return;
        }

        state.brandVisual = data;

        // Show the generated image
        previewEl.innerHTML = `
            <div class="brand-visual-container card card-glow mb-24">
                <div class="brand-visual-header">
                    <span class="tag tag-purple">AI Generated • ${escapeHtml(mockupType.replace(/_/g, ' ').toUpperCase())}</span>
                    <span class="text-xs text-muted">${escapeHtml(data.brand_name || '')}</span>
                </div>
                <div class="brand-visual-image-wrapper">
                    <img src="${escapeHtml(data.image_url)}" alt="Brand Concept for ${escapeHtml(data.brand_name || 'Brand')}" class="brand-visual-image" onclick="window.open('${escapeHtml(data.image_url)}', '_blank')"/>
                </div>
                ${data.description ? `<p class="text-sm text-dim mt-16" style="padding:0 24px 16px">${escapeHtml(data.description)}</p>` : ''}
            </div>`;

        // Show feedback section
        document.getElementById('brandFeedbackSection').style.display = 'block';

        // Auto-run critique
        showToast('Visual generated! Running Brand Critic...', 'success');
        runBrandCritique(data.image_url);

    } catch (e) {
        previewEl.innerHTML = `<div class="callout mt-16" style="border-color:var(--red)"><div class="callout-title">⚠️ Connection Error</div>${escapeHtml(e.message)}</div>`;
    }
}

async function runBrandVisualizeWithFeedback() {
    const identity = state.results.brand;
    const feedback = document.getElementById('brandFeedbackInput')?.value;
    if (!identity) return showToast('Generate a brand identity first', 'error');
    if (!feedback?.trim()) return showToast('Please provide feedback for the visual', 'error');

    const mockupType = document.getElementById('mockupTypeSelect')?.value || 'brand_board';
    const previewEl = document.getElementById('brandVisualPreview');

    previewEl.innerHTML = `
        <div class="card card-glow mb-24" style="text-align:center;padding:60px">
            <div class="brand-visual-loading">
                <div class="visual-spinner"></div>
                <p style="margin-top:20px;font-size:16px;color:var(--text-primary);font-weight:600">🔄 Regenerating with your feedback...</p>
            </div>
        </div>`;

    try {
        const r = await fetch(`${API}/brand-studio/visualize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                identity,
                mockup_type: mockupType,
                project_name: state.projectName,
                feedback: feedback,
            })
        });
        const data = await r.json();

        if (data.error) {
            previewEl.innerHTML = `<div class="callout mt-16" style="border-color:var(--red)"><div class="callout-title">⚠️ Error</div>${escapeHtml(data.error)}</div>`;
            return;
        }

        state.brandVisual = data;
        previewEl.innerHTML = `
            <div class="brand-visual-container card card-glow mb-24">
                <div class="brand-visual-header">
                    <span class="tag tag-purple">AI Generated • REFINED</span>
                    <span class="text-xs text-muted">${escapeHtml(data.brand_name || '')}</span>
                </div>
                <div class="brand-visual-image-wrapper">
                    <img src="${escapeHtml(data.image_url)}" alt="Refined Brand Concept" class="brand-visual-image" onclick="window.open('${escapeHtml(data.image_url)}', '_blank')"/>
                </div>
                ${data.description ? `<p class="text-sm text-dim mt-16" style="padding:0 24px 16px">${escapeHtml(data.description)}</p>` : ''}
            </div>`;

        showToast('Visual refined! Running critique...', 'success');
        runBrandCritique(data.image_url);
    } catch (e) {
        previewEl.innerHTML = `<div class="callout mt-16" style="border-color:var(--red)">${escapeHtml(e.message)}</div>`;
    }
}

// ── Brand Critic (Marcus Vane) ──────────────────────────────

async function runBrandCritique(imagePath) {
    const identity = state.results.brand;
    if (!identity) return;

    const critiqueEl = document.getElementById('brandCritiquePanel');
    critiqueEl.innerHTML = `
        <div class="card mb-24" style="text-align:center;padding:40px">
            <div class="visual-spinner" style="margin:0 auto"></div>
            <p style="margin-top:16px;color:var(--text-primary);font-weight:600">🧑‍🎨 Marcus Vane is reviewing your brand...</p>
            <p class="text-xs text-dim mt-8">Senior Creative Director • Pentagram / IDEO / Collins</p>
        </div>`;

    try {
        const r = await fetch(`${API}/brand-studio/critique`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                identity,
                image_path: imagePath || null,
                project_name: state.projectName,
            })
        });
        const critique = await r.json();
        state.brandCritique = critique;
        critiqueEl.innerHTML = renderBrandCritique(critique);
    } catch (e) {
        critiqueEl.innerHTML = `<div class="callout" style="border-color:var(--red)">Critique failed: ${escapeHtml(e.message)}</div>`;
    }
}

function renderBrandCritique(c) {
    const score = c.overall_score || 0;
    const scoreColor = score >= 80 ? 'var(--green)' : score >= 60 ? 'var(--yellow)' : 'var(--red)';
    const verdictColors = { 'EXCEPTIONAL': 'green', 'STRONG': 'cyan', 'SOLID': 'blue', 'NEEDS_WORK': 'yellow', 'WEAK': 'red' };

    let html = `<div class="brand-critic-card card card-glow mb-24">`;

    // Critic Header
    html += `<div class="critic-header">`;
    html += `<div class="critic-avatar">MV</div>`;
    html += `<div><strong style="color:var(--text-primary);font-size:16px">${escapeHtml(c.critic_name || 'Marcus Vane')}</strong>`;
    html += `<div class="text-xs text-dim">${escapeHtml(c.critic_title || 'Senior Creative Director')}</div></div>`;
    html += `<div class="critic-score-badge" style="--score-color:${scoreColor}">`;
    html += `<svg viewBox="0 0 36 36" class="critic-score-ring"><path class="score-bg" d="M18 2.0845a15.9155 15.9155 0 0 1 0 31.831a15.9155 15.9155 0 0 1 0-31.831" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="3"/><path class="score-fill" d="M18 2.0845a15.9155 15.9155 0 0 1 0 31.831a15.9155 15.9155 0 0 1 0-31.831" fill="none" stroke="${scoreColor}" stroke-width="3" stroke-dasharray="${score}, 100" stroke-linecap="round"/></svg>`;
    html += `<span class="score-value">${score}</span>`;
    html += `</div></div>`;

    // Verdict + One-liner
    html += `<div style="margin:16px 0"><span class="tag tag-${verdictColors[c.verdict] || 'blue'}" style="font-size:13px;padding:6px 16px">${escapeHtml(c.verdict || 'REVIEWING')}</span></div>`;
    if (c.one_liner) {
        html += `<p style="font-size:16px;font-style:italic;color:var(--text-primary);margin:12px 0;font-weight:500">"${escapeHtml(c.one_liner)}"</p>`;
    }

    // Strengths
    if (c.strengths?.length) {
        html += `<div class="critic-section"><h4 class="critic-section-title" style="color:var(--green)">✅ Strengths</h4>`;
        c.strengths.forEach(s => {
            html += `<div class="critic-item"><strong>${escapeHtml(s.point)}</strong><p class="text-sm text-dim">${escapeHtml(s.detail)}</p>`;
            if (s.industry_reference) html += `<span class="text-xs" style="color:var(--purple)">Industry ref: ${escapeHtml(s.industry_reference)}</span>`;
            html += `</div>`;
        });
        html += `</div>`;
    }

    // Weaknesses
    if (c.weaknesses?.length) {
        html += `<div class="critic-section"><h4 class="critic-section-title" style="color:var(--red)">⚠️ Weaknesses</h4>`;
        c.weaknesses.forEach(w => {
            html += `<div class="critic-item"><strong>${escapeHtml(w.point)}</strong><p class="text-sm text-dim">${escapeHtml(w.detail)}</p>`;
            if (w.fix) html += `<p class="text-sm" style="color:var(--cyan)">💡 Fix: ${escapeHtml(w.fix)}</p>`;
            html += `</div>`;
        });
        html += `</div>`;
    }

    // Suggestions
    if (c.suggestions?.length) {
        html += `<div class="critic-section"><h4 class="critic-section-title" style="color:var(--purple)">🎯 Suggestions</h4>`;
        c.suggestions.forEach(s => {
            const effortColor = s.effort === 'QUICK_WIN' ? 'green' : s.effort === 'MODERATE' ? 'yellow' : 'red';
            html += `<div class="critic-item"><div class="flex justify-between items-center"><strong>#${s.priority} ${escapeHtml(s.suggestion)}</strong><span class="tag tag-${effortColor}">${escapeHtml(s.effort || '')}</span></div>`;
            html += `<p class="text-sm text-dim">${escapeHtml(s.rationale)}</p></div>`;
        });
        html += `</div>`;
    }

    // Sub-scores
    const subScores = [
        { label: 'Typography', data: c.typography_review, icon: '🔤' },
        { label: 'Colors', data: c.color_review, icon: '🎨' },
        { label: 'Naming', data: c.naming_review, icon: '✨' },
    ];
    const validScores = subScores.filter(s => s.data?.score);
    if (validScores.length) {
        html += `<div class="grid-3 mt-16">`;
        validScores.forEach(s => {
            const sc = s.data.score;
            const col = sc >= 80 ? 'var(--green)' : sc >= 60 ? 'var(--yellow)' : 'var(--red)';
            html += `<div class="card text-center" style="padding:16px"><div style="font-size:20px">${s.icon}</div><div class="kpi-value" style="color:${col};font-size:28px;margin:4px 0">${sc}</div><div class="kpi-label">${s.label}</div><p class="text-xs text-dim mt-8">${escapeHtml(s.data.comment || '')}</p></div>`;
        });
        html += `</div>`;
    }

    // Competitor Comparison
    if (c.competitor_comparison) {
        const cc = c.competitor_comparison;
        html += `<div class="callout mt-16" style="border-color:var(--purple)"><div class="callout-title">⚔️ Competitive Context: ${escapeHtml(cc.industry || '')}</div>`;
        html += `<p class="text-sm"><strong>Top Competitors:</strong> ${(cc.top_competitors||[]).map(t => escapeHtml(t)).join(', ')}</p>`;
        html += `<p class="text-sm mt-8">${escapeHtml(cc.positioning_gap || '')}</p></div>`;
    }

    // Final Recommendation
    if (c.overall_recommendation) {
        html += `<div class="callout success mt-16"><div class="callout-title">💡 Marcus's Final Recommendation</div>${escapeHtml(c.overall_recommendation)}</div>`;
    }

    html += `</div>`;
    return html;
}

// ── Brand Refine (Full Identity Regeneration) ───────────────

async function runBrandRefine() {
    const feedback = document.getElementById('brandFeedbackInput')?.value;
    if (!feedback?.trim()) return showToast('Please provide feedback to refine the brand', 'error');

    const originalInput = document.getElementById('brandInput')?.value || state.lastQuery;
    const criticNotes = state.brandCritique?.overall_recommendation || '';

    showProgress('🔄 Refining Brand Identity...', 'brand-refine');

    try {
        const r = await fetch(`${API}/brand-studio/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input: originalInput,
                feedback,
                critic_notes: criticNotes,
                project_name: state.projectName,
            })
        });
        const data = await r.json();
        hideProgress(true);

        if (data.error) {
            showToast(`Error: ${data.error}`, 'error');
            return;
        }

        state.results.brand = data;
        document.getElementById('brandResults').innerHTML = renderBrandResults(data);
        showToast('Brand identity refined! Click Visualize to see the updated design.', 'success');
    } catch (e) {
        hideProgress(false);
        showToast(`Refinement failed: ${e.message}`, 'error');
    }
}


// ══════════════════════════════════════════════════════════
//  GTM PLANNER PANEL
// ══════════════════════════════════════════════════════════

function renderGTMPlanner() {
    const prev = state.results.gtm;
    const suggested = getSuggestedInput('gtm');
    const banner = renderContextBanner('gtm');
    return `
        <div class="panel-header">
            <div class="panel-badge">Strategy Engine — Gemini Pro</div>
            <h1 class="panel-title">GTM Planner</h1>
            <p class="panel-subtitle">Go-to-Market playbooks with launch phasing, channel strategy, pricing architecture, and growth levers.</p>
        </div>

        ${banner}

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Product and Target Market</label>
                <textarea class="input-field" id="gtmInput" rows="4" placeholder="Example: AI-powered educational companion for special-needs students. B2B licensing model targeting therapy clinics and private schools.">${suggested ? escapeHtml(suggested) : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runGTMPlan()">🚀 Generate GTM Playbook</button>
        </div>

        <div id="gtmResults">${prev ? renderGTMResults(prev) : ''}</div>
    `;
}

async function runGTMPlan() {
    const input = document.getElementById('gtmInput').value;
    if (!input.trim()) return showToast('Please describe a product for GTM planning', 'error');
    if (!state.lastQuery) state.lastQuery = input.trim();
    const data = await apiCall('gtm-plan', input, '🚀 Building GTM Playbook...');
    if (data) {
        state.results.gtm = data;
        document.getElementById('gtmResults').innerHTML = renderGTMResults(data);
    }
}

function renderGTMResults(d) {
    let html = `<div class="result-section">`;

    html += `<div class="callout success"><div class="callout-title">🚀 GTM Summary</div>${escapeHtml(d.gtm_summary || '')}</div>`;

    // Launch Phases as Timeline
    if (d.launch_phases?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">📅</span> Launch Phases</div>`;
        html += `<div class="timeline">`;
        d.launch_phases.forEach(p => {
            html += `<div class="timeline-item"><div class="timeline-phase">${escapeHtml(p.phase)}</div><div class="timeline-period">${escapeHtml(p.timeline)}</div>`;
            html += `<p class="text-sm text-dim mb-16">${(p.objectives||[]).map(o=>'• '+escapeHtml(o)).join('<br>')}</p>`;
            html += `<div class="persona-traits">${(p.tactics||[]).map(t=>`<span class="tag tag-blue">${escapeHtml(t)}</span>`).join('')}</div>`;
            html += `</div>`;
        });
        html += `</div>`;
    }

    // Channel Strategy
    if (d.channel_strategy?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">📣</span> Channel Strategy</div>`;
        html += `<table class="data-table"><thead><tr><th>Channel</th><th>Priority</th><th>Audience Fit</th><th>Est. CAC</th></tr></thead><tbody>`;
        d.channel_strategy.forEach(c => {
            const pColor = c.priority === 'PRIMARY' ? 'rose' : c.priority === 'SECONDARY' ? 'blue' : 'yellow';
            html += `<tr><td><strong>${escapeHtml(c.channel)}</strong></td><td><span class="tag tag-${pColor}">${escapeHtml(c.priority)}</span></td><td class="text-sm">${escapeHtml(c.audience_fit)}</td><td class="text-mono">${escapeHtml(c.estimated_cac)}</td></tr>`;
        });
        html += `</tbody></table>`;
    }

    // Pricing
    if (d.pricing_architecture?.tiers?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">💰</span> Pricing Architecture</div>`;
        html += `<div class="callout mb-16"><div class="callout-title">Model: ${escapeHtml(d.pricing_architecture.model)}</div>${escapeHtml(d.pricing_architecture.rationale)}</div>`;
        html += `<div class="grid-3">`;
        d.pricing_architecture.tiers.forEach(t => {
            html += `<div class="card"><div class="kpi-value cyan" style="margin-bottom:8px">${escapeHtml(t.price)}</div><div class="kpi-label mb-16">${escapeHtml(t.name)}</div><p class="text-xs text-dim mb-16">${escapeHtml(t.target_segment)}</p>${(t.features||[]).map(f=>`<p class="text-sm mb-8">✓ ${escapeHtml(f)}</p>`).join('')}</div>`;
        });
        html += `</div>`;
    }

    // Growth Levers
    if (d.growth_levers?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">📈</span> Growth Levers</div><div class="grid-2">`;
        d.growth_levers.forEach(l => {
            const typeColor = { 'PRODUCT_LED': 'green', 'COMMUNITY_LED': 'purple', 'PARTNER_LED': 'blue', 'CONTENT_LED': 'cyan', 'SALES_LED': 'orange' };
            html += `<div class="card"><div class="flex justify-between items-center mb-16"><strong>${escapeHtml(l.lever)}</strong><span class="tag tag-${typeColor[l.type]||'blue'}">${escapeHtml(l.type?.replace(/_/g, ' '))}</span></div><p class="text-sm text-dim">${escapeHtml(l.description)}</p><p class="text-xs text-muted mt-8">Impact: ${severityTag(l.expected_impact)} • Timeline: ${escapeHtml(l.timeline_to_impact)}</p></div>`;
        });
        html += `</div>`;
    }

    // First 90 Days
    if (d.first_90_days_plan) {
        html += `<div class="callout insight mt-24"><div class="callout-title">📋 First 90 Days</div>${escapeHtml(d.first_90_days_plan)}</div>`;
    }

    html += `</div>`;
    return html;
}

// ══════════════════════════════════════════════════════════
//  PERSONA BUILDER PANEL
// ══════════════════════════════════════════════════════════

function renderPersonaBuilder() {
    const prev = state.results.personas;
    const suggested = getSuggestedInput('personas');
    const banner = renderContextBanner('personas');
    return `
        <div class="panel-header">
            <div class="panel-badge">Audience Intelligence + Dr. Aris</div>
            <h1 class="panel-title">Persona Builder</h1>
            <p class="panel-subtitle">AI-generated buyer personas with psychographic profiling, enriched by Dr. Aris's cognitive bias and emotional trigger audit.</p>
        </div>

        ${banner}

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Product and Target Audience</label>
                <textarea class="input-field" id="personaInput" rows="4" placeholder="Example: A calendar-synced smart reminder system with voice input and ML categorization. Target audience: busy professionals, startup founders, and productivity enthusiasts.">${suggested ? escapeHtml(suggested) : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runPersonas()">👥 Build Personas + Dr. Aris Audit</button>
        </div>

        <div id="personaResults">${prev ? renderPersonaResults(prev) : ''}</div>
    `;
}

async function runPersonas() {
    const input = document.getElementById('personaInput').value;
    if (!input.trim()) return showToast('Please describe a target audience', 'error');
    if (!state.lastQuery) state.lastQuery = input.trim();
    const data = await apiCall('personas', input, '👥 Building Personas + Dr. Aris Audit...');
    if (data) {
        state.results.personas = data;
        document.getElementById('personaResults').innerHTML = renderPersonaResults(data);
    }
}

function renderPersonaResults(d) {
    let html = `<div class="result-section">`;

    // Personas
    if (d.personas?.length) {
        d.personas.forEach(p => {
            html += `<div class="persona-card mb-24">`;
            html += `<div class="persona-avatar">${escapeHtml(p.avatar_emoji || '👤')}</div>`;
            html += `<div class="persona-name">${escapeHtml(p.name)}</div>`;
            html += `<div class="persona-title-text">${escapeHtml(p.title)}</div>`;

            // Demographics
            const demo = p.demographics;
            if (demo) {
                html += `<p class="text-sm text-dim mb-16">Age: ${escapeHtml(demo.age_range)} • Income: ${escapeHtml(demo.income_range)} • ${escapeHtml(demo.job_title)}</p>`;
            }

            // Traits
            const traits = p.psychographics?.personality_traits || [];
            if (traits.length) {
                html += `<div class="persona-traits">${traits.map((t,i)=>`<span class="tag tag-${['rose','purple','green','cyan','blue'][i%5]}">${escapeHtml(t)}</span>`).join('')}</div>`;
            }

            // Pain Points
            if (p.pain_points?.length) {
                html += `<div class="mt-16"><h4 class="text-sm text-dim mb-8" style="text-transform:uppercase;letter-spacing:1px">Pain Points</h4>`;
                p.pain_points.forEach(pp => {
                    html += `<div style="padding:8px 12px;background:rgba(0,0,0,0.2);border-radius:8px;margin-bottom:6px;border-left:3px solid var(--red)"><strong class="text-sm">${escapeHtml(pp.pain)}</strong> ${severityTag(pp.intensity)}<br><span class="text-xs text-dim">${escapeHtml(pp.frustration)}</span></div>`;
                });
                html += `</div>`;
            }

            // Emotional Hooks
            if (p.emotional_hooks?.length) {
                html += `<div class="mt-16"><h4 class="text-sm text-dim mb-8" style="text-transform:uppercase;letter-spacing:1px">🎯 Emotional Hooks</h4>`;
                p.emotional_hooks.forEach(h => {
                    html += `<div class="callout mb-8" style="font-style:italic;font-size:13px">"${escapeHtml(h)}"</div>`;
                });
                html += `</div>`;
            }

            // Buyer Journey
            const bj = p.buyer_journey;
            if (bj) {
                html += `<div class="mt-16"><h4 class="text-sm text-dim mb-8" style="text-transform:uppercase;letter-spacing:1px">Buyer Journey</h4>`;
                html += `<div class="grid-2"><div class="text-sm"><strong class="text-accent">Awareness Trigger:</strong><br>${escapeHtml(bj.awareness_trigger)}</div><div class="text-sm"><strong class="text-accent">Decision Driver:</strong><br>${escapeHtml(bj.decision_driver)}</div></div>`;
                html += `</div>`;
            }

            html += `</div>`;
        });
    }

    // Cross-persona insights
    if (d.segment_prioritization) {
        html += `<div class="callout success mt-24"><div class="callout-title">🎯 Segment Prioritization</div>${escapeHtml(d.segment_prioritization)}</div>`;
    }

    // Dr. Aris Audit
    const audit = d.dr_aris_audit;
    if (audit && audit.audit_status) {
        html += `<div class="dr-aris-section mt-32">`;
        html += `<div class="dr-aris-header"><span class="dr-aris-icon">🩻</span><div><div class="dr-aris-title">Dr. Aris — Behavioral Strategy Audit</div><div class="dr-aris-subtitle">Cognitive biases, emotional triggers, and persuasion architecture</div></div><span class="tag tag-purple" style="margin-left:auto">${escapeHtml(audit.audit_status)}</span></div>`;

        // Per-persona audits
        const personaAudits = audit.persona_audits || [];
        personaAudits.forEach(pa => {
            html += `<div class="card mb-16"><h4 style="color:var(--text-primary);margin-bottom:12px">${escapeHtml(pa.persona_name)} <span class="text-mono text-sm" style="color:var(--purple)">Persuasion: ${(pa.persuasion_score * 100).toFixed(0)}%</span></h4>`;

            // Cognitive Biases
            if (pa.cognitive_biases?.length) {
                html += `<h5 class="text-xs text-dim mb-8" style="text-transform:uppercase;letter-spacing:1px">Cognitive Biases</h5>`;
                pa.cognitive_biases.forEach(b => {
                    html += `<div class="bias-item"><div class="flex justify-between items-center"><strong class="text-sm">${escapeHtml(b.bias)}</strong>${severityTag(b.relevance)}</div><p class="text-sm text-dim mt-8">${escapeHtml(b.messaging_leverage)}</p></div>`;
                });
            }

            // Emotional Triggers
            if (pa.emotional_triggers?.length) {
                html += `<h5 class="text-xs text-dim mb-8 mt-16" style="text-transform:uppercase;letter-spacing:1px">Emotional Triggers</h5>`;
                pa.emotional_triggers.forEach(t => {
                    html += `<div class="trigger-item"><div class="flex justify-between items-center"><strong class="text-sm">${escapeHtml(t.trigger)}</strong><span class="tag tag-${t.intensity==='STRONG'?'rose':t.intensity==='MODERATE'?'yellow':'blue'}">${escapeHtml(t.intensity)}</span></div><p class="text-sm text-dim mt-8">${escapeHtml(t.recommended_message)}</p></div>`;
                });
            }

            html += `</div>`;
        });

        // Strategic Recommendation
        if (audit.strategic_recommendation) {
            html += `<div class="callout insight"><div class="callout-title">🧠 Dr. Aris Strategic Recommendation</div>${escapeHtml(audit.strategic_recommendation)}</div>`;
        }

        html += `</div>`;
    }

    html += `</div>`;
    return html;
}

// ══════════════════════════════════════════════════════════
//  CAMPAIGN HUB PANEL
// ══════════════════════════════════════════════════════════

function renderCampaignHub() {
    const prev = state.results.campaign;
    const suggested = getSuggestedInput('campaign');
    const banner = renderContextBanner('campaign');
    return `
        <div class="panel-header">
            <div class="panel-badge">Campaign Intelligence</div>
            <h1 class="panel-title">Campaign Hub</h1>
            <p class="panel-subtitle">Generate complete campaign plans with messaging frameworks, channel strategies, content calendars, and creative briefs.</p>
        </div>

        ${banner}

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Campaign Objective</label>
                <textarea class="input-field" id="campaignInput" rows="4" placeholder="Example: Launch campaign for Alpha Architect — an AI options trading platform. Goal: acquire 500 paid subscribers in 90 days. Budget: $15K.">${suggested ? escapeHtml(suggested) : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runCampaign()">📣 Generate Campaign Plan</button>
        </div>

        <div id="campaignResults">${prev ? renderCampaignResults(prev) : ''}</div>
    `;
}

async function runCampaign() {
    const input = document.getElementById('campaignInput').value;
    if (!input.trim()) return showToast('Please describe a campaign objective', 'error');
    if (!state.lastQuery) state.lastQuery = input.trim();
    const data = await apiCall('campaigns', input, '📣 Building Campaign Plan...');
    if (data) {
        state.results.campaign = data;
        document.getElementById('campaignResults').innerHTML = renderCampaignResults(data);
    }
}

function renderCampaignResults(d) {
    let html = `<div class="result-section">`;

    // Campaign Header
    html += `<div class="card card-glow mb-24" style="text-align:center;padding:32px">`;
    html += `<div class="kpi-label mb-8">${escapeHtml(d.campaign_type)}</div>`;
    html += `<h2 style="font-family:'Outfit',sans-serif;font-size:28px;font-weight:800;color:var(--text-primary);margin-bottom:8px">${escapeHtml(d.campaign_name)}</h2>`;
    html += `<p class="text-dim">${escapeHtml(d.campaign_summary)}</p>`;
    html += `<div class="grid-2 mt-16" style="max-width:400px;margin-left:auto;margin-right:auto"><div><span class="text-mono text-accent">${escapeHtml(d.duration)}</span><br><span class="text-xs text-muted">Duration</span></div><div><span class="text-mono text-accent">${escapeHtml(d.budget_range)}</span><br><span class="text-xs text-muted">Budget</span></div></div>`;
    html += `</div>`;

    // Messaging Framework
    const msg = d.messaging_framework;
    if (msg) {
        html += `<div class="result-section-title mt-24"><span class="section-icon">💬</span> Messaging Framework</div>`;
        html += `<div class="card mb-24"><div class="callout" style="font-size:16px;font-weight:600;text-align:center">"${escapeHtml(msg.core_message)}"</div>`;
        html += `<div class="grid-2 mt-16"><div>${(msg.supporting_messages||[]).map(m=>`<p class="text-sm mb-8">✓ ${escapeHtml(m)}</p>`).join('')}</div>`;
        html += `<div><p class="text-sm"><strong>Primary CTA:</strong> ${escapeHtml(msg.cta_primary)}</p><p class="text-sm mt-8"><strong>Secondary CTA:</strong> ${escapeHtml(msg.cta_secondary)}</p></div></div></div>`;
    }

    // Channel Plan
    if (d.channel_plan?.length) {
        html += `<div class="result-section-title mt-24"><span class="section-icon">📡</span> Channel Plan</div>`;
        html += `<table class="data-table"><thead><tr><th>Channel</th><th>Role</th><th>Frequency</th><th>Budget</th></tr></thead><tbody>`;
        d.channel_plan.forEach(c => {
            html += `<tr><td><strong>${escapeHtml(c.channel)}</strong></td><td class="text-sm">${escapeHtml(c.role)}</td><td class="text-sm">${escapeHtml(c.frequency)}</td><td class="text-mono">${escapeHtml(c.budget_share)}</td></tr>`;
        });
        html += `</tbody></table>`;
    }

    // Content Calendar
    if (d.content_calendar?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">📅</span> Content Calendar</div>`;
        html += `<div class="timeline">`;
        d.content_calendar.forEach(week => {
            html += `<div class="timeline-item"><div class="timeline-phase">${escapeHtml(week.theme)}</div><div class="timeline-period">${escapeHtml(week.week)}</div>`;
            (week.deliverables || []).forEach(del => {
                html += `<div style="padding:8px 12px;background:rgba(0,0,0,0.2);border-radius:8px;margin-top:8px"><span class="tag tag-cyan">${escapeHtml(del.type)}</span> <span class="tag tag-blue">${escapeHtml(del.channel)}</span><p class="text-sm text-dim mt-8">${escapeHtml(del.description)}</p></div>`;
            });
            html += `</div>`;
        });
        html += `</div>`;
    }

    // Creative Brief
    const cb = d.creative_brief;
    if (cb) {
        html += `<div class="callout insight mt-24"><div class="callout-title">🎬 Creative Brief</div><p><strong>Concept:</strong> ${escapeHtml(cb.concept)}</p><p class="mt-8"><strong>Visual:</strong> ${escapeHtml(cb.visual_direction)}</p><p class="mt-8"><strong>Copy:</strong> ${escapeHtml(cb.copy_direction)}</p></div>`;
    }

    html += `</div>`;
    return html;
}

// ══════════════════════════════════════════════════════════
//  COMPETITIVE INTEL PANEL
// ══════════════════════════════════════════════════════════

function renderCompetitiveIntel() {
    const prev = state.results.competitive;
    const suggested = getSuggestedInput('competitive');
    const banner = renderContextBanner('competitive');
    return `
        <div class="panel-header">
            <div class="panel-badge">Strategic Intelligence</div>
            <h1 class="panel-title">Competitive Intel</h1>
            <p class="panel-subtitle">SWOT analysis, competitive matrix, moat assessment, and strategic positioning recommendations.</p>
        </div>

        ${banner}

        <div class="card mb-24">
            <div class="input-group">
                <label class="input-label">Describe the Company and Its Competitive Context</label>
                <textarea class="input-field" id="competitiveInput" rows="4" placeholder="Example: Antigravity-AI Meta App Factory — an AI venture studio engine that generates, deploys, and self-heals production apps.">${suggested ? escapeHtml(suggested) : ''}</textarea>
            </div>
            <button class="btn btn-primary" onclick="runCompetitiveAnalysis()">⚔️ Run Competitive Analysis</button>
        </div>

        <div id="competitiveResults">${prev ? renderCompetitiveResults(prev) : ''}</div>
    `;
}

async function runCompetitiveAnalysis() {
    const input = document.getElementById('competitiveInput').value;
    if (!input.trim()) return showToast('Please describe a competitive context', 'error');
    if (!state.lastQuery) state.lastQuery = input.trim();
    const data = await apiCall('competitive-analysis', input, '⚔️ Analyzing Competitive Landscape...');
    if (data) {
        state.results.competitive = data;
        document.getElementById('competitiveResults').innerHTML = renderCompetitiveResults(data);
    }
}

function renderCompetitiveResults(d) {
    let html = `<div class="result-section">`;

    html += `<div class="callout success"><div class="callout-title">📊 Analysis Summary</div>${escapeHtml(d.analysis_summary)}</div>`;

    // SWOT
    if (d.swot) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">🎯</span> SWOT Analysis</div>`;
        html += `<div class="swot-grid">`;

        ['strengths','weaknesses','opportunities','threats'].forEach(q => {
            const items = d.swot[q] || [];
            html += `<div class="swot-quadrant ${q}"><div class="swot-title">${q.charAt(0).toUpperCase() + q.slice(1)}</div>`;
            items.forEach(item => {
                html += `<div style="margin-bottom:12px;padding:8px 12px;background:rgba(0,0,0,0.2);border-radius:8px"><strong class="text-sm">${escapeHtml(item.factor)}</strong><p class="text-xs text-dim mt-8">${escapeHtml(item.description)}</p></div>`;
            });
            html += `</div>`;
        });

        html += `</div>`;
    }

    // Competitive Matrix
    if (d.competitive_matrix?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">⚔️</span> Competitive Matrix</div>`;
        html += `<table class="data-table"><thead><tr><th>Competitor</th><th>Category</th><th>Threat</th><th>Weakness to Exploit</th></tr></thead><tbody>`;
        d.competitive_matrix.forEach(c => {
            const catColor = { 'DIRECT': 'red', 'INDIRECT': 'yellow', 'POTENTIAL': 'blue' };
            html += `<tr><td><strong>${escapeHtml(c.competitor)}</strong><br><span class="text-xs text-dim">${escapeHtml(c.pricing)}</span></td><td><span class="tag tag-${catColor[c.category]||'blue'}">${escapeHtml(c.category)}</span></td><td>${severityTag(c.threat_level)}</td><td class="text-sm">${escapeHtml(c.weakness_to_exploit)}</td></tr>`;
        });
        html += `</tbody></table>`;
    }

    // Moat Analysis
    const moat = d.moat_analysis;
    if (moat) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">🏰</span> Moat Analysis</div>`;
        html += `<div class="card"><div class="grid-3 mb-16"><div class="text-center"><div class="kpi-value ${moat.moat_strength==='STRONG'?'green':moat.moat_strength==='MODERATE'?'orange':'red'}" style="font-size:24px">${escapeHtml(moat.moat_strength)}</div><div class="kpi-label">Moat Strength</div></div><div class="text-center"><div class="kpi-value purple" style="font-size:16px">${escapeHtml(moat.moat_type)}</div><div class="kpi-label">Moat Type</div></div><div class="text-center"><div class="kpi-value cyan" style="font-size:16px">${escapeHtml(moat.time_to_replicate)}</div><div class="kpi-label">Time to Replicate</div></div></div>`;
        html += `<p class="text-sm text-dim">${escapeHtml(moat.description)}</p>`;
        if (moat.moat_builders?.length) {
            html += `<div class="mt-16"><h4 class="text-xs text-dim mb-8" style="text-transform:uppercase;letter-spacing:1px">Moat Builders</h4>${moat.moat_builders.map(b=>`<p class="text-sm mb-8" style="color:var(--green)">↑ ${escapeHtml(b)}</p>`).join('')}</div>`;
        }
        html += `</div>`;
    }

    // Strategy
    if (d.strategic_recommendations?.length) {
        html += `<div class="result-section-title mt-32"><span class="section-icon">🎯</span> Strategic Recommendations</div>`;
        d.strategic_recommendations.forEach(r => {
            html += `<div class="card mb-16"><div class="flex justify-between items-center mb-8"><strong>#${r.priority} ${escapeHtml(r.recommendation)}</strong><div>${severityTag(r.expected_impact)} <span class="tag tag-${r.effort==='HIGH'?'red':'green'}">Effort: ${escapeHtml(r.effort)}</span></div></div><p class="text-sm text-dim">${escapeHtml(r.rationale)}</p></div>`;
        });
    }

    html += `</div>`;
    return html;
}

// ══════════════════════════════════════════════════════════
//  PROJECT PORTFOLIO
// ══════════════════════════════════════════════════════════

const ENGINE_LABELS = {
    'market_research': { icon: '🔍', label: 'Market Research' },
    'brand_studio': { icon: '🎨', label: 'Brand Studio' },
    'brand_critique': { icon: '🧑‍🎨', label: 'Brand Critique' },
    'brand_refinement': { icon: '🔄', label: 'Brand Refinement' },
    'gtm_plan': { icon: '🚀', label: 'GTM Plan' },
    'personas': { icon: '👥', label: 'Personas' },
    'campaign': { icon: '📣', label: 'Campaign' },
    'competitive_analysis': { icon: '⚔️', label: 'Competitive Intel' },
};

function renderProjects() {
    return `
        <div class="engine-badge" style="--badge-color: var(--purple)">📁 PROJECT PORTFOLIO</div>
        <h1 class="panel-title">Your Projects</h1>
        <p class="text-dim mb-24">All your marketing intelligence projects — organized, persistent, and ready to revisit.</p>

        <div style="display:flex; gap:16px; margin-bottom:32px; align-items:center">
            <button class="btn-glow" onclick="showNewProjectModal()">➕ New Project</button>
            <span class="text-sm text-dim" id="projectCounter">Loading projects...</span>
        </div>

        <div id="projectsGrid" class="projects-grid">
            <div class="projects-loading">
                <div class="visual-spinner"></div>
                <p class="text-dim mt-16">Loading project portfolio...</p>
            </div>
        </div>
    `;
}

async function loadProjects() {
    try {
        const r = await fetch(`${API}/projects`);
        const projects = await r.json();
        const grid = document.getElementById('projectsGrid');
        const counter = document.getElementById('projectCounter');

        if (!projects.length) {
            grid.innerHTML = `
                <div class="card" style="text-align:center; padding:48px; grid-column: 1/-1">
                    <p style="font-size:48px; margin-bottom:16px">📁</p>
                    <h3>No Projects Yet</h3>
                    <p class="text-dim mt-8">Run any engine (Market Research, Brand Studio, etc.) to auto-create your first project, or click "New Project" above.</p>
                </div>
            `;
            counter.textContent = '0 projects';
            return;
        }

        counter.textContent = `${projects.length} project${projects.length > 1 ? 's' : ''}`;

        grid.innerHTML = projects.map(p => {
            const engines = (p.engines_used || []).map(e => {
                const info = ENGINE_LABELS[e] || { icon: '⚙️', label: e };
                return `<span class="engine-pill" title="${info.label}">${info.icon}</span>`;
            }).join('');

            const isActive = p.name === state.projectName;
            const updated = p.updated_at ? new Date(p.updated_at + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A';

            return `
                <div class="project-card ${isActive ? 'project-card-active' : ''}" onclick="openProjectDetail('${p.name}')">
                    <div class="project-card-header">
                        <div>
                            <h3 class="project-card-title">${escapeHtml(p.display_name || p.name)}</h3>
                            ${p.brand_name ? `<span class="project-brand-tag">🏷️ ${escapeHtml(p.brand_name)}</span>` : ''}
                        </div>
                        ${isActive ? '<span class="tag tag-green" style="font-size:10px">ACTIVE</span>' : ''}
                    </div>
                    <p class="project-card-desc">${escapeHtml(p.description || 'No description')}</p>
                    <div class="project-card-stats">
                        <span class="project-stat">📊 ${p.analysis_count || 0} analyses</span>
                        <span class="project-stat">👥 ${p.persona_count || 0} personas</span>
                        <span class="project-stat">📣 ${p.campaign_count || 0} campaigns</span>
                    </div>
                    <div class="project-card-footer">
                        <div class="project-engines">${engines || '<span class="text-dim text-sm">No engines run</span>'}</div>
                        <span class="text-sm text-dim">${updated}</span>
                    </div>
                    <div class="project-card-actions">
                        <button class="btn-sm btn-primary" onclick="event.stopPropagation(); switchProject('${p.name}', '${escapeHtml(p.display_name || p.name)}')">Open</button>
                        <button class="btn-sm btn-ghost" onclick="event.stopPropagation(); duplicateProject('${p.name}')">Duplicate</button>
                        <button class="btn-sm btn-ghost" onclick="event.stopPropagation(); archiveProject('${p.name}')">Archive</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        const grid = document.getElementById('projectsGrid');
        if (grid) grid.innerHTML = `<div class="card" style="padding:24px"><p class="text-dim">Failed to load projects: ${err.message}</p></div>`;
    }
}


// ── Project Detail View ────────────────────────────────────

async function openProjectDetail(projectName) {
    const container = document.getElementById('panel-container');
    container.innerHTML = `
        <div class="panel active">
            <div class="engine-badge" style="--badge-color: var(--cyan)">📋 PROJECT DETAIL</div>
            <div id="projectDetailContent">
                <div style="text-align:center; padding:48px">
                    <div class="visual-spinner"></div>
                    <p class="text-dim mt-16">Loading project detail...</p>
                </div>
            </div>
        </div>
    `;

    try {
        const r = await fetch(`${API}/projects/${projectName}`);
        const detail = await r.json();
        const el = document.getElementById('projectDetailContent');
        if (!detail || detail.error) {
            el.innerHTML = `<p class="text-dim">Project not found.</p>`;
            return;
        }

        const history = detail.history || [];
        const brand = detail.brand;

        let html = `
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:32px">
                <div>
                    <h1 class="panel-title">${escapeHtml(detail.display_name || detail.name)}</h1>
                    <p class="text-dim">${escapeHtml(detail.description || '')} &mdash; Created ${new Date(detail.created_at + 'Z').toLocaleDateString()}</p>
                </div>
                <div style="display:flex; gap:8px">
                    <button class="btn-sm btn-primary" onclick="switchProject('${detail.name}', '${escapeHtml(detail.display_name || detail.name)}')">🎯 Set as Active</button>
                    <button class="btn-sm btn-ghost" onclick="navigateTo('projects')">← Back</button>
                </div>
            </div>
        `;

        // Brand summary card if exists
        if (brand && brand.full_identity) {
            const bi = brand.full_identity;
            html += `
                <div class="card mb-24" style="border-left:3px solid var(--purple)">
                    <h3>🏷️ Active Brand: ${escapeHtml(bi.company_name || 'Unnamed')}</h3>
                    <p class="text-dim mt-4">"${escapeHtml(bi.tagline || '')}"</p>
                </div>
            `;
        }

        // Timeline
        html += `<h2 style="margin-bottom:16px">📜 Activity Timeline (${history.length} entries)</h2>`;
        if (history.length === 0) {
            html += `<p class="text-dim">No engine runs yet for this project.</p>`;
        } else {
            html += `<div class="project-timeline">`;
            history.forEach(entry => {
                const info = ENGINE_LABELS[entry.module] || { icon: '⚙️', label: entry.module };
                const time = new Date(entry.created_at + 'Z').toLocaleString();
                const summary = entry.input_summary || '';
                html += `
                    <div class="timeline-entry">
                        <div class="timeline-dot">${info.icon}</div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <strong>${info.label}</strong>
                                <span class="text-sm text-dim">${time}</span>
                            </div>
                            <p class="text-sm text-dim mt-4">${escapeHtml(summary)}</p>
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        el.innerHTML = html;
    } catch (err) {
        document.getElementById('projectDetailContent').innerHTML =
            `<p class="text-dim">Error loading project: ${err.message}</p>`;
    }
}


// ── Project Switcher ───────────────────────────────────────

async function loadProjectSwitcher() {
    const select = document.getElementById('projectSwitcher');
    if (!select) return;

    try {
        const r = await fetch(`${API}/projects`);
        const projects = await r.json();

        select.innerHTML = projects.length
            ? projects.map(p => `<option value="${p.name}" ${p.name === state.projectName ? 'selected' : ''}>${escapeHtml(p.display_name || p.name)}</option>`).join('')
            : `<option value="default">Default Project</option>`;

        select.onchange = () => {
            const name = select.value;
            const display = select.options[select.selectedIndex]?.text || name;
            switchProject(name, display);
        };
    } catch {
        // Keep default
    }
}

function switchProject(name, displayName) {
    state.projectName = name;
    state.results = {};   // Clear session results for clean slate
    state.brandVisual = null;
    state.brandCritique = null;

    // Update switcher
    const select = document.getElementById('projectSwitcher');
    if (select) {
        for (const opt of select.options) {
            if (opt.value === name) { opt.selected = true; break; }
        }
    }

    // Navigate to dashboard for this project
    navigateTo('dashboard');
}


// ── New Project Modal ──────────────────────────────────────

function showNewProjectModal() {
    // Remove existing modal if any
    const existing = document.getElementById('newProjectModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'newProjectModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-card">
            <h2 style="margin-bottom:20px">➕ New Project</h2>
            <div class="form-group mb-16">
                <label class="form-label">PROJECT NAME</label>
                <input type="text" class="form-input" id="newProjectName" placeholder="e.g., Chocolate Fruit Brand" autofocus />
            </div>
            <div class="form-group mb-24">
                <label class="form-label">DESCRIPTION (OPTIONAL)</label>
                <textarea class="form-input" id="newProjectDesc" rows="3" placeholder="Brief description of this project..."></textarea>
            </div>
            <div style="display:flex; gap:12px; justify-content:flex-end">
                <button class="btn-sm btn-ghost" onclick="document.getElementById('newProjectModal').remove()">Cancel</button>
                <button class="btn-glow" onclick="createNewProject()">Create Project</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    document.getElementById('newProjectName').focus();
}

async function createNewProject() {
    const name = document.getElementById('newProjectName')?.value?.trim();
    const desc = document.getElementById('newProjectDesc')?.value?.trim();

    if (!name) { alert('Please enter a project name.'); return; }

    try {
        const r = await fetch(`${API}/projects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc })
        });
        const project = await r.json();

        if (project.error) { alert(project.error); return; }

        // Close modal
        document.getElementById('newProjectModal')?.remove();

        // Switch to new project
        switchProject(project.name, project.display_name);

        // Reload switcher
        loadProjectSwitcher();
    } catch (err) {
        alert('Failed to create project: ' + err.message);
    }
}

async function archiveProject(name) {
    if (!confirm(`Archive project "${name}"? You can restore it later.`)) return;

    try {
        await fetch(`${API}/projects/${name}`, { method: 'DELETE' });
        // Reload if we're on the projects page
        if (state.activePanel === 'projects') loadProjects();
        loadProjectSwitcher();
    } catch (err) {
        alert('Failed to archive: ' + err.message);
    }
}

async function duplicateProject(name) {
    const newName = prompt('Name for the duplicated project (leave blank for auto):', '');
    if (newName === null) return;  // User cancelled

    try {
        const r = await fetch(`${API}/projects/${name}/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: newName || '' })
        });
        const project = await r.json();
        if (project.error) { alert(project.error); return; }

        // Reload projects & switcher
        if (state.activePanel === 'projects') loadProjects();
        loadProjectSwitcher();
    } catch (err) {
        alert('Failed to duplicate: ' + err.message);
    }
}
