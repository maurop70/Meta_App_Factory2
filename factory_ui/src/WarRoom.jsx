import React, { useState, useEffect, useRef } from 'react';
import NaturalLanguageGateway from './components/NaturalLanguageGateway';
import axios from 'axios';

export default function WarRoom({ selectedApp }) {
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isPending = useRef(false);

  const [sreIncidents, setSreIncidents] = useState([]);
  const [sreLoading, setSreLoading] = useState(true);
  const [sreError, setSreError] = useState(null);
  const srePending = useRef(false);

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

  const fetchSreIncidents = async () => {
    if (srePending.current) return;
    srePending.current = true;
    try {
      const res = await axios.get('/agent/phantomsre/api/sre/incidents', {
        headers: {
          'X-API-KEY': 'default_secret_key'
        }
      });
      if (res.data && res.data.incidents) {
        try {
          const parsed = JSON.parse(res.data.incidents);
          setSreIncidents(parsed);
        } catch (e) {
          console.error("Failed to parse SRE incidents:", e);
          setSreIncidents([]);
        }
      }
      setSreError(null);
    } catch (err) {
      console.warn("Failed to fetch PhantomSRE incidents:", err);
      setSreError(err.message);
    } finally {
      setSreLoading(false);
      srePending.current = false;
    }
  };

  useEffect(() => {
    fetchTelemetry();
    fetchSreIncidents();
    const interval = setInterval(() => {
      fetchTelemetry();
      fetchSreIncidents();
    }, 6000);
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

        {/* SRE Active Incident Feed */}
        <div className="bg-slate-950/35 border border-slate-800/60 rounded-xl p-4 backdrop-blur-md flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
              SRE Autonomic Incident Feed
            </h3>
            <span className="text-[10px] font-mono text-cyan-400/80 uppercase">Active Monitoring</span>
          </div>
          
          {sreLoading && !sreIncidents.length ? (
            <div className="text-xs font-mono text-slate-400 py-2">Auditing system state logs...</div>
          ) : sreError ? (
            <div className="text-xs font-mono text-amber-500/80 py-2">SRE Status Offline</div>
          ) : !sreIncidents.length ? (
            <div className="text-xs font-mono text-emerald-400/80 py-2 flex items-center gap-1.5">
              <span>✓</span> Zero runtime tracebacks detected. Self-healing matrix nominal.
            </div>
          ) : (
            <div className="flex flex-col gap-2 max-h-[150px] overflow-y-auto pr-1">
              {sreIncidents.map((incident) => (
                <div key={incident.id} className="flex flex-col md:flex-row justify-between md:items-center bg-slate-900/40 border border-slate-800/50 rounded-lg p-2.5 px-3 gap-2">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold text-cyan-300">{incident.agent_id}</span>
                      <span className="text-[10px] font-mono text-slate-500">{new Date(incident.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <span className="text-[10px] font-mono text-rose-400/90 truncate max-w-[400px]">{incident.error}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-mono text-slate-400 truncate max-w-[200px]" title={incident.blueprint}>{incident.blueprint}</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${incident.status === 'RESOLVED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
                      {incident.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="h-[550px]">
          <NaturalLanguageGateway mode="warroom" selectedApp={selectedApp} />
        </div>
      </div>
    </div>
  );
}
