import React, { useEffect, useState } from 'react';
import api from '../services/api';
import './EnterpriseDataMatrix.css';
import UserDetailModal from './UserDetailModal';

const EnterpriseDataMatrix = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Enforce baseline pagination state
  const [page, setPage] = useState(1);
  const [limit] = useState(50); 
  
  const [inspectUserId, setInspectUserId] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0); // Orchestration trigger

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    
    const fetchEnterpriseData = async () => {
      try {
        const response = await api.get(`/admin/users?page=${page}&limit=${limit}`);
        if (isMounted) {
          setUsers(response.data);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.response?.data?.detail || err.message || 'Failed to fetch matrix.');
          setLoading(false);
        }
      }
    };
    
    fetchEnterpriseData();
    return () => { isMounted = false; };
  }, [page, limit, refreshTick]); // Add refreshTick to dependency array

  if (loading) return <div className="matrix-status-msg">Initializing Paginated Telemetry...</div>;
  if (error) return <div className="matrix-error-msg"><strong>Data Ingestion Failure:</strong> {error}</div>;

  return (
    <div style={{ width: '100%', marginTop: '2rem' }}>
      <h2 style={{ color: 'var(--text-primary, #e2e8f0)', fontSize: '1.25rem', marginBottom: '0.5rem', fontWeight: 600 }}>
        Enterprise Personnel Matrix
      </h2>
      <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
        Live organization hierarchy. Paginated rendering via SQLite backend.
      </p>

      <table className="erp-data-matrix">
        <thead>
          <tr>
            <th>User ID</th>
            <th>Personnel Name</th>
            <th>Taxonomy Role</th>
            <th>Department</th>
            <th>HM Reporting Vector</th>
            <th>System Status</th>
            <th style={{ textAlign: 'center' }}>Actuation</th>
          </tr>
        </thead>
        <tbody>
          {users.length === 0 ? (
            <tr>
              <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted, #64748b)' }}>
                No enterprise personnel records available.
              </td>
            </tr>
          ) : (
            users.map((user) => (
              <tr key={user.user_id}>
                <td data-label="User ID">{user.user_id}</td>
                <td data-label="Personnel Name">{user.name}</td>
                <td data-label="Taxonomy Role">
                  <span className="badge badge-role">{user.role}</span>
                </td>
                <td data-label="Department">{user.department}</td>
                <td data-label="HM Reporting Vector">{user.reports_to_hm_id || 'N/A'}</td>
                <td data-label="System Status">
                  <span className="badge badge-status">
                    <span className="status-dot"></span> ACTIVE
                  </span>
                </td>
                <td data-label="Actuation" style={{ textAlign: 'center' }}>
                  <button 
                    onClick={() => setInspectUserId(user.user_id)}
                    style={{
                      padding: '0.4rem 1rem', background: 'rgba(99, 102, 241, 0.15)',
                      color: 'var(--accent, #818cf8)', border: '1px solid rgba(99, 102, 241, 0.3)',
                      borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem'
                    }}
                  >
                    INSPECT
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      
      {/* Pagination Controls must be implemented here */}
      <div className="matrix-pagination">
         <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
         <span>Page {page}</span>
         <button disabled={users.length < limit} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>

      {inspectUserId && (
        <UserDetailModal 
          userId={inspectUserId} 
          onClose={() => setInspectUserId(null)} 
          onActuationSuccess={() => {
            setInspectUserId(null);
            setRefreshTick(prev => prev + 1); // Force matrix reconstruction
          }}
        />
      )}
    </div>
  );
};

export default EnterpriseDataMatrix;
