import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

/**
 * Dynamic Role Registry console. Lists roles from GET /admin/roles, registers
 * new roles via POST, and deletes custom roles via DELETE. The delete control is
 * disabled for system-default roles (is_system_default) so the UI mirrors the
 * backend's 400 guard rather than relying on the error round-trip; the backend's
 * 409 ("role in use") and 400 ("system role") are surfaced as readable messages.
 */
const RoleManagement = () => {
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newRole, setNewRole] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState({ type: '', message: '' });

  const fetchRoles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/roles');
      setRoles(res.data?.data || []);
    } catch (err) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to load roles.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRoles(); }, [fetchRoles]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (submitting) return;
    const name = newRole.trim();
    if (!name) {
      setStatus({ type: 'error', message: 'Role name is required.' });
      return;
    }
    setSubmitting(true);
    setStatus({ type: '', message: '' });
    try {
      await api.post('/admin/roles', { role_name: name, description: newDesc.trim() || null });
      setStatus({ type: 'success', message: `Role '${name.toUpperCase()}' registered.` });
      setNewRole('');
      setNewDesc('');
      await fetchRoles();
    } catch (err) {
      // Backend 409 (duplicate) / 422 (validation) surface here as readable text.
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to register role.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (role) => {
    if (role.is_system_default) return; // UI guard mirrors the backend 400
    if (!window.confirm(`Delete role '${role.role_name}'? This cannot be undone.`)) return;
    setStatus({ type: '', message: '' });
    try {
      await api.delete(`/admin/roles/${encodeURIComponent(role.role_name)}`);
      setStatus({ type: 'success', message: `Role '${role.role_name}' deleted.` });
      await fetchRoles();
    } catch (err) {
      // 409 ("held by N active employee(s)") and 400 ("system-default") land here.
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to delete role.' });
    }
  };

  const cardStyle = {
    background: 'var(--bg-card, rgba(15, 23, 42, 0.85))',
    border: '1px solid var(--border, rgba(99, 102, 241, 0.15))',
    borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)',
  };
  const inputStyle = {
    padding: '0.6rem 0.8rem', borderRadius: '6px',
    border: '1px solid rgba(56, 189, 248, 0.3)', background: 'rgba(15, 23, 42, 0.6)',
    color: '#e2e8f0', fontSize: '0.85rem', fontFamily: 'inherit', outline: 'none',
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: '2rem', marginTop: '20px', fontFamily: 'var(--font, Inter)' }}>
      {/* LEFT: register a new role */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '0.5rem' }}>Register Role</h3>
        <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
          Add a custom role to the dynamic registry. Names are stored uppercase.
        </p>
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <input
            type="text" placeholder="Role name (e.g. SUPERVISOR)"
            value={newRole} onChange={(e) => setNewRole(e.target.value)} style={inputStyle}
          />
          <input
            type="text" placeholder="Description (optional)"
            value={newDesc} onChange={(e) => setNewDesc(e.target.value)} style={inputStyle}
          />
          <button
            type="submit" disabled={submitting || !newRole.trim()}
            style={{
              padding: '0.6rem 1.5rem',
              background: (submitting || !newRole.trim()) ? 'rgba(99, 102, 241, 0.2)' : 'linear-gradient(135deg, var(--accent, #6366f1), #7c3aed)',
              color: (submitting || !newRole.trim()) ? 'var(--text-muted, #64748b)' : '#fff',
              border: 'none', borderRadius: '8px',
              cursor: (submitting || !newRole.trim()) ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: '0.85rem', transition: 'all 0.2s',
            }}
          >
            {submitting ? 'Registering...' : '+ Register Role'}
          </button>
          {status.message && (
            <span style={{
              fontSize: '0.85rem', fontWeight: 500, padding: '6px 12px', borderRadius: '6px',
              background: status.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
              color: status.type === 'error' ? 'var(--danger, #ef4444)' : 'var(--success, #10b981)',
            }}>
              {status.message}
            </span>
          )}
        </form>
      </div>

      {/* RIGHT: registry table */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '1rem' }}>Role Registry</h3>
        {loading ? (
          <div style={{ color: '#94a3b8', padding: '1rem 0' }}>Loading roles...</div>
        ) : (
          <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', background: 'rgba(10, 14, 23, 0.5)' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'rgba(99, 102, 241, 0.1)', color: 'var(--text-secondary, #94a3b8)', textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>
                  <th style={{ padding: '0.8rem 1rem' }}>Role</th>
                  <th style={{ padding: '0.8rem 1rem' }}>Description</th>
                  <th style={{ padding: '0.8rem 1rem' }}>Type</th>
                  <th style={{ padding: '0.8rem 1rem' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {roles.length === 0 ? (
                  <tr><td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>No roles registered.</td></tr>
                ) : roles.map((role) => (
                  <tr key={role.role_name} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '0.8rem 1rem', color: '#818cf8', fontWeight: 600 }}>{role.role_name}</td>
                    <td style={{ padding: '0.8rem 1rem', color: '#cbd5e1' }}>{role.description || '—'}</td>
                    <td style={{ padding: '0.8rem 1rem' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 600,
                        background: role.is_system_default ? 'rgba(148, 163, 184, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                        color: role.is_system_default ? '#94a3b8' : '#34d399',
                      }}>
                        {role.is_system_default ? 'SYSTEM' : 'CUSTOM'}
                      </span>
                    </td>
                    <td style={{ padding: '0.8rem 1rem' }}>
                      <button
                        onClick={() => handleDelete(role)}
                        disabled={role.is_system_default}
                        title={role.is_system_default ? 'System-default roles cannot be deleted.' : 'Delete this role'}
                        style={{
                          padding: '0.35rem 0.8rem', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600,
                          textTransform: 'uppercase', letterSpacing: '0.05em',
                          border: '1px solid', transition: 'all 0.2s',
                          borderColor: role.is_system_default ? 'rgba(148, 163, 184, 0.2)' : 'rgba(239, 68, 68, 0.3)',
                          background: role.is_system_default ? 'rgba(148, 163, 184, 0.08)' : 'rgba(239, 68, 68, 0.12)',
                          color: role.is_system_default ? '#475569' : '#fca5a5',
                          cursor: role.is_system_default ? 'not-allowed' : 'pointer',
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default RoleManagement;
