'use client';
import React, { useState } from 'react';
import { readSSE } from '../utils/sse';

interface Msg { role: 'user' | 'assistant'; text: string; }

export default function AssistantChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim()) return;
    const user = input;
    setInput('');
    let aiIndex = 0;
    setMsgs(prev => {
      aiIndex = prev.length + 1;
      return [...prev, { role: 'user', text: user }, { role: 'assistant', text: '' }];
    });
    setLoading(true);
    try {
      const res = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: user, stream: true }),
      });
      if (res.headers.get('content-type')?.includes('text/event-stream')) {
        // Consume token stream and append chunks in real time
        await readSSE(res, token => {
          setMsgs(m => {
            const copy = [...m];
            copy[aiIndex].text += token;
            return copy;
          });
        });
      } else {
        const data = await res.json();
        const text = data.response || data.result || data.completion || '';
        setMsgs(m => {
          const copy = [...m];
          copy[aiIndex].text = text;
          return copy;
        });
      }
    } catch (e) {
      setMsgs(m => {
        const copy = [...m];
        copy[aiIndex].text = 'Error';
        return copy;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-4 right-4 bg-primary text-primary-foreground px-4 py-2 rounded-full"
      >
        {open ? 'Close' : 'Chat'}
      </button>
      {open && (
        <div className="fixed bottom-16 right-4 bg-background border rounded shadow-lg w-80 max-h-96 flex flex-col">
          <div className="flex-1 p-2 overflow-auto space-y-2">
            {msgs.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                <span className="text-sm whitespace-pre-wrap">{m.text}</span>
              </div>
            ))}
            {loading && <p className="text-sm opacity-50">...</p>}
          </div>
          <form
            onSubmit={e => { e.preventDefault(); send(); }}
            className="p-2 border-t flex gap-2"
          >
            <input
              className="flex-1 border px-2 py-1 rounded"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Message"
            />
            <button type="submit" disabled={loading} className="bg-primary text-primary-foreground px-3 py-1 rounded">
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
