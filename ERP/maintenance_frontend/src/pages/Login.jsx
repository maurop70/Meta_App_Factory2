import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AUTH_API_BASE_URL } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DEVICE_ID_KEY = 'mwo_device_id';

// Stable per-browser/per-device identifier. Stored in localStorage so it
// survives reloads; clearing storage reverts the device to "unrecognized".
function getDeviceId() {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : `dev-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

const deviceType = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ? 'mobile' : 'desktop';

const Login = () => {
  const { authenticateContext } = useAuth();
  const navigate = useNavigate();

  const [booted, setBooted] = useState(false);
  const [recognized, setRecognized] = useState(null); // { name, role, department }
  const [identifier, setIdentifier] = useState('');
  const [pin, setPin] = useState('');
  const [remember, setRemember] = useState(false);
  const [status, setStatus] = useState({ type: 'idle', message: '' });
  const [isActuating, setIsActuating] = useState(false);

  // On load, ask the gateway whether this device is already mapped to a user.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${AUTH_API_BASE_URL}/v1/auth/recognize-device`, {
          params: { device_id: getDeviceId() },
        });
        if (!cancelled && data?.recognized) setRecognized(data);
      } catch {
        /* recognition is best-effort; fall back to standard login */
      } finally {
        if (!cancelled) setBooted(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const finishLogin = (accessToken) => {
    const payloadBase64 = accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(payloadBase64));
    authenticateContext(accessToken, payload.role, payload);
    navigate('/', { replace: true });
  };

  const handlePinChange = (e) => {
    if (isActuating) return;
    setPin(e.target.value.replace(/[^0-9]/g, ''));
    if (status.type === 'error') setStatus({ type: 'idle', message: '' });
  };

  // Recognized-device quick login: send only device_id + pin. The gateway
  // resolves the employee server-side, so no identity is exposed to the DOM.
  const handleRecognizedSubmit = async (e) => {
    e.preventDefault();
    if (isActuating) return;
    if (pin.length < 4) {
      setStatus({ type: 'error', message: 'Enter your PIN.' });
      return;
    }
    setStatus({ type: 'loading', message: '' });
    setIsActuating(true);
    try {
      const response = await axios.post(
        `${AUTH_API_BASE_URL}/v1/auth/login`,
        { device_id: getDeviceId(), pin },
        { withCredentials: true }
      );
      finishLogin(response.data.access_token);
    } catch (err) {
      setIsActuating(false);
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Authentication failed.' });
    }
  };

  const handleStandardSubmit = async (e) => {
    e.preventDefault();
    if (isActuating) return;
    if (!identifier.trim()) {
      setStatus({ type: 'error', message: 'An identifier is required.' });
      return;
    }
    if (pin.length < 4) {
      setStatus({ type: 'error', message: 'Authorization PIN is required.' });
      return;
    }
    setStatus({ type: 'loading', message: '' });
    setIsActuating(true);
    try {
      const response = await axios.post(
        `${AUTH_API_BASE_URL}/v1/auth/login`,
        { emp_id: identifier.trim(), pin },
        { withCredentials: true }
      );
      const accessToken = response.data.access_token;

      // Register this device for future quick logins, if requested.
      if (remember) {
        try {
          await axios.post(
            `${AUTH_API_BASE_URL}/v1/auth/register-device`,
            { device_id: getDeviceId(), device_name: navigator.platform || 'Browser', device_type: deviceType },
            { headers: { Authorization: `Bearer ${accessToken}` }, withCredentials: true }
          );
        } catch {
          /* non-fatal: login still proceeds even if device registration fails */
        }
      }
      finishLogin(accessToken);
    } catch (err) {
      setIsActuating(false);
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Authentication failed. Please verify credentials.' });
    }
  };

  const switchAccount = () => {
    setRecognized(null);
    setPin('');
    setStatus({ type: 'idle', message: '' });
  };

  const statusBlock = status.type !== 'idle' && (
    <div className={`erp-status-message ${status.type}`}>
      {status.type === 'loading' ? 'Authenticating...' : status.message}
    </div>
  );

  // Avoid flashing the standard form before recognition resolves.
  if (!booted) {
    return (
      <div className="erp-login-container">
        <div className="erp-login-card"><p>Initializing secure gateway…</p></div>
      </div>
    );
  }

  if (recognized) {
    return (
      <div className="erp-login-container">
        <div className="erp-login-card">
          <h2>Welcome back</h2>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-h)' }}>{recognized.name}</p>
          {recognized.role && <p style={{ color: 'var(--text-muted)' }}>{recognized.role}{recognized.department ? ` · ${recognized.department}` : ''}</p>}
          <form onSubmit={handleRecognizedSubmit} className="erp-login-form" autoComplete="off">
            <div className="erp-form-group">
              <label>Enter your PIN</label>
              <input
                type="text"
                style={{ WebkitTextSecurity: 'disc' }}
                inputMode="numeric"
                value={pin}
                onChange={handlePinChange}
                disabled={isActuating}
                autoComplete="new-password"
                placeholder="••••"
                autoFocus
              />
            </div>
            {statusBlock}
            <button type="submit" className="erp-submit-btn" disabled={isActuating || pin.length < 4}>
              Authorize
            </button>
          </form>
          <button type="button" onClick={switchAccount}
            style={{ marginTop: '1rem', background: 'none', border: 'none', color: 'var(--accent, #6366f1)', cursor: 'pointer', textDecoration: 'underline' }}>
            Switch Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="erp-login-container">
      <div className="erp-login-card">
        <h2>Maintenance Command</h2>
        <p>Restricted Access Gateway</p>
        <form onSubmit={handleStandardSubmit} className="erp-login-form" autoComplete="off">
          {/* Extension Honeypot: Force extensions to hook here instead of active inputs */}
          <div style={{ position: 'absolute', left: '-9999px', top: '-9999px' }} aria-hidden="true">
            <input type="text" name="honeypot_user" autoComplete="username" tabIndex="-1" />
            <input type="password" name="honeypot_pass" autoComplete="current-password" tabIndex="-1" />
          </div>

          <div className="erp-form-group">
            <label>Username / Phone / Employee ID</label>
            <input
              type="text"
              name="mwo_operator_id"
              id="mwo_operator_id"
              value={identifier}
              onChange={(e) => {
                if (isActuating) return;
                setIdentifier(e.target.value);
                if (status.type === 'error') setStatus({ type: 'idle', message: '' });
              }}
              disabled={isActuating}
              placeholder="e.g. ERP-1029, tech1, or 5550199"
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

          <label className="erp-remember-device" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center', margin: '0.5rem 0', cursor: 'pointer', fontSize: '0.9rem' }}>
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} disabled={isActuating} />
            Remember this PC / cell phone
          </label>

          {statusBlock}
          <button type="submit" className="erp-submit-btn" disabled={isActuating || pin.length < 4 || !identifier.trim()}>
            Authorize Session
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
