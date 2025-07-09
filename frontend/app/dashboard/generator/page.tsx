import React from 'react';
import GeneratorPanel from '../../../components/GeneratorPanel';

export default function GeneratorPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Claude Product Generator</h2>
      <GeneratorPanel />
    </div>
  );
}
