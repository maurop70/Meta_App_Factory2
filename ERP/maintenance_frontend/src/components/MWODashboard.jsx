import React, { useState, useEffect } from 'react';
import api from '../services/api';

const MWODashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });

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
  }, []);

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
              <th>Priority</th>
              <th>Description</th>
              <th>Technician</th>
              <th>Consumed SKU</th>
              <th>Manual Log</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '15px' }}>No work orders found.</td>
              </tr>
            ) : (
              workOrders.map((order, idx) => (
                <tr key={order.id || order.mwo_id || idx} style={{ borderBottom: '1px solid #444' }}>
                  <td>{order.mwo_id || order.id || 'N/A'}</td>
                  <td>{order.status || 'Pending'}</td>
                  <td>{order.priority || 'Normal'}</td>
                  <td>{order.description || 'N/A'}</td>
                  <td>{order.technician || order.assigned_tech || 'Unassigned'}</td>
                  <td>{order.consumed_sku || order.sku || 'None'}</td>
                  <td>{order.manual_log || order.log || 'None'}</td>
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
