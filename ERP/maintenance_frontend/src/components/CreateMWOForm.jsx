import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const CreateMWOForm = ({ onMWOCreated }) => {
  const [description, setDescription] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [location, setLocation] = useState('');
  const [urgency, setUrgency] = useState('Normal');
  const [statusMsg, setStatusMsg] = useState('');
  const [equipments, setEquipments] = useState([]);
  const [locations, setLocations] = useState([]);
  const [personnel, setPersonnel] = useState([]);
  const [impersonatedCreatorId, setImpersonatedCreatorId] = useState('');

  const { userRole, jwtPayload } = useAuth();
  const currentUserId = jwtPayload?.sub || 'Unknown DM';
  const currentUserName = jwtPayload?.name || 'Unknown DM';

  const navigate = useNavigate();

  useEffect(() => {
    const fetchLookups = async () => {
      try {
        // Decoupled promise chain: one failing lookup (RBAC / connectivity)
        // degrades to an empty list instead of rejecting every dropdown.
        const safeGet = (path) => api.get(path).catch(err => {
          console.warn(`Lookup degraded for ${path}:`, err.response?.status || err.message);
          return { data: { data: [] } };
        });
        const [eqRes, locRes, personnelRes] = await Promise.all([
          safeGet('/admin/equipment'),
          safeGet('/admin/lookups/locations'),
          safeGet('/dm/personnel')
        ]);
        setEquipments(eqRes.data.data || []);
        setLocations(locRes.data.data || []);
        
        const personnelData = personnelRes.data.data || [];
        // Ensure the current DM is in the list for selection
        if (!personnelData.find(p => p.id === currentUserId)) {
          personnelData.unshift({ id: currentUserId, name: `${currentUserName} (Myself)` });
        }
        setPersonnel(personnelData);
        setImpersonatedCreatorId(currentUserId); // Default to self

      } catch (err) {
        console.error("Failed to load dynamic dropdowns", err);
      }
    };

    fetchLookups();
  }, [currentUserId, currentUserName]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatusMsg('Submitting...');
    try {
      await api.post('/mwo', {
        description: description,
        equipment_id: equipmentId,
        location_id: location,
        urgency: urgency,
        status: 'PENDING_REVIEW',
        impersonated_creator_id: impersonatedCreatorId === currentUserId ? null : impersonatedCreatorId
      });
      setStatusMsg('Work Order created successfully.');
      
      setDescription('');
      setEquipmentId('');
      setLocation('');
      setUrgency('Normal');
      
      if (onMWOCreated) onMWOCreated();
    } catch (err) {
      console.error(err);
      setStatusMsg('Failed to create Work Order. ' + (err.response?.data?.detail || err.message));
    }
  };

  const labelStyle = {
    display: 'block', textAlign: 'left', fontSize: '0.75rem', textTransform: 'uppercase', 
    letterSpacing: '0.05em', color: '#ffffff', marginBottom: '0.4rem', fontWeight: '600'
  };
  
  const selectedUser = personnel.find(p => p.id === impersonatedCreatorId);

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', fontFamily: "var(--font, Inter)", maxWidth: '800px', margin: '0 auto', textAlign: 'left' }}>
      
      <style>{`
        .modern-input {
          width: 100%;
          padding: 0.6rem 1rem;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          background: rgba(255, 255, 255, 0.04);
          color: var(--text-primary, #e2e8f0);
          font-size: 0.85rem;
          outline: none;
          transition: border-color 0.2s;
          font-family: var(--font, Inter);
        }
        .modern-input:focus {
          border-color: #6366f1;
        }
        .modern-input option {
          background-color: #0f172a;
          color: #e2e8f0;
        }
        .responsive-grid {
          display: grid;
          grid-template-columns: 1.5fr 1fr 1fr;
          gap: 1.5rem;
          width: 100%;
        }
        @media (max-width: 800px) {
          .responsive-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff', margin: 0 }}>Create Maintenance Work Order (DM)</h3>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', color: '#94a3b8', fontSize: '0.8rem', fontWeight: '500', alignItems: 'center' }}>
          <span>[DM: {currentUserName}]</span>
          {impersonatedCreatorId !== currentUserId && selectedUser && (
            <>
              <span>|</span>
              <span style={{ color: '#fbbf24', fontWeight: 700 }}>Acting as: {selectedUser.name}</span>
            </>
          )}
        </div>
        <div>
          <label style={{...labelStyle, marginBottom: '0.2rem', fontSize: '0.65rem'}}>Submit As:</label>
          <select 
            value={impersonatedCreatorId} 
            onChange={(e) => setImpersonatedCreatorId(e.target.value)}
            className="modern-input"
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
          >
            {personnel.map(p => (
              <option key={p.id} value={p.id}>{p.name}{p.id === currentUserId ? ' (Myself)' : ''}</option>
            ))}
          </select>
        </div>
      </div>
      
      {impersonatedCreatorId !== currentUserId && selectedUser && (
        <div style={{ width: '100%', background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.3)', color: '#fbbf24', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.85rem', fontWeight: 600 }}>
          ⚠️ Acting as: {selectedUser.name}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', alignItems: 'flex-start', width: '100%' }}>
        
        <div className="responsive-grid">
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.4rem' }}>
              <label style={{ ...labelStyle, marginBottom: 0, whiteSpace: 'nowrap' }}>Equipment</label>
              {equipmentId && <span style={{ fontSize: '0.65rem', color: '#818cf8', background: 'rgba(99, 102, 241, 0.15)', padding: '0.2rem 0.6rem', borderRadius: '12px', fontWeight: '600', whiteSpace: 'nowrap' }}>{equipmentId}</span>}
            </div>
            <select 
              value={equipmentId} 
              onChange={(e) => {
                const selectedEqId = e.target.value;
                setEquipmentId(selectedEqId);
                const selectedEq = equipments.find(eq => eq.equipment_id === selectedEqId);
                if (selectedEq && selectedEq.location_id) {
                  setLocation(selectedEq.location_id);
                }
              }}
              className="modern-input"
              required
            >
              <option value="" disabled>Select Equipment...</option>
              {equipments.map(eq => (
                <option key={eq.equipment_id} value={eq.equipment_id}>
                  {eq.nomenclature} (Loc: {eq.location_name || 'N/A'})
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label style={labelStyle}>Location</label>
            <select 
              value={location} 
              onChange={(e) => setLocation(e.target.value)}
              className="modern-input"
              required
            >
              <option value="" disabled>Select Location...</option>
              {locations.map(loc => (
                <option key={loc.id} value={loc.id}>{loc.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={labelStyle}>URGENCY LEVEL</label>
            <select 
              value={urgency} 
              onChange={(e) => setUrgency(e.target.value)}
              className="modern-input"
              required
            >
              <option value="Low">Low</option>
              <option value="Normal">Normal</option>
              <option value="High">High</option>
              <option value="Critical">Critical</option>
            </select>
          </div>
        </div>

        <div style={{ width: '100%' }}>
          <label style={labelStyle}>Issue Description</label>
          <textarea 
            value={description} 
            onChange={(e) => setDescription(e.target.value)} 
            placeholder="Describe the issue in detail..."
            className="modern-input"
            style={{ minHeight: '100px', resize: 'vertical' }}
            required
          />
        </div>

        <div style={{ width: '100%', display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: '1.5rem', marginTop: '1rem' }}>
          <button type="submit" style={{ padding: '0.7rem 2rem', background: 'linear-gradient(145deg, #6366f1, #4338ca)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '700', fontSize: '0.9rem', transition: 'all 0.2s', boxShadow: '0 4px 6px rgba(0,0,0,0.4), inset 0 1px 1px rgba(255, 255, 255, 0.3)' }}>
            Submit MWO
          </button>
          
          <button type="button" onClick={() => navigate('/archive')} style={{ padding: '0.7rem 2rem', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '8px', cursor: 'pointer', fontWeight: '700', fontSize: '0.9rem', transition: 'all 0.2s' }}>
            View Archives
          </button>

          {statusMsg && (
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: statusMsg.includes('Failed') ? 'var(--danger, #ef4444)' : 'var(--success, #10b981)' }}>{statusMsg}</span>
          )}
        </div>
      </form>
    </div>
  );
};

export default CreateMWOForm;
