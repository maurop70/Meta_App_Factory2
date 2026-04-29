import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const EquipmentDetailModal = ({ equipment, onClose }) => {
  const [status, setStatus] = useState(equipment.status);
  const [assignedTech, setAssignedTech] = useState(equipment.assigned_tech_id || '');
  const [technicians, setTechnicians] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Fetch Technicians for Relational Actuation via <select>
  useEffect(() => {
    let isMounted = true;
    const fetchTechs = async () => {
      try {
        const response = await api.get('/mwo/technicians');
        if (isMounted && response.data && response.data.data) {
          setTechnicians(response.data.data);
        }
      } catch (err) {
        if (isMounted) {
          console.error("Failed to fetch technicians", err);
          setError("Failed to load relational tech matrix.");
        }
      }
    };
    fetchTechs();
    return () => { isMounted = false; };
  }, []);

  const handleActuate = async () => {
    let isMounted = true;
    try {
      setIsSubmitting(true);
      setError(null);
      await api.patch(`/admin/equipment/${equipment.equipment_id}/status`, {
        status: status,
        assigned_tech_id: assignedTech === '' ? null : assignedTech
      });
      if (isMounted) {
        onClose(true); // signal refresh
      }
    } catch (err) {
      if (isMounted) {
        setError(err.response?.data?.detail || "Mutation failed. RBAC violation or network error.");
      }
    } finally {
      if (isMounted) {
        setIsSubmitting(false);
      }
    }
  };

  const modalContent = (
    <div style={styles.overlay}>
      <div style={styles.modal} role="dialog" aria-modal="true">
        <div style={styles.header}>
          <h3 style={styles.title}>Actuate Equipment State</h3>
          <button style={styles.closeBtn} onClick={() => onClose(false)} aria-label="Close modal">&times;</button>
        </div>
        
        <div style={styles.body}>
          {error && <div style={styles.errorMsg}>{error}</div>}
          
          <div style={styles.payloadContext}>
            <p style={{ margin: '0 0 0.5rem 0' }}><strong>ID:</strong> {equipment.equipment_id}</p>
            <p style={{ margin: '0 0 0.5rem 0' }}><strong>Nomenclature:</strong> {equipment.nomenclature}</p>
            <p style={{ margin: 0 }}><strong>Department:</strong> {equipment.department}</p>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Operational Status</label>
            <select 
              style={styles.select} 
              value={status} 
              onChange={(e) => setStatus(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="DEGRADED">DEGRADED</option>
              <option value="OFFLINE">OFFLINE</option>
            </select>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Assigned Technician (Optional)</label>
            <select 
              style={styles.select} 
              value={assignedTech} 
              onChange={(e) => setAssignedTech(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="">-- UNASSIGNED --</option>
              {technicians.map(t => (
                <option key={t.user_id} value={t.user_id}>{t.name} ({t.user_id})</option>
              ))}
            </select>
          </div>
        </div>

        <div style={styles.footer}>
          <button style={styles.cancelBtn} onClick={() => onClose(false)} disabled={isSubmitting}>
            CANCEL
          </button>
          <button 
            style={{...styles.actuateBtn, opacity: (isSubmitting || (status === equipment.status && assignedTech === (equipment.assigned_tech_id || ''))) ? 0.5 : 1}} 
            onClick={handleActuate} 
            disabled={isSubmitting || (status === equipment.status && assignedTech === (equipment.assigned_tech_id || ''))}
          >
            {isSubmitting ? 'ACTUATING...' : 'COMMIT STATE'}
          </button>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

const styles = {
  overlay: {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
    backdropFilter: 'blur(4px)'
  },
  modal: {
    background: '#1e293b',
    borderRadius: '12px',
    width: '90%',
    maxWidth: '500px',
    border: '1px solid rgba(99, 102, 241, 0.3)',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    fontFamily: 'var(--font, "Inter", sans-serif)'
  },
  header: {
    padding: '1.25rem 1.5rem',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: 'rgba(15, 23, 42, 0.5)'
  },
  title: {
    margin: 0,
    color: '#e2e8f0',
    fontSize: '1.1rem',
    fontWeight: '600'
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    fontSize: '1.5rem',
    cursor: 'pointer',
    lineHeight: 1
  },
  body: {
    padding: '1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem'
  },
  payloadContext: {
    background: 'rgba(0, 0, 0, 0.2)',
    padding: '1rem',
    borderRadius: '8px',
    fontSize: '0.9rem',
    color: '#cbd5e1',
    lineHeight: '1.6',
    border: '1px solid rgba(255, 255, 255, 0.05)'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem'
  },
  label: {
    color: '#94a3b8',
    fontSize: '0.85rem',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  },
  select: {
    width: '100%',
    padding: '0.75rem',
    background: '#0f172a',
    border: '1px solid rgba(99, 102, 241, 0.3)',
    borderRadius: '6px',
    color: '#e2e8f0',
    fontSize: '0.95rem',
    outline: 'none'
  },
  errorMsg: {
    background: 'rgba(239, 68, 68, 0.1)',
    color: '#ef4444',
    padding: '0.75rem',
    borderRadius: '6px',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    fontSize: '0.9rem'
  },
  footer: {
    padding: '1.25rem 1.5rem',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '1rem',
    background: 'rgba(15, 23, 42, 0.5)'
  },
  cancelBtn: {
    padding: '0.6rem 1.2rem',
    background: 'transparent',
    border: '1px solid #64748b',
    color: '#cbd5e1',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.85rem'
  },
  actuateBtn: {
    padding: '0.6rem 1.2rem',
    background: '#4f46e5',
    border: 'none',
    color: '#ffffff',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.85rem'
  }
};

export default EquipmentDetailModal;
