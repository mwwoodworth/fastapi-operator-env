# FastAPI Operator Dashboard

This Next.js app provides a realtime dashboard for the FastAPI operator server.
It uses Tailwind CSS, shadcn/ui style components and can be installed as a PWA.

## Setup

```bash
cd dashboard_ui
npm install
npm run dev
```

Set environment variables in `.env.local` or your hosting platform:

- `NEXT_PUBLIC_API_BASE` – base URL of the FastAPI server (default '')
- `NEXT_PUBLIC_AUTH_HEADER` – optional static `Authorization` header. JWT tokens will otherwise be read from `localStorage.token`.

## Build & Export

```bash
npm run build && npm run export
```

The static files will be in `../static/dashboard/` ready for hosting or serving from FastAPI at `/dashboard/ui`.

## Embed

Use this iframe snippet anywhere:

```html
<iframe src="/dashboard/ui" width="100%" height="600" style="border:0;"></iframe>
```

## Deploy

You can deploy the `dashboard_ui` folder to Vercel or Netlify as a static site.
