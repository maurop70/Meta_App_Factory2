import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function WorkspaceVault({ setSelectedApp }) {
  const navigate = useNavigate();
  const [activatingId, setActivatingId] = useState(null);
  const [projects, setProjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const handleActuateProject = async (project) => {
    if (activatingId) return;
    setActivatingId(project.project_name);
    try {
      if (setSelectedApp) {
        setSelectedApp(project.project_name);
      }
      localStorage.setItem('last_active_project', project.project_name);
      
      await axios.post('/api/warroom/execute', {
        project_id: project.project_name,
        intent: `@Operator Directive: Actuate boardroom debate for ${project.project_name}`
      });
      
      navigate('/warroom');
    } catch (err) {
      console.error("Failed to actuate workspace ledger:", err);
      alert("Encryption boundary handshake failed. Unable to actuate War Room session.");
    } finally {
      setActivatingId(null);
    }
  };

  const renderOperationalContext = (context) => {
    if (!context) {
      return 'No operational context defined for this persistent workspace matrix.';
    }
    
    if (typeof context === 'object') {
      return Object.entries(context)
        .map(([key, val]) => `${key.replace(/_/g, ' ').toUpperCase()}: ${val}`)
        .join('\n');
    }
    
    return String(context);
  };

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        // GET request strictly matching Unified I/O envelope request params
        const response = await axios.get('/api/projects/?limit=50&offset=0');
        // Parse Unified I/O serialization envelope {"items": [...], "total": <int>}
        if (response.data && Array.isArray(response.data.items)) {
          setProjects(response.data.items);
          setTotal(response.data.total || response.data.items.length);
        } else {
          setProjects([]);
          setTotal(0);
        }
        setError(null);
      } catch (err) {
        console.error("Failed to load workspace projects:", err);
        setError("System Net connection degraded. Unable to retrieve workspace vaults.");
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  return (
    <div className="workspace-vault-matrix p-6 min-h-screen bg-[#0B0F19] text-gray-100" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* Header Container */}
      <div className="w-full flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-[#1E293B]/60 to-[#0F172A]/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md mb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">📂</span>
            <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
              Workspace Vault
            </h1>
          </div>
          <p className="text-xs text-cyan-400/80 font-mono mt-1 uppercase tracking-wider">
            SECURE SOCRATIC PERSISTENCE RETRIEVAL & ARCHITECTURAL LEDGER ({total} ACTIVE WORKSPACES)
          </p>
        </div>
        <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 px-4 backdrop-blur-sm text-xs font-mono">
          <span className="text-slate-400 mr-2">VAULT VERDICT:</span>
          <span className="text-emerald-400 font-bold">ONLINE</span>
        </div>
      </div>

      {/* Main Content Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center h-[300px] text-slate-400 font-mono text-sm uppercase">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mb-4"></div>
          Accessing encrypted workspace volumes...
        </div>
      ) : error ? (
        <div className="bg-red-950/20 border border-red-500/30 p-6 rounded-xl text-center text-red-400 font-mono text-sm uppercase shadow-lg">
          ⚠️ {error}
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-slate-900/30 border border-slate-800/60 p-10 rounded-xl text-center text-slate-500 font-mono text-sm uppercase">
          No persistence records found in Socratic Registry.
        </div>
      ) : (
        <div 
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" 
          id="workspace-grid" 
          style={{ display: 'grid' }}
        >
          {projects.map((project) => (
            <div 
              key={project.id || project.project_name} 
              className="workspace-card group flex flex-col justify-between bg-gradient-to-br from-[#1E293B]/40 to-[#0F172A]/70 border border-slate-800/80 hover:border-cyan-500/50 rounded-2xl p-5 shadow-lg hover:shadow-cyan-500/5 transition-all duration-300 transform hover:-translate-y-1 backdrop-blur-sm"
              style={{ minHeight: '220px' }}
            >
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-start gap-2">
                  <h3 className="text-base font-bold text-white group-hover:text-cyan-300 transition-colors tracking-tight line-clamp-1" style={{ fontFamily: 'Outfit, sans-serif' }}>
                    {project.project_name}
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold bg-cyan-950/40 text-cyan-400 border border-cyan-500/20 uppercase tracking-wider">
                    active
                  </span>
                </div>
                
                <div className="h-[1px] bg-slate-800/60"></div>
                
                <p className="text-xs text-slate-400 font-mono leading-relaxed line-clamp-4 overflow-hidden" style={{ whiteSpace: 'pre-wrap' }}>
                  {renderOperationalContext(project.operational_context)}
                </p>
              </div>

              <div className="mt-4 flex justify-between items-center text-[10px] font-mono text-slate-500">
                <span>INDEX: #{project.id || 'N/A'}</span>
                <span 
                  className={`group-hover:text-cyan-300 transition-colors flex items-center gap-1 font-semibold cursor-pointer ${activatingId === project.project_name ? 'text-cyan-500 animate-pulse' : 'text-cyan-400/70'}`}
                  onClick={() => handleActuateProject(project)}
                >
                  {activatingId === project.project_name ? 'ACTIVATING...' : 'ACTUATE LEDGER ➜'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
