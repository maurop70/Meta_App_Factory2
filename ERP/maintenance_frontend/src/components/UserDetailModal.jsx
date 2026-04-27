import React, { useEffect, useState, useRef } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const UserDetailModal = ({ userId, onClose, onActuationSuccess }) => {
  const [auditLog, setAuditLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmId, setConfirmId] = useState('');
  const [actuationStatus, setActuationStatus] = useState(null);
  
  const closeTimerRef = useRef(null);

  // Esc Key Interception & Timer Cleanup
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, [onClose]);

  useEffect(() => {
    let isMounted = true;
    const fetchAuditPayload = async () => {
      try {
        const response = await api.get(`/admin/users/${userId}/audit-log`);
        if (isMounted) {
          setAuditLog(response.data);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.response?.data?.detail || err.message || 'Failed to fetch contextual log.');
          setLoading(false);
        }
      }
    };
    fetchAuditPayload();
    return () => { isMounted = false; };
  }, [userId]);

  const handleTerminateAccess = async () => {
    if (confirmId !== userId) return; 
    
    setActuationStatus({ type: 'loading', message: 'Executing structural termination...' });
    try {
      await api.delete(`/admin/users/${userId}`);
      setActuationStatus({ type: 'success', message: 'Access terminated successfully.' });
      
      closeTimerRef.current = setTimeout(() => {
        onActuationSuccess(); // Trigger parent refresh and close
      }, 2000);
    } catch (err) {
      setActuationStatus({ type: 'error', message: err.response?.data?.detail || 'System actuation failed.' });
    }
  };

  const modalContent = (
    <div 
      className="modal-overlay" 
      role="dialog" 
      aria-modal="true"
      style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.85)', zIndex: 9999, display: 'flex', justifyContent: 'center', alignItems: 'center', backdropFilter: 'blur(4px)' }}
    >
      <div className="modal-container" style={{ background: 'var(--bg-dark, #0a0e17)', padding: '2rem', borderRadius: '12px', border: '1px solid var(--border)', width: '90%', maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '1rem' }}>
          <h2 style={{ color: 'var(--text-primary)', margin: 0, fontSize: '1.25rem' }}>System Actuation: <span style={{ color: 'var(--accent)' }}>{userId}</span></h2>
          <button onClick={onClose} aria-label="Close modal" style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.5rem', transition: 'color 0.2s' }}>×</button>
        </div>

        {loading && <div style={{ color: 'var(--text-secondary)', padding: '2rem', textAlign: 'center' }}>Ingesting contextual audit log...</div>}
        {error && <div style={{ color: 'var(--danger)', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>{error}</div>}
        
        {auditLog && (
          <>
            <div className="audit-context" style={{ marginBottom: '2.5rem', padding: '1rem', background: 'var(--bg-card, rgba(15, 23, 42, 0.5))', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.02)' }}>
              <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Contextual History</h3>
              {auditLog.events?.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontStyle: 'italic' }}>No prior structural mutations logged for this subject.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {auditLog.events.map((event, idx) => (
                     <li key={idx} style={{ fontSize: '0.85rem', color: 'var(--text-primary)', borderBottom: '1px solid rgba(255,255,255,0.05)', padding: '0.75rem 0' }}>
                       <span style={{ color: 'var(--accent, #818cf8)', marginRight: '1rem', fontFamily: 'monospace' }}>[{event.timestamp}]</span>
                       {event.action}
                     </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="actuation-zone" style={{ border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', padding: '1.5rem', background: 'rgba(239, 68, 68, 0.05)' }}>
              <h3 style={{ color: 'var(--danger, #ef4444)', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>⚠️</span> Destructive Actuation
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                To execute structural access revocation, strictly type the exact User ID (<strong style={{ color: 'white' }}>{userId}</strong>) below to authorize the transaction.
              </p>
              
              <input 
                type="text" 
                value={confirmId}
                onChange={(e) => setConfirmId(e.target.value)}
                placeholder={`Type ${userId} to confirm`}
                disabled={actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                style={{ width: '100%', boxSizing: 'border-box', padding: '0.75rem', marginBottom: '1rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px', fontFamily: 'monospace' }}
              />
              <button 
                onClick={handleTerminateAccess}
                disabled={confirmId !== userId || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                style={{ 
                  width: '100%', padding: '0.8rem', fontWeight: 700, borderRadius: '4px', transition: 'all 0.2s',
                  cursor: confirmId === userId ? 'pointer' : 'not-allowed',
                  background: confirmId === userId ? 'var(--danger, #ef4444)' : 'rgba(239, 68, 68, 0.1)',
                  color: confirmId === userId ? 'white' : 'var(--text-muted, #64748b)',
                  border: 'none', letterSpacing: '0.05em'
                }}
              >
                {actuationStatus?.type === 'loading' ? 'EXECUTING TRANSACTION...' : 'TERMINATE SYSTEM ACCESS'}
              </button>
              {actuationStatus && (
                <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '4px', textAlign: 'center', fontSize: '0.85rem', fontWeight: 600, color: actuationStatus.type === 'error' ? 'var(--danger)' : 'var(--success)', background: actuationStatus.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)' }}>
                  {actuationStatus.message}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default UserDetailModal;
