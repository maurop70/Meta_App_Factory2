import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const ProcurementActuationModal = ({ procurement, onClose, onSuccess }) => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState('');
    
    const [targetStatus, setTargetStatus] = useState('');
    const [authorizedQuantity, setAuthorizedQuantity] = useState('');

    // Determine available transitions
    const availableTransitions = [];
    if (procurement.status === 'PENDING') {
        availableTransitions.push('APPROVED', 'REJECTED');
    } else if (procurement.status === 'APPROVED') {
        availableTransitions.push('FULFILLED');
    }

    // Default target selection logic
    useEffect(() => {
        if (availableTransitions.length > 0) {
            setTargetStatus(availableTransitions[0]);
        }
    }, []);

    const totalExpenditure = targetStatus === 'APPROVED' && authorizedQuantity 
        ? (parseInt(authorizedQuantity) * procurement.unit_cost).toFixed(2)
        : '0.00';

    const handleActuation = async () => {
        if (!targetStatus) return;
        
        if (targetStatus === 'APPROVED' && (!authorizedQuantity || parseInt(authorizedQuantity) < 1)) {
            setError('Authorized quantity must be at least 1.');
            return;
        }

        setIsProcessing(true);
        setError('');

        try {
            const payload = { status: targetStatus };
            if (targetStatus === 'APPROVED') {
                payload.authorized_quantity = parseInt(authorizedQuantity, 10);
            }
            
            await api.put(`/admin/procurement/${procurement.procurement_id}/actuate`, payload);
            onSuccess();
        } catch (err) {
            console.error("Actuation Error:", err);
            setError(err.response?.data?.detail || "Fatal execution error during transit.");
            setIsProcessing(false);
        }
    };

    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
            <div className="bg-[#151925] border border-gray-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col scale-100 transition-transform duration-200">
                {/* Header */}
                <div className="p-5 border-b border-gray-800 bg-gradient-to-r from-[#1A1F2E] to-[#151925]">
                    <h3 className="text-xl font-bold text-gray-100 flex items-center gap-2">
                        <span className="w-2 h-6 bg-indigo-500 rounded-full"></span>
                        Authorize Procurement
                    </h3>
                    <p className="text-xs text-gray-500 mt-1 font-mono uppercase tracking-wider">{procurement.procurement_id}</p>
                </div>

                <div className="p-6 space-y-6">
                    {/* Read-Only Contextual Ingestion Matrix */}
                    <div className="p-4 bg-[#1A1F2E] border border-gray-800 rounded-lg space-y-4">
                        <div className="flex justify-between items-start">
                            <div>
                                <div className="text-xs text-gray-500 uppercase tracking-wider">Asset Designation</div>
                                <div className="text-lg text-gray-200 font-medium">{procurement.nomenclature}</div>
                            </div>
                            <div className="text-right">
                                <div className="text-xs text-gray-500 uppercase tracking-wider">Current State</div>
                                <div className="px-2 py-0.5 mt-1 bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded text-xs font-semibold inline-block">
                                    {procurement.status}
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-3 gap-4 pt-3 border-t border-gray-800">
                            <div>
                                <div className="text-xs text-gray-500 uppercase">QOH / THRESH</div>
                                <div className="text-gray-300 font-mono mt-1 font-medium">
                                    {procurement.quantity_on_hand} <span className="text-gray-600">/</span> {procurement.reorder_threshold}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500 uppercase">Unit Cost</div>
                                <div className="text-emerald-400 font-mono mt-1 font-medium">${procurement.unit_cost.toFixed(2)}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500 uppercase">Total Deficit</div>
                                <div className="text-red-400 font-mono mt-1 font-medium">
                                    -{Math.max(0, procurement.reorder_threshold - procurement.quantity_on_hand)} units
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Actuation Controls */}
                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Target Status</label>
                            <select
                                value={targetStatus}
                                onChange={(e) => setTargetStatus(e.target.value)}
                                disabled={isProcessing}
                                className="w-full bg-[#1A1F2E] border border-gray-700 text-gray-200 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50 appearance-none"
                            >
                                {availableTransitions.map(state => (
                                    <option key={state} value={state}>{state}</option>
                                ))}
                            </select>
                        </div>

                        {/* Dynamic Economic Gate */}
                        {targetStatus === 'APPROVED' && (
                            <div className="animate-slide-down">
                                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Authorized Quantity</label>
                                <input
                                    type="number"
                                    min="1"
                                    value={authorizedQuantity}
                                    onChange={(e) => setAuthorizedQuantity(e.target.value)}
                                    disabled={isProcessing}
                                    placeholder="Enter physical units to order..."
                                    className="w-full bg-[#1A1F2E] border border-gray-700 text-gray-200 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                                />
                                
                                <div className="mt-4 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg flex justify-between items-center">
                                    <span className="text-indigo-300 font-medium">Total Capital Expenditure</span>
                                    <span className="text-indigo-400 font-bold font-mono text-xl">${totalExpenditure}</span>
                                </div>
                            </div>
                        )}
                        
                        {targetStatus === 'FULFILLED' && (
                            <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400 text-sm">
                                Fulfilling this order will autonomously restock the inventory using the previously authorized quantity.
                            </div>
                        )}
                        
                        {targetStatus === 'REJECTED' && (
                            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                                This will abort the procurement cycle permanently.
                            </div>
                        )}
                    </div>

                    {error && (
                        <div className="p-3 bg-red-900/20 border border-red-500/50 text-red-400 rounded-lg text-sm flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                            {error}
                        </div>
                    )}
                </div>

                {/* Footer Controls */}
                <div className="p-5 border-t border-gray-800 bg-[#1A1F2E] flex justify-end gap-3">
                    <button
                        onClick={() => !isProcessing && onClose()}
                        disabled={isProcessing}
                        className="px-4 py-2 bg-transparent text-gray-400 hover:text-gray-200 rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                        ABORT TRANSIT
                    </button>
                    <button
                        onClick={handleActuation}
                        disabled={isProcessing || !targetStatus}
                        className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {isProcessing ? 'ACTUATING...' : 'EXECUTE STATE SHIFT'}
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
};

export default ProcurementActuationModal;
