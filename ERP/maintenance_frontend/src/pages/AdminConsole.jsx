import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import CreateMWOForm from '../components/CreateMWOForm';
import MWODashboard from '../components/MWODashboard';
import AdminDataIngestion from '../components/AdminDataIngestion';
import EnterpriseDataMatrix from '../components/EnterpriseDataMatrix';

const AdminConsole = () => {
  const { userRole, logout } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState('ingestion');

  const handleMWOCreated = () => {
    setRefreshKey(prev => prev + 1);
  };

  const tabs = [
    { id: 'ingestion', label: 'Data Ingestion' },
    { id: 'dm', label: 'DM View' },
    { id: 'hm', label: 'HM View' },
    { id: 'tech', label: 'Tech View' }
  ];
  
  return (
    <div className="factory-main" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', fontFamily: 'var(--font, Inter)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border, rgba(99,102,241,0.15))' }}>
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

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              border: '1px solid',
              borderColor: activeTab === tab.id ? 'var(--accent, #6366f1)' : 'var(--border, rgba(99,102,241,0.15))',
              background: activeTab === tab.id ? 'rgba(99, 102, 241, 0.15)' : 'rgba(15, 23, 42, 0.5)',
              color: activeTab === tab.id ? 'var(--text-primary, #e2e8f0)' : 'var(--text-muted, #64748b)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem',
              transition: 'all 0.2s'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      
      {activeTab === 'ingestion' && (
        <>
          <AdminDataIngestion />
          <EnterpriseDataMatrix />
        </>
      )}
      
      {activeTab === 'dm' && (
        <CreateMWOForm onMWOCreated={handleMWOCreated} />
      )}
      
      {activeTab === 'hm' && (
        <MWODashboard key={refreshKey} />
      )}

      {activeTab === 'tech' && (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted, #64748b)', background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', borderRadius: '12px', border: '1px solid var(--border)' }}>
          Tech Dashboard Component Pending...
        </div>
      )}
      
    </div>
  );
};

export default AdminConsole;
