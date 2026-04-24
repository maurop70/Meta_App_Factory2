import React, { useState } from 'react';
import { useAuth } from '../context/MockAuthContext';
import MWODashboard from '../components/MWODashboard';
import CreateMWOForm from '../components/CreateMWOForm';

const AdminConsole = () => {
  const { userRole, logout } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);

  const handleMWOCreated = () => {
    setRefreshKey(prev => prev + 1);
  };
  
  return (
    <div className="factory-main" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', fontFamily: 'var(--font, Inter)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border, rgba(99,102,241,0.15))' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary, #e2e8f0)', marginBottom: '0.3rem' }}>Admin Command Console</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary, #94a3b8)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success, #10b981)', boxShadow: '0 0 8px rgba(16,185,129,0.5)' }}></span>
            Security clearance verified. Active Role: <span style={{ color: 'var(--accent-hover, #818cf8)', fontWeight: 600 }}>{userRole}</span>
          </div>
        </div>
        <button onClick={logout} className="action-btn" style={{ padding: '0.5rem 1rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger, #ef4444)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.8rem', fontWeight: 600 }}>
          Terminate Session
        </button>
      </div>
      
      <CreateMWOForm onMWOCreated={handleMWOCreated} />
      
      <div style={{ marginTop: '2rem' }}>
        <MWODashboard key={refreshKey} />
      </div>
    </div>
  );
};

export default AdminConsole;
