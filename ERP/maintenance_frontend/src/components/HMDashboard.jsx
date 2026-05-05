import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import HMAssignmentModal from './HMAssignmentModal';
import HMReviewModal from './HMReviewModal';
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

  if (status.type === 'loading') {
    return <div className="erp-status-message loading">{status.message}</div>;
  }

  if (status.type === 'error') {
    return <div className="erp-status-message error">{status.message}</div>;
  }

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
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
              <th>Assigned Tech</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {unassignedOrders.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No active work orders in queue.</td>
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
