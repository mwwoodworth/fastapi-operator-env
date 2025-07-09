import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { prompt } = req.body ?? {};
  const base = process.env.NEXT_PUBLIC_API_BASE || '';
  try {
    const upstream = await fetch(`${base}/chatgpt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    res.status(upstream.status);
    if (upstream.body) {
      for await (const chunk of upstream.body as any) {
        res.write(chunk);
      }
      res.end();
    } else {
      const data = await upstream.json();
      res.json(data);
    }
  } catch (e) {
    res.status(500).json({ error: 'request failed' });
  }
}
