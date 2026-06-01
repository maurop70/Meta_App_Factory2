import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function CIOIntel() {
  const [memos, setMemos] = useState([]);
  const [selectedMemo, setSelectedMemo] = useState(null);
  const [loading, setLoading] = useState(false);
  const CIO_BASE = "";

  const fetchMemos = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${CIO_BASE}/api/cio/memos`, { params: { limit: 15, offset: 0 } });
      setMemos(res.data.items);
    } catch (e) {
      console.warn("Failed to load CIO memos:", e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemos();
  }, []);

  const viewMemo = async (filename) => {
    try {
      const res = await axios.get(`${CIO_BASE}/api/cio/memos/${filename}`);
      setSelectedMemo({ filename, text: res.data });
    } catch (e) {
      console.warn("Failed to load memo text:", e.message);
    }
  };

  const authorizeMemo = async () => {
    if (!selectedMemo) return;
    const directive = window.prompt(
      "Enter specific implementation instructions for the Master Architect:",
      "Implement the technical upgrades outlined in this memo."
    );
    if (!directive) return;

    try {
      const res = await axios.post(`${CIO_BASE}/api/cio/authorize`, {
        memo_filename: selectedMemo.filename,
        directive: directive
      });
      if (res.data.status === 'dispatched') {
        alert("✅ Upgrade Memo authorized and sent to the War Room!");
      } else {
        alert(`❌ Dispatch failed: ${res.data.error || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`❌ Connection error: ${e.message}`);
    }
  };

  return (
    <div className="cio-dashboard" style={{ padding: '20px', background: 'rgba(0,0,0,0.1)', borderRadius: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ color: '#A855F7', margin: 0, fontSize: '1.5rem' }}>🔬 CIO Strategic Intelligence</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={fetchMemos} 
            style={{
              padding: '8px 16px', borderRadius: '8px', border: '1px solid #A855F7', 
              background: 'transparent', color: '#A855F7', cursor: 'pointer', fontSize: '13px'
            }}
          >
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
          {selectedMemo && (
            <button 
              onClick={authorizeMemo} 
              style={{ 
                padding: '8px 20px', borderRadius: '8px', background: 'linear-gradient(135deg, #A855F7, #7c3aed)', 
                color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold'
              }}
            >
              ⚡ Authorize Upgrade
            </button>
          )}
        </div>
      </div>

      <div className="cio-layout" style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '30px' }}>
        <aside className="memo-list" style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', padding: '15px', minHeight: '300px', maxHeight: '500px', overflowY: 'auto' }}>
          <h3 style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', marginBottom: '15px' }}>Upgrade Memos (24h)</h3>
          {memos.length === 0 ? (
            <p style={{ opacity: 0.3, fontSize: '0.9rem' }}>No memos generated yet.</p>
          ) : (
            memos.map(m => (
              <div 
                key={m.filename} 
                className={`memo-item ${selectedMemo?.filename === m.filename ? 'active' : ''}`} 
                onClick={() => viewMemo(m.filename)} 
                style={{ 
                  padding: '12px', borderRadius: '8px', cursor: 'pointer', marginBottom: '8px', 
                  border: '1px solid rgba(255,255,255,0.05)', 
                  background: selectedMemo?.filename === m.filename ? 'rgba(168,85,247,0.2)' : 'transparent',
                  color: selectedMemo?.filename === m.filename ? '#fff' : '#cbd5e1'
                }}
              >
                <div style={{ fontSize: '0.9rem', marginBottom: '4px' }}>📋 {m.filename}</div>
                <span className="date" style={{ fontSize: '0.75rem', opacity: 0.4 }}>
                  {m.created ? m.created.slice(0, 16).replace('T', ' ') : ''}
                </span>
              </div>
            ))
          )}
        </aside>
        
        <main className="memo-view" style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '12px', padding: '30px', minHeight: '300px', maxHeight: '500px', overflowY: 'auto' }}>
          {selectedMemo ? (
            <div className="memo-content">
              <h3 style={{ color: '#A855F7', marginBottom: '20px', borderBottom: '1px solid rgba(168,85,247,0.2)', paddingBottom: '10px' }}>
                {selectedMemo.filename}
              </h3>
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Inter", sans-serif', fontSize: '0.95rem', lineHeight: '1.6', color: '#e2e8f0', opacity: 0.9 }}>
                {selectedMemo.text}
              </pre>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.2, fontSize: '1.2rem', color: '#fff' }}>
              Select an upgrade memo to view strategic intelligence.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
