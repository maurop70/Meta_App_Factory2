import { useState, useEffect, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════
//  PHANTOM QA ELITE — Quality Assurance Command Center
//  Sub-views: Dashboard | Runner | Pulse
//  Backend: http://localhost:5030
// ═══════════════════════════════════════════════════════════

// No hardcoded backend URL — all requests route through Vite proxy (vite.config.js)
// /api/qa/*      → http://localhost:5030
// /api/test/*     → http://localhost:5030
// /api/pulse      → http://localhost:5030
// /api/dashboard  → http://localhost:5030
// /api/reports    → http://localhost:5030

// ── Verdict Badge ──────────────────────────────────────────
function VerdictBadge({ verdict, size = 'sm' }) {
  const colors = {
    PASS: { bg: 'rgba(34,197,94,0.15)', color: '#22c55e', border: 'rgba(34,197,94,0.3)' },
    WARN: { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
    FAIL: { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', border: 'rgba(239,68,68,0.3)' },
  };
  const c = colors[verdict] || colors.WARN;
  const fontSize = size === 'lg' ? '14px' : '11px';
  const padding = size === 'lg' ? '6px 16px' : '3px 10px';
  return (
    <span style={{
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      borderRadius: '6px', fontSize, fontWeight: 700, padding,
      letterSpacing: '0.5px', textTransform: 'uppercase',
    }}>
      {verdict === 'PASS' ? '✅' : verdict === 'FAIL' ? '❌' : '⚠️'} {verdict}
    </span>
  );
}

// ── Score Ring ──────────────────────────────────────────────
function ScoreRing({ score, size = 80 }) {
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444';
  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
      <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize="18" fontWeight="700" fontFamily="Inter, sans-serif">
        {score}
      </text>
    </svg>
  );
}

// ── Stat Card ──────────────────────────────────────────────
function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '14px', padding: '20px', textAlign: 'center', flex: 1, minWidth: '140px',
    }}>
      <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '8px' }}>{label}</div>
      <div style={{ fontSize: '28px', fontWeight: 700, color: accent || '#818cf8', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', marginTop: '6px' }}>{sub}</div>}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
//  TAB 1: DASHBOARD
// ═══════════════════════════════════════════════════════════

function DashboardTab() {
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [dashRes, reportsRes] = await Promise.all([
        fetch('/api/dashboard'),
        fetch('/api/reports'),
      ]);
      const dashData = await dashRes.json();
      const reportsData = await reportsRes.json();
      setStats(dashData.stats || {});
      setRuns(reportsData.reports || []);
    } catch (err) {
      console.error('QA Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px', color: 'rgba(255,255,255,0.3)' }}>
        <div className="qa-spinner" /> Loading telemetry...
      </div>
    );
  }

  const totalRuns = stats?.total_runs || 0;
  const passRate = stats?.pass_rate != null ? Math.round(stats.pass_rate) : 0;
  const lastScore = stats?.last_score ?? '—';
  const avgScore = stats?.avg_score != null ? Math.round(stats.avg_score) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Stats Row */}
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
        <StatCard label="Total Test Runs" value={totalRuns} sub="All time" accent="#818cf8" />
        <StatCard label="Pass Rate" value={`${passRate}%`} sub="PASS verdicts" accent={passRate >= 80 ? '#22c55e' : passRate >= 50 ? '#f59e0b' : '#ef4444'} />
        <StatCard label="Last Score" value={lastScore} sub="Most recent" accent={lastScore >= 80 ? '#22c55e' : lastScore >= 50 ? '#f59e0b' : '#ef4444'} />
        <StatCard label="Avg Score" value={avgScore} sub="Composite" accent="#6366f1" />
      </div>

      {/* Recent Runs Table */}
      <div style={{
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '14px', overflow: 'hidden',
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: '13px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '1px' }}>Recent Test Runs</h3>
          <button onClick={fetchData} style={{
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
            color: '#818cf8', borderRadius: '8px', padding: '4px 12px', fontSize: '11px',
            cursor: 'pointer', fontWeight: 600,
          }}>↻ Refresh</button>
        </div>

        {runs.length === 0 ? (
          <div style={{ padding: '40px 20px', textAlign: 'center', color: 'rgba(255,255,255,0.2)', fontSize: '13px' }}>
            No test runs recorded yet. Use the Runner tab to execute your first test.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {['#', 'App', 'Verdict', 'Score', 'Duration', 'Timestamp'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', color: 'rgba(255,255,255,0.35)', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 15).map((run, i) => (
                  <tr key={run.id || i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', transition: 'background 0.2s' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '10px 16px', color: 'rgba(255,255,255,0.3)' }}>{run.id || i + 1}</td>
                    <td style={{ padding: '10px 16px', color: '#e0e0e0', fontWeight: 500 }}>{run.app_name || '—'}</td>
                    <td style={{ padding: '10px 16px' }}><VerdictBadge verdict={run.verdict || 'WARN'} /></td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{ color: run.score >= 80 ? '#22c55e' : run.score >= 50 ? '#f59e0b' : '#ef4444', fontWeight: 700 }}>{run.score ?? '—'}</span>
                      <span style={{ color: 'rgba(255,255,255,0.2)' }}>/100</span>
                    </td>
                    <td style={{ padding: '10px 16px', color: 'rgba(255,255,255,0.4)' }}>{run.duration ? `${run.duration}s` : '—'}</td>
                    <td style={{ padding: '10px 16px', color: 'rgba(255,255,255,0.3)', fontSize: '12px' }}>
                      {run.created_at ? new Date(run.created_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
//  TAB 2: RUNNER — Full Test Bench Trigger + SSE Progress
// ═══════════════════════════════════════════════════════════

function RunnerTab() {
  const [targetUrl, setTargetUrl] = useState('http://localhost:5070');
  const [appName, setAppName] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [events, setEvents] = useState([]);
  const [phase, setPhase] = useState(null);
  const logRef = useRef(null);
  const esRef = useRef(null);

  // Connect to SSE stream
  const connectStream = useCallback(() => {
    if (esRef.current) esRef.current.close();
    const es = new EventSource('/api/qa/stream');
    esRef.current = es;

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'HEARTBEAT') return;
        setEvents(prev => [...prev.slice(-200), { ...data, _ts: Date.now() }]);

        // Phase detection
        const msg = (data.message || '').toLowerCase();
        if (msg.includes('architect') || msg.includes('planning')) setPhase('architect');
        else if (msg.includes('ghost') || msg.includes('playwright')) setPhase('ghost');
        else if (msg.includes('skeptic') || msg.includes('stress')) setPhase('skeptic');
        else if (data.status === 'PASS' || data.status === 'FAIL') setPhase('complete');
      } catch {}
    };

    return () => es.close();
  }, []);

  useEffect(() => {
    const cleanup = connectStream();
    return cleanup;
  }, [connectStream]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const runFullTest = async () => {
    setRunning(true);
    setResult(null);
    setEvents([]);
    setPhase('architect');

    try {
      const res = await fetch('/api/test/full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_url: targetUrl,
          app_name: appName || targetUrl.split('://').pop().split('/')[0],
          skip_ghost: false,
        }),
      });
      const data = await res.json();
      setResult(data);
      setPhase('complete');
    } catch (err) {
      setResult({ verdict: 'FAIL', score: 0, error: err.message });
      setPhase('complete');
    } finally {
      setRunning(false);
    }
  };

  const phases = [
    { id: 'architect', icon: '📐', label: 'Architect', desc: 'Planning test strategy' },
    { id: 'ghost', icon: '👻', label: 'Ghost User', desc: 'Playwright UI testing' },
    { id: 'skeptic', icon: '🧪', label: 'Skeptic', desc: 'API stress testing' },
    { id: 'complete', icon: '✅', label: 'Verdict', desc: 'Composite scoring' },
  ];
  const phaseIdx = phases.findIndex(p => p.id === phase);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Controls */}
      <div style={{
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '14px', padding: '20px',
      }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 2, minWidth: '200px' }}>
            <label style={{ display: 'block', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '6px' }}>Target URL</label>
            <input
              id="qa-target-url"
              value={targetUrl}
              onChange={e => setTargetUrl(e.target.value)}
              placeholder="http://localhost:5070"
              disabled={running}
              style={{
                width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: '#e0e0e0',
                fontSize: '13px', fontFamily: 'JetBrains Mono, Consolas, monospace', outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => e.target.style.borderColor = 'rgba(233,69,96,0.5)'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>
          <div style={{ flex: 1, minWidth: '140px' }}>
            <label style={{ display: 'block', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '6px' }}>App Name <span style={{ opacity: 0.5 }}>(optional)</span></label>
            <input
              id="qa-app-name"
              value={appName}
              onChange={e => setAppName(e.target.value)}
              placeholder="Auto-detect"
              disabled={running}
              style={{
                width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: '#e0e0e0',
                fontSize: '13px', outline: 'none', transition: 'border-color 0.2s',
              }}
              onFocus={e => e.target.style.borderColor = 'rgba(233,69,96,0.5)'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>
          <button
            id="qa-run-full-test"
            onClick={runFullTest}
            disabled={running || !targetUrl.trim()}
            style={{
              padding: '10px 28px', borderRadius: '10px', border: 'none', fontWeight: 700,
              fontSize: '13px', cursor: running ? 'not-allowed' : 'pointer',
              background: running
                ? 'linear-gradient(135deg, #f59e0b, #d97706)'
                : 'linear-gradient(135deg, #e94560, #c23152)',
              color: '#fff', transition: 'all 0.3s', letterSpacing: '0.3px',
              opacity: running || !targetUrl.trim() ? 0.7 : 1,
              boxShadow: running ? 'none' : '0 4px 16px rgba(233,69,96,0.25)',
              whiteSpace: 'nowrap',
            }}
          >
            {running ? '⏳ Running...' : '⚡ Run Full Test'}
          </button>
        </div>

        {/* Phase Progress Bar */}
        {phase && (
          <div style={{ marginTop: '20px' }}>
            <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
              {phases.map((p, i) => {
                const isActive = p.id === phase;
                const isDone = i < phaseIdx;
                return (
                  <div key={p.id} style={{
                    flex: 1, height: '4px', borderRadius: '2px',
                    background: isDone ? '#22c55e' : isActive ? '#f59e0b' : 'rgba(255,255,255,0.06)',
                    transition: 'background 0.5s',
                  }} />
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              {phases.map((p, i) => {
                const isActive = p.id === phase;
                const isDone = i < phaseIdx;
                return (
                  <div key={p.id} style={{
                    fontSize: '11px', textAlign: 'center', flex: 1,
                    color: isActive ? '#f59e0b' : isDone ? '#22c55e' : 'rgba(255,255,255,0.2)',
                    fontWeight: isActive ? 700 : 400, transition: 'color 0.3s',
                  }}>
                    <span style={{ fontSize: '14px' }}>{isDone ? '✅' : isActive && running ? '⏳' : p.icon}</span>
                    <br />{p.label}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Result Card */}
      {result && (
        <div style={{
          background: result.verdict === 'PASS' ? 'rgba(34,197,94,0.05)' : result.verdict === 'FAIL' ? 'rgba(239,68,68,0.05)' : 'rgba(245,158,11,0.05)',
          border: `1px solid ${result.verdict === 'PASS' ? 'rgba(34,197,94,0.2)' : result.verdict === 'FAIL' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)'}`,
          borderRadius: '14px', padding: '24px', display: 'flex', alignItems: 'center', gap: '24px',
        }}>
          <ScoreRing score={result.score || 0} />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <VerdictBadge verdict={result.verdict || 'FAIL'} size="lg" />
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '13px' }}>{result.app_name || ''}</span>
            </div>
            <div style={{ display: 'flex', gap: '24px', fontSize: '12px', color: 'rgba(255,255,255,0.4)' }}>
              {result.duration_seconds && <span>⏱️ {result.duration_seconds}s</span>}
              {result.phases?.ghost_user && <span>👻 Ghost: {result.phases.ghost_user.score || 0}/100</span>}
              {result.phases?.skeptic && <span>🧪 Skeptic: {result.phases.skeptic.score || 0}/100</span>}
              {result.fix_required?.length > 0 && <span style={{ color: '#ef4444' }}>🔧 {result.fix_required.length} repairs needed</span>}
            </div>
            {result.error && <div style={{ marginTop: '8px', fontSize: '12px', color: '#ef4444' }}>Error: {result.error}</div>}
          </div>
        </div>
      )}

      {/* SSE Event Log */}
      <div style={{
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '14px', overflow: 'hidden',
      }}>
        <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: '13px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '1px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            👻 Ghost Stream
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: events.length > 0 ? '#22c55e' : '#ef4444',
              display: 'inline-block', animation: 'pulse 2s infinite',
            }} />
          </h3>
          <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)' }}>{events.length} events</span>
        </div>
        <div ref={logRef} style={{
          maxHeight: '300px', overflowY: 'auto', padding: '8px 0',
          fontFamily: 'JetBrains Mono, Consolas, monospace', fontSize: '12px',
        }}>
          {events.length === 0 ? (
            <div style={{ padding: '30px 20px', textAlign: 'center', color: 'rgba(255,255,255,0.15)', fontSize: '12px' }}>
              Waiting for telemetry events... Run a test to see real-time progress.
            </div>
          ) : events.map((evt, i) => {
            const statusColors = {
              PASS: '#22c55e', HEAL_PASS: '#22c55e', RUNNING: '#818cf8',
              FAIL: '#ef4444', HEAL_FAIL: '#ef4444',
              WARN: '#f59e0b', DEGRADED_MANUAL_REQUIRED: '#f59e0b',
              CONNECTED: '#06b6d4', INFO: '#94a3b8', HEARTBEAT: '#475569',
            };
            const color = statusColors[evt.status] || '#94a3b8';
            return (
              <div key={i} style={{
                padding: '4px 20px', display: 'flex', gap: '10px', alignItems: 'flex-start',
                borderLeft: `3px solid ${color}`, marginBottom: '2px',
                background: evt.status === 'FAIL' ? 'rgba(239,68,68,0.03)' : 'transparent',
              }}>
                <span style={{ color: 'rgba(255,255,255,0.15)', minWidth: '70px', flexShrink: 0, fontSize: '10px' }}>
                  {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                </span>
                <span style={{ color: 'rgba(255,255,255,0.3)', minWidth: '60px', flexShrink: 0 }}>[{evt.agent || '?'}]</span>
                <span style={{ color: color, minWidth: '50px', flexShrink: 0, fontWeight: 600, fontSize: '11px' }}>{evt.status || ''}</span>
                <span style={{ color: 'rgba(255,255,255,0.6)', wordBreak: 'break-word' }}>{evt.message || ''}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
//  TAB 3: PULSE — C-Suite Port Health Scanner
// ═══════════════════════════════════════════════════════════

function PulseTab() {
  const [pulseData, setPulseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const scan = useCallback(async () => {
    setScanning(true);
    try {
      const res = await fetch('/api/pulse');
      const data = await res.json();
      setPulseData(data);
    } catch (err) {
      console.error('Pulse scan error:', err);
    } finally {
      setLoading(false);
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    scan();
    const interval = setInterval(scan, 20000);
    return () => clearInterval(interval);
  }, [scan]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px', color: 'rgba(255,255,255,0.3)' }}>
        <div className="qa-spinner" /> Scanning ports...
      </div>
    );
  }

  const apps = pulseData?.apps || {};
  const online = pulseData?.online || 0;
  const total = pulseData?.total_apps || 0;
  const healthPct = total > 0 ? Math.round((online / total) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Summary Bar */}
      <div style={{
        display: 'flex', gap: '14px', alignItems: 'center', padding: '16px 20px',
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '14px',
      }}>
        <ScoreRing score={healthPct} size={64} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#e0e0e0' }}>
            {online}/{total} Services Online
          </div>
          <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', marginTop: '2px' }}>
            Last scan: {pulseData?.timestamp ? new Date(pulseData.timestamp).toLocaleTimeString() : '—'}
          </div>
        </div>
        <button onClick={scan} disabled={scanning} style={{
          padding: '8px 20px', borderRadius: '10px', border: '1px solid rgba(99,102,241,0.3)',
          background: 'rgba(99,102,241,0.1)', color: '#818cf8', fontSize: '12px',
          fontWeight: 600, cursor: scanning ? 'not-allowed' : 'pointer',
          opacity: scanning ? 0.5 : 1,
        }}>
          {scanning ? '⏳ Scanning...' : '🔍 Rescan'}
        </button>
      </div>

      {/* Port Grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: '12px',
      }}>
        {Object.entries(apps).map(([name, info]) => {
          const isOnline = info.status === 'online';
          const port = info.url?.split(':').pop() || '?';
          return (
            <div key={name} style={{
              background: isOnline ? 'rgba(34,197,94,0.04)' : 'rgba(239,68,68,0.04)',
              border: `1px solid ${isOnline ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)'}`,
              borderRadius: '12px', padding: '16px', display: 'flex', alignItems: 'center', gap: '14px',
              transition: 'all 0.3s', cursor: isOnline ? 'pointer' : 'default',
            }}
              onClick={() => isOnline && window.open(info.url, '_blank')}
              onMouseEnter={e => { if (isOnline) e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
            >
              <div style={{
                width: '10px', height: '10px', borderRadius: '50%',
                background: isOnline ? '#22c55e' : '#ef4444',
                boxShadow: isOnline ? '0 0 8px rgba(34,197,94,0.4)' : '0 0 8px rgba(239,68,68,0.3)',
                animation: isOnline ? 'pulse 2s infinite' : 'none',
                flexShrink: 0,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '13px', fontWeight: 600, color: '#e0e0e0',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{name}</div>
                <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono, Consolas, monospace' }}>
                  :{port}
                </div>
              </div>
              <span style={{
                fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
                color: isOnline ? '#22c55e' : '#ef4444', letterSpacing: '0.5px',
              }}>
                {isOnline ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
//  MAIN COMPONENT — Tabbed Container
// ═══════════════════════════════════════════════════════════

const TABS = [
  { id: 'dashboard', icon: '📊', label: 'Dashboard' },
  { id: 'runner', icon: '⚡', label: 'Test Runner' },
  { id: 'pulse', icon: '💓', label: 'System Pulse' },
];

export default function PhantomQA() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '20px', flexWrap: 'wrap', gap: '12px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <span style={{
              background: 'linear-gradient(135deg, #e94560, #c23152)', color: '#fff',
              padding: '3px 12px', borderRadius: '16px', fontSize: '10px', fontWeight: 700,
              letterSpacing: '1.2px', textTransform: 'uppercase',
            }}>QA Command Center</span>
            <span style={{
              background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)',
              padding: '2px 10px', borderRadius: '12px', fontSize: '10px', fontWeight: 600,
            }}>PORT 5030</span>
          </div>
          <h2 style={{
            margin: 0, fontSize: '22px', fontWeight: 700,
            background: 'linear-gradient(135deg, #e94560, #ff6b81)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>Phantom QA Elite</h2>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
            Autonomous quality assurance — Architect · Ghost User · Skeptic
          </p>
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{
        display: 'flex', gap: '4px', padding: '4px',
        background: 'rgba(255,255,255,0.02)', borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.06)', marginBottom: '20px',
      }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            id={`qa-tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1, padding: '10px 16px', borderRadius: '10px', border: 'none',
              background: activeTab === tab.id
                ? 'linear-gradient(135deg, rgba(233,69,96,0.15), rgba(194,49,82,0.1))'
                : 'transparent',
              color: activeTab === tab.id ? '#e94560' : 'rgba(255,255,255,0.4)',
              fontSize: '13px', fontWeight: activeTab === tab.id ? 700 : 500,
              cursor: 'pointer', transition: 'all 0.2s',
              borderBottom: activeTab === tab.id ? '2px solid #e94560' : '2px solid transparent',
            }}
            onMouseEnter={e => {
              if (activeTab !== tab.id) e.currentTarget.style.color = 'rgba(255,255,255,0.6)';
            }}
            onMouseLeave={e => {
              if (activeTab !== tab.id) e.currentTarget.style.color = 'rgba(255,255,255,0.4)';
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'dashboard' && <DashboardTab />}
      {activeTab === 'runner' && <RunnerTab />}
      {activeTab === 'pulse' && <PulseTab />}
    </div>
  );
}
