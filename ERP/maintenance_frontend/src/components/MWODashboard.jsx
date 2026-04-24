import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/MockAuthContext';

const MWODashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [selectedMWO, setSelectedMWO] = useState(null);
  const { userRole } = useAuth();

  useEffect(() => {
    const fetchMWO = async () => {
      try {
        const response = await api.get('/api/mwo');
        // Handle potential schema wrappers
        const data = response.data.data || response.data;
        const processedData = (Array.isArray(data) ? data : []).map(order => {
          let updatedOrder = { ...order };
          // 1. Force PENDING_ASSIGNMENT for unassigned tickets
          if (!updatedOrder.assigned_tech || updatedOrder.assigned_tech === 'Unassigned') {
            if (updatedOrder.status === 'IN_PROGRESS') updatedOrder.status = 'PENDING_ASSIGNMENT';
          }
          // 2. Force Mock Urgency for UI testing
          if (updatedOrder.mwo_id === 'MWO-1002') updatedOrder.dm_urgency = 'High';
          if (updatedOrder.mwo_id === 'MWO-1005') updatedOrder.dm_urgency = 'Critical';
          return updatedOrder;
        });
        setWorkOrders(processedData);
        setStatus({ type: 'success', message: '' });
      } catch (err) {
        const errorMsg = err.response?.data?.detail || err.message || "Failed to fetch work orders.";
        setStatus({ type: 'error', message: errorMsg });
      }
    };
    
    fetchMWO();
  }, [fetchTrigger]);

  const handleComplete = async (mwo_id) => {
    try {
      await api.patch(`/api/mwo/${mwo_id}`, { status: "COMPLETED" });
      alert(`Work order ${mwo_id} successfully COMPLETED.`);
      setFetchTrigger(prev => prev + 1);
    } catch (err) {
      console.error("Failed to complete work order:", err);
      alert("Failed to complete work order. See console for details.");
    }
  };

  const handleReject = async (mwo_id) => {
    try {
      await api.patch(`/api/mwo/${mwo_id}`, { status: "IN_PROGRESS" });
      alert(`Work order ${mwo_id} REJECTED and returned to IN_PROGRESS.`);
      setFetchTrigger(prev => prev + 1);
    } catch (err) {
      console.error("Failed to reject work order:", err);
      alert("Failed to reject work order. See console for details.");
    }
  };

  const getUrgencyBadge = (urgency) => {
    switch(urgency) {
      case 'High': return { background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' };
      case 'Critical':
      case 'AOG': return { background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' };
      default: return { background: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8' };
    }
  };

  if (status.type === 'loading') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error') {
    return <div className="erp-status-message error">Error: {status.message}</div>;
  }

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
      <style>{`
        .table-select {
          width: 100%;
          min-width: 130px;
          padding: 0.3rem 0.5rem;
          border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          background: rgba(255, 255, 255, 0.04);
          color: var(--text-primary, #e2e8f0);
          font-size: 0.75rem;
          outline: none;
          transition: border-color 0.2s;
          font-family: var(--font, Inter);
        }
        .table-select:focus {
          border-color: #6366f1;
        }
        .table-select option {
          background-color: #0f172a;
          color: #e2e8f0;
        }
        .btn-approve {
          background: rgba(16, 185, 129, 0.15);
          color: #34d399;
          border: 1px solid rgba(16,185,129,0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.7rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        .btn-approve:hover {
          background: var(--success, #10b981);
          color: #fff;
        }
        .btn-reject {
          background: rgba(239, 68, 68, 0.15);
          color: #f87171;
          border: 1px solid rgba(239,68,68,0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.7rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        .btn-reject:hover {
          background: var(--danger, #ef4444);
          color: #fff;
        }
        @media (max-width: 900px) {
          table, thead, tbody, th, td, tr { display: block; width: 100%; }
          thead tr { position: absolute; top: -9999px; left: -9999px; }
          tr {
            margin-bottom: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.02);
            padding: 1rem;
          }
          td {
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
          td:last-child { border-bottom: 0; }
          td::before {
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
          .table-select { min-width: 150px; }
        }
      `}</style>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '1.2rem' }}>Active Work Orders</h3>
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: 'rgba(99, 102, 241, 0.1)', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>MWO ID</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Assigned Tech</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Status</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>DM Urgency</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>HM Priority</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Description</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Manual Log</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No work orders found.</td>
              </tr>
            ) : (
              workOrders.map((order, idx) => (
                <tr key={order.mwo_id || idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', transition: 'background 0.2s' }} onMouseOver={(e) => e.currentTarget.style.background = 'rgba(99, 102, 241, 0.05)'} onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}>
                  <td data-label="MWO ID" style={{ padding: '1rem 1.2rem', color: '#818cf8', fontWeight: 500, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => setSelectedMWO(order)}>
                    {order.mwo_id || 'N/A'}
                  </td>
                  <td data-label="ASSIGNED TECH" style={{ padding: '1rem 1.2rem', color: 'var(--accent-hover, #818cf8)' }}>
                    {order.status !== 'COMPLETED' && userRole === 'HM' ? (
                      <select className="table-select" defaultValue={order.assigned_tech || 'Unassigned'}>
                        <option value="Unassigned">Unassigned</option>
                        <option value="Tech-Alpha">Tech-Alpha</option>
                        <option value="Tech-Bravo">Tech-Bravo</option>
                        <option value="Tech-Charlie">Tech-Charlie</option>
                      </select>
                    ) : (
                      order.assigned_tech || 'Unassigned'
                    )}
                  </td>
                  <td data-label="STATUS" style={{ padding: '1rem 1.2rem' }}>
                    <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, background: order.status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)', color: order.status === 'COMPLETED' ? 'var(--success, #10b981)' : 'var(--warning, #f59e0b)' }}>
                      {order.status || 'Pending'}
                    </span>
                  </td>
                  <td data-label="DM URGENCY" style={{ padding: '1rem 1.2rem' }}>
                    <span style={{ padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', whiteSpace: 'nowrap', fontWeight: 600, ...getUrgencyBadge(order.dm_urgency || 'Normal') }}>
                      {order.dm_urgency || 'Normal'}
                    </span>
                  </td>
                  <td data-label="HM PRIORITY" style={{ padding: '1rem 1.2rem', color: 'var(--text-secondary, #94a3b8)' }}>
                    {order.status !== 'COMPLETED' && userRole === 'HM' ? (
                      <select className="table-select" defaultValue={order.hm_priority || 'Normal'}>
                        <option value="Low">Low</option>
                        <option value="Normal">Normal</option>
                        <option value="High">High</option>
                        <option value="Critical">Critical</option>
                        <option value="AOG">AOG</option>
                      </select>
                    ) : (
                      order.hm_priority || 'Normal'
                    )}
                  </td>
                  <td data-label="DESCRIPTION" style={{ padding: '1rem 1.2rem', color: 'var(--text-primary, #e2e8f0)' }}>{order.description || 'N/A'}</td>
                  <td data-label="MANUAL LOG" style={{ padding: '1rem 1.2rem', color: 'var(--text-muted, #64748b)' }}>{order.manual_log || 'None'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      
      {/* Detail Overlay Modal */}
      {selectedMWO && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.95))', border: '1px solid rgba(255, 255, 255, 0.12)', borderRadius: '12px', padding: '2rem', width: '90%', maxWidth: '500px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', color: '#fff' }}>
            <h3 style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.5rem', marginBottom: '1.5rem', fontWeight: 600 }}>Work Order Details</h3>
            <p style={{ marginBottom: '0.8rem' }}><strong style={{ color: '#94a3b8' }}>ID:</strong> {selectedMWO.mwo_id}</p>
            <p style={{ marginBottom: '0.8rem' }}><strong style={{ color: '#94a3b8' }}>Requester Name:</strong> {selectedMWO.requester_name || 'DM-Alpha'}</p>
            <p style={{ marginBottom: '0.8rem' }}><strong style={{ color: '#94a3b8' }}>Department:</strong> {selectedMWO.department || 'Operations'}</p>
            <p style={{ marginBottom: '0.8rem' }}><strong style={{ color: '#94a3b8' }}>Location:</strong> {selectedMWO.location_id}</p>
            <p style={{ marginBottom: '0.8rem' }}><strong style={{ color: '#94a3b8' }}>Description:</strong><br/>{selectedMWO.description}</p>
            <p style={{ marginBottom: '1.5rem' }}><strong style={{ color: '#94a3b8' }}>Technician Log:</strong><br/>{selectedMWO.manual_log || 'No notes provided by technician.'}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {selectedMWO.status === 'PENDING_REVIEW' ? (
                <div style={{ display: 'flex', gap: '0.8rem', marginRight: 'auto' }}>
                  <button className="btn-approve" onClick={() => { handleComplete(selectedMWO.mwo_id); setSelectedMWO(null); }}>Approve Work</button>
                  <button className="btn-reject" onClick={() => { handleReject(selectedMWO.mwo_id); setSelectedMWO(null); }}>Reject / Rework</button>
                </div>
              ) : (
                <div />
              )}
              <button onClick={() => setSelectedMWO(null)} style={{ padding: '0.6rem 1.2rem', background: 'rgba(255, 255, 255, 0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s', marginLeft: 'auto' }} onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'} onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MWODashboard;
