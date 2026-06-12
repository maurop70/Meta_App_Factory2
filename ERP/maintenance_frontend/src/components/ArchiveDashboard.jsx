import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const ArchiveDashboard = () => {
  const [archives, setArchives] = useState([]);
  const [status, setStatus] = useState({ type: 'loading', message: 'Loading Archives...' });
  const navigate = useNavigate();

  useEffect(() => {
    const fetchArchives = async () => {
      try {
        const response = await api.get('/mwo/archive/list');
        setArchives(response.data.data || []);
        setStatus({ type: 'success', message: '' });
      } catch (err) {
        console.error("Failed to fetch archives", err);
        setStatus({ type: 'error', message: 'Failed to connect to backend or unauthorized.' });
      }
    };
    fetchArchives();
  }, []);

  const formatDate = (dateVal) => {
    if (!dateVal) return 'N/A';
    const parsedNum = Number(dateVal);
    if (!isNaN(parsedNum) && parsedNum > 0) {
      const ms = parsedNum < 1e11 ? parsedNum * 1000 : parsedNum;
      return new Date(ms).toLocaleString();
    }
    const d = new Date(dateVal);
    return isNaN(d.getTime()) ? 'Invalid Date' : d.toLocaleString();
  };

  const handleDownloadPDF = async (mwo_id) => {
    try {
      const response = await api.get(`/mwo/${mwo_id}/archive`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ARCHIVE_${mwo_id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download PDF", err);
      alert("Failed to download PDF. Please check permissions or try again.");
    }
  };

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)", maxWidth: '1200px', margin: '0 auto', textAlign: 'left' }}>
      
      <style>{`
        .responsive-matrix {
          width: 100%;
          text-align: left;
          border-collapse: collapse;
          font-size: 0.85rem;
        }
        .responsive-matrix th {
          padding: 1rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          font-size: 0.75rem;
          color: #94a3b8;
          background: rgba(99, 102, 241, 0.1);
          border-bottom: 1px solid rgba(99, 102, 241, 0.15);
        }
        .responsive-matrix td {
          padding: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          color: #e2e8f0;
        }
        .btn-inspect {
          background: rgba(99, 102, 241, 0.15);
          color: #818cf8;
          border: 1px solid rgba(99, 102, 241, 0.3);
          padding: 0.4rem 0.8rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.75rem;
          font-weight: 700;
          transition: all 0.2s;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          text-decoration: none;
          display: inline-block;
        }
        .btn-inspect:hover {
          background: var(--accent-purple, #8b5cf6);
          color: #fff;
        }
      `}</style>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', color: '#e2e8f0', margin: 0 }}>Archived Work Orders</h2>
          <p style={{ margin: '0.3rem 0 0 0', color: '#94a3b8', fontSize: '0.9rem' }}>Historical records of completed maintenance tasks.</p>
        </div>
        <button 
          onClick={() => navigate('/')} 
          style={{ padding: '0.6rem 1.2rem', background: 'rgba(255, 255, 255, 0.05)', color: '#e2e8f0', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem', transition: 'all 0.2s' }}
        >
          &larr; Back to Dashboard
        </button>
      </div>

      {status.type === 'loading' && <div style={{ color: '#94a3b8', padding: '2rem', textAlign: 'center' }}>{status.message}</div>}
      {status.type === 'error' && <div style={{ color: '#ef4444', padding: '2rem', textAlign: 'center' }}>{status.message}</div>}

      {status.type === 'success' && (
        archives.length > 0 ? (
          <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', background: 'rgba(10, 14, 23, 0.5)' }}>
            <table className="responsive-matrix">
              <thead>
                <tr>
                  <th>MWO ID</th>
                  <th>Equipment</th>
                  <th>Completed At</th>
                  <th>Description</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {archives.map(order => (
                  <tr key={order.mwo_id}>
                    <td style={{ fontWeight: 600, color: '#818cf8' }}>{order.mwo_id}</td>
                    <td>{order.equipment_nomenclature || order.equipment_id}</td>
                    <td>{formatDate(order.completed_at)}</td>
                    <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{order.description}</td>
                    <td>
                      <button 
                        onClick={() => handleDownloadPDF(order.mwo_id)}
                        className="btn-inspect"
                        style={{ border: 'none', cursor: 'pointer' }}
                      >
                        Download PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '3rem', textAlign: 'center', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', color: '#64748b' }}>
            No archived work orders found.
          </div>
        )
      )}
    </div>
  );
};

export default ArchiveDashboard;
