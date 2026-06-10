import React, { useState } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

/**
 * [BACK OFFICE INVENTORY] Dedicated supplier registration modal.
 * Name and email are strictly compulsory; phone/address are optional contact details.
 */
const SupplierCreationModal = ({ closeModal, onRegistrationSuccess }) => {
  const [formData, setFormData] = useState({
    supplier_id: '',
    name: '',
    email: '',
    phone: '',
    address: '',
    default_lead_time_days: '7'
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const leadTime = parseInt(formData.default_lead_time_days, 10);
    if (isNaN(leadTime) || leadTime < 0) {
      setError("Lead time must be a non-negative number of days.");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(formData.email.trim())) {
      setError("A valid supplier email address is compulsory (user@domain.tld).");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/inventory/suppliers', {
        supplier_id: formData.supplier_id.trim(),
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: formData.phone.trim() || null,
        address: formData.address.trim() || null,
        default_lead_time_days: leadTime
      });
      if (onRegistrationSuccess) onRegistrationSuccess();
      closeModal();
    } catch (err) {
      console.error("Supplier Registration Error:", err);
      setError(err.response?.data?.detail || "Failed to register supplier. System error.");
      setIsSubmitting(false);
    }
  };

  const modalContent = (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h3 style={styles.title}>SUPPLIER REGISTRATION MATRIX</h3>
        </div>

        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Supplier ID *</label>
            <input type="text" name="supplier_id" value={formData.supplier_id} onChange={handleInputChange}
              disabled={isSubmitting} required minLength={2} maxLength={50} placeholder="e.g. SUP-PARTS-02" style={styles.input} />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Supplier Name *</label>
            <input type="text" name="name" value={formData.name} onChange={handleInputChange}
              disabled={isSubmitting} required minLength={2} maxLength={200} style={styles.input} />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Order Email *</label>
            <input type="email" name="email" value={formData.email} onChange={handleInputChange}
              disabled={isSubmitting} required placeholder="orders@supplier.example.com" style={styles.input} />
          </div>

          <div style={styles.row}>
            <div style={{ ...styles.inputGroup, flex: 1 }}>
              <label style={styles.label}>Phone</label>
              <input type="tel" name="phone" value={formData.phone} onChange={handleInputChange}
                disabled={isSubmitting} placeholder="Optional" style={styles.input} />
            </div>
            <div style={{ ...styles.inputGroup, width: '130px' }}>
              <label style={styles.label}>Lead Time (Days)</label>
              <input type="number" name="default_lead_time_days" value={formData.default_lead_time_days}
                onChange={handleInputChange} disabled={isSubmitting} min={0} max={365} style={styles.input} />
            </div>
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Address</label>
            <input type="text" name="address" value={formData.address} onChange={handleInputChange}
              disabled={isSubmitting} placeholder="Optional" style={styles.input} />
          </div>

          <div style={styles.footer}>
            <button type="button" onClick={closeModal} disabled={isSubmitting} style={styles.cancelBtn}>
              CANCEL
            </button>
            <button type="submit" disabled={isSubmitting} style={{ ...styles.submitBtn, opacity: isSubmitting ? 0.5 : 1 }}>
              {isSubmitting ? 'REGISTERING...' : 'REGISTER SUPPLIER'}
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
    border: '1px solid rgba(16, 185, 129, 0.3)',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '480px',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
    overflow: 'hidden'
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
    background: 'linear-gradient(135deg, #10b981, #059669)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: '0.8rem',
    letterSpacing: '0.05em',
    boxShadow: '0 4px 15px rgba(16, 185, 129, 0.25)',
    transition: 'all 0.2s'
  }
};

export default SupplierCreationModal;
