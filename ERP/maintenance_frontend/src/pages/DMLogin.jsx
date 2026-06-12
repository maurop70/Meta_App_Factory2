import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';

const DMLogin = () => {
  const { authenticateContext } = useAuth();
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState('');
  const [pin, setPin] = useState('');
  const [status, setStatus] = useState({ type: 'idle', message: '' });
  const [isActuating, setIsActuating] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isActuating) return;

    if (!employeeId.trim()) {
      setStatus({ type: 'error', message: 'Employee ID is required.' });
      return;
    }
    if (!pin.trim()) {
      setStatus({ type: 'error', message: 'Authorization PIN is required.' });
      return;
    }

    setStatus({ type: 'loading', message: '' });
    setIsActuating(true);

    try {
      const response = await axios.post(
        '/api/v1/auth/login',
        { emp_id: employeeId, pin },
        { withCredentials: true }
      );
      const { access_token } = response.data;

      const payloadBase64 = access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(payloadBase64));

      if (payload.role !== 'DM') {
        setIsActuating(false);
        setStatus({ type: 'error', message: 'Access denied. This portal is for Department Managers only.' });
        return;
      }

      authenticateContext(access_token, payload.role, payload);
      navigate('/dm', { replace: true });
    } catch (err) {
      setIsActuating(false);
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Authentication failed. Please verify credentials.',
      });
    }
  };

  const handlePinChange = (e) => {
    if (isActuating) return;
    const val = e.target.value.replace(/[^0-9]/g, '');
    setPin(val);
    if (status.type === 'error') setStatus({ type: 'idle', message: '' });
  };

  return (
    <div className="erp-login-container">
      <div className="erp-login-card">
        <h2>Department Manager Portal</h2>
        <p>Restricted Access — DM Gateway</p>
        <form onSubmit={handleSubmit} className="erp-login-form" autoComplete="off">
          <div style={{ position: 'absolute', left: '-9999px', top: '-9999px' }} aria-hidden="true">
            <input type="text" name="honeypot_user" autoComplete="username" tabIndex="-1" />
            <input type="password" name="honeypot_pass" autoComplete="current-password" tabIndex="-1" />
          </div>

          <div className="erp-form-group">
            <label>Employee ID</label>
            <input
              type="text"
              name="dm_operator_id"
              id="dm_operator_id"
              value={employeeId}
              onChange={(e) => {
                if (isActuating) return;
                setEmployeeId(e.target.value);
                if (status.type === 'error') setStatus({ type: 'idle', message: '' });
              }}
              disabled={isActuating}
              placeholder="e.g. ERP-4000"
              autoComplete="new-password"
              data-1p-ignore="true"
              data-lpignore="true"
              autoFocus
            />
          </div>
          <div className="erp-form-group">
            <label>Authorization Code</label>
            <input
              type="text"
              style={{ WebkitTextSecurity: 'disc' }}
              name="dm_operator_pin"
              id="dm_operator_pin"
              inputMode="numeric"
              value={pin}
              onChange={handlePinChange}
              disabled={isActuating}
              autoComplete="new-password"
              data-1p-ignore="true"
              data-lpignore="true"
              placeholder="••••"
            />
          </div>
          {status.type !== 'idle' && (
            <div className={`erp-status-message ${status.type}`}>
              {status.type === 'loading' ? 'Authenticating...' : status.message}
            </div>
          )}
          <button
            type="submit"
            className="erp-submit-btn"
            disabled={isActuating || pin.length < 4 || !employeeId.trim()}
          >
            Authorize Session
          </button>
        </form>
      </div>
    </div>
  );
};

export default DMLogin;
