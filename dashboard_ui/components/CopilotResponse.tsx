'use client';
import React from 'react';

interface Props {
  role: 'user' | 'ai';
  text: string;
}

export default function CopilotResponse({ role, text }: Props) {
  const isUser = role === 'user';
  return (
    <div className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'}`}> 
      <div
        className={`whitespace-pre-wrap max-w-[80%] px-3 py-2 rounded text-sm ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}
      >
        {text}
      </div>
    </div>
  );
}
