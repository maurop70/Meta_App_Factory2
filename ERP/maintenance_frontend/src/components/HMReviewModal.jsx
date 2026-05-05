import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

const HMReviewModal = ({ selectedMWO, closeModal, executeApproval }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  
  // Memory Leak Prevention: Track physical mount state
  const isMounted = useRef(true);
  
  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  // CLOSURE VECTOR: Escape Key Listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isSubmitting) {
        closeModal();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isSubmitting, closeModal]);

  if (!selectedMWO) return null;

  // CLOSURE VECTOR: Backdrop Click Handler
  const handleBackdropClick = (e) => {
    if (isSubmitting) return;
    if (e.target === e.currentTarget) {
      closeModal();
    }
  };

  const handleExecute = async () => {
    setErrorMsg(null);
    setIsSubmitting(true);
    
    try {
      await executeApproval(selectedMWO.mwo_id);
      
      if (isMounted.current) {
        closeModal();
      }
    } catch (err) {
      if (isMounted.current) {
        setErrorMsg(err.response?.data?.detail || err.message || "Approval failed.");
        setIsSubmitting(false);
      }
    }
  };

  const modalContent = (
    <div 
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={handleBackdropClick}
      style={{ 
        position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', 
        background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', 
        display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 99999,
        cursor: isSubmitting ? 'wait' : 'pointer'
      }}
    >
      <div 
        style={{ 
          background: 'var(--bg-card, rgba(15, 23, 42, 1))', 
          border: '1px solid rgba(255, 255, 255, 0.1)', 
          borderRadius: '12px', padding: '2rem', width: '90%', maxWidth: '600px', 
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', color: '#fff',
          cursor: 'default',
          opacity: isSubmitting ? 0.6 : 1,
          pointerEvents: isSubmitting ? 'none' : 'auto',
          transition: 'opacity 0.2s ease-in-out'
        }}
      >
        <h3 style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.75rem', marginBottom: '1.5rem', fontWeight: 600 }}>
          {isSubmitting ? 'FINALIZING WORK ORDER...' : 'WORK ORDER REVIEW & APPROVAL'}
        </h3>
        
        {/* Payload Context (Review Section) */}
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1.25rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div>
              <p style={{ margin: '0 0 0.5rem 0' }}><strong style={{ color: '#94a3b8' }}>MWO ID:</strong> <span style={{ color: '#818cf8', fontWeight: 600 }}>{selectedMWO.mwo_id}</span></p>
              <p style={{ margin: '0 0 0.5rem 0' }}><strong style={{ color: '#94a3b8' }}>Equipment:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedMWO.equipment_nomenclature || selectedMWO.equipment_id}</span></p>
            </div>
            <div>
              <p style={{ margin: '0 0 0.5rem 0', textAlign: 'right' }}><strong style={{ color: '#94a3b8' }}>Tech:</strong> {selectedMWO.assigned_tech}</p>
              <p style={{ margin: '0 0 0.5rem 0', textAlign: 'right' }}><strong style={{ color: '#94a3b8' }}>Labor Logged:</strong> {selectedMWO.labor_hours ? `${selectedMWO.labor_hours.toFixed(2)} hrs` : 'N/A'}</p>
            </div>
          </div>
          
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem', marginTop: '0.5rem' }}>
            <p style={{ margin: '0 0 0.5rem 0', color: '#94a3b8', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Resolution Notes / Manual Log:</p>
            <div style={{ 
              background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '6px', 
              color: '#cbd5e1', fontSize: '0.95rem', lineHeight: '1.6', 
              border: '1px solid rgba(255,255,255,0.05)', minHeight: '80px', whiteSpace: 'pre-wrap'
            }}>
              {selectedMWO.manual_log || "No manual log provided."}
            </div>
          </div>
        </div>
        
        {errorMsg && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '1rem', borderRadius: '6px', color: '#fca5a5', marginBottom: '1.5rem', fontSize: '0.875rem' }}>
            {errorMsg}
          </div>
        )}

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button 
            onClick={closeModal} 
            disabled={isSubmitting}
            style={{ 
              flex: 1, padding: '0.875rem', background: 'transparent', color: isSubmitting ? '#475569' : '#94a3b8', 
              border: '1px solid', borderColor: isSubmitting ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.2)', 
              borderRadius: '6px', cursor: isSubmitting ? 'not-allowed' : 'pointer', fontWeight: 600, transition: 'all 0.2s', textTransform: 'uppercase'
            }}
          >
            Cancel
          </button>
          
          <button 
            onClick={handleExecute}
            disabled={isSubmitting}
            style={{ 
              flex: 2, background: isSubmitting ? 'rgba(16, 185, 129, 0.2)' : 'var(--success, #10b981)', 
              color: isSubmitting ? '#94a3b8' : '#fff', 
              padding: '0.875rem', borderRadius: '6px', border: 'none', 
              cursor: isSubmitting ? 'not-allowed' : 'pointer', 
              fontWeight: 600, transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '0.05em'
            }}
          >
            {isSubmitting ? 'Transmitting...' : 'Approve & Finalize'}
          </button>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default HMReviewModal;
