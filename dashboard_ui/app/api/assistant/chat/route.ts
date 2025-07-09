import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const { message } = await req.json();
  if (!message) {
    return NextResponse.json({ error: 'message required' }, { status: 400 });
  }
  const base = process.env.NEXT_PUBLIC_API_BASE || '';
  try {
    const res = await fetch(`${base}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: 'request failed' }, { status: 500 });
  }
}
