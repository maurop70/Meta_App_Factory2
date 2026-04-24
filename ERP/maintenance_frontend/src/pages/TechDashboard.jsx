import React from 'react';
import { useAuth } from '../context/MockAuthContext';
import TechDashboardComponent from '../components/TechDashboard';

const TechDashboard = () => {
  const { userRole, logout } = useAuth();
  
  return (
    <div className="factory-main maf-layout-grid">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.3rem' }}>Technician Dashboard</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 8px rgba(16,185,129,0.5)' }}></span>
            Floor access granted. Active Role: <span style={{ color: 'var(--accent-hover)', fontWeight: '600' }}>{userRole}</span>
          </div>
        </div>
        <button 
          onClick={logout} 
          style={{ padding: '0.5rem 1rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.8rem', fontWeight: '600' }}
          onMouseOver={(e) => { e.target.style.background = 'rgba(239, 68, 68, 0.2)'; }}
          onMouseOut={(e) => { e.target.style.background = 'rgba(239, 68, 68, 0.1)'; }}
        >
          Terminate Session
        </button>
      </div>
      <div style={{ marginTop: '2rem' }}>
        <TechDashboardComponent />
      </div>
    </div>
  );
};

export default TechDashboard;
