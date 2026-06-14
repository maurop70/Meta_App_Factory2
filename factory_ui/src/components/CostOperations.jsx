import { useState, useEffect } from 'react';

const fmtNum = (n) => (n || 0).toLocaleString();
const fmtUsd = (n) => '$' + (Number(n) || 0).toFixed(4);

const CARD = {
  background: 'rgba(15,23,42,0.6)',
  border: '1px solid rgba(99,102,241,0.18)',
  borderRadius: '14px',
  padding: '1.3rem',
  backdropFilter: 'blur(10px)',
};

function BarRow({ label, value, max, sub, color }) {
  const pct = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '0.25rem' }}>
        <span style={{ fontWeight: 600, color: '#e2e8f0' }}>{label}</span>
        <span style={{ color: '#94a3b8' }}>{sub}</span>
      </div>
      <div style={{ height: '10px', borderRadius: '6px', background: 'rgba(148,163,184,0.12)', overflow: 'hidden' }}>
        <div style={{ width: pct + '%', height: '100%', borderRadius: '6px', background: color, transition: 'width 0.4s ease' }} />
      </div>
    </div>
  );
}

export default function CostOperations() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      const res = await fetch('/api/telemetry/stats');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      setStats(await res.json());
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load telemetry');
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000); // live refresh
    return () => clearInterval(id);
  }, []);

  const totals = stats?.totals || {};
  const byApp = stats?.by_app || [];
  const byModel = stats?.by_model || [];
  const maxAppCost = Math.max(1e-9, ...byApp.map((a) => a.cost_usd || 0));
  const maxModelCost = Math.max(1e-9, ...byModel.map((m) => m.cost_usd || 0));

  const kpis = [
    { label: 'Estimated Spend', value: fmtUsd(totals.cost_usd), accent: '#4ade80' },
    { label: 'Total Tokens', value: fmtNum(totals.total_tokens), accent: '#818cf8' },
    { label: 'Input Tokens', value: fmtNum(totals.input_tokens), accent: '#38bdf8' },
    { label: 'Output Tokens', value: fmtNum(totals.output_tokens), accent: '#f472b6' },
    { label: 'Recorded Calls', value: fmtNum(totals.calls), accent: '#fbbf24' },
  ];

  return (
    <div style={{ padding: '1.5rem', fontFamily: 'Inter, system-ui, sans-serif', color: '#e2e8f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.2rem' }}>
        <span style={{ fontSize: '1.6rem' }}>💰</span>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700 }}>Cost Operations</h2>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Live token spend across MAF &amp; child apps · refreshes every 5s
          </div>
        </div>
      </div>

      {error && (
        <div style={{ ...CARD, borderColor: 'rgba(239,68,68,0.4)', color: '#fca5a5', marginBottom: '1rem' }}>
          ⚠ {error} — has any usage been recorded yet?
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {kpis.map((k) => (
          <div key={k.label} style={CARD}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{k.label}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: k.accent, marginTop: '0.3rem' }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.2rem' }}>
        <div style={CARD}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '0.95rem' }}>Spend by App</h3>
          {byApp.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '0.85rem' }}>No usage recorded yet.</div>
          ) : (
            byApp.map((a) => (
              <BarRow key={a.name} label={a.name} value={a.cost_usd} max={maxAppCost}
                color="linear-gradient(90deg,#6366f1,#818cf8)"
                sub={`${fmtUsd(a.cost_usd)} · ${fmtNum(a.total_tokens)} tok`} />
            ))
          )}
        </div>

        <div style={CARD}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '0.95rem' }}>Spend by Model</h3>
          {byModel.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '0.85rem' }}>No usage recorded yet.</div>
          ) : (
            byModel.map((m) => (
              <BarRow key={m.name} label={m.name} value={m.cost_usd} max={maxModelCost}
                color="linear-gradient(90deg,#10b981,#4ade80)"
                sub={`${fmtUsd(m.cost_usd)} · ${fmtNum(m.total_tokens)} tok`} />
            ))
          )}
        </div>
      </div>

      <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '1rem' }}>
        Cost is an estimate from per-model token pricing (shared_modules/telemetry.py · PRICING). Token counts are the source of truth.
      </div>
    </div>
  );
}
