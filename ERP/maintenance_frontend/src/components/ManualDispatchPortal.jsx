import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import api from '../services/api';

const ManualDispatchPortal = ({ mwo, onSuccess, onClose }) => {
    const [selectedHM, setSelectedHM] = useState('');
    const [employees, setEmployees] = useState([]);
    const [isActuating, setIsActuating] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchEmployees = async () => {
            try {
                // Relational lookup enforcing foreign key bounds
                const response = await api.get('/employees?role=HM&is_active=1');
                setEmployees(response.data.data || []);
            } catch (err) {
                console.error("Failed to fetch employees", err);
                setError("Failed to load HM roster.");
            }
        };
        fetchEmployees();
    }, []);

    const handleDispatch = async () => {
        if (!selectedHM) {
            setError("You must select an HM.");
            return;
        }
        setIsActuating(true);
        setError('');
        try {
            await api.patch(`/mwo/${mwo.mwo_id}/assign`, { assigned_hm_id: selectedHM });
            // Strict Doctrine: Await parent refresh before unmounting
            await onSuccess();
        } catch (error) {
            console.error("Actuation failed", error);
            setError(error.response?.data?.detail || "Failed to dispatch MWO.");
            setIsActuating(false); // Only release lock on failure
        }
    };

    const modalContent = (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                background: 'var(--bg-card, rgba(15, 23, 42, 0.95))',
                border: '1px solid var(--border, rgba(99, 102, 241, 0.3))',
                borderRadius: '12px', padding: '2rem', width: '400px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
                fontFamily: 'var(--font, Inter)'
            }}>
                <h3 style={{ marginTop: 0, color: 'var(--text-primary, #f8fafc)' }}>
                    Manual Dispatch
                </h3>
                <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.85rem' }}>
                    Assign MWO <strong style={{color: '#818cf8'}}>{mwo.mwo_id}</strong> to a verified HM.
                </p>

                {error && (
                    <div style={{
                        background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444',
                        padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem',
                        marginBottom: '1rem', border: '1px solid rgba(239, 68, 68, 0.2)'
                    }}>
                        {error}
                    </div>
                )}

                <div style={{ marginBottom: '2rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 600 }}>
                        Assign To (HM)
                    </label>
                    <select
                        value={selectedHM}
                        onChange={(e) => setSelectedHM(e.target.value)}
                        disabled={isActuating}
                        style={{
                            width: '100%', padding: '0.85rem', borderRadius: '6px',
                            background: 'rgba(15, 23, 42, 0.5)', color: '#f8fafc',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                            outline: 'none', cursor: isActuating ? 'not-allowed' : 'pointer'
                        }}
                    >
                        <option value="">-- Select Personnel --</option>
                        {employees.map(emp => (
                            <option key={emp.id} value={emp.id}>
                                {emp.name} ({emp.id})
                            </option>
                        ))}
                    </select>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                    <button
                        onClick={onClose}
                        disabled={isActuating}
                        style={{
                            background: 'transparent', color: '#94a3b8',
                            border: 'none', cursor: isActuating ? 'not-allowed' : 'pointer',
                            fontSize: '0.85rem', fontWeight: 600
                        }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleDispatch}
                        disabled={isActuating}
                        style={{
                            background: 'var(--accent-purple, #8b5cf6)', color: '#fff',
                            border: 'none', padding: '0.6rem 1.2rem', borderRadius: '6px',
                            cursor: isActuating ? 'not-allowed' : 'pointer',
                            opacity: isActuating ? 0.7 : 1, fontWeight: 600,
                            boxShadow: '0 4px 6px -1px rgba(139, 92, 246, 0.3)'
                        }}
                    >
                        {isActuating ? 'Actuating...' : 'Confirm Dispatch'}
                    </button>
                </div>
            </div>
        </div>
    );

    // Eject to document body to ensure it breaks out of parent stacking contexts
    return createPortal(modalContent, document.body);
};

export default ManualDispatchPortal;
