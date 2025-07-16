'use client';
import { useState } from 'react';

export const metadata = { title: 'Newsletter Signup' };

export default function NewsletterPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('sending');
    const res = await fetch('/api/newsletter/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (res.ok) {
      setStatus('sent');
      setEmail('');
    } else {
      setStatus('error');
    }
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <h2 className="text-3xl font-semibold">Join our Newsletter</h2>
      <p>Get product updates and BrainOps tips. Please confirm your subscription via the email we send.</p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input type="email" required className="flex-1 border p-2" placeholder="Your email" value={email} onChange={e => setEmail(e.target.value)} />
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Subscribe</button>
      </form>
      {status === 'sent' && <p className='text-green-600'>Check your inbox to confirm.</p>}
      {status === 'error' && <p className='text-red-600'>Subscription failed.</p>}
    </div>
  );
}
