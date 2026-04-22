import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [pin, setPin] = useState('');
  const [status, setStatus] = useState({ type: 'idle', message: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pin.trim()) {
      setStatus({ type: 'error', message: 'Authorization PIN is required.' });
      return;
    }
    setStatus({ type: 'loading', message: 'Verifying Security Credentials...' });
    try {
      const response = await api.post('/api/user/verify-pin', { pin });
      if (response.data && response.data.status === 'success') {
        const { role, user } = response.data;
        login(role, user, pin);
        navigate(role.toLowerCase() === 'admin' ? '/admin' : '/tech');
      } else if (response.data && response.data.role) {
        // Fallback for raw schema without status wrapper
        login(response.data.role, response.data.name || 'User', pin);
        navigate(response.data.role.toLowerCase() === 'admin' ? '/admin' : '/tech');
      } else {
        // Expose unknown 200 OK payload to the UI
        setStatus({ type: 'error', message: `Unhandled Schema: ${JSON.stringify(response.data)}` });
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Network Error: Core Server Unreachable.";
      setStatus({ type: 'error', message: `Verification Rejected: ${errorMsg}` });
      setPin('');
    }
  };

  const handlePinChange = (e) => {
    const val = e.target.value.replace(/[^0-9]/g, '');
    setPin(val);
    if (status.type === 'error') setStatus({ type: 'idle', message: '' });
  };

  return (
    <div className="erp-login-container">
      <div className="erp-login-card">
        <h2>Maintenance Command</h2>
        <p>Restricted Access Gateway</p>
        <form onSubmit={handleSubmit} className="erp-login-form">
          <div className="erp-form-group">
            <label>Authorization Code</label>
            <input
              type="password"
              inputMode="numeric"
              value={pin}
              onChange={handlePinChange}
              disabled={status.type === 'loading'}
              placeholder="••••"
              autoFocus
            />
          </div>
          {status.type !== 'idle' && (
            <div className={`erp-status-message ${status.type}`}>
              {status.type === 'loading' ? 'Authenticating...' : status.message}
            </div>
          )}
          <button type="submit" className="erp-submit-btn" disabled={status.type === 'loading' || pin.length < 4}>
            Authorize Session
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
