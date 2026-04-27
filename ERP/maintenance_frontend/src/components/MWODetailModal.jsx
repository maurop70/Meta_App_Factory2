import React, { useState } from 'react';

const MWODetailModal = ({ selectedMWO, closeModal, handlePatch }) => {
  const [selectedTech, setSelectedTech] = useState('');

  if (!selectedMWO) return null;

  // Determine Actuation State
  const isUnassigned = selectedMWO.status === 'UNASSIGNED';
  const isPendingReview = selectedMWO.status === 'PENDING_REVIEW';
  const isTerminal = selectedMWO.status === 'COMPLETED';
  const isAssignedActive = selectedMWO.assigned_tech && !isUnassigned && !isPendingReview && !isTerminal;

  const onExecuteAssignment = () => {
    if (!selectedTech) {
      alert("Validation Error: Please select a technician from the roster.");
      return;
    }
    handlePatch(selectedMWO, { assigned_tech: selectedTech, status: 'ASSIGNED' });
  };

  const onRevokeAssignment = () => {
    handlePatch(selectedMWO, { assigned_tech: null, status: 'UNASSIGNED' });
  };

  const onValidateComplete = () => {
    handlePatch(selectedMWO, { status: 'COMPLETED' });
  };

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
      <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.95))', border: '1px solid rgba(255, 255, 255, 0.12)', borderRadius: '12px', padding: '2rem', width: '90%', maxWidth: '500px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', color: '#fff' }}>
        <h3 style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.5rem', marginBottom: '1.5rem', fontWeight: 600 }}>Work Order Details</h3>
        
        <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '1.5rem' }}>
          <p style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#94a3b8' }}>MWO ID:</strong> <span style={{ color: '#818cf8', fontWeight: 600 }}>{selectedMWO.mwo_id}</span></p>
          <p style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#94a3b8' }}>Equipment:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedMWO.equipment_id || '—'}</span></p>
          <p style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#94a3b8' }}>Status:</strong> {selectedMWO.status}</p>
          <p style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#94a3b8' }}>DM Urgency:</strong> {selectedMWO.dm_urgency || 'Normal'}</p>
          <p style={{ marginBottom: '0' }}><strong style={{ color: '#94a3b8' }}>Description:</strong><br/><span style={{ color: '#e2e8f0', display: 'inline-block', marginTop: '0.3rem' }}>{selectedMWO.description}</span></p>
        </div>
        
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <h4 style={{ marginBottom: '1rem', color: '#e2e8f0', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Actuation Controls</h4>
          
          {isUnassigned && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <select 
                style={{ padding: '0.8rem', borderRadius: '6px', background: 'rgba(0, 0, 0, 0.2)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', outline: 'none' }}
                value={selectedTech} 
                onChange={(e) => setSelectedTech(e.target.value)}
              >
                <option value="">-- Select Technician Roster --</option>
                <option value="Tech-Alpha">Tech-Alpha</option>
                <option value="Tech-Bravo">Tech-Bravo</option>
                <option value="Tech-Charlie">Tech-Charlie</option>
              </select>
              <button 
                onClick={onExecuteAssignment}
                style={{ background: 'var(--success, #10b981)', color: '#fff', padding: '0.8rem', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600, transition: 'opacity 0.2s' }}
                onMouseOver={(e) => e.currentTarget.style.opacity = '0.9'}
                onMouseOut={(e) => e.currentTarget.style.opacity = '1'}
              >
                EXECUTE ASSIGNMENT
              </button>
            </div>
          )}

          {isAssignedActive && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <p style={{ padding: '0.8rem', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '6px' }}>
                <strong style={{ color: '#94a3b8' }}>Assigned To:</strong> <span style={{ color: '#38bdf8', fontWeight: 600, marginLeft: '0.5rem' }}>{selectedMWO.assigned_tech}</span>
              </p>
              <button 
                onClick={onRevokeAssignment}
                style={{ background: 'var(--danger, #ef4444)', color: '#fff', padding: '0.8rem', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600, transition: 'opacity 0.2s' }}
                onMouseOver={(e) => e.currentTarget.style.opacity = '0.9'}
                onMouseOut={(e) => e.currentTarget.style.opacity = '1'}
              >
                REVOKE ASSIGNMENT
              </button>
            </div>
          )}

          {isPendingReview && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <p style={{ padding: '0.8rem', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '6px' }}>
                <strong style={{ color: '#94a3b8' }}>Awaiting Validation From:</strong> <span style={{ color: '#fcd34d', fontWeight: 600 }}>HM</span>
              </p>
              <button 
                onClick={onValidateComplete}
                style={{ background: 'var(--success, #10b981)', color: '#fff', padding: '0.8rem', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600 }}
              >
                VALIDATE & COMPLETE
              </button>
            </div>
          )}

          {isTerminal && (
             <p style={{ color: '#10b981', fontWeight: 600 }}>WORK ORDER LOCKED</p>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
          <button onClick={closeModal} style={{ padding: '0.6rem 1.2rem', background: 'rgba(255, 255, 255, 0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, transition: 'background 0.2s' }} onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'} onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default MWODetailModal;
