import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './EnterpriseDataMatrix.css';
import SkuCreationModal from './SkuCreationModal';
import SupplierCreationModal from './SupplierCreationModal';
import { useAuth } from '../context/AuthContext';

const SkuLedger = () => {
  const { userRole } = useAuth();
  // HOD operators (HM) manage the catalog alongside administrators
  const canIngest = ['ADMINISTRATOR', 'ADMIN', 'HM'].includes(userRole);
  const [skus, setSkus] = useState([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showIngestionModal, setShowIngestionModal] = useState(false);
  const [showSupplierModal, setShowSupplierModal] = useState(false);
  const [suppliers, setSuppliers] = useState([]);
  const [selectedSkuForEdit, setSelectedSkuForEdit] = useState(null);

  const fetchSuppliers = async () => {
    try {
      const response = await api.get('/inventory/suppliers');
      setSuppliers(response.data.data || []);
    } catch (err) {
      console.warn('Supplier directory fetch failed.', err);
    }
  };

  useEffect(() => {
    if (canIngest) fetchSuppliers();
  }, [canIngest]);

  const reassignSupplier = async (skuId, supplierId) => {
    try {
      setError(null);
      setSuccess(null);
      await api.put(`/inventory/skus/${skuId}/supplier`, { supplier_id: supplierId || null });
      const sup = suppliers.find(s => s.supplier_id === supplierId);
      const supplierName = sup ? sup.name : 'Unassigned';
      setSuccess(`SKU ${skuId} successfully reassigned to ${supplierName}.`);
      setTimeout(() => setSuccess(null), 4000);
      await fetchSkus();
    } catch (err) {
      console.error('Supplier reassignment failed:', err);
      setError(err.response?.data?.detail || 'Supplier reassignment failed.');
      setSuccess(null);
    }
  };

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
        {canIngest && (
          <div style={{ display: 'flex', gap: '0.7rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => setShowSupplierModal(true)}
              style={{
                padding: '0.6rem 1.4rem',
                background: 'rgba(16, 185, 129, 0.12)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '0.85rem',
                transition: 'all 0.2s',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}
            >
              [+ Register New Supplier]
            </button>
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
        )}
      </div>

      {error && <div className="matrix-error-msg">{error}</div>}
      {success && (
        <div style={{ marginBottom: '1rem', padding: '0.6rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
          {success}
        </div>
      )}

      {loading ? (
        <div className="matrix-status-msg">Synchronizing SKU ledger...</div>
      ) : (
        <table className="erp-data-matrix">
          <thead>
            <tr>
              <th>SKU ID</th>
              <th>Nomenclature</th>
              <th>Supplier</th>
              <th>Unit Cost</th>
              <th>Qty On Hand</th>
              <th>Reorder Threshold</th>
              <th>Min Order Qty</th>
              <th>Status</th>
              {canIngest && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {skus.length === 0 ? (
              <tr>
                <td colSpan={canIngest ? 9 : 8} className="matrix-status-msg">No SKUs present in the ledger matrix.</td>
              </tr>
            ) : (
              skus.map((sku) => {
                const stock = getStockBadge(sku.quantity_on_hand, sku.reorder_threshold);
                return (
                  <tr key={sku.sku_id}>
                    <td data-label="SKU ID"><span className="badge badge-role">{sku.sku_id}</span></td>
                    <td data-label="Nomenclature">{sku.nomenclature}</td>
                    <td data-label="Supplier" style={{ color: sku.supplier_name ? '#94a3b8' : '#475569' }}>
                      {canIngest ? (
                        <select
                          value={sku.supplier_id || ''}
                          onChange={e => reassignSupplier(sku.sku_id, e.target.value)}
                          style={{ background: 'rgba(15, 23, 42, 0.6)', color: sku.supplier_id ? '#94a3b8' : '#475569', border: '1px solid rgba(99, 102, 241, 0.2)', borderRadius: '6px', padding: '0.3rem 0.4rem', fontSize: '0.78rem', fontFamily: 'inherit', cursor: 'pointer', outline: 'none', maxWidth: '180px' }}
                        >
                          <option value="">Unassigned</option>
                          {suppliers.map(s => (
                            <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>
                          ))}
                        </select>
                      ) : (
                        sku.supplier_name || 'Unassigned'
                      )}
                    </td>
                    <td data-label="Unit Cost">${sku.unit_cost?.toFixed(2) || '0.00'}</td>
                    <td data-label="Qty On Hand" style={{ fontWeight: 700, color: stock.color }}>{sku.quantity_on_hand ?? 0}</td>
                    <td data-label="Reorder Threshold">{sku.reorder_threshold}</td>
                    <td data-label="Min Order Qty" style={{ color: (sku.min_order_qty || 1) > 1 ? '#fbbf24' : '#64748b', fontWeight: (sku.min_order_qty || 1) > 1 ? 600 : 400 }}>
                      {sku.min_order_qty || 1}
                    </td>
                    <td data-label="Status">
                      <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.65rem', fontWeight: 600, background: stock.bg, color: stock.color }}>
                        {stock.label}
                      </span>
                    </td>
                    {canIngest && (
                      <td data-label="Action">
                        <button
                          onClick={() => setSelectedSkuForEdit(sku)}
                          style={{ padding: '0.3rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(99, 102, 241, 0.35)', background: 'rgba(99, 102, 241, 0.12)', color: '#818cf8', cursor: 'pointer', fontWeight: 700, fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}
                        >
                          Edit
                        </button>
                      </td>
                    )}
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
          onIngestionSuccess={() => { fetchSkus(); fetchSuppliers(); }}
        />
      )}

      {selectedSkuForEdit && (
        <SkuCreationModal
          editSku={selectedSkuForEdit}
          closeModal={() => setSelectedSkuForEdit(null)}
          onIngestionSuccess={() => { fetchSkus(); fetchSuppliers(); }}
        />
      )}

      {showSupplierModal && (
        <SupplierCreationModal
          closeModal={() => setShowSupplierModal(false)}
          onRegistrationSuccess={() => { fetchSkus(); fetchSuppliers(); }}
        />
      )}
    </div>
  );
};

export default SkuLedger;
