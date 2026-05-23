import React from 'react';
import NaturalLanguageGateway from './components/NaturalLanguageGateway';

export default function WarRoom() {
  return (
    <div className="war-room-container p-6 w-full h-full bg-[#0B0F19] text-gray-200">
      <div className="mb-6 border-b border-red-500/30 pb-4">
        <h1 className="text-4xl font-extrabold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-red-500 via-orange-500 to-purple-500" style={{ fontFamily: 'Outfit, sans-serif' }}>Adversarial War Room</h1>
        <p className="text-red-400/70 font-mono text-sm mt-2 uppercase">Threat modeling and logic stress-testing matrix. Input your target architecture.</p>
      </div>
      <div className="h-[calc(100%-100px)]">
        <NaturalLanguageGateway mode="warroom" />
      </div>
    </div>
  );
}
