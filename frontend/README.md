# Skills frontend

React 18 + TypeScript + Vite. Portals (freelancer, work host, organisation, admin) are added under `src/portals/`. See `docs/specification/06-frontend.md`.

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api and /health to VITE_API_PROXY (default http://localhost:8000)
npm run lint && npm run format:check && npm run typecheck && npm test
```
