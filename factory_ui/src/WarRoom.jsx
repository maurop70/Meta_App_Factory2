import { useState, useEffect, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════
//  WAR ROOM — Adversarial Boardroom UI (Phase 2 + 3)
//  Real-time agent dialogue | Socratic Challenger | Convince Logic
// ═══════════════════════════════════════════════════════════

const WS_URL = 'ws://localhost:8000/ws/warroom';
const API_BASE = 'http://localhost:8000';

const AGENT_STYLES = {
  CEO:       { icon: '👔', color: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
  CMO:       { icon: '📢', color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)' },
  CFO:       { icon: '💰', color: '#22c55e', bg: 'rgba(34,197,94,0.08)' },
  CRITIC:    { icon: '🔍', color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
  ARCHITECT: { icon: '🏗️', color: '#06b6d4', bg: 'rgba(6,182,212,0.08)' },
  SYSTEM:    { icon: '⚡', color: '#eab308', bg: 'rgba(234,179,8,0.08)' },
  COMMANDER: { icon: '⚡', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
};

const SEVERITY_COLORS = {
  CRITICAL: '#ef4444',
  SIGNIFICANT: '#f97316',
  MODERATE: '#eab308',
};

export default function WarRoom() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [persuasion, setPersuasion] = useState(5);
  const [connected, setConnected] = useState(false);
  const [topicInput, setTopicInput] = useState('');
  // Phase 3 state
  const [activeChallenge, setActiveChallenge] = useState(null);
  const [challengeScore, setChallengeScore] = useState('');
  const [convinceMode, setConvinceMode] = useState(false);
  const wsRef = useRef(null);
  const feedEndRef = useRef(null);
  const _seenIds = useRef(new Set());
  const _msgIdCounter = useRef(0);

  // ── WebSocket Connection (dedup-safe for StrictMode) ──
  useEffect(() => {
    let ws;
    let reconnectTimer;
    let didCancel = false;

    const dedup = (data) => {
      // Create a fingerprint from agent + message + timestamp
      const fp = `${data.agent || ''}:${(data.message || '').slice(0, 80)}:${data.timestamp || ''}`;
      if (_seenIds.current.has(fp)) return true; // duplicate
      _seenIds.current.add(fp);
      // Keep set bounded — prune after 500 entries
      if (_seenIds.current.size > 500) {
        const arr = [..._seenIds.current];
        _seenIds.current = new Set(arr.slice(-250));
      }
      return false;
    };

    const connect = () => {
      if (didCancel) return;
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!didCancel) setConnected(true);
      };

      ws.onmessage = (event) => {
        if (didCancel) return;
        const data = JSON.parse(event.data);

        if (data.type === 'init') {
          setMessages(data.history || []);
          setPersuasion(data.persuasion || 5);
        } else if (data.type === 'dialogue') {
          if (!dedup(data)) {
            data._id = ++_msgIdCounter.current;
            setMessages(prev => [...prev, data]);
          }
        } else if (data.type === 'persuasion_update') {
          setPersuasion(data.score);
        } else if (data.type === 'challenge') {
          setActiveChallenge(prev => prev?.challenge_id === data.challenge_id ? prev : data);
          setConvinceMode(true);
        } else if (data.type === 'challenge_resolved') {
          if (data.verdict === 'CONVINCED' || data.verdict === 'OVERRIDE') {
            setActiveChallenge(null);
            setConvinceMode(false);
          }
        }
      };

      ws.onclose = () => {
        if (!didCancel) {
          setConnected(false);
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      didCancel = true;
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // ── Auto-scroll ───────────────────────────────────────
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Send Intervention (Phase 2) ───────────────────────
  const sendIntervention = useCallback(() => {
    if (!inputText.trim() || !wsRef.current) return;

    if (convinceMode && activeChallenge) {
      // Phase 3: Submit as convince reasoning
      fetch(`${API_BASE}/api/warroom/convince`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: activeChallenge.challenge_id,
          reasoning: inputText.trim(),
        }),
      });
    } else {
      wsRef.current.send(JSON.stringify({
        type: 'intervention',
        message: inputText.trim(),
      }));
    }
    setInputText('');
  }, [inputText, convinceMode, activeChallenge]);

  // ── Hard Override (Phase 3 enhanced) ──────────────────
  const sendOverride = useCallback(() => {
    if (activeChallenge) {
      // Phase 3: Structured force proceed
      fetch(`${API_BASE}/api/warroom/force_proceed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: activeChallenge.challenge_id,
          note: inputText.trim() || 'Commander override — proceeding.',
        }),
      });
      setInputText('');
    } else if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'override' }));
    }
  }, [activeChallenge, inputText]);

  // ── Issue Socratic Challenge (Phase 3) ────────────────
  const issueChallenge = useCallback(() => {
    if (!topicInput.trim()) return;
    const score = parseFloat(challengeScore) || persuasion;
    fetch(`${API_BASE}/api/warroom/challenge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        proposal: topicInput.trim(),
        critic_score: score,
      }),
    });
    setTopicInput('');
    setChallengeScore('');
  }, [topicInput, challengeScore, persuasion]);

  // ── Seed Topic (Phase 2) ──────────────────────────────
  const seedTopic = useCallback(() => {
    if (!topicInput.trim()) return;
    fetch(`${API_BASE}/api/warroom/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topicInput.trim() }),
    });
    setTopicInput('');
  }, [topicInput]);

  // ── Helpers ───────────────────────────────────────────
  const getMeterColor = (score) => {
    if (score <= 3) return '#ef4444';
    if (score <= 5) return '#eab308';
    if (score <= 7) return '#f97316';
    return '#22c55e';
  };

  const getMeterLabel = (score) => {
    if (score <= 2) return 'Hostile';
    if (score <= 4) return 'Skeptical';
    if (score <= 6) return 'Neutral';
    if (score <= 8) return 'Receptive';
    return 'Convinced';
  };

  const formatTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div style={styles.container}>
      {/* ── Header ── */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.headerIcon}>🏛️</span>
          <div>
            <h2 style={styles.headerTitle}>Adversarial War Room</h2>
            <span style={styles.headerSub}>
              {convinceMode ? '🔴 STRATEGIC PAUSE — Socratic Challenge Active' : 'Boardroom Socratic Dialogue — Live Feed'}
            </span>
          </div>
        </div>
        <div style={styles.headerRight}>
          {convinceMode && (
            <span style={styles.pauseBadge}>⏸ PAUSED</span>
          )}
          <span style={{
            ...styles.statusDot,
            background: connected ? '#22c55e' : '#ef4444',
            boxShadow: connected ? '0 0 8px rgba(34,197,94,0.5)' : '0 0 8px rgba(239,68,68,0.5)',
          }} />
          <span style={styles.statusText}>{connected ? 'LIVE' : 'RECONNECTING...'}</span>
        </div>
      </div>

      <div style={styles.body}>
        {/* ── Left: Dialogue Feed ── */}
        <div style={styles.feedPanel}>
          {/* Topic Seeder + Challenge Trigger */}
          <div style={styles.topicBar}>
            <input
              type="text"
              value={topicInput}
              onChange={e => setTopicInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && seedTopic()}
              placeholder="Set debate topic / proposal..."
              style={styles.topicInput}
            />
            <input
              type="number"
              value={challengeScore}
              onChange={e => setChallengeScore(e.target.value)}
              placeholder="Score"
              style={{ ...styles.topicInput, width: '70px', flex: 'none', textAlign: 'center' }}
              min="1" max="10" step="0.5"
            />
            <button onClick={seedTopic} style={styles.topicBtn}>🏛️ Debate</button>
            <button onClick={issueChallenge} style={{ ...styles.topicBtn, background: 'linear-gradient(135deg, #ef4444, #dc2626)' }}>🔍 Challenge</button>
          </div>

          {/* Message Feed */}
          <div style={styles.feed}>
            {messages.length === 0 && (
              <div style={styles.emptyState}>
                <span style={{ fontSize: '48px' }}>🏛️</span>
                <p style={{ color: '#64748b', marginTop: '12px' }}>
                  No boardroom session active.<br />
                  <strong>Debate</strong> opens free discussion. <strong>Challenge</strong> triggers Socratic Pause.
                </p>
              </div>
            )}
            {messages.filter(m => m.type === 'dialogue').map((msg, i) => {
              const agentStyle = AGENT_STYLES[msg.agent] || AGENT_STYLES.SYSTEM;
              const isUser = msg.is_user || msg.agent === 'COMMANDER';
              return (
                <div key={i} style={{
                  ...styles.message,
                  background: agentStyle.bg,
                  borderLeft: `3px solid ${agentStyle.color}`,
                  ...(isUser ? { background: 'rgba(249,115,22,0.1)', borderLeft: '3px solid #f97316' } : {}),
                }}>
                  <div style={styles.msgHeader}>
                    <span style={styles.msgIcon}>{agentStyle.icon || msg.icon}</span>
                    <span style={{ ...styles.msgAgent, color: agentStyle.color }}>{msg.agent}</span>
                    <span style={styles.msgTime}>{formatTime(msg.timestamp)}</span>
                    {isUser && <span style={styles.userBadge}>YOU</span>}
                  </div>
                  <p style={styles.msgText}>{msg.message}</p>
                </div>
              );
            })}
            <div ref={feedEndRef} />
          </div>
        </div>

        {/* ── Right: Controls ── */}
        <div style={styles.controlPanel}>
          {/* Persuasion Meter */}
          <div style={styles.meterCard}>
            <h3 style={styles.meterTitle}>Persuasion Meter</h3>
            <p style={styles.meterSub}>Critic's Agreement Level</p>

            <div style={styles.meterGauge}>
              <div style={styles.meterTrack}>
                <div style={{
                  ...styles.meterFill,
                  width: `${(persuasion / 10) * 100}%`,
                  background: `linear-gradient(90deg, #ef4444, ${getMeterColor(persuasion)})`,
                  boxShadow: `0 0 12px ${getMeterColor(persuasion)}40`,
                }} />
                {/* Threshold marker at 9.5 */}
                <div style={styles.thresholdMarker} title="Threshold: 9.5/10" />
              </div>
              <div style={styles.meterLabels}>
                {[1,2,3,4,5,6,7,8,9,10].map(n => (
                  <span key={n} style={{
                    ...styles.meterTick,
                    color: n <= persuasion ? getMeterColor(persuasion) : '#334155',
                    fontWeight: n === persuasion ? 700 : 400,
                  }}>{n}</span>
                ))}
              </div>
            </div>

            <div style={styles.meterScore}>
              <span style={{ fontSize: '42px', fontWeight: 800, color: getMeterColor(persuasion) }}>{persuasion}</span>
              <span style={{ fontSize: '18px', color: '#64748b' }}>/10</span>
            </div>
            <span style={{ ...styles.meterStatus, color: getMeterColor(persuasion) }}>
              {getMeterLabel(persuasion)}
            </span>
            <div style={{ fontSize: '10px', color: '#475569', marginTop: '6px' }}>
              Threshold: 9.5 | {persuasion >= 9.5 ? '✅ Approved' : `Gap: ${(9.5 - persuasion).toFixed(1)}`}
            </div>
          </div>

          {/* Active Challenge Card (Phase 3) */}
          {activeChallenge && (
            <div style={styles.challengeCard}>
              <div style={styles.challengeHeader}>
                <span style={{ fontSize: '16px' }}>🛑</span>
                <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '12px', letterSpacing: '0.5px' }}>STRATEGIC PAUSE</span>
                <span style={styles.challengeId}>{activeChallenge.challenge_id}</span>
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8', margin: '8px 0' }}>
                Score: {activeChallenge.score}/{activeChallenge.threshold} (Gap: {activeChallenge.gap})
              </div>
              {activeChallenge.weaknesses && activeChallenge.weaknesses.map((w, i) => (
                <div key={i} style={styles.weaknessItem}>
                  <div style={styles.weaknessHeader}>
                    <span style={{
                      ...styles.severityBadge,
                      background: `${SEVERITY_COLORS[w.severity] || '#eab308'}20`,
                      color: SEVERITY_COLORS[w.severity] || '#eab308',
                    }}>{w.severity}</span>
                    <span style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 600 }}>{w.category}</span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: '#94a3b8', lineHeight: 1.5 }}>{w.challenge}</p>
                </div>
              ))}
              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '8px', fontStyle: 'italic' }}>
                Address these weaknesses below or Force Proceed.
              </div>
            </div>
          )}

          {/* Intervention Box */}
          <div style={styles.interventionCard}>
            <h3 style={styles.interventionTitle}>
              {convinceMode ? '🏛️ Convince the Critic' : '⚡ Commander Intervention'}
            </h3>
            <p style={styles.interventionSub}>
              {convinceMode
                ? 'Present data & evidence to address the weaknesses above'
                : 'Convince the board or issue a Hard Override'}
            </p>
            <textarea
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendIntervention(); } }}
              placeholder={convinceMode
                ? 'Present your evidence: data, metrics, validated research...'
                : 'Present your argument to the board...'}
              style={{
                ...styles.interventionInput,
                ...(convinceMode ? { borderColor: 'rgba(239,68,68,0.4)', minHeight: '100px' } : {}),
              }}
              rows={convinceMode ? 5 : 4}
            />
            <div style={styles.interventionActions}>
              <button onClick={sendIntervention} style={{
                ...styles.btnPersuade,
                ...(convinceMode ? { background: 'linear-gradient(135deg, #22c55e, #16a34a)' } : {}),
              }} disabled={!inputText.trim()}>
                {convinceMode ? '✅ Submit Evidence' : '💬 Persuade'}
              </button>
              <button onClick={sendOverride} style={styles.btnOverride}>
                🚨 {convinceMode ? 'Force Proceed' : 'Hard Override'}
              </button>
            </div>
            {convinceMode && (
              <p style={{ fontSize: '10px', color: '#64748b', marginTop: '8px' }}>
                💡 Tip: Use data-driven language — "metrics show", "validated by", "A/B test results"
              </p>
            )}
          </div>

          {/* Active Agents */}
          <div style={styles.agentList}>
            <h4 style={styles.agentListTitle}>Board Members</h4>
            {Object.entries(AGENT_STYLES).filter(([k]) => k !== 'COMMANDER' && k !== 'SYSTEM').map(([name, s]) => (
              <div key={name} style={styles.agentItem}>
                <span style={{ fontSize: '18px' }}>{s.icon}</span>
                <span style={{ color: s.color, fontWeight: 600, fontSize: '13px' }}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  STYLES
// ═══════════════════════════════════════════════════════════
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 140px)',
    borderRadius: '14px',
    overflow: 'hidden',
    background: 'rgba(10, 14, 23, 0.6)',
    border: '1px solid rgba(100,116,139,0.15)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.06))',
    borderBottom: '1px solid rgba(100,116,139,0.15)',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '12px' },
  headerIcon: { fontSize: '28px' },
  headerTitle: { margin: 0, fontSize: '18px', fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.3px' },
  headerSub: { fontSize: '12px', color: '#64748b' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '8px' },
  statusDot: { width: '8px', height: '8px', borderRadius: '50%' },
  statusText: { fontSize: '11px', fontWeight: 600, letterSpacing: '1px', color: '#94a3b8' },
  pauseBadge: {
    padding: '3px 10px', borderRadius: '6px', fontSize: '10px', fontWeight: 700,
    background: 'rgba(239,68,68,0.15)', color: '#ef4444', letterSpacing: '0.5px',
    animation: 'pulse 2s infinite',
  },

  body: { display: 'flex', flex: 1, overflow: 'hidden' },

  // ── Feed Panel ──
  feedPanel: { flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(100,116,139,0.12)' },
  topicBar: {
    display: 'flex', gap: '8px', padding: '12px 16px',
    borderBottom: '1px solid rgba(100,116,139,0.1)',
    background: 'rgba(15,23,42,0.4)',
    flexWrap: 'wrap',
  },
  topicInput: {
    flex: 1, padding: '8px 14px', borderRadius: '8px',
    border: '1px solid rgba(100,116,139,0.2)', background: 'rgba(0,0,0,0.3)',
    color: '#e2e8f0', fontSize: '13px', outline: 'none',
    fontFamily: 'Inter, sans-serif',
  },
  topicBtn: {
    padding: '8px 16px', borderRadius: '8px', border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', color: 'white',
    fontSize: '12px', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
    fontFamily: 'Inter, sans-serif',
  },
  feed: {
    flex: 1, overflowY: 'auto', padding: '16px',
    display: 'flex', flexDirection: 'column', gap: '8px',
  },
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', textAlign: 'center',
  },

  // ── Messages ──
  message: {
    padding: '12px 16px', borderRadius: '10px',
    transition: 'all 0.2s',
  },
  msgHeader: {
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px',
  },
  msgIcon: { fontSize: '16px' },
  msgAgent: { fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' },
  msgTime: { fontSize: '10px', color: '#475569', marginLeft: 'auto' },
  userBadge: {
    padding: '1px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: 700,
    background: 'rgba(249,115,22,0.2)', color: '#f97316', letterSpacing: '0.5px',
  },
  msgText: { margin: 0, fontSize: '13.5px', lineHeight: 1.6, color: '#cbd5e1' },

  // ── Control Panel ──
  controlPanel: {
    width: '320px', display: 'flex', flexDirection: 'column', gap: '0',
    background: 'rgba(15,23,42,0.3)', overflowY: 'auto',
  },

  // ── Meter ──
  meterCard: {
    padding: '24px 20px', textAlign: 'center',
    borderBottom: '1px solid rgba(100,116,139,0.12)',
  },
  meterTitle: { margin: 0, fontSize: '15px', fontWeight: 700, color: '#f1f5f9' },
  meterSub: { margin: '4px 0 20px', fontSize: '11px', color: '#64748b' },
  meterGauge: { marginBottom: '12px' },
  meterTrack: {
    height: '8px', borderRadius: '4px', background: 'rgba(100,116,139,0.15)',
    overflow: 'visible', marginBottom: '8px', position: 'relative',
  },
  meterFill: {
    height: '100%', borderRadius: '4px', transition: 'width 0.6s ease, background 0.6s ease',
  },
  thresholdMarker: {
    position: 'absolute', top: '-3px', left: '95%',
    width: '2px', height: '14px', background: '#f1f5f9',
    borderRadius: '1px', opacity: 0.6,
  },
  meterLabels: { display: 'flex', justifyContent: 'space-between', padding: '0 2px' },
  meterTick: { fontSize: '10px', fontFamily: 'JetBrains Mono, monospace', transition: 'color 0.3s' },
  meterScore: { display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: '2px', margin: '8px 0 4px' },
  meterStatus: { fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1.5px' },

  // ── Challenge Card (Phase 3) ──
  challengeCard: {
    margin: '0', padding: '16px 20px',
    background: 'rgba(239,68,68,0.05)',
    borderBottom: '1px solid rgba(239,68,68,0.15)',
    borderTop: '1px solid rgba(239,68,68,0.15)',
  },
  challengeHeader: {
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px',
  },
  challengeId: {
    marginLeft: 'auto', fontSize: '10px', fontFamily: 'JetBrains Mono, monospace',
    color: '#475569', background: 'rgba(0,0,0,0.2)', padding: '2px 6px', borderRadius: '4px',
  },
  weaknessItem: {
    padding: '8px 10px', marginTop: '6px', borderRadius: '8px',
    background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(100,116,139,0.1)',
  },
  weaknessHeader: {
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  severityBadge: {
    padding: '1px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: 700,
    letterSpacing: '0.5px',
  },

  // ── Intervention ──
  interventionCard: {
    padding: '20px',
    borderBottom: '1px solid rgba(100,116,139,0.12)',
  },
  interventionTitle: { margin: 0, fontSize: '14px', fontWeight: 700, color: '#f1f5f9' },
  interventionSub: { margin: '4px 0 12px', fontSize: '11px', color: '#64748b' },
  interventionInput: {
    width: '100%', padding: '10px 14px', borderRadius: '10px',
    border: '1px solid rgba(100,116,139,0.2)', background: 'rgba(0,0,0,0.3)',
    color: '#e2e8f0', fontSize: '13px', resize: 'none', outline: 'none',
    fontFamily: 'Inter, sans-serif', lineHeight: 1.5, boxSizing: 'border-box',
  },
  interventionActions: { display: 'flex', gap: '8px', marginTop: '10px' },
  btnPersuade: {
    flex: 1, padding: '10px', borderRadius: '8px', border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #6366f1)', color: 'white',
    fontSize: '13px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif',
    opacity: 1, transition: 'opacity 0.2s',
  },
  btnOverride: {
    padding: '10px 16px', borderRadius: '8px',
    border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.1)',
    color: '#ef4444', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif',
  },

  // ── Agent List ──
  agentList: { padding: '16px 20px' },
  agentListTitle: { margin: '0 0 10px', fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' },
  agentItem: {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0',
  },
};
