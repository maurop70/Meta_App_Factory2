import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/MockAuthContext';

const MWODashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const { userRole } = useAuth();

  useEffect(() => {
    const fetchMWO = async () => {
      try {
        const response = await api.get('/api/mwo');
        // Handle potential schema wrappers
        const data = response.data.data || response.data;
        setWorkOrders(Array.isArray(data) ? data : []);
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

  if (status.type === 'loading') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error') {
    return <div className="erp-status-message error">Error: {status.message}</div>;
  }

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '1.2rem' }}>Active Work Orders</h3>
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: 'rgba(99, 102, 241, 0.1)', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>MWO ID</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Status</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>DM Urgency</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>HM Priority</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Description</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Assigned Tech</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Consumed SKU</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Manual Log</th>
              {userRole === 'HM (Admin)' && <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Action</th>}
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan={userRole === 'HM (Admin)' ? "9" : "8"} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No work orders found.</td>
              </tr>
            ) : (
              workOrders.map((order, idx) => (
                <tr key={order.mwo_id || idx} style={{ borderBottom: '1px solid rgba(99, 102, 241, 0.08)', transition: 'background 0.2s' }} onMouseOver={(e) => e.currentTarget.style.background = 'rgba(99, 102, 241, 0.05)'} onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-primary, #e2e8f0)', fontWeight: 500 }}>{order.mwo_id || 'N/A'}</td>
                  <td style={{ padding: '0.8rem 1rem' }}>
                    <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, background: order.status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)', color: order.status === 'COMPLETED' ? 'var(--success, #10b981)' : 'var(--warning, #f59e0b)' }}>
                      {order.status || 'Pending'}
                    </span>
                  </td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-secondary, #94a3b8)' }}>{order.dm_urgency || 'Normal'}</td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-secondary, #94a3b8)' }}>{order.hm_priority || 'Normal'}</td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-primary, #e2e8f0)' }}>{order.description || 'N/A'}</td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--accent-hover, #818cf8)' }}>{order.assigned_tech || 'Unassigned'}</td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-muted, #64748b)' }}>{order.consumed_sku || 'None'}</td>
                  <td style={{ padding: '0.8rem 1rem', color: 'var(--text-muted, #64748b)' }}>{order.manual_log || 'None'}</td>
                  {userRole === 'HM (Admin)' && (
                    <td style={{ padding: '0.8rem 1rem' }}>
                      {order.status === 'PENDING_REVIEW' && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => handleComplete(order.mwo_id)}
                            style={{ padding: '4px 10px', cursor: 'pointer', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--success, #10b981)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', fontSize: '0.7rem', fontWeight: 600, transition: 'all 0.2s' }}
                            onMouseOver={(e) => { e.currentTarget.style.background = 'var(--success, #10b981)'; e.currentTarget.style.color = '#fff'; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(16, 185, 129, 0.15)'; e.currentTarget.style.color = 'var(--success, #10b981)'; }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(order.mwo_id)}
                            style={{ padding: '4px 10px', cursor: 'pointer', background: 'rgba(239, 68, 68, 0.15)', color: 'var(--danger, #ef4444)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', fontSize: '0.7rem', fontWeight: 600, transition: 'all 0.2s' }}
                            onMouseOver={(e) => { e.currentTarget.style.background = 'var(--danger, #ef4444)'; e.currentTarget.style.color = '#fff'; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'; e.currentTarget.style.color = 'var(--danger, #ef4444)'; }}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MWODashboard;
