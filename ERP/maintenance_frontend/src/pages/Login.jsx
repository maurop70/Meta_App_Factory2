import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const { authenticateContext } = useAuth();
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState('');
  const [pin, setPin] = useState('');
  const [status, setStatus] = useState({ type: 'idle', message: '' });
  const [isActuating, setIsActuating] = useState(false);

  // Keyboard listener unbind handled implicitly via disabled states on forms during isActuating
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isActuating) return; // Strict Lockout
    
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
      const response = await api.post('/user/authenticate', { employee_id: employeeId, pin });
      const { access_token } = response.data;
      
      const payloadBase64 = access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(payloadBase64));
      
      authenticateContext(access_token, payload.role, payload);
      navigate('/', { replace: true });
      
    } catch (err) {
      console.error(err);
      setIsActuating(false);
      setStatus({ 
        type: 'error', 
        message: err.response?.data?.detail || 'Authentication failed. Please verify credentials.' 
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
        <h2>Maintenance Command</h2>
        <p>Restricted Access Gateway</p>
        <form onSubmit={handleSubmit} className="erp-login-form" autoComplete="off">
          {/* Extension Honeypot: Force extensions to hook here instead of active inputs */}
          <div style={{ position: 'absolute', left: '-9999px', top: '-9999px' }} aria-hidden="true">
            <input type="text" name="honeypot_user" autoComplete="username" tabIndex="-1" />
            <input type="password" name="honeypot_pass" autoComplete="current-password" tabIndex="-1" />
          </div>

          <div className="erp-form-group">
            <label>Employee ID</label>
            <input
              type="text"
              name="mwo_operator_id"
              id="mwo_operator_id"
              value={employeeId}
              onChange={(e) => {
                if (isActuating) return;
                setEmployeeId(e.target.value);
                if (status.type === 'error') setStatus({ type: 'idle', message: '' });
              }}
              disabled={isActuating}
              placeholder="e.g. ERP-1029"
              autoComplete="new-password"
              data-1p-ignore="true"
              data-lpignore="true"
              data-bwignore="true"
              data-nordpass-ignore="true"
              autoFocus
            />
          </div>
          <div className="erp-form-group">
            <label>Authorization Code</label>
            <input
              type="text"
              style={{ WebkitTextSecurity: 'disc' }}
              name="mwo_operator_pin"
              id="mwo_operator_pin"
              inputMode="numeric"
              value={pin}
              onChange={handlePinChange}
              disabled={isActuating}
              autoComplete="new-password"
              data-1p-ignore="true"
              data-lpignore="true"
              data-bwignore="true"
              data-nordpass-ignore="true"
              placeholder="••••"
            />
          </div>
          {status.type !== 'idle' && (
            <div className={`erp-status-message ${status.type}`}>
              {status.type === 'loading' ? 'Authenticating...' : status.message}
            </div>
          )}
          <button type="submit" className="erp-submit-btn" disabled={isActuating || pin.length < 4 || !employeeId.trim()}>
            Authorize Session
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
