import React, { useState } from 'react';
import api from '../services/api';

const CreateMWOForm = ({ onMWOCreated }) => {
  const [mwoId, setMwoId] = useState('');
  const [description, setDescription] = useState('');
  const [assignedTech, setAssignedTech] = useState('Tech-Alpha');
  const [statusMsg, setStatusMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatusMsg('Submitting...');
    try {
      await api.post('/api/mwo', {
        mwo_id: mwoId,
        description: description,
        assigned_tech: assignedTech,
        status: 'PENDING_REVIEW'
      });
      setStatusMsg('Work Order created successfully.');
      setMwoId('');
      setDescription('');
      setAssignedTech('Tech-Alpha');
      if (onMWOCreated) {
        onMWOCreated();
      }
    } catch (err) {
      console.error(err);
      setStatusMsg('Failed to create Work Order. ' + (err.response?.data?.detail || err.message));
    }
  };

  const inputStyle = {
    width: '100%', padding: '0.6rem 1rem', borderRadius: '8px', 
    border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', 
    background: 'rgba(15, 23, 42, 0.6)', color: 'var(--text-primary, #e2e8f0)', 
    fontSize: '0.85rem', outline: 'none', transition: 'border 0.2s', fontFamily: 'var(--font, Inter)'
  };
  const labelStyle = {
    display: 'block', fontSize: '0.75rem', textTransform: 'uppercase', 
    letterSpacing: '0.05em', color: 'var(--text-muted, #64748b)', marginBottom: '0.4rem'
  };

  return (
    <div style={{ background: 'var(--bg-card, rgba(15, 23, 42, 0.85))', border: '1px solid var(--border, rgba(99, 102, 241, 0.15))', borderRadius: '12px', padding: '1.5rem', backdropFilter: 'blur(8px)', marginTop: '20px', fontFamily: "var(--font, Inter)" }}>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary, #e2e8f0)', marginBottom: '1rem', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border, rgba(99, 102, 241, 0.15))' }}>New Work Order</h3>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.2rem', alignItems: 'end' }}>
        <div>
          <label htmlFor="mwoId" style={labelStyle}>Work Order ID (Asset ID):</label>
          <input 
            id="mwoId"
            name="mwoId"
            type="text" 
            value={mwoId} 
            onChange={(e) => setMwoId(e.target.value)} 
            placeholder="e.g., AUTO-QA-003"
            style={inputStyle}
            required
          />
        </div>
        <div>
          <label htmlFor="assignedTech" style={labelStyle}>Assigned Tech:</label>
          <select 
            id="assignedTech"
            name="assignedTech"
            value={assignedTech} 
            onChange={(e) => setAssignedTech(e.target.value)}
            style={inputStyle}
          >
            <option value="Tech-Alpha">Tech-Alpha</option>
            <option value="Tech-Bravo">Tech-Bravo</option>
            <option value="AY-Agent">AY-Agent</option>
          </select>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label htmlFor="description" style={labelStyle}>Description (SKU / Issue):</label>
          <textarea 
            id="description"
            name="description"
            value={description} 
            onChange={(e) => setDescription(e.target.value)} 
            placeholder="e.g., dummy SKU"
            style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
            required
          />
        </div>
        <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '1rem' }}>
          {statusMsg && <span style={{ fontSize: '0.8rem', color: statusMsg.includes('Failed') ? 'var(--danger, #ef4444)' : 'var(--success, #10b981)' }}>{statusMsg}</span>}
          <button type="submit" id="submitBtn" style={{ padding: '0.6rem 1.5rem', background: 'linear-gradient(135deg, var(--accent, #6366f1), #7c3aed)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem', transition: 'all 0.2s', boxShadow: '0 4px 15px var(--accent-glow, rgba(99, 102, 241, 0.25))' }}>
            Submit MWO
          </button>
        </div>
      </form>
    </div>
  );
};

export default CreateMWOForm;
