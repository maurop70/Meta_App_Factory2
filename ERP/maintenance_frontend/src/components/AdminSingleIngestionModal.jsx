import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const AdminSingleIngestionModal = ({ closeModal }) => {
  const [departments, setDepartments] = useState([]);
  const [hms, setHms] = useState([]);
  const [formData, setFormData] = useState({ 
    name: '', 
    role: 'TECH', 
    pin_code: '',
    is_active: 1,
    department_id: '',
    reports_to_hm_id: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  
  // Fetch bounded lookups on mount
  useEffect(() => {
    let isMounted = true;
    api.get('/admin/lookups/departments?limit=100&offset=0')
      .then(res => {
        if (isMounted) setDepartments(res.data.data || []);
      })
      .catch(err => {
        if (isMounted) console.error("Department lookup failure:", err);
      });
    return () => { isMounted = false; };
  }, []);

  // Dynamically fetch HM matrix strictly scoped to selected department_id
  useEffect(() => {
    let isMounted = true; // Strict React 18 teardown closure

    if (formData.role === 'TECH' && formData.department_id) {
      // Axios prefix truncation enforced
      api.get(`/admin/hms?department_id=${encodeURIComponent(formData.department_id)}&limit=50&offset=0`)
        .then(res => {
          if (isMounted) {
            setHms(res.data.data || []);
            // Force reset selected HM if the list changes
            setFormData(prev => ({ ...prev, reports_to_hm_id: '' }));
          }
        })
        .catch(err => {
            if (isMounted) console.error("HM Matrix Error:", err);
        });
    } else {
      setHms([]); // Purge HM cache if role changes or department is unselected
    }

    return () => {
      isMounted = false; // Physically locks asynchronous state mutations on unmount
    };
  }, [formData.department_id, formData.role]);

  // Structural Isolation: Actuation Lockout Doctrine
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && !isSubmitting) closeModal();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [closeModal, isSubmitting]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    
    // Convert pin_code to string to strictly enforce schema
    const submitData = {
        ...formData,
        pin_code: String(formData.pin_code),
        reports_to_hm_id: formData.reports_to_hm_id || null
    };

    try {
      // AXIOS PREFIX TRUNCATION DOCTRINE ENFORCED
      const response = await api.post('/admin/ingest/single-user', submitData);
      closeModal(true); // Signal success
    } catch (err) {
      setError(err.response?.data?.detail || 'Ingestion failed');
      setIsSubmitting(false);
    }
  };

  const modalContent = (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 99999, fontFamily: "var(--font, Inter)" }}>
      <div style={{ background: 'var(--bg-card, #0f172a)', border: '1px solid var(--border, rgba(99, 102, 241, 0.3))', borderRadius: '12px', width: '90%', maxWidth: '500px', padding: '2rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
        <h2 style={{ marginTop: 0, color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1.5rem' }}>Manual Record Entry (Phase 35.3)</h2>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          {error && (
            <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>Name <span style={{ color: '#ef4444' }}>*</span></label>
            <input type="text" name="name" value={formData.name} onChange={handleChange} placeholder="e.g. Jane Doe" required disabled={isSubmitting} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none' }} />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>Role <span style={{ color: '#ef4444' }}>*</span></label>
            <select name="role" value={formData.role} onChange={handleChange} disabled={isSubmitting} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none' }}>
              <option value="TECH">TECH</option>
              <option value="HM">HM</option>
              <option value="ADMIN">ADMIN</option>
              <option value="ADMINISTRATOR">ADMINISTRATOR</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>Department <span style={{ color: '#ef4444' }}>*</span></label>
            <select name="department_id" value={formData.department_id} onChange={handleChange} required disabled={isSubmitting} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none' }}>
              <option value="">-- Select Department --</option>
              {departments.map(dep => (
                <option key={dep.id} value={dep.id}>{dep.name}</option>
              ))}
            </select>
          </div>

          {formData.role === 'TECH' && (
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>Assigned Manager (HM)</label>
              <select name="reports_to_hm_id" value={formData.reports_to_hm_id} onChange={handleChange} required disabled={hms.length === 0 || isSubmitting} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none' }}>
                <option value="">-- Select Manager --</option>
                {hms.map(hm => (
                  <option key={hm.id} value={hm.id}>{hm.name} ({hm.id})</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>PIN Code <span style={{ color: '#ef4444' }}>*</span></label>
            <input type="password" name="pin_code" value={formData.pin_code} onChange={handleChange} placeholder="Min 4 characters (Never Stored Plaintext)" required disabled={isSubmitting} style={{ width: '100%', padding: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#e2e8f0', outline: 'none' }} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1rem' }}>
            <button type="button" onClick={() => closeModal()} disabled={isSubmitting} style={{ padding: '0.6rem 1.2rem', background: 'transparent', border: '1px solid rgba(255, 255, 255, 0.2)', borderRadius: '6px', color: '#e2e8f0', cursor: isSubmitting ? 'not-allowed' : 'pointer', fontWeight: 600 }}>
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting} style={{ padding: '0.6rem 1.2rem', background: isSubmitting ? 'rgba(99, 102, 241, 0.5)' : 'linear-gradient(135deg, var(--accent, #6366f1), #7c3aed)', border: 'none', borderRadius: '6px', color: 'white', cursor: isSubmitting ? 'not-allowed' : 'pointer', fontWeight: 600, boxShadow: isSubmitting ? 'none' : '0 4px 15px rgba(99, 102, 241, 0.4)' }}>
              {isSubmitting ? 'Injecting...' : 'Inject Record'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default AdminSingleIngestionModal;
