# Harvest2Value — frontend

Next.js 16 (App Router), React 19, Tailwind v4, TypeScript strict. Il affiche ce que calcule l'API
`/api/v2` ; aucune logique métier côté client.

```bash
npm install
npm run dev          # http://localhost:5173 (API attendue sur NEXT_PUBLIC_API_URL, défaut http://localhost:8000)
npm run build && npm start
```

Structure, tests et déploiement : voir `../README.md` et `../docs/` (architecture, testing, deployment).
