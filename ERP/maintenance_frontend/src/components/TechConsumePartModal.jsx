import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const TechConsumePartModal = ({ isOpen, onClose, mwoId, onConsumeSuccess }) => {
  const [catalog, setCatalog] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [formData, setFormData] = useState({ part_id: '', quantity_consumed: 1 });
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (isOpen) {
      // Truncated API call with bounded pagination & zero-stock exclusion
      api.get('/inventory/available?limit=50&offset=0')
        .then(res => {
          if (isMounted) setCatalog(res.data.data || []);
        })
        .catch(err => {
          if (isMounted) console.error("Catalog Fetch Error:", err);
        });
    }
    return () => { isMounted = false; };
  }, [isOpen]);

  useEffect(() => {
    let isMounted = true;
    const handleEsc = (e) => {
      if (e.key === 'Escape' && isMounted && !isProcessing) onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => {
      isMounted = false;
      document.removeEventListener('keydown', handleEsc);
    };
  }, [onClose, isProcessing]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isProcessing) return;
    let isMounted = true;

    try {
      setIsProcessing(true);
      setError(null);
      await api.post(`/mwo/${mwoId}/consume_part`, {
        part_id: formData.part_id,
        quantity_consumed: parseInt(formData.quantity_consumed, 10)
      });
      if (isMounted) {
        onConsumeSuccess();
        onClose();
      }
    } catch (err) {
      if (isMounted) {
        setError(err.response?.data?.detail || "Structural Violation: Allocation failed.");
      }
    } finally {
      if (isMounted) setIsProcessing(false);
    }

    return () => { isMounted = false; };
  };

  const inputStyle = {
    width: '100%', padding: '0.6rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.3rem', color: '#94a3b8',
    fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em'
  };

  const modalContent = (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={() => { if (!isProcessing) onClose(); }}
    >
      <div
        style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '16px', padding: '2rem', width: '480px', maxWidth: '90vw', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
            Consume Part
          </h3>
          <button
            onClick={onClose}
            disabled={isProcessing}
            style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: isProcessing ? 'not-allowed' : 'pointer', fontSize: '0.75rem', fontWeight: 600, opacity: isProcessing ? 0.5 : 1 }}
          >
            ESC
          </button>
        </div>

        <div style={{ padding: '0.5rem 0.8rem', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px', marginBottom: '1.5rem' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600 }}>TARGET MWO: </span>
          <span style={{ color: '#34d399', fontWeight: 700, fontSize: '0.85rem' }}>{mwoId}</span>
        </div>

        {error && (
          <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Select Consumable</label>
            <select
              required
              value={formData.part_id}
              onChange={e => setFormData({ ...formData, part_id: e.target.value })}
              disabled={isProcessing}
              style={{ ...inputStyle, cursor: isProcessing ? 'not-allowed' : 'pointer' }}
            >
              <option value="">-- Select Part from Inventory --</option>
              {catalog.map(part => (
                <option key={part.part_id} value={part.part_id}>
                  {part.part_id} — {part.nomenclature} (Avail: {part.quantity_on_hand})
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Quantity to Consume</label>
            <input
              type="number"
              min="1"
              required
              value={formData.quantity_consumed}
              onChange={e => setFormData({ ...formData, quantity_consumed: e.target.value })}
              disabled={isProcessing}
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
              disabled={isProcessing || !formData.part_id}
              style={{ flex: 1, padding: '0.7rem', background: isProcessing || !formData.part_id ? 'rgba(16, 185, 129, 0.2)' : 'linear-gradient(135deg, #10b981, #059669)', color: isProcessing || !formData.part_id ? '#94a3b8' : '#fff', border: 'none', borderRadius: '8px', cursor: isProcessing || !formData.part_id ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: isProcessing || !formData.part_id ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.25)' }}
            >
              {isProcessing ? 'ALLOCATING...' : 'CONSUME PART'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default TechConsumePartModal;
