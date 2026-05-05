import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const MwoClosureModal = ({ isOpen, onClose, mwoId, onCompleteSuccess }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [formData, setFormData] = useState({ resolution_notes: '', labor_hours: '' });
  const [error, setError] = useState(null);

  // Transit Lockout: Escape key listener
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && !isProcessing) onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose, isProcessing]);

  // Reset form state when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({ resolution_notes: '', labor_hours: '' });
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isProcessing) return;

    const hours = parseFloat(formData.labor_hours);
    if (isNaN(hours) || hours <= 0) {
      setError('Labor hours must be a positive number.');
      return;
    }

    try {
      setIsProcessing(true);
      setError(null);

      // 1. Atomic Termination Dispatch
      await api.post(`/mwo/${mwoId}/complete`, {
        resolution_notes: formData.resolution_notes,
        labor_hours: hours
      });

      // 2. Success Resolution Phase — Transit Lockout HELD
      await onCompleteSuccess();

      // 3. Post-resolution teardown
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Termination actuation failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '0.7rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.3rem', color: '#94a3b8',
    fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em'
  };

  const modalContent = (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={() => { if (!isProcessing) onClose(); }}
    >
      <div
        style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '16px', padding: '2rem', width: '520px', maxWidth: '90vw', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
            Finalize Work Order
          </h3>
          <button
            onClick={onClose}
            disabled={isProcessing}
            style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: isProcessing ? 'not-allowed' : 'pointer', fontSize: '0.75rem', fontWeight: 600, opacity: isProcessing ? 0.5 : 1 }}
          >
            ESC
          </button>
        </div>

        <div style={{ padding: '0.5rem 0.8rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', marginBottom: '1.5rem' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600 }}>TERMINATION TARGET: </span>
          <span style={{ color: '#f87171', fontWeight: 700, fontSize: '0.85rem' }}>{mwoId}</span>
        </div>

        {error && (
          <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>
              Resolution Notes <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <textarea
              required
              rows="4"
              value={formData.resolution_notes}
              onChange={e => setFormData({ ...formData, resolution_notes: e.target.value })}
              disabled={isProcessing}
              placeholder="Detailed explanation of physical resolution performed..."
              style={{ ...inputStyle, resize: 'vertical', cursor: isProcessing ? 'not-allowed' : 'text' }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>
              Labor Hours <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="number"
              step="0.25"
              min="0.25"
              required
              value={formData.labor_hours}
              onChange={e => setFormData({ ...formData, labor_hours: e.target.value })}
              disabled={isProcessing}
              placeholder="e.g. 2.5"
              style={{ ...inputStyle, cursor: isProcessing ? 'not-allowed' : 'text' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isProcessing}
              style={{ flex: 1, padding: '0.7rem', background: 'rgba(148, 163, 184, 0.1)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '8px', cursor: isProcessing ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.85rem', opacity: isProcessing ? 0.5 : 1, transition: 'all 0.2s' }}
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isProcessing || !formData.resolution_notes.trim() || !formData.labor_hours}
              style={{ flex: 1, padding: '0.7rem', background: isProcessing || !formData.resolution_notes.trim() ? 'rgba(239, 68, 68, 0.2)' : 'linear-gradient(135deg, #ef4444, #dc2626)', color: isProcessing || !formData.resolution_notes.trim() ? '#94a3b8' : '#fff', border: 'none', borderRadius: '8px', cursor: isProcessing || !formData.resolution_notes.trim() ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: isProcessing || !formData.resolution_notes.trim() ? 'none' : '0 4px 15px rgba(239, 68, 68, 0.25)' }}
            >
              {isProcessing ? 'FINALIZING...' : 'SEAL WORK ORDER'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default MwoClosureModal;
