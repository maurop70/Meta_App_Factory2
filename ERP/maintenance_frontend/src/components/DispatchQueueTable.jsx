import React, { useState, useEffect } from 'react';
import api from '../services/api';
import ManualDispatchPortal from './ManualDispatchPortal';
import { useAuth } from '../context/AuthContext';
import './EnterpriseDataMatrix.css';

const DispatchQueueTable = () => {
    const { userRole, jwtPayload } = useAuth();
    const currentUserId = jwtPayload?.sub || 'Unknown DM';
    const [dmRoster, setDmRoster] = useState([]);
    const [targetDm, setTargetDm] = useState('');

    const [queue, setQueue] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(true);
    const [selectedMwo, setSelectedMwo] = useState(null);

    const LIMIT = 25;

    useEffect(() => {
        if (['ADMINISTRATOR', 'ADMIN'].includes(userRole)) {
            const fetchDms = async () => {
                try {
                    const response = await api.get('/employees?role=DM&is_active=1');
                    setDmRoster(response.data.data || []);
                } catch (err) {
                    console.error("Failed to fetch DM roster", err);
                }
            };
            fetchDms();
        }
    }, [userRole]);

    const fetchQueue = async () => {
        setLoading(true);
        try {
            const url = targetDm 
                ? `/work-orders/queue?status=UNASSIGNED_ESCALATION&limit=${LIMIT}&offset=${page * LIMIT}&target_dm=${encodeURIComponent(targetDm)}` 
                : `/work-orders/queue?status=UNASSIGNED_ESCALATION&limit=${LIMIT}&offset=${page * LIMIT}`;
            const response = await api.get(url);
            setQueue(response.data.data || []);
            setTotalCount(response.data.total_count || 0);
        } catch (err) {
            console.error("Failed to fetch queue", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchQueue();
    }, [page, targetDm]);

    const handleSuccess = async () => {
        await fetchQueue();
        setSelectedMwo(null); // Teardown only AFTER state refresh
    };

    return (
        <div className="dispatch-queue-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0, color: 'var(--text-primary, #f8fafc)', fontSize: '1.2rem' }}>
                    Central Dispatch Queue
                </h3>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.4rem 0.8rem', borderRadius: '6px', color: '#38bdf8', fontWeight: 600, fontSize: '0.85rem' }}>
                        DM ID: {currentUserId}
                    </div>
                </div>
            </div>
            
            {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
                    Synchronizing Queue Matrix...
                </div>
            ) : (
                <>
                    <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <table className="erp-data-matrix">
                            <thead>
                                <tr style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
                                    <th>MWO ID</th>
                                    <th>Status</th>
                                    <th>Urgency</th>
                                    <th>Equipment</th>
                                    <th>Created</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {queue.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                                            No unassigned work orders in queue.
                                        </td>
                                    </tr>
                                ) : (
                                    queue.map(order => (
                                        <tr key={order.mwo_id}>
                                            <td data-label="MWO ID" style={{ color: '#818cf8', fontWeight: 600 }}>{order.mwo_id}</td>
                                            <td data-label="STATUS">
                                                <span style={{ 
                                                    padding: '4px 10px', borderRadius: '12px', fontSize: '0.7rem', 
                                                    fontWeight: 600, background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444',
                                                    textTransform: 'uppercase'
                                                }}>
                                                    {order.status}
                                                </span>
                                            </td>
                                            <td data-label="URGENCY">
                                                <span style={{ 
                                                    padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', 
                                                    fontWeight: 600, color: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? '#fbbf24' : '#94a3b8' 
                                                }}>
                                                    {order.dm_urgency}
                                                </span>
                                            </td>
                                            <td data-label="EQUIPMENT" style={{ color: '#cbd5e1' }}>{order.equipment_id}</td>
                                            <td data-label="CREATED" style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>
                                                {new Date(order.created_at).toLocaleDateString()}
                                            </td>
                                            <td data-label="ACTION">
                                                <button 
                                                    className="dispatch-btn"
                                                    onClick={() => setSelectedMwo(order)}
                                                >
                                                    Dispatch
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>

                        <div className="mobile-kv-card-container">
                            {queue.length === 0 ? (
                                <div className="mobile-kv-card" style={{ opacity: 0.7 }}>
                                    <div className="mobile-kv-row">
                                        <span className="mobile-kv-label">Queue Status</span>
                                        <span className="mobile-kv-value" style={{ color: '#64748b' }}>No unassigned work orders in queue.</span>
                                    </div>
                                    <div className="mobile-kv-row" style={{ marginTop: '0.5rem' }}>
                                        <button className="dispatch-btn" style={{ width: '100%', padding: '0.75rem' }} disabled>
                                            Manage Dispatch
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                queue.map(order => (
                                    <div key={order.mwo_id} className="mobile-kv-card">
                                        <div className="mobile-kv-row">
                                            <span className="mobile-kv-label">MWO ID</span>
                                            <span className="mobile-kv-value" style={{ color: '#818cf8', fontWeight: 600 }}>{order.mwo_id}</span>
                                        </div>
                                        <div className="mobile-kv-row">
                                            <span className="mobile-kv-label">Status</span>
                                            <span className="mobile-kv-value">
                                                <span style={{ 
                                                    padding: '4px 10px', borderRadius: '12px', fontSize: '0.7rem', 
                                                    fontWeight: 600, background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444',
                                                    textTransform: 'uppercase'
                                                }}>
                                                    {order.status}
                                                </span>
                                            </span>
                                        </div>
                                        <div className="mobile-kv-row">
                                            <span className="mobile-kv-label">Urgency</span>
                                            <span className="mobile-kv-value">
                                                <span style={{ 
                                                    padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', 
                                                    fontWeight: 600, color: order.dm_urgency === 'High' || order.dm_urgency === 'Critical' ? '#fbbf24' : '#94a3b8' 
                                                }}>
                                                    {order.dm_urgency}
                                                </span>
                                            </span>
                                        </div>
                                        <div className="mobile-kv-row">
                                            <span className="mobile-kv-label">Equipment</span>
                                            <span className="mobile-kv-value" style={{ color: '#cbd5e1' }}>{order.equipment_id}</span>
                                        </div>
                                        <div className="mobile-kv-row">
                                            <span className="mobile-kv-label">Created</span>
                                            <span className="mobile-kv-value" style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>
                                                {new Date(order.created_at).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div className="mobile-kv-row" style={{ marginTop: '0.5rem' }}>
                                            <button 
                                                className="dispatch-btn"
                                                style={{ width: '100%', padding: '0.75rem' }}
                                                onClick={() => setSelectedMwo(order)}
                                            >
                                                Manage Dispatch
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    <div className="dispatch-pagination">
                        <button 
                            className="dispatch-btn" 
                            disabled={page === 0} 
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                        >
                            Previous
                        </button>
                        <span style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>
                            Page {page + 1} <span style={{ opacity: 0.6, fontWeight: 400 }}>({totalCount} Total)</span>
                        </span>
                        <button 
                            className="dispatch-btn" 
                            disabled={(page + 1) * LIMIT >= totalCount} 
                            onClick={() => setPage(p => p + 1)}
                        >
                            Next
                        </button>
                    </div>
                </>
            )}

            {selectedMwo && (
                <ManualDispatchPortal
                    mwo={selectedMwo}
                    onSuccess={handleSuccess}
                    onClose={() => setSelectedMwo(null)}
                />
            )}
        </div>
    );
};

export default DispatchQueueTable;
