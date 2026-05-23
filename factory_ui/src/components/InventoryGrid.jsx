import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';

function InventoryDetailModal({ item, onClose, onUpdate }) {
  const [stock, setStock] = useState(item.stock);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const getStatusPreview = (currentStock) => {
    if (currentStock === 0) return { label: 'Out of Stock', classes: 'bg-rose-950/30 text-rose-400 border border-rose-500/20' };
    if (currentStock < 10) return { label: 'Critical', classes: 'bg-amber-950/30 text-amber-400 border border-amber-500/20' };
    return { label: 'Active', classes: 'bg-emerald-950/30 text-emerald-400 border border-emerald-500/20' };
  };

  const statusPreview = getStatusPreview(stock);

  const handleSave = async () => {
    if (stock < 0) {
      setError("Stock level cannot be negative.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`/api/inventory/${item.id}/stock`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ stock }),
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to update database layer.');
      }
      const updatedItem = await response.json();
      onUpdate(updatedItem);
      onClose();
    } catch (err) {
      setError(err.message || 'Database error occurred.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      <div 
        className="absolute inset-0 bg-black/75 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
      />
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-slate-800 bg-[#0F172A]/95 p-6 shadow-2xl backdrop-blur-xl transition-all flex flex-col gap-5">
        <div className="flex justify-between items-start">
          <div>
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Asset Integrity Control</span>
            <h2 className="text-lg font-extrabold text-white mt-1">{item.name}</h2>
            <p className="text-xs text-slate-400 mt-0.5">SKU: <span className="font-mono text-slate-300">{item.sku}</span></p>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white bg-slate-800/40 hover:bg-slate-800 p-1.5 rounded-lg transition-all"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/40">
          <div>
            <span className="text-xs text-slate-500 block uppercase font-bold">Category</span>
            <span className="text-sm font-semibold text-slate-200">{item.category}</span>
          </div>
          <div>
            <span className="text-xs text-slate-500 block uppercase font-bold">Price (USD)</span>
            <span className="text-sm font-semibold text-cyan-400 font-mono">${item.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
        </div>

        <div className="flex flex-col gap-2.5">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Adjust Stock Level</label>
          <div className="flex items-center justify-between gap-4 bg-[#060A12] border border-slate-800/80 rounded-xl p-2.5">
            <button 
              onClick={() => setStock(prev => Math.max(0, prev - 1))}
              className="h-9 w-9 flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-white font-bold text-base transition-all active:scale-95"
            >
              -
            </button>
            <input 
              type="number" 
              value={stock}
              onChange={(e) => setStock(Math.max(0, parseInt(e.target.value) || 0))}
              className="bg-transparent border-none text-center text-xl font-bold text-white focus:outline-none w-20 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <button 
              onClick={() => setStock(prev => prev + 1)}
              className="h-9 w-9 flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-white font-bold text-base transition-all active:scale-95"
            >
              +
            </button>
          </div>
          
          <div className="flex gap-2">
            <button 
              onClick={() => setStock(0)}
              className="flex-1 text-[10px] py-1 rounded-lg border border-rose-950/30 bg-rose-950/20 text-rose-400 font-semibold hover:bg-rose-950/40 transition-all"
            >
              Out of Stock
            </button>
            <button 
              onClick={() => setStock(5)}
              className="flex-1 text-[10px] py-1 rounded-lg border border-amber-950/30 bg-amber-950/20 text-amber-400 font-semibold hover:bg-amber-950/40 transition-all"
            >
              Critical (5)
            </button>
            <button 
              onClick={() => setStock(prev => prev + 10)}
              className="flex-1 text-[10px] py-1 rounded-lg border border-slate-700 bg-slate-800/40 text-slate-300 font-semibold hover:bg-slate-700 hover:text-white transition-all"
            >
              +10 Units
            </button>
          </div>
        </div>

        <div className="flex justify-between items-center p-3 rounded-xl bg-slate-900/40 border border-slate-800/40">
          <span className="text-xs font-semibold text-slate-400">Live Status Preview:</span>
          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${statusPreview.classes}`}>
            {statusPreview.label}
          </span>
        </div>

        {error && (
          <div className="p-2.5 text-xs bg-rose-950/30 border border-rose-800/30 text-rose-400 rounded-lg font-medium">
            {error}
          </div>
        )}

        <div className="flex gap-2.5 mt-1">
          <button 
            onClick={onClose}
            className="flex-1 py-2 rounded-xl border border-slate-700 bg-slate-850 hover:bg-slate-800 text-xs font-bold text-slate-300 hover:text-white transition-all"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={submitting}
            className="flex-1 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-xs font-extrabold text-slate-950 hover:text-black transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-cyan-500/10"
          >
            {submitting ? 'Updating...' : 'Save Adjustments'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function InventoryGrid() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(5);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);

  const fetchInventory = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/inventory?limit=${limit}&offset=${offset}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message || 'Failed to fetch inventory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, [limit, offset]);

  const handleUpdateStock = (updatedItem) => {
    setItems(prev => prev.map(item => item.id === updatedItem.id ? updatedItem : item));
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  const handlePrevPage = () => {
    if (offset - limit >= 0) {
      setOffset(offset - limit);
    }
  };

  const handleNextPage = () => {
    if (offset + limit < total) {
      setOffset(offset + limit);
    }
  };

  return (
    <div className="min-h-screen bg-[#090D16] text-[#E2E8F0] font-sans antialiased p-6 md:p-10 flex flex-col items-center">
      {/* Embedded CSS Reflow Matrix for Viewports < 900px */}
      <style>{`
        @media (max-width: 899px) {
          .reflow-table {
            display: block;
            width: 100%;
          }
          .reflow-table thead {
            display: none;
          }
          .reflow-table tbody {
            display: block;
            width: 100%;
          }
          .reflow-table tr {
            display: block;
            width: 100%;
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            margin-bottom: 16px;
            padding: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            backdrop-filter: blur(8px);
          }
          .reflow-table td {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 10px 8px;
            text-align: right;
          }
          .reflow-table td:last-child {
            border-bottom: none;
          }
          .reflow-table td::before {
            content: attr(data-label);
            font-weight: 700;
            color: #06B6D4;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            text-align: left;
            margin-right: 16px;
          }
        }
      `}</style>

      <div className="w-full max-w-6xl flex flex-col gap-6">
        {/* Header Block */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-[#1E293B]/60 to-[#0F172A]/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
          <div>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-cyan-400 animate-ping"></div>
              <h1 className="text-2xl font-bold tracking-tight text-white">MAF Enterprise Inventory</h1>
            </div>
            <p className="text-sm text-slate-400 mt-1">Strict python3.14 + SQLite pagination engine connected</p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Page Size:</label>
            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setOffset(0);
              }}
              className="bg-[#0D1527] border border-slate-700 text-white rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-cyan-500 transition-colors cursor-pointer"
            >
              <option value={5}>5 per page</option>
              <option value={10}>10 per page</option>
              <option value={20}>20 per page</option>
              <option value={50}>50 per page</option>
            </select>
            <button
              onClick={fetchInventory}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/20 text-cyan-400 text-sm font-semibold hover:bg-cyan-500/20 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Data Table Container */}
        <div className="bg-[#0F172A]/40 border border-slate-800/80 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-lg">
          {loading && (
            <div className="flex items-center justify-center p-20 text-cyan-400 text-sm font-semibold tracking-widest uppercase">
              Connecting database matrix...
            </div>
          )}

          {!loading && error && (
            <div className="p-8 text-center bg-rose-950/20 border border-rose-800/30 text-rose-400 rounded-xl m-6">
              <p className="font-bold">Database Error Inception</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="p-20 text-center text-slate-500 font-medium">
              No records registered in sqlite database layer.
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="reflow-table w-full border-collapse text-left">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800">
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">SKU</th>
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Category</th>
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Stock Level</th>
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Price (USD)</th>
                    <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedItem(item)}
                      className="hover:bg-slate-800/25 transition-colors group cursor-pointer"
                    >
                      <td data-label="SKU" className="px-6 py-4 text-sm font-semibold text-slate-400 group-hover:text-cyan-400 transition-colors">
                        {item.sku}
                      </td>
                      <td data-label="Name" className="px-6 py-4 text-sm font-bold text-white">
                        {item.name}
                      </td>
                      <td data-label="Category" className="px-6 py-4 text-sm text-slate-300">
                        {item.category}
                      </td>
                      <td data-label="Stock Level" className="px-6 py-4 text-sm">
                        <span className={`font-bold ${item.stock === 0 ? 'text-rose-500' : item.stock < 10 ? 'text-amber-400' : 'text-slate-200'}`}>
                          {item.stock} <span className="text-xs text-slate-500 font-normal">units</span>
                        </span>
                      </td>
                      <td data-label="Price (USD)" className="px-6 py-4 text-sm font-mono text-cyan-400 font-semibold">
                        ${item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td data-label="Status" className="px-6 py-4 text-sm">
                        <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          item.status === 'Active'
                            ? 'bg-emerald-950/30 text-emerald-400 border border-emerald-500/20'
                            : item.status === 'Critical'
                            ? 'bg-amber-950/30 text-amber-400 border border-amber-500/20'
                            : 'bg-rose-950/30 text-rose-400 border border-rose-500/20'
                        }`}>
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        {!loading && !error && items.length > 0 && (
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-slate-950/30 border border-slate-800/60 rounded-2xl p-4 shadow-lg backdrop-blur-md">
            <span className="text-sm text-slate-400">
              Showing <span className="font-semibold text-white">{offset + 1}</span> to{' '}
              <span className="font-semibold text-white">{Math.min(offset + limit, total)}</span> of{' '}
              <span className="font-semibold text-white">{total}</span> assets
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevPage}
                disabled={offset === 0}
                className="px-4 py-1.5 rounded-lg border border-slate-700 bg-[#0D1527] text-sm font-medium text-slate-300 hover:text-white hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                Previous
              </button>
              <div className="px-4 py-1 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-400">
                Page <span className="font-bold text-white">{currentPage}</span> of{' '}
                <span className="font-bold text-white">{totalPages}</span>
              </div>
              <button
                onClick={handleNextPage}
                disabled={offset + limit >= total}
                className="px-4 py-1.5 rounded-lg border border-slate-700 bg-[#0D1527] text-sm font-medium text-slate-300 hover:text-white hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {selectedItem && ReactDOM.createPortal(
        <InventoryDetailModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onUpdate={handleUpdateStock}
        />,
        document.body
      )}
    </div>
  );
}
