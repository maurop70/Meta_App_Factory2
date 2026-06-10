import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const CREATE_NEW = '__CREATE_NEW_SUPPLIER__';

const SkuCreationModal = ({ closeModal, onIngestionSuccess }) => {
  const [formData, setFormData] = useState({
    sku_id: '',
    nomenclature: '',
    unit_cost: '',
    reorder_threshold: ''
  });

  const [suppliers, setSuppliers] = useState([]);
  const [supplierChoice, setSupplierChoice] = useState('');
  const [newSupplier, setNewSupplier] = useState({
    supplier_id: '',
    name: '',
    email: '',
    phone: '',
    address: '',
    default_lead_time_days: '7'
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.get('/inventory/suppliers')
      .then(res => { if (!cancelled) setSuppliers(res.data.data || []); })
      .catch(err => console.warn('Supplier directory fetch failed.', err));
    return () => { cancelled = true; };
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSupplierFieldChange = (e) => {
    const { name, value } = e.target;
    setNewSupplier(prev => ({ ...prev, [name]: value }));
  };

  const isInlineMode = supplierChoice === CREATE_NEW;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validate payload types
    const payload = {
      sku_id: formData.sku_id.trim(),
      nomenclature: formData.nomenclature.trim(),
      unit_cost: parseFloat(formData.unit_cost),
      reorder_threshold: parseInt(formData.reorder_threshold, 10),
      supplier_id: null
    };

    if (isNaN(payload.unit_cost) || isNaN(payload.reorder_threshold)) {
      setError("Unit cost and Reorder threshold must be numeric.");
      return;
    }

    if (isInlineMode) {
      if (newSupplier.supplier_id.trim().length < 2 || newSupplier.name.trim().length < 2) {
        setError("Supplier ID and Name are compulsory (min 2 characters).");
        return;
      }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(newSupplier.email.trim())) {
        setError("A valid supplier email address is compulsory (user@domain.tld).");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (isInlineMode) {
        // Atomic inline registration: supplier + SKU land in one backend
        // transaction — an SKU failure rolls the supplier back (no orphans).
        payload.new_supplier = {
          supplier_id: newSupplier.supplier_id.trim(),
          name: newSupplier.name.trim(),
          email: newSupplier.email.trim(),
          phone: newSupplier.phone.trim() || null,
          address: newSupplier.address.trim() || null,
          default_lead_time_days: parseInt(newSupplier.default_lead_time_days, 10) || 7
        };
      } else if (supplierChoice) {
        payload.supplier_id = supplierChoice;
      }

      const response = await api.post('/inventory/skus', payload);
      if (response.status === 201) {
        onIngestionSuccess();
        closeModal();
      } else {
        // Fallback for non-201 success if any, though mandate specifies 201
        onIngestionSuccess();
        closeModal();
      }
    } catch (err) {
      console.error("SKU Ingestion Error:", err);
      setError(err.response?.data?.detail || "Failed to ingest SKU. System error.");
      setIsSubmitting(false);
    }
  };

  const modalContent = (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h3 style={styles.title}>SKU INGESTION MATRIX</h3>
        </div>

        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>SKU ID</label>
            <input
              type="text"
              name="sku_id"
              value={formData.sku_id}
              onChange={handleInputChange}
              disabled={isSubmitting}
              required
              style={styles.input}
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Nomenclature</label>
            <input
              type="text"
              name="nomenclature"
              value={formData.nomenclature}
              onChange={handleInputChange}
              disabled={isSubmitting}
              required
              style={styles.input}
            />
          </div>

          <div style={styles.row}>
            <div style={{ ...styles.inputGroup, flex: 1 }}>
              <label style={styles.label}>Unit Cost ($)</label>
              <input
                type="number"
                step="0.01"
                name="unit_cost"
                value={formData.unit_cost}
                onChange={handleInputChange}
                disabled={isSubmitting}
                required
                style={styles.input}
              />
            </div>
            <div style={{ ...styles.inputGroup, flex: 1 }}>
              <label style={styles.label}>Reorder Threshold</label>
              <input
                type="number"
                name="reorder_threshold"
                value={formData.reorder_threshold}
                onChange={handleInputChange}
                disabled={isSubmitting}
                required
                style={styles.input}
              />
            </div>
          </div>

          {/* Supplier Association */}
          <div style={styles.inputGroup}>
            <label style={styles.label}>Supplier</label>
            <select
              value={supplierChoice}
              onChange={e => setSupplierChoice(e.target.value)}
              disabled={isSubmitting}
              style={{ ...styles.input, cursor: 'pointer' }}
            >
              <option value="">Select Supplier (Optional)</option>
              <option value={CREATE_NEW}>+ Create New Supplier...</option>
              {suppliers.map(s => (
                <option key={s.supplier_id} value={s.supplier_id}>
                  {s.name} ({s.supplier_id})
                </option>
              ))}
            </select>
          </div>

          {/* Inline Supplier Registration */}
          {isInlineMode && (
            <div style={styles.inlineBox}>
              <div style={styles.inlineTitle}>NEW SUPPLIER DETAILS</div>
              <div style={styles.row}>
                <div style={{ ...styles.inputGroup, flex: 1 }}>
                  <label style={styles.label}>Supplier ID *</label>
                  <input type="text" name="supplier_id" value={newSupplier.supplier_id} onChange={handleSupplierFieldChange}
                    disabled={isSubmitting} required={isInlineMode} minLength={2} maxLength={50} placeholder="SUP-..." style={styles.input} />
                </div>
                <div style={{ ...styles.inputGroup, flex: 1 }}>
                  <label style={styles.label}>Supplier Name *</label>
                  <input type="text" name="name" value={newSupplier.name} onChange={handleSupplierFieldChange}
                    disabled={isSubmitting} required={isInlineMode} minLength={2} maxLength={200} style={styles.input} />
                </div>
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Supplier Email *</label>
                <input type="email" name="email" value={newSupplier.email} onChange={handleSupplierFieldChange}
                  disabled={isSubmitting} required={isInlineMode} placeholder="orders@supplier.example.com" style={styles.input} />
              </div>
              <div style={styles.row}>
                <div style={{ ...styles.inputGroup, flex: 1 }}>
                  <label style={styles.label}>Phone</label>
                  <input type="tel" name="phone" value={newSupplier.phone} onChange={handleSupplierFieldChange}
                    disabled={isSubmitting} placeholder="Optional" style={styles.input} />
                </div>
                <div style={{ ...styles.inputGroup, width: '120px' }}>
                  <label style={styles.label}>Lead Time (D)</label>
                  <input type="number" name="default_lead_time_days" value={newSupplier.default_lead_time_days}
                    onChange={handleSupplierFieldChange} disabled={isSubmitting} min={0} max={365} style={styles.input} />
                </div>
              </div>
              <div style={{ ...styles.inputGroup, marginBottom: 0 }}>
                <label style={styles.label}>Address</label>
                <input type="text" name="address" value={newSupplier.address} onChange={handleSupplierFieldChange}
                  disabled={isSubmitting} placeholder="Optional" style={styles.input} />
              </div>
            </div>
          )}

          <div style={styles.footer}>
            <button
              type="button"
              onClick={closeModal}
              disabled={isSubmitting}
              style={styles.cancelBtn}
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{ ...styles.submitBtn, opacity: isSubmitting ? 0.5 : 1 }}
            >
              {isSubmitting ? 'INGESTING...' : (isInlineMode ? 'REGISTER + SUBMIT' : 'SUBMIT')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

const styles = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999
  },
  modal: {
    background: '#1e293b',
    border: '1px solid rgba(99, 102, 241, 0.3)',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '520px',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
  },
  header: {
    padding: '1.25rem 1.5rem',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    background: 'rgba(15, 23, 42, 0.4)'
  },
  title: {
    color: '#e2e8f0',
    fontSize: '1.1rem',
    fontWeight: 700,
    margin: 0,
    letterSpacing: '0.05em'
  },
  errorBanner: {
    background: 'rgba(239, 68, 68, 0.1)',
    color: '#ef4444',
    padding: '0.75rem 1.5rem',
    fontSize: '0.85rem',
    fontWeight: 500,
    borderBottom: '1px solid rgba(239, 68, 68, 0.2)'
  },
  form: {
    padding: '1.5rem'
  },
  row: {
    display: 'flex',
    gap: '0.75rem'
  },
  inputGroup: {
    marginBottom: '1.25rem'
  },
  inlineBox: {
    border: '1px solid rgba(16, 185, 129, 0.3)',
    background: 'rgba(16, 185, 129, 0.05)',
    borderRadius: '10px',
    padding: '1rem',
    marginBottom: '1.25rem'
  },
  inlineTitle: {
    color: '#10b981',
    fontSize: '0.7rem',
    fontWeight: 800,
    letterSpacing: '0.1em',
    marginBottom: '0.9rem'
  },
  label: {
    display: 'block',
    color: '#94a3b8',
    fontSize: '0.75rem',
    fontWeight: 600,
    marginBottom: '0.5rem',
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  },
  input: {
    width: '100%',
    padding: '0.75rem',
    background: 'rgba(15, 23, 42, 0.5)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    color: '#f8fafc',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.2s'
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.75rem',
    marginTop: '1rem'
  },
  cancelBtn: {
    padding: '0.6rem 1.2rem',
    background: 'transparent',
    color: '#94a3b8',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.8rem',
    transition: 'all 0.2s'
  },
  submitBtn: {
    padding: '0.6rem 1.2rem',
    background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: '0.8rem',
    letterSpacing: '0.05em',
    boxShadow: '0 4px 15px rgba(99, 102, 241, 0.25)',
    transition: 'all 0.2s'
  }
};

export default SkuCreationModal;
