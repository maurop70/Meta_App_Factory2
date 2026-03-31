import os
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── The React HOC Content ─────────────────────────────────────────────────────
AETHER_SUITE_CODE = """
import React, { useState } from 'react';

export default function AetherCommandSuite({ appName }) {
  const [loadingExplain, setLoadingExplain] = useState(false);
  const [loadingRefine, setLoadingRefine] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type='info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleExplain = async () => {
    setLoadingExplain(true);
    try {
      const res = await fetch(`http://localhost:5000/api/socratic/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: appName })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Request failed');
      
      alert(`🤖 AETHER SOCRATIC TRACE [${appName}]\\n\\n${data.trace || data.message || JSON.stringify(data)}`);
    } catch (err) {
      alert(`⚠️ Socratic Bridge Error:\\n${err.message}`);
    } finally {
      setLoadingExplain(false);
    }
  };

  const handleRefine = async () => {
    setLoadingRefine(true);
    try {
        const res = await fetch(`http://localhost:5000/api/system/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_name: appName })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Validation failed');
        showToast("Refinement Loop Triggered 🚀 Check Factory UI for logs.", "success");
    } catch (err) {
        showToast(`Refinement Failed: ${err.message}`, "error");
    } finally {
        setLoadingRefine(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      fontFamily: 'system-ui, sans-serif'
    }}>
      {toast && (
        <div style={{
          background: toast.type === 'error' ? 'rgba(239,68,68,0.9)' : 'rgba(0,209,255,0.9)',
          color: '#000', padding: '10px 16px', borderRadius: '8px', fontSize: '13px',
          boxShadow: `0 4px 12px ${toast.type === 'error' ? 'rgba(239,68,68,0.4)' : 'rgba(0,209,255,0.4)'}`,
          marginBottom: '8px', textAlign: 'center', fontWeight: 'bold'
        }}>
          {toast.msg}
        </div>
      )}
      
      <div style={{
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(0, 209, 255, 0.3)',
        borderRadius: '12px',
        padding: '12px 16px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px'
      }}>
        <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Aether Controls
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={handleExplain} 
            disabled={loadingExplain}
            style={{
              padding: '8px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.2)', color: '#fff', cursor: 'pointer',
              fontWeight: 500, fontSize: '13px', transition: 'all 0.2s', display: 'flex', alignItems: 'center'
            }}
          >
            {loadingExplain ? '⏳' : '🧠 Explain'}
          </button>
          <button 
            onClick={handleRefine}
            disabled={loadingRefine}
            style={{
              padding: '8px 14px', borderRadius: '8px', background: '#00D1FF',
              border: 'none', color: '#000', cursor: 'pointer', display: 'flex', alignItems: 'center',
              fontWeight: 700, fontSize: '13px', boxShadow: '0 0 10px rgba(0, 209, 255, 0.4)',
              transition: 'all 0.2s'
            }}
          >
            {loadingRefine ? '⏳' : '🚀 Refine App'}
          </button>
        </div>
      </div>
    </div>
  );
}
"""

def inject_command_suite():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    registry_path = os.path.join(script_dir, "registry.json")
    
    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)
        
    apps = registry_data.get("apps", {})
    
    for app_name, metadata in apps.items():
        # Override paths explicitly if defined
        app_path = metadata.get("path", app_name)
        if not os.path.isabs(app_path):
            app_path = os.path.join(script_dir, os.path.basename(app_path))
            
        if not os.path.exists(app_path):
            continue
            
        main_file = None
        src_dir = None
        
        # Try finding a main.jsx or main.tsx
        for root, dirs, files in os.walk(app_path):
            if "node_modules" in dirs:
                dirs.remove("node_modules")
            if "main.jsx" in files:
                main_file = os.path.join(root, "main.jsx")
                src_dir = root
                break
            elif "main.tsx" in files:
                main_file = os.path.join(root, "main.tsx")
                src_dir = root
                break
                
        if not src_dir or not main_file:
            continue
            
        # Write AetherCommandSuite.jsx
        suite_path = os.path.join(src_dir, "AetherCommandSuite.jsx")
        with open(suite_path, "w", encoding="utf-8") as f:
            f.write(AETHER_SUITE_CODE)
            
        # Patch main.jsx
        with open(main_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Avoid double-injection
        if "AetherCommandSuite" in content:
            continue
            
        injection_code = f"\n// ── Aether Command Suite Injection ──\n" \
                         f"import {{ createRoot as _createAetherRoot }} from 'react-dom/client';\n" \
                         f"import AetherCommandSuite from './AetherCommandSuite.jsx';\n" \
                         f"const _aetherDiv = document.createElement('div');\n" \
                         f"_aetherDiv.id = 'aether-command-suite-root';\n" \
                         f"document.body.appendChild(_aetherDiv);\n" \
                         f"_createAetherRoot(_aetherDiv).render(<AetherCommandSuite appName=\"{app_name}\" />);\n"
                         
        with open(main_file, "a", encoding="utf-8") as f:
            f.write(injection_code)
            
        logging.info(f"SUCCESS: Injected Aether Command Suite into {app_name} ({main_file})")

if __name__ == "__main__":
    inject_command_suite()
