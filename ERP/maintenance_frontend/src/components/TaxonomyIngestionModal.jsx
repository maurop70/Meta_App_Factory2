import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const TaxonomyIngestionModal = ({ isOpen, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState('DEPARTMENT');
  const [name, setName] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    setName('');
    setError(null);
  }, [isOpen, activeTab]);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && !isProcessing) onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose, isProcessing]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isProcessing || !name.trim()) return;

    try {
      setIsProcessing(true);
      setError(null);

      const endpoint = activeTab === 'DEPARTMENT' ? '/admin/ingest/department' : '/admin/ingest/location';
      await api.post(endpoint, { name: name.trim() });

      if (onSuccess) await onSuccess();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to ingest ${activeTab.toLowerCase()}.`);
    } finally {
      setIsProcessing(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '0.65rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
    transition: 'border-color 0.2s'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.25rem', color: '#94a3b8',
    fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em'
  };

  const modalContent = (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={() => { if (!isProcessing) onClose(); }}
    >
      <div
        style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '16px', padding: '2rem', width: '450px', maxWidth: '92vw', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
              Taxonomy Management
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.75rem', margin: '0.25rem 0 0 0' }}>
              Add global departments or physical locations
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: isProcessing ? 'not-allowed' : 'pointer', fontSize: '0.75rem', fontWeight: 600, opacity: isProcessing ? 0.5 : 1 }}
          >
            ESC
          </button>
        </div>

        {error && (
          <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        {/* Tab Selection */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(148, 163, 184, 0.2)', paddingBottom: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('DEPARTMENT')}
            disabled={isProcessing}
            style={{ background: 'none', border: 'none', color: activeTab === 'DEPARTMENT' ? '#10b981' : '#94a3b8', fontSize: '0.85rem', fontWeight: 700, cursor: isProcessing ? 'not-allowed' : 'pointer', padding: '0.5rem 1rem', borderBottom: activeTab === 'DEPARTMENT' ? '2px solid #10b981' : '2px solid transparent', transition: 'all 0.2s' }}
          >
            DEPARTMENT
          </button>
          <button
            onClick={() => setActiveTab('LOCATION')}
            disabled={isProcessing}
            style={{ background: 'none', border: 'none', color: activeTab === 'LOCATION' ? '#10b981' : '#94a3b8', fontSize: '0.85rem', fontWeight: 700, cursor: isProcessing ? 'not-allowed' : 'pointer', padding: '0.5rem 1rem', borderBottom: activeTab === 'LOCATION' ? '2px solid #10b981' : '2px solid transparent', transition: 'all 0.2s' }}
          >
            LOCATION / ZONE
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>{activeTab === 'DEPARTMENT' ? 'Department Name' : 'Location / Zone Name'} <span style={{ color: '#ef4444' }}>*</span></label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isProcessing}
              placeholder={activeTab === 'DEPARTMENT' ? "e.g. Engineering" : "e.g. Packaging Line B"}
              style={{ ...inputStyle, cursor: isProcessing ? 'not-allowed' : 'text' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isProcessing}
              style={{ flex: 1, padding: '0.7rem', background: 'rgba(148, 163, 184, 0.1)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '8px', cursor: isProcessing ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.85rem', transition: 'all 0.2s' }}
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isProcessing || !name.trim()}
              style={{ flex: 1, padding: '0.7rem', background: isProcessing || !name.trim() ? 'rgba(16, 185, 129, 0.15)' : 'linear-gradient(135deg, #10b981, #059669)', color: isProcessing || !name.trim() ? '#64748b' : '#fff', border: 'none', borderRadius: '8px', cursor: isProcessing || !name.trim() ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s' }}
            >
              {isProcessing ? 'SAVING...' : 'SAVE RECORD'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default TaxonomyIngestionModal;
