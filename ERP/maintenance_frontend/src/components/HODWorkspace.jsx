import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import ManualLogWidget from './ManualLogWidget';
import SkuLedger from './SkuLedger';

/**
 * [BACK OFFICE INVENTORY] HOD (Head of Department) Procurement Workspace.
 * Draft PO grid grouped by supplier with inline quantity adjustment,
 * line-item exclusion, ETA override, and High Priority pulse toggle.
 */
const HODWorkspace = ({ highlightPoId = null, onHighlightConsumed = null }) => {
  const [drafts, setDrafts] = useState([]);
  const [inbound, setInbound] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Synchronizing procurement state...' });
  const [banner, setBanner] = useState(null);
  const [dirtyQty, setDirtyQty] = useState({}); // { `${po_id}|${sku_id}`: qty }
  const [dirtyMeta, setDirtyMeta] = useState({}); // { po_id: { notes, eta_date } }
  const [pulsingPoId, setPulsingPoId] = useState(null); // alert deep-link highlight

  const fetchOrders = useCallback(async () => {
    try {
      const [draftRes, inboundRes] = await Promise.all([
        api.get('/orders/drafts'),
        api.get('/orders/inbound')
      ]);
      setDrafts(draftRes.data.data || []);
      setInbound(inboundRes.data.data || []);
      setStatus({ type: 'success', message: '' });
    } catch (err) {
      console.warn('Procurement sync failed.', err);
      setStatus({ type: 'error', message: 'Failed to synchronize procurement state.' });
    }
  }, []);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  // [SAFETY ALERTS] Deep-link from the HM dashboard alert panel: scroll the
  // target draft card into view and pulse it briefly.
  // Race fix: defer the DOM query one tick (100ms) so the freshly-mounted
  // card list is painted before getElementById runs; only consume the
  // highlight after the scroll resolves or the element is genuinely absent.
  useEffect(() => {
    if (!highlightPoId || status.type !== 'success') return;
    const timer = setTimeout(() => {
      const el = document.getElementById(`po-card-${highlightPoId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setPulsingPoId(highlightPoId);
        setTimeout(() => {
          setPulsingPoId(null);
          if (onHighlightConsumed) onHighlightConsumed();
        }, 3500);
      } else {
        if (onHighlightConsumed) onHighlightConsumed();
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [highlightPoId, status.type, drafts]);

  const flash = (type, message) => {
    setBanner({ type, message });
    setTimeout(() => setBanner(null), 4000);
  };

  const stageQty = (poId, skuId, qty) => {
    setDirtyQty(prev => ({ ...prev, [`${poId}|${skuId}`]: qty }));
  };

  const stageMeta = (poId, field, value) => {
    setDirtyMeta(prev => ({ ...prev, [poId]: { ...(prev[poId] || {}), [field]: value } }));
  };

  const persistDraft = async (po) => {
    const items = po.items
      .map(item => {
        const staged = dirtyQty[`${po.po_id}|${item.sku_id}`];
        return staged !== undefined && Number(staged) > 0
          ? { sku_id: item.sku_id, quantity: Number(staged) }
          : null;
      })
      .filter(Boolean);
    const meta = dirtyMeta[po.po_id] || {};
    try {
      await api.put(`/orders/${po.po_id}/update`, {
        items: items.length ? items : null,
        notes: meta.notes !== undefined ? meta.notes : null,
        eta_date: meta.eta_date !== undefined ? meta.eta_date : null
      });
      flash('success', `Draft ${po.po_id} saved.`);
      await fetchOrders();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Draft save failed.');
    }
  };

  const togglePriority = async (po) => {
    try {
      await api.put(`/orders/${po.po_id}/update`, { priority: po.priority === 1 ? 0 : 1 });
      await fetchOrders();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Priority toggle failed.');
    }
  };

  const excludeItem = async (poId, skuId) => {
    try {
      const { data } = await api.delete(`/orders/${poId}/items/${skuId}`);
      flash('success', data.po_dissolved ? `Last item removed — draft ${poId} dissolved.` : `${skuId} excluded from ${poId}.`);
      await fetchOrders();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Item exclusion failed.');
    }
  };

  const submitToCfo = async (poId) => {
    try {
      await api.post('/orders/submit', { po_id: poId });
      flash('success', `${poId} routed to CFO approval queue.`);
      await fetchOrders();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Submission failed.');
    }
  };

  const receiveShipment = async (poId) => {
    try {
      const { data } = await api.post(`/orders/${poId}/receive`);
      flash('success', data.detail);
      await fetchOrders();
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Receipt actuation failed.');
    }
  };

  if (status.type === 'loading') return <div className="erp-status-message loading">{status.message}</div>;
  if (status.type === 'error') return <div className="erp-status-message error">{status.message}</div>;

  const statusChip = (s) => {
    const palette = {
      PENDING_CFO: { bg: 'rgba(245, 158, 11, 0.15)', fg: '#fbbf24' },
      APPROVED: { bg: 'rgba(16, 185, 129, 0.15)', fg: '#10b981' },
      HOLD: { bg: 'rgba(148, 163, 184, 0.15)', fg: '#94a3b8' },
      DRAFT: { bg: 'rgba(99, 102, 241, 0.15)', fg: '#818cf8' }
    }[s] || { bg: 'rgba(148, 163, 184, 0.15)', fg: '#94a3b8' };
    return <span style={{ padding: '2px 10px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 700, background: palette.bg, color: palette.fg }}>{s}</span>;
  };

  return (
    <div>
      <style>{`
        @keyframes hod-priority-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.45); border-color: rgba(249, 115, 22, 0.8); }
          50%      { box-shadow: 0 0 22px 4px rgba(249, 115, 22, 0.35); border-color: rgba(249, 115, 22, 0.5); }
        }
        .hod-po-card {
          background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.15);
          border-radius: 12px; padding: 1.2rem; backdrop-filter: blur(8px); margin-bottom: 1.2rem;
        }
        .hod-po-card.high-priority { animation: hod-priority-pulse 1.8s ease-in-out infinite; }
        @keyframes hod-alert-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.45); border-color: rgba(239, 68, 68, 0.8); }
          50%      { box-shadow: 0 0 22px 4px rgba(239, 68, 68, 0.35); border-color: rgba(239, 68, 68, 0.5); }
        }
        .hod-po-card.alert-highlight { animation: hod-alert-pulse 1.1s ease-in-out 3; }
        .hod-moq-badge {
          display: inline-flex; align-items: center; gap: 0.35rem; margin-left: 0.45rem;
          padding: 1px 7px; border-radius: 10px; font-size: 0.65rem; font-weight: 700;
          background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);
          white-space: nowrap;
        }
        .hod-moq-roundup {
          background: transparent; border: none; color: #38bdf8; cursor: pointer;
          font-size: 0.65rem; font-weight: 700; padding: 0; text-decoration: underline;
        }
        .hod-qty-input {
          width: 70px; padding: 0.35rem 0.5rem; border-radius: 6px; text-align: center;
          border: 1px solid rgba(99, 102, 241, 0.3); background: rgba(10, 14, 23, 0.6);
          color: #e2e8f0; font-family: inherit; font-size: 0.85rem; outline: none;
        }
        .hod-meta-input {
          padding: 0.4rem 0.7rem; border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.25);
          background: rgba(10, 14, 23, 0.6); color: #e2e8f0; font-family: inherit; font-size: 0.8rem; outline: none;
        }
        .hod-btn {
          padding: 0.45rem 0.9rem; border-radius: 6px; cursor: pointer; font-weight: 700;
          font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; transition: all 0.2s;
        }
        .hod-item-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        .hod-item-table th { text-align: left; padding: 0.5rem 0.7rem; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; border-bottom: 1px solid rgba(255,255,255,0.07); }
        .hod-item-table td { padding: 0.55rem 0.7rem; border-bottom: 1px solid rgba(255,255,255,0.04); color: #e2e8f0; }
        .hod-switch { position: relative; width: 46px; height: 24px; border-radius: 12px; cursor: pointer; transition: background 0.25s; border: 1px solid rgba(255,255,255,0.15); }
        .hod-switch-knob { position: absolute; top: 2px; width: 18px; height: 18px; border-radius: 50%; background: #e2e8f0; transition: left 0.25s; }
      `}</style>

      {banner && (
        <div style={{ marginBottom: '1rem', padding: '0.6rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: banner.type === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)', color: banner.type === 'success' ? '#10b981' : '#ef4444', border: `1px solid ${banner.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}` }}>
          {banner.message}
        </div>
      )}

      {/* Manual Stock Adjustment Widget */}
      <div style={{ marginBottom: '1.5rem' }}>
        <ManualLogWidget onLogged={fetchOrders} />
      </div>

      {/* Draft PO Grid */}
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', margin: '0 0 1rem 0' }}>
        Draft Purchase Orders
        <span style={{ marginLeft: '0.6rem', fontSize: '0.7rem', color: '#64748b', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Grouped by Supplier</span>
      </h3>

      {drafts.length === 0 && (
        <div style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '12px', border: '1px dashed rgba(99, 102, 241, 0.2)', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
          No open drafts. Low-stock breaches will auto-synthesize supplier drafts here.
        </div>
      )}

      {drafts.map(po => (
        <div key={po.po_id} id={`po-card-${po.po_id}`} className={`hod-po-card ${po.priority === 1 ? 'high-priority' : ''} ${pulsingPoId === po.po_id ? 'alert-highlight' : ''}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.8rem', marginBottom: '0.9rem' }}>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#818cf8' }}>{po.po_id} {statusChip(po.status)}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                {po.supplier_name} <span style={{ color: '#475569' }}>({po.supplier_id})</span> · Total: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>${po.total_cost.toFixed(2)}</span>
              </div>
            </div>

            {/* High Priority Pulse Switch */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: po.priority === 1 ? '#f97316' : '#64748b' }}>High Priority</span>
              <div
                className="hod-switch"
                onClick={() => togglePriority(po)}
                style={{ background: po.priority === 1 ? 'rgba(249, 115, 22, 0.6)' : 'rgba(30, 41, 59, 0.9)' }}
              >
                <div className="hod-switch-knob" style={{ left: po.priority === 1 ? '24px' : '3px' }} />
              </div>
            </div>
          </div>

          <table className="hod-item-table">
            <thead>
              <tr>
                <th>SKU</th><th>Description</th><th>On Hand / Threshold</th><th>MOQ</th><th>Qty</th><th>Unit Cost</th><th></th>
              </tr>
            </thead>
            <tbody>
              {po.items.map(item => {
                const moq = item.min_order_qty || 1;
                const stagedQty = dirtyQty[`${po.po_id}|${item.sku_id}`] !== undefined
                  ? dirtyQty[`${po.po_id}|${item.sku_id}`] : item.quantity;
                const belowMoq = Number(stagedQty) > 0 && Number(stagedQty) < moq;
                return (
                <tr key={item.sku_id}>
                  <td style={{ color: '#818cf8', fontWeight: 600 }}>{item.sku_id}</td>
                  <td>{item.nomenclature}</td>
                  <td style={{ color: item.quantity_on_hand <= item.reorder_threshold ? '#ef4444' : '#94a3b8' }}>
                    {item.quantity_on_hand} / {item.reorder_threshold}
                  </td>
                  <td style={{ color: moq > 1 ? '#fbbf24' : '#64748b', fontWeight: moq > 1 ? 600 : 400 }}>
                    {moq}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <input
                      type="number" min="1" className="hod-qty-input"
                      value={stagedQty}
                      onChange={e => stageQty(po.po_id, item.sku_id, e.target.value)}
                      style={belowMoq ? { borderColor: 'rgba(245, 158, 11, 0.7)' } : {}}
                    />
                    {/* Q1 policy: non-blocking warning + one-click round-up */}
                    {belowMoq && (
                      <span className="hod-moq-badge">
                        Below MOQ {moq}
                        <button className="hod-moq-roundup" onClick={() => stageQty(po.po_id, item.sku_id, moq)}>
                          Round up
                        </button>
                      </span>
                    )}
                  </td>
                  <td style={{ color: '#94a3b8' }}>${item.unit_cost.toFixed(2)}</td>
                  <td>
                    <button
                      className="hod-btn"
                      onClick={() => excludeItem(po.po_id, item.sku_id)}
                      style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                    >
                      Exclude
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>

          <div style={{ display: 'flex', gap: '0.8rem', marginTop: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              ETA Override{' '}
              <input
                type="date" className="hod-meta-input"
                value={(dirtyMeta[po.po_id]?.eta_date !== undefined ? dirtyMeta[po.po_id].eta_date : po.eta_date) || ''}
                onChange={e => stageMeta(po.po_id, 'eta_date', e.target.value)}
                style={{ marginLeft: '0.4rem' }}
              />
            </label>
            <input
              className="hod-meta-input"
              placeholder="Notes / special instructions for supplier..."
              value={(dirtyMeta[po.po_id]?.notes !== undefined ? dirtyMeta[po.po_id].notes : po.notes) || ''}
              onChange={e => stageMeta(po.po_id, 'notes', e.target.value)}
              style={{ flex: 1, minWidth: '220px' }}
            />
            <button className="hod-btn" onClick={() => persistDraft(po)} style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.35)' }}>
              Save Draft
            </button>
            <button className="hod-btn" onClick={() => submitToCfo(po.po_id)} style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.35)' }}>
              Submit to CFO
            </button>
          </div>
        </div>
      ))}

      {/* Inbound / Pipeline Tracking */}
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#e2e8f0', margin: '1.8rem 0 1rem 0' }}>
        Order Pipeline
        <span style={{ marginLeft: '0.6rem', fontSize: '0.7rem', color: '#64748b', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Pending CFO · Hold · Inbound</span>
      </h3>

      {inbound.length === 0 ? (
        <div style={{ padding: '1.2rem', textAlign: 'center', color: '#64748b', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '12px', border: '1px dashed rgba(99, 102, 241, 0.2)', fontSize: '0.85rem' }}>
          No orders in the approval or delivery pipeline.
        </div>
      ) : (
        <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.15)', background: 'rgba(10, 14, 23, 0.5)' }}>
          <table className="hod-item-table">
            <thead>
              <tr><th>PO</th><th>Supplier</th><th>Status</th><th>ETA</th><th>Items</th><th>Total</th><th>Action</th></tr>
            </thead>
            <tbody>
              {inbound.map(po => (
                <tr key={po.po_id}>
                  <td style={{ color: '#818cf8', fontWeight: 600 }}>{po.po_id}</td>
                  <td>{po.supplier_name}</td>
                  <td>{statusChip(po.status)}</td>
                  <td style={{ color: '#94a3b8' }}>{po.eta_date || '—'}</td>
                  <td style={{ color: '#94a3b8' }}>{po.items.length}</td>
                  <td style={{ color: '#e2e8f0', fontWeight: 600 }}>${po.total_cost.toFixed(2)}</td>
                  <td>
                    {po.status === 'APPROVED' ? (
                      <button className="hod-btn" onClick={() => receiveShipment(po.po_id)} style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.35)' }}>
                        Receive Shipment
                      </button>
                    ) : (
                      <span style={{ fontSize: '0.72rem', color: '#475569' }}>Awaiting CFO</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {/* Real-time SKU Master Inventory Ledger */}
      <div style={{ marginTop: '2.5rem', borderTop: '1px solid rgba(99, 102, 241, 0.15)', paddingTop: '2rem' }}>
        <SkuLedger />
      </div>
    </div>
  );
};

export default HODWorkspace;
