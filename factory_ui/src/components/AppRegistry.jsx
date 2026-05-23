import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function AppRegistry() {
  const [registry, setRegistry] = useState([]);
  const [runningApps, setRunningApps] = useState({});
  const [launchingApp, setLaunchingApp] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchManifestAndRunning = async () => {
    setLoading(true);
    try {
      // 1. Fetch manifest
      const manifestRes = await axios.get('/api/operator/manifest');
      const apps = manifestRes.data || [];
      setRegistry(apps);

      // 2. Fetch running apps status
      const runningRes = await axios.get('/api/apps/running');
      const runningData = runningRes.data.items || [];
      const runningMap = {};
      runningData.forEach(app => {
        runningMap[app.name] = app;
      });
      setRunningApps(runningMap);
    } catch (e) {
      console.warn("Failed to sync App Registry:", e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchManifestAndRunning();
    const interval = setInterval(fetchManifestAndRunning, 8000);
    return () => clearInterval(interval);
  }, []);

  const launchApp = async (appName) => {
    setLaunchingApp(appName);
    try {
      const res = await axios.post(`/api/apps/${encodeURIComponent(appName)}/launch`);
      const data = res.data;
      if (data.port || data.status === 'already_running') {
        let targetUrl = data.url;
        if (appName === 'Alpha_V2_Genesis') targetUrl = 'http://localhost:5175';
        else if (appName === 'Resonance') targetUrl = 'http://localhost:5174';
        
        window.open(targetUrl, '_blank');
        fetchManifestAndRunning();
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
      await axios.post(`/api/apps/${encodeURIComponent(appName)}/stop`);
      fetchManifestAndRunning();
    } catch (e) {
      console.error("Stop application error:", e);
    }
  };

  return (
    <div className="registry-panel" style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ color: '#6366f1', margin: 0 }}>📦 C-Suite App Registry</h3>
        <button 
          onClick={fetchManifestAndRunning} 
          className="refresh-btn" 
          disabled={loading}
          style={{
            padding: '6px 16px', borderRadius: '8px', border: '1px solid #6366f1', 
            background: 'transparent', color: '#6366f1', cursor: 'pointer', fontSize: '13px'
          }}
        >
          {loading ? 'Refreshing...' : '🔄 Sync Registry'}
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="registry-table" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.4)', fontSize: '12px', textTransform: 'uppercase' }}>
              <th style={{ padding: '12px 8px' }}>App Name</th>
              <th style={{ padding: '12px 8px' }}>Type</th>
              <th style={{ padding: '12px 8px' }}>Status</th>
              <th style={{ padding: '12px 8px' }}>Port</th>
              <th style={{ padding: '12px 8px' }}>Dialogue</th>
              <th style={{ padding: '12px 8px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {registry.map(app => {
              const running = !!runningApps[app.name]?.alive;
              const port = runningApps[app.name]?.port || app.port;
              return (
                <tr key={app.name} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', fontSize: '14px' }}>
                  <td 
                    style={{ 
                      padding: '16px 8px', color: '#818cf8', fontWeight: 600, cursor: 'pointer', 
                      textDecoration: 'underline dotted rgba(99,102,241,0.4)' 
                    }}
                    onClick={() => {
                      if (running) {
                        let targetUrl = port ? `http://localhost:${port}` : null;
                        if (app.name === 'Alpha_V2_Genesis') targetUrl = 'http://localhost:5175';
                        else if (app.name === 'Resonance') targetUrl = 'http://localhost:5174';
                        if (targetUrl) window.open(targetUrl, '_blank');
                      } else {
                        launchApp(app.name);
                      }
                    }}
                  >
                    {app.name}
                  </td>
                  <td style={{ padding: '16px 8px', opacity: 0.8 }}>{app.type || 'Agent Service'}</td>
                  <td style={{ padding: '16px 8px' }}>
                    <span style={{ 
                      color: running ? '#10b981' : 'rgba(255,255,255,0.3)', 
                      display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 'bold', fontSize: '12px'
                    }}>
                      {running ? '🟢 Running' : '○ Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '16px 8px', fontFamily: 'monospace' }}>{running ? port : app.port || '—'}</td>
                  <td style={{ padding: '16px 8px' }}>
                    {app.form_url && port ? (
                      <button
                        onClick={() => window.open(`http://localhost:${port}${app.form_url}`, '_blank')}
                        style={{ 
                          fontSize: '11px', padding: '3px 10px', borderRadius: '4px', 
                          border: '1px solid rgba(139,92,246,0.3)', background: 'rgba(139,92,246,0.1)', 
                          color: '#a78bfa', cursor: 'pointer', fontWeight: 600 
                        }}
                      >
                        💬 Open
                      </button>
                    ) : (
                      <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: '11px' }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: '16px 8px' }}>
                    {running ? (
                      <button
                        onClick={() => stopApp(app.name)}
                        style={{ 
                          fontSize: '11px', padding: '4px 10px', borderRadius: '6px', 
                          border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)', 
                          color: '#ef4444', cursor: 'pointer', fontWeight: 600
                        }}
                      >
                        ⏹ Stop
                      </button>
                    ) : (
                      <button
                        onClick={() => launchApp(app.name)}
                        disabled={launchingApp === app.name}
                        style={{ 
                          fontSize: '11px', padding: '4px 10px', borderRadius: '6px', 
                          border: '1px solid rgba(99,102,241,0.3)', background: 'rgba(99,102,241,0.1)', 
                          color: '#818cf8', cursor: 'pointer', fontWeight: 600
                        }}
                      >
                        {launchingApp === app.name ? '⏳ Starting...' : '🚀 Launch'}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
