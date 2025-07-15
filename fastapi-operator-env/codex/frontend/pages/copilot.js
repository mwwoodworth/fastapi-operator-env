import { useState } from 'react';

export default function Copilot() {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');

  async function handleSend(e) {
    e.preventDefault();
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt }),
    });
    const data = await res.json();
    setResponse(data.response || '');
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-4">Copilot</h1>
      <form onSubmit={handleSend} className="mb-4">
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} className="border px-3 py-2 mr-2" placeholder="Ask..." />
        <button className="bg-green-600 text-white px-4 py-2" type="submit">Send</button>
      </form>
      {response && <pre className="whitespace-pre-wrap border p-4">{response}</pre>}
    </div>
  );
}
