/**
 * IP_SOP_Modal.jsx — One-Click IP SOP Modal
 * ==========================================
 * Meta App Factory | Antigravity-AI
 *
 * Rendered when the URL contains ?view=sop (e.g., tapping an ntfy deep-link).
 * Reads app_name + score from URL params, fetches LEDGER data for claims.pdf,
 * and presents the 5-step IP Standard Operating Procedure.
 *
 * Steps:
 *   1. 🔍 Triage       — Review IP evaluation score
 *   2. 📋 Review Claims — Open generated claims.pdf
 *   3. ⚖️ Conflict Check — Run API conflict scan
 *   4. 🚀 Execute       — Initiate USPTO filing
 *   5. 📁 Archive       — Confirm LEDGER.md logged
 */

import { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000';

// ── SOP Step Definitions ───────────────────────────

const SOP_STEPS = [
    {
        id: 1,
        icon: '🔍',
        label: 'Triage',
        description: 'Review the IP evaluation report and confirm confidence score meets filing threshold (>70%).',
        action: null,
    },
    {
        id: 2,
        icon: '📋',
        label: 'Review Claims',
        description: 'Open the auto-generated patent claims document produced by the USPTO Drafting Engine.',
        action: 'claims',
    },
    {
        id: 3,
        icon: '⚖️',
        label: 'Conflict Check',
        description: 'Cross-reference against MASTER_INDEX.md to confirm no internal IP duplication.',
        action: 'conflict',
    },
    {
        id: 4,
        icon: '🚀',
        label: 'Execute Filing',
        description: 'Initiate Automated Filing Portal — generates USPTO-ready draft and logs to LEDGER.md.',
        action: 'filing',
    },
    {
        id: 5,
        icon: '📁',
        label: 'Archive',
        description: 'Confirm audit log entry is recorded in LEDGER.md under SECURITY_INTERCEPTIONS.',
        action: 'archive',
    },
];

// ── Main Modal Component ───────────────────────────

export default function IP_SOP_Modal({ onClose }) {
    // Read URL params — set when navigating from ntfy deep-link
    const params = new URLSearchParams(window.location.search);
    const appName = params.get('app') || 'Unknown App';
    const score = parseInt(params.get('score') || '0', 10);

    const [activeStep, setActiveStep] = useState(1);
    const [completedSteps, setCompletedSteps] = useState(new Set());
    const [claimsUrl, setClaimsUrl] = useState(null);
    const [conflictResult, setConflictResult] = useState(null);
    const [filingResult, setFilingResult] = useState(null);
    const [loading, setLoading] = useState('');
    const [ledgerEntry, setLedgerEntry] = useState(null);

    // Fetch LEDGER entries to find claims.pdf for this app
    useEffect(() => {
        fetch(`${API_BASE}/api/ip/ledger`)
            .then(r => r.json())
            .then(data => {
                const entries = data.entries || [];
                const match = entries.find(e =>
                    e.app_name?.toLowerCase() === appName.toLowerCase() ||
                    e.app?.toLowerCase() === appName.toLowerCase()
                );
                if (match) {
                    setLedgerEntry(match);
                    // Try to extract claims PDF path
                    const claimsPath = match.claims_file || match.files?.find(f => f.endsWith('.pdf'));
                    if (claimsPath) setClaimsUrl(claimsPath);
                }
            })
            .catch(() => {
                // Non-critical — continue without ledger data
            });
    }, [appName]);

    const markComplete = (stepId) => {
        setCompletedSteps(prev => new Set([...prev, stepId]));
        if (stepId < SOP_STEPS.length) setActiveStep(stepId + 1);
    };

    const handleConflictCheck = async () => {
        setLoading('conflict');
        try {
            const res = await fetch(`${API_BASE}/api/ip/conflicts?app_name=${encodeURIComponent(appName)}`);
            const data = await res.json();
            setConflictResult(data);
            markComplete(3);
        } catch {
            setConflictResult({ error: 'Conflict check failed — API unreachable' });
        } finally {
            setLoading('');
        }
    };

    const handleFiling = async () => {
        setLoading('filing');
        try {
            const res = await fetch(`${API_BASE}/api/ip/filing`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ app_name: appName, confidence_score: score / 100 }),
            });
            const data = await res.json();
            setFilingResult(data);
            markComplete(4);
        } catch {
            setFilingResult({ error: 'Filing API unreachable — try again when factory is running' });
        } finally {
            setLoading('');
        }
    };

    const handleArchive = () => {
        // Archive is confirmed by the LEDGER.md entry already written by leak_monitor
        markComplete(5);
    };

    const allComplete = completedSteps.size === SOP_STEPS.length;

    return (
        <div className="sop-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="sop-modal">

                {/* ── Header ── */}
                <div className="sop-header">
                    <div className="sop-header-left">
                        <span className="sop-shield">🛡️</span>
                        <div>
                            <h2 className="sop-title">IP Shield — Standard Operating Procedure</h2>
                            <p className="sop-subtitle">
                                <strong>{appName}</strong>
                                <span className="sop-score-badge" style={{ background: score >= 80 ? '#0d4d0d' : '#4d4d00', color: score >= 80 ? '#4cff4c' : '#ffff4c' }}>
                                    {score}% confidence
                                </span>
                            </p>
                        </div>
                    </div>
                    <button className="sop-close" onClick={onClose} title="Close">✕</button>
                </div>

                {/* ── Progress Bar ── */}
                <div className="sop-progress">
                    <div
                        className="sop-progress-fill"
                        style={{ width: `${(completedSteps.size / SOP_STEPS.length) * 100}%` }}
                    />
                </div>
                <p className="sop-progress-label">
                    {completedSteps.size}/{SOP_STEPS.length} steps complete
                    {allComplete && ' — Filing workflow done! ✅'}
                </p>

                {/* ── Step List ── */}
                <div className="sop-steps">
                    {SOP_STEPS.map(step => {
                        const isDone = completedSteps.has(step.id);
                        const isActive = step.id === activeStep;

                        return (
                            <div
                                key={step.id}
                                className={`sop-step ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
                                onClick={() => !isDone && setActiveStep(step.id)}
                            >
                                {/* Step number / check */}
                                <div className="sop-step-num">
                                    {isDone ? '✅' : <span>{step.id}</span>}
                                </div>

                                <div className="sop-step-content">
                                    <div className="sop-step-label">
                                        {step.icon} {step.label}
                                    </div>
                                    <div className="sop-step-desc">{step.description}</div>

                                    {/* Step-specific inline action */}
                                    {isActive && !isDone && (
                                        <div className="sop-step-actions">

                                            {/* Step 1: Triage — just review the score */}
                                            {step.id === 1 && (
                                                <div className="sop-triage-card">
                                                    <div className="triage-row">
                                                        <span>Application</span>
                                                        <strong>{appName}</strong>
                                                    </div>
                                                    <div className="triage-row">
                                                        <span>Confidence Score</span>
                                                        <strong style={{ color: score >= 80 ? '#4cff4c' : '#ffff4c' }}>{score}%</strong>
                                                    </div>
                                                    <div className="triage-row">
                                                        <span>Threshold</span>
                                                        <strong>70% (filing) / 80% (alert)</strong>
                                                    </div>
                                                    <div className="triage-row">
                                                        <span>Status</span>
                                                        <strong style={{ color: '#4cff4c' }}>
                                                            {score >= 70 ? '✅ Eligible for filing' : '⚠️ Below threshold'}
                                                        </strong>
                                                    </div>
                                                    <button className="sop-btn primary" onClick={() => markComplete(1)}>
                                                        ✅ Triage Complete
                                                    </button>
                                                </div>
                                            )}

                                            {/* Step 2: Review Claims PDF */}
                                            {step.id === 2 && (
                                                <div className="sop-claims-card">
                                                    {claimsUrl ? (
                                                        <>
                                                            <p className="sop-claims-found">Claims document found in LEDGER</p>
                                                            <a
                                                                href={claimsUrl}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="sop-btn primary"
                                                                onClick={() => setTimeout(() => markComplete(2), 500)}
                                                            >
                                                                📄 Open claims.pdf
                                                            </a>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <p className="sop-claims-missing">
                                                                No claims PDF found — generate one using the USPTO Drafting Engine.
                                                            </p>
                                                            <button
                                                                className="sop-btn secondary"
                                                                onClick={async () => {
                                                                    setLoading('claims');
                                                                    try {
                                                                        const res = await fetch(
                                                                            `${API_BASE}/api/ip/claims?app_name=${encodeURIComponent(appName)}`,
                                                                            { method: 'POST' }
                                                                        );
                                                                        const data = await res.json();
                                                                        if (data.claims_file) setClaimsUrl(data.claims_file);
                                                                        markComplete(2);
                                                                    } catch {
                                                                        markComplete(2); // Non-blocking
                                                                    } finally {
                                                                        setLoading('');
                                                                    }
                                                                }}
                                                                disabled={loading === 'claims'}
                                                            >
                                                                {loading === 'claims' ? '⏳ Generating...' : '📝 Generate Claims Draft'}
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            )}

                                            {/* Step 3: Conflict Check */}
                                            {step.id === 3 && (
                                                <div className="sop-conflict-card">
                                                    {conflictResult ? (
                                                        <div className={`conflict-result ${conflictResult.error ? 'error' : 'ok'}`}>
                                                            {conflictResult.error ? (
                                                                <p>⚠️ {conflictResult.error}</p>
                                                            ) : (
                                                                <>
                                                                    <p>✅ Conflict check complete</p>
                                                                    <p>Conflicts found: <strong>{conflictResult.conflicts?.length ?? 0}</strong></p>
                                                                    {conflictResult.conflicts?.length > 0 && (
                                                                        <ul>
                                                                            {conflictResult.conflicts.map((c, i) => (
                                                                                <li key={i}>{c}</li>
                                                                            ))}
                                                                        </ul>
                                                                    )}
                                                                </>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <button
                                                            className="sop-btn primary"
                                                            onClick={handleConflictCheck}
                                                            disabled={loading === 'conflict'}
                                                        >
                                                            {loading === 'conflict' ? '⏳ Scanning...' : '⚖️ Run Conflict Check'}
                                                        </button>
                                                    )}
                                                </div>
                                            )}

                                            {/* Step 4: Execute Filing */}
                                            {step.id === 4 && (
                                                <div className="sop-filing-card">
                                                    {filingResult ? (
                                                        <div className={`filing-result ${filingResult.error ? 'error' : 'ok'}`}>
                                                            {filingResult.error ? (
                                                                <p>⚠️ {filingResult.error}</p>
                                                            ) : (
                                                                <>
                                                                    <p>✅ Filing initiated</p>
                                                                    <p>Draft: <strong>{filingResult.draft_file || 'Generated'}</strong></p>
                                                                    <p>LEDGER logged: <strong>{filingResult.ledger_logged ? 'Yes' : 'Pending'}</strong></p>
                                                                </>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <>
                                                            <p className="sop-warning">
                                                                ⚠️ This will initiate a USPTO filing draft for <strong>{appName}</strong>.
                                                            </p>
                                                            <button
                                                                className="sop-btn danger"
                                                                onClick={handleFiling}
                                                                disabled={loading === 'filing'}
                                                            >
                                                                {loading === 'filing' ? '⏳ Filing...' : '🚀 Initiate Filing'}
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            )}

                                            {/* Step 5: Archive */}
                                            {step.id === 5 && (
                                                <div className="sop-archive-card">
                                                    <div className="triage-row">
                                                        <span>LEDGER Entry</span>
                                                        <strong style={{ color: ledgerEntry ? '#4cff4c' : '#ffff4c' }}>
                                                            {ledgerEntry ? '✅ Found' : '⏳ Check LEDGER.md manually'}
                                                        </strong>
                                                    </div>
                                                    {ledgerEntry && (
                                                        <div className="ledger-preview">
                                                            <p>Last action: {ledgerEntry.action || 'IP_MILESTONE'}</p>
                                                            <p>App: {ledgerEntry.app_name || appName}</p>
                                                        </div>
                                                    )}
                                                    <button className="sop-btn primary" onClick={handleArchive}>
                                                        📁 Confirm Archive
                                                    </button>
                                                </div>
                                            )}

                                        </div>
                                    )}

                                    {/* Done state */}
                                    {isDone && (
                                        <div className="sop-step-done-label">✅ Complete</div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* ── Footer ── */}
                <div className="sop-footer">
                    {allComplete ? (
                        <div className="sop-complete-banner">
                            🎉 All steps complete. IP Shield workflow archived.
                        </div>
                    ) : (
                        <p className="sop-footer-hint">
                            Deep-link: <code>{window.location.href}</code>
                        </p>
                    )}
                    <button className="sop-btn secondary" onClick={onClose}>
                        Close
                    </button>
                </div>

            </div>
        </div>
    );
}
