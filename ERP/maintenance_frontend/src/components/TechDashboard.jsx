import React, { useState, useEffect } from 'react';
import api from '../services/api';
import TechCompletionModal from './TechCompletionModal';
import TechConsumePartModal from './TechConsumePartModal';

const TechDashboard = () => {
  const [workOrders, setWorkOrders] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Assigned Work Orders...' });
  const [selectedMWO, setSelectedMWO] = useState(null);
  const [page, setPage] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [consumeMwoId, setConsumeMwoId] = useState(null);

  const executeArchiveRetrieval = async (mwoId) => {
    if (isDownloading) return; // Prevent race conditions
    
    try {
      setIsDownloading(true);
      
      // 1. Authenticated Blob Hydration
      const response = await api.get(`/mwo/${mwoId}/archive`, {
        responseType: 'blob' // CRITICAL: Bypass JSON parsing
      });

      // 2. Dynamic Memory Mount
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const downloadUrl = window.URL.createObjectURL(blob);

      // 3. Phantom DOM Actuation
      const phantomLink = document.createElement('a');
      phantomLink.href = downloadUrl;
      phantomLink.setAttribute('download', `ARCHIVE_${mwoId}.pdf`);
      document.body.appendChild(phantomLink);
      phantomLink.click();

      // 4. Synchronous Teardown & Memory Purge
      phantomLink.remove();
      window.URL.revokeObjectURL(downloadUrl);

    } catch (error) {
      console.error("Archive Retrieval Execution Error:", error);
      alert("Failed to retrieve structural archive. Verify RBAC clearance and file integrity.");
    } finally {
      setIsDownloading(false);
    }
  };

  const fetchAssignedMWO = async () => {
    try {
      const response = await api.get(`/mwo/assigned?limit=50&offset=${page * 50}`);
      const dbPayload = response.data.data || response.data;
      setWorkOrders(Array.isArray(dbPayload) ? dbPayload : []);
      setStatus({ type: 'success', message: '' });
    } catch (err) {
      console.warn("Network fragmentation detected.", err);
      setStatus({ type: 'error', message: 'Failed to connect to backend' });
    }
  };

  useEffect(() => {
    fetchAssignedMWO();
  }, [page]);

  const handleExecute = (mwo) => {
    setSelectedMWO(mwo);
  };

  const closeModal = () => {
    setSelectedMWO(null);
  };

  const executeCompletion = async (mwo_id, payload) => {
    await api.patch(`/mwo/${mwo_id}/complete`, payload);
    await fetchAssignedMWO();
  };

  if (status.type === 'loading') return <div className="erp-status-message loading">{status.message}</div>;
  if (status.type === 'error') return <div className="erp-status-message error">{status.message}</div>;

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(16, 185, 129, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)" }}>
      <style>{`
        .btn-execute {
          background: rgba(16, 185, 129, 0.15);
          color: #34d399;
          border: 1px solid rgba(16, 185, 129, 0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.7rem;
          font-weight: 600;
          transition: all 0.2s;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .btn-execute:hover {
          background: var(--accent-green, #10b981);
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
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', margin: 0 }}>My Active Assignments</h3>
      </div>
      
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(16, 185, 129, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
        <table className="responsive-matrix">
          <thead>
            <tr style={{ background: 'rgba(16, 185, 129, 0.1)', borderBottom: '1px solid var(--border, rgba(16, 185, 129, 0.15))', color: 'var(--text-secondary, #94a3b8)' }}>
              <th>MWO ID</th>
              <th>Status</th>
              <th>Equipment</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.length === 0 ? (
              <tr>
                <td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted, #64748b)' }}>No active assignments found.</td>
              </tr>
            ) : (
              workOrders.map((order) => (
                <tr key={order.mwo_id}>
                  <td data-label="MWO ID" style={{ color: '#34d399', fontWeight: 500 }}>
                    {order.mwo_id}
                  </td>
                  <td data-label="STATUS">
                    <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600, background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                      {order.status}
                    </span>
                  </td>
                  <td data-label="EQUIPMENT" style={{ color: '#e2e8f0' }}>
                    {order.equipment_id}
                  </td>
                  <td data-label="ACTION">
                    {order.status === 'COMPLETED' ? (
                      <button 
                        className="btn-execute" 
                        onClick={() => executeArchiveRetrieval(order.mwo_id)}
                        disabled={isDownloading}
                        style={{ background: isDownloading ? 'rgba(148, 163, 184, 0.15)' : 'rgba(99, 102, 241, 0.15)', color: isDownloading ? '#94a3b8' : '#818cf8', borderColor: isDownloading ? 'transparent' : 'rgba(99, 102, 241, 0.3)' }}
                      >
                        {isDownloading ? 'EXTRACTING...' : 'DOWNLOAD ARCHIVE'}
                      </button>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                        <button 
                          className="btn-execute" 
                          onClick={() => handleExecute(order)}
                        >
                          Execute
                        </button>
                        <button 
                          className="btn-execute" 
                          onClick={() => setConsumeMwoId(order.mwo_id)}
                          style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', borderColor: 'rgba(245, 158, 11, 0.3)' }}
                        >
                          Consume Part
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
        <button 
          onClick={() => setPage(p => Math.max(0, p - 1))}
          disabled={page === 0}
          style={{ padding: '0.5rem 1rem', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.5 : 1, transition: 'all 0.2s', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}
        >
          Previous
        </button>
        <span style={{ color: '#94a3b8', fontSize: '0.85rem', alignSelf: 'center', fontWeight: 600 }}>Page {page + 1}</span>
        <button 
          onClick={() => setPage(p => p + 1)}
          disabled={workOrders.length < 50}
          style={{ padding: '0.5rem 1rem', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', cursor: workOrders.length < 50 ? 'not-allowed' : 'pointer', opacity: workOrders.length < 50 ? 0.5 : 1, transition: 'all 0.2s', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}
        >
          Next
        </button>
      </div>

      {selectedMWO && (
        <TechCompletionModal 
          selectedMWO={selectedMWO} 
          closeModal={closeModal} 
          executeCompletion={executeCompletion}
        />
      )}

      <TechConsumePartModal
        isOpen={!!consumeMwoId}
        onClose={() => setConsumeMwoId(null)}
        mwoId={consumeMwoId}
        onConsumeSuccess={() => fetchAssignedMWO()}
      />
    </div>
  );
};

export default TechDashboard;
