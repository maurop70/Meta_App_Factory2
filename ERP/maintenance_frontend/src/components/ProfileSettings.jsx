import React, { useState } from 'react';
import axios from 'axios';
import { AUTH_API_BASE_URL } from '../services/api';

/**
 * Reusable "Profile Settings" overlay. Lets an authenticated employee set a
 * custom username, phone number, and PIN. Talks directly to the Gateway
 * (AUTH_API_BASE_URL) with a manually-attached Bearer token, since the auth
 * endpoints sit outside the MWO apiClient interceptor.
 *
 * Props:
 *   onClose()    — dismiss the overlay (ignored in forced mode).
 *   forced       — first-time activation: the overlay is mandatory and cannot
 *                  be dismissed until custom credentials are chosen.
 *   onComplete() — called after a successful forced activation (the app uses
 *                  this to log the user out so they re-authenticate with the
 *                  new credentials, clearing the setup_required gate).
 */
const ProfileSettings = ({ onClose, forced = false, onComplete }) => {
  const [username, setUsername] = useState('');
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [status, setStatus] = useState({ type: 'idle', message: '' });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving) return;

    // First-time activation requires the operator to choose all three.
    if (forced && (!username.trim() || !phone.trim() || !pin.trim())) {
      setStatus({ type: 'error', message: 'Username, phone number, and a new PIN are all required to activate.' });
      return;
    }

    // Only submit fields the user actually filled in (all are optional).
    const payload = {};
    if (username.trim()) payload.username = username.trim();
    if (phone.trim()) payload.phone_number = phone.trim();
    if (pin.trim()) {
      if (pin !== confirmPin) {
        setStatus({ type: 'error', message: 'PINs do not match.' });
        return;
      }
      if (!/^\d{4,8}$/.test(pin.trim())) {
        setStatus({ type: 'error', message: 'PIN must be 4-8 digits.' });
        return;
      }
      payload.pin = pin.trim();
    }

    if (Object.keys(payload).length === 0) {
      setStatus({ type: 'error', message: 'Nothing to update.' });
      return;
    }

    setSaving(true);
    setStatus({ type: 'loading', message: '' });
    try {
      const token = localStorage.getItem('accessToken');
      await axios.post(`${AUTH_API_BASE_URL}/v1/auth/setup-credentials`, payload, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setStatus({
        type: 'success',
        message: forced ? 'Account activated. Re-authenticating...' : 'Credentials updated. Use them at your next login.',
      });
      setPin('');
      setConfirmPin('');
      if (forced && onComplete) {
        setTimeout(() => onComplete(), 1500);
      }
    } catch (err) {
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Update failed. Please try again.',
      });
    } finally {
      setSaving(false);
    }
  };

  const onlyDigits = (setter) => (e) => setter(e.target.value.replace(/[^0-9]/g, ''));

  return (
    <div
      className="profile-settings-overlay"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem',
      }}
      onClick={forced ? undefined : onClose}
    >
      <div
        className="profile-settings-card"
        style={{
          background: 'var(--bg-card, #0f172a)', border: '1px solid var(--border, #2e303a)',
          borderRadius: 12, padding: '1.5rem', width: '100%', maxWidth: 420, textAlign: 'left',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>{forced ? 'Activate Your Account' : 'Profile Settings'}</h2>
          {!forced && (
            <button type="button" onClick={onClose} aria-label="Close"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.4rem', cursor: 'pointer' }}>×</button>
          )}
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
          {forced
            ? 'First-time access: choose a secure username, your cell phone number, and a new PIN to continue.'
            : 'Leave a field blank to keep it unchanged.'}
        </p>

        <form onSubmit={handleSubmit} autoComplete="off">
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4 }}>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. tech1"
            autoComplete="off" style={inputStyle} />

          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.75rem 0 4px' }}>Phone Number</label>
          <input value={phone} onChange={onlyDigits(setPhone)} inputMode="numeric" placeholder="e.g. 5550199"
            autoComplete="off" style={inputStyle} />

          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.75rem 0 4px' }}>New PIN (4-8 digits)</label>
          <input value={pin} onChange={onlyDigits(setPin)} inputMode="numeric" style={{ ...inputStyle, WebkitTextSecurity: 'disc' }} autoComplete="new-password" />

          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.75rem 0 4px' }}>Confirm PIN</label>
          <input value={confirmPin} onChange={onlyDigits(setConfirmPin)} inputMode="numeric" style={{ ...inputStyle, WebkitTextSecurity: 'disc' }} autoComplete="new-password" />

          {status.type !== 'idle' && (
            <div style={{
              marginTop: '0.75rem', fontSize: '0.85rem',
              color: status.type === 'error' ? 'var(--danger, #ef4444)'
                : status.type === 'success' ? 'var(--success, #10b981)' : 'var(--text-muted)',
            }}>
              {status.type === 'loading' ? 'Saving...' : status.message}
            </div>
          )}

          <button type="submit" disabled={saving}
            style={{
              marginTop: '1.25rem', width: '100%', minHeight: 48, padding: '0.75rem',
              background: 'var(--accent, #6366f1)', color: '#fff', border: 'none', borderRadius: 8,
              cursor: saving ? 'default' : 'pointer', fontWeight: 600, opacity: saving ? 0.6 : 1,
            }}>
            {saving ? 'Saving...' : (forced ? 'Activate Account' : 'Save Changes')}
          </button>
        </form>
      </div>
    </div>
  );
};

const inputStyle = {
  width: '100%', padding: '0.6rem 0.75rem', boxSizing: 'border-box',
  background: 'var(--code-bg, #1f2028)', border: '1px solid var(--border, #2e303a)',
  borderRadius: 8, color: 'var(--text-primary, #e2e8f0)', fontSize: '1rem',
};

export default ProfileSettings;
