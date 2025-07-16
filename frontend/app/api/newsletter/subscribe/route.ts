import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const { email } = await req.json();
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ error: 'invalid email' }, { status: 400 });
  }
  const url = process.env.NEWSLETTER_API_URL;
  if (url) {
    try {
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${process.env.NEWSLETTER_API_KEY || ''}` },
        body: JSON.stringify({ email }),
      });
    } catch (err) {
      console.error(err);
    }
  }
  return NextResponse.json({ ok: true });
}
