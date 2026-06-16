import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import TechDashboardComponent from '../components/TechDashboard';
import ProfileSettings from '../components/ProfileSettings';

const TechDashboard = () => {
  const { userRole, logout } = useAuth();
  const [showProfile, setShowProfile] = useState(false);

  return (
    <div className="factory-main maf-layout-grid">
      {showProfile && <ProfileSettings onClose={() => setShowProfile(false)} />}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.3rem' }}>Technician Dashboard</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 8px rgba(16,185,129,0.5)' }}></span>
            Floor access granted. Active Role: <span style={{ color: 'var(--accent-hover)', fontWeight: '600' }}>{userRole}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button onClick={() => setShowProfile(true)}
            style={{ padding: '0.5rem 1rem', background: 'rgba(99,102,241,0.1)', color: 'var(--accent-hover, #818cf8)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600' }}>
            Profile
          </button>
          <button
            onClick={logout}
            style={{ padding: '0.5rem 1rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.8rem', fontWeight: '600' }}
            onMouseOver={(e) => { e.target.style.background = 'rgba(239, 68, 68, 0.2)'; }}
            onMouseOut={(e) => { e.target.style.background = 'rgba(239, 68, 68, 0.1)'; }}
          >
            Terminate Session
          </button>
        </div>
      </div>
      <div style={{ marginTop: '2rem' }}>
        <TechDashboardComponent />
      </div>
    </div>
  );
};

export default TechDashboard;
