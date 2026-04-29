import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const PartIngestionModal = ({ closeModal, onIngestionSuccess }) => {
  const [formData, setFormData] = useState({
    part_id: '',
    nomenclature: '',
    category: '',
    quantity_on_hand: 0,
    reorder_threshold: 5,
    unit_cost: 0.0
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    const handleEsc = (e) => {
      if (e.key === 'Escape' && isMounted) closeModal();
    };
    document.addEventListener('keydown', handleEsc);

    return () => {
      isMounted = false;
      document.removeEventListener('keydown', handleEsc);
    };
  }, [closeModal]);

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? (value === '' ? '' : Number(value)) : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    let isMounted = true;
    setSubmitting(true);
    setError(null);

    try {
      await api.post('/admin/ingest/part', formData);
      if (isMounted) {
        onIngestionSuccess();
        closeModal();
      }
    } catch (err) {
      if (isMounted) {
        setError(err.response?.data?.detail || 'Failed to ingest part record.');
      }
    } finally {
      if (isMounted) setSubmitting(false);
    }

    return () => { isMounted = false; };
  };

  const inputStyle = {
    width: '100%', padding: '0.6rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.3rem', color: '#94a3b8',
    fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em'
  };

  const modalContent = (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }} onClick={closeModal}>
      <div style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: '16px', padding: '2rem', width: '500px', maxWidth: '90vw', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>Ingest Part Record</h3>
          <button onClick={closeModal} style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}>ESC</button>
        </div>

        {error && <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={labelStyle}>Part ID</label>
              <input name="part_id" value={formData.part_id} onChange={handleChange} required style={inputStyle} placeholder="PRT-001" />
            </div>
            <div>
              <label style={labelStyle}>Category</label>
              <input name="category" value={formData.category} onChange={handleChange} required style={inputStyle} placeholder="ELECTRICAL" />
            </div>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Nomenclature</label>
            <input name="nomenclature" value={formData.nomenclature} onChange={handleChange} required style={inputStyle} placeholder="Hydraulic Seal Ring" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div>
              <label style={labelStyle}>Qty On Hand</label>
              <input name="quantity_on_hand" type="number" value={formData.quantity_on_hand} onChange={handleChange} min="0" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Reorder Threshold</label>
              <input name="reorder_threshold" type="number" value={formData.reorder_threshold} onChange={handleChange} min="0" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Unit Cost ($)</label>
              <input name="unit_cost" type="number" step="0.01" value={formData.unit_cost} onChange={handleChange} min="0" style={inputStyle} />
            </div>
          </div>

          <button type="submit" disabled={submitting} style={{ width: '100%', padding: '0.7rem', background: submitting ? 'rgba(99, 102, 241, 0.2)' : 'linear-gradient(135deg, #6366f1, #7c3aed)', color: submitting ? '#94a3b8' : '#fff', border: 'none', borderRadius: '8px', cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: submitting ? 'none' : '0 4px 15px rgba(99, 102, 241, 0.25)' }}>
            {submitting ? 'PROCESSING...' : 'INGEST PART RECORD'}
          </button>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default PartIngestionModal;
