import re

p = 'factory_ui/src/WarRoom.jsx'
with open(p, 'r', encoding='utf-8') as f:
    code = f.read()

# Add a function to load wisdom
wisdom_loader = """  const loadWisdom = async () => {
    setWisdomLoading(true);
    try {
      const pRes = await axios.get('http://localhost:8000/api/wisdom/pending');
      setPendingStandards(pRes.data);
      const aRes = await axios.get('http://localhost:8000/api/wisdom/standards');
      setActiveStandards(aRes.data);
    } catch(e) { console.error('Wisdom load failed', e); }
    setWisdomLoading(false);
  };

  const approveStandard = async (id) => {
    await axios.post('http://localhost:8000/api/wisdom/approve', { standard_id: id });
    loadWisdom();
  };

  const rejectStandard = async (id) => {
    await axios.post('http://localhost:8000/api/wisdom/reject', { standard_id: id });
    loadWisdom();
  };
"""

insert_point = "  // ── Auto-scroll ───────────────────────────────────────"
code = code.replace(insert_point, wisdom_loader + '\n' + insert_point)

# Now inject the modals at the end of the return
modal_code = """
      {/* ── DISPATCH MODAL ── */}
      {showDispatchModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '24px', width: '400px', fontFamily: 'Inter, sans-serif' }}>
            <h2 style={{ margin: '0 0 16px', color: '#f8fafc', fontSize: '18px' }}>🚀 Strategic Dispatch</h2>
            
            <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '8px' }}>Philosophy Intent:</p>
            <select 
              value={strategyMode} 
              onChange={e => setStrategyMode(e.target.value)}
              style={{ width: '100%', padding: '10px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', marginBottom: '16px' }}
            >
              <option value="balanced">⚖️ Balanced (Standard 7.0)</option>
              <option value="aggressive_growth">🚀 Aggressive Growth (Lowers gates to 6.0)</option>
              <option value="lean_mvp">🔬 Lean MVP (Raises gates to 8.0)</option>
              <option value="custom">✏️ Custom Directive</option>
            </select>
            
            {strategyMode === 'custom' && (
              <textarea 
                value={customDirective}
                onChange={e => setCustomDirective(e.target.value)}
                placeholder="Custom steering directive..."
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', marginBottom: '16px', height: '60px' }}
              />
            )}
            
            <div style={{ background: stressTest ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.05)', border: `1px solid ${stressTest ? '#ef4444' : '#334155'}`, padding: '12px', borderRadius: '8px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => setStressTest(!stressTest)}>
              <div style={{ width: '20px', height: '20px', borderRadius: '4px', border: `2px solid ${stressTest ? '#ef4444' : '#64748b'}`, background: stressTest ? '#ef4444' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {stressTest && <span style={{ color: '#fff', fontSize: '14px' }}>✓</span>}
              </div>
              <div>
                <div style={{ color: stressTest ? '#ef4444' : '#f8fafc', fontWeight: 'bold', fontSize: '14px' }}>Execute Red Team Chaos Drill</div>
                <div style={{ color: '#64748b', fontSize: '11px' }}>Simulate a crisis scenario post-pipeline.</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '12px' }}>
              <button onClick={() => setShowDispatchModal(false)} style={{ flex: 1, padding: '12px', background: 'transparent', border: '1px solid #334155', color: '#cbd5e1', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>Cancel</button>
              <button onClick={executeDispatch} style={{ flex: 2, padding: '12px', background: stressTest ? 'linear-gradient(90deg, #ef4444, #dc2626)' : 'linear-gradient(90deg, #3b82f6, #2563eb)', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', animation: stressTest ? 'pulsePhase 1.5s infinite' : 'none' }}>
                {stressTest ? 'LAUNCH DRILL 🔴' : 'AUTHORIZE DISPATCH 🚀'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── WISDOM VAULT SIDEBAR ── */}
      {showWisdomVault && (
        <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: '450px', background: '#0a0e17', borderLeft: '1px solid #1e293b', zIndex: 9999, display: 'flex', flexDirection: 'column', fontFamily: 'Inter, sans-serifOuter', boxShadow: '-10px 0 30px rgba(0,0,0,0.5)' }}>
          <div style={{ padding: '20px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ margin: 0, color: '#f8fafc', fontSize: '18px' }}>💡 Wisdom Vault</h2>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>Cross-Project Intelligence Memory</span>
            </div>
            <button onClick={() => setShowWisdomVault(false)} style={{ background: 'transparent', border: 'none', color: '#ef4444', fontSize: '24px', cursor: 'pointer' }}>×</button>
          </div>
          
          <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
            <h3 style={{ color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #334155', paddingBottom: '8px', marginBottom: '16px' }}>PENDING PROPOSALS ({pendingStandards.length})</h3>
            {wisdomLoading ? <div style={{ color: '#64748b' }}>Refreshing Vault...</div> : null}
            
            {pendingStandards.map(std => (
              <div key={std.standard_id} style={{ background: '#1e293b', border: '1px solid #3b82f6', borderRadius: '8px', padding: '14px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ background: '#3b82f620', color: '#60a5fa', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{std.domain.toUpperCase()}</span>
                  <span style={{ background: '#10b98120', color: '#34d399', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{(std.confidence * 100).toFixed(0)}% CONFIDENCE</span>
                </div>
                <h4 style={{ margin: '0 0 8px', color: '#f8fafc', fontSize: '14px' }}>{std.title}</h4>
                <p style={{ margin: '0 0 12px', color: '#cbd5e1', fontSize: '12px', lineHeight: 1.4 }}>{std.insight}</p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => approveStandard(std.standard_id)} style={{ flex: 1, padding: '8px', background: '#22c55e', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>APPROVE AS LAW</button>
                  <button onClick={() => rejectStandard(std.standard_id)} style={{ flex: 1, padding: '8px', background: '#ef4444', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>REJECT</button>
                </div>
              </div>
            ))}
            {pendingStandards.length === 0 && !wisdomLoading && <div style={{ color: '#64748b', fontSize: '12px', marginBottom: '24px' }}>No new proposals from the C-Suite.</div>}

            <h3 style={{ color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #334155', paddingBottom: '8px', marginTop: '32px', marginBottom: '16px' }}>ACTIVE CORPORATE STANDARDS ({activeStandards.length})</h3>
            {activeStandards.map(std => (
              <div key={std.standard_id} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '14px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{std.domain.toUpperCase()}</span>
                </div>
                <h4 style={{ margin: '0 0 8px', color: '#cbd5e1', fontSize: '13px' }}>{std.title}</h4>
                <p style={{ margin: 0, color: '#64748b', fontSize: '11px', lineHeight: 1.4 }}>{std.insight}</p>
              </div>
            ))}
          </div>
        </div>
      )}
"""

code = code.replace('    </div>\n  );\n}', modal_code + '    </div>\n  );\n}')

# Add Wisdom Vault button to header
header_btn = """          <button onClick={() => { setShowWisdomVault(true); loadWisdom(); }}
            style={{
              padding: '6px 14px', borderRadius: '6px', border: '1px solid #4338ca',
              background: 'linear-gradient(90deg, #4f46e5, #4338ca)',
              color: '#fff', fontSize: '11px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginRight: '8px',
            }}
          >💡 Wisdom Vault</button>
          <button
            onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}"""
code = code.replace("""          <button
            onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}""", header_btn)


with open(p, 'w', encoding='utf-8') as f:
    f.write(code)

print('Added Modal logic!')
