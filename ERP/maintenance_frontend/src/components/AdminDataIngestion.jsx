import React, { useState } from 'react';
import AdminSingleIngestionModal from './AdminSingleIngestionModal';
import TaxonomyIngestionModal from './TaxonomyIngestionModal';
import api from '../services/api';

const AdminDataIngestion = () => {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showSingleModal, setShowSingleModal] = useState(false);
  const [showTaxonomyModal, setShowTaxonomyModal] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setStatus({ type: 'error', message: 'Please select a CSV file first.' });
      return;
    }

    setLoading(true);
    setStatus({ type: '', message: '' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/admin/ingest/personnel/bulk', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const result = response.data;

      setStatus({ 
        type: 'success', 
        message: result.message || 'Upload successful!'
      });
      setFile(null);
      // Reset input value to allow uploading the same file again if needed
      document.getElementById('csvUpload').value = '';
    } catch (error) {
      console.error(error);
      setStatus({ type: 'error', message: error.response?.data?.detail || error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginTop: '20px', fontFamily: "var(--font, Inter)" }}>
      {/* LEFT PANE: BULK INGESTION */}
      <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '0.5rem' }}>Bulk Personnel Ingestion</h3>
      <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>Upload an XLSX file containing personnel data.</p>
      
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <button
          onClick={async () => {
            try {
              const response = await api.get('/admin/ingest/personnel/template', { responseType: 'blob' });
              const blob = new Blob([response.data]);
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'personnel_ingestion_template.xlsx';
              document.body.appendChild(a);
              a.click();
              a.remove();
            } catch (err) {
              setStatus({ type: 'error', message: 'Failed to download template.' });
            }
          }}
          disabled={loading}
          style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '6px', padding: '0.6rem 1.2rem', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '0.8rem', fontWeight: 600, transition: 'all 0.2s' }}
        >
          ⬇ DOWNLOAD XLSX TEMPLATE
        </button>
      </div>
      
      <div 
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        style={{ border: `2px dashed ${isDragging ? 'var(--accent, #6366f1)' : 'var(--border, rgba(99, 102, 241, 0.3))'}`, borderRadius: '8px', padding: '2rem', textAlign: 'center', background: isDragging ? 'rgba(99, 102, 241, 0.1)' : 'rgba(10, 14, 23, 0.4)', marginBottom: '1.5rem', transition: 'all 0.3s' }}>
        <input 
          type="file" 
          id="csvUpload"
          accept=".xlsx"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <label htmlFor="csvUpload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '2rem' }}>📁</span>
          <span style={{ color: 'var(--text-primary, #e2e8f0)', fontWeight: 500 }}>
            {file ? file.name : 'Click to browse or drag XLSX file here'}
          </span>
          <span style={{ color: 'var(--text-muted, #64748b)', fontSize: '0.75rem' }}>Maximum file size: 5MB</span>
        </label>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          {status.message && (
            <span style={{ 
              fontSize: '0.85rem', 
              fontWeight: 500,
              padding: '6px 12px',
              borderRadius: '6px',
              background: status.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
              color: status.type === 'error' ? 'var(--danger, #ef4444)' : 'var(--success, #10b981)' 
            }}>
              {status.message}
            </span>
          )}
        </div>
        <button 
          onClick={handleUpload}
          disabled={!file || loading}
          style={{ 
            padding: '0.6rem 1.5rem', 
            background: file && !loading ? 'linear-gradient(135deg, var(--accent, #6366f1), #7c3aed)' : 'rgba(99, 102, 241, 0.2)', 
            color: file && !loading ? 'white' : 'var(--text-muted, #64748b)', 
            border: 'none', 
            borderRadius: '8px', 
            cursor: file && !loading ? 'pointer' : 'not-allowed', 
            fontWeight: '600', 
            fontSize: '0.85rem', 
            transition: 'all 0.2s', 
            boxShadow: file && !loading ? '0 4px 15px var(--accent-glow, rgba(99, 102, 241, 0.25))' : 'none' 
          }}
        >
          {loading ? 'Processing...' : 'Upload Data'}
        </button>
      </div>
      </div>

      {/* RIGHT PANE: MANUAL ENTRY */}
      <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '0.5rem' }}>Manual Record Entry</h3>
        <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>Inject single personnel records directly into the live schema.</p>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button 
            onClick={() => setShowSingleModal(true)}
            style={{ padding: '0.6rem 1.5rem', background: 'linear-gradient(135deg, var(--accent, #6366f1), #7c3aed)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem', boxShadow: '0 4px 15px var(--accent-glow, rgba(99, 102, 241, 0.25))' }}
          >
            + Add Personnel
          </button>
          
          <button 
            onClick={() => setShowTaxonomyModal(true)}
            style={{ padding: '0.6rem 1.5rem', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem' }}
          >
            + Add Department/Location
          </button>
        </div>
      </div>

      {showSingleModal && (
        <AdminSingleIngestionModal closeModal={() => setShowSingleModal(false)} />
      )}
      
      <TaxonomyIngestionModal isOpen={showTaxonomyModal} onClose={() => setShowTaxonomyModal(false)} />
    </div>
  );
};

export default AdminDataIngestion;
