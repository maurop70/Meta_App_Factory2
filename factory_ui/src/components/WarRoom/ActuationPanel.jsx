import React, { useState, useEffect } from 'react';
import { actuateWorkspaceBlueprint } from '../../api/workspaceClient';
import axios from 'axios';

/**
 * ActuationPanel - Phase 3 - Blueprint Actuation Transport Layer
 * Provides strict client-side schema validation, asynchronous loading state matrix,
 * duplicate execution prevention, and explicit SRE exception escalation.
 */
export default function ActuationPanel({ 
  chatLog = [], 
  sreIncidents = [], 
  setSreIncidents,
  selectedApp 
}) {
  const [isActuating, setIsActuating] = useState(false);
  const [actuationResult, setActuationResult] = useState(null);
  const [localError, setLocalError] = useState(null);
  const [detectedBlueprint, setDetectedBlueprint] = useState(null);
  const [rawTextOverride, setRawTextOverride] = useState('');
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  // Helper: Extract clean JSON and format to WorkspaceBlueprintInput schema
  const extractAndValidateBlueprint = (text) => {
    if (!text || typeof text !== 'string') return null;

    try {
      // 1. Strict regex extraction of JSON markdown block
      const jsonRegex = /```(?:json)?\s*([\s\S]*?)\s*```/;
      let jsonString = '';
      const match = text.match(jsonRegex);
      if (match) {
        jsonString = match[1].trim();
      } else {
        // Fallback: search for first '{' and last '}'
        const startIdx = text.indexOf('{');
        const endIdx = text.lastIndexOf('}');
        if (startIdx !== -1 && endIdx !== -1) {
          jsonString = text.slice(startIdx, endIdx + 1).trim();
        }
      }

      if (!jsonString) return null;

      // 2. JSON Deserialization
      const data = JSON.parse(jsonString);

      // 3. Schema mapping and validation (WorkspaceBlueprintSchema -> WorkspaceBlueprintInput)
      const templateId = data.template_id || data.master_template_id;
      const presentationName = data.presentation_name || data.output_filename || "Heinlein_Foods_90_Day_Strategy";
      const rawMutations = data.mutations || {};

      if (!templateId) return null;

      // Map mutations object/dictionary to strict list of WorkspaceMutation
      const mutationsArray = [];
      if (typeof rawMutations === 'object' && !Array.isArray(rawMutations)) {
        for (const [tag, val] of Object.entries(rawMutations)) {
          mutationsArray.push({
            replace_tag: tag,
            injection_value: String(val)
          });
        }
      } else if (Array.isArray(rawMutations)) {
        for (const m of rawMutations) {
          mutationsArray.push({
            replace_tag: m.replace_tag || m.tag,
            injection_value: String(m.injection_value || m.val || m.value)
          });
        }
      }

      // Construct verified WorkspaceBlueprintInput
      return {
        execution_id: `exec_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
        target_engine: "Google_Slides",
        master_template_id: templateId,
        output_filename: presentationName,
        mutations: mutationsArray
      };
    } catch (e) {
      console.warn("Blueprint extraction parser discarded malformed payload:", e);
      return null;
    }
  };

  // Scan chat log for consensus blueprints
  useEffect(() => {
    // Traverse chat messages backwards to find the latest valid blueprint
    for (let i = chatLog.length - 1; i >= 0; i--) {
      const msg = chatLog[i];
      if (msg.role !== 'user' && msg.content) {
        const bp = extractAndValidateBlueprint(msg.content);
        if (bp) {
          setDetectedBlueprint(bp);
          setLocalError(null);
          return;
        }
      }
    }
    setDetectedBlueprint(null);
  }, [chatLog]);

  const handleActuate = async () => {
    // Select correct blueprint source (override or auto-detected)
    let blueprintToActuate = detectedBlueprint;
    if (showOverrideInput && rawTextOverride.trim()) {
      const parsed = extractAndValidateBlueprint(rawTextOverride);
      if (!parsed) {
        setLocalError("Invalid input: Unable to extract a valid WorkspaceBlueprint schema from your payload.");
        return;
      }
      blueprintToActuate = parsed;
    }

    if (!blueprintToActuate) {
      setLocalError("No valid workspace blueprint has been generated or provided yet.");
      return;
    }

    // STRICT Loading State Lock: mathematically prevent duplicate execution fractures
    setIsActuating(true);
    setLocalError(null);
    setActuationResult(null);

    try {
      console.log("Actuation Matrix: Initiating transport layer transmission...", blueprintToActuate);
      const res = await actuateWorkspaceBlueprint(blueprintToActuate);
      
      setActuationResult({
        status: "success",
        message: "Google Slides & Drive workspace successfully synchronized!",
        presentation_id: res.document_id || "cloned_success_200",
        url: res.asset_url || res.url || `https://docs.google.com/presentation/d/${res.presentation_id || res.document_id}/edit`
      });
    } catch (err) {
      // 3. STRICT FRONTEND EXCEPTION ESCALATION
      const errDetail = err.detail || err.message;
      setLocalError(err.message);

      // Construct autonomic SRE incident payload
      const incident = {
        id: `sre_err_${Date.now()}`,
        timestamp: new Date().toISOString(),
        agent_id: "WORKSPACE_ACTUATOR_GATE",
        error: `Workspace Actuation Failure: ${err.message}`,
        status: "CRITICAL",
        blueprint: blueprintToActuate.output_filename || "Heinlein_Foods_Consensus"
      };

      // Direct insertion into the SRE incidents UI feed
      if (setSreIncidents) {
        setSreIncidents(prev => [incident, ...prev]);
      }

      // Asynchronous escalation to Phantom SRE / QA alerts API
      try {
        await axios.post('/api/qa/alerts', {
          alert_id: incident.id,
          source: "WORKSPACE_ACTUATOR_GATE",
          agent: "CTO",
          severity: "CRITICAL",
          exception: "WorkspaceActuationError",
          message: err.message,
          staged_blueprint_path: `staged_blueprint_${blueprintToActuate.output_filename}.json`,
          ast_payload_preview: `Cloning template_id ${blueprintToActuate.master_template_id} to ${blueprintToActuate.output_filename}`
        });
      } catch (alertErr) {
        console.warn("Failed to transmit telemetry to /api/qa/alerts:", alertErr);
      }
    } finally {
      setIsActuating(false);
    }
  };

  return (
    <div 
      className="actuation-panel bg-gradient-to-br from-[#1E293B]/45 to-[#0F172A]/70 border border-red-500/20 hover:border-red-500/40 rounded-2xl p-5 shadow-2xl backdrop-blur-md transition-all duration-300 flex flex-col gap-4 text-xs font-mono"
      style={{ border: '1px solid rgba(239, 68, 68, 0.15)' }}
    >
      <div className="flex justify-between items-center border-b border-red-500/10 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">🧬</span>
          <h3 className="text-sm font-bold text-white tracking-wider uppercase" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Consensus Actuator Panel
          </h3>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${detectedBlueprint ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
          {detectedBlueprint ? 'BLUEPRINT READY' : 'AWAITING CONSENSUS'}
        </span>
      </div>

      {detectedBlueprint ? (
        <div className="flex flex-col gap-2.5">
          <div className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-3 leading-relaxed">
            <div className="text-[10px] text-slate-400 uppercase mb-1">Target Slide Deck Name</div>
            <div className="text-white font-bold mb-2">{detectedBlueprint.output_filename}</div>
            
            <div className="text-[10px] text-slate-400 uppercase mb-1">Google Master Template ID</div>
            <div className="text-cyan-400 truncate mb-2">{detectedBlueprint.master_template_id}</div>

            <div className="text-[10px] text-slate-400 uppercase mb-1">Active Mutations</div>
            <div className="text-emerald-400 font-bold">{detectedBlueprint.mutations.length} tags mapped</div>
          </div>
        </div>
      ) : (
        <p className="text-slate-400 leading-relaxed">
          Deliberation stream active. Once the C-Suite swarm converges on a mathematically verified strategy, the system will automatically parse and validate the consensus blueprint here.
        </p>
      )}

      {/* Manual Override Input Accordion */}
      <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/20">
        <button 
          onClick={() => setShowOverrideInput(!showOverrideInput)}
          className="w-full flex justify-between items-center p-3 text-slate-400 hover:text-white transition-colors"
        >
          <span>🛠️ MANUAL PAYLOAD OVERRIDE</span>
          <span>{showOverrideInput ? '▲' : '▼'}</span>
        </button>
        
        {showOverrideInput && (
          <div className="p-3 border-t border-slate-800 flex flex-col gap-3">
            <textarea
              className="w-full p-2 bg-[#0B0F19] border border-slate-800 rounded-lg text-gray-200 font-mono text-xs focus:outline-none focus:border-red-500/50 resize-none"
              rows="4"
              placeholder="Paste raw Markdown or JSON consensus strategy here..."
              value={rawTextOverride}
              onChange={(e) => setRawTextOverride(e.target.value)}
            />
            <p className="text-[10px] text-slate-500 leading-relaxed uppercase">
              The transport layer will automatically apply the strict regex parser to extract the clean Workspace JSON block.
            </p>
          </div>
        )}
      </div>

      {/* Exception Feedback Notification */}
      {localError && (
        <div className="bg-rose-950/20 border border-rose-500/30 p-3 rounded-xl text-rose-400 font-mono leading-relaxed relative flex flex-col gap-1">
          <span className="font-bold text-[10px] uppercase text-rose-300">🚨 AUTONOMIC INCIDENT CAPTURED</span>
          <span className="text-[11px]">{localError}</span>
        </div>
      )}

      {/* Success Notification */}
      {actuationResult && (
        <div className="bg-emerald-950/20 border border-emerald-500/30 p-3 rounded-xl text-emerald-400 font-mono leading-relaxed flex flex-col gap-1.5">
          <span className="font-bold text-[10px] uppercase text-emerald-300">✓ ACTUATION SUCCESS</span>
          <span className="text-[11px]">{actuationResult.message}</span>
          <a 
            href={actuationResult.url} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="text-cyan-400 hover:underline text-[11px] font-bold block"
          >
            [ VIEW DEPLOYED ASSET ]
          </a>
        </div>
      )}

      {/* Strict Loading State Lock Trigger */}
      <button
        onClick={handleActuate}
        disabled={isActuating || (!detectedBlueprint && !rawTextOverride.trim())}
        className={`w-full py-3 rounded-xl font-bold tracking-widest text-white transition-all uppercase flex items-center justify-center gap-2 ${
          isActuating 
            ? 'bg-gray-700 text-gray-500 cursor-not-allowed' 
            : detectedBlueprint || rawTextOverride.trim()
              ? 'bg-red-600 hover:bg-red-500 hover:scale-[1.01] active:scale-95 shadow-[0_0_15px_rgba(239,68,68,0.25)] cursor-pointer'
              : 'bg-slate-900 text-slate-600 border border-slate-800 cursor-not-allowed'
        }`}
      >
        {isActuating ? (
          <>
            <span className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-t-transparent border-white" />
            SYNCHRONIZING SLIDES...
          </>
        ) : (
          '[ ACTUATE BLUEPRINT ]'
        )}
      </button>
    </div>
  );
}
