import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

const TechCompletionModal = ({ selectedMWO, closeModal, executeCompletion }) => {
  const [consumedSku, setConsumedSku] = useState('');
  const [manualLog, setManualLog] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const isMounted = useRef(true);
  useEffect(() => {
    return () => { isMounted.current = false; };
  }, []);

  // Isolation Guard: Trap focus inside modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && !isSubmitting) closeModal();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [closeModal, isSubmitting]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!manualLog.trim()) {
      setError('Manual log is strictly required for completion.');
      return;
    }
    
    setIsSubmitting(true);
    setError('');
    
    try {
      await executeCompletion(selectedMWO.mwo_id, {
        consumed_sku: consumedSku.trim() || null,
        manual_log: manualLog.trim()
      });
      closeModal();
    } catch (err) {
      if (isMounted.current) {
        setError(err.response?.data?.detail || 'Execution failed. Telemetry sync error.');
        setIsSubmitting(false);
      }
    }
  };

  const modalContent = (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 99999, // Explicit ejection from CSS stacking context
      fontFamily: "var(--font, Inter)"
    }}>
      <div style={{
        background: 'var(--bg-card, #0f172a)',
        border: '1px solid var(--border, rgba(16, 185, 129, 0.3))',
        borderRadius: '12px',
        width: '90%',
        maxWidth: '500px',
        padding: '2rem',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
      }}>
        <h2 style={{ marginTop: 0, color: '#e2e8f0', fontSize: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          Execute Completion
          <span style={{ fontSize: '0.8rem', padding: '0.2rem 0.6rem', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', borderRadius: '12px' }}>
            {selectedMWO.mwo_id}
          </span>
        </h2>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', marginTop: '1.5rem' }}>
          
          {error && (
            <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>
              Consumed SKU (Optional)
            </label>
            <input 
              type="text" 
              value={consumedSku}
              onChange={(e) => setConsumedSku(e.target.value)}
              placeholder="e.g. BEAR-608-ZZ"
              style={{
                width: '100%',
                padding: '0.75rem',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                color: '#e2e8f0',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>
              Manual Resolution Log <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <textarea 
              value={manualLog}
              onChange={(e) => setManualLog(e.target.value)}
              required
              rows="4"
              placeholder="Detailed explanation of physical resolution..."
              style={{
                width: '100%',
                padding: '0.75rem',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                color: '#e2e8f0',
                outline: 'none',
                resize: 'vertical',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1rem' }}>
            <button 
              type="button" 
              onClick={closeModal}
              disabled={isSubmitting}
              style={{
                padding: '0.6rem 1.2rem',
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#e2e8f0',
                borderRadius: '6px',
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                fontWeight: 600
              }}
            >
              Cancel
            </button>
            <button 
              type="submit"
              disabled={isSubmitting}
              style={{
                padding: '0.6rem 1.2rem',
                background: 'var(--accent-green, #10b981)',
                border: 'none',
                color: '#fff',
                borderRadius: '6px',
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                boxShadow: '0 4px 6px -1px rgba(16, 185, 129, 0.2)'
              }}
            >
              {isSubmitting ? 'Executing...' : 'Finalize Completion'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default TechCompletionModal;
