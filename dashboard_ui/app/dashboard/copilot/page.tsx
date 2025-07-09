import React from 'react';
import CopilotChat from '../../../components/CopilotChat';

export default function CopilotPage() {
  return (
    <div className="h-full flex flex-col">
      <h2 className="text-xl font-semibold mb-4">Copilot Assistant</h2>
      <CopilotChat />
    </div>
  );
}
