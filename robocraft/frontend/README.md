# RoboCraft web app

Next.js 16 (App Router) + React Three Fiber + Tailwind CSS v4. See
[`../README.md`](../README.md) for the full project overview.

```bash
npm install
npm run dev          # http://localhost:3000, expects the API on http://127.0.0.1:8000
npm run lint
npm run typecheck
npm run build
```

`BACKEND_URL` sets where `/api/*` is proxied to. It is read at build time.

Code map:

- `src/app/`: the landing page and `studio/[template]`.
- `src/components/studio/`:
  - panels: parameters (generated from the API's template spec), pose, insights tabs;
  - the wiring diagram renderer;
  - the code viewer.
- `src/components/viewport/`: the 3D scene. The robot models use a Z-up robot frame, the
  same frame as the backend maths.
- `src/lib/`:
  - the typed API client;
  - the zustand store;
  - data hooks (debounced analysis, latest-wins pose requests, code generation);
  - playback interpolation.
