import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const EquipmentActuationModal = ({ isOpen, onClose, equipment, onActuateSuccess }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [technicians, setTechnicians] = useState([]);
  const [lookupsLoading, setLookupsLoading] = useState(true);
  const [confirmRetire, setConfirmRetire] = useState(false);

  // Mutable state — only status and assigned_tech_id are editable
  const [status, setStatus] = useState('');
  const [assignedTechId, setAssignedTechId] = useState('');

  // Initialize from equipment prop
  useEffect(() => {
    if (isOpen && equipment) {
      setStatus(equipment.status || 'ACTIVE');
      setAssignedTechId(equipment.assigned_tech_id || '');
      setError(null);
      setConfirmRetire(false);
    }
  }, [isOpen, equipment]);

  // Fetch technician lookup on mount
  useEffect(() => {
    if (!isOpen) return;
    const fetchTechs = async () => {
      setLookupsLoading(true);
      try {
        const res = await api.get('/admin/lookups/technicians?limit=100&offset=0');
        setTechnicians(res.data.data || []);
      } catch (err) {
        console.error("Technician lookup failure:", err);
      } finally {
        setLookupsLoading(false);
      }
    };
    fetchTechs();
  }, [isOpen]);

  // Transit Lockout: Escape key
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && !isProcessing) onClose(false);
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose, isProcessing]);

  // Reset retirement confirmation when status changes away from RETIRED
  useEffect(() => {
    if (status !== 'RETIRED') setConfirmRetire(false);
  }, [status]);

  if (!isOpen || !equipment) return null;

  const isRetired = equipment.status === 'RETIRED';
  const isDirty = status !== equipment.status || assignedTechId !== (equipment.assigned_tech_id || '');
  const isRetiring = status === 'RETIRED';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isProcessing || isRetired) return;

    // Retirement confirmation gate
    if (isRetiring && !confirmRetire) {
      setConfirmRetire(true);
      return;
    }

    try {
      setIsProcessing(true);
      setError(null);

      await api.put(`/admin/equipment/${equipment.equipment_id}/actuate`, {
        status: status,
        assigned_tech_id: isRetiring ? null : (assignedTechId || null)
      });

      // Transit lockout held through success resolution
      await onActuateSuccess();
      onClose(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Actuation failed.');
    } finally {
      setIsProcessing(false);
    }
  };



  const inputStyle = {
    width: '100%', padding: '0.65rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.25rem', color: '#94a3b8',
    fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em'
  };

  const readOnlyStyle = {
    padding: '0.5rem 0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.05)', color: '#cbd5e1', fontSize: '0.85rem'
  };

  const statusColors = {
    ACTIVE: { bg: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: 'rgba(16, 185, 129, 0.3)' },
    DEGRADED: { bg: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
    OFFLINE: { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: 'rgba(239, 68, 68, 0.3)' },
    RETIRED: { bg: 'rgba(107, 114, 128, 0.2)', color: '#9ca3af', border: 'rgba(107, 114, 128, 0.3)' }
  };

  const currentColors = statusColors[equipment.status] || statusColors.ACTIVE;

  const modalContent = (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={() => { if (!isProcessing) onClose(false); }}
    >
      <div
        style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: `1px solid ${currentColors.border}`, borderRadius: '16px', padding: '2rem', width: '540px', maxWidth: '92vw', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
              Equipment Actuation Gateway
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.75rem', margin: '0.25rem 0 0 0' }}>
              State mutation | Tech reassignment | Retirement
            </p>
          </div>
          <button
            onClick={() => onClose(false)}
            disabled={isProcessing}
            style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: isProcessing ? 'not-allowed' : 'pointer', fontSize: '0.75rem', fontWeight: 600, opacity: isProcessing ? 0.5 : 1 }}
          >
            ESC
          </button>
        </div>

        {/* Read-Only Context Block */}
        <div style={{ background: 'rgba(0,0,0,0.25)', borderRadius: '10px', padding: '1rem', marginBottom: '1.25rem', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
            <div>
              <span style={{ ...labelStyle, marginBottom: '0.15rem' }}>Equipment ID</span>
              <div style={readOnlyStyle}>{equipment.equipment_id}</div>
            </div>
            <div>
              <span style={{ ...labelStyle, marginBottom: '0.15rem' }}>Current Status</span>
              <div style={{ ...readOnlyStyle, background: currentColors.bg, color: currentColors.color, border: `1px solid ${currentColors.border}`, fontWeight: 700 }}>
                {equipment.status}
              </div>
            </div>
          </div>
          <div style={{ marginTop: '0.6rem' }}>
            <span style={{ ...labelStyle, marginBottom: '0.15rem' }}>Nomenclature</span>
            <div style={readOnlyStyle}>{equipment.nomenclature}</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', marginTop: '0.6rem' }}>
            <div>
              <span style={{ ...labelStyle, marginBottom: '0.15rem' }}>Category</span>
              <div style={readOnlyStyle}>{equipment.category || 'N/A'}</div>
            </div>
            <div>
              <span style={{ ...labelStyle, marginBottom: '0.15rem' }}>Department</span>
              <div style={readOnlyStyle}>{equipment.department || 'N/A'}</div>
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        {isRetired ? (
          <div style={{ padding: '1rem', background: 'rgba(107, 114, 128, 0.1)', border: '1px solid rgba(107, 114, 128, 0.2)', borderRadius: '8px', color: '#9ca3af', textAlign: 'center', fontSize: '0.85rem', fontWeight: 600 }}>
            PERMANENTLY LOCKED — This equipment has been retired and cannot be actuated.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {/* Mutable Fields */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', marginBottom: '1rem' }}>
              <div>
                <label style={labelStyle}>Target Status <span style={{ color: '#ef4444' }}>*</span></label>
                <select
                  value={status}
                  onChange={e => setStatus(e.target.value)}
                  disabled={isProcessing}
                  style={{ ...inputStyle, cursor: isProcessing ? 'not-allowed' : 'pointer', appearance: 'auto' }}
                >
                  <option value="ACTIVE" style={{ background: '#0f172a' }}>ACTIVE</option>
                  <option value="DEGRADED" style={{ background: '#0f172a' }}>DEGRADED</option>
                  <option value="OFFLINE" style={{ background: '#0f172a' }}>OFFLINE</option>
                  <option value="RETIRED" style={{ background: '#0f172a', color: '#ef4444' }}>RETIRED (Permanent)</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Assigned Tech <span style={{ color: '#64748b', fontWeight: 400 }}>(optional)</span></label>
                <select
                  value={isRetiring ? '' : assignedTechId}
                  onChange={e => setAssignedTechId(e.target.value)}
                  disabled={isProcessing || isRetiring || lookupsLoading}
                  style={{ ...inputStyle, cursor: (isProcessing || isRetiring) ? 'not-allowed' : 'pointer', appearance: 'auto', opacity: isRetiring ? 0.4 : 1 }}
                >
                  <option value="" style={{ background: '#0f172a', color: '#64748b' }}>-- Unassigned --</option>
                  {technicians.map(tech => (
                    <option key={tech.id} value={tech.id} style={{ background: '#0f172a', color: '#e2e8f0' }}>{tech.name} ({tech.id})</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Retirement Warning */}
            {isRetiring && (
              <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '8px', marginBottom: '1rem' }}>
                <p style={{ color: '#f87171', fontSize: '0.8rem', margin: 0, fontWeight: 600 }}>
                  ⚠ DESTRUCTIVE ACTION — Retiring equipment is permanent. The entity will be locked from all future MWOs and state mutations. Tech assignment will be cleared.
                </p>
                {confirmRetire && (
                  <p style={{ color: '#fbbf24', fontSize: '0.75rem', margin: '0.5rem 0 0', fontWeight: 700 }}>
                    Click "RETIRE EQUIPMENT" again to confirm permanent retirement.
                  </p>
                )}
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button
                type="button"
                onClick={() => onClose(false)}
                disabled={isProcessing}
                style={{ flex: 1, padding: '0.7rem', background: 'rgba(148, 163, 184, 0.1)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '8px', cursor: isProcessing ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.85rem', opacity: isProcessing ? 0.5 : 1 }}
              >
                CANCEL
              </button>
              <button
                type="submit"
                disabled={isProcessing || (!isDirty && !isRetiring)}
                style={{
                  flex: 1, padding: '0.7rem', border: 'none', borderRadius: '8px', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s',
                  background: isRetiring
                    ? (confirmRetire ? 'linear-gradient(135deg, #dc2626, #991b1b)' : 'linear-gradient(135deg, #ef4444, #dc2626)')
                    : (isProcessing || !isDirty ? 'rgba(99, 102, 241, 0.15)' : 'linear-gradient(135deg, #6366f1, #4f46e5)'),
                  color: (isProcessing || (!isDirty && !isRetiring)) ? '#64748b' : '#fff',
                  cursor: (isProcessing || (!isDirty && !isRetiring)) ? 'not-allowed' : 'pointer',
                  boxShadow: (isProcessing || (!isDirty && !isRetiring)) ? 'none' : isRetiring ? '0 4px 15px rgba(239, 68, 68, 0.25)' : '0 4px 15px rgba(99, 102, 241, 0.25)'
                }}
              >
                {isProcessing ? 'ACTUATING...' : isRetiring ? (confirmRetire ? 'CONFIRM RETIREMENT' : 'RETIRE EQUIPMENT') : 'COMMIT STATE'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default EquipmentActuationModal;
