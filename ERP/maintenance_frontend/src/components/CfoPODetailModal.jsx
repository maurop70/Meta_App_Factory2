import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

/**
 * [BACK OFFICE INVENTORY] CFO Purchase Order inspection overlay.
 * Renders the full PO context already hydrated by /orders/approvals
 * (supplier contact card, HM/DM notes, line items with live stock status)
 * and actuates Approve / Hold / Reject via the existing bulk endpoint.
 */
const CfoPODetailModal = ({ po, onClose, onActuationSuccess }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [cfoNotes, setCfoNotes] = useState('');

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, busy]);

  useEffect(() => { setCfoNotes(po?.cfo_notes || ''); }, [po?.po_id]);

  if (!po) return null;

  const actuate = async (action) => {
    setBusy(true);
    setError(null);
    try {
      await api.post('/orders/actuate-bulk', { po_ids: [po.po_id], action, cfo_notes: cfoNotes.trim() || null });
      onActuationSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Bulk actuation failed.');
      setBusy(false);
    }
  };

  const fmtTs = (ts) => (ts ? ts.slice(0, 16).replace('T', ' ') : '—');

  const actionBtn = (label, action, palette) => (
    <button
      onClick={() => actuate(action)}
      disabled={busy}
      style={{
        flex: 1, padding: '0.75rem', borderRadius: '8px', fontWeight: 800, fontSize: '0.82rem',
        textTransform: 'uppercase', letterSpacing: '0.06em', cursor: busy ? 'not-allowed' : 'pointer',
        opacity: busy ? 0.5 : 1, background: palette.bg, color: palette.fg, border: `1px solid ${palette.border}`
      }}
    >
      {label}
    </button>
  );

  const modalContent = (
    <div
      role="dialog"
      aria-modal="true"
      style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.85)', zIndex: 9999, display: 'flex', justifyContent: 'center', alignItems: 'center', backdropFilter: 'blur(6px)' }}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
    >
      <div style={{ background: 'var(--bg-dark, #0a0e17)', padding: '2rem', borderRadius: '12px', border: '1px solid var(--border, rgba(99,102,241,0.2))', width: '90%', maxWidth: '720px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '1rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-primary, #e2e8f0)' }}>
              Purchase Order <span style={{ color: '#818cf8' }}>{po.po_id}</span>
            </h2>
            <div style={{ marginTop: '0.4rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ padding: '2px 10px', borderRadius: '12px', fontSize: '0.68rem', fontWeight: 700, background: po.status === 'HOLD' ? 'rgba(148,163,184,0.15)' : 'rgba(245,158,11,0.15)', color: po.status === 'HOLD' ? '#94a3b8' : '#fbbf24' }}>
                {po.status}
              </span>
              {po.priority === 1 && (
                <span style={{ padding: '2px 10px', borderRadius: '12px', fontSize: '0.68rem', fontWeight: 800, background: 'rgba(249,115,22,0.18)', color: '#f97316', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  ⬆ High Priority
                </span>
              )}
            </div>
          </div>
          <button onClick={onClose} disabled={busy} aria-label="Close" style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary, #94a3b8)', cursor: busy ? 'not-allowed' : 'pointer', fontSize: '1.5rem' }}>×</button>
        </div>

        {/* Metadata */}
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.78rem', color: '#94a3b8', marginBottom: '1.25rem' }}>
          <span>Created: <strong style={{ color: '#cbd5e1' }}>{fmtTs(po.created_at)}</strong></span>
          <span>Submitted: <strong style={{ color: '#cbd5e1' }}>{fmtTs(po.submitted_at)}</strong></span>
          <span>ETA: <strong style={{ color: '#cbd5e1' }}>{po.eta_date || 'TBC'}</strong></span>
        </div>

        {/* Supplier contact card */}
        <div style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px', padding: '1rem', marginBottom: '1.25rem' }}>
          <h3 style={{ margin: '0 0 0.6rem 0', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#818cf8' }}>Supplier</h3>
          <div style={{ fontSize: '0.9rem', color: '#e2e8f0', fontWeight: 600, marginBottom: '0.3rem' }}>{po.supplier_name || '—'} <span style={{ color: '#475569', fontWeight: 400 }}>({po.supplier_id})</span></div>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.8rem', color: '#94a3b8' }}>
            <span>✉ {po.supplier_email || '—'}</span>
            <span>☎ {po.supplier_phone || '—'}</span>
          </div>
          {po.supplier_address && <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.3rem' }}>📍 {po.supplier_address}</div>}
        </div>

        {/* HM / DM notes */}
        {po.notes && (
          <div style={{ background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.35)', borderRadius: '8px', padding: '1rem', marginBottom: '1.25rem' }}>
            <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#fbbf24' }}>HM / DM Notes &amp; Special Instructions</h3>
            <div style={{ fontSize: '0.86rem', color: '#fde68a', fontStyle: 'italic', whiteSpace: 'pre-wrap' }}>{po.notes}</div>
          </div>
        )}

        {/* Line items */}
        <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(99,102,241,0.15)', marginBottom: '1.25rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr>
                {['SKU', 'Description', 'Qty', 'Unit Cost', 'Line Cost', 'On Hand / Threshold'].map((h, i) => (
                  <th key={h} style={{ textAlign: i >= 2 && i <= 4 ? 'right' : 'left', padding: '0.5rem 0.7rem', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {po.items.map((item) => (
                <tr key={item.sku_id}>
                  <td style={{ padding: '0.5rem 0.7rem', color: '#818cf8', fontWeight: 600, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>{item.sku_id}</td>
                  <td style={{ padding: '0.5rem 0.7rem', color: '#cbd5e1', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>{item.nomenclature}</td>
                  <td style={{ padding: '0.5rem 0.7rem', textAlign: 'right', color: '#cbd5e1', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>×{item.quantity}</td>
                  <td style={{ padding: '0.5rem 0.7rem', textAlign: 'right', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>${item.unit_cost.toFixed(2)}</td>
                  <td style={{ padding: '0.5rem 0.7rem', textAlign: 'right', color: '#e2e8f0', fontWeight: 600, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>${(item.quantity * item.unit_cost).toFixed(2)}</td>
                  <td style={{ padding: '0.5rem 0.7rem', color: (item.quantity_on_hand != null && item.reorder_threshold != null && item.quantity_on_hand <= item.reorder_threshold) ? '#ef4444' : '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    {item.quantity_on_hand != null ? `${item.quantity_on_hand} / ${item.reorder_threshold}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '1rem', fontWeight: 800, color: '#e2e8f0', marginBottom: '1.25rem' }}>
          Total: ${po.total_cost.toFixed(2)}
        </div>

        {error && (
          <div style={{ marginBottom: '1rem', padding: '0.6rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: 'rgba(239,68,68,0.12)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }}>{error}</div>
        )}

        {/* CFO supplier notes */}
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#818cf8', fontWeight: 700, marginBottom: '0.4rem' }}>CFO Notes to Supplier (Optional)</label>
          <textarea
            value={cfoNotes}
            onChange={(e) => setCfoNotes(e.target.value)}
            disabled={busy}
            rows="3"
            placeholder="Instructions appended to the supplier dispatch email…"
            style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: '6px', color: '#e2e8f0', outline: 'none', resize: 'vertical', boxSizing: 'border-box', fontSize: '0.85rem' }}
          />
        </div>

        {/* Actuation */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {actionBtn('Approve Order', 'APPROVE', { bg: 'rgba(16,185,129,0.15)', fg: '#10b981', border: 'rgba(16,185,129,0.4)' })}
          {actionBtn('Hold Order', 'HOLD', { bg: 'rgba(148,163,184,0.12)', fg: '#94a3b8', border: 'rgba(148,163,184,0.35)' })}
          {actionBtn('Reject Order', 'REJECT', { bg: 'rgba(239,68,68,0.12)', fg: '#ef4444', border: 'rgba(239,68,68,0.4)' })}
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default CfoPODetailModal;
