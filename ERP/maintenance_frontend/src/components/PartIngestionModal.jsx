import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const PartIngestionModal = ({ closeModal, onIngestionSuccess }) => {
  const [activeTab, setActiveTab] = useState('SINGLE');
  const [categories, setCategories] = useState([]);
  
  const [formData, setFormData] = useState({
    nomenclature: '',
    category_id: '',
    quantity_on_hand: 0,
    reorder_threshold: 5,
    unit_cost: 0.0
  });
  
  const [bulkFile, setBulkFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    api.get('/admin/lookups/categories?limit=100&offset=0')
      .then(res => {
        if (isMounted) setCategories(res.data.data || []);
      })
      .catch(err => {
        if (isMounted) console.error("Category lookup failure:", err);
      });
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const handleEsc = (e) => {
      if (e.key === 'Escape' && isMounted && !submitting) closeModal();
    };
    document.addEventListener('keydown', handleEsc);
    return () => {
      isMounted = false;
      document.removeEventListener('keydown', handleEsc);
    };
  }, [closeModal, submitting]);

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? (value === '' ? '' : Number(value)) : value
    }));
  };

  const handleSingleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await api.post('/admin/ingest/part', formData);
      onIngestionSuccess();
      closeModal();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to ingest part record.');
      setSubmitting(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const response = await api.get('/admin/ingest/part/template', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'part_ingestion_template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Failed to download template.');
    }
  };

  const handleBulkSubmit = async (e) => {
    e.preventDefault();
    if (!bulkFile || submitting) return;
    
    try {
      setSubmitting(true);
      setError(null);
      
      const formData = new FormData();
      formData.append('file', bulkFile);
      
      await api.post('/admin/ingest/part/bulk', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      onIngestionSuccess();
      closeModal();
    } catch (err) {
      setError(err.response?.data?.detail || 'Bulk part ingestion failed.');
      setSubmitting(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '0.6rem', background: 'rgba(10, 14, 23, 0.8)',
    border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '6px',
    color: '#e2e8f0', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box'
  };

  const labelStyle = {
    display: 'block', marginBottom: '0.3rem', color: '#94a3b8',
    fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em'
  };

  const modalContent = (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }} onClick={() => !submitting && closeModal()}>
      <div style={{ background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95))', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: '16px', padding: '2rem', width: '500px', maxWidth: '90vw', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e2e8f0', margin: 0 }}>Ingest Part Record (Phase 35.4)</h3>
          </div>
          <button disabled={submitting} onClick={closeModal} style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', padding: '0.3rem 0.6rem', cursor: submitting ? 'not-allowed' : 'pointer', fontSize: '0.75rem', fontWeight: 600, opacity: submitting ? 0.5 : 1 }}>ESC</button>
        </div>

        {error && <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.8rem', marginBottom: '1rem' }}>{error}</div>}

        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(148, 163, 184, 0.2)', paddingBottom: '0.5rem' }}>
          <button
            onClick={() => setActiveTab('SINGLE')}
            disabled={submitting}
            style={{ background: 'none', border: 'none', color: activeTab === 'SINGLE' ? '#6366f1' : '#94a3b8', fontSize: '0.85rem', fontWeight: 700, cursor: submitting ? 'not-allowed' : 'pointer', padding: '0.5rem 1rem', borderBottom: activeTab === 'SINGLE' ? '2px solid #6366f1' : '2px solid transparent', transition: 'all 0.2s' }}
          >
            SINGLE ENTRY
          </button>
          <button
            onClick={() => setActiveTab('BULK')}
            disabled={submitting}
            style={{ background: 'none', border: 'none', color: activeTab === 'BULK' ? '#6366f1' : '#94a3b8', fontSize: '0.85rem', fontWeight: 700, cursor: submitting ? 'not-allowed' : 'pointer', padding: '0.5rem 1rem', borderBottom: activeTab === 'BULK' ? '2px solid #6366f1' : '2px solid transparent', transition: 'all 0.2s' }}
          >
            BULK XLSX UPLOAD
          </button>
        </div>

        {activeTab === 'SINGLE' && (
          <form onSubmit={handleSingleSubmit}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={labelStyle}>Category <span style={{ color: '#ef4444' }}>*</span></label>
              <select name="category_id" value={formData.category_id} onChange={handleChange} required disabled={submitting} style={inputStyle}>
                <option value="">-- Select Category --</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={labelStyle}>Nomenclature <span style={{ color: '#ef4444' }}>*</span></label>
              <input name="nomenclature" value={formData.nomenclature} onChange={handleChange} required disabled={submitting} style={inputStyle} placeholder="Hydraulic Seal Ring" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <label style={labelStyle}>Qty On Hand <span style={{ color: '#ef4444' }}>*</span></label>
                <input name="quantity_on_hand" type="number" value={formData.quantity_on_hand} onChange={handleChange} required min="0" disabled={submitting} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Reorder Threshold <span style={{ color: '#ef4444' }}>*</span></label>
                <input name="reorder_threshold" type="number" value={formData.reorder_threshold} onChange={handleChange} required min="0" disabled={submitting} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Unit Cost ($) <span style={{ color: '#ef4444' }}>*</span></label>
                <input name="unit_cost" type="number" step="0.01" value={formData.unit_cost} onChange={handleChange} required min="0" disabled={submitting} style={inputStyle} />
              </div>
            </div>

            <button type="submit" disabled={submitting} style={{ width: '100%', padding: '0.7rem', background: submitting ? 'rgba(99, 102, 241, 0.2)' : 'linear-gradient(135deg, #6366f1, #7c3aed)', color: submitting ? '#94a3b8' : '#fff', border: 'none', borderRadius: '8px', cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: submitting ? 'none' : '0 4px 15px rgba(99, 102, 241, 0.25)' }}>
              {submitting ? 'PROCESSING...' : 'INGEST PART RECORD'}
            </button>
          </form>
        )}

        {activeTab === 'BULK' && (
          <form onSubmit={handleBulkSubmit}>
            <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                disabled={submitting}
                style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '6px', padding: '0.6rem 1.2rem', cursor: submitting ? 'not-allowed' : 'pointer', fontSize: '0.8rem', fontWeight: 600, transition: 'all 0.2s' }}
              >
                ⬇ DOWNLOAD XLSX TEMPLATE
              </button>
              <p style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                Download the exact schema mapping needed for bulk upload.
              </p>
            </div>
            
            <div style={{ marginBottom: '1.5rem', background: 'rgba(10, 14, 23, 0.5)', padding: '1.5rem', borderRadius: '8px', border: '1px dashed rgba(99, 102, 241, 0.4)', textAlign: 'center' }}>
              <label style={{ ...labelStyle, marginBottom: '1rem', cursor: 'pointer' }}>
                Select XLSX File
                <input
                  type="file"
                  accept=".xlsx"
                  onChange={e => setBulkFile(e.target.files[0])}
                  disabled={submitting}
                  style={{ display: 'none' }}
                />
                <div style={{ marginTop: '0.5rem', color: '#e2e8f0', fontSize: '0.85rem', fontWeight: 500 }}>
                  {bulkFile ? bulkFile.name : 'Click to browse...'}
                </div>
              </label>
            </div>

            <button
              type="submit"
              disabled={submitting || !bulkFile}
              style={{ width: '100%', padding: '0.7rem', background: submitting || !bulkFile ? 'rgba(99, 102, 241, 0.2)' : 'linear-gradient(135deg, #6366f1, #7c3aed)', color: submitting || !bulkFile ? '#64748b' : '#fff', border: 'none', borderRadius: '8px', cursor: submitting || !bulkFile ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: submitting || !bulkFile ? 'none' : '0 4px 15px rgba(99, 102, 241, 0.25)' }}
            >
              {submitting ? 'UPLOADING...' : 'UPLOAD BULK XLSX'}
            </button>
          </form>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default PartIngestionModal;
