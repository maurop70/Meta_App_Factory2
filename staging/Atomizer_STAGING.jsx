import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function Atomizer() {
    const [registryKeys, setRegistryKeys] = useState([]);
    const [appId, setAppId] = useState('');
    const [atomType, setAtomType] = useState('frontend_component');
    const [relativePath, setRelativePath] = useState('');
    const [startLine, setStartLine] = useState(1);
    const [endLine, setEndLine] = useState(250);
    const [directive, setDirective] = useState('audit');
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        const fetchRegistry = async () => {
            try {
                const response = await axios.get('/registry.json');
                const keys = Object.keys(response.data);
                setRegistryKeys(keys);
                if (keys.length > 0) setAppId(keys[0]);
            } catch (err) {
                console.error("Failed to load registry keys", err);
            }
        };
        fetchRegistry();
    }, []);

    const handleIngest = async () => {
        setErrorMsg('');
        
        const start = parseInt(startLine, 10);
        const end = parseInt(endLine, 10);
        
        if (isNaN(start) || isNaN(end) || start <= 0 || end <= 0) {
            setErrorMsg('[FATAL] Token boundaries must be strict positive integers.');
            return;
        }
        
        if ((end - start) > 250) {
            setErrorMsg('[FATAL] Context vapor limit exceeded. Max 250 lines.');
            return;
        }

        const payload = {
            child_app_id: appId,
            atom_type: atomType,
            relative_path: relativePath,
            directive: directive,
            token_boundary: { start_line: start, end_line: end }
        };

        try {
            await axios.post('/api/atomizer/ingest', payload);
        } catch (err) {
            setErrorMsg(`[FATAL] I/O Collapse: ${err.message}`);
        }
    };

    return (
        <div id="atomizer-panel" className="atomizer-container">
            <div className="field-group">
                <label>Child App ID</label>
                <select id="child-app-id" value={appId} onChange={(e) => setAppId(e.target.value)}>
                    {registryKeys.map(key => (
                        <option key={key} value={key}>{key}</option>
                    ))}
                </select>
            </div>

            <div className="field-group">
                <label>Atom Type</label>
                <select value={atomType} onChange={(e) => setAtomType(e.target.value)}>
                    <option value="backend_api">backend_api</option>
                    <option value="frontend_component">frontend_component</option>
                    <option value="database_schema">database_schema</option>
                    <option value="configuration">configuration</option>
                </select>
            </div>

            <div className="field-group">
                <label>Relative Path</label>
                <input 
                    id="relative-path" 
                    type="text" 
                    value={relativePath} 
                    onChange={(e) => setRelativePath(e.target.value)} 
                />
            </div>

            <div className="field-group token-boundary">
                <div className="boundary-input">
                    <label>Start Line</label>
                    <input 
                        type="number" 
                        min="1" 
                        value={startLine} 
                        onChange={(e) => setStartLine(e.target.value)} 
                    />
                </div>
                <div className="boundary-input">
                    <label>End Line</label>
                    <input 
                        type="number" 
                        min="1" 
                        value={endLine} 
                        onChange={(e) => setEndLine(e.target.value)} 
                    />
                </div>
            </div>

            <div className="field-group">
                <label>Directive</label>
                <select value={directive} onChange={(e) => setDirective(e.target.value)}>
                    <option value="audit">audit</option>
                    <option value="refactor">refactor</option>
                    <option value="optimize">optimize</option>
                    <option value="security_scan">security_scan</option>
                </select>
            </div>

            {errorMsg && (
                <div className="error-matrix">
                    {errorMsg}
                </div>
            )}

            <button id="ingest-btn" onClick={handleIngest}>
                Ingest Atom
            </button>
        </div>
    );
}