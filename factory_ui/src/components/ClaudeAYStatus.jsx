import React, { useState, useEffect } from 'react';

export default function ClaudeAYStatus() {
  const [status, setStatus] = useState(null);
  const [collapsed, setCollapsed] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/claudeay/status');
      if (!res.ok) return;
      const data = await res.json();
      setStatus(data);
    } catch (_) {}
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  const cay = status?.claudeay;
  const isLocalUrl = (url) => !url || url.startsWith('http://localhost') || url.startsWith('http://127.0.0.1') || url.startsWith('http://::1');
  const recentErrors = (status?.recent_telemetry || [])
    .filter(e => (e.type === 'console_error' || e.type === 'page_error') && isLocalUrl(e.url))
    .slice(-2);
  const lastLoop = (status?.recent_loop || []).slice(-1)[0];

  return (
    <div className="claudeay-bar">
      {/* Toggle button */}
      <button
        className="claudeay-bar-toggle"
        onClick={() => setCollapsed(c => !c)}
        title="Toggle ClaudeAY status"
      >
        {collapsed ? '▶ ClaudeAY' : '▼ ClaudeAY'}
      </button>

      {!collapsed && (
        <div className="claudeay-bar-inner">
          {/* MCP Bridge indicator */}
          <span className="claudeay-chip">
            <span className={`claudeay-dot ${cay?.mcp_bridge_online ? 'dot-live' : 'dot-off'}`} />
            MCP {cay?.mcp_bridge_online ? 'LIVE' : 'OFF'}
          </span>

          {/* Rules indicator */}
          <span className="claudeay-chip">
            <span className="claudeay-dot dot-indigo" />
            Rules {cay?.rules_loaded ? `${cay.rules_lines}L` : '—'}
          </span>

          {/* Telemetry indicator */}
          <span className={`claudeay-chip ${cay?.critical_errors > 0 ? 'chip-error' : ''}`}>
            <span className={`claudeay-dot ${cay?.critical_errors > 0 ? 'dot-error' : 'dot-cyan'}`} />
            {cay?.critical_errors > 0
              ? `${cay.critical_errors} ERR`
              : `${cay?.telemetry_events || 0} EVT`}
          </span>

          {/* Last loop event */}
          {lastLoop && (
            <span className="claudeay-chip claudeay-chip-loop">
              <span className="claudeay-dot dot-purple" />
              {lastLoop.type?.replace('_', ' ')}
            </span>
          )}

          {/* Routing legend */}
          <span className="claudeay-legend">
            AUTO&#8209;ROUTE: <b className="text-indigo-400">CLAUDE</b>
            &nbsp;|&nbsp;
            <b className="text-purple-400">GEMINI</b>
          </span>

          {/* Inline errors if any */}
          {recentErrors.map((e, i) => (
            <span key={i} className="claudeay-err-chip" title={e.message}>
              ⚑ {(e.message || e.type || '').slice(0, 40)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
