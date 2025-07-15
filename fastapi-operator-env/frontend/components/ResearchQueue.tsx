'use client';
import React, { useState } from 'react';
import { addResearch, listResearch } from '../utils/pipeline';

export default function ResearchQueue() {
  const [question, setQuestion] = useState('');
  const [items, setItems] = useState<any[]>(listResearch());

  function handleAdd() {
    if (!question.trim()) return;
    addResearch(question);
    setItems([...listResearch()]);
    setQuestion('');
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input className="flex-1 border px-2 py-1 rounded" value={question} onChange={e => setQuestion(e.target.value)} placeholder="Research question" />
        <button onClick={handleAdd} className="bg-primary text-primary-foreground px-3 py-1 rounded">Add</button>
      </div>
      <ul className="space-y-1 text-sm">
        {items.map((i, idx) => (
          <li key={idx} className="border p-1 rounded flex justify-between">
            <span>{i.question}</span>
            <span className="opacity-60">{i.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
