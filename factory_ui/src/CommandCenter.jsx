import React, { useState, useEffect, useRef } from 'react';
import './index.css';

// ═══════════════════════════════════════════════════════════
// COMMAND CENTER — ANTIGRAVITY AETHER-NATIVE DASHBOARD
// ═══════════════════════════════════════════════════════════



const SEQUENCE_STAGES = [
  { id: 'CMO_STRATEGY', label: '1. CMO Strategy', icon: '📈' },
  { id: 'CTO_EVALUATION', label: '2. CTO Stack Evaluator', icon: '⚙️' },
  { id: 'CFO_MODELING', label: '3. CFO Architect', icon: '📊' },
  { id: 'ADVERSARIAL_GATES', label: '4. Critic & UI Phantom', icon: '🛡️' },
  { id: 'COMMERCIALLY_READY', label: '5. Launch Ready', icon: '🚀' }
];

export default function CommandCenter({ projectName = "Aether" }) {
  const [sequenceState, setSequenceState] = useState({});
  const [logs, setLogs] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [operatorCmd, setOperatorCmd] = useState('');
  const [isSendingCmd, setIsSendingCmd] = useState(false);
  
  const bottomRef = useRef(null);

  const sendOperatorCmd = async () => {
    if (!operatorCmd.trim()) return;
    setIsSendingCmd(true);
    try {
      await fetch('/api/war-room/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: operatorCmd.trim(),
          project_id: projectName || 'AntigravityWorkspace_Q3',
          strategy_mode: 'operator_directive'
        })
      });
      setLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(),
        agent: 'COMMANDER',
        message: `[OPERATOR COMMAND] ${operatorCmd.trim()}`
      }]);
      setOperatorCmd('');
    } catch(e) {
      console.error('Operator dispatch failed', e);
    } finally {
      setIsSendingCmd(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Connect to the unified _broadcast stream natively
  useEffect(() => {
    const eventSource = new EventSource(`/api/war-room/stream?project=${projectName}`);
    
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        
        // 1. The Live Feed (Terminal styled)
        if (data.type === 'dialogue') {
            setLogs(prev => [...prev, {
                time: new Date().toLocaleTimeString(),
                agent: data.agent || 'SYSTEM',
                message: data.message
            }]);
        }
        
        if (data.type === 'error') {
            setLogs(prev => [...prev, {
                time: new Date().toLocaleTimeString(),
                agent: 'SYSTEM FAULT',
                message: data.error,
                isError: true
            }]);
        }

        // 2. The JSON State-Machine Stepper
        if (data.type === 'state_machine') {
            setSequenceState(prev => ({
                ...prev,
                [data.phase]: data.status // 'PROCESSING', 'PASS', 'FAIL'
            }));
            
            if (data.status === 'PROCESSING') setCurrentPhase(data.phase);
            
            if (data.phase === 'COMMERCIALLY_READY' && data.status === 'PASS') {
                setIsReady(true);
                setIsExecuting(false);
            }
            if (data.status === 'FAIL') {
                setIsExecuting(false);
            }
        }

      } catch (err) {
        console.error("Stream parse error:", err);
      }
    };

    return () => eventSource.close();
  }, [projectName]);

  const triggerUnifiedExecution = async () => {
      setIsExecuting(true);
      setIsReady(false);
      setSequenceState({});
      setLogs([{ time: new Date().toLocaleTimeString(), agent: 'COMMANDER', message: `Initiating Aether-Native Execution for ${projectName}...` }]);
      
      try {
          await fetch(`/api/warroom/execute`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ project_id: projectName })
          });
      } catch (error) {
          setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), agent: 'SYSTEM', message: `Execution failed to start: ${error.message}`, isError: true }]);
          setIsExecuting(false);
      }
  };

  const deployToProduction = () => {
      alert(`🚀 Launching ${projectName} to Production via Antigravity Cloud!`);
  };

  const viewFinancials = () => {
      window.open(`file://C:/Users/mpetr/.gemini/antigravity/projects/${projectName}/artifacts/cfo_reports/business_plan.xlsx`, '_blank');
  };

  return (
    <div className="command-center-container" style={{ padding: '20px', color: '#e2e8f0', background: '#0f172a', borderRadius: '12px', height: '100%', display: 'flex', flexDirection: 'column', gap: '20px', fontFamily: '"Inter", sans-serif' }}>
        
        {/* Header section */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #334155', paddingBottom: '15px' }}>
            <div>
                <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#38bdf8' }}>🌐 AETHER-NATIVE COMMAND CENTER</h1>
                <p style={{ margin: '5px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>Target: <span style={{ color: '#fff' }}>{projectName}</span> — Zero-Latency Internal Execution</p>
            </div>
            
            <div style={{ display: 'flex', gap: '10px' }}>
                <button 
                  onClick={viewFinancials}
                  style={{ background: '#334155', color: 'white', border: '1px solid #475569', padding: '10px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
                >
                  📊 View Financials
                </button>
                <button 
                  onClick={triggerUnifiedExecution} 
                  disabled={isExecuting}
                  style={{ background: isExecuting ? '#475569' : '#6366f1', color: 'white', border: 'none', padding: '10px 20px', borderRadius: '6px', cursor: isExecuting ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}
                >
                  {isExecuting ? '⚡ Executing...' : '▶ Initialize Protocol'}
                </button>
            </div>
        </div>

        {/* State Machine Visual Stepper */}
        <div style={{ display: 'flex', justifyContent: 'space-between', background: '#1e293b', padding: '20px', borderRadius: '8px', border: '1px solid #334155' }}>
            {SEQUENCE_STAGES.map((stage, index) => {
                const status = sequenceState[stage.id] || 'WAITING';
                let color = '#64748b'; // default waiting
                let iconPulse = false;
                
                if (status === 'PROCESSING') { color = '#eab308'; iconPulse = true; } // Yellow
                if (status === 'PASS') color = '#22c55e'; // Green
                if (status === 'FAIL') color = '#ef4444'; // Red

                // Add chevron connector between items
                return (
                    <React.Fragment key={stage.id}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: status === 'WAITING' ? 0.6 : 1, transition: 'all 0.3s' }}>
                            <div style={{ 
                                fontSize: '24px', 
                                width: '50px', 
                                height: '50px', 
                                borderRadius: '50%', 
                                background: status === 'WAITING' ? '#0f172a' : `${color}20`,
                                border: `2px solid ${color}`,
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                animation: iconPulse ? 'pulse 1.5s infinite' : 'none'
                             }}>
                                {stage.icon}
                            </div>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: status === 'WAITING' ? '#94a3b8' : '#f8fafc' }}>{stage.label}</span>
                            <span style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '12px', background: `${color}30`, color: color, fontWeight: 'bold' }}>
                                {status.replace('_', ' ')}
                            </span>
                        </div>
                        {index < SEQUENCE_STAGES.length - 1 && (
                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', margin: '0 15px' }}>
                                <div style={{ height: '3px', width: '100%', background: (sequenceState[SEQUENCE_STAGES[index + 1]?.id] && sequenceState[SEQUENCE_STAGES[index + 1]?.id] !== 'WAITING') ? '#22c55e' : '#334155', borderRadius: '3px', transition: 'background 0.5s' }} />
                            </div>
                        )}
                    </React.Fragment>
                );
            })}
        </div>

        {/* Live Terminal Feed */}
        <div style={{ flex: 1, background: '#020617', borderRadius: '8px', border: '1px solid #334155', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '10px 15px', background: '#0f172a', borderBottom: '1px solid #334155', fontSize: '12px', fontWeight: 'bold', color: '#94a3b8', display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: isExecuting ? '#22c55e' : '#64748b' }}></span>
                LIVE COMMAND CORE FEED
            </div>
            <div style={{ padding: '15px', overflowY: 'auto', flex: 1, fontFamily: '"Fira Code", monospace', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {logs.length === 0 ? (
                    <div style={{ color: '#475569', textAlign: 'center', marginTop: '40px' }}>No active telemetry. Initialize protocol to begin.</div>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} style={{ display: 'flex', gap: '15px', color: log.isError ? '#f87171' : '#cbd5e1' }}>
                            <span style={{ color: '#64748b', whiteSpace: 'nowrap' }}>[{log.time}]</span>
                            <span style={{ color: log.isError ? '#ef4444' : '#38bdf8', minWidth: '100px', fontWeight: 'bold' }}>{log.agent}</span>
                            <span style={{ whiteSpace: 'pre-wrap' }}>{log.message}</span>
                        </div>
                    ))
                )}
                <div ref={bottomRef} />
            </div>
        </div>

        {/* ── Active Command Bar (Phase 11) ── */}
        <div style={{
          display: 'flex', gap: '8px', padding: '16px',
          background: '#0a0f18', borderTop: '1px solid rgba(100,116,139,0.2)',
          borderRadius: '0 0 8px 8px'
        }}>
          <span style={{ fontSize: '20px', display: 'flex', alignItems: 'center' }}>⚡</span>
          <input 
            type="text"
            placeholder="@Operator command / directives..."
            value={operatorCmd}
            onChange={e => setOperatorCmd(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendOperatorCmd()}
            style={{
                flex: 1, background: '#1e293b', border: '1px solid #475569',
                color: '#f8fafc', padding: '12px 16px', borderRadius: '8px',
                fontSize: '14px', fontFamily: '"Fira Code", monospace'
            }}
          />
          <button 
            onClick={sendOperatorCmd}
            disabled={!operatorCmd.trim() || isSendingCmd}
            style={{
              background: operatorCmd.trim() ? 'linear-gradient(135deg, #10b981, #059669)' : '#334155',
              color: 'white', border: 'none', padding: '0 24px', borderRadius: '8px',
              fontWeight: 'bold', cursor: operatorCmd.trim() ? 'pointer' : 'not-allowed'
            }}
          >
            {isSendingCmd ? '...' : 'DISPATCH'}
          </button>
        </div>

        {/* Commercial Action Footer */}
        <div style={{ borderTop: '1px solid #334155', paddingTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={deployToProduction}
              disabled={!isReady}
              style={{
                  background: isReady ? 'linear-gradient(90deg, #10b981 0%, #059669 100%)' : '#334155',
                  color: isReady ? 'white' : '#94a3b8',
                  padding: '14px 28px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  cursor: isReady ? 'pointer' : 'not-allowed',
                  boxShadow: isReady ? '0 4px 15px rgba(16, 185, 129, 0.4)' : 'none',
                  transition: 'all 0.3s ease'
              }}
            >
              {isReady ? '🚀 DEPLOY TO PRODUCTION' : '🔒 DEPLOY LOCKED (AWAITING VERDICT)'}
            </button>
        </div>

        <style>{`
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0.4); }
                70% { box-shadow: 0 0 0 10px rgba(234, 179, 8, 0); }
                100% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
            }
        `}</style>
    </div>
  );
}

