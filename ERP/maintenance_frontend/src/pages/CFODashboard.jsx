import React from 'react';
import { useAuth } from '../context/AuthContext';
import CFOApprovals from '../components/CFOApprovals';

/**
 * [BACK OFFICE INVENTORY] Gated landing page for the CFO role.
 * Hosts the purchase order approval queue.
 */
const CFODashboard = () => {
  const { userRole, jwtPayload, logout } = useAuth();

  return (
    <div className="factory-main" style={{ padding: '2rem', maxWidth: '1100px', margin: '0 auto', width: '100%', boxSizing: 'border-box', fontFamily: 'var(--font, Inter)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border, rgba(99,102,241,0.15))' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary, #e2e8f0)', marginBottom: '0.3rem' }}>CFO Approval Console</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary, #94a3b8)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success, #10b981)', boxShadow: '0 0 8px rgba(16,185,129,0.5)' }}></span>
            Financial actuation gateway. Active Role: <span style={{ color: 'var(--accent-hover, #818cf8)', fontWeight: 600 }}>{userRole}</span>
            <span style={{ color: '#475569' }}>· {jwtPayload?.sub}</span>
          </div>
        </div>
        <button onClick={logout} className="action-btn" style={{ padding: '0.5rem 1rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger, #ef4444)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.8rem', fontWeight: 600 }}>
          Terminate Session
        </button>
      </div>

      <CFOApprovals />
    </div>
  );
};

export default CFODashboard;
