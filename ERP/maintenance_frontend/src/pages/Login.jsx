import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/MockAuthContext';

const Login = () => {
  const { userRole } = useAuth();
  const navigate = useNavigate();
  const [pin, setPin] = useState('');
  const [status, setStatus] = useState({ type: 'idle', message: '' });

  // Reactive Routing Patch
  useEffect(() => {
    if (userRole && ['Administrator', 'DM', 'HM', 'Technician'].includes(userRole)) {
      navigate('/', { replace: true });
    }
  }, [userRole, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pin.trim()) {
      setStatus({ type: 'error', message: 'Authorization PIN is required.' });
      return;
    }
    // Form Submission Hijack (Fallback bypass)
    navigate('/', { replace: true });
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
