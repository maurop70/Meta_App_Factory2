import React from 'react';
import NaturalLanguageGateway from './components/NaturalLanguageGateway';

export default function WarRoom() {
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
        </div>
        <div className="h-[550px]">
          <NaturalLanguageGateway mode="warroom" />
        </div>
      </div>
    </div>
  );
}
