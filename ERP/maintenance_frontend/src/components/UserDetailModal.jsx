import React, { useEffect, useState, useRef } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const UserDetailModal = ({ userId, onClose, onActuationSuccess }) => {
  const [auditLog, setAuditLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmId, setConfirmId] = useState('');
  const [actuationStatus, setActuationStatus] = useState(null);
  
  // Escalation State
  const [escalationRole, setEscalationRole] = useState('TECH');
  const [escalationDept, setEscalationDept] = useState('');
  // Designation: department inventory manager (auto-provisions the department's
  // inventory category on the backend when checked).
  const [isInventoryManager, setIsInventoryManager] = useState(false);

  // Procurement SKU clearance state
  const [skuAccess, setSkuAccess] = useState({ assigned: [], available: [] });
  const [skuToAssign, setSkuToAssign] = useState('');
  const [procMsg, setProcMsg] = useState(null);

  // Quick-issue draft state
  const [issueSku, setIssueSku] = useState('');
  const [issueQty, setIssueQty] = useState(1);
  const [issueNotes, setIssueNotes] = useState('');

  const closeTimerRef = useRef(null);

  // Esc Key Interception & Timer Cleanup
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    
    const isLocked = actuationStatus?.type === 'loading' || actuationStatus?.type === 'success';
    
    // Temporarily unbind global Escape key interception while loading or success
    if (!isLocked) {
      window.addEventListener('keydown', handleKeyDown);
    }
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose, actuationStatus?.type]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

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

  const handleEscalateUser = async () => {
    setActuationStatus({ type: 'loading', message: 'Executing structural escalation...' });
    try {
      const payload = {
        role: escalationRole,
        department: escalationDept,
        is_inventory_manager: isInventoryManager
      };
      
      const response = await api.put(`/admin/users/${userId}/escalate`, payload);
      
      // Seamlessly handle both the 205 Reset Content and 200 OK responses
      if (response.status === 205) {
        setActuationStatus({ type: 'success', message: 'Self-escalation successful. Re-authenticating...' });
      } else {
        setActuationStatus({ type: 'success', message: 'Role escalation successful.' });
      }

      closeTimerRef.current = setTimeout(() => {
        onActuationSuccess(); // Trigger parent refresh and close
      }, 2000);
    } catch (err) {
      setActuationStatus({ type: 'error', message: err.response?.data?.detail || 'System actuation failed.' });
    }
  };

  const loadSkuAccess = async () => {
    try {
      const { data } = await api.get(`/admin/users/${userId}/skus`);
      setSkuAccess({ assigned: data.assigned || [], available: data.available || [] });
    } catch (err) {
      // Non-fatal: leave the clearances panel empty if the fetch degrades.
      console.warn('SKU access fetch degraded', err.response?.status || err.message);
    }
  };

  useEffect(() => { loadSkuAccess(); }, [userId]);

  const handleAssignSku = async () => {
    if (!skuToAssign) return;
    setProcMsg(null);
    try {
      await api.post(`/admin/users/${userId}/skus`, { sku_id: skuToAssign });
      setSkuToAssign('');
      await loadSkuAccess();
      setProcMsg({ type: 'success', message: 'SKU clearance assigned.' });
    } catch (err) {
      setProcMsg({ type: 'error', message: err.response?.data?.detail || 'Assignment failed.' });
    }
  };

  const handleRevokeSku = async (skuId) => {
    setProcMsg(null);
    try {
      await api.delete(`/admin/users/${userId}/skus/${skuId}`);
      if (issueSku === skuId) setIssueSku('');
      await loadSkuAccess();
      setProcMsg({ type: 'success', message: `Revoked ${skuId}.` });
    } catch (err) {
      setProcMsg({ type: 'error', message: err.response?.data?.detail || 'Revoke failed.' });
    }
  };

  const handleIssueDraft = async () => {
    if (!issueSku || !(Number(issueQty) > 0)) return;
    setProcMsg(null);
    try {
      const { data } = await api.post(`/admin/users/${userId}/orders/drafts/add-item`, {
        sku_id: issueSku,
        quantity: Number(issueQty),
        notes: issueNotes || null
      });
      setProcMsg({ type: 'success', message: `Draft ${data.po_id} ${data.created ? 'created' : 'updated'} on behalf of ${userId}.` });
      setIssueQty(1);
      setIssueNotes('');
    } catch (err) {
      setProcMsg({ type: 'error', message: err.response?.data?.detail || 'Draft issuance failed.' });
    }
  };

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
      onClick={(e) => {
        // Unbind backdrop click handler during lockout
        const isLocked = actuationStatus?.type === 'loading' || actuationStatus?.type === 'success';
        if (e.target === e.currentTarget && !isLocked) {
          onClose();
        }
      }}
    >
      <div className="modal-container" style={{ background: 'var(--bg-dark, #0a0e17)', padding: '2rem', borderRadius: '12px', border: '1px solid var(--border)', width: '90%', maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '1rem' }}>
          <h2 style={{ color: 'var(--text-primary)', margin: 0, fontSize: '1.25rem' }}>System Actuation: <span style={{ color: 'var(--accent)' }}>{userId}</span></h2>
          <button 
            onClick={onClose} 
            disabled={actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
            aria-label="Close modal" 
            style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: (actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 'not-allowed' : 'pointer', fontSize: '1.5rem', transition: 'color 0.2s', opacity: (actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 0.5 : 1 }}
          >
            ×
          </button>
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

            <div className="escalation-zone" style={{ border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '8px', padding: '1.5rem', background: 'rgba(99, 102, 241, 0.05)', marginBottom: '1.5rem' }}>
              <h3 style={{ color: 'var(--accent, #6366f1)', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>⬆️</span> Role Escalation
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                Mutate the structural taxonomy clearance for this subject.
              </p>
              
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                <select 
                  value={escalationRole} 
                  onChange={(e) => setEscalationRole(e.target.value)}
                  disabled={actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                  style={{ flex: 1, padding: '0.75rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }}
                >
                  <option value="ADMIN">ADMIN</option>
                  <option value="DM">DM</option>
                  <option value="HM">HM</option>
                  <option value="TECH">TECH</option>
                </select>
                <input 
                  type="text" 
                  value={escalationDept} 
                  onChange={(e) => setEscalationDept(e.target.value)}
                  placeholder="Department String"
                  disabled={actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                  style={{ flex: 2, padding: '0.75rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px' }}
                />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: '1rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={isInventoryManager}
                  onChange={(e) => setIsInventoryManager(e.target.checked)}
                  disabled={actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                />
                Designate as Department Inventory Manager
              </label>
              <button
                onClick={handleEscalateUser}
                disabled={!escalationRole || !escalationDept.trim() || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success'}
                style={{ 
                  width: '100%', padding: '0.8rem', fontWeight: 700, borderRadius: '4px', transition: 'all 0.2s',
                  cursor: (!escalationRole || !escalationDept.trim() || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 'not-allowed' : 'pointer',
                  background: (!escalationRole || !escalationDept.trim() || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 'rgba(99, 102, 241, 0.1)' : 'var(--accent, #6366f1)',
                  color: (!escalationRole || !escalationDept.trim() || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 'var(--text-muted, #64748b)' : 'white',
                  border: 'none', letterSpacing: '0.05em'
                }}
              >
                EXECUTE ESCALATION
              </button>
            </div>

            {/* Procurement SKU Clearances */}
            <div className="sku-clearance-zone" style={{ border: '1px solid rgba(45, 212, 191, 0.3)', borderRadius: '8px', padding: '1.5rem', background: 'rgba(45, 212, 191, 0.05)', marginBottom: '1.5rem' }}>
              <h3 style={{ color: '#2dd4bf', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🔐</span> Procurement SKU Clearances
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: 1.5 }}>
                Restrict this subject's Inventory &amp; Procurement panel to the SKUs assigned below.
              </p>

              {skuAccess.assigned.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', marginBottom: '1rem' }}>No SKU clearances assigned.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1rem 0', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {skuAccess.assigned.map((s) => (
                    <li key={s.sku_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,0,0,0.25)', borderRadius: '6px', padding: '0.5rem 0.75rem' }}>
                      <span style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                        <span style={{ color: '#2dd4bf', fontWeight: 600, fontFamily: 'monospace', marginRight: '0.5rem' }}>{s.sku_id}</span>
                        {s.nomenclature}
                      </span>
                      <button
                        onClick={() => handleRevokeSku(s.sku_id)}
                        style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '4px', padding: '0.3rem 0.7rem', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                      >
                        Revoke
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <select
                  value={skuToAssign}
                  onChange={(e) => setSkuToAssign(e.target.value)}
                  style={{ flex: 1, padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px', fontSize: '0.82rem' }}
                >
                  <option value="">Select a SKU to clear...</option>
                  {skuAccess.available.map((s) => (
                    <option key={s.sku_id} value={s.sku_id}>{s.sku_id} — {s.nomenclature}</option>
                  ))}
                </select>
                <button
                  onClick={handleAssignSku}
                  disabled={!skuToAssign}
                  style={{ padding: '0.6rem 1rem', fontWeight: 700, borderRadius: '4px', border: 'none', whiteSpace: 'nowrap', cursor: skuToAssign ? 'pointer' : 'not-allowed', background: skuToAssign ? '#2dd4bf' : 'rgba(45, 212, 191, 0.15)', color: skuToAssign ? '#0a0e17' : 'var(--text-muted, #64748b)', fontSize: '0.8rem' }}
                >
                  Assign SKU Clearance
                </button>
              </div>
            </div>

            {/* Quick Issue Draft Order */}
            <div className="quick-issue-zone" style={{ border: '1px solid rgba(251, 191, 36, 0.3)', borderRadius: '8px', padding: '1.5rem', background: 'rgba(251, 191, 36, 0.05)', marginBottom: '1.5rem' }}>
              <h3 style={{ color: '#fbbf24', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>📝</span> Quick Issue Draft Order
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: 1.5 }}>
                Issue a draft purchase order on this subject's behalf, scoped to their assigned SKUs.
              </p>

              {skuAccess.assigned.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>Assign a SKU clearance above to enable draft issuance.</p>
              ) : (
                <>
                  <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <select
                      value={issueSku}
                      onChange={(e) => setIssueSku(e.target.value)}
                      style={{ flex: 2, padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px', fontSize: '0.82rem' }}
                    >
                      <option value="">Select assigned SKU...</option>
                      {skuAccess.assigned.map((s) => (
                        <option key={s.sku_id} value={s.sku_id}>{s.sku_id} — {s.nomenclature}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min="1"
                      value={issueQty}
                      onChange={(e) => setIssueQty(e.target.value)}
                      placeholder="Qty"
                      style={{ flex: 1, padding: '0.6rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px', fontSize: '0.82rem' }}
                    />
                  </div>
                  <textarea
                    value={issueNotes}
                    onChange={(e) => setIssueNotes(e.target.value)}
                    placeholder="Notes / special instructions for supplier..."
                    style={{ width: '100%', boxSizing: 'border-box', minHeight: '60px', resize: 'vertical', padding: '0.6rem', marginBottom: '0.75rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'white', borderRadius: '4px', fontSize: '0.82rem', fontFamily: 'inherit' }}
                  />
                  <button
                    onClick={handleIssueDraft}
                    disabled={!issueSku || !(Number(issueQty) > 0)}
                    style={{ width: '100%', padding: '0.75rem', fontWeight: 700, borderRadius: '4px', border: 'none', cursor: (issueSku && Number(issueQty) > 0) ? 'pointer' : 'not-allowed', background: (issueSku && Number(issueQty) > 0) ? '#fbbf24' : 'rgba(251, 191, 36, 0.15)', color: (issueSku && Number(issueQty) > 0) ? '#0a0e17' : 'var(--text-muted, #64748b)', fontSize: '0.85rem', letterSpacing: '0.03em' }}
                  >
                    Issue Draft PO on Behalf of User
                  </button>
                </>
              )}

              {procMsg && (
                <div style={{ marginTop: '1rem', padding: '0.6rem', borderRadius: '4px', textAlign: 'center', fontSize: '0.82rem', fontWeight: 600, color: procMsg.type === 'error' ? 'var(--danger, #ef4444)' : 'var(--success, #10b981)', background: procMsg.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)' }}>
                  {procMsg.message}
                </div>
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
                  cursor: (confirmId !== userId || actuationStatus?.type === 'loading' || actuationStatus?.type === 'success') ? 'not-allowed' : 'pointer',
                  background: (confirmId === userId && actuationStatus?.type !== 'loading' && actuationStatus?.type !== 'success') ? 'var(--danger, #ef4444)' : 'rgba(239, 68, 68, 0.1)',
                  color: (confirmId === userId && actuationStatus?.type !== 'loading' && actuationStatus?.type !== 'success') ? 'white' : 'var(--text-muted, #64748b)',
                  border: 'none', letterSpacing: '0.05em'
                }}
              >
                TERMINATE SYSTEM ACCESS
              </button>
            </div>
            
            {actuationStatus && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '4px', textAlign: 'center', fontSize: '0.85rem', fontWeight: 600, color: actuationStatus.type === 'error' ? 'var(--danger)' : 'var(--success)', background: actuationStatus.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)' }}>
                {actuationStatus.message}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default UserDetailModal;
