import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

/**
 * [BACK OFFICE INVENTORY] CFO Approval Queue.
 * Priority orders float to the top with a soft ambient aura.
 * Multi-select checkboxes drive bulk Approve / Hold / Reject actuation.
 */
const CFOApprovals = () => {
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading approval queue...' });
  const [banner, setBanner] = useState(null);
  const [busy, setBusy] = useState(false);

  const fetchQueue = useCallback(async () => {
    try {
      const { data } = await api.get('/orders/approvals');
      setOrders(data.data || []);
      setStatus({ type: 'success', message: '' });
    } catch (err) {
      console.warn('Approval queue sync failed.', err);
      setStatus({ type: 'error', message: err.response?.status === 403 ? 'RBAC Violation: CFO clearance required.' : 'Failed to load approval queue.' });
    }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const flash = (type, message) => {
    setBanner({ type, message });
    setTimeout(() => setBanner(null), 4500);
  };

  const toggleSelect = (poId) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(poId)) next.delete(poId); else next.add(poId);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected(prev => prev.size === orders.length ? new Set() : new Set(orders.map(o => o.po_id)));
  };

  const actuate = async (action) => {
    if (selected.size === 0) {
      flash('error', 'Select at least one purchase order.');
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post('/orders/actuate-bulk', { po_ids: [...selected], action });
      const ok = data.results.filter(r => ['APPROVED', 'HOLD', 'REJECTED'].includes(r.result)).length;
      flash('success', `${action}: ${ok}/${data.results.length} purchase order(s) actuated.${action === 'APPROVE' ? ' Supplier emails dispatched.' : ''}`);
      setSelected(new Set());
      await fetchQueue();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Bulk actuation failed.');
    } finally {
      setBusy(false);
    }
  };

  if (status.type === 'loading') return <div className="erp-status-message loading">{status.message}</div>;
  if (status.type === 'error') return <div className="erp-status-message error">{status.message}</div>;

  return (
    <div>
      <style>{`
        @keyframes cfo-priority-aura {
          0%, 100% { box-shadow: 0 0 18px 2px rgba(249, 115, 22, 0.22); }
          50%      { box-shadow: 0 0 32px 6px rgba(249, 115, 22, 0.38); }
        }
        .cfo-card {
          background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.15);
          border-radius: 12px; padding: 1.1rem 1.3rem; backdrop-filter: blur(8px);
          margin-bottom: 1rem; display: flex; gap: 1rem; align-items: flex-start;
          transition: border-color 0.2s;
        }
        .cfo-card.selected { border-color: rgba(99, 102, 241, 0.6); }
        .cfo-card.priority { border-color: rgba(249, 115, 22, 0.55); animation: cfo-priority-aura 2.4s ease-in-out infinite; }
        .cfo-bulk-btn {
          padding: 0.55rem 1.3rem; border-radius: 8px; cursor: pointer; font-weight: 700;
          font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.07em; transition: all 0.2s;
        }
        .cfo-bulk-btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .cfo-items-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-top: 0.6rem; }
        .cfo-items-table td { padding: 0.3rem 0.6rem; color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .cfo-checkbox { width: 18px; height: 18px; accent-color: #6366f1; cursor: pointer; margin-top: 0.3rem; }
      `}</style>

      {banner && (
        <div style={{ marginBottom: '1rem', padding: '0.6rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: banner.type === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)', color: banner.type === 'success' ? '#10b981' : '#ef4444', border: `1px solid ${banner.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}` }}>
          {banner.message}
        </div>
      )}

      {/* Bulk Action Bar */}
      <div style={{ display: 'flex', gap: '0.7rem', marginBottom: '1.3rem', flexWrap: 'wrap', alignItems: 'center', background: 'rgba(15, 23, 42, 0.7)', padding: '0.8rem 1rem', borderRadius: '10px', border: '1px solid rgba(99, 102, 241, 0.15)' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600, cursor: 'pointer' }}>
          <input type="checkbox" className="cfo-checkbox" style={{ marginTop: 0 }} checked={orders.length > 0 && selected.size === orders.length} onChange={toggleAll} />
          Select All ({selected.size}/{orders.length})
        </label>
        <div style={{ flex: 1 }} />
        <button className="cfo-bulk-btn" disabled={busy || selected.size === 0} onClick={() => actuate('APPROVE')}
          style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
          Bulk Approve
        </button>
        <button className="cfo-bulk-btn" disabled={busy || selected.size === 0} onClick={() => actuate('HOLD')}
          style={{ background: 'rgba(148, 163, 184, 0.12)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.35)' }}>
          Bulk Hold
        </button>
        <button className="cfo-bulk-btn" disabled={busy || selected.size === 0} onClick={() => actuate('REJECT')}
          style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
          Bulk Reject
        </button>
      </div>

      {orders.length === 0 && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '12px', border: '1px dashed rgba(99, 102, 241, 0.2)', fontSize: '0.9rem' }}>
          Approval queue is clear. No purchase orders awaiting CFO actuation.
        </div>
      )}

      {orders.map(po => (
        <div key={po.po_id} className={`cfo-card ${selected.has(po.po_id) ? 'selected' : ''} ${po.priority === 1 ? 'priority' : ''}`}>
          <input type="checkbox" className="cfo-checkbox" checked={selected.has(po.po_id)} onChange={() => toggleSelect(po.po_id)} />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#818cf8' }}>{po.po_id}</span>
                {po.priority === 1 && (
                  <span style={{ marginLeft: '0.6rem', padding: '2px 10px', borderRadius: '12px', fontSize: '0.68rem', fontWeight: 800, background: 'rgba(249, 115, 22, 0.18)', color: '#f97316', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    ⬆ High Priority
                  </span>
                )}
                <span style={{ marginLeft: '0.6rem', padding: '2px 10px', borderRadius: '12px', fontSize: '0.68rem', fontWeight: 700, background: po.status === 'HOLD' ? 'rgba(148, 163, 184, 0.15)' : 'rgba(245, 158, 11, 0.15)', color: po.status === 'HOLD' ? '#94a3b8' : '#fbbf24' }}>
                  {po.status}
                </span>
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#e2e8f0' }}>${po.total_cost.toFixed(2)}</div>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.3rem' }}>
              {po.supplier_name} · ETA {po.eta_date || 'TBC'} · Submitted {po.submitted_at ? po.submitted_at.slice(0, 16).replace('T', ' ') : '—'}
            </div>
            {po.notes && (
              <div style={{ fontSize: '0.76rem', color: '#fbbf24', marginTop: '0.3rem', fontStyle: 'italic' }}>“{po.notes}”</div>
            )}
            <table className="cfo-items-table">
              <tbody>
                {po.items.map(item => (
                  <tr key={item.sku_id}>
                    <td style={{ color: '#818cf8', fontWeight: 600, width: '120px' }}>{item.sku_id}</td>
                    <td>{item.nomenclature}</td>
                    <td style={{ textAlign: 'right', width: '70px' }}>×{item.quantity}</td>
                    <td style={{ textAlign: 'right', width: '100px' }}>${(item.quantity * item.unit_cost).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
};

export default CFOApprovals;
