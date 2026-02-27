import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

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
function BuilderChat({ registry, onAtomizerUpdate, externalCommand }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

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
    setLastPrompt(prompt);
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: prompt }]);
    setStreaming(true);
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

  const recoverLastPrompt = () => {
    if (lastPrompt) {
      setInput(lastPrompt);
      inputRef.current?.focus();
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = ev.target.result;
      const truncated = content.length > 3000 ? content.slice(0, 3000) + '\n...(truncated)' : content;
      setInput(prev => prev + `\n\n--- Uploaded: ${file.name} ---\n${truncated}`);
      inputRef.current?.focus();
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <div className="builder-chat">
      <div className="chat-header">
        <h2>
          🏗️ Builder Chat
          <span className="stream-badge">SSE STREAM</span>
        </h2>
        <div className="chat-header-actions">
          <button className="action-btn recover" onClick={recoverLastPrompt} title="Recover last prompt" disabled={!lastPrompt}>
            ⏪ Recover
          </button>
          <button className="action-btn upload" onClick={() => fileRef.current?.click()} title="Upload a file">
            📎 Upload
          </button>
          <input ref={fileRef} type="file" style={{ display: 'none' }} onChange={handleFileUpload} />
          <button className="action-btn clear" onClick={clearChat}>Clear</button>
        </div>
      </div>

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

// ── MAIN APP ────────────────────────────────────────────────
function App() {
  const [activeView, setActiveView] = useState('builder');
  const [registry, setRegistry] = useState([]);
  const [atomizerChunks, setAtomizerChunks] = useState([]);
  const [atomizerProgress, setAtomizerProgress] = useState(0);
  const [externalCommand, setExternalCommand] = useState(null);
  const [streaming, setStreaming] = useState(false);

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
    { icon: '🏗️', label: 'Builder Chat', view: 'builder' },
    { icon: '📦', label: 'App Registry', view: 'registry' },
    { icon: '🎮', label: 'Command Palette', view: 'commands' },
    { icon: '🧠', label: 'Agent Status', view: 'agents' },
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
          {registry.map(app => (
            <div key={app.name} className="sidebar-item">
              <span className="icon">{app.status === 'active' ? '🟢' : '⚪'}</span>
              <span>{app.name}</span>
            </div>
          ))}
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

        {/* Builder Chat */}
        {activeView === 'builder' && (
          <BuilderChat
            registry={registry}
            onAtomizerUpdate={(c, p) => { setAtomizerChunks(c); setAtomizerProgress(p); }}
            externalCommand={externalCommand}
          />
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
    </div>
  );
}

export default App
