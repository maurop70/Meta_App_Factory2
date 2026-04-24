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

  const handleUpdateClick = async (mwo_id) => {
    const originalOrder = workOrders.find(o => o.mwo_id === mwo_id) || {};
    const localUpdates = updates[mwo_id] || {};
    
    // Defensive payload merge (Mapping back to backend schema)
    const payload = {
      status: localUpdates.status || originalOrder.status,
      consumed_sku: localUpdates.sku_consumed !== undefined ? localUpdates.sku_consumed : (originalOrder.sku_consumed || ""),
      manual_log: localUpdates.manual_log !== undefined ? localUpdates.manual_log : (originalOrder.manual_log || "")
    };

    try {
      await api.patch(`/api/mwo/${mwo_id}`, payload);
      alert(`Work order ${mwo_id} successfully updated.`);
      
      // State Re-Hydration Logic & Local State Cleanup
      setFetchTrigger(prev => prev + 1);
      setUpdates(prev => {
        const next = { ...prev };
        delete next[mwo_id];
        return next;
      });
    } catch (err) {
      console.error("Failed to update work order:", err);
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

  return (
    <div className="erp-dashboard-section" style={{ marginTop: '20px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1rem' }}>
      <h3 style={{ color: 'var(--text-primary)' }}>Technician Edge Node - Active Tasks</h3>
      <div className="maf-data-table-wrapper">
        <table className="erp-data-table maf-data-matrix">
          <thead>
            <tr>
              <th className="maf-table-header">MWO ID</th>
              <th className="maf-table-header">Task Description</th>
              <th className="maf-table-header">Current Status</th>
              <th className="maf-table-header">Update Status</th>
              <th className="maf-table-header">Consumed SKU</th>
              <th className="maf-table-header">Manual Log</th>
              <th className="maf-table-header">Action</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '15px' }}>No active assignments found.</td>
              </tr>
            ) : (
              workOrders.map((order, idx) => {
                const orderUpdates = updates[order.mwo_id] || {};
                const currentUpdateStatus = orderUpdates.status || order.status;
                
                const isRework = order.status === 'IN_PROGRESS' && order.execution_end !== null;
                
                return (
                  <tr key={order.mwo_id || idx} className="maf-data-row" style={{ 
                    borderLeft: isRework ? '4px solid var(--danger)' : 'none',
                    backgroundColor: isRework ? 'rgba(239, 68, 68, 0.08)' : 'transparent'
                  }}>
                    <td className="maf-table-cell">{order.mwo_id || 'N/A'}</td>
                    <td className="maf-table-cell">{order.description || 'N/A'}</td>
                    <td className="maf-table-cell">
                      {isRework ? (
                        <span style={{ color: 'var(--danger)', fontWeight: 'bold', fontSize: '0.85rem' }}>IN PROGRESS (REWORK REQUIRED)</span>
                      ) : (
                        <span style={{ color: 'var(--accent)', fontWeight: '500' }}>{STATUS_DISPLAY_MAP[order.status] || order.status}</span>
                      )}
                    </td>
                    
                    {/* Read/Write Matrix: Restricted Status Dropdown */}
                    <td className="maf-table-cell">
                      <select 
                        value={orderUpdates.status || ""}
                        onChange={(e) => handleInputChange(order.mwo_id, 'status', e.target.value)}
                        style={{ padding: '6px', width: '140px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '6px' }}
                      >
                        <option value="" disabled>Select Action</option>
                        {/* Only allow valid state transitions from the Edge Node */}
                        <option value="IN_PROGRESS">{STATUS_DISPLAY_MAP["IN_PROGRESS"]}</option>
                        <option value="PENDING_REVIEW">{STATUS_DISPLAY_MAP["PENDING_REVIEW"]}</option>
                      </select>
                    </td>

                    {/* Read/Write Matrix: SKU Input */}
                    <td className="maf-table-cell">
                      <input 
                        type="text" 
                        placeholder="Enter SKU..."
                        defaultValue={order.sku_consumed || ''}
                        onChange={(e) => handleInputChange(order.mwo_id, 'sku_consumed', e.target.value)}
                        style={{ padding: '6px', width: '120px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '6px' }}
                      />
                    </td>

                    {/* Read/Write Matrix: Manual Log Input */}
                    <td className="maf-table-cell">
                      <textarea 
                        placeholder="Enter diagnostic/resolution log..."
                        defaultValue={order.manual_log || ''}
                        onChange={(e) => handleInputChange(order.mwo_id, 'manual_log', e.target.value)}
                        style={{ padding: '6px', width: '200px', resize: 'vertical', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '6px', minHeight: '40px' }}
                      />
                    </td>

                    {/* Submit Actuator */}
                    <td className="maf-table-cell">
                      <button 
                        onClick={() => handleUpdateClick(order.mwo_id)}
                        onMouseOver={(e) => { e.target.style.background = 'var(--accent-hover)'; e.target.style.transform = 'scale(1.02)'; }}
                        onMouseOut={(e) => { e.target.style.background = 'var(--accent)'; e.target.style.transform = 'scale(1)'; }}
                        style={{ padding: '6px 12px', cursor: 'pointer', backgroundColor: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '6px', transition: 'all 0.2s', fontWeight: '500' }}
                      >
                        Update Work Order
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TechDashboard;
