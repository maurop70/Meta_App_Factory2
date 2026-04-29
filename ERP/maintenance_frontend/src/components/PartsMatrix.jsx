import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './EnterpriseDataMatrix.css';
import PartIngestionModal from './PartIngestionModal';

const PartsMatrix = () => {
  const [parts, setParts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const LIMIT = 50;
  const [showIngestionModal, setShowIngestionModal] = useState(false);

  const fetchParts = async () => {
    let isMounted = true;
    try {
      setLoading(true);
      setError(null);
      const response = await api.get(`/admin/parts?limit=${LIMIT}&offset=${page * LIMIT}`);
      if (isMounted) {
        setParts(response.data.data || []);
      }
    } catch (err) {
      if (isMounted) {
        setError("Failed to fetch parts matrix. Connection or RBAC error.");
        console.error("Parts Fetch Error:", err);
      }
    } finally {
      if (isMounted) setLoading(false);
    }
    return () => { isMounted = false; };
  };

  useEffect(() => {
    const teardown = fetchParts();
    return () => teardown.then(t => t && t());
  }, [page]);

  const handleNextPage = () => setPage(p => p + 1);
  const handlePrevPage = () => setPage(p => Math.max(0, p - 1));

  const getStockBadge = (qty, threshold) => {
    if (qty <= 0) return { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', label: 'OUT OF STOCK' };
    if (qty <= threshold) return { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', label: 'LOW STOCK' };
    return { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', label: 'IN STOCK' };
  };

  return (
    <div className="parts-matrix-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Master Parts Catalog</h2>
        <button
          onClick={() => setShowIngestionModal(true)}
          style={{
            padding: '0.5rem 1.2rem', background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
            color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer',
            fontWeight: 700, fontSize: '0.8rem', boxShadow: '0 4px 15px rgba(99, 102, 241, 0.25)',
            transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '0.05em'
          }}
        >
          + Ingest Part
        </button>
      </div>

      {error && <div className="matrix-error-msg">{error}</div>}

      {loading ? (
        <div className="matrix-status-msg">Synchronizing parts ledger...</div>
      ) : (
        <>
          <table className="erp-data-matrix">
            <thead>
              <tr>
                <th>Part ID</th>
                <th>Nomenclature</th>
                <th>Category</th>
                <th>Qty On Hand</th>
                <th>Reorder Threshold</th>
                <th>Unit Cost</th>
              </tr>
            </thead>
            <tbody>
              {parts.length === 0 ? (
                <tr>
                  <td colSpan="6" className="matrix-status-msg">No parts found in the master catalog.</td>
                </tr>
              ) : (
                parts.map((part) => {
                  const stock = getStockBadge(part.quantity_on_hand, part.reorder_threshold);
                  return (
                    <tr key={part.part_id}>
                      <td data-label="Part ID"><span className="badge badge-role">{part.part_id}</span></td>
                      <td data-label="Nomenclature">{part.nomenclature}</td>
                      <td data-label="Category">{part.category}</td>
                      <td data-label="Qty On Hand">
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                          <strong style={{ color: '#e2e8f0' }}>{part.quantity_on_hand}</strong>
                          <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.65rem', fontWeight: 600, background: stock.bg, color: stock.color }}>
                            {stock.label}
                          </span>
                        </span>
                      </td>
                      <td data-label="Reorder Threshold">{part.reorder_threshold}</td>
                      <td data-label="Unit Cost">${part.unit_cost.toFixed(2)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>

          <div className="matrix-pagination">
            <button onClick={handlePrevPage} disabled={page === 0 || loading}>Previous</button>
            <span>Page {page + 1}</span>
            <button onClick={handleNextPage} disabled={parts.length < LIMIT || loading}>Next</button>
          </div>
        </>
      )}

      {showIngestionModal && (
        <PartIngestionModal
          closeModal={() => setShowIngestionModal(false)}
          onIngestionSuccess={() => fetchParts()}
        />
      )}
    </div>
  );
};

export default PartsMatrix;
