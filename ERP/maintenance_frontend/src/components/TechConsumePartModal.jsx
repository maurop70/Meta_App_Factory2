import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const TechConsumePartModal = ({ isOpen, onClose, mwoId, onConsumeSuccess }) => {
  const [catalog, setCatalog] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedParts, setSelectedParts] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (isOpen) {
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

    try {
      setIsProcessing(true);
      setError(null);

      // 1. Atomic Mutation Dispatch
      await api.post(`/work-orders/${mwoId}/consume`, {
        part_ids: selectedParts
      });

      // 2. Success Resolution Phase — Transit Lockout HELD
      await onConsumeSuccess();

      // 3. Post-resolution teardown — safe to release
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "Structural Violation: Allocation failed.");
    } finally {
      setIsProcessing(false);
    }
  };

  const togglePartSelection = (partId) => {
    setSelectedParts(prev => 
      prev.includes(partId) ? prev.filter(id => id !== partId) : [...prev, partId]
    );
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
      style={{ position: 'fixed', inset: 0, zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={() => { if (!isProcessing) onClose(); }}
    >
      <div
        style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '16px', padding: '2rem', width: '480px', maxWidth: '90vw', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
            Consume Parts
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
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Select Consumable Parts</label>
            <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '6px', background: 'rgba(10, 14, 23, 0.6)' }}>
              {catalog.length === 0 ? (
                <div style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.85rem', textAlign: 'center' }}>No parts available in inventory.</div>
              ) : (
                catalog.map(part => (
                  <label key={part.part_id} style={{ display: 'flex', alignItems: 'center', padding: '0.6rem 0.8rem', borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: isProcessing ? 'not-allowed' : 'pointer', transition: 'background 0.2s' }}>
                    <input
                      type="checkbox"
                      checked={selectedParts.includes(part.part_id)}
                      onChange={() => togglePartSelection(part.part_id)}
                      disabled={isProcessing}
                      style={{ marginRight: '0.8rem', cursor: isProcessing ? 'not-allowed' : 'pointer' }}
                    />
                    <div>
                      <div style={{ color: '#e2e8f0', fontSize: '0.85rem', fontWeight: 500 }}>{part.nomenclature}</div>
                      <div style={{ color: '#34d399', fontSize: '0.7rem', fontFamily: 'monospace' }}>{part.part_id}</div>
                    </div>
                  </label>
                ))
              )}
            </div>
            <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '0.5rem', textAlign: 'right' }}>
              Selected: <span style={{ color: '#34d399', fontWeight: 700 }}>{selectedParts.length}</span> parts
            </div>
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
              disabled={isProcessing || selectedParts.length === 0}
              style={{ flex: 1, padding: '0.7rem', background: isProcessing || selectedParts.length === 0 ? 'rgba(16, 185, 129, 0.2)' : 'linear-gradient(135deg, #10b981, #059669)', color: isProcessing || selectedParts.length === 0 ? '#94a3b8' : '#fff', border: 'none', borderRadius: '8px', cursor: isProcessing || selectedParts.length === 0 ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: isProcessing || selectedParts.length === 0 ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.25)' }}
            >
              {isProcessing ? 'ALLOCATING...' : 'CONSUME PARTS'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default TechConsumePartModal;
