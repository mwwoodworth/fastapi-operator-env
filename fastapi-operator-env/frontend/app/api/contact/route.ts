import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const { name, email, message } = await req.json();
  if (!name || !email || !message) {
    return NextResponse.json({ error: 'missing fields' }, { status: 400 });
  }
  const webhook = process.env.MAKE_WEBHOOK_URL;
  if (webhook) {
    try {
      await fetch(webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, message }),
      });
    } catch (err) {
      console.error(err);
    }
  }
  return NextResponse.json({ ok: true });
}
