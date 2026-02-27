import { useState, useEffect } from 'react'

const RiskRadar = ({ score }) => {
  const getScoreColor = (s) => {
    if (s > 70) return '#ef4444';
    if (s > 40) return '#f59e0b';
    return '#10b981';
  };

  const color = getScoreColor(score);

  return (
    <div style={{
      position: 'relative',
      width: '120px',
      height: '60px',
      overflow: 'hidden',
      margin: '0 auto'
    }}>
      <div style={{
        width: '120px',
        height: '120px',
        borderRadius: '50%',
        border: '12px solid #334155',
        borderBottomColor: 'transparent',
        borderLeftColor: 'transparent',
        transform: 'rotate(-45deg)',
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 1
      }} />
      <div style={{
        width: '120px',
        height: '120px',
        borderRadius: '50%',
        border: `12px solid ${color}`,
        borderBottomColor: 'transparent',
        borderLeftColor: 'transparent',
        transform: `rotate(${(score / 100) * 180 - 45}deg)`,
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 2,
        transition: 'transform 1s ease-out'
      }} />
      <div style={{
        position: 'absolute',
        bottom: 0,
        width: '100%',
        textAlign: 'center',
        fontWeight: 'bold',
        fontSize: '1.25rem',
        color: color,
        zIndex: 3
      }}>
        {score}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// ⓘ INFO TOOLTIP — hover any section title for instant context
// ─────────────────────────────────────────────────────────────
const InfoTooltip = ({ text, wide }) => {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-block', verticalAlign: 'middle' }}>
      <span
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: '14px', height: '14px',
          background: 'rgba(100,116,139,0.2)', border: '1px solid rgba(100,116,139,0.3)',
          borderRadius: '50%', fontSize: '8px', color: '#94a3b8',
          cursor: 'help', marginLeft: '6px', fontWeight: 700,
        }}
      >ⓘ</span>
      {show && (
        <div style={{
          position: 'absolute', bottom: 'calc(100% + 8px)', left: '50%',
          transform: 'translateX(-50%)',
          background: '#0f172a', border: '1px solid rgba(148,163,184,0.2)',
          borderRadius: '10px', padding: '0.6rem 0.9rem',
          fontSize: '0.7rem', color: '#cbd5e1', lineHeight: '1.55',
          width: wide ? '300px' : '230px', zIndex: 9999,
          boxShadow: '0 12px 32px rgba(0,0,0,0.7)',
          pointerEvents: 'none', whiteSpace: 'normal', textAlign: 'left',
        }}>
          {text}
          <div style={{
            position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0,
            borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
            borderTop: '6px solid rgba(148,163,184,0.2)',
          }} />
          <div style={{
            position: 'absolute', top: 'calc(100% - 1px)', left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0,
            borderLeft: '5px solid transparent', borderRight: '5px solid transparent',
            borderTop: '5px solid #0f172a',
          }} />
        </div>
      )}
    </span>
  );
};

// ────────────────────────────────────────────────────────────
// 📈 THETA DECAY CURVE (Priority 4)
// ────────────────────────────────────────────────────────────
const ThetaDecayCurve = ({ credit, currentMark, expiry, events = [] }) => {
  if (!credit || !currentMark || !expiry) return null;

  const today = new Date();
  const expiryDate = new Date(expiry + 'T12:00:00');
  const currentDte = Math.max(1, Math.round((expiryDate - today) / 86400000));
  const W = 560, H = 90;
  const pad = { l: 32, r: 12, t: 14, b: 22 };
  const cW = W - pad.l - pad.r;
  const cH = H - pad.t - pad.b;

  // Scale functions
  const xS = d => pad.l + (d / currentDte) * cW;
  const yS = v => pad.t + cH - Math.max(0, Math.min(1, v / credit)) * cH;

  // Decay model: accelerating theta (gamma risk increases near expiry)
  // mark(d) = currentMark * (remaining_dte / currentDte) ^ 0.65
  const N = 80;
  const pts = [];
  for (let i = 0; i <= N; i++) {
    const d = (i / N) * currentDte;
    const rem = currentDte - d;
    const m = currentMark * Math.pow(rem / currentDte, 0.65);
    pts.push([xS(d), yS(m)]);
  }
  const pathD = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const fillD = `${pathD} L${xS(currentDte).toFixed(1)},${(pad.t + cH).toFixed(1)} L${xS(0).toFixed(1)},${(pad.t + cH).toFixed(1)}Z`;

  const y50 = yS(credit / 2);
  const yBot = pad.t + cH;
  const yTop = pad.t;
  const x21 = currentDte > 21 ? xS(currentDte - 21) : null;

  // Filter catalysts within the remaining DTE window
  const cats = (events || []).filter(e => e.days_away >= 0 && e.days_away <= currentDte);

  return (
    <div style={{ marginTop: '0.75rem' }}>
      <div style={{ fontSize: '0.62rem', color: '#64748b', marginBottom: '0.25rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Theta Decay Projection &nbsp;·&nbsp; {currentDte} DTE
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="theta decay curve">
        <defs>
          <linearGradient id="tdGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Chart background */}
        <rect x={pad.l} y={pad.t} width={cW} height={cH} fill="rgba(255,255,255,0.018)" rx="3" />

        {/* 50% profit target horizontal line */}
        <line x1={pad.l} y1={y50} x2={pad.l + cW} y2={y50} stroke="#eab308" strokeWidth="1" strokeDasharray="5,4" opacity="0.7" />
        <text x={pad.l - 3} y={y50 + 3.5} fontSize="7.5" fill="#eab308" textAnchor="end" opacity="0.9">50%</text>

        {/* 21-DTE exit marker */}
        {x21 && (
          <>
            <line x1={x21} y1={yTop} x2={x21} y2={yBot} stroke="#94a3b8" strokeWidth="1" strokeDasharray="3,3" opacity="0.5" />
            <text x={x21} y={yBot + 13} fontSize="7" fill="#64748b" textAnchor="middle">21d</text>
          </>
        )}

        {/* Catalyst event markers */}
        {cats.map((ev, i) => {
          const xEv = xS(ev.days_away);
          const col = ev.impact === 'HIGH' ? '#ef4444' : '#eab308';
          const abbr = ev.event.replace(/[^A-Z]/g, '').slice(0, 3) || ev.event.slice(0, 3).toUpperCase();
          return (
            <g key={i}>
              <line x1={xEv} y1={yTop + 8} x2={xEv} y2={yBot} stroke={col} strokeWidth="1" opacity="0.55" />
              <text x={xEv} y={yTop + 6} fontSize="6.5" fill={col} textAnchor="middle" opacity="0.9">{abbr}</text>
            </g>
          );
        })}

        {/* Decay fill */}
        <path d={fillD} fill="url(#tdGrad)" />

        {/* Profit zone fill (below 50% line = captured profit) */}
        {currentMark < credit / 2 && (
          <rect x={pad.l} y={y50} width={cW} height={yBot - y50} fill="url(#profitGrad)" />
        )}

        {/* Decay curve */}
        <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth="1.8" strokeLinejoin="round" />

        {/* Current mark dot (today) */}
        <circle cx={xS(0)} cy={yS(currentMark)} r="3.5" fill="#60a5fa" stroke="#1e293b" strokeWidth="1" />
        <text x={xS(0)} y={yS(currentMark) - 6} fontSize="7.5" fill="#60a5fa" textAnchor="middle">${currentMark?.toFixed(2)}</text>

        {/* Y-axis labels */}
        <text x={pad.l - 3} y={yTop + 5} fontSize="7.5" fill="#475569" textAnchor="end">${credit?.toFixed(0)}</text>
        <text x={pad.l - 3} y={yBot + 3} fontSize="7.5" fill="#475569" textAnchor="end">$0</text>

        {/* X-axis labels */}
        <text x={xS(0)} y={yBot + 13} fontSize="7" fill="#64748b" textAnchor="middle">Now</text>
        <text x={xS(currentDte)} y={yBot + 13} fontSize="7" fill="#64748b" textAnchor="middle">Exp</text>
      </svg>
    </div>
  );
};


// ─────────────────────────────────────────────────────────────
const LedgerCard = ({ ledger }) => {
  if (!ledger || !ledger.positions || Object.keys(ledger.positions).length === 0) {
    return (
      <div className="card" style={{ gridColumn: '1 / -1', opacity: 0.7 }}>
        <div className="card-label">STRATEGY LEDGER</div>
        <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          No open positions in ledger. Ledger auto-triggers on new trade entry.
        </div>
      </div>
    );
  }

  const thesisColors = {
    'THESIS INTACT': { bg: 'rgba(16,185,129,0.15)', border: '#10b981', text: '#10b981' },
    'THESIS NEUTRAL': { bg: 'rgba(100,116,139,0.15)', border: '#64748b', text: '#94a3b8' },
    'THESIS DRIFTING': { bg: 'rgba(234,179,8,0.15)', border: '#eab308', text: '#eab308' },
    'THESIS BROKEN': { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#ef4444' },
  };

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="card-label" style={{ display: 'flex', alignItems: 'center' }}>STRATEGY LEDGER <InfoTooltip wide text="Daily audit of your open Iron Condor. Runs at 09:15 EST. Tracks thesis drift across 6 factors (VIX, SPX move, IV-HV spread, catalysts, P&L, DTE). Fires mobile alerts when thresholds cross." /></div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
          Last run: {ledger.last_run ? new Date(ledger.last_run).toLocaleTimeString() : 'Never'}
        </span>
        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Lead Quant Architect v2.1</span>
      </div>

      {Object.entries(ledger.positions).map(([tid, pstate]) => {
        const thesis = pstate.original_thesis || {};
        const drift = pstate.drift || {};
        const chall = pstate.challenger || {};
        const greeks = pstate.position_greeks || {};
        const updates = pstate.daily_updates || [];
        const credit = thesis.credit_opened || 0;
        const mark = pstate.current_mark || credit;
        const pnl = credit - mark;
        const pnlPct = credit > 0 ? Math.min((pnl / credit) * 100, 100) : 0;
        const target50 = credit / 2;
        const dte = thesis.dte_at_report || 0;

        const driftStyle = thesisColors[drift.status] || thesisColors['THESIS NEUTRAL'];
        const ratingEmoji = { 'STRONG ENTRY': '🟢', 'GOOD ENTRY': '🟡', 'MARGINAL': 'ퟠ️', 'POOR TIMING': '🔴' };

        // Upcoming catalysts
        const nextCatalyst = (thesis.upcoming_events || []).find(e => e.days_away >= 0);

        return (
          <div key={tid} style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px',
            padding: '1rem',
            marginBottom: '0.75rem',
          }}>
            {/* Header row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#e2e8f0' }}>{tid}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                  {thesis.entry_date} → {thesis.expiry} &nbsp;| {dte} DTE
                </div>
              </div>
              {/* Thesis status badge */}
              <div style={{
                padding: '0.25rem 0.65rem',
                borderRadius: '6px',
                background: driftStyle.bg,
                border: `1px solid ${driftStyle.border}`,
                color: driftStyle.text,
                fontSize: '0.7rem',
                fontWeight: 700,
                letterSpacing: '0.05em'
              }}>
                {drift.status || 'EVALUATING'}
                {drift.drift_score !== undefined && (
                  <span style={{ marginLeft: '0.4rem', opacity: 0.8 }}>
                    ({drift.drift_score > 0 ? '+' : ''}{drift.drift_score})
                  </span>
                )}
              </div>
            </div>

            {/* P&L Progress Bar */}
            <div style={{ marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                <span>P&amp;L Progress</span>
                <span style={{ color: pnl >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  +${pnl.toFixed(2)} ({pnlPct.toFixed(1)}% of max)
                </span>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.07)', borderRadius: '4px', height: '6px', overflow: 'hidden', position: 'relative' }}>
                {/* 50% target line */}
                <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '2px', background: '#eab308', zIndex: 2, opacity: 0.7 }} />
                {/* Fill */}
                <div style={{
                  width: `${Math.max(0, Math.min(pnlPct, 100))}%`,
                  height: '100%',
                  background: pnlPct >= 50 ? 'linear-gradient(90deg,#10b981,#059669)' : 'linear-gradient(90deg,#3b82f6,#6366f1)',
                  borderRadius: '4px',
                  transition: 'width 0.8s ease-out'
                }} />
              </div>
              <div style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '0.2rem' }}>
                50% target: ${target50.toFixed(2)} mark &nbsp;│&nbsp; Entry credit: ${credit.toFixed(2)}
              </div>
            </div>

            {/* Greeks Row */}
            {greeks.net_theta_per_day !== undefined && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.5rem', marginBottom: '0.85rem' }}>
                {[
                  { label: 'θ Theta', value: `+$${greeks.net_theta_per_day?.toFixed(2)}/day`, color: '#10b981', hint: 'Daily time-decay income' },
                  { label: 'ν Vega', value: `$${greeks.net_vega_per_pp?.toFixed(2)}/pp`, color: '#ef4444', hint: 'P&L per 1pp VIX move' },
                  { label: 'δ Delta', value: `${greeks.net_delta_per_pt > 0 ? '+' : ''}${greeks.net_delta_per_pt?.toFixed(2)}/pt`, color: Math.abs(greeks.net_delta_per_pt || 0) < 5 ? '#10b981' : '#eab308', hint: 'Directional exposure' },
                ].map(g => (
                  <div key={g.label} style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.07)',
                    borderRadius: '8px',
                    padding: '0.5rem 0.75rem',
                  }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b', marginBottom: '0.15rem' }}>{g.label}</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: g.color, fontFamily: 'monospace' }}>{g.value}</div>
                    <div style={{ fontSize: '0.6rem', color: '#475569', marginTop: '0.1rem' }}>{g.hint}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Priority 4 — Theta Decay Curve */}
            <ThetaDecayCurve
              credit={credit}
              currentMark={mark}
              expiry={thesis.expiry}
              events={thesis.upcoming_events || []}
            />

            {/* Bottom Info Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', fontSize: '0.72rem' }}>
              {/* Entry Rating */}
              <div style={{ color: '#94a3b8' }}>
                <div style={{ color: '#64748b', marginBottom: '0.1rem' }}>Entry Rating</div>
                <span style={{ fontWeight: 600 }}>
                  {ratingEmoji[thesis.rating] || '❓'} {thesis.rating || 'N/A'}
                </span>
              </div>

              {/* Challenger */}
              <div style={{ color: '#94a3b8' }}>
                <div style={{ color: '#64748b', marginBottom: '0.1rem' }}>Challenger Scan</div>
                {chall.available ? (
                  <span style={{ color: chall.pivot_warranted ? '#ef4444' : '#10b981', fontWeight: 600 }}>
                    {chall.pivot_warranted ? '⚠️ PIVOT' : '✔ HOLD'}
                  </span>
                ) : (
                  <span style={{ color: '#64748b' }}>Pending</span>
                )}
              </div>

              {/* Next Catalyst */}
              <div style={{ color: '#94a3b8' }}>
                <div style={{ color: '#64748b', marginBottom: '0.1rem' }}>Next Catalyst</div>
                {nextCatalyst ? (
                  <span style={{ color: nextCatalyst.impact === 'HIGH' ? '#ef4444' : '#eab308', fontWeight: 600 }}>
                    {nextCatalyst.event.split(' ').slice(0, 2).join(' ')} (T-{nextCatalyst.days_away}d)
                  </span>
                ) : (
                  <span style={{ color: '#64748b' }}>None in window</span>
                )}
              </div>
            </div>

            {/* Drift Flags (latest 2) */}
            {drift.flags && drift.flags.length > 0 && (
              <div style={{ marginTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
                {drift.flags.slice(-2).map((f, i) => {
                  const isRisk = f.startsWith('DRIFT') || f.startsWith('WARNING');
                  const isTail = f.startsWith('TAILWIND') || f.startsWith('EDGE');
                  return (
                    <div key={i} style={{
                      fontSize: '0.68rem',
                      color: isRisk ? '#fca5a5' : isTail ? '#6ee7b7' : '#94a3b8',
                      marginBottom: '0.2rem',
                      paddingLeft: '0.5rem',
                      borderLeft: `2px solid ${isRisk ? '#ef4444' : isTail ? '#10b981' : '#475569'}`,
                    }}>
                      {f}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};



// ─────────────────────────────────────────────────────────────
// 💬 STREAMING CHAT PANEL (SSE via Gemini 2.5 Flash)
// ─────────────────────────────────────────────────────────────
const ChatPanel = ({ isOpen, onToggle, apiBase, getContext }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const chatEndRef = { current: null };
  const inputRef = { current: null };

  const scrollToBottom = () => {
    if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen]);

  const clearChat = async () => {
    setMessages([]);
    try {
      await fetch(`${apiBase}/api/chat/clear`, { method: 'POST' });
    } catch (e) { /* ignore */ }
  };

  const sendMessage = async () => {
    const prompt = input.trim();
    if (!prompt || streaming) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: prompt }]);
    setStreaming(true);

    // Add empty assistant message that will be streamed into
    const assistantIdx = messages.length + 1; // +1 for the user message we just added
    setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

    try {
      // Gather live dashboard context for LLM situational awareness
      const dashboard_context = getContext ? getContext() : null;

      const res = await fetch(`${apiBase}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, dashboard_context }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: 'assistant', text: `❌ ${err.error || 'Server error'}` };
          return copy;
        });
        setStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.error) {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: 'assistant',
                  text: copy[copy.length - 1].text + `\n❌ ${event.error}`
                };
                return copy;
              });
              break;
            }
            if (event.done) break;
            if (event.text) {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: 'assistant',
                  text: copy[copy.length - 1].text + event.text
                };
                return copy;
              });
            }
          } catch (e) { /* skip malformed */ }
        }
      }
    } catch (e) {
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', text: `❌ Connection failed: ${e.message}` };
        return copy;
      });
    }
    setStreaming(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isOpen) return null;

  return (
    <div id="chat-panel" style={{
      position: 'fixed', bottom: '80px', right: '20px',
      width: '420px', maxHeight: '600px',
      background: 'rgba(15, 23, 42, 0.95)',
      backdropFilter: 'blur(20px)',
      border: '1px solid rgba(59, 130, 246, 0.3)',
      borderRadius: '16px',
      boxShadow: '0 25px 60px rgba(0,0,0,0.6), 0 0 30px rgba(59,130,246,0.1)',
      display: 'flex', flexDirection: 'column',
      zIndex: 10000,
      animation: 'slideUp 0.3s ease-out',
    }}>
      {/* Header */}
      <div style={{
        padding: '0.75rem 1rem',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1rem' }}>⚡</span>
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#e2e8f0', letterSpacing: '0.04em' }}>
            ALPHA CHAT
          </span>
          <span style={{
            fontSize: '0.6rem', background: 'rgba(16,185,129,0.15)',
            color: '#10b981', padding: '1px 6px', borderRadius: '4px',
            border: '1px solid rgba(16,185,129,0.3)', fontWeight: 600,
          }}>STREAMING</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={clearChat} title="Clear chat" style={{
            background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
            color: '#64748b', borderRadius: '6px', padding: '2px 8px',
            fontSize: '0.7rem', cursor: 'pointer',
          }}>Clear</button>
          <button onClick={onToggle} title="Close" style={{
            background: 'transparent', border: 'none',
            color: '#64748b', fontSize: '1.2rem', cursor: 'pointer', lineHeight: 1,
          }}>×</button>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '0.75rem',
        maxHeight: '420px', minHeight: '200px',
      }}>
        {messages.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '2rem 1rem',
            color: '#475569', fontSize: '0.8rem', lineHeight: '1.6',
          }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>🧠</div>
            <div style={{ fontWeight: 600, color: '#64748b', marginBottom: '0.25rem' }}>
              Alpha Architect AI
            </div>
            Ask about market conditions, strategy analysis, or option pricing.
            <br />Responses stream in real-time via Gemini 2.5 Flash.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '0.6rem',
          }}>
            <div style={{
              maxWidth: '85%',
              padding: '0.6rem 0.85rem',
              borderRadius: msg.role === 'user'
                ? '14px 14px 4px 14px'
                : '14px 14px 14px 4px',
              background: msg.role === 'user'
                ? 'linear-gradient(135deg, #2563eb, #1d4ed8)'
                : 'rgba(255,255,255,0.05)',
              border: msg.role === 'user'
                ? 'none'
                : '1px solid rgba(255,255,255,0.08)',
              color: '#e2e8f0',
              fontSize: '0.82rem',
              lineHeight: '1.5',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.text}
              {streaming && i === messages.length - 1 && msg.role === 'assistant' && (
                <span style={{
                  display: 'inline-block', width: '6px', height: '14px',
                  background: '#60a5fa', marginLeft: '2px',
                  animation: 'blink 0.8s infinite',
                  verticalAlign: 'text-bottom',
                }} />
              )}
            </div>
          </div>
        ))}
        <div ref={el => chatEndRef.current = el} />
      </div>

      {/* Input */}
      <div style={{
        padding: '0.6rem 0.75rem',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', gap: '0.5rem', alignItems: 'flex-end',
      }}>
        <textarea
          ref={el => inputRef.current = el}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={streaming ? 'Streaming...' : 'Ask Alpha Architect...'}
          disabled={streaming}
          rows={1}
          style={{
            flex: 1, resize: 'none',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '10px', padding: '0.5rem 0.75rem',
            color: '#e2e8f0', fontSize: '0.82rem',
            outline: 'none', fontFamily: 'inherit',
            maxHeight: '100px', overflowY: 'auto',
          }}
          onInput={e => {
            e.target.style.height = 'auto';
            e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
          }}
        />
        <button
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
          style={{
            background: streaming ? '#334155' : '#2563eb',
            border: 'none', borderRadius: '10px',
            width: '36px', height: '36px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: streaming ? 'not-allowed' : 'pointer',
            color: 'white', fontSize: '1rem',
            transition: 'background 0.2s',
            flexShrink: 0,
          }}
        >
          {streaming ? '⏳' : '↑'}
        </button>
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        #chat-panel ::-webkit-scrollbar { width: 4px; }
        #chat-panel ::-webkit-scrollbar-track { background: transparent; }
        #chat-panel ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
      `}</style>
    </div>
  );
};


function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [availability, setAvailability] = useState(2000)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [ledger, setLedger] = useState(null)
  const [tradeJournal, setTradeJournal] = useState([])
  const [activeTab, setActiveTab] = useState('dashboard')  // 'dashboard' | 'journal'
  const [chatOpen, setChatOpen] = useState(false)
  const [apiBase, setApiBase] = useState('http://localhost:5005')

  // Load API base URL from config
  useEffect(() => {
    fetch('/config.json').then(r => r.json()).then(cfg => {
      if (cfg.apiBaseUrl) setApiBase(cfg.apiBaseUrl);
    }).catch(() => { });
  }, []);

  // Strategy Ledger fetch (every 5 minutes, non-blocking)
  const fetchLedger = async () => {
    try {
      const configRes = await fetch('/config.json');
      const config = await configRes.json();
      const base = config.apiBaseUrl || 'http://localhost:5005';
      const res = await fetch(`${base}/api/ledger`);
      if (res.ok) setLedger(await res.json());
    } catch (e) {
      console.warn('[Ledger] Fetch failed (non-critical):', e);
    }
  };

  // Trade Journal fetch (on mount + after ledger refresh)
  const fetchJournal = async () => {
    try {
      const configRes = await fetch('/config.json');
      const config = await configRes.json();
      const base = config.apiBaseUrl || 'http://localhost:5005';
      const res = await fetch(`${base}/api/journal`);
      if (res.ok) {
        const data = await res.json();
        setTradeJournal(data.trades || []);
      }
    } catch (e) {
      console.warn('[Journal] Fetch failed (non-critical):', e);
    }
  };

  useEffect(() => {
    fetchLedger();
    fetchJournal();
    const ledgerInterval = setInterval(() => { fetchLedger(); fetchJournal(); }, 300000);
    return () => clearInterval(ledgerInterval);
  }, []);


  const fetchAnalysis = async (retryCount = 0) => {
    if (retryCount === 0) {
      setLoading(true);
      setError(null);
    }
    try {
      // 1. Load Config (Self-Healing)
      const configRes = await fetch('/config.json');
      const config = await configRes.json();
      const baseUrl = config.apiBaseUrl || "http://localhost:5005";

      console.log(`[Connecting] Fetching Alpha data from ${baseUrl}...`);

      const response = await fetch(`${baseUrl}/api/analyze?availability=${availability}`);
      if (!response.ok) throw new Error(`API Error: ${response.status}`);
      const json = await response.json();
      setData(json);
      setLastUpdated(new Date().toLocaleTimeString());
      setLoading(false);
    } catch (err) {
      console.error("Fetch error:", err);
      if (retryCount < 5) {
        // Retry after 2 seconds
        console.log(`Retrying connection... (${retryCount + 1}/5)`);
        setTimeout(() => fetchAnalysis(retryCount + 1), 2000);
      } else {
        setError("❌ Server Error: Run 'python server.py' in the Alpha_V2_Genesis folder.");
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchAnalysis();
    const interval = setInterval(() => {
      const now = new Date();
      const hours = now.getHours();
      const minutes = now.getMinutes();
      const currentTime = hours * 100 + minutes;

      if (currentTime >= 930 && currentTime <= 1600) {
        fetchAnalysis();
      } else {
        console.log("Skipping auto-refresh outside of market hours (09:30 - 16:00)");
      }
    }, 1800000); // Polling every 30 minutes

    return () => clearInterval(interval);
  }, [availability]);

  if (loading && !data) return <div className="header"><h1>Loading Alpha...</h1></div>
  if (error) return <div className="header"><h1 style={{ color: 'red' }}>{error}</h1></div>
  if (!data) return null;

  const { market_snapshot, expert_opinions, loki_proposal, risk_check, final_action, markdown_report, hot_update_widgets } = data;
  const wd = expert_opinions.watchdog || {};

  return (
    <>
      <div className="header">
        <h1>ALPHA ARCHITECT</h1>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', alignItems: 'center' }}>
          <p style={{ color: '#94a3b8', margin: 0 }}>Agentic Trading System</p>
          {lastUpdated && (
            <span style={{ fontSize: '0.75rem', color: '#64748b', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px' }}>
              Last Updated: {lastUpdated}
            </span>
          )}
          {(!expert_opinions.macro || expert_opinions.macro.risk_level === "N/A") && (
            <span style={{ fontSize: '0.75rem', color: '#eab308', background: 'rgba(234, 179, 8, 0.1)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
              ⏳ Syncing System Intelligence...
            </span>
          )}
        </div>
      </div>

      {/* Genesis Hot Updates */}
      {hot_update_widgets && hot_update_widgets.length > 0 && (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          {hot_update_widgets.map((widget, i) => (
            <div key={i} className="card" style={{
              flex: 1,
              minWidth: '300px',
              margin: 0,
              border: `1px solid ${widget.color || '#3b82f6'}`,
              background: `linear-gradient(135deg, ${widget.color || '#3b82f6'}1a 0%, rgba(15, 23, 42, 0.8) 100%)`,
              boxShadow: `0 0 15px ${widget.color || '#3b82f6'}22`,
              animation: 'pulse 3s infinite ease-in-out',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: '-50%',
                left: '-50%',
                width: '200%',
                height: '200%',
                background: `radial-gradient(circle, ${widget.color || '#3b82f6'}0a 0%, transparent 70%)`,
                pointerEvents: 'none'
              }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', position: 'relative' }}>
                <span style={{ fontSize: '1.2rem', filter: `drop-shadow(0 0 5px ${widget.color || '#3b82f6'})` }}>⚡</span>
                <h3 style={{ margin: 0, color: widget.color || '#60a5fa', letterSpacing: '0.05em' }}>{widget.title.toUpperCase()}</h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.5', position: 'relative' }}>{widget.content}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid">
        {/* Dual-Strategy Rationale Card */}
        <div className="card" style={{ gridColumn: 'span 2', border: '1px solid #3b82f6', background: 'rgba(59, 130, 246, 0.05)' }}>
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, color: '#60a5fa', display: 'flex', alignItems: 'center' }}>{data.strategy || "STRATEGIC REGIME"}<InfoTooltip wide text="STABLE → 7 DTE Tactical (fast theta, weekly premium). VOLATILE → 45 DTE Core Income (higher credit, wider buffers). Driven by VIX, IV Rank, and IV-HV spread." /></h3>
            <span style={{ fontSize: '0.75rem', background: '#2563eb', padding: '2px 8px', borderRadius: '4px', color: 'white' }}>{data.dte} DTE TARGET</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.25rem 0' }}>Current Verdict</p>
                <h2 style={{ color: data.verdict === 'ENTRY' ? '#10b981' : (data.verdict === 'WAIT' ? '#f59e0b' : '#ef4444'), margin: 0, fontSize: '1.75rem' }}>{data.verdict}</h2>
              </div>
              <div style={{ textAlign: 'center', padding: '0 2rem', borderLeft: '1px solid rgba(255,255,255,0.1)', borderRight: '1px solid rgba(255,255,255,0.1)' }}>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.5rem 0' }}>N8N Risk Score</p>
                <RiskRadar score={loki_proposal.risk_score || 50} />
                <div style={{ fontSize: '0.7rem', marginTop: '4px', color: data.n8n_status?.includes('LIVE') ? '#4ade80' : '#f87171' }}>
                  {data.n8n_status || '🔴 STANDBY'}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.25rem 0' }}>Delta Target</p>
                <h2 style={{ margin: 0, fontSize: '1.75rem' }}>{data.delta}</h2>
              </div>
            </div>
            <div style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', borderLeft: '3px solid #3b82f6' }}>
              <p style={{ color: '#cbd5e1', fontSize: '0.9rem', lineHeight: '1.4', margin: 0 }}>
                <b>Rationale:</b> {loki_proposal.rationale || 'Awaiting strategy synthesis...'}
              </p>
            </div>
          </div>
        </div>

        {/* LOKI BRAIN */}
        <div className="card loki-brain">
          <div className="card-title">
            <span>CORE STRATEGY (LOKI)</span>
            <span className={`status-badge ${final_action !== 'WAIT' ? 'status-green' : 'status-yellow'}`}>
              STATUS: {final_action}
            </span>
          </div>
          <div className="metric-large">{loki_proposal.strategy}</div>
          <div className="rationale">{loki_proposal.rationale}</div>

          {data.expert_opinions.defense ? (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 0.5rem 0', color: '#f87171' }}>🛡️ Defense Matrix</h3>

              {data.expert_opinions.defense.target_trade && (
                <div style={{ marginBottom: '0.75rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{ color: '#white', fontWeight: 'bold' }}>
                    RECOMMENDATION: <span style={{ color: '#60a5fa' }}>ROLL to {data.expert_opinions.defense.target_trade.short_call}/{data.expert_opinions.defense.target_trade.long_call} Call Vertical</span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    Exp: {data.expert_opinions.defense.target_trade.expiration}
                  </div>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.9rem' }}>
                <div>
                  <div style={{ color: '#94a3b8' }}>Cost to Close</div>
                  <div style={{ color: '#f87171', fontWeight: 'bold' }}>-${data.expert_opinions.defense.financials.debit_close}</div>
                </div>
                <div>
                  <div style={{ color: '#94a3b8' }}>Roll Credit</div>
                  <div style={{ color: '#4ade80', fontWeight: 'bold' }}>+${data.expert_opinions.defense.financials.credit_open}</div>
                </div>
                <div style={{ gridColumn: 'span 2', marginTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.5rem' }}>
                  <div style={{ color: '#94a3b8' }}>Optimal Width (Avail):</div>
                  <div style={{ color: 'white' }}>{data.expert_opinions.defense.financials.width}</div>
                </div>
                <div style={{ gridColumn: 'span 2', marginTop: '0.5rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                  <div style={{ color: '#94a3b8' }}>Net P&L Impact</div>
                  <div style={{ color: data.expert_opinions.defense.financials.net_impact > 0 ? '#4ade80' : '#f87171', fontWeight: 'bold' }}>
                    {data.expert_opinions.defense.financials.net_impact > 0 ? '+' : ''}${data.expert_opinions.defense.financials.net_impact}
                  </div>
                </div>
              </div>
              <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: '#cbd5e1' }}>
                {data.expert_opinions.defense.details}
              </p>
            </div>
          ) : data.expert_opinions.defense && data.market_state === 'STABLE' ? (
            /* STABLE STATE: Challenger Trade Scan */
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(148, 163, 184, 0.08)', border: '1px solid #475569', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 0.75rem 0', color: '#94a3b8', fontSize: '0.9rem', letterSpacing: '0.05em' }}>🔄 CHALLENGER TRADE SCAN</h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 0.75rem 0', fontStyle: 'italic', lineHeight: '1.4' }}>
                A <b style={{ color: '#94a3b8' }}>Challenger Trade</b> is a hypothetical fresh entry at today's optimal strikes (based on {data.delta || '0.15'} delta). Loki compares its margin buffer against your current trade to decide if switching is worth the cost.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.85rem' }}>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '6px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem', fontWeight: 'bold', marginBottom: '0.25rem' }}>CURRENT TRADE</div>
                  <div style={{ color: '#cbd5e1' }}>{data.expert_opinions.watchdog?.trade_details?.short_put_strike || '—'} / {data.expert_opinions.watchdog?.trade_details?.short_call_strike || '—'}</div>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem', marginTop: '2px' }}>Strikes (Put / Call)</div>
                </div>
                <div style={{ background: 'rgba(59,130,246,0.1)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(59,130,246,0.3)' }}>
                  <div style={{ color: '#60a5fa', fontSize: '0.7rem', fontWeight: 'bold', marginBottom: '0.25rem' }}>CHALLENGER TARGET</div>
                  <div style={{ color: '#cbd5e1' }}>{data.expert_opinions.defense?.target_trade?.short_put || '—'} / {data.expert_opinions.defense?.target_trade?.long_put || '—'}</div>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem', marginTop: '2px' }}>Put Vertical Strikes</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.15)', padding: '0.5rem', borderRadius: '6px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Cost to Switch (Debit)</div>
                  <div style={{ color: '#f87171', fontWeight: 'bold' }}>-${data.expert_opinions.defense?.financials?.debit_close ?? '0.00'}</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.15)', padding: '0.5rem', borderRadius: '6px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>New Entry Credit</div>
                  <div style={{ color: '#4ade80', fontWeight: 'bold' }}>+${data.expert_opinions.defense?.financials?.credit_open ?? '0.00'}</div>
                </div>
                <div style={{ gridColumn: 'span 2', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '6px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Net P&L if Switched</div>
                  <div style={{
                    fontWeight: 'bold',
                    color: (data.expert_opinions.defense?.financials?.net_impact ?? 0) >= 0 ? '#4ade80' : '#f87171'
                  }}>
                    {(data.expert_opinions.defense?.financials?.net_impact ?? 0) >= 0 ? '+' : ''}${data.expert_opinions.defense?.financials?.net_impact ?? '0.00'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>
                    {(data.expert_opinions.defense?.financials?.net_impact ?? 0) >= 0
                      ? '✅ Switch would be net positive — Loki will flag ROLL if gate opens.'
                      : '⏸ Switch is net negative — HOLD until conditions improve.'}
                  </div>
                </div>
              </div>
              <p style={{ fontSize: '0.75rem', marginTop: '0.75rem', color: '#475569', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.5rem' }}>
                {data.expert_opinions.defense?.details}
              </p>
            </div>
          ) : data.expert_opinions.new_trade ? (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid #3b82f6', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 0.5rem 0', color: '#60a5fa' }}>🚀 Opportunity Scan</h3>
              <div style={{ fontSize: '0.9rem', color: '#cbd5e1' }}>Based on Availability (${availability})</div>

              <div style={{ marginTop: '0.5rem', fontSize: '1rem', fontWeight: 'bold', color: 'white' }}>
                Credit: <span style={{ color: '#4ade80' }}>${data.expert_opinions.new_trade.credit}</span>
              </div>

              {data.expert_opinions.new_trade.mmm && (
                <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.25rem', borderRadius: '4px' }}>
                    <span style={{ color: '#94a3b8' }}>MMM (Exp):</span>
                    <div style={{ color: '#eab308' }}>${data.expert_opinions.new_trade.mmm}</div>
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.25rem', borderRadius: '4px' }}>
                    <span style={{ color: '#94a3b8' }}>Dist. Put:</span>
                    <div style={{ color: 'white' }}>{data.expert_opinions.new_trade.distances?.put}</div>
                  </div>
                  {data.expert_opinions.new_trade.distances?.call > 0 && (
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.25rem', borderRadius: '4px', gridColumn: 'span 2' }}>
                      <span style={{ color: '#94a3b8' }}>Dist. Call:</span>
                      <span style={{ color: 'white', marginLeft: '0.5rem' }}>{data.expert_opinions.new_trade.distances?.call}</span>
                    </div>
                  )}
                </div>
              )}

              <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                {data.expert_opinions.new_trade.details}
              </div>
            </div>
          ) : null}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '1rem' }}>
            <button
              onClick={() => setShowModal(true)}
              style={{ padding: '0.5rem', background: 'transparent', border: '1px solid #3b82f6', color: '#3b82f6', borderRadius: '4px', cursor: 'pointer' }}
            >
              📄 System Report
            </button>
            <button
              onClick={() => {
                fetch('/config.json').then(r => r.json()).then(cfg => {
                  fetch(`${cfg.apiBaseUrl || 'http://localhost:5005'}/api/memo`)
                    .then(res => res.json())
                    .then(memoData => {
                      // MERGE with existing data, don't replace it!
                      setData(prevData => ({
                        ...prevData,
                        markdown_report: memoData.content
                      }));
                      setShowModal(true);
                    })
                })
              }}
              style={{ padding: '0.5rem', background: 'transparent', border: '1px solid #eab308', color: '#eab308', borderRadius: '4px', cursor: 'pointer' }}
            >
              📝 Analyst Memo
            </button>
          </div>
        </div>

        {/* ACTIVE TRADE WATCHDOG */}
        <div className="card" style={{ border: wd.status === 'DANGER' ? '1px solid red' : '1px solid rgba(255,255,255,0.1)' }}>
          <div className="card-title">
            <span>ACTIVE TRADE ({wd.trade_details?.status || 'NONE'})</span>
            <span className={`status-badge ${wd.status === 'SAFE' ? 'status-green' : wd.status === 'DANGER' ? 'status-red' : 'status-yellow'}`}>
              {wd.status}
            </span>
          </div>
          {wd.trade_details ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '0.4rem', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <span style={{ color: '#f87171', display: 'block', fontSize: '0.7rem', fontWeight: 'bold', letterSpacing: '0.05em' }}>SHORT PUT</span>
                  <b style={{ fontSize: '1.1rem' }}>{wd.trade_details.short_put_strike}</b>
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '4px' }}>
                    <b>${Math.abs(market_snapshot.spx - wd.trade_details.short_put_strike).toFixed(2)}</b>
                    <span style={{ color: '#94a3b8', marginLeft: '4px' }}>({((Math.abs(market_snapshot.spx - wd.trade_details.short_put_strike) / market_snapshot.spx) * 100).toFixed(2)}%)</span>
                  </div>
                </div>
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '0.4rem', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <span style={{ color: '#f87171', display: 'block', fontSize: '0.7rem', fontWeight: 'bold', letterSpacing: '0.05em' }}>SHORT CALL</span>
                  <b style={{ fontSize: '1.1rem' }}>{wd.trade_details.short_call_strike}</b>
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '4px' }}>
                    <b>${Math.abs(market_snapshot.spx - wd.trade_details.short_call_strike).toFixed(2)}</b>
                    <span style={{ color: '#94a3b8', marginLeft: '4px' }}>({((Math.abs(market_snapshot.spx - wd.trade_details.short_call_strike) / market_snapshot.spx) * 100).toFixed(2)}%)</span>
                  </div>
                </div>
                <div style={{ background: 'rgba(34, 197, 94, 0.05)', padding: '0.25rem', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ color: '#4ade80', display: 'block', fontSize: '0.7rem' }}>LONG PUT</span>
                  <b>{wd.trade_details.long_put_strike}</b>
                </div>
                <div style={{ background: 'rgba(34, 197, 94, 0.05)', padding: '0.25rem', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ color: '#4ade80', display: 'block', fontSize: '0.7rem' }}>LONG CALL</span>
                  <b>{wd.trade_details.long_call_strike}</b>
                </div>

                <div style={{ gridColumn: 'span 2', background: 'rgba(234, 179, 8, 0.1)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(234, 179, 8, 0.2)', textAlign: 'center', marginTop: '0.5rem' }}>
                  <span style={{ color: '#eab308', fontSize: '0.8rem', fontWeight: 'bold' }}>SCANNING CHALLENGER TRADES vs MMM 📡</span>
                  <div style={{ fontSize: '1.1rem', marginTop: '2px' }}>
                    <b style={{ color: '#eab308' }}>${data.expert_opinions.new_trade?.mmm || data.expert_opinions.simulation?.financials?.mmm || data.expert_opinions.defense?.financials?.mmm || "N/A"}</b>
                    <span style={{ color: '#94a3b8', fontSize: '0.8rem', marginLeft: '4px' }}>Market Range</span>
                  </div>
                </div>
              </div>



              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.25rem' }}>
                <div style={{ background: 'rgba(34, 197, 94, 0.1)', padding: '0.4rem', borderRadius: '6px', textAlign: 'center' }}>
                  <span style={{ color: '#4ade80', display: 'block', fontSize: '0.7rem', fontWeight: 'bold' }}>CREDIT</span>
                  <b style={{ fontSize: '1.1rem', color: '#4ade80' }}>${wd.trade_details.credit_received || wd.trade_details.open_price || 'N/A'}</b>
                </div>
                <div style={{ background: 'rgba(234, 179, 8, 0.1)', padding: '0.4rem', borderRadius: '6px', textAlign: 'center' }}>
                  <span style={{ color: '#eab308', display: 'block', fontSize: '0.7rem', fontWeight: 'bold' }}>50% TARGET</span>
                  <b style={{ fontSize: '1.1rem', color: '#eab308' }}>${((wd.trade_details.credit_received || wd.trade_details.open_price || 0) / 2).toFixed(2)}</b>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', marginTop: '0.5rem' }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.3rem', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.65rem' }}>EXPIRATION</span>
                  <span style={{ fontSize: '0.85rem' }}>{wd.trade_details.expiration_date}</span>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.3rem', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.65rem' }}>DTE</span>
                  <span style={{ fontSize: '0.85rem' }}>{Math.max(0, Math.ceil((new Date(wd.trade_details.expiration_date) - new Date()) / (1000 * 60 * 60 * 24)))}</span>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.3rem', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.65rem' }}>WIDTH</span>
                  <span style={{ fontSize: '0.85rem' }}>${wd.trade_details.short_put_strike - wd.trade_details.long_put_strike}</span>
                </div>
              </div>
              <div style={{ textAlign: 'center', marginTop: '0.75rem' }}>
                <div className="metric-large">{wd.verdict}</div>
                <div className="metric-label">WATCHDOG VERDICT</div>
              </div>
            </>
          ) : (
            <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>No positions found in portfolio.json</div>
          )}
        </div>

        {/* MARKET SENSE */}
        <div className="card">
          <div className="card-title">MARKET DATA</div>
          <div className="metric-large">{market_snapshot.spx.toFixed(2)}</div>
          <div className="metric-label">SPX PRICE</div>
          <hr style={{ borderColor: '#334155', margin: '1rem 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>VIX: <b>{market_snapshot.vix.toFixed(2)}</b></span>
            <span>Trend: <b>{market_snapshot.trend_5d_pct}%</b></span>
          </div>
        </div>

        {/* VOLATILITY AGENT */}
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center' }}>VOLATILITY AGENT <InfoTooltip text="IV Rank (0-100%) measures how expensive options are vs the past 30 days. High IVR = more premium. HV30 = realized volatility. SELL signal when IVR > 30 and VIX > 15." /></div>
          <div className="metric-large">{expert_opinions.volatility.vix_rank_30d}%</div>
          <div className="metric-label">IV RANK (30D)</div>
          <div style={{ marginTop: '1rem', color: expert_opinions.volatility.signal.includes('SELL') ? '#ef4444' : '#22c55e' }}>
            SIGNAL: {expert_opinions.volatility.signal}
          </div>
          {/* N8N Cloud Forecast — the authoritative forward-looking bias */}
          {(() => {
            const n8nForecast = expert_opinions.n8n?.forecast || expert_opinions.volatility.forecast || null;
            if (!n8nForecast) return null;
            const fColor = n8nForecast === 'BULLISH' ? '#4ade80' : n8nForecast === 'BEARISH' ? '#f87171' : '#eab308';
            const fExplain = n8nForecast === 'BULLISH'
              ? 'Cloud Brain expects upward pressure. Favour call-side buffer.'
              : n8nForecast === 'BEARISH'
                ? 'Cloud Brain expects downward pressure. Favour put-side buffer.'
                : 'Cloud Brain sees no clear directional edge. Fair-value Iron Condor conditions.';
            const fSource = expert_opinions.n8n?.n8n_live ? '🟢 Genesis v3' : '🔴 Local Cache';
            return (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: `${fColor}11`, border: `1px solid ${fColor}44`, borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#94a3b8', letterSpacing: '0.05em', display: 'flex', alignItems: 'center' }}>N8N FORECAST <InfoTooltip text="Cloud Brain's 7-day directional bias from Gemini AI. BULLISH = widen call buffer. BEARISH = widen put buffer. NEUTRAL = symmetric IC. 🟢 = live Genesis v3. 🔴 = Gemini direct fallback." /></span>
                  <span style={{ fontSize: '0.65rem', color: expert_opinions.n8n?.n8n_live ? '#4ade80' : '#f87171' }}>{fSource}</span>
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 'bold', color: fColor }}>{n8nForecast}</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem', lineHeight: '1.3' }}>{fExplain}</div>
              </div>
            );
          })()}
        </div>

        {/* SENTIMENT AGENT */}
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center' }}>SENTIMENT AGENT <InfoTooltip text="News bias scored from recent SPX headlines. Used as a directional tiebreaker for strike placement. BEARISH sentiment + NEUTRAL forecast → Loki widens the put buffer slightly." /></div>
          <div className="metric-large">{expert_opinions.sentiment.bias.toUpperCase()}</div>
          <div className="metric-label">NEWS BIAS</div>
          <div style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#94a3b8' }}>
            "{expert_opinions.sentiment.narrative}"
          </div>
        </div>

        {/* MACRO AGENT (NEW) */}
        {expert_opinions.macro && (
          <div className="card">
            <div className="card-title" style={{ display: 'flex', alignItems: 'center' }}>MACRO RISK RADAR <InfoTooltip text="Upcoming HIGH-impact events (FOMC, CPI, NFP) that can spike volatility. HIGH events within 2 days trigger a drift penalty and apply a wider strike recommendation." /></div>
            <div className="metric-large" style={{ color: expert_opinions.macro.risk_level === 'HIGH' ? '#ef4444' : '#eab308' }}>
              {expert_opinions.macro.risk_level} ALERT
            </div>
            <div className="metric-label">7-DAY OUTLOOK</div>

            <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {expert_opinions.macro.events.map((evt, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem',
                  borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.25rem'
                }}>
                  <span style={{ color: evt.impact === 'HIGH' ? '#f87171' : '#cbd5e1' }}>
                    {evt.event}
                  </span>
                  <span style={{ color: '#94a3b8' }}>
                    {evt.days_until === 0 ? "TODAY" : `${evt.days_until}d`}
                  </span>
                </div>
              ))}
              {expert_opinions.macro.events.length === 0 && (
                <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>No major events upcoming.</div>
              )}
            </div>
          </div>
        )}

        {/* RISK AGENT */}
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center' }}>RISK GUARDIAN <InfoTooltip text="Final safety veto. APPROVED = all checks pass (IVR ≥ 20, VIX < 40, capital OK, DTE > 3). VETOED = one or more conditions failed — do NOT enter the trade." /></div>
          <div className="metric-large" style={{ color: risk_check.approved ? '#22c55e' : '#ef4444' }}>
            {risk_check.approved ? "APPROVED" : "VETOED"}
          </div>
          <div className="metric-label">SAFETY CHECK</div>
          {!risk_check.approved && (
            <div style={{ marginTop: '1rem', color: '#ef4444' }}>
              Reasons: {risk_check.reasons.join(", ")}
            </div>
          )}
        </div>

        {/* STRATEGY LEDGER — full-width row at bottom of grid */}
        <LedgerCard ledger={ledger} />

      </div>

      <div style={{ textAlign: 'center', marginTop: '3rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.05)', padding: '0.5rem 1rem', borderRadius: '8px' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Availability ($):</span>
          <input
            type="number"
            value={availability}
            onChange={(e) => setAvailability(Number(e.target.value))}
            style={{
              background: 'transparent', border: '1px solid #475569', color: 'white',
              padding: '0.25rem', borderRadius: '4px', width: '80px', textAlign: 'center'
            }}
          />
        </div>

        <button
          onClick={fetchAnalysis}
          style={{
            padding: '1rem 2rem',
            background: '#3b82f6',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          {loading ? "Scanning..." : "Refine Scan"}
        </button>
      </div>

      {/* MODAL */}
      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
          background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{
            background: '#1e293b', padding: '2rem', borderRadius: '16px', maxWidth: '800px', width: '90%', maxHeight: '90vh', overflowY: 'auto', position: 'relative'
          }}>
            <button
              onClick={() => setShowModal(false)}
              style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: 'pointer' }}
            >
              &times;
            </button>

            <button
              onClick={() => {
                // Regenerate Memo
                setData(prev => ({ ...prev, markdown_report: "## ⏳ Generating fresh analysis..." }));
                fetch('/config.json').then(r => r.json()).then(cfg => {
                  fetch(`${cfg.apiBaseUrl || 'http://localhost:5005'}/api/memo/refresh`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                      setData(prevData => ({
                        ...prevData,
                        markdown_report: data.content
                      }));
                    })
                })
              }}
              style={{
                position: 'absolute', top: '1rem', right: '4rem',
                padding: '0.25rem 0.5rem', fontSize: '0.8rem',
                background: '#3b82f6', border: 'none', borderRadius: '4px',
                color: 'white', cursor: 'pointer'
              }}
            >
              ↻ Refresh
            </button>

            <div style={{ fontFamily: 'monospace', color: '#cbd5e1', lineHeight: '1.6', marginTop: '1rem' }}>
              {/* Keep formatting but allow wrapping */}
              <div dangerouslySetInnerHTML={{ __html: markdown_report?.replace(/\n/g, '<br/>').replace(/# (.*)/g, '<h2>$1</h2>').replace(/\*\*(.*)\*\*/g, '<b>$1</b>') }} />
              {/* Simple renderer for now. In real app, use react-markdown */}
            </div>
          </div>
        </div>
      )}

      {/* ══ TAB BAR ═══════════════════════════════════════════ */}
      <div style={{
        display: 'flex', gap: '0.5rem', margin: '2rem 1rem 0',
        borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0',
      }}>
        {[
          { id: 'dashboard', label: '📊 Dashboard' },
          { id: 'journal', label: `📘 Trade Journal${tradeJournal.length > 0 ? ` (${tradeJournal.length})` : ''}` },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            padding: '0.5rem 1.25rem',
            background: activeTab === tab.id ? 'rgba(59,130,246,0.15)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
            borderRadius: '6px 6px 0 0',
            color: activeTab === tab.id ? '#60a5fa' : '#64748b',
            fontSize: '0.8rem', fontWeight: activeTab === tab.id ? 700 : 400,
            cursor: 'pointer', transition: 'all 0.2s',
          }}>{tab.label}</button>
        ))}
      </div>

      {/* ══ TAB: TRADE JOURNAL ══════════════════════════════════ */}
      {activeTab === 'journal' && (
        <div style={{
          margin: '0 1rem 2rem',
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderTop: 'none',
          borderRadius: '0 0 14px 14px',
          padding: '1.5rem',
        }}>
          {tradeJournal.length === 0 ? (
            // ── Empty State ──
            <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📭</div>
              <div style={{ fontWeight: 700, color: '#94a3b8', fontSize: '1rem', marginBottom: '0.5rem' }}>
                No closed trades yet
              </div>
              <div style={{ color: '#475569', fontSize: '0.8rem', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto' }}>
                The Trade Journal automatically archives positions when you close them.<br />
                Remove a position from <code style={{ background: 'rgba(255,255,255,0.05)', padding: '1px 5px', borderRadius: '3px' }}>portfolio.json</code> (or change its status to CLOSED)
                and the next ledger run will archive it here with full P&amp;L details.
              </div>
            </div>
          ) : (
            // ── Trade Table ──
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#e2e8f0' }}>
                    Closed Trade History
                  </div>
                  <div style={{ fontSize: '0.65rem', color: '#475569', marginTop: '0.15rem' }}>
                    {tradeJournal.length} trade{tradeJournal.length > 1 ? 's' : ''} &nbsp;·&nbsp;
                    Win rate: <span style={{ color: '#10b981' }}>
                      {Math.round(tradeJournal.filter(t => t.realized_pnl >= 0).length / tradeJournal.length * 100)}%
                    </span> &nbsp;·&nbsp;
                    Avg P&L: <span style={{ color: '#10b981' }}>
                      {(tradeJournal.reduce((s, t) => s + (t.realized_pnl_pct || 0), 0) / tradeJournal.length).toFixed(1)}% of max
                    </span>
                  </div>
                </div>
                <button onClick={fetchJournal} style={{
                  padding: '0.3rem 0.7rem', fontSize: '0.72rem',
                  background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
                  borderRadius: '6px', color: '#60a5fa', cursor: 'pointer'
                }}>↻ Refresh</button>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                      {['Trade ID', 'Strategy', 'Opened', 'Closed', 'Days', 'Credit', 'Close', 'P&L $', 'P&L %', 'Drawdown', 'Rating'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: '#64748b', fontWeight: 600, fontSize: '0.68rem', letterSpacing: '0.04em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tradeJournal.map((t, i) => {
                      const won = t.realized_pnl >= 0;
                      const great = t.realized_pnl_pct >= 40;
                      return (
                        <tr key={i} style={{
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                        }}>
                          <td style={{ padding: '0.45rem 0.6rem', fontFamily: 'monospace', fontSize: '0.7rem', color: '#94a3b8' }}>{t.trade_id}</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#cbd5e1' }}>{t.strategy}</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#64748b' }}>{t.entry_date}</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#64748b' }}>{t.close_date}</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#94a3b8', textAlign: 'center' }}>{t.days_held ?? '—'}d</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#cbd5e1', fontFamily: 'monospace' }}>${t.credit_received?.toFixed(2)}</td>
                          <td style={{ padding: '0.45rem 0.6rem', color: '#94a3b8', fontFamily: 'monospace' }}>${t.close_mark?.toFixed(2)}</td>
                          <td style={{ padding: '0.45rem 0.6rem', fontWeight: 700, fontFamily: 'monospace', color: won ? '#10b981' : '#ef4444' }}>
                            {won ? '+' : ''}${t.realized_pnl?.toFixed(2)}
                          </td>
                          <td style={{ padding: '0.45rem 0.6rem', fontWeight: 600, color: great ? '#10b981' : won ? '#6ee7b7' : '#f87171' }}>
                            {t.realized_pnl_pct?.toFixed(1)}%
                          </td>
                          <td style={{ padding: '0.45rem 0.6rem', color: t.max_drawdown_pct > 20 ? '#f87171' : '#94a3b8' }}>
                            {t.max_drawdown_pct?.toFixed(1)}%
                          </td>
                          <td style={{ padding: '0.45rem 0.6rem' }}>
                            <span style={{
                              fontSize: '0.65rem', fontWeight: 600,
                              color: t.entry_rating === 'STRONG ENTRY' ? '#10b981' : t.entry_rating === 'GOOD ENTRY' ? '#eab308' : '#94a3b8',
                            }}>{t.entry_rating}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ══ FLOATING CHAT BUTTON ═══════════════════════════════ */}
      <button
        id="chat-toggle-btn"
        onClick={() => setChatOpen(prev => !prev)}
        title={chatOpen ? 'Close Chat' : 'Open Alpha Chat (Streaming)'}
        style={{
          position: 'fixed', bottom: '20px', right: '20px',
          width: '52px', height: '52px',
          borderRadius: '50%',
          background: chatOpen
            ? 'linear-gradient(135deg, #475569, #334155)'
            : 'linear-gradient(135deg, #2563eb, #1d4ed8)',
          border: 'none',
          boxShadow: chatOpen
            ? '0 4px 15px rgba(0,0,0,0.4)'
            : '0 4px 20px rgba(37,99,235,0.4), 0 0 40px rgba(37,99,235,0.15)',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.4rem',
          zIndex: 10001,
          transition: 'all 0.3s ease',
          color: 'white',
        }}
      >
        {chatOpen ? '×' : '💬'}
      </button>

      {/* ══ STREAMING CHAT PANEL ═══════════════════════════════ */}
      <ChatPanel
        isOpen={chatOpen}
        onToggle={() => setChatOpen(false)}
        apiBase={apiBase}
        getContext={() => {
          const ctx = {};
          if (data) {
            ctx.market = {
              spx_price: data.spx_price,
              vix: data.vix,
              signal: data.signal,
              risk_score: data.risk_score,
              recommendation: data.recommendation,
            };
            if (data.trade) ctx.active_trade = data.trade;
            if (data.greeks) ctx.greeks = data.greeks;
          }
          if (ledger) {
            ctx.ledger_summary = {
              total_trades: ledger.state?.total_trades,
              win_rate: ledger.state?.win_rate,
              net_pnl: ledger.state?.net_pnl,
              avg_credit: ledger.state?.avg_credit,
            };
          }
          if (tradeJournal?.length) {
            ctx.recent_trades = tradeJournal.slice(0, 5).map(t => ({
              date: t.date, strikes: t.strikes, credit: t.credit,
              result: t.result, pnl: t.pnl,
            }));
          }
          return Object.keys(ctx).length ? ctx : null;
        }}
      />

    </>
  )
}

export default App

