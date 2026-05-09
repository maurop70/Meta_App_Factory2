import React, { useState, useEffect } from 'react';
import api from '../services/api';
import ProcurementActuationModal from './ProcurementActuationModal';
import './EnterpriseDataMatrix.css';

const ProcurementMatrix = () => {
    const [procurements, setProcurements] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [activeProcurement, setActiveProcurement] = useState(null);

    const fetchProcurements = async () => {
        setIsLoading(true);
        setError(null);
        try {
            // Strict Pagination Transit
            const response = await api.get('/admin/procurement?limit=50&offset=0');
            setProcurements(response.data.items || response.data.data || []);
        } catch (err) {
            console.error('Matrix extraction failed:', err);
            setError('Failed to synchronize procurement ledger.');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchProcurements();
    }, []);

    const getStatusStyle = (status) => {
        switch(status) {
            case 'PENDING': return 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/50';
            case 'APPROVED': return 'bg-blue-500/20 text-blue-300 border border-blue-500/50';
            case 'FULFILLED': return 'bg-green-500/20 text-green-300 border border-green-500/50';
            case 'REJECTED': return 'bg-red-500/20 text-red-300 border border-red-500/50';
            default: return 'bg-gray-500/20 text-gray-300';
        }
    };

    return (
        <div className="w-full bg-[#1A1F2E] border border-gray-800 rounded-xl overflow-hidden shadow-2xl animate-fade-in">
            <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gradient-to-r from-[#1E2538] to-[#1A1F2E]">
                <div>
                    <h2 className="text-xl font-bold text-gray-100 flex items-center gap-3">
                        <span className="w-2 h-6 bg-purple-500 rounded-full"></span>
                        Procurement Authorization Queue
                    </h2>
                    <p className="text-sm text-gray-400 mt-1">Manage physical supply chain inventory requests.</p>
                </div>
                <button 
                    onClick={fetchProcurements}
                    disabled={isLoading}
                    className="px-4 py-2 bg-[#252D40] hover:bg-[#2D3748] text-gray-300 rounded-lg transition-colors text-sm font-medium border border-gray-700 disabled:opacity-50"
                >
                    Refresh Matrix
                </button>
            </div>

            {error && (
                <div className="m-6 p-4 bg-red-900/20 border border-red-500/50 text-red-400 rounded-lg text-sm">
                    {error}
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="erp-data-matrix">
                    <thead>
                        <tr className="bg-[#151925] text-xs uppercase tracking-wider text-gray-500 border-b border-gray-800">
                            <th className="p-4 font-medium">Triggered At</th>
                            <th className="p-4 font-medium">Part ID / Nomenclature</th>
                            <th className="p-4 font-medium text-right">QOH / Threshold</th>
                            <th className="p-4 font-medium text-right">Unit Cost</th>
                            <th className="p-4 font-medium text-center">Status</th>
                            <th className="p-4 font-medium text-center">Actuation</th>
                        </tr>
                    </thead>
                    <tbody className="text-sm text-gray-300 divide-y divide-gray-800">
                        {isLoading ? (
                            <tr><td colSpan="6" className="p-8 text-center text-gray-500">Extracting Ledger...</td></tr>
                        ) : procurements.length === 0 ? (
                            <tr><td colSpan="6" className="p-8 text-center text-gray-500">Procurement queue is clear.</td></tr>
                        ) : (
                            procurements.map((proc) => (
                                <tr key={proc.procurement_id} className="hover:bg-[#1E2538] transition-colors group">
                                    <td data-label="Triggered At" className="p-4 text-gray-400">
                                        {new Date(proc.triggered_at).toLocaleString()}
                                    </td>
                                    <td data-label="Part ID / Nomenclature" className="p-4">
                                        <div className="font-medium text-gray-200">{proc.nomenclature}</div>
                                        <div className="text-xs text-gray-500 mt-0.5">{proc.part_id}</div>
                                    </td>
                                    <td data-label="QOH / Threshold" className="p-4 text-right">
                                        <span className={`font-mono ${proc.quantity_on_hand <= proc.reorder_threshold ? 'text-red-400 font-bold' : 'text-gray-300'}`}>
                                            {proc.quantity_on_hand}
                                        </span>
                                        <span className="text-gray-600 mx-1">/</span>
                                        <span className="text-gray-500 font-mono">{proc.reorder_threshold}</span>
                                    </td>
                                    <td data-label="Unit Cost" className="p-4 text-right font-mono text-emerald-400">
                                        ${proc.unit_cost.toFixed(2)}
                                    </td>
                                    <td data-label="Status" className="p-4 text-center">
                                        <span className={`px-2 py-1 rounded text-xs font-semibold tracking-wider ${getStatusStyle(proc.status)}`}>
                                            {proc.status}
                                        </span>
                                    </td>
                                    <td data-label="Actuation" className="p-4 text-center">
                                        <button
                                            onClick={() => setActiveProcurement(proc)}
                                            className="px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 rounded transition-colors text-xs font-medium border border-indigo-500/20 uppercase tracking-wider"
                                        >
                                            View Payload
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {activeProcurement && (
                <ProcurementActuationModal
                    procurement={activeProcurement}
                    onClose={() => setActiveProcurement(null)}
                    onSuccess={() => {
                        setActiveProcurement(null);
                        fetchProcurements();
                    }}
                />
            )}
        </div>
    );
};

export default ProcurementMatrix;
