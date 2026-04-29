import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom';

const HMAssignmentModal = ({ selectedMWO, closeModal, executeAssignment, technicianRoster = [] }) => {
  const [selectedTech, setSelectedTech] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  
  // Memory Leak Prevention: Track physical mount state
  const isMounted = useRef(true);
  
  useEffect(() => {
    return () => { isMounted.current = false; };
  }, []);

  // 1. CLOSURE VECTOR: Escape Key Listener
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

  // 2. CLOSURE VECTOR: Backdrop Click Handler
  const handleBackdropClick = (e) => {
    if (isSubmitting) return;
    if (e.target === e.currentTarget) {
      closeModal();
    }
  };

  const handleExecute = async () => {
    if (!selectedTech) {
      setErrorMsg("Validation Error: Please select a technician.");
      return;
    }
    
    setErrorMsg(null);
    setIsSubmitting(true);
    
    try {
      await executeAssignment(selectedMWO.mwo_id, selectedTech);
      
      // Structural Lockout: Only trigger unmount callbacks if parent hasn't already destroyed the portal
      if (isMounted.current) {
        closeModal();
      }
    } catch (err) {
      if (isMounted.current) {
        setErrorMsg(err.response?.data?.detail || err.message || "Assignment failed.");
        setIsSubmitting(false);
      }
    }
  };

  const modalContent = (
    <div 
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
          borderRadius: '12px', padding: '2rem', width: '90%', maxWidth: '500px', 
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', color: '#fff',
          cursor: 'default',
          opacity: isSubmitting ? 0.6 : 1,
          pointerEvents: isSubmitting ? 'none' : 'auto',
          transition: 'opacity 0.2s ease-in-out'
        }}
      >
        <h3 style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.75rem', marginBottom: '1.5rem', fontWeight: 600 }}>
          {isSubmitting ? 'EXECUTING ASSIGNMENT...' : 'WORK ORDER ASSIGNMENT'}
        </h3>
        
        {/* Payload Context (Mandatory Review Isolation) */}
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1.25rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '1.5rem' }}>
          <p style={{ marginBottom: '0.5rem' }}><strong style={{ color: '#94a3b8' }}>MWO ID:</strong> <span style={{ color: '#818cf8', fontWeight: 600 }}>{selectedMWO.mwo_id}</span></p>
          <p style={{ marginBottom: '0.5rem' }}><strong style={{ color: '#94a3b8' }}>Equipment:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedMWO.equipment_id}</span></p>
          <p style={{ marginBottom: '0.5rem' }}><strong style={{ color: '#94a3b8' }}>DM Urgency:</strong> {selectedMWO.dm_urgency || 'Normal'}</p>
          <p style={{ marginBottom: '0' }}><strong style={{ color: '#94a3b8' }}>Description:</strong><br/>
            <span style={{ color: '#e2e8f0', display: 'inline-block', marginTop: '0.5rem', lineHeight: '1.6' }}>
              {selectedMWO.description}
            </span>
          </p>
        </div>
        
        {errorMsg && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '1rem', borderRadius: '6px', color: '#fca5a5', marginBottom: '1.5rem', fontSize: '0.875rem' }}>
            {errorMsg}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <select 
            style={{ 
              padding: '0.875rem', borderRadius: '6px', background: 'rgba(0, 0, 0, 0.4)', 
              color: '#fff', border: '1px solid rgba(255,255,255,0.2)', outline: 'none',
              cursor: isSubmitting ? 'not-allowed' : 'pointer'
            }}
            value={selectedTech} 
            onChange={(e) => setSelectedTech(e.target.value)}
            disabled={isSubmitting}
          >
            <option value="">-- Select Technician --</option>
            {technicianRoster.map((tech) => (
              <option key={tech.user_id} value={tech.user_id}>
                {tech.user_id} ({tech.name || 'Technician'})
              </option>
            ))}
          </select>
          
          <button 
            onClick={handleExecute}
            disabled={isSubmitting || !selectedTech}
            style={{ 
              background: (isSubmitting || !selectedTech) ? 'rgba(16, 185, 129, 0.2)' : 'var(--success, #10b981)', 
              color: (isSubmitting || !selectedTech) ? '#94a3b8' : '#fff', 
              padding: '0.875rem', borderRadius: '6px', border: 'none', 
              cursor: (isSubmitting || !selectedTech) ? 'not-allowed' : 'pointer', 
              fontWeight: 600, transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '0.05em'
            }}
          >
            {isSubmitting ? 'Transmitting...' : 'Execute Assignment'}
          </button>
        </div>

        {/* 3. CLOSURE VECTOR: UI Close Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '1.25rem' }}>
          <button 
            onClick={closeModal} 
            disabled={isSubmitting}
            style={{ 
              padding: '0.5rem 1rem', background: 'transparent', color: isSubmitting ? '#475569' : '#94a3b8', 
              border: '1px solid', borderColor: isSubmitting ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.2)', 
              borderRadius: '6px', cursor: isSubmitting ? 'not-allowed' : 'pointer', fontWeight: 600, transition: 'all 0.2s' 
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default HMAssignmentModal;
