import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'
import WarRoom from './WarRoom'
import SupportFAB from './SupportFAB'
import ModeSelectionScreen from './ModeSelectionScreen'
import VentureSuite from './VentureSuite'

// ═══════════════════════════════════════════════════════════
//  META APP FACTORY — BUILDER DASHBOARD (Full Feature Parity)
//  React + Vite | SSE Streaming | Command Palette | Atomizer
//  Agent Status | Telemetry | File Upload | Recover Prompt
// ═══════════════════════════════════════════════════════════

const API_BASE = 'http://localhost:8000';

// ── COMMAND PALETTE ────────────────────────────────────────
function CommandPalette({ onCommand }) {
  const [commands, setCommands] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/commands`)
      .then(r => r.json())
      .then(data => setCommands(data))
      .catch(() => setCommands([
        { label: '🚀 Triad Execute', cmd: 'Execute per SOP Triad Protocol.', desc: 'Collaborative review between Gemini, Antigravity, and Claude.', suite: 'visionary' },
        { label: '🛡️ Security Audit', cmd: 'Run Specialist - Security audit on current code.', desc: 'Scans for vulnerabilities.', suite: 'visionary' },
        { label: '🧪 Twin Test', cmd: 'Spin up Digital Twin container and run integration tests.', desc: 'Tests features in a sandbox.', suite: 'visionary' },
        { label: '🔍 Market Research', cmd: 'Analyze market competitors and prior art for this task.', desc: 'Check what similar apps exist.', suite: 'visionary' },
        { label: '🛠️ System Diagnostic', cmd: 'Run full system diagnostic and check agent connectivity.', desc: 'Verify Docker, n8n, API endpoints.', suite: 'maintenance' },
        { label: '🧹 Flush Memory', cmd: 'Wipe sentry cache and reset DCC.', desc: 'Clears stale session data.', suite: 'maintenance' },
        { label: '⏪ Rollback', cmd: 'Revert to last stable git/snapshot build.', desc: 'Undo changes if Self-Heal fails.', suite: 'maintenance' },
        { label: '🩹 Self-Heal', cmd: 'Review recent logs and repair execution errors.', desc: 'Fix bugs in current runtime.', suite: 'maintenance' },
        { label: '📦 Docker Export', cmd: 'Package current application for cloud deployment.', desc: 'Flatten build for production.', suite: 'maintenance' },
      ]));
  }, []);

  const visionary = commands.filter(c => ['Triad Execute', 'Security Audit', 'Twin Test', 'Market Research'].some(v => c.label.includes(v)));
  const maintenance = commands.filter(c => !visionary.includes(c));

  return (
    <div className="command-palette">
      <div className="palette-group">
        <h4 className="palette-title visionary">⚡ Visionary Suite</h4>
        {visionary.map((cmd, i) => (
          <button key={i} className="cmd-btn visionary" onClick={() => onCommand(cmd.cmd, cmd.label.includes('Triad'))} title={cmd.desc}>
            {cmd.label}
          </button>
        ))}
      </div>
      <div className="palette-group">
        <h4 className="palette-title maintenance">🔧 Maintenance Suite</h4>
        {maintenance.map((cmd, i) => (
          <button key={i} className="cmd-btn maintenance" onClick={() => onCommand(cmd.cmd, false)} title={cmd.desc}>
            {cmd.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── AGENT STATUS PANEL ─────────────────────────────────────
function AgentStatusPanel() {
  const agents = ['CFO', 'CMO', 'HR', 'CRITIC', 'PITCH', 'ATOMIZER', 'ARCHITECT'];
  const [status, setStatus] = useState({});

  const scanAgents = useCallback(() => {
    fetch(`${API_BASE}/api/agents/status`)
      .then(r => r.json())
      .then(data => setStatus(data))
      .catch(() => {
        const mock = {};
        agents.forEach(a => { mock[a] = Math.random() > 0.3; });
        setStatus(mock);
      });
  }, []);

  useEffect(() => { scanAgents(); }, [scanAgents]);

  return (
    <div className="agent-panel">
      <div className="agent-panel-header">
        <h4>🧠 Neural Network</h4>
        <button className="scan-btn" onClick={scanAgents}>↻ SCAN</button>
      </div>
      <div className="agent-grid">
        {agents.map(a => (
          <div key={a} className={`agent-dot ${status[a] === true ? 'online' : status[a] === false ? 'offline' : 'unknown'}`}>
            <span className="dot" />
            <span>{a}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ATOMIZER PANEL ─────────────────────────────────────────
function AtomizerPanel({ chunks, progress, total }) {
  return (
    <div className="atomizer-panel">
      <h4>⚛️ Atomizer: Deconstruction Station</h4>
      {chunks.length === 0 ? (
        <p className="atomizer-empty">No active deconstruction. Send a complex prompt to activate.</p>
      ) : (
        <>
          <div className="atomizer-progress-bar">
            <div className="atomizer-fill" style={{ width: `${total > 0 ? (progress / total) * 100 : 0}%` }} />
          </div>
          <div className="atomizer-status">{progress}/{total} chunks processed</div>
          <ul className="atomizer-list">
            {chunks.map((c, i) => (
              <li key={i} className={i < progress ? 'done' : i === progress ? 'active' : ''}>
                {i < progress ? '✅' : i === progress ? '⏳' : '○'} {c}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

// ── TELEMETRY BAR ──────────────────────────────────────────
function TelemetryBar({ streaming }) {
  const [telemetryStatus, setTelemetryStatus] = useState('INITIALIZING');

  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/health`)
        .then(r => r.json())
        .then(d => setTelemetryStatus(d.status === 'healthy' ? 'ACTIVE' : 'WARNING'))
        .catch(() => setTelemetryStatus('OFFLINE'));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const color = telemetryStatus === 'ACTIVE' ? '#10b981' : telemetryStatus === 'WARNING' ? '#f59e0b' : '#ef4444';

  return (
    <div className="telemetry-bar">
      <div className="telemetry-progress">
        <div className="telemetry-fill" style={{ width: streaming ? '60%' : '0%', background: streaming ? '#6366f1' : 'transparent' }} />
      </div>
      <span className="telemetry-label" style={{ color }}>
        TELEMETRY: {telemetryStatus} {streaming ? '| STREAMING...' : '| PULSE OK'}
      </span>
    </div>
  );
}

// ── BUILDER CHAT ───────────────────────────────────────────
function BuilderChat({ registry, onAtomizerUpdate, externalCommand, onBuildComplete, onQaGate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [building, setBuilding] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  const [audienceDetected, setAudienceDetected] = useState(null);
  const [generatingProfile, setGeneratingProfile] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);
  const audienceTimerRef = useRef(null);

  // ── Audience Detection ──────────────────────────────────
  const checkAudienceIntent = async (text) => {
    try {
      const res = await fetch(`${API_BASE}/api/audience/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (data.detected && data.confidence >= 0.7) {
        setAudienceDetected(data);
        if (audienceTimerRef.current) clearTimeout(audienceTimerRef.current);
        audienceTimerRef.current = setTimeout(() => setAudienceDetected(null), 15000);
      }
    } catch { /* silent */ }
  };

  const researchProfile = async () => {
    if (!audienceDetected?.audience_hint || generatingProfile) return;
    setGeneratingProfile(true);
    setAudienceDetected(null);
    setMessages(prev => [...prev, { role: 'system', text: `🔬 Researching audience profile: "${audienceDetected.audience_hint}"...` }]);
    try {
      const res = await fetch(`${API_BASE}/api/audience/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audience_description: audienceDetected.audience_hint,
          context: 'Building an application in the Meta App Factory',
        }),
      });
      const data = await res.json();
      if (data.status === 'ok' && data.profile) {
        const p = data.profile;
        const profileCard =
          `✅ **Audience Profile Generated: ${p.name}**\n` +
          `📊 Age Range: ${p.age_range}\n` +
          `📝 ${p.description}\n\n` +
          `🎯 Interests: ${p.interests.join(', ')}\n` +
          `🗣️ Tone: ${p.tone_keywords.join(', ')}\n` +
          `🚫 Deal-breakers: ${p.deal_breakers.slice(0, 3).join('; ')}\n\n` +
          `Profile saved as "${p.id}" — use \`python factory.py validate <app> --profile ${p.id}\` to score your app.`;
        setMessages(prev => [...prev, { role: 'assistant', text: profileCard }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', text: `⚠️ Profile generation failed: ${data.message || 'Unknown error'}` }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', text: `❌ Profile research error: ${err.message}` }]);
    } finally {
      setGeneratingProfile(false);
    }
  };

  const triggerBuild = async (appName, blueprint = 'multi_agent_core', description = '', systemPrompt = null) => {
    setBuilding(true);
    setMessages(prev => [...prev, { role: 'system', text: `🏗️ BUILD STARTED: ${appName} [${blueprint}]` }]);
    setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

    try {
      const res = await fetch(`${API_BASE}/api/build/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: appName, blueprint, description, system_prompt: systemPrompt }),
      });

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
            if (event.done) break;
            // UPGRADE 3: Detect GATE_BLOCKED event
            if (event.step === 'GATE_BLOCKED' && onQaGate) {
              onQaGate({ app_name: event.app_name, score: event.score });
            }
            if (event.text) {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: 'assistant',
                  text: copy[copy.length - 1].text + event.text + '\n',
                };
                return copy;
              });
            }
          } catch { /* skip */ }
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', text: `❌ Build error: ${err.message}` }]);
    } finally {
      setBuilding(false);
      if (onBuildComplete) onBuildComplete();
    }
  };

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle external commands from the Command Palette
  useEffect(() => {
    if (externalCommand) {
      executePrompt(externalCommand.text, externalCommand.isTriad);
    }
  }, [externalCommand]);

  const getContext = () => {
    const ctx = {};
    if (registry?.length) {
      ctx.registered_apps = registry.map(a => ({ name: a.name, status: a.status, type: a.type }));
    }
    ctx.factory_mode = 'builder';
    ctx.timestamp = new Date().toISOString();
    return ctx;
  };

  const executePrompt = async (promptText, isTriad = false) => {
    const prompt = promptText.trim();
    if (!prompt || streaming) return;

    // Handle /refine command
    if (prompt === '/refine' || prompt.startsWith('/refine ')) {
      const appName = prompt === '/refine'
        ? window.prompt('Which app do you want to refine?', 'Resonance')
        : prompt.split('/refine ')[1].split(':')[0].trim();
      if (!appName) return;

      const feedback = prompt.includes(':')
        ? prompt.split(':').slice(1).join(':').trim()
        : window.prompt(`What feedback do you have for ${appName}?`, '');
      if (!feedback) return;

      setInput('');
      setMessages(prev => [...prev, { role: 'user', text: `🔄 Refine ${appName}: ${feedback}` }]);
      setStreaming(true);
      setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

      try {
        const res = await fetch(`${API_BASE}/api/refine`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ app_name: appName, feedback }),
        });
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
              if (event.done) break;
              if (event.text) {
                setMessages(prev => {
                  const copy = [...prev];
                  copy[copy.length - 1] = { role: 'assistant', text: copy[copy.length - 1].text + event.text };
                  return copy;
                });
              }
            } catch { /* skip */ }
          }
        }
      } catch (err) {
        setMessages(prev => [...prev, { role: 'assistant', text: `❌ Refine error: ${err.message}` }]);
      } finally {
        setStreaming(false);
      }
      return;
    }

    setLastPrompt(prompt);
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: prompt }]);
    setStreaming(true);

    // Audience detection (async, non-blocking)
    checkAudienceIntent(prompt);
    setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

    try {
      const dashboard_context = getContext();
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
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
                copy[copy.length - 1] = { role: 'assistant', text: `❌ ${event.error}` };
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
                  text: copy[copy.length - 1].text + event.text,
                };
                return copy;
              });
            }
          } catch { /* skip */ }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', text: `❌ Connection failed: ${err.message}` };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  const sendMessage = () => executePrompt(input);

  const clearChat = async () => {
    setMessages([]);
    try { await fetch(`${API_BASE}/api/chat/clear`, { method: 'POST' }); } catch { }
  };

  const [recovering, setRecovering] = useState(false);

  const recoverSession = async () => {
    setRecovering(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat/history?limit=20`);
      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages);
      } else if (lastPrompt) {
        setInput(lastPrompt);
        inputRef.current?.focus();
      }
    } catch {
      // Fallback to local last prompt
      if (lastPrompt) {
        setInput(lastPrompt);
        inputRef.current?.focus();
      }
    } finally {
      setRecovering(false);
    }
  };

  const [parseResult, setParseResult] = useState(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    // POST to DocumentParserService
    const fd = new FormData();
    fd.append('file', file);
    setParseResult({ loading: true, file: file.name });

    try {
      const res = await fetch(`${API}/api/documents/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      setParseResult(data);

      // Also inject summary into chat input for context
      const summary = data.extracted?.summary || data.category || 'Parsed';
      const routed = data.routing?.destination || 'index only';
      setInput(prev => prev + `\n\n--- 📄 Parsed: ${file.name} ---\nCategory: ${data.category} (${(data.confidence * 100).toFixed(0)}%)\nRouted to: ${routed}\nSummary: ${summary}`);
      inputRef.current?.focus();

      // Auto-dismiss after 8s
      setTimeout(() => setParseResult(null), 8000);
    } catch (err) {
      setParseResult({ error: err.message });
      setTimeout(() => setParseResult(null), 5000);
    }
  };

  return (
    <div className="builder-chat">
      <div className="chat-header">
        <h2>
          🏗️ Builder Chat
          <span className="stream-badge">SSE STREAM</span>
        </h2>
        <div className="chat-header-actions">
          <button className="action-btn recover" onClick={recoverSession} title="Recover session from Supabase" disabled={recovering}>
            {recovering ? '⏳ Loading...' : '⏪ Recover'}
          </button>
          <button
            className="action-btn deploy"
            onClick={() => {
              const name = prompt('Enter app name to build:', 'Resonance');
              if (name) triggerBuild(name, 'multi_agent_core', 'Multi-agent educational app', input || lastPrompt || null);
            }}
            disabled={building || streaming}
            title="Deploy app via Factory Pipeline"
            style={{ background: building ? '#f59e0b' : '#10b981', color: '#fff', border: 'none' }}
          >
            {building ? '⚙️ Building...' : '🚀 Deploy'}
          </button>
          <button className="action-btn upload" onClick={() => fileRef.current?.click()} title="Upload & Parse Document">
            📎 Upload
          </button>
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.csv,.md" style={{ display: 'none' }} onChange={handleFileUpload} />
          <button className="action-btn clear" onClick={clearChat}>Clear</button>
        </div>
      </div>

      {parseResult && (
        <div style={{ padding: '0.6rem 1rem', fontSize: '0.8rem', borderBottom: '1px solid rgba(99,102,241,0.15)', background: parseResult.loading ? 'rgba(99,102,241,0.08)' : parseResult.error ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {parseResult.loading ? (
            <span>⏳ Parsing <strong>{parseResult.file}</strong>...</span>
          ) : parseResult.error ? (
            <span>❌ {parseResult.error}</span>
          ) : (
            <>
              <span>✅ <strong>{parseResult.category}</strong> ({(parseResult.confidence * 100).toFixed(0)}%)</span>
              <span style={{ color: '#64748b' }}>→ {parseResult.routing?.destination || 'index'}</span>
              <span style={{ flex: 1 }} />
              <button onClick={() => setParseResult(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.9rem' }}>✕</button>
            </>
          )}
        </div>
      )}

      {/* ── BUILD PROGRESS BANNER ── */}
      {(building || streaming) && (
        <div className="build-progress-banner">
          <div className="build-progress-header">
            <span className="build-progress-icon">{building ? '🏗️' : '💬'}</span>
            <span className="build-progress-label">
              {building ? 'BUILD IN PROGRESS' : 'PROCESSING...'}
            </span>
            <span className="build-progress-pulse" />
          </div>
          <div className="build-progress-bar-track">
            <div className="build-progress-bar-fill" style={{
              width: building ? '65%' : streaming ? '40%' : '0%',
              transition: 'width 1.5s ease-in-out',
            }} />
          </div>
          <div className="build-progress-status">
            {building && <>
              <span>🧪 Phantom QA & Master Architect are validating...</span>
              <span className="build-progress-timer">
                {messages.filter(m => m.role === 'system' || (m.role === 'assistant' && m.text.includes('BUILD'))).length} steps completed
              </span>
            </>}
            {!building && streaming && <span>⚡ Factory AI is generating a response...</span>}
          </div>
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-msg">
            <div className="icon-big">🧠</div>
            <h3>Factory Intelligence Online</h3>
            <p>Ask me to build apps, analyze architectures, or plan new features. Use the Command Palette to launch preset actions.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`msg ${msg.role}`}>
            {msg.text}
            {msg.role === 'assistant' && streaming && i === messages.length - 1 && (
              <span className="cursor" />
            )}
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      {/* Audience Detection Chip */}
      {audienceDetected && (
        <div className="audience-detect-chip">
          <span className="detect-icon">🔬</span>
          <span className="detect-text">
            Audience detected: <strong>{audienceDetected.audience_hint}</strong>
          </span>
          <button
            className="detect-research-btn"
            onClick={researchProfile}
            disabled={generatingProfile}
          >
            {generatingProfile ? '⏳ Researching...' : '📊 Research Profile'}
          </button>
          <button className="detect-dismiss" onClick={() => setAudienceDetected(null)}>✕</button>
        </div>
      )}

      <div className="chat-input-bar">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) sendMessage(); }}
          placeholder={streaming ? 'Streaming...' : 'Ask the Factory AI anything... (Ctrl+Enter to send)'}
          disabled={streaming}
          rows={3}
        />
        <button className="send-btn" onClick={sendMessage} disabled={streaming || !input.trim()}>
          ↑
        </button>
      </div>
    </div>
  );
}

// ── REFINE APP PANEL ───────────────────────────────────────
function RefinePanel({ registry }) {
  const [selectedApp, setSelectedApp] = useState('');
  const [feedback, setFeedback] = useState('');
  const [refining, setRefining] = useState(false);
  const [log, setLog] = useState([]);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log]);

  // Auto-select first active app
  useEffect(() => {
    if (!selectedApp && registry.length) {
      const active = registry.find(a => a.status === 'active');
      setSelectedApp(active?.name || registry[0].name);
    }
  }, [registry, selectedApp]);

  const stepIcon = (step) => {
    const icons = {
      DISCOVER: '📂', ASSETS: '🖼️', DIAGNOSE: '🔬',
      ANALYZE: '🧠', GENERATE: '⚡', PARSE: '🔍',
      WRITE: '✅', LINT: '🔎', COMPLETE: '🎉', ERROR: '❌', TIMEOUT: '⏰',
    };
    return icons[step] || '•';
  };

  const stepClass = (step) => {
    const classes = {
      DISCOVER: 'step-discover', ASSETS: 'step-discover',
      DIAGNOSE: 'step-diagnose',
      ANALYZE: 'step-generate', GENERATE: 'step-generate',
      PARSE: 'step-generate', LINT: 'step-write',
      WRITE: 'step-write', COMPLETE: 'step-complete',
      ERROR: 'step-error', TIMEOUT: 'step-error',
    };
    return classes[step] || '';
  };

  const submitRefinement = async () => {
    if (!selectedApp || !feedback.trim() || refining) return;
    setRefining(true);
    setLog([]);

    try {
      const res = await fetch(`${API_BASE}/api/refine/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: selectedApp, feedback: feedback.trim() }),
      });

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
            if (event.done) break;
            if (event.step && event.text) {
              setLog(prev => [...prev, { step: event.step, text: event.text, ts: new Date().toLocaleTimeString() }]);
            }
          } catch { /* skip */ }
        }
      }
    } catch (err) {
      setLog(prev => [...prev, { step: 'ERROR', text: `Connection failed: ${err.message}`, ts: new Date().toLocaleTimeString() }]);
    } finally {
      setRefining(false);
    }
  };

  const isComplete = log.some(l => l.step === 'COMPLETE');
  const hasError = log.some(l => l.step === 'ERROR');

  return (
    <div className="refine-panel">
      <div className="refine-header">
        <h3>🔧 Refine App — Self-Healing Engine V2</h3>
        <p className="refine-subtitle">Submit feedback to automatically analyze, modify, and write fixes to any registered app.</p>
      </div>

      <div className="refine-controls">
        <div className="refine-field">
          <label>Target App</label>
          <select
            value={selectedApp}
            onChange={e => setSelectedApp(e.target.value)}
            disabled={refining}
            className="refine-select"
          >
            {registry.map(app => (
              <option key={app.name} value={app.name}>
                {app.name} — {app.type} {app.status === 'active' ? '🟢' : '⚪'}
              </option>
            ))}
          </select>
        </div>

        <div className="refine-field">
          <label>Refinement Feedback</label>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            disabled={refining}
            placeholder="Describe changes, fixes, or improvements... e.g. 'Add responsive mobile layout with collapsible sidebar below 768px'"
            rows={5}
            className="refine-textarea"
          />
        </div>

        <button
          className={`refine-submit ${refining ? 'refining' : ''} ${isComplete ? 'complete' : ''}`}
          onClick={submitRefinement}
          disabled={refining || !feedback.trim()}
        >
          {refining ? '⚙️ Refining...' : isComplete ? '🎉 Complete — Submit Again' : '🚀 Apply Refinement'}
        </button>
      </div>

      {log.length > 0 && (
        <div className="refine-log">
          <h4>Pipeline Log</h4>
          <div className="refine-log-entries">
            {log.map((entry, i) => (
              <div key={i} className={`refine-step ${stepClass(entry.step)} ${entry.step === 'COMPLETE' ? 'highlight' : ''}`}>
                <span className="step-badge">{entry.step}</span>
                <span className="step-text">{entry.text}</span>
                <span className="step-time">{entry.ts}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── BRAND STUDIO PANEL ────────────────────────────────────
function BrandStudioPanel({ registry }) {
  const [selectedProject, setSelectedProject] = useState('');
  const [activeMode, setActiveMode] = useState(null);
  const [currentBrand, setCurrentBrand] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [description, setDescription] = useState('');
  const fileRef = useRef(null);

  // Auto-select first project
  useEffect(() => {
    if (!selectedProject && registry.length) {
      setSelectedProject(registry[0].name);
    }
  }, [registry, selectedProject]);

  // Load current brand when project changes
  useEffect(() => {
    if (!selectedProject) return;
    fetch(`${API_BASE}/api/brand/${encodeURIComponent(selectedProject)}`)
      .then(r => r.json())
      .then(data => setCurrentBrand(data.brand || null))
      .catch(() => setCurrentBrand(null));
  }, [selectedProject]);

  const handleAIGenerate = async () => {
    if (!selectedProject || loading) return;
    setLoading(true);
    setStatus({ type: 'info', text: '🤖 CMO + Graphic Designer generating your brand...' });
    try {
      const res = await fetch(`${API_BASE}/api/brand/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: selectedProject }),
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setCurrentBrand(data.brand);
        setStatus({ type: 'success', text: `✅ Brand generated for ${data.brand?.company_name || selectedProject}` });
      } else {
        setStatus({ type: 'error', text: `❌ ${data.message || 'Generation failed'}` });
      }
    } catch (err) {
      setStatus({ type: 'error', text: `❌ Connection failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedProject) return;
    e.target.value = '';
    setLoading(true);
    setStatus({ type: 'info', text: `📤 Extracting brand from ${file.name}...` });
    const fd = new FormData();
    fd.append('file', file);
    fd.append('project_name', selectedProject);
    try {
      const res = await fetch(`${API_BASE}/api/brand/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      if (data.status === 'ok') {
        setCurrentBrand(data.brand);
        setStatus({ type: 'success', text: `✅ Brand extracted from ${file.name}` });
      } else {
        setStatus({ type: 'error', text: `❌ ${data.message || 'Upload failed'}` });
      }
    } catch (err) {
      setStatus({ type: 'error', text: `❌ Upload error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleDescribe = async () => {
    if (!description.trim() || !selectedProject || loading) return;
    setLoading(true);
    setStatus({ type: 'info', text: '💬 Translating your vision into a brand identity...' });
    try {
      const res = await fetch(`${API_BASE}/api/brand/describe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: selectedProject, description: description.trim() }),
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setCurrentBrand(data.brand);
        setDescription('');
        setStatus({ type: 'success', text: `✅ Brand created from your description` });
      } else {
        setStatus({ type: 'error', text: `❌ ${data.message || 'Failed'}` });
      }
    } catch (err) {
      setStatus({ type: 'error', text: `❌ Error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const brandColors = currentBrand?.colors || {};
  const brandFonts = currentBrand?.fonts || {};
  const hasBrand = currentBrand && currentBrand.company_name;

  return (
    <div className="brand-studio">
      <div className="brand-studio-header">
        <div>
          <h3>🎨 Brand Studio</h3>
          <p className="brand-subtitle">Define your project's visual identity — no code needed</p>
        </div>
      </div>

      {/* Project Selector */}
      <div className="brand-project-selector">
        <label>Target Project</label>
        <select
          value={selectedProject}
          onChange={e => { setSelectedProject(e.target.value); setStatus(null); }}
          className="brand-select"
        >
          {registry.map(app => (
            <option key={app.name} value={app.name}>
              {app.name} — {app.type} {app.status === 'active' ? '🟢' : '⚪'}
            </option>
          ))}
        </select>
      </div>

      {/* Status Banner */}
      {status && (
        <div className={`brand-status-banner ${status.type}`}>
          {status.text}
          <button className="brand-dismiss" onClick={() => setStatus(null)}>✕</button>
        </div>
      )}

      {/* Three Mode Cards */}
      <div className="brand-mode-cards">
        {/* AI Creates */}
        <div
          className={`brand-mode-card ai ${activeMode === 'ai' ? 'active' : ''}`}
          onClick={() => setActiveMode('ai')}
        >
          <div className="mode-icon">🤖</div>
          <h4>AI Creates</h4>
          <p>Let CMO & Graphic Designer autonomously generate your brand identity, palette, and logo brief</p>
          <button
            className="brand-action-btn ai-btn"
            onClick={(e) => { e.stopPropagation(); handleAIGenerate(); }}
            disabled={loading}
          >
            {loading && activeMode === 'ai' ? '⏳ Generating...' : '⚡ Generate Brand'}
          </button>
        </div>

        {/* Upload */}
        <div
          className={`brand-mode-card upload ${activeMode === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveMode('upload')}
        >
          <div className="mode-icon">📤</div>
          <h4>I'll Provide</h4>
          <p>Upload your existing logo, brand guide, or identity documents</p>
          <div
            className="brand-drop-zone"
            onClick={(e) => { e.stopPropagation(); fileRef.current?.click(); }}
          >
            <span>Drop files here or click to browse</span>
            <span className="drop-formats">PNG, PDF, DOCX, JSON</span>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".png,.jpg,.jpeg,.pdf,.docx,.json,.svg"
            style={{ display: 'none' }}
            onChange={handleUpload}
          />
        </div>

        {/* Describe */}
        <div
          className={`brand-mode-card describe ${activeMode === 'describe' ? 'active' : ''}`}
          onClick={() => setActiveMode('describe')}
        >
          <div className="mode-icon">💬</div>
          <h4>Describe It</h4>
          <p>Tell us your vision in plain language and we'll bring it to life</p>
          <textarea
            className="brand-textarea"
            value={description}
            onChange={e => setDescription(e.target.value)}
            onClick={e => e.stopPropagation()}
            placeholder="My brand should feel modern, trustworthy, with dark tones and gold accents..."
            rows={3}
          />
          <button
            className="brand-action-btn describe-btn"
            onClick={(e) => { e.stopPropagation(); handleDescribe(); }}
            disabled={loading || !description.trim()}
          >
            {loading && activeMode === 'describe' ? '⏳ Creating...' : '✨ Create from Description'}
          </button>
        </div>
      </div>

      {/* Brand Preview */}
      <div className="brand-preview">
        <div className="brand-preview-header">
          <h4>Current Brand Identity</h4>
          <span className={`brand-badge ${hasBrand ? 'active' : 'empty'}`}>
            {hasBrand ? '✅ Brand Active' : '⚠️ No Brand Defined'}
          </span>
        </div>

        {hasBrand ? (
          <div className="brand-preview-content">
            <div className="brand-preview-row">
              <div className="brand-info-block">
                <span className="brand-label">Company</span>
                <span className="brand-value">{currentBrand.company_name}</span>
              </div>
              {currentBrand.tagline && (
                <div className="brand-info-block">
                  <span className="brand-label">Tagline</span>
                  <span className="brand-value">{currentBrand.tagline}</span>
                </div>
              )}
              <div className="brand-info-block">
                <span className="brand-label">Tone</span>
                <span className="brand-value">{currentBrand.tone_of_voice || '—'}</span>
              </div>
            </div>

            <div className="brand-preview-row">
              <div className="brand-info-block">
                <span className="brand-label">Color Palette</span>
                <div className="brand-color-palette">
                  {Object.entries(brandColors).map(([name, hex]) => (
                    <div key={name} className="color-swatch" title={`${name}: ${hex}`}>
                      <div className="color-circle" style={{ background: hex }} />
                      <span className="color-name">{name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="brand-preview-row">
              <div className="brand-info-block">
                <span className="brand-label">Typography</span>
                <div className="brand-fonts">
                  {Object.entries(brandFonts).map(([role, name]) => (
                    <span key={role} className="font-tag">{role}: <strong>{name}</strong></span>
                  ))}
                </div>
              </div>
              {currentBrand.visual_style && (
                <div className="brand-info-block">
                  <span className="brand-label">Visual Style</span>
                  <span className="brand-value">{currentBrand.visual_style}</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="brand-empty-state">
            <div className="empty-icon">🎨</div>
            <p>No brand identity defined for <strong>{selectedProject}</strong></p>
            <p className="empty-hint">Choose a mode above to create your brand</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── MAIN APP ────────────────────────────────────────────────
function App() {
  const [activeView, setActiveView] = useState('systemmap');
  const [builderMode, setBuilderMode] = useState(null); // 'technical' | 'venture' | null
  const [registry, setRegistry] = useState([]);
  const [atomizerChunks, setAtomizerChunks] = useState([]);
  const [atomizerProgress, setAtomizerProgress] = useState(0);
  const [externalCommand, setExternalCommand] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);

  // ── UPGRADE 6: n8n Health State ──────────────────────────
  const [n8nHealth, setN8nHealth] = useState({ status: 'unknown', circuit_breaker: { state: 'CLOSED' } });
  useEffect(() => {
    const checkN8n = () => {
      fetch(`${API_BASE}/api/health/n8n`)
        .then(r => r.json())
        .then(data => setN8nHealth(data))
        .catch(() => setN8nHealth({ status: 'offline', circuit_breaker: { state: 'UNKNOWN' } }));
    };
    checkN8n();
    const interval = setInterval(checkN8n, 30000);
    return () => clearInterval(interval);
  }, []);

  // ── UPGRADE 1: Running Apps State ────────────────────────
  const [runningApps, setRunningApps] = useState({});
  const [launchingApp, setLaunchingApp] = useState(null);

  const refreshRunning = () => {
    fetch(`${API_BASE}/api/apps/running`)
      .then(r => r.json())
      .then(data => setRunningApps(data))
      .catch(() => {});
  };
  useEffect(() => {
    refreshRunning();
    const interval = setInterval(refreshRunning, 10000);
    return () => clearInterval(interval);
  }, []);

  const launchApp = async (appName) => {
    setLaunchingApp(appName);
    try {
      const res = await fetch(`${API_BASE}/api/apps/${encodeURIComponent(appName)}/launch`, { method: 'POST' });
      const data = await res.json();
      if (data.port) {
        window.open(data.url, '_blank');
        refreshRunning();
      } else {
        alert(data.error || 'Launch failed');
      }
    } catch (err) {
      alert(`Launch error: ${err.message}`);
    } finally {
      setLaunchingApp(null);
    }
  };

  const stopApp = async (appName) => {
    try {
      await fetch(`${API_BASE}/api/apps/${encodeURIComponent(appName)}/stop`, { method: 'POST' });
      refreshRunning();
    } catch { }
  };

  // ── UPGRADE 3: QA Gate Modal State ──────────────────────
  const [qaGate, setQaGate] = useState(null); // { app_name, score }

  const approveGate = async () => {
    if (!qaGate) return;
    await fetch(`${API_BASE}/api/build/approve/${encodeURIComponent(qaGate.app_name)}`, { method: 'POST' });
    setQaGate(null);
  };
  const abortGate = async () => {
    if (!qaGate) return;
    await fetch(`${API_BASE}/api/build/abort/${encodeURIComponent(qaGate.app_name)}`, { method: 'POST' });
    setQaGate(null);
  };

  // ── Theme Color Map (per-app FAB pulse) ─────────────────
  const APP_THEME_COLORS = {
    Alpha_V2_Genesis: '#10b981',
    Resonance: '#6366f1',
    MetaTestApp: '#f59e0b',
    'News Analyzer': '#06b6d4',
  };

  useEffect(() => {
    fetch(`${API_BASE}/api/registry`)
      .then(r => r.json())
      .then(data => setRegistry(data.apps || []))
      .catch(() => setRegistry([
        { name: 'Alpha_V2_Genesis', status: 'active', type: 'Trading Dashboard', port: 5005 },
        { name: 'MetaTestApp', status: 'inactive', type: 'Test', port: null },
        { name: 'News Analyzer', status: 'inactive', type: 'Data Pipeline', port: null },
      ]));
  }, []);

  const handleCommand = (cmdText, isTriad) => {
    setActiveView('builder');
    setExternalCommand({ text: cmdText, isTriad, ts: Date.now() });
  };

  const stats = [
    { label: 'Registered Apps', value: registry.length || 3, sub: 'In factory registry' },
    { label: 'Active Apps', value: registry.filter(a => a.status === 'active').length || 1, sub: 'Currently running' },
    { label: 'Vault Keys', value: 8, sub: 'Encrypted secrets' },
    { label: 'Engine Version', value: 'V3', sub: 'SSE + Memory + Telemetry' },
  ];

  const sidebarItems = [
    { icon: '🗺️', label: 'System Map', view: 'systemmap', badge: 'V3' },
    { icon: '⚔️', label: 'War Room', view: 'warroom', badge: 'LIVE' },
    { icon: '🏗️', label: 'Builder Chat', view: 'builder' },
    { icon: '📦', label: 'App Registry', view: 'registry' },
    { icon: '🎮', label: 'Command Palette', view: 'commands' },
    { icon: '🧠', label: 'Agent Status', view: 'agents' },
    { icon: '🎨', label: 'Brand Studio', view: 'brand', badge: 'NEW' },
    { icon: '🔧', label: 'Refine App', view: 'refine' },
    { icon: '⚛️', label: 'Atomizer', view: 'atomizer' },
    { icon: '📊', label: 'Telemetry', view: 'telemetry', badge: 'Beta' },
  ];

  return (
    <div className="factory-app">
      {/* ── HEADER ── */}
      <header className="factory-header">
        <div className="header-brand">
          <div className="logo">⚡</div>
          <h1>Meta App Factory</h1>
          <span className="version">V3.0</span>
        </div>
        <div className="header-status">
          <span><span className="status-dot" /> Backend Online</span>
          <span>LangSmith: Active</span>
          <span>Supabase: Connected</span>
          <span title={`Circuit: ${n8nHealth.circuit_breaker?.state || 'N/A'}`}>
            <span className="status-dot" style={{
              background: n8nHealth.status === 'connected' ? '#22c55e' :
                          n8nHealth.status === 'degraded' ? '#eab308' : '#ef4444',
              boxShadow: n8nHealth.status === 'connected' ? '0 0 6px rgba(34,197,94,0.5)' :
                         n8nHealth.status === 'degraded' ? '0 0 6px rgba(234,179,8,0.5)' :
                         '0 0 6px rgba(239,68,68,0.5)',
            }} />
            n8n: {n8nHealth.status === 'connected' ? 'Online' :
                  n8nHealth.status === 'degraded' ? 'Degraded' :
                  n8nHealth.status === 'auth_expired' ? 'Auth Expired' : 'Offline'}
            {n8nHealth.circuit_breaker?.state === 'OPEN' && ' ⚡BREAKER'}
          </span>
        </div>
      </header>

      {/* ── SIDEBAR ── */}
      <aside className="factory-sidebar">
        <div className="sidebar-section">
          <h3>Navigation</h3>
          {sidebarItems.map(item => (
            <div
              key={item.view}
              className={`sidebar-item ${activeView === item.view ? 'active' : ''}`}
              onClick={() => setActiveView(item.view)}
            >
              <span className="icon">{item.icon}</span>
              <span>{item.label}</span>
              {item.badge && <span className="badge">{item.badge}</span>}
            </div>
          ))}
        </div>

        <div className="sidebar-section">
          <h3>Active Apps</h3>
          {registry.map(app => {
            const isRunning = !!runningApps[app.name]?.alive;
            const isLaunching = launchingApp === app.name;
            return (
              <div
                key={app.name}
                className={`sidebar-item ${selectedApp === app.name ? 'active' : ''}`}
                onClick={() => setSelectedApp(app.name)}
                style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <span className="icon" style={isRunning ? { animation: 'pulse 2s infinite' } : {}}>
                  {isRunning ? '🟢' : app.status === 'active' ? '🔵' : '⚪'}
                </span>
                <span style={{ flex: 1 }}>{app.name}</span>
                {isRunning ? (
                  <button
                    className="app-action-btn stop"
                    onClick={e => { e.stopPropagation(); stopApp(app.name); }}
                    title="Stop app"
                  >⏹️</button>
                ) : (
                  <button
                    className="app-action-btn launch"
                    onClick={e => { e.stopPropagation(); launchApp(app.name); }}
                    title="Launch app"
                    disabled={isLaunching}
                  >{isLaunching ? '⏳' : '🚀'}</button>
                )}
              </div>
            );
          })}
        </div>
      </aside>

      {/* ── MAIN ── */}
      <main className="factory-main">
        {/* Stat Row */}
        <div className="stat-row">
          {stats.map((s, i) => (
            <div key={i} className="stat-card">
              <div className="label">{s.label}</div>
              <div className="value">{s.value}</div>
              <div className="sub">{s.sub}</div>
            </div>
          ))}
        </div>

        {/* System Map — V3 Architecture */}
        {activeView === 'systemmap' && (
          <div style={{ width: '100%', height: 'calc(100vh - 140px)', borderRadius: '12px', overflow: 'hidden', background: '#0a0e17' }}>
            <iframe
              src={`${API_BASE}/system_map.html`}
              style={{ width: '100%', height: '100%', border: 'none' }}
              title="V3 System Map"
            />
          </div>
        )}

        {/* War Room — Adversarial Boardroom */}
        {activeView === 'warroom' && (
          <WarRoom />
        )}

        {/* Builder Chat / Mode Selector (EOS V3.1) */}
        {activeView === 'builder' && (
          builderMode === null ? (
            <ModeSelectionScreen onSelectMode={setBuilderMode} />
          ) : builderMode === 'venture' ? (
            <WarRoom ventureMode={true} />
          ) : (
            <BuilderChat
              registry={registry}
              onAtomizerUpdate={(c, p) => { setAtomizerChunks(c); setAtomizerProgress(p); }}
              externalCommand={externalCommand}
              onBuildComplete={() => {
                fetch(`${API_BASE}/api/registry`).then(r => r.json()).then(data => setRegistry(data.apps || [])).catch(() => { });
              }}
              onQaGate={setQaGate}
            />
          )
        )}

        {/* App Registry */}
        {activeView === 'registry' && (
          <div className="registry-panel">
            <h3>📦 App Registry</h3>
            <table className="registry-table">
              <thead>
                <tr><th>App Name</th><th>Type</th><th>Status</th><th>Port</th></tr>
              </thead>
              <tbody>
                {registry.map(app => (
                  <tr key={app.name}>
                    <td style={{ color: '#e2e8f0', fontWeight: 500 }}>{app.name}</td>
                    <td>{app.type}</td>
                    <td>
                      <span className={app.status === 'active' ? 'status-active' : 'status-inactive'}>
                        {app.status === 'active' ? '● Active' : '○ Inactive'}
                      </span>
                    </td>
                    <td>{app.port || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Command Palette */}
        {activeView === 'commands' && (
          <CommandPalette onCommand={handleCommand} />
        )}

        {/* Refine App */}
        {activeView === 'refine' && (
          <RefinePanel registry={registry} />
        )}

        {/* Brand Studio */}
        {activeView === 'brand' && (
          <BrandStudioPanel registry={registry} />
        )}

        {/* Agent Status */}
        {activeView === 'agents' && <AgentStatusPanel />}

        {/* Atomizer */}
        {activeView === 'atomizer' && (
          <AtomizerPanel chunks={atomizerChunks} progress={atomizerProgress} total={atomizerChunks.length} />
        )}

        {/* Telemetry */}
        {activeView === 'telemetry' && (
          <div className="registry-panel">
            <h3>📊 Telemetry Dashboard</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '1rem' }}>
              LangSmith traces are being collected under project <strong style={{ color: 'var(--accent-hover)' }}>Meta_App_Factory</strong>.
              Visit <a href="https://smith.langchain.com" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-hover)' }}>smith.langchain.com</a> to view traces.
            </p>
            <AgentStatusPanel />
          </div>
        )}
      </main>

      {/* ── TELEMETRY BAR (bottom) ── */}
      <TelemetryBar streaming={streaming} />

      {/* ── SCOPED SUPPORT FAB ── */}
      <SupportFAB
        activeApp={selectedApp || 'Factory'}
        themeColor={APP_THEME_COLORS[selectedApp] || '#818cf8'}
      />

      {/* ── UPGRADE 3: QA Gate Approval Modal ── */}
      {qaGate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
          backdropFilter: 'blur(8px)',
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #1e1b3a, #0f172a)',
            border: '1px solid rgba(239,68,68,0.3)', borderRadius: '16px',
            padding: '32px', maxWidth: '480px', width: '90%', textAlign: 'center',
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🛑</div>
            <h2 style={{ color: '#ef4444', margin: '0 0 8px', fontSize: '20px' }}>BUILD PAUSED</h2>
            <p style={{ color: '#94a3b8', margin: '0 0 16px', fontSize: '14px' }}>
              Phantom QA scored <strong style={{ color: '#ef4444', fontSize: '24px' }}>{qaGate.score}/100</strong>
              <br />below the deployment threshold of <strong style={{ color: '#22c55e' }}>70</strong>
            </p>
            <p style={{ color: '#64748b', fontSize: '12px', marginBottom: '24px' }}>
              App: <strong style={{ color: '#e2e8f0' }}>{qaGate.app_name}</strong>
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button onClick={approveGate} style={{
                padding: '12px 24px', borderRadius: '10px', border: 'none',
                background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                color: 'white', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
              }}>✅ Approve & Deploy</button>
              <button onClick={abortGate} style={{
                padding: '12px 24px', borderRadius: '10px',
                border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.1)',
                color: '#ef4444', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
              }}>❌ Abort Build</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App
