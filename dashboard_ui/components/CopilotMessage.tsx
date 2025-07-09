'use client';
import React from 'react';

export interface CopilotMsg {
  role: 'user' | 'ai';
  content: string;
}

export default function CopilotMessage({ message }: { message: CopilotMsg }) {
  const isUser = message.role === 'user';
  return (
    <div className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`whitespace-pre-wrap max-w-[80%] px-3 py-2 rounded text-sm ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}
      >
        <pre className="whitespace-pre-wrap font-sans text-sm">
          {message.content}
        </pre>
      </div>
    </div>
  );
}
