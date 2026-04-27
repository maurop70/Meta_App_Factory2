import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';

const TechDashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Work Orders...' });
  const [updates, setUpdates] = useState({});
  const { userRole } = useAuth();
  
  // Assume Tech-Alpha is the active mock identity for strict data isolation
  const activeTech = 'Tech-Alpha';

  useEffect(() => {
    const fetchMWO = async () => {
      try {
        const response = await axios.get('/api/mwo');
        const dbPayload = response.data.data;
        
        // Strict Data Isolation: Filter active state to assigned_tech and hide PENDING_ASSIGNMENT
        const filtered = dbPayload.filter(order => 
          order.assigned_tech === activeTech && 
          order.status !== 'PENDING_ASSIGNMENT'
        );
        
        setWorkOrders(filtered);
        setStatus({ type: 'success', message: '' });
      } catch (err) {
        console.warn("Network fragmentation detected.", err);
        setStatus({ type: 'error', message: 'Failed to connect to backend' });
      }
    };
    
    fetchMWO();
  }, [activeTech]);

  const handleLogChange = (mwo_id, val) => {
    setUpdates(prev => ({ ...prev, [mwo_id]: val }));
  };

  const handleStartWork = async (mwo_id) => {
    const originalState = [...workOrders];
    
    // Optimistic mutation to IN_PROGRESS
    setWorkOrders(prev => prev.map(order => {
      if (order.mwo_id === mwo_id) {
        return { ...order, status: 'IN_PROGRESS' };
      }
      return order;
    }));
    
    try {
      await axios.patch('/api/mwo/' + mwo_id, { status: 'IN_PROGRESS' });
    } catch (err) {
      console.error("Backend patch failed. Reverting local state.", err);
      setWorkOrders(originalState);
    }
  };

  const handleCompleteWork = async (mwo_id) => {
    const currentLogInputValue = updates[mwo_id] || '';
    const originalState = [...workOrders];
    
    // Optimistic mutation to PENDING_REVIEW
    setWorkOrders(prev => prev.map(order => {
      if (order.mwo_id === mwo_id) {
        return { ...order, status: 'PENDING_REVIEW', manual_log: currentLogInputValue };
      }
      return order;
    }));
    
    try {
      await axios.patch('/api/mwo/' + mwo_id, { status: 'PENDING_REVIEW', manual_log: currentLogInputValue });
    } catch (err) {
      console.error("Backend patch failed. Reverting local state.", err);
      setWorkOrders(originalState);
    }
  };

  const handleUndoWork = async (mwo_id) => {
    const currentLogInputValue = updates[mwo_id] || '';
    const originalState = [...workOrders];
    
    // Optimistic mutation back to IN_PROGRESS
    setWorkOrders(prev => prev.map(order => {
      if (order.mwo_id === mwo_id) {
        return { ...order, status: 'IN_PROGRESS', manual_log: currentLogInputValue };
      }
      return order;
    }));
    
    try {
      await axios.patch('/api/mwo/' + mwo_id, { status: 'IN_PROGRESS', manual_log: currentLogInputValue });
    } catch (err) {
      console.error("Backend patch failed. Reverting local state.", err);
      setWorkOrders(originalState);
    }
  };

  if (status.type === 'loading') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error') {
    return <div className="erp-status-message error">{status.message}</div>;
  }

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
      {/* Mobile-First CSS Reflow */}
      <style>{`
        .btn-action {
          background: rgba(59, 130, 246, 0.15);
          color: #60a5fa;
          border: 1px solid rgba(59, 130, 246, 0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.7rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        .btn-action:hover {
          background: var(--accent, #3b82f6);
          color: #fff;
        }
        .log-input {
          width: 100%;
          min-width: 150px;
          padding: 0.4rem 0.5rem;
          border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          background: rgba(255, 255, 255, 0.04);
          color: var(--text-primary, #e2e8f0);
          font-size: 0.75rem;
          outline: none;
          transition: border-color 0.2s;
        }
        .log-input:focus {
          border-color: #6366f1;
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
        }
      `}</style>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', margin: 0 }}>Active Assignments - Tech Edge</h3>
      </div>
      
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: 'rgba(99, 102, 241, 0.1)', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>MWO ID</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Status</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>DM Urgency</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Description</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Manual Log</th>
              <th style={{ padding: '0.8rem 1rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No active assignments.</td>
              </tr>
            ) : (
              workOrders.map((order) => {
                const isPendingReview = order.status === 'PENDING_REVIEW';
                const currentLog = updates[order.mwo_id] !== undefined ? updates[order.mwo_id] : (order.manual_log || '');
                return (
                  <tr key={order.mwo_id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <td data-label="MWO ID" style={{ padding: '1rem 1.2rem', color: '#818cf8', fontWeight: 500 }}>
                      {order.mwo_id}
                    </td>
                    <td data-label="STATUS" style={{ padding: '1rem 1.2rem' }}>
                      <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, background: isPendingReview ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)', color: isPendingReview ? 'var(--warning, #f59e0b)' : 'var(--accent, #3b82f6)' }}>
                        {order.status}
                      </span>
                    </td>
                    <td data-label="DM URGENCY" style={{ padding: '1rem 1.2rem', color: '#e2e8f0' }}>
                      <span style={{ padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', whiteSpace: 'nowrap', fontWeight: 600, background: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(148, 163, 184, 0.15)', color: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? '#fbbf24' : '#94a3b8' }}>
                        {order.dm_urgency || 'Normal'}
                      </span>
                    </td>
                    <td data-label="DESCRIPTION" style={{ padding: '1rem 1.2rem', color: '#e2e8f0' }}>
                      {order.description}
                    </td>
                    <td data-label="MANUAL LOG" style={{ padding: '1rem 1.2rem' }}>
                      <textarea 
                        className="log-input"
                        placeholder="Enter repair log..."
                        value={currentLog}
                        onChange={(e) => handleLogChange(order.mwo_id, e.target.value)}
                        disabled={isPendingReview}
                        style={{ 
                          minHeight: '40px', 
                          resize: 'vertical',
                          opacity: isPendingReview ? 0.5 : 1,
                          cursor: isPendingReview ? 'not-allowed' : 'text'
                        }}
                      />
                    </td>
                    <td data-label="ACTION" style={{ padding: '1rem 1.2rem' }}>
                      {order.status === 'ASSIGNED' && (
                        <button 
                          className="btn-action" 
                          onClick={() => handleStartWork(order.mwo_id)}
                        >
                          Start Work
                        </button>
                      )}
                      {order.status === 'IN_PROGRESS' && (
                        <button 
                          className="btn-action" 
                          onClick={() => handleCompleteWork(order.mwo_id)}
                        >
                          Complete Work
                        </button>
                      )}
                      {order.status === 'PENDING_REVIEW' && (
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', justifyContent: 'flex-end' }}>
                          <span style={{ color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic' }}>Review Pending</span>
                          <button 
                            className="btn-action" 
                            style={{ background: 'transparent', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444' }}
                            onClick={() => handleUndoWork(order.mwo_id)}
                          >
                            Undo
                          </button>
                        </div>
                      )}
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
