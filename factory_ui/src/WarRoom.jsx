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
  DR_ARIS:   { icon: '🩻', color: '#14b8a6', bg: 'rgba(20,184,166,0.08)' },
  SYSTEM:    { icon: '⚡', color: '#eab308', bg: 'rgba(234,179,8,0.08)' },
  COMMANDER: { icon: '⚡', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
};

const SEVERITY_COLORS = {
  CRITICAL: '#ef4444',
  SIGNIFICANT: '#f97316',
  MODERATE: '#eab308',
};

export default function WarRoom({ ventureMode = false, onHandoff, projectName = 'Aether' }) {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [eosState, setEosState] = useState(null);
  const [persuasion, setPersuasion] = useState(5);
  const [connected, setConnected] = useState(false);
  const [topicInput, setTopicInput] = useState('');
  // Phase 3 state
  const [activeChallenge, setActiveChallenge] = useState(null);
  const [challengeScore, setChallengeScore] = useState('');
  const [convinceMode, setConvinceMode] = useState(false);
  // UPGRADE 2: History state
  const [showHistory, setShowHistory] = useState(false);
  const [historySessions, setHistorySessions] = useState([]);
  // UPGRADE: Outcome Decision Flow
  const [outcomeProposal, setOutcomeProposal] = useState(null);
  const [implementationPlan, setImplementationPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const wsRef = useRef(null);
  const feedEndRef = useRef(null);
  const fileRef = useRef(null);
  const _seenIds = useRef(new Set());
  const _msgIdCounter = useRef(0);

  // Load history
  const loadHistory = () => {
    setHistoryLoading(true);
    fetch(`${API_BASE}/api/warroom/history?project_name=${encodeURIComponent(projectName)}`)
      .then(r => r.json())
      .then(data => setHistorySessions(data.sessions || []))
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  };

  // ── EOS Polling (Phase Tracker) ───────────────────────
  useEffect(() => {
    if (!ventureMode) return;
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/eos/state?project_name=${encodeURIComponent(projectName)}`)
        .then(r => r.json())
        .then(setEosState)
        .catch(() => {});
    }, 2000);
    return () => clearInterval(interval);
  }, [ventureMode, projectName]);

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
      ws = new WebSocket(`${WS_URL}?project=${encodeURIComponent(projectName)}`);
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
        } else if (data.type === 'outcome_proposal') {
          setOutcomeProposal(data);
        } else if (data.type === 'implementation_plan') {
          setImplementationPlan(data);
          setGeneratingPlan(false);
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
  }, [projectName]);

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
          project_name: projectName,
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
          project_name: projectName,
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
        project_name: projectName,
        proposal: topicInput.trim(),
        critic_score: score,
      }),
    });
    setTopicInput('');
    setChallengeScore('');
  }, [topicInput, challengeScore, persuasion, projectName]);

  // ── Seed Topic (Phase 2) ──────────────────────────────
  const seedTopic = useCallback(() => {
    if (!topicInput.trim()) return;
    fetch(`${API_BASE}/api/warroom/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_name: projectName, topic: topicInput.trim() }),
    });
    setTopicInput('');
  }, [topicInput, projectName]);

  // ── 🆕 EOS Action Trigger ─────────────────────────────
  const triggerEosAction = useCallback((cmd) => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'intervention', message: cmd }));
    }
  }, []);

  // ── 🆕 Upload Handler ─────────────────────────────────
  const uploadFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || uploading) return;
    e.target.value = '';
    
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('project_name', projectName);
    
    try {
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'intervention', message: `Uploading document: ${file.name}...` }));
      }
      await fetch(`${API_BASE}/api/warroom/upload`, { method: 'POST', body: fd });
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setUploading(false);
    }
  };

  // ── Outcome Decision Handlers ──────────────────────────
  const handleOutcomeChoice = async (choice) => {
    if (choice === 'dismiss') {
      setOutcomeProposal(null);
      return;
    }
    setGeneratingPlan(true);
    setOutcomeProposal(null);
    try {
      await fetch(`${API_BASE}/api/warroom/execute_outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: projectName, outcome_type: choice }),
      });
    } catch (err) {
      console.error('Outcome execution failed', err);
      setGeneratingPlan(false);
    }
  };

  const approvePlan = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'intervention',
        message: `✅ APPROVED: Implementation plan for ${implementationPlan?.outcome_type?.toUpperCase() || 'UPDATE'}. Proceeding to build.`,
      }));
    }
    if (implementationPlan?.outcome_type === 'new' && onHandoff) {
      onHandoff({ plan: implementationPlan.plan });
    }
    setImplementationPlan(null);
  };

  const rejectPlan = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'intervention',
        message: '❌ REJECTED: Implementation plan needs revision. Re-entering deliberation.',
      }));
    }
    setImplementationPlan(null);
  };

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
          <button
            onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}
            style={{
              padding: '4px 12px', borderRadius: '6px', border: '1px solid rgba(100,116,139,0.3)',
              background: showHistory ? 'rgba(99,102,241,0.15)' : 'rgba(0,0,0,0.2)',
              color: showHistory ? '#818cf8' : '#94a3b8', fontSize: '11px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginRight: '8px',
            }}
          >📜 History</button>
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
        {/* ── History Panel (Upgrade 2) ── */}
        {showHistory && (
          <div style={{
            width: '280px', borderRight: '1px solid rgba(100,116,139,0.12)',
            background: 'rgba(15,23,42,0.4)', overflowY: 'auto', padding: '12px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700, color: '#f1f5f9' }}>📜 Past Debates</h4>
              <span style={{ fontSize: '10px', color: '#64748b' }}>{historySessions.length} sessions</span>
            </div>
            {historyLoading && <p style={{ fontSize: '11px', color: '#64748b' }}>Loading...</p>}
            {historySessions.map((session, i) => (
              <div key={i} style={{
                padding: '10px', marginBottom: '6px', borderRadius: '8px',
                background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(100,116,139,0.1)',
                cursor: 'pointer',
              }}
              onClick={() => {
                setMessages(session.messages);
                setShowHistory(false);
              }}
              >
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  {session.topic?.slice(0, 60) || 'Untitled'}
                </div>
                <div style={{ fontSize: '10px', color: '#64748b' }}>
                  {session.messages?.length || 0} messages • {session.started ? new Date(session.started).toLocaleDateString() : ''}
                </div>
              </div>
            ))}
            {historySessions.length === 0 && !historyLoading && (
              <p style={{ fontSize: '11px', color: '#475569', textAlign: 'center', marginTop: '20px' }}>
                No debate history yet.
              </p>
            )}
          </div>
        )}
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
            <button onClick={() => fileRef.current?.click()} disabled={uploading} style={{ ...styles.topicBtn, background: uploading ? '#64748b' : 'linear-gradient(135deg, #10b981, #059669)' }}>
              {uploading ? '⏳' : '📎 Upload'}
            </button>
            <input type="file" ref={fileRef} onChange={uploadFile} style={{ display: 'none' }} />
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

            {/* UPGRADE V3.3: Phase Tracker & Handoff */}
            {ventureMode && eosState && (
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '16px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                  📈 Venture Progress
                </div>
                
                {['market', 'brand', 'legal', 'business_plan', 'financials', 'funding', 'pitch'].map(phase => {
                  const status = eosState.phase_status?.[phase] || 'pending';
                  const isLocked = status === 'locked';
                  return (
                    <div key={phase} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px', padding: '4px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                      <span style={{ textTransform: 'capitalize', color: '#cbd5e1' }}>{phase.replace('_', ' ')}</span>
                      <span style={{ 
                        color: isLocked ? '#10b981' : status === 'iterating' ? '#eab308' : status === 'deadlocked' ? '#ef4444' : '#64748b',
                        fontWeight: isLocked ? 700 : 400 
                      }}>
                        {isLocked ? '✅ Locked' : status === 'iterating' ? '🔄 Iterating' : status === 'deadlocked' ? '🚨 Deadlocked' : '⏳ Pending'}
                      </span>
                    </div>
                  );
                })}

                {eosState.phase_status?.market === 'locked' && 
                 eosState.phase_status?.brand === 'locked' && 
                 eosState.phase_status?.legal === 'locked' && 
                 eosState.phase_status?.business_plan === 'locked' && 
                 eosState.phase_status?.financials === 'locked' && (
                  <button 
                    onClick={() => onHandoff?.(eosState)}
                    style={{
                      width: '100%', padding: '12px', marginTop: '12px', borderRadius: '8px', border: 'none',
                      background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: 'white',
                      fontSize: '13px', fontWeight: 700, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                      boxShadow: '0 4px 14px rgba(34,197,94,0.3)', animation: 'pulse 2s infinite'
                    }}>
                    🚀 APPROVE PLAN & SEND TO BUILDER
                  </button>
                )}
              </div>
            )}

            {ventureMode && !convinceMode && (
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '16px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                  🚀 Venture Architect Commands
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <button onClick={() => triggerEosAction('/market')} style={styles.btnEos}>1. Market Intel</button>
                  <button onClick={() => triggerEosAction('/brand')} style={styles.btnEos}>2. Brand DNA</button>
                  <button onClick={() => triggerEosAction('/legal')} style={styles.btnEos}>3. Legal & IP</button>
                  <button onClick={() => triggerEosAction('/financials')} style={styles.btnEos}>4. Financials</button>
                  <button onClick={() => triggerEosAction('/business-plan')} style={styles.btnEos}>5. Business Plan</button>
                  <button onClick={() => triggerEosAction('/funding')} style={styles.btnEos}>6. Funding Strat</button>
                  <button onClick={() => triggerEosAction('/pitch')} style={{ ...styles.btnEos, gridColumn: 'span 2', background: 'rgba(244,63,94,0.1)', color: '#f43f5e', borderColor: 'rgba(244,63,94,0.3)' }}>
                    7. Validate & Export Start-Up Decks
                  </button>
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', marginTop: '8px', fontStyle: 'italic', lineHeight: 1.4 }}>
                  Click to execute EOS workstreams. Tell the CEO your company name and industry first.
                </div>
              </div>
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

      {/* ── Outcome Decision Modal ── */}
      {outcomeProposal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={{ fontSize: '48px', textAlign: 'center', marginBottom: '16px' }}>🎯</div>
            <h2 style={{ color: '#22c55e', margin: '0 0 8px', fontSize: '20px', textAlign: 'center' }}>CONSENSUS REACHED</h2>
            <p style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'center', marginBottom: '20px' }}>
              The board finalized <strong style={{ color: '#e2e8f0' }}>{outcomeProposal.summary?.deliverables_count || 0}</strong> deliverables
              for <strong style={{ color: '#e2e8f0' }}>{outcomeProposal.summary?.company_name}</strong>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button onClick={() => handleOutcomeChoice('update')} style={{ ...styles.outcomeBtn, background: 'linear-gradient(135deg, #3b82f6, #6366f1)' }}>
                🔄 Update Existing Product
                <span style={{ display: 'block', fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>Merge deliverables into the current codebase</span>
              </button>
              <button onClick={() => handleOutcomeChoice('new')} style={{ ...styles.outcomeBtn, background: 'linear-gradient(135deg, #22c55e, #16a34a)' }}>
                🆕 Create New Product
                <span style={{ display: 'block', fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>Spin up a fresh build from these deliverables</span>
              </button>
              <button onClick={() => handleOutcomeChoice('dismiss')} style={{ ...styles.outcomeBtn, background: 'rgba(100,116,139,0.2)', border: '1px solid rgba(100,116,139,0.3)' }}>
                📦 Dismiss — Archive for Later
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Implementation Plan Viewer ── */}
      {implementationPlan && (
        <div style={styles.modalOverlay}>
          <div style={{ ...styles.modalContent, maxWidth: '700px', maxHeight: '80vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ color: '#6366f1', margin: 0, fontSize: '18px' }}>📋 Implementation Plan ({implementationPlan.outcome_type?.toUpperCase()})</h2>
              <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}>{implementationPlan.project_name}</span>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '10px', padding: '16px', fontSize: '13px', color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap', fontFamily: 'Inter, sans-serif', maxHeight: '50vh', overflow: 'auto' }}>
              {implementationPlan.plan}
            </div>
            <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'center' }}>
              <button onClick={approvePlan} style={{ padding: '12px 32px', borderRadius: '10px', border: 'none', background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: 'white', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                ✅ Approve & Execute
              </button>
              <button onClick={rejectPlan} style={{ padding: '12px 32px', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.1)', color: '#ef4444', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                ❌ Reject & Revise
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Generating Plan Spinner ── */}
      {generatingPlan && (
        <div style={styles.modalOverlay}>
          <div style={{ ...styles.modalContent, textAlign: 'center', maxWidth: '400px' }}>
            <div style={{ fontSize: '48px', animation: 'pulse 2s infinite' }}>🧠</div>
            <h3 style={{ color: '#e2e8f0', margin: '12px 0 4px' }}>Generating Implementation Plan...</h3>
            <p style={{ color: '#64748b', fontSize: '12px' }}>Claude is analyzing the deliverables and structuring the plan.</p>
          </div>
        </div>
      )}
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

  // ── EOS Buttons ──
  btnEos: {
    padding: '8px', borderRadius: '6px',
    border: '1px solid rgba(148,163,184,0.2)', background: 'rgba(0,0,0,0.2)',
    color: '#cbd5e1', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', textAlign: 'center',
    transition: 'all 0.2s',
  },

  // ── Modals ──
  modalOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
    backdropFilter: 'blur(8px)',
  },
  modalContent: {
    background: 'linear-gradient(135deg, #1e1b3a, #0f172a)',
    border: '1px solid rgba(99,102,241,0.3)', borderRadius: '16px',
    padding: '32px', maxWidth: '480px', width: '90%',
  },
  outcomeBtn: {
    width: '100%', padding: '14px 20px', borderRadius: '10px', border: 'none',
    color: 'white', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', textAlign: 'center',
  },
};
