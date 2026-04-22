// ══════════════════════════════════════════════════════
// Venture Architect Agent — Core UI Logic
// ══════════════════════════════════════════════════════

// State
let state = {
    activeProject: "default",
    activePanel: "dashboard",
    results: {
        business_model: null,
        unit_economics: null,
        financials: null,
        pitch_deck: null,
        cap_table: null,
        valuation: null,
        gtm_budget: null,
        scenarios: null
    }
};

const API_BASE = "http://localhost:5110/api";

// ── DOM Elements ──
const els = {
    navButtons: document.querySelectorAll('.nav-item'),
    panelContainer: document.getElementById('panel-container'),
    projectSwitcher: document.getElementById('projectSwitcher'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    toastContainer: document.getElementById('toastContainer')
};

// ── Initialization ──
document.addEventListener('DOMContentLoaded', async () => {
    await fetchProjects();
    await switchProject("default");
    
    // Bind Nav
    els.navButtons.forEach(btn => {
        btn.addEventListener('click', () => switchPanel(btn.dataset.panel));
    });

    // Bind Project Switcher
    els.projectSwitcher.addEventListener('change', (e) => switchProject(e.target.value));

    // Initial render
    switchPanel('dashboard');
});

// ── API & State ──
async function fetchProjects() {
    try {
        const res = await fetch(`${API_BASE}/projects`);
        const data = await res.json();
        const projects = data.projects || [];
        
        els.projectSwitcher.innerHTML = '';
        projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.textContent = p;
            els.projectSwitcher.appendChild(opt);
        });
        if (!projects.includes("default")) {
            const opt = document.createElement('option');
            opt.value = "default";
            opt.textContent = "Default Project";
            els.projectSwitcher.appendChild(opt);
        }
    } catch (e) {
        showToast("Error loading projects", "error");
    }
}

async function switchProject(projectName) {
    state.activeProject = projectName;
    els.projectSwitcher.value = projectName;
    
    try {
        const res = await fetch(`${API_BASE}/state/${projectName}`);
        const data = await res.json();
        
        state.results.business_model = data.business_model || null;
        state.results.unit_economics = data.unit_economics || null;
        state.results.financials = data.financials || null;
        state.results.pitch_deck = data.pitch_deck || null;
        state.results.cap_table = data.cap_table || null;
        state.results.valuation = data.valuation || null;
        state.results.gtm_budget = data.gtm_budget || null;
        state.results.scenarios = data.scenarios || null;
        
        renderCurrentPanel();
        showToast(`Loaded project: ${projectName}`, "success");
    } catch (e) {
        showToast("Error loading state", "error");
    }
}

// ── UI Routing ──
function switchPanel(panelId) {
    state.activePanel = panelId;
    els.navButtons.forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-panel="${panelId}"]`).classList.add('active');
    renderCurrentPanel();
}

function renderCurrentPanel() {
    const p = state.activePanel;
    els.panelContainer.innerHTML = ''; // clear

    if (p === 'dashboard') renderDashboard();
    else if (p === 'business-model') renderBusinessModel();
    else if (p === 'unit-economics') renderUnitEconomics();
    else if (p === 'financials') renderFinancials();
    else if (p === 'pitch-deck') renderPitchDeck();
    else if (p === 'cap-table') renderCapTable();
    else if (p === 'valuation') renderValuation();
    else if (p === 'gtm-budget') renderGtmBudget();
    else if (p === 'scenarios') renderScenarios();
    else els.panelContainer.innerHTML = `<h2>Coming Soon</h2><p>The ${p} panel is under construction.</p>`;
}

// ── Generators ──
async function triggerGeneration(endpoint, key, inputPrompt) {
    showLoading();
    try {
        const res = await fetch(`${API_BASE}/generate/${endpoint}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                project_name: state.activeProject,
                user_input: inputPrompt
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        state.results[key] = data;
        renderCurrentPanel();
        showToast("Generation complete!", "success");
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        hideLoading();
    }
}

// ── Render Functions ──
function renderDashboard() {
    const html = `
        <div class="header-section">
            <h1 class="page-title">Venture Architect Dashboard</h1>
            <p class="page-description">Master view for project ${state.activeProject}</p>
        </div>
        <div class="grid-2">
            <div class="card">
                <h3>Business Model</h3>
                <p>${state.results.business_model ? '✅ Complete' : '❌ Pending'}</p>
                <button class="btn-primary" onclick="switchPanel('business-model')">View</button>
            </div>
            <div class="card">
                <h3>Financials</h3>
                <p>${state.results.financials ? '✅ Complete' : '❌ Pending'}</p>
                <button class="btn-primary" onclick="switchPanel('financials')">View</button>
            </div>
            <div class="card">
                <h3>Cap Table</h3>
                <p>${state.results.cap_table ? '✅ Complete' : '❌ Pending'}</p>
                <button class="btn-primary" onclick="switchPanel('cap-table')">View</button>
            </div>
            <div class="card">
                <h3>Valuation</h3>
                <p>${state.results.valuation ? '✅ Complete' : '❌ Pending'}</p>
                <button class="btn-primary" onclick="switchPanel('valuation')">View</button>
            </div>
        </div>
    `;
    els.panelContainer.innerHTML = html;
}

function renderBusinessModel() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Business Model Canvas</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Describe the business concept..."></textarea>
                <button class="btn-primary" onclick="triggerGeneration('business-model', 'business_model', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;

    const data = state.results.business_model;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderUnitEconomics() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Unit Economics</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Any specific pricing data to consider?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('unit-economics', 'unit_economics', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.unit_economics;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderFinancials() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">5-Year Financials</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Any CapEx or OpEx details?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('financials', 'financials', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.financials;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderPitchDeck() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Pitch Deck Generator</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Targeting a specific investor archetype?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('pitch-deck', 'pitch_deck', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.pitch_deck;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

// ── Utils ──
function showLoading() {
    els.loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
    els.loadingOverlay.classList.add('hidden');
}

function showToast(message, type="info") {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    els.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function renderCapTable() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Cap Table Simulator</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Any specific founder splits or ESOP targets?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('cap-table', 'cap_table', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.cap_table;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderValuation() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Valuation & Exit Modeling</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Any preferred valuation methodologies?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('valuation', 'valuation', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.valuation;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderGtmBudget() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">GTM Capital Allocator</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Total available capital for GTM?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('gtm-budget', 'gtm_budget', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.gtm_budget;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}

function renderScenarios() {
    let html = `
        <div class="header-section">
            <h1 class="page-title">Scenario & Sensitivity Modeling</h1>
            <div class="input-group">
                <textarea id="promptInput" class="custom-input" placeholder="Which variables should we stress-test?"></textarea>
                <button class="btn-primary" onclick="triggerGeneration('scenarios', 'scenarios', document.getElementById('promptInput').value)">✨ Auto-Generate</button>
            </div>
        </div>
    `;
    const data = state.results.scenarios;
    if (data) {
        html += `<div class="card"><pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 13px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    }
    els.panelContainer.innerHTML = html;
}
