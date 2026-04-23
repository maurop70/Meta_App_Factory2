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
        
        // Edge Node Filter: Strictly render ASSIGNED or IN_PROGRESS and assigned to active persona
        const activeTechOrders = allOrders.filter(
          order => (order.status === 'ASSIGNED' || order.status === 'IN_PROGRESS') && order.assigned_tech === userRole
        );
        
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
    
    // Defensive payload merge
    const payload = {
      status: localUpdates.status || originalOrder.status,
      consumed_sku: localUpdates.consumed_sku !== undefined ? localUpdates.consumed_sku : (originalOrder.consumed_sku || ""),
      manual_log: localUpdates.manual_log !== undefined ? localUpdates.manual_log : (originalOrder.manual_log || "")
    };

    try {
      await api.patch(`/api/mwo/${mwo_id}`, payload);
      alert(`Work order ${mwo_id} successfully updated.`);
      setFetchTrigger(prev => prev + 1);
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

  return (
    <div className="erp-dashboard-section" style={{ marginTop: '20px' }}>
      <h3>Technician Edge Node - Active Tasks</h3>
      <div style={{ overflowX: 'auto' }}>
        <table className="erp-data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #333' }}>
              <th>MWO ID</th>
              <th>Task Description</th>
              <th>Current Status</th>
              <th>Update Status</th>
              <th>Consumed SKU</th>
              <th>Manual Log</th>
              <th>Action</th>
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
                  <tr key={order.mwo_id || idx} style={{ 
                    borderBottom: '1px solid #444',
                    borderLeft: isRework ? '4px solid #dc3545' : 'none',
                    backgroundColor: isRework ? '#3a1c1d' : 'transparent'
                  }}>
                    <td>{order.mwo_id || 'N/A'}</td>
                    <td>{order.description || 'N/A'}</td>
                    <td>
                      {isRework ? (
                        <span style={{ color: '#dc3545', fontWeight: 'bold' }}>IN PROGRESS (REWORK REQUIRED)</span>
                      ) : (
                        order.status
                      )}
                    </td>
                    
                    {/* Read/Write Matrix: Restricted Status Dropdown */}
                    <td>
                      <select 
                        value={currentUpdateStatus === 'ASSIGNED' ? "" : currentUpdateStatus}
                        onChange={(e) => handleInputChange(order.mwo_id, 'status', e.target.value)}
                        style={{ padding: '5px', width: '140px' }}
                      >
                        <option value="" disabled>Select Action</option>
                        {/* Only allow valid state transitions from the Edge Node */}
                        <option value="IN_PROGRESS">IN_PROGRESS</option>
                        <option value="PENDING_REVIEW">PENDING_REVIEW</option>
                      </select>
                    </td>

                    {/* Read/Write Matrix: SKU Input */}
                    <td>
                      <input 
                        type="text" 
                        placeholder="Enter SKU..."
                        defaultValue={order.consumed_sku || ''}
                        onChange={(e) => handleInputChange(order.mwo_id, 'consumed_sku', e.target.value)}
                        style={{ padding: '5px', width: '120px' }}
                      />
                    </td>

                    {/* Read/Write Matrix: Manual Log Input */}
                    <td>
                      <textarea 
                        placeholder="Enter diagnostic/resolution log..."
                        defaultValue={order.manual_log || ''}
                        onChange={(e) => handleInputChange(order.mwo_id, 'manual_log', e.target.value)}
                        style={{ padding: '5px', width: '200px', resize: 'vertical' }}
                      />
                    </td>

                    {/* Submit Actuator */}
                    <td>
                      <button 
                        onClick={() => handleUpdateClick(order.mwo_id)}
                        style={{ padding: '6px 12px', cursor: 'pointer', backgroundColor: '#0056b3', color: '#fff', border: 'none', borderRadius: '4px' }}
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
