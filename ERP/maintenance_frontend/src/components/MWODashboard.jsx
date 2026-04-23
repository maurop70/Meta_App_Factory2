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
    <div className="erp-dashboard-section" style={{ marginTop: '20px' }}>
      <h3>Active Work Orders</h3>
      <div style={{ overflowX: 'auto' }}>
        <table className="erp-data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #333' }}>
              <th>MWO ID</th>
              <th>Status</th>
              <th>DM Urgency</th>
              <th>HM Priority</th>
              <th>Description</th>
              <th>Assigned Tech</th>
              <th>Consumed SKU</th>
              <th>Manual Log</th>
              {userRole === 'HM (Admin)' && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan={userRole === 'HM (Admin)' ? "9" : "8"} style={{ textAlign: 'center', padding: '15px' }}>No work orders found.</td>
              </tr>
            ) : (
              workOrders.map((order, idx) => (
                <tr key={order.mwo_id || idx} style={{ borderBottom: '1px solid #444' }}>
                  <td>{order.mwo_id || 'N/A'}</td>
                  <td>{order.status || 'Pending'}</td>
                  <td>{order.dm_urgency || 'Normal'}</td>
                  <td>{order.hm_priority || 'Normal'}</td>
                  <td>{order.description || 'N/A'}</td>
                  <td>{order.assigned_tech || 'Unassigned'}</td>
                  <td>{order.consumed_sku || 'None'}</td>
                  <td>{order.manual_log || 'None'}</td>
                  {userRole === 'HM (Admin)' && (
                    <td>
                      {order.status === 'PENDING_REVIEW' && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => handleComplete(order.mwo_id)}
                            style={{ padding: '6px 12px', cursor: 'pointer', backgroundColor: '#28a745', color: '#fff', border: 'none', borderRadius: '4px' }}
                          >
                            Approve & Complete
                          </button>
                          <button
                            onClick={() => handleReject(order.mwo_id)}
                            style={{ padding: '6px 12px', cursor: 'pointer', backgroundColor: '#dc3545', color: '#fff', border: 'none', borderRadius: '4px' }}
                          >
                            Reject & Return
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
