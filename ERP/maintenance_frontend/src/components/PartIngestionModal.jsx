import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import api from '../services/api';

const PartIngestionModal = ({ isOpen, onClose, onPartIngested }) => {
    const isMounted = React.useRef(true);

    React.useEffect(() => {
        isMounted.current = true;
        return () => { isMounted.current = false; };
    }, []);

    const [skus, setSkus] = useState([]);
    const [selectedSku, setSelectedSku] = useState('');
    const [serialNumber, setSerialNumber] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errorMsg, setErrorMsg] = useState(null);

    // Fetch SKUs for Relational Lookup Doctrine
    useEffect(() => {
        if (isOpen) {
            setErrorMsg(null);
            setSerialNumber('');
            setSelectedSku('');
            
            // Hydrate SKU matrix adhering strictly to Unified I/O Serialization Envelope
            api.get('/inventory/skus?limit=100')
                .then(res => {
                    const items = res.data.items || [];
                    setSkus(items);
                })
                .catch(err => {
                    setErrorMsg("Failed to hydrate SKU matrix: " + (err.response?.data?.detail || err.message));
                });
        }
    }, [isOpen]);

    // Portal Actuation Lockout: Block backdrop/escape during submission
    const handleBackdropClick = (e) => {
        if (isSubmitting) return;
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape' && isOpen && !isSubmitting) {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [isOpen, isSubmitting, onClose]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!selectedSku) {
            setErrorMsg("Relational Lock: A valid SKU must be selected.");
            return;
        }

        setIsSubmitting(true);
        setErrorMsg(null);

        try {
            const payload = {
                sku_id: selectedSku,
                serial_number: serialNumber.trim() || null
            };
            const response = await api.post('/inventory/parts', payload);
            
            // Success
            if (onPartIngested) onPartIngested(response.data);
            onClose();
        } catch (error) {
            // Deterministic Exception Handling
            if (error.response) {
                const status = error.response.status;
                const detail = error.response.data?.detail || "Network transit failed.";
                if (status === 409) {
                    setErrorMsg(`HTTP 409: Serial number already exists. (${detail})`);
                } else if (status === 400) {
                    setErrorMsg(`HTTP 400: Invalid SKU ID. (${detail})`);
                } else if (status === 422) {
                    setErrorMsg(`HTTP 422: Pydantic validation failure. (${detail})`);
                } else {
                    setErrorMsg(`HTTP ${status}: ${detail}`);
                }
            } else {
                setErrorMsg("HTTP 500: Fatal network partition.");
            }
        } finally {
            if (isMounted.current) {
                setIsSubmitting(false);
            }
        }
    };

    if (!isOpen) return null;

    const modalContent = (
        <div 
            className="fixed inset-0 bg-black/60 z-[9999] flex justify-center items-center backdrop-blur-sm"
            onClick={handleBackdropClick}
        >
            <div className="bg-[#1a1b23] border border-[#2a2b36] rounded-lg shadow-2xl p-6 max-w-md w-full relative">
                <h2 className="text-xl font-bold text-white mb-4">Physical Part Instantiation</h2>
                
                {errorMsg && (
                    <div className="bg-red-500/20 border border-red-500/50 text-red-200 p-3 rounded mb-4 text-sm font-mono">
                        {errorMsg}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    {/* Relational Lookup Doctrine */}
                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-gray-400 font-semibold uppercase">Financial Catalog Binding (SKU)</label>
                        <select 
                            className="bg-[#2a2b36] text-white border border-[#3a3b46] rounded p-2 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                            value={selectedSku}
                            onChange={(e) => setSelectedSku(e.target.value)}
                            disabled={isSubmitting}
                            required
                        >
                            <option value="">-- Select Nomenclature --</option>
                            {skus.map(sku => (
                                <option key={sku.sku_id} value={sku.sku_id}>
                                    {sku.nomenclature} ({sku.sku_id})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-gray-400 font-semibold uppercase">Physical Serial Number</label>
                        <input 
                            type="text" 
                            className="bg-[#2a2b36] text-white border border-[#3a3b46] rounded p-2 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                            placeholder="Optional (Autogenerated if blank)"
                            value={serialNumber}
                            onChange={(e) => setSerialNumber(e.target.value)}
                            disabled={isSubmitting}
                        />
                    </div>

                    <div className="flex justify-end gap-3 mt-4">
                        <button 
                            type="button" 
                            className="px-4 py-2 text-gray-400 hover:text-white disabled:opacity-50"
                            onClick={() => !isSubmitting && onClose()}
                            disabled={isSubmitting}
                        >
                            Cancel
                        </button>
                        <button 
                            type="submit" 
                            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded font-medium disabled:opacity-50 flex items-center gap-2"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Instantiating...' : 'Instantiate Part'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );

    // Portal Actuation Lockout: Eject to root DOM
    return ReactDOM.createPortal(modalContent, document.body);
};

export default PartIngestionModal;
