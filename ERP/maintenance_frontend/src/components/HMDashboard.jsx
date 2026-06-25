import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import HMAssignmentModal from './HMAssignmentModal';
import HMReviewModal from './HMReviewModal';
import HODWorkspace from './HODWorkspace';
import ProfileSettings from './ProfileSettings';
import { useAuth } from '../context/AuthContext';

const HMDashboard = () => {
  const { userRole, jwtPayload } = useAuth();
  const hmId = jwtPayload?.sub || 'Unknown HM';
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });
  const [selectedMWO, setSelectedMWO] = useState(null);
  const [reviewMWO, setReviewMWO] = useState(null);
  const [technicianRoster, setTechnicianRoster] = useState([]);
  const [page, setPage] = useState(0);
  
  const navigate = useNavigate();

  // Filter States
  const [filterTech, setFilterTech] = useState('');
  const [filterEquipment, setFilterEquipment] = useState('');
  const [filterLocation, setFilterLocation] = useState('');
  
  const [hmRoster, setHmRoster] = useState([]);
  const [targetHm, setTargetHm] = useState('');

  // [BACK OFFICE INVENTORY] Command console view switcher
  const [activeView, setActiveView] = useState('mwo');
  const [showProfile, setShowProfile] = useState(false);

  // [SAFETY ALERTS] Low-stock alert feed + draft PO deep-link target
  const [inventoryAlerts, setInventoryAlerts] = useState([]);
  const [highlightPoId, setHighlightPoId] = useState(null);
  // Tracks the sku_id whose draft PO is currently being synthesized (drives
  // the button's disabled/loading state and blocks double-submit).
  const [creatingDraftFor, setCreatingDraftFor] = useState(null);
  const [draftError, setDraftError] = useState(null);

  const fetchAlerts = async () => {
    try {
      const response = await api.get('/inventory/alerts');
      setInventoryAlerts(response.data.data || []);
    } catch (err) {
      console.warn('Inventory alert sync failed.', err);
    }
  };

  const downloadCsv = async (path, filename) => {
    try {
      const res = await api.get(path, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Download failed.');
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [activeView]); // re-sync when returning from the procurement view

  const openAlertDraft = (alert) => {
    setHighlightPoId(alert.draft_po_id || null);
    setActiveView('inventory');
  };

  // Synthesize (or append to) the supplier's open draft PO for a below-threshold
  // SKU, then deep-link the HM into the procurement workspace at that draft.
  // Note: the backend field is `quantity`, not `min_order_qty` — we send the
  // SKU's minimum order quantity as the line quantity.
  const handleCreateDraft = async (alert) => {
    if (creatingDraftFor) return; // single in-flight request; blocks double-click
    setCreatingDraftFor(alert.sku_id);
    setDraftError(null);
    try {
      // Mirror the backend reorder heuristic (maintenance_backend.py): target
      // twice the threshold less current stock, floored at 1 and the SKU MOQ.
      const threshold = alert.reorder_threshold || 5;
      const onHand = alert.quantity_on_hand || 0;
      const moq = alert.min_order_qty || 1;
      const calculatedQty = Math.max((threshold * 2) - onHand, 1);
      const quantity = Math.max(calculatedQty, moq);
      const response = await api.post('/orders/drafts/add-item', {
        sku_id: alert.sku_id,
        quantity,
      });
      // Switching to the inventory view re-syncs the alert feed via the
      // activeView effect, so the row will flip to "View Draft" on return.
      setHighlightPoId(response.data?.po_id || null);
      setActiveView('inventory');
    } catch (err) {
      console.warn('Draft PO synthesis failed.', err);
      const detail = err?.response?.data?.detail
        || 'Could not create draft PO. Confirm the SKU has a supplier assigned.';
      setDraftError(`${alert.sku_id}: ${detail}`);
    } finally {
      setCreatingDraftFor(null);
    }
  };

  const fetchHms = async () => {
    try {
      const response = await api.get('/mwo/hms');
      setHmRoster(response.data.data || response.data || []);
    } catch (err) {
      console.warn("Failed to fetch HM roster.", err);
    }
  };

  const fetchTechnicians = async () => {
    try {
      const response = await api.get('/mwo/technicians');
      setTechnicianRoster(response.data.data || response.data);
    } catch (err) {
      console.warn("Failed to fetch technician roster.", err);
    }
  };

  const fetchMWO = async () => {
    try {
      const response = await api.get(`/mwo?limit=50&offset=${page * 50}`);
      const dbPayload = response.data.data || response.data;
      
      const rawOrders = Array.isArray(dbPayload) ? dbPayload : [];
      
      setWorkOrders(rawOrders);
      setStatus({ type: 'success', message: '' });
    } catch (err) {
      console.warn("Network fragmentation detected.", err);
      setStatus({ type: 'error', message: 'Failed to connect to backend' });
    }
  };

  useEffect(() => {
    fetchTechnicians();
    if (['ADMINISTRATOR', 'ADMIN'].includes(userRole)) {
      fetchHms();
    }
  }, [userRole]);

  useEffect(() => {
    fetchMWO();
  }, [page, targetHm, hmId]);

  const handleInspect = (mwo) => {
    setSelectedMWO(mwo);
  };

  const closeModal = () => {
    setSelectedMWO(null);
    setReviewMWO(null);
  };

  const executeAssignment = async (mwo_id, assigned_tech) => {
    await api.patch(`/mwo/${mwo_id}`, { status: 'ASSIGNED', assigned_tech: assigned_tech });
    // After successful assignment, immediately fetch the latest state
    await fetchMWO();
  };

  const executeApproval = async (mwo_id) => {
    await api.patch(`/mwo/${mwo_id}`, { status: 'COMPLETED' });
    await fetchMWO();
  };

  const applyFilters = (order) => {
    const matchTech = filterTech === '' || (order.assigned_tech || '').toLowerCase().includes(filterTech.toLowerCase());
    const matchEquip = filterEquipment === '' || (order.equipment_id || '').toLowerCase().includes(filterEquipment.toLowerCase());
    const matchLoc = filterLocation === '' || (order.location_id || '').toLowerCase().includes(filterLocation.toLowerCase());
    return matchTech && matchEquip && matchLoc;
  };

  const unassignedOrders = workOrders
    .filter(o => o.status === 'UNASSIGNED' || o.status === 'ASSIGNED')
    .filter(applyFilters);
    
  const reviewOrders = workOrders
    .filter(o => o.status === 'PENDING_REVIEW')
    .filter(applyFilters);

  if (status.type === 'loading' && activeView === 'mwo') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error' && activeView === 'mwo') {
    return (
      <div>
        <div className="erp-status-message error">{status.message}</div>
        <button onClick={() => setActiveView('inventory')} style={{ margin: '1rem', padding: '0.5rem 1rem', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem' }}>
          Open Inventory & Procurement
        </button>
      </div>
    );
  }

  if (activeView === 'inventory') {
    return (
      <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
          <button onClick={() => setActiveView('mwo')} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border, rgba(99,102,241,0.15))', background: 'rgba(15, 23, 42, 0.5)', color: 'var(--text-muted, #64748b)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem', transition: 'all 0.2s' }}>
            Work Orders
          </button>
          <button style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--accent, #6366f1)', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--text-primary, #e2e8f0)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            Inventory & Procurement
          </button>
        </div>
        <HODWorkspace highlightPoId={highlightPoId} onHighlightConsumed={() => setHighlightPoId(null)} />
      </div>
    );
  }

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
      {/* HOD Command Console Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <button style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--accent, #6366f1)', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--text-primary, #e2e8f0)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
          Work Orders
        </button>
        <button onClick={() => setActiveView('inventory')} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border, rgba(99,102,241,0.15))', background: 'rgba(15, 23, 42, 0.5)', color: 'var(--text-muted, #64748b)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem', transition: 'all 0.2s' }}>
          Inventory & Procurement
        </button>
        <button onClick={() => downloadCsv('/reports/hm-work-orders/download', 'hm_work_orders.csv')} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.1)', color: '#34d399', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
          Export Work Orders (CSV)
        </button>
        <button onClick={() => downloadCsv('/reports/inventory/download', 'inventory_report.csv')} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.1)', color: '#34d399', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
          Download Inventory Report
        </button>
        <button onClick={() => setShowProfile(true)} style={{ marginLeft: 'auto', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid rgba(99,102,241,0.3)', background: 'rgba(99,102,241,0.1)', color: 'var(--accent-hover, #818cf8)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
          Profile
        </button>
      </div>
      {showProfile && <ProfileSettings onClose={() => setShowProfile(false)} />}

      {/* Mobile-First CSS Reflow Matrix */}
      <style>{`
        .btn-inspect {
          background: rgba(139, 92, 246, 0.15);
          color: #a78bfa;
          border: 1px solid rgba(139, 92, 246, 0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.7rem;
          font-weight: 600;
          transition: all 0.2s;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .btn-inspect:hover {
          background: var(--accent-purple, #8b5cf6);
          color: #fff;
        }
        
        .responsive-matrix {
          width: 100%;
          text-align: left;
          border-collapse: collapse;
          font-size: 0.82rem;
        }
        .responsive-matrix th {
          padding: 0.8rem 1rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          font-size: 0.7rem;
        }
        .responsive-matrix td {
          padding: 1rem 1.2rem;
        }
        .responsive-matrix tr {
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        /* Fallback stacked CSS cards for viewports < 900px */
        @media (max-width: 900px) {
          .responsive-matrix, .responsive-matrix thead, .responsive-matrix tbody, .responsive-matrix th, .responsive-matrix td, .responsive-matrix tr { 
            display: block; 
            width: 100%; 
          }
          .responsive-matrix thead tr { 
            position: absolute; top: -9999px; left: -9999px; 
          }
          .responsive-matrix tr {
            margin-bottom: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.02);
            padding: 1rem;
          }
          .responsive-matrix td {
            border: none;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            position: relative;
            padding: 0.8rem 0 0.8rem 45% !important;
            text-align: right;
            min-height: 40px;
            display: flex;
            justify-content: flex-end;
            align-items: center;
          }
          .responsive-matrix td:last-child { border-bottom: 0; }
          .responsive-matrix td::before {
            content: attr(data-label);
            position: absolute;
            left: 0;
            width: 40%;
            text-align: left;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #94a3b8;
          }
        }
      `}</style>
      
      <style>{`
        .filter-input {
          padding: 0.5rem 0.8rem;
          border-radius: 6px;
          border: 1px solid rgba(56, 189, 248, 0.3);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          flex: 1;
          min-width: 150px;
          font-family: inherit;
          font-size: 0.85rem;
          outline: none;
          transition: border-color 0.2s;
        }
        .filter-input:focus {
          border-color: #38bdf8;
          box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
        }
      `}</style>
      
      {/* [SAFETY ALERTS] Inventory Alerts Panel — dedicated, deep-links to draft POs */}
      {inventoryAlerts.length > 0 && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem 1.2rem', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.35)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.7rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ef4444', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Inventory Alerts
            </span>
            <span style={{ padding: '1px 8px', borderRadius: '10px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5' }}>
              {inventoryAlerts.length}
            </span>
          </div>
          {draftError && (
            <div style={{ marginBottom: '0.4rem', fontSize: '0.72rem', color: '#fca5a5', fontWeight: 600 }}>
              ⚠ {draftError}
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {inventoryAlerts.map(alert => (
              <div key={alert.sku_id} style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap', fontSize: '0.82rem' }}>
                <span style={{ color: '#fca5a5', fontWeight: 600 }}>{alert.sku_id}</span>
                <span style={{ color: '#e2e8f0' }}>{alert.nomenclature}</span>
                <span style={{ color: '#94a3b8' }}>
                  is below safety threshold ({alert.quantity_on_hand} / {alert.reorder_threshold} on hand)
                </span>
                {alert.active_po_id ? (
                  <span
                    title={`An active purchase order already covers this SKU (${alert.active_po_id}).`}
                    style={{ padding: '0.2rem 0.7rem', borderRadius: '6px', border: '1px solid rgba(251, 191, 36, 0.4)', background: 'rgba(251, 191, 36, 0.12)', color: '#fbbf24', fontWeight: 700, fontSize: '0.72rem' }}
                  >
                    PO {alert.active_po_status}: {alert.active_po_id}
                  </span>
                ) : alert.draft_po_id ? (
                  <button
                    onClick={() => openAlertDraft(alert)}
                    style={{ padding: '0.2rem 0.7rem', borderRadius: '6px', border: '1px solid rgba(99, 102, 241, 0.4)', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', cursor: 'pointer', fontWeight: 700, fontSize: '0.72rem' }}
                  >
                    View Draft {alert.draft_po_id} →
                  </button>
                ) : (
                  <button
                    onClick={() => handleCreateDraft(alert)}
                    disabled={creatingDraftFor === alert.sku_id}
                    style={{ padding: '0.2rem 0.7rem', borderRadius: '6px', border: '1px solid rgba(34, 197, 94, 0.4)', background: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', cursor: creatingDraftFor === alert.sku_id ? 'wait' : 'pointer', fontWeight: 700, fontSize: '0.72rem', opacity: creatingDraftFor === alert.sku_id ? 0.6 : 1 }}
                  >
                    {creatingDraftFor === alert.sku_id ? 'Creating…' : 'Create Draft PO →'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Global Filters */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap', background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', alignItems: 'center' }}>
        <input 
          type="text" 
          placeholder="Filter by Technician..." 
          value={filterTech} 
          onChange={e => setFilterTech(e.target.value)} 
          className="filter-input"
        />
        <input 
          type="text" 
          placeholder="Filter by Equipment..." 
          value={filterEquipment} 
          onChange={e => setFilterEquipment(e.target.value)} 
          className="filter-input"
        />
        <input 
          type="text" 
          placeholder="Filter by Location..." 
          value={filterLocation} 
          onChange={e => setFilterLocation(e.target.value)} 
          className="filter-input"
        />
        <button type="button" onClick={() => navigate('/archive')} style={{ padding: '0.5rem 1.5rem', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px', cursor: 'pointer', fontWeight: '700', fontSize: '0.85rem', transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          View Archives
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', margin: 0 }}>Inbound MWO Queue - HM</h3>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {['ADMINISTRATOR', 'ADMIN'].includes(userRole) && (
            <select 
              value={targetHm} 
              onChange={(e) => setTargetHm(e.target.value)}
              style={{
                background: 'rgba(15, 23, 42, 0.8)', color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.4rem 0.8rem',
                borderRadius: '6px', fontWeight: 600, fontSize: '0.85rem', outline: 'none'
              }}
            >
              <option value="">-- Impersonate HM --</option>
              {hmRoster.map(hm => (
                <option key={hm.user_id} value={hm.user_id}>{hm.user_id} ({hm.name})</option>
              ))}
            </select>
          )}
          <div style={{ background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.4rem 0.8rem', borderRadius: '6px', color: '#38bdf8', fontWeight: 600, fontSize: '0.85rem' }}>
            HM ID: {targetHm || hmId}
          </div>
        </div>
      </div>
      
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
        <table className="responsive-matrix">
          <thead>
            <tr style={{ background: 'rgba(99, 102, 241, 0.1)', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
              <th>MWO ID</th>
              <th>Status</th>
              <th>DM Urgency</th>
              <th>Equipment</th>
              <th>Location</th>
              <th>Assigned Tech</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {unassignedOrders.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No active work orders in queue.</td>
              </tr>
            ) : (
              unassignedOrders.map((order) => (
                <tr key={order.mwo_id}>
                  <td data-label="MWO ID" style={{ color: '#818cf8', fontWeight: 500 }}>
                    {order.mwo_id}
                  </td>
                  <td data-label="STATUS">
                    <span style={{ 
                      padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, 
                      background: order.status === 'ASSIGNED' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(239, 68, 68, 0.15)', 
                      color: order.status === 'ASSIGNED' ? '#38bdf8' : '#ef4444' 
                    }}>
                      {order.status}
                    </span>
                  </td>
                  <td data-label="DM URGENCY" style={{ color: '#e2e8f0' }}>
                    <span style={{ padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', whiteSpace: 'nowrap', fontWeight: 600, background: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(148, 163, 184, 0.15)', color: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? '#fbbf24' : '#94a3b8' }}>
                      {order.dm_urgency || 'Normal'}
                    </span>
                  </td>
                  <td data-label="EQUIPMENT" style={{ color: '#e2e8f0' }}>
                    {order.equipment_nomenclature || order.equipment_id}
                  </td>
                  <td data-label="LOCATION" style={{ color: '#e2e8f0' }}>
                    {order.location_nomenclature || order.location_id || 'Zone Alpha'}
                  </td>
                  <td data-label="ASSIGNED TECH" style={{ color: '#94a3b8' }}>
                    {order.assigned_tech || 'Unassigned'}
                  </td>
                  <td data-label="ACTION">
                    {/* Mandatory Review Isolation - No inline assignments */}
                    <button 
                      className="btn-inspect" 
                      onClick={() => handleInspect(order)}
                    >
                      {order.status === 'ASSIGNED' ? 'Re-Assign' : 'Inspect'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {reviewOrders.length > 0 && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '2rem 0 1.2rem 0' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', margin: 0 }}>Pending Review Queue - HM</h3>
          </div>
          
          <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(16, 185, 129, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
            <table className="responsive-matrix">
              <thead>
                <tr style={{ background: 'rgba(16, 185, 129, 0.1)', borderBottom: '1px solid var(--border, rgba(16, 185, 129, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
                  <th>MWO ID</th>
                  <th>Status</th>
                  <th>Location</th>
                  <th>Tech</th>
                  <th>Labor (Hrs)</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reviewOrders.map((order) => (
                  <tr key={order.mwo_id}>
                    <td data-label="MWO ID" style={{ color: '#10b981', fontWeight: 500 }}>
                      {order.mwo_id}
                    </td>
                    <td data-label="STATUS">
                      <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
                        {order.status}
                      </span>
                    </td>
                    <td data-label="LOCATION" style={{ color: '#e2e8f0' }}>
                      {order.location_nomenclature || order.location_id || 'Zone Alpha'}
                    </td>
                    <td data-label="TECH" style={{ color: '#e2e8f0' }}>
                      {order.assigned_tech}
                    </td>
                    <td data-label="LABOR (HRS)" style={{ color: '#e2e8f0' }}>
                      {order.labor_hours ? order.labor_hours.toFixed(2) : 'N/A'}
                    </td>
                    <td data-label="ACTION">
                      <button 
                        className="btn-inspect" 
                        onClick={() => setReviewMWO(order)}
                        style={{ color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)', background: 'rgba(16, 185, 129, 0.15)' }}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}


      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
        <button 
          onClick={() => setPage(p => Math.max(0, p - 1))}
          disabled={page === 0}
          style={{ padding: '0.5rem 1rem', background: 'rgba(99, 102, 241, 0.15)', color: '#a78bfa', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.5 : 1, transition: 'all 0.2s', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}
        >
          Previous
        </button>
        <span style={{ color: '#94a3b8', fontSize: '0.85rem', alignSelf: 'center', fontWeight: 600 }}>Page {page + 1}</span>
        <button 
          onClick={() => setPage(p => p + 1)}
          disabled={workOrders.length < 50}
          style={{ padding: '0.5rem 1rem', background: 'rgba(99, 102, 241, 0.15)', color: '#a78bfa', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px', cursor: workOrders.length < 50 ? 'not-allowed' : 'pointer', opacity: workOrders.length < 50 ? 0.5 : 1, transition: 'all 0.2s', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}
        >
          Next
        </button>
      </div>

      {/* Actuation Lockout Modal */}
      {selectedMWO && (
        <HMAssignmentModal 
          selectedMWO={selectedMWO} 
          closeModal={closeModal} 
          executeAssignment={executeAssignment}
          technicianRoster={technicianRoster}
        />
      )}

      {reviewMWO && (
        <HMReviewModal
          selectedMWO={reviewMWO}
          closeModal={closeModal}
          executeApproval={executeApproval}
        />
      )}
    </div>
  );
};

export default HMDashboard;
