import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

/**
 * [BACK OFFICE INVENTORY] Manual Stock-In / Stock-Out / Procure Widget.
 * Zero-trust doctrine: every adjustment carries operator identity + reasoning.
 * PROCURE mode (HOD only) manually appends any SKU to the supplier's DRAFT PO,
 * regardless of reorder-threshold state.
 */
const MODE_META = {
  IN: {
    accent: '#10b981',
    label: 'Commit Stock-In',
    hint: 'Logs a manual stock addition (e.g. found stock, returns, cycle-count correction). Increases quantity on hand.'
  },
  OUT: {
    accent: '#f59e0b',
    label: 'Commit Stock-Out',
    hint: 'Logs a manual stock reduction (e.g. damage, loss, write-off). Decreases quantity on hand and may auto-draft a reorder.'
  },
  PROCURE: {
    accent: '#6366f1',
    label: 'Add to Purchase Order Draft',
    hint: 'Manually requests procurement: adds this SKU to the supplier’s open DRAFT purchase order (or creates one), even if stock is above the safety threshold.'
  }
};

const ManualLogWidget = ({ onLogged }) => {
  const { userRole } = useAuth();
  const isHod = ['ADMINISTRATOR', 'ADMIN', 'HM'].includes(userRole);

  const [mode, setMode] = useState('OUT');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selectedSku, setSelectedSku] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null); // { type: 'success'|'error', message }
  const [pulse, setPulse] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (selectedSku || query.trim() === '') {
      setResults([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await api.get(`/inventory/skus/search?q=${encodeURIComponent(query)}&limit=8`);
        setResults(data.data || []);
      } catch (err) {
        console.warn('SKU autocomplete failed.', err);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query, selectedSku]);

  const pickSku = (sku) => {
    setSelectedSku(sku);
    setQuery(`${sku.sku_id} — ${sku.nomenclature}`);
    setResults([]);
  };

  const resetSku = () => {
    setSelectedSku(null);
    setQuery('');
  };

  const submitLog = async () => {
    if (!selectedSku || quantity < 1) {
      setFeedback({ type: 'error', message: 'Select a SKU and a positive quantity.' });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      if (mode === 'PROCURE') {
        const { data } = await api.post('/orders/drafts/add-item', {
          sku_id: selectedSku.sku_id,
          quantity: Number(quantity),
          notes: comment.trim() || null
        });
        setFeedback({
          type: 'success',
          message: `${quantity}× ${selectedSku.sku_id} ${data.created ? 'added to new draft' : 'merged into draft'} ${data.po_id} (line total: ${data.line_quantity}).`
        });
      } else {
        const { data } = await api.post('/inventory/manual-log', {
          sku_id: selectedSku.sku_id,
          direction: mode,
          quantity: Number(quantity),
          comment: comment.trim() || null
        });
        setFeedback({ type: 'success', message: `${mode === 'IN' ? '+' : '-'}${quantity} ${selectedSku.sku_id} → on hand: ${data.new_quantity_on_hand}` });
      }
      setPulse(true);
      setTimeout(() => setPulse(false), 900);
      setComment('');
      setQuantity(1);
      resetSku();
      if (onLogged) onLogged();
    } catch (err) {
      setFeedback({ type: 'error', message: err.response?.data?.detail || 'Submission failed.' });
    } finally {
      setBusy(false);
    }
  };

  const { accent, label, hint } = MODE_META[mode];

  return (
    <div style={{ background: 'rgba(15, 23, 42, 0.85)', border: '1px solid rgba(99, 102, 241, 0.15)', borderRadius: '12px', padding: '1.2rem', backdropFilter: 'blur(8px)', position: 'relative', overflow: 'visible' }}>
      <style>{`
        @keyframes mlw-success-pulse {
          0%   { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.55); }
          100% { box-shadow: 0 0 0 18px rgba(16, 185, 129, 0); }
        }
        .mlw-pulse { animation: mlw-success-pulse 0.9s ease-out; }
        .mlw-toggle-btn {
          flex: 1; padding: 0.5rem 0; border-radius: 8px; cursor: pointer;
          font-weight: 700; font-size: 0.8rem; letter-spacing: 0.08em;
          border: 1px solid transparent; transition: all 0.2s; background: transparent; color: #64748b;
        }
        .mlw-input {
          width: 100%; padding: 0.55rem 0.8rem; border-radius: 8px;
          border: 1px solid rgba(99, 102, 241, 0.25); background: rgba(10, 14, 23, 0.6);
          color: #e2e8f0; font-family: inherit; font-size: 0.85rem; outline: none;
          transition: border-color 0.2s; box-sizing: border-box;
        }
        .mlw-input:focus { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2); }
        .mlw-result-row { padding: 0.55rem 0.8rem; cursor: pointer; font-size: 0.8rem; color: #e2e8f0; transition: background 0.15s; }
        .mlw-result-row:hover { background: rgba(99, 102, 241, 0.2); }
        .mlw-metric { flex: 1; min-width: 110px; }
        .mlw-metric-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; font-weight: 700; }
        .mlw-metric-value { font-size: 0.92rem; font-weight: 700; color: #e2e8f0; margin-top: 2px; }
      `}</style>

      <h3 style={{ margin: '0 0 1rem 0', fontSize: '0.95rem', fontWeight: 600, color: '#e2e8f0' }}>
        Manual Inventory Log
        <span style={{ marginLeft: '0.6rem', fontSize: '0.7rem', color: '#64748b', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Zero-Trust Ledger</span>
      </h3>

      {/* Mode Toggle Switcher */}
      <div style={{ display: 'flex', gap: '0.4rem', background: 'rgba(10, 14, 23, 0.7)', padding: '0.3rem', borderRadius: '10px', marginBottom: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
        <button
          className="mlw-toggle-btn"
          onClick={() => setMode('IN')}
          style={mode === 'IN' ? { background: 'rgba(16, 185, 129, 0.18)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.4)' } : {}}
        >
          + STOCK-IN
        </button>
        <button
          className="mlw-toggle-btn"
          onClick={() => setMode('OUT')}
          style={mode === 'OUT' ? { background: 'rgba(245, 158, 11, 0.18)', color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.4)' } : {}}
        >
          − STOCK-OUT
        </button>
        {isHod && (
          <button
            className="mlw-toggle-btn"
            onClick={() => setMode('PROCURE')}
            style={mode === 'PROCURE' ? { background: 'rgba(99, 102, 241, 0.18)', color: '#818cf8', borderColor: 'rgba(99, 102, 241, 0.4)' } : {}}
          >
            🛒 PROCURE
          </button>
        )}
      </div>

      {/* Mode Helper Subtext */}
      <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '0.9rem', padding: '0 0.2rem' }}>
        {hint}
      </div>

      {/* SKU Autocomplete */}
      <div style={{ position: 'relative', marginBottom: '0.8rem' }}>
        <input
          className="mlw-input"
          placeholder="Search SKU or part nomenclature..."
          value={query}
          onChange={e => { setQuery(e.target.value); setSelectedSku(null); }}
        />
        {selectedSku && (
          <button onClick={resetSku} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '0.9rem' }}>✕</button>
        )}
        {results.length > 0 && (
          <div style={{ position: 'absolute', top: '110%', left: 0, right: 0, zIndex: 30, background: 'rgba(15, 23, 42, 0.98)', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
            {results.map(sku => (
              <div key={sku.sku_id} className="mlw-result-row" onClick={() => pickSku(sku)}>
                <span style={{ color: '#818cf8', fontWeight: 600 }}>{sku.sku_id}</span>
                <span style={{ margin: '0 0.5rem' }}>{sku.nomenclature}</span>
                <span style={{ color: sku.quantity_on_hand <= sku.reorder_threshold ? '#ef4444' : '#64748b', fontSize: '0.72rem' }}>
                  On hand: {sku.quantity_on_hand}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selected SKU Inventory Metrics */}
      {selectedSku && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.8rem', marginBottom: '0.9rem', padding: '0.75rem 0.9rem', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.07)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
          <div className="mlw-metric">
            <div className="mlw-metric-label">Current Stock</div>
            <div className="mlw-metric-value" style={{ color: selectedSku.quantity_on_hand <= selectedSku.reorder_threshold ? '#ef4444' : '#10b981' }}>
              {selectedSku.quantity_on_hand}
              {selectedSku.quantity_on_hand <= selectedSku.reorder_threshold && (
                <span style={{ marginLeft: '0.4rem', fontSize: '0.6rem', fontWeight: 800, color: '#ef4444', textTransform: 'uppercase' }}>Low</span>
              )}
            </div>
          </div>
          <div className="mlw-metric">
            <div className="mlw-metric-label">Safety Threshold</div>
            <div className="mlw-metric-value">{selectedSku.reorder_threshold}</div>
          </div>
          <div className="mlw-metric">
            <div className="mlw-metric-label">Unit Cost</div>
            <div className="mlw-metric-value">${Number(selectedSku.unit_cost || 0).toFixed(2)}</div>
          </div>
          <div className="mlw-metric">
            <div className="mlw-metric-label">Supplier</div>
            <div className="mlw-metric-value" style={{ fontSize: '0.8rem' }}>{selectedSku.supplier_name || 'Unassigned'}</div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '0.8rem' }}>
        <input
          className="mlw-input"
          type="number"
          min="1"
          value={quantity}
          onChange={e => setQuantity(e.target.value)}
          style={{ maxWidth: '110px' }}
          placeholder="Qty"
        />
        <input
          className="mlw-input"
          placeholder={mode === 'PROCURE' ? 'Special instructions for supplier (optional)...' : 'Reason / comment (e.g. "damaged parts write-off")'}
          value={comment}
          onChange={e => setComment(e.target.value)}
        />
      </div>

      <button
        onClick={submitLog}
        disabled={busy || !selectedSku}
        className={pulse ? 'mlw-pulse' : ''}
        style={{
          width: '100%', padding: '0.65rem', borderRadius: '8px', cursor: busy || !selectedSku ? 'not-allowed' : 'pointer',
          background: `${accent}22`, color: accent, border: `1px solid ${accent}66`,
          fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.08em', textTransform: 'uppercase',
          opacity: busy || !selectedSku ? 0.55 : 1, transition: 'all 0.2s'
        }}
      >
        {busy ? 'Committing…' : label}
      </button>

      {feedback && (
        <div style={{ marginTop: '0.8rem', padding: '0.55rem 0.8rem', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600, background: feedback.type === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)', color: feedback.type === 'success' ? '#10b981' : '#ef4444', border: `1px solid ${feedback.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}` }}>
          {feedback.message}
        </div>
      )}
    </div>
  );
};

export default ManualLogWidget;
