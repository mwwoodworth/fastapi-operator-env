import React from 'react';

interface Props {
  item: any;
}

export default function MemoryResultCard({ item }: Props) {
  return (
    <div className="border p-4 rounded-md">
      <h3 className="font-semibold mb-2">{item.title || 'Untitled'}</h3>
      <p className="text-sm whitespace-pre-wrap">{item.content_chunk || item.content}</p>
    </div>
  );
}
