# Site público

Frontend estático do eleitorado (Vite + React + TypeScript), publicado pelo Cloudflare Pages a
cada push na `main`. Ele só lê os arquivos JSON que o pipeline publica em `site/` no R2.

- Desenho: `docs/superpowers/specs/2026-10-07-site-publico-design.md`.
- Visual: `DESIGN.md` (as adaptações do topo prevalecem).
- Contrato dos dados: `esquemas/` (JSON Schemas) e `exemplos/` (dados fictícios no layout do R2).

## Rodar

```bash
npm ci
npm run dev        # http://localhost:5173, com os dados de exemplos/
npm test           # Vitest + Testing Library
npm run lint
npm run typecheck
npm run build      # dist/
```

Com os dados reais: `VITE_DADOS_URL=https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/site npm run dev`
(a regra de CORS do R2 precisa liberar `http://localhost:5173`).

## Estrutura

- `src/dados.ts`: baixa os arquivos, confere `esquema === 1`, guarda na memória; erros `rede`,
  `esquema` e `nao_encontrado`.
- `src/busca.ts`: busca por nome e CNPJ; as regras de palavra são as de
  `dbt/models/site/site_arquivos_busca.sql`.
- `src/componentes/`, `src/paginas/`: telas. Todo alerta passa por `componentes/Alertas.tsx`
  (aviso fixo, explicação do tipo, correspondência fraca à parte).
- `public/_redirects` (rotas da SPA) e `public/_headers` (CSP: se o endereço dos dados mudar,
  mude o `connect-src`).

## Mudança no formato dos dados

Mude no mesmo PR o modelo `site_*`, o esquema em `esquemas/`, os exemplos em `exemplos/`,
`src/tipos.ts` e as telas que usam o campo (AGENTS.md, Convenções).
