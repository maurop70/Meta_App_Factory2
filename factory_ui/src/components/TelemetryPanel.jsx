import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function TelemetryPanel() {
  const [running, setRunning] = useState([]);
  const [telemetryLog, setTelemetryLog] = useState({});
  const [status, setStatus] = useState({});
  const [loading, setLoading] = useState(false);

  const refreshStatus = async () => {
    try {
      const res = await axios.get('/api/apps/running');
      setRunning(res.data.items || []);
    } catch (e) {
      console.warn("Failed to refresh telemetry app status:", e.message);
    }
  };

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 8000);

    const clientId = self.crypto?.randomUUID ? self.crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
    // Watchdog Streaming Telemetry (Native Port 5030)
    const es = new EventSource(`/api/qa/stream?client_id=${clientId}`);
    
    es.onopen = () => {
      console.log("Telemetry EventSource stream connection successfully opened.");
    };

    es.onerror = (err) => {
      console.warn("Telemetry EventSource error:", err);
    };

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.agent) {
          setStatus(prev => ({
            ...prev,
            [data.agent]: data.status || 'ACTIVE'
          }));
          const eventId = data.id || data.uuid || `${data.timestamp || Date.now()}_${data.agent || ''}_${data.status || ''}_${(data.message || '').substring(0, 30)}`;
          setTelemetryLog(prev => ({
            ...prev,
            [eventId]: {
              id: eventId,
              time: new Date().toLocaleTimeString(),
              agent: data.agent,
              status: data.status,
              message: data.message || 'Heartbeat signal received',
              _ts: Date.now()
            }
          }));
        }
      } catch (e) {}
    };

    // Strict Memory Sanitization closure on unmount
    return () => {
      console.log("Telemetry component unmounting. Safely closing EventSource stream...");
      clearInterval(interval);
      es.close();
    };
  }, []);

  return (
    <div className="telemetry-panel" style={{ padding: '20px', background: 'rgba(0,0,0,0.1)', borderRadius: '16px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: '#00FFFF', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>📊 Live C-Suite Telemetry</h3>
        <button 
          onClick={refreshStatus} 
          style={{
            padding: '6px 16px', borderRadius: '8px', border: '1px solid #00FFFF', 
            background: 'transparent', color: '#00FFFF', cursor: 'pointer', fontSize: '13px'
          }}
        >
          🔄 Sync Telemetry
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '15px' }}>
        {running.map(app => {
          const isAlive = app.alive;
          const currentTelemetry = status[app.name] || (isAlive ? 'ONLINE' : 'OFFLINE');
          return (
            <div key={app.name} className="agent-card" style={{
              background: 'rgba(255,255,255,0.03)',
              border: isAlive ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(255,255,255,0.05)',
              borderRadius: '12px',
              padding: '20px',
              position: 'relative',
              boxShadow: isAlive ? '0 4px 20px rgba(16,185,129,0.05)' : 'none'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <strong style={{ color: '#fff', fontSize: '0.95rem' }}>{app.name.replace(/_/g, ' ')}</strong>
                <span style={{
                  background: isAlive ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                  color: isAlive ? '#10b981' : '#ef4444',
                  padding: '2px 8px',
                  borderRadius: '20px',
                  fontSize: '11px',
                  fontWeight: 'bold'
                }}>
                  {currentTelemetry}
                </span>
              </div>
              <div style={{ fontSize: '12px', opacity: 0.6, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Port: <span style={{ fontFamily: 'monospace', color: '#00FFFF' }}>{app.port}</span></div>
                <div>PID: <span style={{ fontFamily: 'monospace' }}>{app.pid || 'N/A'}</span></div>
                <div>Health Rating: <span style={{ color: app.health === 'healthy' ? '#10b981' : '#ef4444' }}>{app.health}</span></div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="telemetry-log" style={{
        background: 'rgba(0,0,0,0.3)',
        borderRadius: '12px',
        padding: '20px',
        border: '1px solid rgba(255,255,255,0.05)'
      }}>
        <h4 style={{ color: '#00FFFF', margin: '0 0 15px 0', fontSize: '0.9rem', letterSpacing: '1px', textTransform: 'uppercase' }}>Live Network Telemetry Trace Log</h4>
        <div style={{ maxHeight: '200px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Object.keys(telemetryLog).length === 0 ? (
            <div style={{ opacity: 0.3, textAlign: 'center', padding: '20px' }}>Awaiting backend stream signals...</div>
          ) : (
            Object.values(telemetryLog)
              .sort((a, b) => b._ts - a._ts)
              .slice(0, 30)
              .map((log) => (
                <div key={log.id} style={{ display: 'flex', gap: '10px', opacity: 0.8 }}>
                  <span style={{ color: '#818cf8' }}>[{log.time}]</span>
                  <strong style={{ color: '#c084fc' }}>{log.agent}:</strong>
                  <span style={{ color: '#34d399' }}>{log.status}</span>
                  <span style={{ opacity: 0.7 }}>- {log.message}</span>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
