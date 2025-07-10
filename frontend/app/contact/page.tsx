'use client';
import { useState } from 'react';

export const metadata = { title: 'Contact' };

export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('sending');
    const res = await fetch('/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, message }),
    });
    if (res.ok) {
      setStatus('sent');
      setName('');
      setEmail('');
      setMessage('');
    } else {
      setStatus('error');
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <h2 className="text-3xl font-semibold">Contact Us</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input className="w-full border p-2" placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
        <input className="w-full border p-2" type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
        <textarea className="w-full border p-2" rows={5} placeholder="Message" value={message} onChange={e => setMessage(e.target.value)} />
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Send</button>
      </form>
      {status === 'sent' && <p className='text-green-600'>Thanks! We\'ll be in touch.</p>}
      {status === 'error' && <p className='text-red-600'>Something went wrong.</p>}
    </div>
  );
}
