import { useState, useEffect, useCallback } from 'react'

const API = 'http://localhost:5007'

function App() {
    const [health, setHealth] = useState(null)
    const [alerts, setAlerts] = useState([])
    const [agreements, setAgreements] = useState([])
    const [auditLog, setAuditLog] = useState([])
    const [activeTab, setActiveTab] = useState('dashboard')
    const [loading, setLoading] = useState(true)

    // ── Fetch all data ──
    const refresh = useCallback(async () => {
        try {
            const [hRes, aRes, agRes, auRes] = await Promise.all([
                fetch(`${API}/health`),
                fetch(`${API}/alerts?status=all`),
                fetch(`${API}/vault/list`),
                fetch(`${API}/audit?limit=30`),
            ])
            setHealth(await hRes.json())
            const alertData = await aRes.json()
            setAlerts(alertData.alerts || [])
            const agData = await agRes.json()
            setAgreements(agData.agreements || [])
            const auData = await auRes.json()
            setAuditLog(auData.entries || [])
        } catch (e) {
            console.error('Fetch error:', e)
        }
        setLoading(false)
    }, [])

    useEffect(() => {
        refresh()
        const id = setInterval(refresh, 10000)
        return () => clearInterval(id)
    }, [refresh])

    // ── Dismiss alert ──
    const dismissAlert = async (alertId) => {
        await fetch(`${API}/alerts/dismiss`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ alert_id: alertId, dismissed_by: 'operator' }),
        })
        refresh()
    }

    // ── Escalate alerts ──
    const escalateAlerts = async () => {
        await fetch(`${API}/alerts/escalate`, { method: 'POST' })
        refresh()
    }

    const activeAlerts = alerts.filter(a => a.status === 'active')
    const criticalAlerts = activeAlerts.filter(a => a.box >= 4)

    const boxColor = (box) => {
        if (box >= 5) return '#ef4444'
        if (box >= 4) return '#f59e0b'
        if (box >= 3) return '#fb923c'
        if (box >= 2) return '#6366f1'
        return '#94a3b8'
    }

    if (loading) return (
        <div style={styles.loadingScreen}>
            <div style={styles.loadingSpinner} />
            <p style={{ color: '#94a3b8', marginTop: 20 }}>Initializing Vault Security Dashboard...</p>
        </div>
    )

    return (
        <div style={styles.app}>
            {/* Header */}
            <header style={styles.header}>
                <div style={styles.headerLeft}>
                    <span style={styles.shield}>🛡️</span>
                    <div>
                        <h1 style={styles.title}>Delegate AI — Agreement Vault</h1>
                        <p style={styles.subtitle}>Real-Time Security Dashboard • DAI-2026-A1F3E7</p>
                    </div>
                </div>
                <div style={styles.headerRight}>
                    <span style={{
                        ...styles.statusBadge,
                        background: health?.status === 'healthy' ? '#10b981' : '#f59e0b'
                    }}>
                        {health?.status === 'healthy' ? '● SECURE' : '⚠ WARNING'}
                    </span>
                    <span style={styles.encBadge}>🔐 {health?.encryption || 'AES-128'}</span>
                </div>
            </header>

            {/* Stats Bar */}
            <div style={styles.statsBar}>
                <div style={styles.stat}>
                    <span style={styles.statValue}>{health?.agreements_stored || 0}</span>
                    <span style={styles.statLabel}>Agreements</span>
                </div>
                <div style={styles.stat}>
                    <span style={{ ...styles.statValue, color: activeAlerts.length > 0 ? '#f59e0b' : '#10b981' }}>
                        {activeAlerts.length}
                    </span>
                    <span style={styles.statLabel}>Active Alerts</span>
                </div>
                <div style={styles.stat}>
                    <span style={{ ...styles.statValue, color: criticalAlerts.length > 0 ? '#ef4444' : '#10b981' }}>
                        {criticalAlerts.length}
                    </span>
                    <span style={styles.statLabel}>Critical (Box 4-5)</span>
                </div>
                <div style={styles.stat}>
                    <span style={styles.statValue}>{auditLog.length}</span>
                    <span style={styles.statLabel}>Audit Entries</span>
                </div>
            </div>

            {/* Tabs */}
            <div style={styles.tabs}>
                {['dashboard', 'alerts', 'agreements', 'audit'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            ...styles.tab,
                            ...(activeTab === tab ? styles.tabActive : {}),
                        }}
                    >
                        {tab === 'dashboard' && '📊 '}
                        {tab === 'alerts' && `🔔 `}
                        {tab === 'agreements' && '📄 '}
                        {tab === 'audit' && '📋 '}
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        {tab === 'alerts' && activeAlerts.length > 0 &&
                            <span style={styles.alertCount}>{activeAlerts.length}</span>}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={styles.content}>
                {activeTab === 'dashboard' && (
                    <div style={styles.grid}>
                        {/* Leitner Box Visualization */}
                        <div style={styles.card}>
                            <h3 style={styles.cardTitle}>🧠 Leitner Alert Boxes</h3>
                            <p style={styles.cardDesc}>Unresolved alerts escalate through 5 boxes. Higher = more urgent.</p>
                            <div style={styles.leitnerBoxes}>
                                {[1, 2, 3, 4, 5].map(box => {
                                    const count = activeAlerts.filter(a => a.box === box).length
                                    return (
                                        <div key={box} style={{
                                            ...styles.leitnerBox,
                                            borderColor: boxColor(box),
                                            background: count > 0 ? `${boxColor(box)}15` : 'transparent',
                                        }}>
                                            <span style={{ fontSize: 24, fontWeight: 700, color: boxColor(box) }}>{count}</span>
                                            <span style={{ fontSize: 11, color: '#94a3b8' }}>Box {box}</span>
                                        </div>
                                    )
                                })}
                            </div>
                            <button onClick={escalateAlerts} style={styles.escBtn}>
                                ⬆️ Trigger Escalation Cycle
                            </button>
                        </div>

                        {/* System Info */}
                        <div style={styles.card}>
                            <h3 style={styles.cardTitle}>⚙️ System Info</h3>
                            <div style={styles.infoGrid}>
                                <div style={styles.infoRow}><span>Encryption</span><span style={{ color: '#10b981' }}>{health?.encryption}</span></div>
                                <div style={styles.infoRow}><span>Project ID</span><span>{health?.project_id}</span></div>
                                <div style={styles.infoRow}><span>Port</span><span>{health?.port}</span></div>
                                <div style={styles.infoRow}><span>Version</span><span>{health?.version}</span></div>
                                <div style={styles.infoRow}><span>Leitner Max</span><span>Box {health?.leitner_max_box}</span></div>
                                <div style={styles.infoRow}><span>Last Check</span><span style={{ fontSize: 11 }}>{health?.timestamp}</span></div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'alerts' && (
                    <div>
                        {activeAlerts.length === 0 ? (
                            <div style={styles.empty}>✅ No active security alerts</div>
                        ) : (
                            activeAlerts.map(alert => (
                                <div key={alert.id} style={{
                                    ...styles.alertCard,
                                    borderLeft: `4px solid ${boxColor(alert.box)}`,
                                }}>
                                    <div style={styles.alertHeader}>
                                        <span style={{ ...styles.alertType, background: boxColor(alert.box) }}>
                                            Box {alert.box} • {alert.type}
                                        </span>
                                        <span style={styles.alertTime}>{alert.created}</span>
                                    </div>
                                    <p style={styles.alertDesc}>{alert.description}</p>
                                    <div style={styles.alertFooter}>
                                        <span style={{ fontSize: 11, color: '#64748b' }}>Source: {alert.source}</span>
                                        <button onClick={() => dismissAlert(alert.id)} style={styles.dismissBtn}>
                                            ✕ Dismiss
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}

                {activeTab === 'agreements' && (
                    <div>
                        {agreements.length === 0 ? (
                            <div style={styles.empty}>📄 No agreements stored yet</div>
                        ) : (
                            agreements.map(ag => (
                                <div key={ag.agreement_id} style={styles.agCard}>
                                    <div style={styles.agHeader}>
                                        <span style={styles.agId}>{ag.agreement_id}</span>
                                        <span style={styles.agType}>{ag.agreement_type}</span>
                                    </div>
                                    <div style={styles.agBody}>
                                        <span>🏢 {ag.party_a || '—'} ↔ {ag.party_b || '—'}</span>
                                        <span style={{ fontSize: 11, color: '#64748b' }}>{ag.stored_at}</span>
                                    </div>
                                    <div style={{ fontSize: 10, color: '#475569', fontFamily: 'monospace' }}>
                                        Hash: {ag.content_hash}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}

                {activeTab === 'audit' && (
                    <div style={styles.auditList}>
                        {auditLog.map((entry, i) => (
                            <div key={i} style={styles.auditEntry}>
                                <span style={styles.auditAction}>{entry.action}</span>
                                <span style={styles.auditTime}>{entry.timestamp}</span>
                                <span style={styles.auditHash}>{entry.hash}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}

// ── Styles ──
const styles = {
    app: { fontFamily: "'Inter', -apple-system, sans-serif", background: '#0a0e17', minHeight: '100vh', color: '#e2e8f0' },
    loadingScreen: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0e17' },
    loadingSpinner: { width: 40, height: 40, border: '3px solid #1e293b', borderTop: '3px solid #6366f1', borderRadius: '50%', animation: 'spin 1s linear infinite' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 32px', borderBottom: '1px solid rgba(99,102,241,0.15)', background: 'rgba(15,23,42,0.95)' },
    headerLeft: { display: 'flex', alignItems: 'center', gap: 16 },
    shield: { fontSize: 36 },
    title: { fontSize: 20, fontWeight: 700, margin: 0, background: 'linear-gradient(135deg, #6366f1, #9D4EDD)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    subtitle: { fontSize: 12, color: '#94a3b8', margin: 0 },
    headerRight: { display: 'flex', gap: 12, alignItems: 'center' },
    statusBadge: { padding: '6px 16px', borderRadius: 20, color: '#fff', fontWeight: 600, fontSize: 13 },
    encBadge: { padding: '6px 14px', borderRadius: 20, background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: 12, fontWeight: 500 },
    statsBar: { display: 'flex', gap: 0, borderBottom: '1px solid rgba(99,102,241,0.1)' },
    stat: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px 0', borderRight: '1px solid rgba(99,102,241,0.08)' },
    statValue: { fontSize: 28, fontWeight: 700, color: '#e2e8f0' },
    statLabel: { fontSize: 11, color: '#64748b', marginTop: 4, textTransform: 'uppercase', letterSpacing: 1 },
    tabs: { display: 'flex', gap: 0, borderBottom: '1px solid rgba(99,102,241,0.1)', background: 'rgba(15,23,42,0.6)' },
    tab: { flex: 1, padding: '14px 0', background: 'none', border: 'none', color: '#94a3b8', fontSize: 14, cursor: 'pointer', fontWeight: 500, borderBottom: '2px solid transparent', transition: 'all 0.2s' },
    tabActive: { color: '#6366f1', borderBottomColor: '#6366f1', background: 'rgba(99,102,241,0.05)' },
    alertCount: { marginLeft: 6, background: '#ef4444', color: '#fff', fontSize: 11, padding: '2px 7px', borderRadius: 10, fontWeight: 700 },
    content: { padding: 24, maxWidth: 960, margin: '0 auto' },
    grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 },
    card: { background: 'rgba(15,23,42,0.85)', border: '1px solid rgba(99,102,241,0.12)', borderRadius: 12, padding: 24 },
    cardTitle: { fontSize: 16, fontWeight: 600, margin: '0 0 8px 0' },
    cardDesc: { fontSize: 12, color: '#94a3b8', margin: '0 0 20px 0' },
    leitnerBoxes: { display: 'flex', gap: 12, marginBottom: 16 },
    leitnerBox: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0', border: '2px solid', borderRadius: 8, transition: 'all 0.3s' },
    escBtn: { width: '100%', padding: '10px', background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, cursor: 'pointer', fontWeight: 500, fontSize: 13 },
    infoGrid: { display: 'flex', flexDirection: 'column', gap: 12 },
    infoRow: { display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#cbd5e1' },
    empty: { textAlign: 'center', padding: 60, color: '#64748b', fontSize: 16 },
    alertCard: { background: 'rgba(15,23,42,0.85)', borderRadius: 10, padding: 16, marginBottom: 12, border: '1px solid rgba(99,102,241,0.08)' },
    alertHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
    alertType: { padding: '4px 12px', borderRadius: 6, color: '#fff', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' },
    alertTime: { fontSize: 11, color: '#64748b' },
    alertDesc: { fontSize: 14, color: '#cbd5e1', margin: '0 0 12px 0' },
    alertFooter: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    dismissBtn: { background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 500 },
    agCard: { background: 'rgba(15,23,42,0.85)', border: '1px solid rgba(99,102,241,0.1)', borderRadius: 10, padding: 16, marginBottom: 10 },
    agHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: 8 },
    agId: { fontWeight: 600, color: '#818cf8', fontSize: 14 },
    agType: { fontSize: 11, color: '#94a3b8', background: 'rgba(99,102,241,0.1)', padding: '3px 10px', borderRadius: 4 },
    agBody: { display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#cbd5e1', marginBottom: 6 },
    auditList: { display: 'flex', flexDirection: 'column', gap: 4 },
    auditEntry: { display: 'flex', gap: 16, padding: '10px 14px', background: 'rgba(15,23,42,0.6)', borderRadius: 6, fontSize: 12, alignItems: 'center' },
    auditAction: { fontWeight: 600, color: '#6366f1', minWidth: 180 },
    auditTime: { color: '#94a3b8', flex: 1 },
    auditHash: { fontFamily: 'monospace', color: '#475569', fontSize: 10 },
}

export default App
