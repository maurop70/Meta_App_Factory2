import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const TechMWODetailModal = ({ mwo, closeModal, executeAction, isActuating, isSyncPending, setConsumeMwoId }) => {
  const [manualLog, setManualLog] = useState('');
  const [error, setError] = useState('');
  const [showCompleteForm, setShowCompleteForm] = useState(false);
  const [consumedParts, setConsumedParts] = useState([]);

  // Strict Actuation Lockout during local I/O / execution
  const isLocked = isActuating || isSyncPending;

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && !isLocked) closeModal();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [closeModal, isLocked]);

  // Load the read-only consumed-parts ledger for this MWO (mwo_consumed_parts).
  useEffect(() => {
    if (!mwo?.mwo_id) { setConsumedParts([]); return; }
    let mounted = true;
    api.get(`/mwo/${mwo.mwo_id}/consumed-parts`)
      .then(res => { if (mounted) setConsumedParts(res.data?.data || []); })
      .catch(() => { if (mounted) setConsumedParts([]); });
    return () => { mounted = false; };
  }, [mwo?.mwo_id]);

  if (!mwo) return null;

  const handleComplete = async (e) => {
    e.preventDefault();
    setError('');
    
    // We delegate the API call and state tracking to the Dashboard's executeAction
    // The modal is locked (isActuating=true) while this awaits.
    // Once the ledger ingestion completes, the parent will automatically force a teardown.
    await executeAction(mwo.mwo_id, 'COMPLETE', {
      manual_log: manualLog.trim()
    });
  };

  const modalContent = (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 99990, fontFamily: "var(--font, Inter)"
    }}
    onClick={() => { if (!isLocked) closeModal(); }}>
      <div style={{
        position: 'relative', background: 'var(--bg-card, #0f172a)', border: '1px solid rgba(16, 185, 129, 0.3)',
        borderRadius: '16px', width: '90%', maxWidth: '600px', padding: '2.5rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', overflow: 'hidden'
      }} onClick={e => e.stopPropagation()}>

        {/* Processing Lockout Overlay */}
        {isLocked && (
          <div style={{
            position: 'absolute', inset: 0, background: isSyncPending ? 'rgba(245, 158, 11, 0.85)' : 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(6px)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 50, color: isSyncPending ? '#fff' : '#34d399'
          }}>
            <div style={{ fontWeight: 800, fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '1rem' }}>
              {isSyncPending ? 'SYNC PENDING...' : 'Processing Actuation...'}
            </div>
            <div style={{ fontSize: '0.9rem', opacity: 0.9, textAlign: 'center' }}>
              {isSyncPending ? 'Awaiting network reconnection to permanently seal the ledger.' : 'Committing transaction to ledger. Do not close.'}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
          <div>
            <h2 style={{ margin: '0 0 0.5rem 0', color: '#e2e8f0', fontSize: '1.5rem' }}>{mwo.mwo_id} Details</h2>
            <span style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 800, background: 'rgba(16, 185, 129, 0.2)', color: '#10b981' }}>
              {mwo.status}
            </span>
          </div>
          <button 
            onClick={closeModal} 
            disabled={isLocked}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: isLocked ? 'not-allowed' : 'pointer', opacity: isLocked ? 0.3 : 1 }}
          >
            &times;
          </button>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '8px', color: '#cbd5e1', fontSize: '0.95rem', lineHeight: '1.6', marginBottom: '2rem' }}>
          <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#94a3b8' }}>Equipment:</strong> {mwo.equipment_nomenclature || mwo.equipment_id}</div>
          <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#94a3b8' }}>Location:</strong> {mwo.location_nomenclature || mwo.location_id || 'Zone Alpha'}</div>
          <div><strong style={{ color: '#94a3b8' }}>Description:</strong><br/>{mwo.description}</div>
        </div>

        {consumedParts.length > 0 && (
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1.25rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.75rem' }}>Consumed Parts</div>
            {consumedParts.map((p, i) => (
              <div key={p.part_id || i} style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1', fontSize: '0.9rem', padding: '0.35rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <span>{p.nomenclature || p.sku_id} <span style={{ color: '#64748b' }}>({p.part_id})</span></span>
                <span style={{ color: '#94a3b8' }}>Qty {p.quantity_consumed}</span>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
            {error}
          </div>
        )}

        {!showCompleteForm ? (
          <div style={{ display: 'flex', gap: '1rem', flexDirection: 'column' }}>
            {(mwo.status === 'ASSIGNED' || mwo.status === 'PAUSED') && (
              <button 
                onClick={() => executeAction(mwo.mwo_id, 'START')}
                disabled={isLocked}
                style={{ padding: '1rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 800, cursor: isLocked ? 'not-allowed' : 'pointer', transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '1px' }}
              >
                Start Execution
              </button>
            )}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button 
                onClick={() => setConsumeMwoId(mwo.mwo_id)}
                disabled={isLocked || mwo.status !== 'IN_PROGRESS'}
                style={{ flex: 1, padding: '1rem', background: 'rgba(148, 163, 184, 0.1)', color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.3)', borderRadius: '8px', fontWeight: 800, cursor: (isLocked || mwo.status !== 'IN_PROGRESS') ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              >
                CONSUME PART
              </button>
              <button 
                onClick={() => setShowCompleteForm(true)}
                disabled={isLocked || mwo.status !== 'IN_PROGRESS'}
                style={{ flex: 1, padding: '1rem', background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 800, cursor: (isLocked || mwo.status !== 'IN_PROGRESS') ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              >
                EXECUTE COMPLETION
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleComplete} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>Manual Resolution Log <span style={{ color: '#ef4444' }}>*</span></label>
              <textarea value={manualLog} onChange={(e) => setManualLog(e.target.value)} required rows="4" disabled={isLocked} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
              <button type="button" onClick={() => setShowCompleteForm(false)} disabled={isLocked} style={{ flex: 1, padding: '0.8rem', background: 'transparent', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#e2e8f0', borderRadius: '6px', cursor: isLocked ? 'not-allowed' : 'pointer', fontWeight: 600 }}>Cancel</button>
              <button type="submit" disabled={isLocked} style={{ flex: 2, padding: '0.8rem', background: 'var(--accent-green, #10b981)', border: 'none', color: '#fff', borderRadius: '6px', cursor: isLocked ? 'not-allowed' : 'pointer', fontWeight: 600 }}>
                {isLocked ? 'Actuating...' : 'Finalize Completion'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default TechMWODetailModal;
