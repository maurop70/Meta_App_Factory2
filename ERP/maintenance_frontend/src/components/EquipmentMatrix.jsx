import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './EnterpriseDataMatrix.css';
import EquipmentDetailModal from './EquipmentDetailModal';

const EquipmentMatrix = () => {
  const [equipment, setEquipment] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Pagination State
  const [page, setPage] = useState(0);
  const LIMIT = 50;
  
  // Modal State
  const [selectedEquipment, setSelectedEquipment] = useState(null);

  const fetchEquipment = async () => {
    let isMounted = true;
    try {
      setLoading(true);
      setError(null);
      const response = await api.get(`/admin/equipment?limit=${LIMIT}&offset=${page * LIMIT}`);
      if (isMounted) {
        setEquipment(response.data.data);
      }
    } catch (err) {
      if (isMounted) {
        setError("Failed to fetch equipment matrix. Connection or RBAC error.");
        console.error("Equipment Fetch Error:", err);
      }
    } finally {
      if (isMounted) setLoading(false);
    }
    return () => { isMounted = false; };
  };

  useEffect(() => {
    const teardown = fetchEquipment();
    return () => teardown.then(t => t && t());
  }, [page]);

  const handleNextPage = () => setPage(p => p + 1);
  const handlePrevPage = () => setPage(p => Math.max(0, p - 1));

  const handleEquipmentClick = (eq) => {
    setSelectedEquipment(eq);
  };

  const handleModalClose = (wasUpdated) => {
    setSelectedEquipment(null);
    if (wasUpdated) {
      fetchEquipment();
    }
  };

  return (
    <div className="equipment-matrix-container">
      <h2>Enterprise Equipment Matrix</h2>
      
      {error && <div className="matrix-error-msg">{error}</div>}
      
      {loading ? (
        <div className="matrix-status-msg">Synchronizing equipment ledger...</div>
      ) : (
        <>
          <table className="erp-data-matrix">
            <thead>
              <tr>
                <th>Equipment ID</th>
                <th>Nomenclature</th>
                <th>Category</th>
                <th>Department</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {equipment.length === 0 ? (
                <tr>
                  <td colSpan="6" className="matrix-status-msg">No equipment found in the current viewport.</td>
                </tr>
              ) : (
                equipment.map((eq) => (
                  <tr key={eq.equipment_id}>
                    <td data-label="Equipment ID"><span className="badge badge-role">{eq.equipment_id}</span></td>
                    <td data-label="Nomenclature">{eq.nomenclature}</td>
                    <td data-label="Category">{eq.category}</td>
                    <td data-label="Department">{eq.department}</td>
                    <td data-label="Status">
                      <span className={`badge ${eq.status === 'ACTIVE' ? 'badge-status' : ''}`} style={{
                        background: eq.status === 'DEGRADED' ? 'rgba(245, 158, 11, 0.15)' : eq.status === 'OFFLINE' ? 'rgba(239, 68, 68, 0.15)' : '',
                        color: eq.status === 'DEGRADED' ? '#f59e0b' : eq.status === 'OFFLINE' ? '#ef4444' : ''
                      }}>
                        {eq.status}
                      </span>
                    </td>
                    <td data-label="Action">
                      <button 
                        onClick={() => handleEquipmentClick(eq)}
                        style={{
                          background: 'transparent',
                          border: '1px solid var(--border, rgba(99, 102, 241, 0.5))',
                          color: '#e2e8f0',
                          padding: '0.4rem 0.8rem',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          textTransform: 'uppercase',
                          fontSize: '0.75rem',
                          fontWeight: '600'
                        }}
                      >
                        ACTUATE
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          
          <div className="matrix-pagination">
            <button onClick={handlePrevPage} disabled={page === 0 || loading}>
              Previous
            </button>
            <span>Page {page + 1}</span>
            <button onClick={handleNextPage} disabled={equipment.length < LIMIT || loading}>
              Next
            </button>
          </div>
        </>
      )}

      {selectedEquipment && (
        <EquipmentDetailModal 
          equipment={selectedEquipment} 
          onClose={handleModalClose} 
        />
      )}
    </div>
  );
};

export default EquipmentMatrix;
