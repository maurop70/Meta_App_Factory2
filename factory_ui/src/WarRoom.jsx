import React, { useState, useEffect, useRef } from 'react';
import NaturalLanguageGateway from './components/NaturalLanguageGateway';
import axios from 'axios';

export default function WarRoom() {
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isPending = useRef(false);

  const fetchTelemetry = async () => {
    if (isPending.current) return;
    isPending.current = true;
    try {
      const res = await axios.get('/agent/warroommonitor/api/health', {
        headers: {
          'X-API-KEY': 'default_secret_key'
        }
      });
      setTelemetry(res.data);
      setError(null);
    } catch (err) {
      console.warn("Failed to fetch WarRoomMonitor telemetry:", err);
      setError(err.message);
    } finally {
      setLoading(false);
      isPending.current = false;
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 6000);
    return () => clearInterval(interval);
  }, []);

  // Parse child agent status dictionary safely
  let childAgents = {};
  if (telemetry && telemetry.child_agents_status) {
    try {
      childAgents = JSON.parse(telemetry.child_agents_status);
    } catch (e) {
      console.error("Failed to parse child agents status:", e);
    }
  }

  return (
    <div className="registry-panel" style={{ padding: '24px', background: 'rgba(15, 23, 42, 0.45)', borderRadius: '16px', backdropFilter: 'blur(10px)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
      <div className="w-full flex flex-col gap-6 bg-[#0a0e17]/80 border border-red-500/20 rounded-2xl p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-[#1E293B]/60 to-[#0F172A]/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
          <div>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-ping"></div>
              <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>Adversarial War Room</h1>
            </div>
            <p className="text-xs text-red-400/80 font-mono mt-1 uppercase tracking-wider">Threat modeling and logic stress-testing matrix. Input your target architecture.</p>
          </div>
          
          {/* Dynamic Telemetry Glassmorphic Dashboard */}
          <div className="flex items-center gap-4 bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 px-4 backdrop-blur-sm text-xs font-mono">
            {loading && !telemetry ? (
              <div className="text-slate-400">Loading Telemetry...</div>
            ) : error ? (
              <div className="text-red-400">Telemetry Offline: {error}</div>
            ) : (
              <div className="flex items-center gap-6">
                <div>
                  <span className="text-slate-400 mr-2">CPU:</span>
                  <span className="text-emerald-400 font-bold">{telemetry.cpu_percent}</span>
                </div>
                <div className="h-4 w-[1px] bg-slate-700"></div>
                <div>
                  <span className="text-slate-400 mr-2">RAM:</span>
                  <span className="text-emerald-400 font-bold">{telemetry.memory_percent}</span>
                </div>
                <div className="h-4 w-[1px] bg-slate-700"></div>
                <div>
                  <span className="text-slate-400 mr-2">C-Suite:</span>
                  <span className={telemetry.overall_status === 'HEALTHY' ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                    {telemetry.overall_status}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Child Agents Dynamic Pings Telemetry */}
        {telemetry && !loading && !error && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-950/40 border border-slate-800/80 rounded-xl p-4 backdrop-blur-md">
            {Object.entries(childAgents).map(([agent, status]) => (
              <div key={agent} className="flex items-center justify-between bg-slate-900/30 border border-slate-800/50 rounded-lg p-2.5 px-3">
                <span className="text-xs font-mono text-slate-300">{agent.replace(/_Agent/g, '')}</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${status === 'ONLINE' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  {status}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="h-[550px]">
          <NaturalLanguageGateway mode="warroom" />
        </div>
      </div>
    </div>
  );
}
