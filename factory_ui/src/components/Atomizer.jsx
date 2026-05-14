import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

export default function Atomizer() {
    const [registryKeys, setRegistryKeys] = useState([]);
    const [appId, setAppId] = useState('');
    const [atomType, setAtomType] = useState('frontend_component');
    
    // File Navigation State
    const [availableFiles, setAvailableFiles] = useState([]);
    const [relativePath, setRelativePath] = useState('');
    const [fileContent, setFileContent] = useState('');
    const [isLoadingFile, setIsLoadingFile] = useState(false);
    
    // Selection & Telemetry State
    const [startLine, setStartLine] = useState(1);
    const [endLine, setEndLine] = useState(1);
    const [selectedTokens, setSelectedTokens] = useState(0);
    const [selectionActive, setSelectionActive] = useState(false);
    
    const [directive, setDirective] = useState('audit');
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    
    const preRef = useRef(null);

    // Initial Mount: Fetch Registry
    useEffect(() => {
        const fetchRegistry = async () => {
            try {
                const response = await axios.get('/api/registry');
                const appsArray = response.data.apps || [];
                const keys = appsArray.map(app => app.name); 
                setRegistryKeys(keys);
                if (keys.length > 0) setAppId(keys[0]);
            } catch (err) {
                console.error("Failed to load registry keys", err);
                setErrorMsg("Failed to load registry keys. Check telemetry link.");
            }
        };
        fetchRegistry();
    }, []);

    // App ID Change: Fetch File Tree
    useEffect(() => {
        if (!appId) return;
        
        const fetchFiles = async () => {
            try {
                const response = await axios.get(`/api/atomizer/files/${appId}`);
                const files = response.data.files || [];
                setAvailableFiles(files);
                if (files.length > 0) {
                    setRelativePath(files[0]);
                } else {
                    setRelativePath('');
                    setFileContent('');
                }
            } catch (err) {
                console.error("Failed to fetch app files", err);
                setAvailableFiles([]);
                setRelativePath('');
            }
        };
        fetchFiles();
    }, [appId]);

    // Relative Path Change: Fetch File Content
    useEffect(() => {
        if (!appId || !relativePath) {
            setFileContent('');
            return;
        }
        
        const fetchContent = async () => {
            setIsLoadingFile(true);
            setErrorMsg('');
            try {
                const response = await axios.get(`/api/atomizer/file-content`, {
                    params: { app_name: appId, relative_path: relativePath }
                });
                setFileContent(response.data.content || '');
                // Reset selection
                setStartLine(1);
                const lines = (response.data.content || '').split('\n').length;
                setEndLine(lines);
                setSelectedTokens(Math.ceil((response.data.content || '').length / 4));
                setSelectionActive(false);
            } catch (err) {
                console.error("Failed to fetch file content", err);
                setFileContent('// [FATAL] Unable to retrieve file context or path traversal blocked.');
            } finally {
                setIsLoadingFile(false);
            }
        };
        fetchContent();
    }, [appId, relativePath]);

    // Native Window Selection Tracker
    const handleMouseUp = () => {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
            // If they click without selecting, default to full file
            setSelectionActive(false);
            setStartLine(1);
            const lines = fileContent.split('\n').length;
            setEndLine(lines || 1);
            setSelectedTokens(Math.ceil(fileContent.length / 4));
            return;
        }

        const range = selection.getRangeAt(0);
        
        // Ensure selection is within our pre block
        if (preRef.current && preRef.current.contains(range.commonAncestorContainer)) {
            // We need to calculate line numbers. A robust way is to slice the text up to the selection start/end.
            const preText = preRef.current.textContent;
            
            // Getting accurate character offsets requires traversing text nodes,
            // but for simplicity we can use string matching or clone range to start
            const preRange = document.createRange();
            preRange.selectNodeContents(preRef.current);
            preRange.setEnd(range.startContainer, range.startOffset);
            const startChars = preRange.toString().length;
            
            preRange.setEnd(range.endContainer, range.endOffset);
            const endChars = preRange.toString().length;
            
            const textUpToStart = preText.substring(0, startChars);
            const textUpToEnd = preText.substring(0, endChars);
            
            const sLine = textUpToStart.split('\n').length;
            const eLine = textUpToEnd.split('\n').length;
            
            const selectedText = selection.toString();
            
            setStartLine(sLine);
            setEndLine(eLine);
            setSelectedTokens(Math.ceil(selectedText.length / 4));
            setSelectionActive(true);
        }
    };

    const handleIngest = async () => {
        setErrorMsg('');
        setSuccessMsg('');
        
        if ((endLine - startLine) > 250) {
            setErrorMsg('[FATAL] Context vapor limit exceeded. Max 250 lines.');
            return;
        }

        const payload = {
            child_app_id: appId,
            atom_type: atomType,
            relative_path: relativePath,
            directive: directive,
            token_boundary: { start_line: startLine, end_line: endLine }
        };

        try {
            await axios.post('/api/atomizer/ingest', payload);
            setSuccessMsg(`[SUCCESS] Atom extracted: ${relativePath} (L${startLine}-L${endLine})`);
        } catch (err) {
            setErrorMsg(`[FATAL] I/O Collapse: ${err.message}`);
        }
    };

    return (
        <div id="atomizer-panel" className="atomizer-container" style={{ padding: '1.5rem', background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border)', maxWidth: '1000px', margin: '0 auto', boxShadow: '0 8px 25px rgba(0,0,0,0.3)' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '1.5rem', color: 'var(--accent)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Atomizer Core</h2>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
                <div className="field-group" style={{ display: 'flex', flexDirection: 'column' }}>
                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Child App ID</label>
                    <select 
                        id="child-app-id" 
                        value={appId} 
                        onChange={(e) => setAppId(e.target.value)}
                        style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '0.6rem', borderRadius: '8px', fontSize: '0.85rem', fontFamily: 'var(--font)', outline: 'none' }}
                    >
                        {registryKeys.map(key => (
                            <option key={key} value={key}>{key}</option>
                        ))}
                    </select>
                </div>

                <div className="field-group" style={{ display: 'flex', flexDirection: 'column' }}>
                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Atom Type</label>
                    <select 
                        value={atomType} 
                        onChange={(e) => setAtomType(e.target.value)}
                        style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '0.6rem', borderRadius: '8px', fontSize: '0.85rem', fontFamily: 'var(--font)', outline: 'none' }}
                    >
                        <option value="backend_api">backend_api</option>
                        <option value="frontend_component">frontend_component</option>
                        <option value="database_schema">database_schema</option>
                        <option value="configuration">configuration</option>
                    </select>
                </div>

                <div className="field-group" style={{ display: 'flex', flexDirection: 'column', gridColumn: '1 / -1' }}>
                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Dynamic Pathing Binding</label>
                    <select 
                        id="relative-path" 
                        value={relativePath} 
                        onChange={(e) => setRelativePath(e.target.value)}
                        style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--success)', color: 'var(--success)', padding: '0.6rem', borderRadius: '8px', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace", outline: 'none' }}
                    >
                        {availableFiles.length === 0 && <option value="">-- No files discovered --</option>}
                        {availableFiles.map(file => (
                            <option key={file} value={file}>{file}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="preview-matrix" style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
                    <span>AST Context Preview</span>
                    <span style={{ color: 'var(--accent)' }}>Highlight to lock boundaries</span>
                </label>
                <div style={{ position: 'relative', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden', background: '#0d1117' }}>
                    {isLoadingFile && (
                        <div style={{ position: 'absolute', inset: 0, background: 'rgba(10, 14, 23, 0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
                            <span style={{ color: 'var(--accent)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem', animation: 'pulse 1.5s infinite' }}>Fetching Matrix...</span>
                        </div>
                    )}
                    <pre 
                        ref={preRef}
                        onMouseUp={handleMouseUp}
                        style={{ padding: '1rem', fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace", color: '#e2e8f0', overflowY: 'auto', maxHeight: '350px', width: '100%', whiteSpace: 'pre-wrap', userSelect: 'text', margin: 0 }}
                    >
                        {fileContent || "// No payload bound"}
                    </pre>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem', alignItems: 'flex-end' }}>
                <div className="field-group" style={{ display: 'flex', flexDirection: 'column' }}>
                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Directive</label>
                    <select 
                        value={directive} 
                        onChange={(e) => setDirective(e.target.value)}
                        style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '0.6rem', borderRadius: '8px', fontSize: '0.85rem', fontFamily: 'var(--font)', outline: 'none' }}
                    >
                        <option value="audit">audit</option>
                        <option value="refactor">refactor</option>
                        <option value="optimize">optimize</option>
                        <option value="security_scan">security_scan</option>
                    </select>
                </div>

                <div className="preflight-telemetry" style={{ padding: '1rem', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.3)', background: 'rgba(245, 158, 11, 0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--warning)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 700, marginBottom: '0.3rem' }}>Pre-Flight Telemetry</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>
                        <span>L{startLine} <span style={{ color: 'var(--text-muted)', margin: '0 0.5rem' }}>➜</span> L{endLine}</span>
                        <span style={{ color: selectedTokens > 2000 ? 'var(--danger)' : 'var(--success)', fontWeight: 600 }}>~{selectedTokens} Tokens</span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{selectionActive ? 'Block' : 'Full File'}</span>
                    </div>
                </div>
            </div>

            {errorMsg && (
                <div className="error-matrix" style={{ marginBottom: '1rem', padding: '0.75rem', border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', fontSize: '0.8rem', fontFamily: "'JetBrains Mono', monospace", borderRadius: '6px' }}>
                    {errorMsg}
                </div>
            )}
            
            {successMsg && (
                <div className="success-matrix" style={{ marginBottom: '1rem', padding: '0.75rem', border: '1px solid rgba(16, 185, 129, 0.3)', background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success)', fontSize: '0.8rem', fontFamily: "'JetBrains Mono', monospace", borderRadius: '6px' }}>
                    {successMsg}
                </div>
            )}

            <button 
                id="ingest-btn" 
                onClick={handleIngest}
                disabled={!appId || !relativePath || isLoadingFile}
                style={{ width: '100%', background: 'linear-gradient(135deg, var(--accent), #7c3aed)', color: 'white', fontWeight: 600, padding: '0.8rem 1rem', borderRadius: '8px', border: 'none', cursor: (!appId || !relativePath || isLoadingFile) ? 'not-allowed' : 'pointer', opacity: (!appId || !relativePath || isLoadingFile) ? 0.5 : 1, textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: '0.85rem', boxShadow: '0 4px 15px var(--accent-glow)' }}
            >
                Ingest Sub-Atomic Payload
            </button>
        </div>
    );
}