import React, { useState, useEffect } from 'react';
import api from '../services/api';

// Mock Dictionary for Relational Mapping
const EQUIPMENT_MAP = {
  "HVAC Roof Unit": "EQ-HVAC-01",
  "Breakroom Sink": "EQ-PLM-02",
  "Forklift A": "EQ-FL-01",
  "Server Rack Cooling": "EQ-IT-05"
};

const CreateMWOForm = ({ onMWOCreated }) => {
  const [mwoId, setMwoId] = useState('');
  const [description, setDescription] = useState('');
  const [equipmentDesc, setEquipmentDesc] = useState('');
  const [location, setLocation] = useState('');
  const [urgency, setUrgency] = useState('Normal');
  const [statusMsg, setStatusMsg] = useState('');

  // Auto-ID Generation on mount
  useEffect(() => {
    const month = String(new Date().getMonth() + 1).padStart(2, '0');
    const randomSeq = String(Math.floor(Math.random() * 999) + 1).padStart(3, '0');
    setMwoId(`RFK26-MWO-${month}-${randomSeq}`);
  }, []);

  const equipmentId = EQUIPMENT_MAP[equipmentDesc] || '';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatusMsg('Submitting...');
    try {
      await api.post('/mwo', {
        mwo_id: mwoId,
        description: description,
        equipment_id: equipmentId,
        location_id: location,
        urgency: urgency,
        status: 'PENDING_REVIEW'
      });
      setStatusMsg('Work Order created successfully.');
      
      // Reset logic & generate new ID
      const month = String(new Date().getMonth() + 1).padStart(2, '0');
      const randomSeq = String(Math.floor(Math.random() * 999) + 1).padStart(3, '0');
      setMwoId(`RFK26-MWO-${month}-${randomSeq}`);
      setDescription('');
      setEquipmentDesc('');
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

      <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff', marginBottom: '0.5rem' }}>Create Maintenance Work Order (DM)</h3>
      
      {/* Metadata Bar */}
      <div style={{ display: 'flex', gap: '1rem', color: '#94a3b8', fontSize: '0.8rem', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))', paddingBottom: '1.5rem', marginBottom: '1.5rem', fontWeight: '500' }}>
        <span>[ID: {mwoId}]</span>
        <span>|</span>
        <span>[Requester: DM-Alpha]</span>
        <span>|</span>
        <span>[Dept: Operations]</span>
      </div>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', alignItems: 'flex-start', width: '100%' }}>
        
        {/* Row 1: Equipment & Location & Urgency */}
        <div className="responsive-grid">
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.4rem' }}>
              <label style={{ ...labelStyle, marginBottom: 0, whiteSpace: 'nowrap' }}>Equipment Description</label>
              {equipmentId && <span style={{ fontSize: '0.65rem', color: '#818cf8', background: 'rgba(99, 102, 241, 0.15)', padding: '0.2rem 0.6rem', borderRadius: '12px', fontWeight: '600', whiteSpace: 'nowrap' }}>{equipmentId}</span>}
            </div>
            <select 
              value={equipmentDesc} 
              onChange={(e) => setEquipmentDesc(e.target.value)}
              className="modern-input"
              required
            >
              <option value="" disabled>Select Equipment...</option>
              {Object.keys(EQUIPMENT_MAP).map(desc => (
                <option key={desc} value={desc}>{desc}</option>
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
              <option value="LOC-A">LOC-A (Main Floor)</option>
              <option value="LOC-B">LOC-B (Warehouse)</option>
              <option value="LOC-C">LOC-C (Rooftop)</option>
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

        {/* Row 2: Description */}
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

        {/* Submit Row */}
        <div style={{ width: '100%', display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: '1.5rem', marginTop: '1rem' }}>
          <button type="submit" style={{ padding: '0.7rem 2rem', background: 'linear-gradient(145deg, #6366f1, #4338ca)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '700', fontSize: '0.9rem', transition: 'all 0.2s', boxShadow: '0 4px 6px rgba(0,0,0,0.4), inset 0 1px 1px rgba(255, 255, 255, 0.3)' }}>
            Submit MWO
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
