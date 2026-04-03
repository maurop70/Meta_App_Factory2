
import React, { useState } from 'react';

export default function AetherCommandSuite({ appName }) {
  const [loadingExplain, setLoadingExplain] = useState(false);
  const [loadingRefine, setLoadingRefine] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type='info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleExplain = async () => {
    setLoadingExplain(true);
    try {
      const res = await fetch(`http://localhost:5000/api/socratic/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: appName })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Request failed');
      
      alert(`🤖 AETHER SOCRATIC TRACE [${appName}]\n\n${data.trace || data.message || JSON.stringify(data)}`);
    } catch (err) {
      alert(`⚠️ Socratic Bridge Error:\n${err.message}`);
    } finally {
      setLoadingExplain(false);
    }
  };

  const handleRefine = async () => {
    setLoadingRefine(true);
    try {
        const res = await fetch(`http://localhost:5000/api/system/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_name: appName })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Validation failed');
        showToast("Refinement Loop Triggered 🚀 Check Factory UI for logs.", "success");
    } catch (err) {
        showToast(`Refinement Failed: ${err.message}`, "error");
    } finally {
        setLoadingRefine(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      fontFamily: 'system-ui, sans-serif'
    }}>
      {toast && (
        <div style={{
          background: toast.type === 'error' ? 'rgba(239,68,68,0.9)' : 'rgba(0,209,255,0.9)',
          color: '#000', padding: '10px 16px', borderRadius: '8px', fontSize: '13px',
          boxShadow: `0 4px 12px ${toast.type === 'error' ? 'rgba(239,68,68,0.4)' : 'rgba(0,209,255,0.4)'}`,
          marginBottom: '8px', textAlign: 'center', fontWeight: 'bold'
        }}>
          {toast.msg}
        </div>
      )}
      
      <div style={{
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(0, 209, 255, 0.3)',
        borderRadius: '12px',
        padding: '12px 16px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px'
      }}>
        <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Aether Controls
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={handleExplain} 
            disabled={loadingExplain}
            style={{
              padding: '8px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.2)', color: '#fff', cursor: 'pointer',
              fontWeight: 500, fontSize: '13px', transition: 'all 0.2s', display: 'flex', alignItems: 'center'
            }}
          >
            {loadingExplain ? '⏳' : '🧠 Explain'}
          </button>
          <button 
            onClick={handleRefine}
            disabled={loadingRefine}
            style={{
              padding: '8px 14px', borderRadius: '8px', background: '#00D1FF',
              border: 'none', color: '#000', cursor: 'pointer', display: 'flex', alignItems: 'center',
              fontWeight: 700, fontSize: '13px', boxShadow: '0 0 10px rgba(0, 209, 255, 0.4)',
              transition: 'all 0.2s'
            }}
          >
            {loadingRefine ? '⏳' : '🚀 Refine App'}
          </button>
        </div>
      </div>
    </div>
  );
}
