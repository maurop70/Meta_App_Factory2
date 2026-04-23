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
    <div style={{ padding: '10px', backgroundColor: '#222', color: '#fff', display: 'flex', gap: '15px', alignItems: 'center', borderBottom: '1px solid #444' }}>
      <strong style={{ color: '#00ffcc' }}>Mock Identity Injection:</strong>
      <span style={{ marginRight: '10px' }}>Active Persona: {userRole}</span>
      {roles.map(role => (
        <button
          key={role}
          onClick={() => setUserRole(role)}
          style={{
            padding: '5px 10px',
            backgroundColor: userRole === role ? '#0056b3' : '#444',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Inject {role}
        </button>
      ))}
    </div>
  );
};
