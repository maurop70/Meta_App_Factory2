import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import TechMWODetailModal from './TechMWODetailModal';
import TechConsumePartModal from './TechConsumePartModal';
import { useAuth } from '../context/AuthContext';

const TechDashboard = () => {
  const { userRole, jwtPayload } = useAuth();
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Assigned Work Orders...' });
  const [actuatingMwo, setActuatingMwo] = useState({});
  const [offlineLedger, setOfflineLedger] = useState([]);
  
  // Modals
  const [selectedDetailMWO, setSelectedDetailMWO] = useState(null);
  const [consumeMwoId, setConsumeMwoId] = useState(null);
  const techId = jwtPayload?.sub || 'Unknown Tech';
  const [technicianRoster, setTechnicianRoster] = useState([]);
  const [targetTech, setTargetTech] = useState('');
  const navigate = useNavigate();

  const fetchRoster = async () => {
    try {
      const response = await api.get('/mwo/technicians');
      const payload = response.data?.data || response.data;
      setTechnicianRoster(Array.isArray(payload) ? payload : []);
    } catch (err) {
      console.warn("Failed to fetch roster", err);
    }
  };

  useEffect(() => {
    if (['ADMINISTRATOR', 'ADMIN', 'HM'].includes(userRole)) {
      fetchRoster();
    }
  }, [userRole]);

  const syncLedgerState = useCallback(() => {
    const queue = JSON.parse(localStorage.getItem('mwoExecutionQueue') || '[]');
    setOfflineLedger(queue);
  }, []);

  const fetchAssignedMWO = useCallback(async () => {
    try {
      const url = targetTech ? `/mwo/assigned?limit=50&offset=0&target_tech=${encodeURIComponent(targetTech)}` : `/mwo/assigned?limit=50&offset=0`;
      const response = await api.get(url);
      const dbPayload = response.data.data || response.data;
      const rawOrders = Array.isArray(dbPayload) ? dbPayload : [];
      setWorkOrders(rawOrders.filter(o => o.status !== 'COMPLETED'));
      setStatus({ type: 'success', message: '' });
    } catch (err) {
      console.warn("Network fragmentation detected.", err);
      if (workOrders.length === 0) {
        setStatus({ type: 'error', message: 'Offline Mode: Waiting for connection...' });
      }
    }
  }, [targetTech, workOrders.length]);

  const flushQueue = useCallback(async () => {
    if (!navigator.onLine) return;
    const queue = JSON.parse(localStorage.getItem('mwoExecutionQueue') || '[]');
    if (queue.length === 0) return;
    
    let newQueue = [...queue];
    let didChange = false;

    for (let i = 0; i < queue.length; i++) {
      const item = queue[i];
      if (item.errorMsg) continue; // Skip items requiring manual resolution

      try {
        await api.patch(`/mwo/${item.mwo_id}/execute`, item.payload);
        newQueue = newQueue.filter(q => q.id !== item.id);
        didChange = true;
      } catch (err) {
        if (!err.response || err.code === 'ERR_NETWORK' || err.response?.status === 504 || err.response?.status === 502) {
           break; // Stop automated flush on physical network partition
        } else {
           // Permanent Backend Rejection -> Shift to SYNC_FAILED
           const failedIndex = newQueue.findIndex(q => q.id === item.id);
           if (failedIndex > -1) {
             newQueue[failedIndex].errorMsg = err.response.data.detail || "Backend rejection error.";
             didChange = true;
           }
        }
      }
    }
    
    if (didChange) {
      localStorage.setItem('mwoExecutionQueue', JSON.stringify(newQueue));
      syncLedgerState();
      fetchAssignedMWO(); 
    }
  }, [fetchAssignedMWO, syncLedgerState]);

  useEffect(() => {
    syncLedgerState();
    fetchAssignedMWO();
    window.addEventListener('online', flushQueue);
    const interval = setInterval(flushQueue, 5000); // 5 sec background watchdog
    
    return () => {
      window.removeEventListener('online', flushQueue);
      clearInterval(interval);
    };
  }, [fetchAssignedMWO, flushQueue, syncLedgerState]);

  // Keep the modal's state completely synchronized with the latest ledger representation
  useEffect(() => {
    if (selectedDetailMWO) {
      const updatedMWO = workOrders.find(m => m.mwo_id === selectedDetailMWO.mwo_id);
      if (updatedMWO && updatedMWO.status !== selectedDetailMWO.status) {
        setSelectedDetailMWO(updatedMWO);
      }
    }
  }, [workOrders, selectedDetailMWO]);

  const executeAction = async (mwo_id, action, additionalPayload = {}) => {
    setActuatingMwo(prev => ({ ...prev, [mwo_id]: true }));
    const payload = { action, ...additionalPayload };
    
    try {
      await api.patch(`/mwo/${mwo_id}/execute`, payload);
      await fetchAssignedMWO();
      if (action === 'COMPLETE') {
        setSelectedDetailMWO(null);
      }
    } catch (err) {
      if (!err.response || err.code === 'ERR_NETWORK' || err.response?.status === 504 || err.response?.status === 502) {
        const queue = JSON.parse(localStorage.getItem('mwoExecutionQueue') || '[]');
        queue.push({
          id: Date.now().toString() + Math.random().toString(36).substring(2, 5),
          mwo_id,
          payload,
          timestamp: Date.now()
        });
        localStorage.setItem('mwoExecutionQueue', JSON.stringify(queue));
        syncLedgerState(); // Triggers SYNC_PENDING overlay natively
      } else {
        alert(err.response?.data?.detail || "Execution conflict detected.");
      }
    } finally {
      setActuatingMwo(prev => ({ ...prev, [mwo_id]: false }));
    }
  };

  const retrySync = (ledgerItem) => {
    const queue = JSON.parse(localStorage.getItem('mwoExecutionQueue') || '[]');
    const idx = queue.findIndex(q => q.id === ledgerItem.id);
    if (idx > -1) {
      delete queue[idx].errorMsg;
      localStorage.setItem('mwoExecutionQueue', JSON.stringify(queue));
      syncLedgerState();
      flushQueue(); 
    }
  };

  const discardSync = (ledgerItem) => {
    const queue = JSON.parse(localStorage.getItem('mwoExecutionQueue') || '[]');
    const newQueue = queue.filter(q => q.id !== ledgerItem.id);
    localStorage.setItem('mwoExecutionQueue', JSON.stringify(newQueue));
    syncLedgerState();
  };

  if (status.type === 'loading') return <div style={{ color: '#94a3b8', padding: '2rem' }}>{status.message}</div>;

  return (
    <div className="erp-dashboard-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border, rgba(56, 189, 248, 0.2))', paddingBottom: '1rem' }}>
        <h2 style={{ color: 'var(--text-primary, #e2e8f0)', fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
          Technician Execution
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {['ADMINISTRATOR', 'ADMIN', 'HM'].includes(userRole) && (
            <select 
              value={targetTech} 
              onChange={(e) => setTargetTech(e.target.value)}
              style={{
                background: 'rgba(15, 23, 42, 0.8)', color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.4rem 0.8rem',
                borderRadius: '6px', fontWeight: 600, fontSize: '0.85rem', outline: 'none'
              }}
            >
              <option value="">-- Impersonate Tech --</option>
              {(Array.isArray(technicianRoster) ? technicianRoster : []).map(tech => (
                <option key={tech.user_id} value={tech.user_id}>{tech.user_id} ({tech.name})</option>
              ))}
            </select>
          )}
          <button type="button" onClick={() => navigate('/archive')} style={{ background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '0.4rem 0.8rem', borderRadius: '6px', color: '#818cf8', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s' }}>
            VIEW ARCHIVES
          </button>
          <div style={{ background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.4rem 0.8rem', borderRadius: '6px', color: '#38bdf8', fontWeight: 600, fontSize: '0.85rem' }}>
            Tech ID: {targetTech || techId}
          </div>
        </div>
      </div>
      
      <h2 style={{ color: '#e2e8f0', marginBottom: '1.5rem', fontSize: '1.4rem' }}>
        {!navigator.onLine && <span style={{ marginLeft: '1rem', fontSize: '0.8rem', color: '#fbbf24', background: 'rgba(245,158,11,0.2)', padding: '4px 8px', borderRadius: '4px' }}>OFFLINE - SYNC QUEUED</span>}
      </h2>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {workOrders.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', color: '#64748b' }}>
            No pending execution targets.
          </div>
        ) : (
          (Array.isArray(workOrders) ? workOrders : []).filter(mwo => mwo != null).map(mwo => {
            const isActuating = actuatingMwo[mwo.mwo_id];
            const ledgerItem = (offlineLedger || []).find(q => q && q.mwo_id === mwo.mwo_id);
            const isSyncPending = ledgerItem && !ledgerItem.errorMsg;
            const isSyncFailed = ledgerItem && ledgerItem.errorMsg;
            
            return (
              <div key={mwo.mwo_id} style={{
                position: 'relative',
                background: 'var(--bg-card, #0f172a)',
                border: mwo.status === 'IN_PROGRESS' ? '2px solid #10b981' : '2px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '16px',
                padding: '1.5rem',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
                overflow: 'hidden'
              }}>
                {/* SYNC_FAILED Overlay (Red) */}
                {isSyncFailed && (
                  <div style={{
                    position: 'absolute', inset: 0, background: 'rgba(239, 68, 68, 0.9)', backdropFilter: 'blur(8px)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 20,
                    color: '#fff', padding: '2rem', textAlign: 'center'
                  }}>
                    <div style={{ fontWeight: 800, fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem' }}>
                      SYNC FAILED
                    </div>
                    <div style={{ fontSize: '0.9rem', marginBottom: '1.5rem', maxWidth: '80%' }}>
                      {ledgerItem.errorMsg}
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', width: '100%', maxWidth: '300px' }}>
                      <button onClick={() => retrySync(ledgerItem)} style={{
                        flex: 1, minHeight: '48px', background: '#fff', color: '#ef4444', border: 'none', borderRadius: '8px',
                        fontWeight: 800, fontSize: '0.9rem', cursor: 'pointer'
                      }}>RETRY</button>
                      <button onClick={() => discardSync(ledgerItem)} style={{
                        flex: 1, minHeight: '48px', background: 'transparent', color: '#fff', border: '2px solid rgba(255,255,255,0.5)', borderRadius: '8px',
                        fontWeight: 800, fontSize: '0.9rem', cursor: 'pointer'
                      }}>DISCARD</button>
                    </div>
                  </div>
                )}

                {/* SYNC_PENDING Overlay (Amber) */}
                {isSyncPending && !isSyncFailed && (
                  <div style={{
                    position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.85)', backdropFilter: 'blur(6px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 15,
                    color: '#fff', fontWeight: 800, fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '2px'
                  }}>
                    SYNC PENDING...
                  </div>
                )}

                {/* Actuating Overlay */}
                {isActuating && !ledgerItem && (
                  <div style={{
                    position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.8)', backdropFilter: 'blur(4px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10,
                    color: '#34d399', fontWeight: 800, fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '2px'
                  }}>
                    Actuating...
                  </div>
                )}
                
                {/* Card Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                  <div>
                    <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.2rem' }}>{mwo.mwo_id}</h3>
                    <p style={{ margin: '0.3rem 0 0 0', color: '#94a3b8', fontSize: '0.9rem' }}>{mwo.equipment_nomenclature || mwo.equipment_id} • {mwo.location_nomenclature || mwo.location_id || 'Zone Alpha'}</p>
                  </div>
                  <span style={{
                    padding: '6px 12px', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 800,
                    background: mwo.status === 'IN_PROGRESS' ? 'rgba(16, 185, 129, 0.2)' : mwo.status === 'PAUSED' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(148, 163, 184, 0.1)',
                    color: mwo.status === 'IN_PROGRESS' ? '#10b981' : mwo.status === 'PAUSED' ? '#fbbf24' : '#94a3b8'
                  }}>
                    {mwo.status}
                  </span>
                </div>
                
                {/* Description */}
                <div style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', color: '#cbd5e1', fontSize: '0.95rem', lineHeight: '1.5' }}>
                  {mwo.description}
                </div>

                {/* Actuation Matrix (Touch-Optimized) */}
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {(mwo.status === 'ASSIGNED' || mwo.status === 'PAUSED') && (
                    <button 
                      onClick={() => executeAction(mwo.mwo_id, 'START')}
                      disabled={isActuating || !!ledgerItem}
                      style={{
                        flex: 1, minHeight: '48px', minWidth: '120px',
                        background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px',
                        fontWeight: 800, fontSize: '1rem', textTransform: 'uppercase',
                        boxShadow: '0 4px 14px 0 rgba(16, 185, 129, 0.39)', cursor: (isActuating || !!ledgerItem) ? 'not-allowed' : 'pointer',
                        opacity: (isActuating || !!ledgerItem) ? 0.5 : 1
                      }}
                    >
                      START
                    </button>
                  )}
                  
                  {mwo.status === 'IN_PROGRESS' && (
                      <button 
                        onClick={() => executeAction(mwo.mwo_id, 'PAUSE')}
                        disabled={isActuating || !!ledgerItem}
                        style={{
                          flex: 1, minHeight: '48px', minWidth: '120px',
                          background: '#fbbf24', color: '#1e293b', border: 'none', borderRadius: '8px',
                          fontWeight: 800, fontSize: '1rem', textTransform: 'uppercase',
                          boxShadow: '0 4px 14px 0 rgba(245, 158, 11, 0.39)', cursor: (isActuating || !!ledgerItem) ? 'not-allowed' : 'pointer',
                          opacity: (isActuating || !!ledgerItem) ? 0.5 : 1
                        }}
                      >
                        PAUSE
                      </button>
                  )}

                  <button 
                    onClick={() => setSelectedDetailMWO(mwo)}
                    disabled={isActuating || !!ledgerItem}
                    style={{
                      flex: 2, minHeight: '48px', minWidth: '160px',
                      background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px',
                      fontWeight: 800, fontSize: '0.9rem', textTransform: 'uppercase', cursor: (isActuating || !!ledgerItem) ? 'not-allowed' : 'pointer',
                      opacity: (isActuating || !!ledgerItem) ? 0.5 : 1
                    }}
                  >
                    OPEN MWO DETAILS
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <TechMWODetailModal
        mwo={selectedDetailMWO}
        closeModal={() => setSelectedDetailMWO(null)}
        executeAction={executeAction}
        isActuating={selectedDetailMWO ? actuatingMwo[selectedDetailMWO.mwo_id] : false}
        isSyncPending={selectedDetailMWO ? !!(offlineLedger || []).find(q => q && q.mwo_id === selectedDetailMWO.mwo_id && !q.errorMsg) : false}
        ledgerItem={selectedDetailMWO ? (offlineLedger || []).find(q => q && q.mwo_id === selectedDetailMWO.mwo_id) : null}
        setConsumeMwoId={setConsumeMwoId}
      />

      <TechConsumePartModal
        isOpen={!!consumeMwoId}
        onClose={() => setConsumeMwoId(null)}
        mwoId={consumeMwoId}
        onConsumeSuccess={() => fetchAssignedMWO()}
      />
    </div>
  );
};

export default TechDashboard;
