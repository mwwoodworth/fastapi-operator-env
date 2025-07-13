import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const { message, stream } = await req.json();
  if (!message) {
    return NextResponse.json({ error: 'message required' }, { status: 400 });
  }
  const base = process.env.NEXT_PUBLIC_API_BASE || '';
  try {
    const url = stream ? `${base}/chat/stream` : `${base}/chat`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    if (stream) {
      // Forward SSE stream directly to the client
      return new Response(res.body, {
        status: res.status,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    }
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json({ error: 'request failed' }, { status: 500 });
  }
}
