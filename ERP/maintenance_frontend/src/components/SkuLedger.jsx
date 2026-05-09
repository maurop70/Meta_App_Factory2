import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './EnterpriseDataMatrix.css';
import SkuCreationModal from './SkuCreationModal';

const SkuLedger = () => {
  const [skus, setSkus] = useState([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showIngestionModal, setShowIngestionModal] = useState(false);

  const fetchSkus = async () => {
    let isMounted = true;
    try {
      setLoading(true);
      setError(null);
      const response = await api.get('/inventory/skus');
      if (isMounted) {
        setSkus(Array.isArray(response.data.items) ? response.data.items : []);
        setTotalRecords(response.data.total || 0);
      }
    } catch (err) {
      if (isMounted) {
        // Handle 404 cleanly since the backend might not have this route fully seeded
        if (err.response?.status === 404) {
          setSkus([]);
          setError("Endpoint /inventory/skus not found. Backend synchronization pending.");
        } else {
          setError("Failed to fetch SKU ledger. Connection or RBAC error.");
        }
        console.error("SKU Fetch Error:", err);
      }
    } finally {
      if (isMounted) setLoading(false);
    }
    return () => { isMounted = false; };
  };

  useEffect(() => {
    const teardown = fetchSkus();
    return () => teardown.then(t => t && t());
  }, []);

  const getStockBadge = (qty, threshold) => {
    if (!qty || qty <= 0) return { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', label: 'DEPLETED' };
    if (qty <= threshold) return { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', label: 'CRITICAL LOW' };
    return { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', label: 'NOMINAL' };
  };

  return (
    <div className="parts-matrix-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>SKU Master Ledger</h2>
        <button
          onClick={() => setShowIngestionModal(true)}
          style={{
            padding: '0.6rem 1.4rem', 
            background: 'linear-gradient(135deg, #10b981, #059669)',
            color: '#fff', 
            border: 'none', 
            borderRadius: '8px', 
            cursor: 'pointer',
            fontWeight: 700, 
            fontSize: '0.85rem', 
            boxShadow: '0 4px 15px rgba(16, 185, 129, 0.25)',
            transition: 'all 0.2s', 
            textTransform: 'uppercase', 
            letterSpacing: '0.05em'
          }}
        >
          [+ Ingest New SKU]
        </button>
      </div>

      {error && <div className="matrix-error-msg">{error}</div>}

      {loading ? (
        <div className="matrix-status-msg">Synchronizing SKU ledger...</div>
      ) : (
        <table className="erp-data-matrix">
          <thead>
            <tr>
              <th>SKU ID</th>
              <th>Nomenclature</th>
              <th>Unit Cost</th>
              <th>Reorder Threshold</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {skus.length === 0 ? (
              <tr>
                <td colSpan="5" className="matrix-status-msg">No SKUs present in the ledger matrix.</td>
              </tr>
            ) : (
              skus.map((sku) => {
                const stock = getStockBadge(sku.quantity_on_hand, sku.reorder_threshold);
                return (
                  <tr key={sku.sku_id}>
                    <td data-label="SKU ID"><span className="badge badge-role">{sku.sku_id}</span></td>
                    <td data-label="Nomenclature">{sku.nomenclature}</td>
                    <td data-label="Unit Cost">${sku.unit_cost?.toFixed(2) || '0.00'}</td>
                    <td data-label="Reorder Threshold">{sku.reorder_threshold}</td>
                    <td data-label="Status">
                      <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.65rem', fontWeight: 600, background: stock.bg, color: stock.color }}>
                        {stock.label}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      )}

      {showIngestionModal && (
        <SkuCreationModal
          closeModal={() => setShowIngestionModal(false)}
          onIngestionSuccess={() => fetchSkus()}
        />
      )}
    </div>
  );
};

export default SkuLedger;
