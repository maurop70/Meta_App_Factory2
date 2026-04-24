import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext();

export const MockAuthProvider = ({ children }) => {
  const [userRole, setUserRole] = useState(localStorage.getItem('userRole') || 'Tech-Alpha');

  const setAndSaveUserRole = (role) => {
    localStorage.setItem('userRole', role);
    setUserRole(role);
  };

  return (
    <AuthContext.Provider value={{ userRole, setUserRole: setAndSaveUserRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

export const LoginSimulator = () => {
  const { userRole, setUserRole } = useAuth();

  const roles = ['HM (Admin)', 'Tech-Alpha', 'Tech-Bravo'];

  return (
    <div style={{ padding: '12px 20px', background: 'rgba(10, 14, 23, 0.95)', color: 'var(--text-primary)', display: 'flex', gap: '15px', alignItems: 'center', borderBottom: '1px solid var(--border)', backdropFilter: 'blur(12px)' }}>
      <strong style={{ color: 'var(--accent)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mock Identity Injection:</strong>
      <span style={{ marginRight: '10px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Active Persona: <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>{userRole}</span></span>
      <div style={{ display: 'flex', gap: '8px' }}>
        {roles.map(role => (
          <button
            key={role}
            onClick={() => setUserRole(role)}
            onMouseOver={(e) => { if(userRole !== role) e.target.style.background = 'rgba(99, 102, 241, 0.2)'; }}
            onMouseOut={(e) => { if(userRole !== role) e.target.style.background = 'rgba(15, 23, 42, 0.6)'; }}
            style={{
              padding: '6px 12px',
              backgroundColor: userRole === role ? 'var(--accent)' : 'rgba(15, 23, 42, 0.6)',
              color: userRole === role ? '#fff' : 'var(--text-secondary)',
              border: `1px solid ${userRole === role ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '0.8rem',
              transition: 'all 0.2s ease',
              fontWeight: '500'
            }}
          >
            Inject {role}
          </button>
        ))}
      </div>
    </div>
  );
};
