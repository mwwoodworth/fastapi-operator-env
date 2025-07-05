import { useState } from 'react';

export default function FeedbackForm({ onSent }) {
  const [text, setText] = useState('');
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

  const send = async () => {
    if (!text) return;
    await fetch(`${API_BASE}/feedback/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    setText('');
    onSent && onSent();
  };

  return (
    <div className="space-y-2">
      <textarea
        className="w-full border p-2 rounded"
        rows="3"
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Report a bug or suggestion"
      />
      <button className="px-3 py-1 border rounded" onClick={send}>
        Submit
      </button>
    </div>
  );
}
