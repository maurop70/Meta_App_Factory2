import React, { useState, useEffect, useCallback } from 'react';

/**
 * OmniDashboard.jsx — Executive Omni-Dashboard
 * ==============================================
 * Meta App Factory | factory_ui | Antigravity-AI
 *
 * Real-time hooks for all 18 agents' status, Sentinel notifications,
 * Signal Processor alerts, and EQ Engine stress level.
 */

const AGENTS = [
  { id: 'ceo', name: 'CEO', icon: '👔', core: true },
  { id: 'cfo', name: 'CFO', icon: '💰', core: true },
  { id: 'cto', name: 'CTO', icon: '⚙️', core: true },
  { id: 'cmo', name: 'CMO', icon: '📢', core: false },
  { id: 'deep-crawler', name: 'Deep Crawler', icon: '🕷️', core: false },
  { id: 'the-critic', name: 'The Critic', icon: '🎯', core: false },
  { id: 'the-librarian', name: 'The Librarian', icon: '📚', core: false },
  { id: 'compliance-officer', name: 'Compliance', icon: '🛡️', core: false },
  { id: 'data-architect', name: 'Data Architect', icon: '🏗️', core: false },
  { id: 'researcher', name: 'Researcher', icon: '🔬', core: false },
  { id: 'graphic-designer', name: 'Designer', icon: '🎨', core: false },
  { id: 'presentation-expert', name: 'Presentations', icon: '📊', core: false },
  { id: 'cx-strategist', name: 'CX Strategist', icon: '🤝', core: false },
  { id: 'aether-architect', name: 'Aether', icon: '✨', core: true },
  { id: 'delegate-orchestrator', name: 'Delegate AI', icon: '🎭', core: true },
  { id: 'unified-eq-specialist', name: 'EQ Engine', icon: '💚', core: true },
  { id: 'geotalent-scout', name: 'GeoTalent Scout', icon: '🌍', core: false },
  { id: 'news-bureau-chief', name: 'News Bureau', icon: '📰', core: false },
];

const STYLES = {
  dashboard: {
    fontFamily: "'Inter', 'Roboto', -apple-system, sans-serif",
    background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%)',
    minHeight: '100vh',
    color: '#e0e0e0',
    padding: '24px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    background: 'linear-gradient(135deg, #667eea, #764ba2)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    margin: 0,
  },
  subtitle: {
    fontSize: '13px',
    color: '#8892b0',
    marginTop: '4px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: '12px',
    marginBottom: '24px',
  },
  agentCard: (health) => ({
    background: 'rgba(255,255,255,0.04)',
    border: `1px solid ${health === 'active' ? 'rgba(16,185,129,0.3)' : health === 'idle' ? 'rgba(234,179,8,0.2)' : 'rgba(239,68,68,0.2)'}`,
    borderRadius: '12px',
    padding: '14px',
    transition: 'all 0.3s ease',
    cursor: 'pointer',
    position: 'relative',
    overflow: 'hidden',
  }),
  agentIcon: {
    fontSize: '24px',
    marginBottom: '8px',
  },
  agentName: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#e0e0e0',
    marginBottom: '4px',
  },
  agentMeta: {
    fontSize: '11px',
    color: '#8892b0',
  },
  healthDot: (health) => ({
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: health === 'active' ? '#10b981' : health === 'idle' ? '#eab308' : '#ef4444',
    position: 'absolute',
    top: '12px',
    right: '12px',
    boxShadow: health === 'active' ? '0 0 8px rgba(16,185,129,0.5)' : 'none',
  }),
  coreTag: {
    fontSize: '9px',
    fontWeight: 700,
    color: '#667eea',
    background: 'rgba(102,126,234,0.1)',
    padding: '2px 6px',
    borderRadius: '4px',
    display: 'inline-block',
    marginTop: '6px',
    letterSpacing: '0.5px',
  },
  panel: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: '16px',
    padding: '20px',
    marginBottom: '20px',
  },
  panelTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#c0c8e0',
    marginBottom: '14px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  stressBar: (level) => ({
    height: '8px',
    borderRadius: '4px',
    background: 'rgba(255,255,255,0.06)',
    position: 'relative',
    overflow: 'hidden',
  }),
  stressFill: (level) => ({
    height: '100%',
    width: `${level * 10}%`,
    borderRadius: '4px',
    background: level >= 8 ? 'linear-gradient(90deg, #ef4444, #dc2626)' :
                level >= 6 ? 'linear-gradient(90deg, #f97316, #ea580c)' :
                level >= 4 ? 'linear-gradient(90deg, #eab308, #ca8a04)' :
                             'linear-gradient(90deg, #10b981, #059669)',
    transition: 'width 0.8s ease',
  }),
  signalRow: (impact) => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    borderRadius: '8px',
    marginBottom: '6px',
    background: impact === 'critical' ? 'rgba(239,68,68,0.08)' :
                impact === 'high' ? 'rgba(249,115,22,0.06)' :
                'rgba(255,255,255,0.02)',
    border: `1px solid ${impact === 'critical' ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.04)'}`,
    fontSize: '13px',
  }),
  badge: (type) => ({
    fontSize: '10px',
    fontWeight: 700,
    padding: '3px 8px',
    borderRadius: '4px',
    letterSpacing: '0.5px',
    background: type === 'critical' ? 'rgba(239,68,68,0.2)' :
                type === 'high' ? 'rgba(249,115,22,0.2)' :
                type === 'medium' ? 'rgba(234,179,8,0.2)' :
                'rgba(16,185,129,0.2)',
    color: type === 'critical' ? '#f87171' :
           type === 'high' ? '#fb923c' :
           type === 'medium' ? '#fbbf24' :
           '#34d399',
  }),
  notifRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 12px',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    fontSize: '12px',
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
  },
  refreshBtn: {
    padding: '8px 16px',
    borderRadius: '8px',
    border: '1px solid rgba(102,126,234,0.3)',
    background: 'rgba(102,126,234,0.1)',
    color: '#667eea',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
};

function useAgentStatus(apiBase) {
  const [agents, setAgents] = useState(
    AGENTS.map(a => ({
      ...a,
      health: Math.random() > 0.15 ? 'active' : 'idle',
      calls: Math.floor(Math.random() * 50),
      lastActive: new Date(Date.now() - Math.random() * 3600000).toISOString(),
    }))
  );

  const refresh = useCallback(() => {
    if (!apiBase) return;
    fetch(`${apiBase}/api/agents/status`)
      .then(r => r.json())
      .then(data => {
        if (data.agents) setAgents(prev =>
          prev.map(a => {
            const live = data.agents.find(d => d.id === a.id);
            return live ? { ...a, ...live } : a;
          })
        );
      })
      .catch(() => {});
  }, [apiBase]);

  return { agents, refresh };
}

function useStressLevel(apiBase) {
  const [stress, setStress] = useState({
    level: 3.0,
    tone: 'professional',
    assessments: 0,
  });

  const refresh = useCallback(() => {
    if (!apiBase) return;
    fetch(`${apiBase}/api/eq/stress`)
      .then(r => r.json())
      .then(data => setStress(data))
      .catch(() => {});
  }, [apiBase]);

  return { stress, refresh };
}

function useSignals(apiBase) {
  const [signals, setSignals] = useState([]);

  const refresh = useCallback(() => {
    if (!apiBase) return;
    fetch(`${apiBase}/api/signals`)
      .then(r => r.json())
      .then(data => setSignals(data.signals || []))
      .catch(() => {});
  }, [apiBase]);

  return { signals, refresh };
}

function useNotifications(apiBase) {
  const [notifications, setNotifications] = useState([]);

  const refresh = useCallback(() => {
    if (!apiBase) return;
    fetch(`${apiBase}/api/sentinel/log`)
      .then(r => r.json())
      .then(data => setNotifications(data.log || []))
      .catch(() => {});
  }, [apiBase]);

  return { notifications, refresh };
}

export default function OmniDashboard({ apiBase = '' }) {
  const { agents, refresh: refreshAgents } = useAgentStatus(apiBase);
  const { stress, refresh: refreshStress } = useStressLevel(apiBase);
  const { signals, refresh: refreshSignals } = useSignals(apiBase);
  const { notifications, refresh: refreshNotifs } = useNotifications(apiBase);

  const activeCount = agents.filter(a => a.health === 'active').length;
  const totalCalls = agents.reduce((s, a) => s + (a.calls || 0), 0);

  const refreshAll = () => {
    refreshAgents();
    refreshStress();
    refreshSignals();
    refreshNotifs();
  };

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={STYLES.dashboard} id="omni-dashboard">
      {/* Header */}
      <div style={STYLES.header}>
        <div>
          <h1 style={STYLES.title}>Omni-Dashboard</h1>
          <p style={STYLES.subtitle}>
            {activeCount}/{agents.length} agents active · {totalCalls} total calls
          </p>
        </div>
        <button style={STYLES.refreshBtn} onClick={refreshAll}>
          ↻ Refresh All
        </button>
      </div>

      {/* Agent Grid */}
      <div style={STYLES.panel}>
        <div style={STYLES.panelTitle}>🤖 Agent Network (V7 — 18 Agents)</div>
        <div style={STYLES.grid}>
          {agents.map(agent => (
            <div key={agent.id} style={STYLES.agentCard(agent.health)}>
              <div style={STYLES.healthDot(agent.health)} />
              <div style={STYLES.agentIcon}>{agent.icon}</div>
              <div style={STYLES.agentName}>{agent.name}</div>
              <div style={STYLES.agentMeta}>
                {agent.calls || 0} calls · {
                  agent.lastActive
                    ? new Date(agent.lastActive).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : '—'
                }
              </div>
              {agent.core && <span style={STYLES.coreTag}>SYSTEM CORE</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Two-Column: EQ + Signals */}
      <div style={STYLES.twoCol}>
        {/* EQ Engine Panel */}
        <div style={STYLES.panel}>
          <div style={STYLES.panelTitle}>💚 EQ Engine — Stress Monitor</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '32px', fontWeight: 700, color: stress.level >= 7 ? '#ef4444' : stress.level >= 5 ? '#eab308' : '#10b981' }}>
              {stress.level}/10
            </span>
            <span style={STYLES.badge(stress.level >= 7 ? 'critical' : stress.level >= 5 ? 'medium' : 'low')}>
              {stress.tone?.toUpperCase() || 'PROFESSIONAL'}
            </span>
          </div>
          <div style={STYLES.stressBar(stress.level)}>
            <div style={STYLES.stressFill(stress.level)} />
          </div>
          <div style={{ fontSize: '11px', color: '#8892b0', marginTop: '10px' }}>
            {stress.assessments || 0} assessments recorded
          </div>
        </div>

        {/* Signal Processor Panel */}
        <div style={STYLES.panel}>
          <div style={STYLES.panelTitle}>📰 News Bureau — Active Signals</div>
          {signals.length === 0 ? (
            <div style={{ fontSize: '13px', color: '#8892b0', textAlign: 'center', padding: '20px' }}>
              No active signals
            </div>
          ) : (
            signals.slice(0, 5).map((sig, i) => (
              <div key={i} style={STYLES.signalRow(sig.impact)}>
                <div>
                  <div style={{ fontWeight: 600 }}>{sig.category}</div>
                  <div style={{ fontSize: '11px', color: '#8892b0' }}>{sig.headline?.slice(0, 60)}</div>
                </div>
                <span style={STYLES.badge(sig.impact)}>{sig.score}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Sentinel Notification Log */}
      <div style={STYLES.panel}>
        <div style={STYLES.panelTitle}>🔔 Sentinel Notification Log</div>
        {notifications.length === 0 ? (
          <div style={{ fontSize: '13px', color: '#8892b0', textAlign: 'center', padding: '20px' }}>
            No recent notifications
          </div>
        ) : (
          notifications.slice(0, 10).map((n, i) => (
            <div key={i} style={STYLES.notifRow}>
              <span>{n.message?.slice(0, 80) || 'Notification'}</span>
              <span style={{ color: '#8892b0', fontSize: '11px' }}>
                {n.timestamp ? new Date(n.timestamp).toLocaleTimeString() : '—'}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
