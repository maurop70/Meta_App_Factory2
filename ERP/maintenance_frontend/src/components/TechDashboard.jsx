import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/MockAuthContext';

const TechDashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });
  const [updates, setUpdates] = useState({});
  const { userRole } = useAuth();
  const [fetchTrigger, setFetchTrigger] = useState(0);

  useEffect(() => {
    const fetchMWO = async () => {
      try {
        const response = await api.get('/api/mwo');
        const data = response.data.data || response.data;
        const allOrders = Array.isArray(data) ? data : [];
        
        // DTO Normalization Layer
        const normalizedOrders = allOrders.map(order => ({
          ...order,
          assigned_tech: order.technician,
          sku_consumed: order.consumed_sku,
          status: order.status ? order.status.toUpperCase().replace(/ /g, '_') : 'UNKNOWN'
        }));

        // RBAC Filter Remediation
        const isAdmin = userRole === 'HM (Admin)' || userRole === 'Admin';
        
        const activeTechOrders = normalizedOrders.filter(order => {
          if (isAdmin) return true;
          return (order.status === 'ASSIGNED' || order.status === 'IN_PROGRESS' || order.status === 'PENDING') && order.assigned_tech === userRole;
        });
        
        setWorkOrders(activeTechOrders);
        setStatus({ type: 'success', message: '' });
      } catch (err) {
        const errorMsg = err.response?.data?.detail || err.message || "Failed to fetch work orders.";
        setStatus({ type: 'error', message: errorMsg });
      }
    };
    
    fetchMWO();
  }, [userRole, fetchTrigger]);

  const handleInputChange = (mwo_id, field, value) => {
    setUpdates(prev => ({
      ...prev,
      [mwo_id]: {
        ...prev[mwo_id],
        [field]: value
      }
    }));
  };

  const executeActuation = async (mwo_id, targetStatus) => {
    const originalOrder = workOrders.find(o => o.mwo_id === mwo_id) || {};
    const localUpdates = updates[mwo_id] || {};
    
    // Merge payload with explicit null mapping for strict JSON compliance
    const payload = {
      status: targetStatus,
      consumed_sku: localUpdates.sku_consumed !== undefined ? localUpdates.sku_consumed : (originalOrder.sku_consumed || null),
      manual_log: localUpdates.manual_log !== undefined ? localUpdates.manual_log : (originalOrder.manual_log || null)
    };

    try {
      await api.patch(`/api/mwo/${mwo_id}`, payload);
      setFetchTrigger(prev => prev + 1);
      // Clean local state
      setUpdates(prev => {
        const newState = { ...prev };
        delete newState[mwo_id];
        return newState;
      });
      alert(`Actuation Confirmed: MWO updated to ${targetStatus}.`);
    } catch (err) {
      console.error(err);
      alert("Failed to update work order. See console for details.");
    }
  };

  if (status.type === 'loading') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error') {
    return <div className="erp-status-message error">Error: {status.message}</div>;
  }

  const STATUS_DISPLAY_MAP = {
    "PENDING": "Pending",
    "ASSIGNED": "Assigned",
    "IN_PROGRESS": "In Progress",
    "PENDING_REVIEW": "Pending Review",
    "COMPLETED": "Completed"
  };

  const isAdmin = userRole === 'HM (Admin)' || userRole === 'Admin';

  return (
    <div className="erp-dashboard-section" style={{ marginTop: '20px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1rem' }}>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>Technician Edge Node - Active Tasks (Expanded Ledger)</h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {workOrders.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No active assignments found.</div>
        ) : (
          workOrders.map((order, idx) => {
            const orderUpdates = updates[order.mwo_id] || {};
            const isRework = order.status === 'IN_PROGRESS' && order.start_date !== null;
            
            return (
              <div key={order.mwo_id || idx} style={{
                background: isRework ? 'rgba(239, 68, 68, 0.05)' : 'rgba(15, 23, 42, 0.4)',
                border: `1px solid ${isRework ? 'var(--danger)' : 'var(--border)'}`,
                borderRadius: '8px',
                padding: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem'
              }}>
                {/* Header Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <div>
                    <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary)' }}>{order.mwo_id || 'N/A'}</h4>
                    <p style={{ margin: 0, color: 'var(--text-secondary)' }}>{order.description || 'N/A'}</p>
                  </div>
                  <div>
                    {isRework ? (
                      <span style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.85rem' }}>REWORK REQUIRED</span>
                    ) : (
                      <span style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', color: 'var(--accent)', padding: '4px 8px', borderRadius: '4px', fontWeight: '500', fontSize: '0.85rem' }}>{STATUS_DISPLAY_MAP[order.status] || order.status}</span>
                    )}
                  </div>
                </div>

                {/* Input Matrix */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Consumed SKU</label>
                    <input 
                      type="text" 
                      placeholder="e.g. SKU-1234"
                      value={orderUpdates.sku_consumed !== undefined ? orderUpdates.sku_consumed : (order.sku_consumed || '')}
                      onChange={(e) => handleInputChange(order.mwo_id, 'sku_consumed', e.target.value)}
                      style={{ padding: '8px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '6px' }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Diagnostic / Resolution Log</label>
                    <textarea 
                      placeholder="Enter details..."
                      value={orderUpdates.manual_log !== undefined ? orderUpdates.manual_log : (order.manual_log || '')}
                      onChange={(e) => handleInputChange(order.mwo_id, 'manual_log', e.target.value)}
                      style={{ padding: '8px', minHeight: '60px', resize: 'vertical', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '6px' }}
                    />
                  </div>
                </div>

                {/* 3-Button State Machine Actuation */}
                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', justifyContent: 'flex-end', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <button 
                    onClick={() => executeActuation(order.mwo_id, 'IN_PROGRESS')}
                    disabled={order.status === 'IN_PROGRESS'}
                    style={{ padding: '8px 16px', cursor: order.status === 'IN_PROGRESS' ? 'not-allowed' : 'pointer', backgroundColor: order.status === 'IN_PROGRESS' ? 'rgba(59,130,246,0.2)' : 'var(--accent)', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '500', transition: 'all 0.2s', opacity: order.status === 'IN_PROGRESS' ? 0.5 : 1 }}
                  >
                    START WORK
                  </button>
                  
                  <button 
                    onClick={() => executeActuation(order.mwo_id, 'PENDING_REVIEW')}
                    disabled={order.status === 'PENDING_REVIEW'}
                    style={{ padding: '8px 16px', cursor: order.status === 'PENDING_REVIEW' ? 'not-allowed' : 'pointer', backgroundColor: order.status === 'PENDING_REVIEW' ? 'rgba(245,158,11,0.2)' : '#f59e0b', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '500', transition: 'all 0.2s', opacity: order.status === 'PENDING_REVIEW' ? 0.5 : 1 }}
                  >
                    DONE - READY FOR REVIEW
                  </button>
                  
                  {isAdmin && (
                    <button 
                      onClick={() => executeActuation(order.mwo_id, 'COMPLETED')}
                      style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: 'var(--success)', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '500', transition: 'all 0.2s' }}
                    >
                      COMPLETE
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default TechDashboard;
