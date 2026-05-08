import React, { useState } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const SkuCreationModal = ({ closeModal, onIngestionSuccess }) => {
  const [formData, setFormData] = useState({
    sku_id: '',
    nomenclature: '',
    unit_cost: '',
    reorder_threshold: ''
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    // Validate payload types
    const payload = {
      sku_id: formData.sku_id.trim(),
      nomenclature: formData.nomenclature.trim(),
      unit_cost: parseFloat(formData.unit_cost),
      reorder_threshold: parseInt(formData.reorder_threshold, 10)
    };

    if (isNaN(payload.unit_cost) || isNaN(payload.reorder_threshold)) {
      setError("Unit cost and Reorder threshold must be numeric.");
      setIsSubmitting(false);
      return;
    }

    try {
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

          <div style={styles.inputGroup}>
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

          <div style={styles.inputGroup}>
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
              {isSubmitting ? 'INGESTING...' : 'SUBMIT'}
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
    maxWidth: '450px',
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
    marginTop: '2rem'
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
