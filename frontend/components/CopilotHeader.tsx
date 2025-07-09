'use client';
import React from 'react';

interface Props {
  model: string;
  onModelChange: (m: string) => void;
}

export default function CopilotHeader({ model, onModelChange }: Props) {
  return (
    <div className="flex items-center justify-between border-b p-2">
      <h2 className="font-semibold">Copilot V2</h2>
      <select
        className="border rounded px-2 py-1 text-sm"
        value={model}
        onChange={e => onModelChange(e.target.value)}
      >
        <option value="claude">Claude</option>
        <option value="chatgpt">ChatGPT</option>
        <option value="gemini">Gemini</option>
        <option value="disabled">Disabled</option>
      </select>
    </div>
  );
}
