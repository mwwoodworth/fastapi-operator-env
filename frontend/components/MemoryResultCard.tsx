import React from 'react';

interface MemoryResult {
  title?: string;
  content_chunk?: string;
  content?: string;
}

interface MemoryResultCardProps {
  result: MemoryResult;
  key?: any;
}

export default function MemoryResultCard({ result }: MemoryResultCardProps) {
  return (
    <div className="border rounded p-4 bg-background">
      {result.title && <h3 className="font-semibold mb-2">{result.title}</h3>}
      <p className="text-sm whitespace-pre-wrap">{result.content_chunk}</p>
    </div>
  );
}
