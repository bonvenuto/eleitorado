# Plano 11: frontend do site público

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** um site estático em `site/` (publicado pelo Cloudflare Pages) em que o cidadão e o
jornalista buscam um parlamentar ou uma empresa pelo nome ou CNPJ e veem, em linguagem simples,
a cota, as emendas, o que a empresa recebeu do governo federal e os alertas automáticos, com a
regra explicada, o aviso de cautela e o caminho até a fonte oficial.

**Architecture:** SPA em Vite + React + TypeScript estrito, com React Router. O site só lê os
arquivos JSON que o plano 10 publica em `site/` no R2 (`VITE_DADOS_URL`; em desenvolvimento e
nos testes, `site/exemplos/`). Um módulo `dados.ts` baixa cada arquivo, confere `esquema === 1`,
guarda o resultado na memória e traduz falhas em três motivos (`rede`, `esquema`,
`nao_encontrado`). A busca (`busca.ts`) segue a spec, seção 4.2: o navegador baixa o bloco das 3
(ou 4) primeiras letras e filtra. As telas montam componentes pequenos (busca, cartão de alerta,
gráfico com tabela) sobre esses módulos. O contrato com o pipeline são os JSON Schemas de
`site/esquemas/`, validados nos testes com `ajv`, e os tipos de `src/tipos.ts`, conferidos contra
os exemplos pelo `tsc`.

**Tech Stack:** Node 22 (≥ 22.13), npm; Vite 8, React 19.3, React Router 8, TypeScript 6.0
(estrito), Tailwind CSS 4.3 (`@tailwindcss/vite`), Observable Plot 0.6, `@fontsource/dm-sans` e
`@fontsource/geist` 5.3; Vitest 5 + Testing Library + jsdom 29; `ajv` 8; ESLint 10 com
`typescript-eslint` 8 e `eslint-plugin-react-hooks` 7; GitHub Actions (`actions/setup-node`
v7.0.0).

**Spec:** `docs/superpowers/specs/2026-10-07-site-publico-design.md` (seções 3, 6, 7, 8 e 9).
Visual: `site/DESIGN.md` (as adaptações do topo prevalecem). Contrato: `site/esquemas/` e
`site/exemplos/`.

**Protótipo do plano (2026-10-07, fora do repositório):** as dependências da tarefa 1 foram
instaladas juntas (Node 22.22.0, npm 10.9.4); o código completo das tarefas 1 a 10 e os testes
de todas as tarefas rodaram com uma versão rápida das páginas: 180 testes verdes (três vezes
seguidas, e também com a faixa de dados antigos ligada), `eslint` e `tsc` limpos, `vite build`
ok, e as provas de mutação das tarefas 3 a 10 falharam como descrito.

## Global Constraints

- Código, comentários, docs, commits e PR em português (os nomes de API das bibliotecas ficam como
  são). Textos da interface em português do Brasil, em linguagem simples.
- Trabalhe no branch `feat/site-frontend`, criado a partir da `main`. Nunca commite na `main`.
- Não faça merge, não dispare workflow (`gh workflow run`) e não mexa em secrets, settings ou
  rulesets sem o ok do usuário. Não crie nada na Cloudflare: o projeto do Pages e a regra de CORS
  são passos do usuário (seção "Depois do merge").
- Tudo do frontend fica em `site/`. Não altere `site/esquemas/` nem `site/exemplos/` (são o
  contrato do plano 10; mudar formato exige mudar os dois lados no mesmo PR, conforme AGENTS.md).
  A única exceção é a prova de mutação da tarefa 2, que é desfeita no mesmo passo.
- Versões: as do `package.json` da tarefa 1. TypeScript fica em `~6.0.3` porque o
  `typescript-eslint` 8 aceita `<6.1.0`; jsdom fica em `^29.1.1` porque o 30 exige Node
  ≥ 22.22.2. Se o `npm install` acusar conflito de peer, resolva com a versão compatível mais
  nova e registre a troca no PR; nunca use `--force` nem `--legacy-peer-deps`.
- `VITE_DADOS_URL`: o padrão de produção é
  `https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/site`; em desenvolvimento (`npm run dev`)
  é `/exemplos`, servido de `site/exemplos/` por um plugin do Vite; nos testes o `fetch` é
  substituído por um dublê que lê `site/exemplos/`. Os testes nunca acessam a rede.
- Os arquivos do R2 vêm em gzip com `Content-Encoding: gzip`: o navegador descomprime sozinho e o
  código só faz `fetch(...).json()`. Nada de descompressão manual.
- Nomes de arquivo (spec, seção 4.2): `busca/parlamentares.json`,
  `busca/empresas/p_<prefixo>.json` (3 ou 4 caracteres `[a-z0-9]`), `empresa/b_<3 primeiros
  caracteres da raiz>.json`, `parlamentar/<casa>-<id>.json` (o id `camara:204554` vira
  `camara-204554`), `alertas/<tipo>/<n>.json`, `resumo.json`.
- Cautela nos alertas (spec, seção 6): todo alerta mostra a `descricao`, o título, a explicação e
  a cautela do tipo (vindos do `resumo.json`, nunca escritos no código), a regra, o aviso fixo
  "Indício gerado automaticamente a partir de dados públicos; não é acusação nem constatação de
  irregularidade.", a data dos dados e o link para a fonte oficial. Alertas `fraca` ficam num
  grupo separado, abaixo dos `forte`, com o aviso específico. **Nada de vermelho:** o âmbar
  (`--color-alerta: #f2a65a`) é a única cor de alerta, só em selos e marcações pequenas.
- Acessibilidade: `lang="pt-BR"`; todo gráfico tem tabela equivalente atrás de um botão "Ver
  tabela" (`aria-expanded`); tudo funciona pelo teclado, com foco visível e link "Pular para o
  conteúdo"; contraste AA (texto ≥ 4,5:1; `#686868`/Slate só em texto ≥ 18px ou decorativo);
  números e datas em pt-BR com `Intl`.
- Privacidade (spec, seção 7): sem cookies, sem `localStorage`, sem analytics, sem fontes ou
  scripts externos. As fontes vêm do `@fontsource`, empacotadas pelo Vite. As únicas origens
  externas são o R2 (dados) e as fotos oficiais de `*.camara.leg.br` e `*.senado.leg.br`
  (`public/_headers`, CSP).
- O site nunca mostra sócios (só a contagem `cadastro.socios`) e não oferece busca por CPF.
- Rotas de SPA: `site/public/_redirects` com `/* /index.html 200`.
- Testes: Vitest + Testing Library, `jsdom`. Dados sempre de `site/exemplos/` (via o dublê
  `servir()`), alterados no próprio teste quando o caso pede. Para o tempo, só
  `vi.useFakeTimers({ toFake: ['Date'] })` (relógios falsos completos travam o `user-event`).
- Ações do GitHub fixadas por SHA, com a versão em comentário. `actions/checkout`: o mesmo do
  `ci.yml` (`3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`). `actions/setup-node`:
  `820762786026740c76f36085b0efc47a31fe5020 # v7.0.0` (obtido com
  `git ls-remote https://github.com/actions/setup-node refs/tags/v7.0.0`; a tag é leve, então o
  SHA é o do commit).
- Antes de cada commit, rode em `site/`: `npm run lint`, `npm run typecheck` e `npm test`. Na
  tarefa final, também `npm run build` e as verificações Python do AGENTS.md (o PR não muda
  Python, mas o check `testes` precisa continuar verde).

## Review Focus

- **Cautela em todo alerta:** nenhum caminho de tela mostra um alerta sem o aviso fixo, sem a
  explicação do tipo ou sem a fonte; `fraca` sempre num grupo separado, depois dos `forte`.
  Testes: `todo alerta traz o aviso fixo` e `fraca fica num grupo separado, depois das fortes`
  (tarefa 9), repetidos nas páginas (tarefas 11 a 14).
- **Nada de vermelho e contraste AA:** a paleta padrão do Tailwind é removida
  (`--color-*: initial`), então `text-red-500` nem é gerado. Testes: `nenhuma cor do tema é
  vermelha`, `pares de texto têm contraste AA` e `nenhuma classe vermelha no código` (tarefa 6).
- **Busca igual ao índice do pipeline:** a normalização (`lower` + `strip_accents` + divisão em
  `[^a-z0-9]+`), as palavras ignoradas e o mínimo de 3 caracteres precisam ser os mesmos de
  `dbt/models/site/site_arquivos_busca.sql`, senão o site procura no bloco errado. Bloco
  subdividido: com 3 letras mostra as empresas de palavra de exatamente 3 letras e pede mais uma
  letra; com 4 ou mais usa o bloco de 4. Testes: `busca.test.ts` (tarefa 5) e
  `caixa de busca` (tarefa 7).
- **CNPJ × nome:** consulta com 8 ou 14 caracteres de CNPJ (com ou sem `.`, `/`, `-`; letras
  aceitas no CNPJ alfanumérico) vai direto à empresa; mas um nome de 8 letras (`construt`) não
  pode ser lido como CNPJ. Regra adotada: a raiz precisa ter ao menos um dígito; espaço no meio
  desqualifica; o CNPJ de 14 termina em 2 dígitos. Teste: `raizDaConsulta` (tarefa 5).
- **Falhas de rede não ficam no cache:** sem isso, "Tentar de novo" nunca funcionaria. Teste:
  `falha de rede não fica no cache` (tarefa 4).
- **Caminhos montados a partir da URL:** `slug`, `raiz`, `tipo` e `pagina` vêm da barra de
  endereço; tudo é validado por expressão regular antes de virar caminho de arquivo (nada de
  `..`). Testes: `slug inválido não baixa nada` e `raiz inválida não baixa nada` (tarefa 4).
- **CSP (`public/_headers`):** se a origem do `VITE_DADOS_URL` mudar (domínio próprio), o
  `connect-src` precisa mudar junto, senão o site para de carregar dados. Teste: `a CSP libera a
  origem dos dados` (tarefa 6). As fotos do Senado vêm em `http://` e são trocadas por `https://`
  (`urlDaFoto`, tarefa 4).
- **Tipos × esquemas:** `src/tipos.ts` é escrito à mão. O `tsc` confere que cada exemplo cabe no
  tipo (`Ampliar<T>`, tarefa 2), e o `ajv` confere os exemplos contra os esquemas; um campo que
  exista no esquema e falte no tipo não é detectado, então compare os dois na revisão.
- **Links de fonte oficial** (`src/fontes.ts`) e o link da empresa no Portal da Transparência:
  o Portal recusa clientes que não são navegador (405), então eles são conferidos no navegador
  (tarefa 16, passo 5).

## Mapa de arquivos

| Arquivo | Tarefa | Responsabilidade |
|---|---|---|
| `site/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js` | 1 | Projeto, scripts, TypeScript estrito, plugin que serve `exemplos/`, Vitest |
| `site/index.html`, `site/public/_redirects`, `site/public/favicon.svg` | 1 | Página base (`lang="pt-BR"`), rotas de SPA, ícone |
| `site/src/main.tsx`, `src/Rotas.tsx`, `src/vite-env.d.ts`, `src/teste/setup.ts` | 1 (8) | Entrada, rotas (esqueleto na 1, completas na 8), tipos do ambiente, setup dos testes |
| `site/src/estrutura.test.tsx` | 1 | `lang`, `_redirects`, sem recursos externos no HTML |
| `site/src/tipos.ts`, `src/contrato.test.ts` | 2 | Tipos dos arquivos; exemplos × esquemas (ajv) e exemplos × tipos (tsc) |
| `site/src/formato.ts` (+ teste) | 3 | Reais, inteiros, percentuais, datas, competência, CNPJ, dados desatualizados |
| `site/src/caminhos.ts`, `src/dados.ts`, `src/teste/exemplos.ts` (+ testes) | 4 | Rotas e nomes de arquivo; download, esquema, cache e erros; dublê do `fetch` |
| `site/src/busca.ts` (+ teste) | 5 | Normalização, CNPJ, palavras ignoradas, blocos, filtro |
| `site/src/index.css`, `public/_headers`, `src/tema.test.ts`, `src/privacidade.test.ts` | 6 | Tokens do DESIGN.md, sem vermelho, contraste, CSP, sem rastreamento |
| `site/src/useDados.ts`, `src/componentes/CaixaBusca.tsx`, `src/teste/rotas.tsx` (+ teste) | 7 | Hook de carregamento; caixa de busca; ajuda de rotas nos testes |
| `site/src/componentes/{Layout,Navegacao,FaixaDesatualizada,Estados}.tsx`, `src/useTitulo.ts`, `src/paginas/NaoEncontrada.tsx` (+ teste) | 8 | Layout, navegação, faixa de dados velhos, erros, 404 |
| `site/src/fontes.ts`, `src/componentes/Alertas.tsx` (+ testes) | 9 | Fonte oficial de cada alerta; cartão e lista com cautela |
| `site/src/componentes/GraficoBarras.tsx` (+ teste) | 10 | Gráfico (Plot) com tabela equivalente |
| `site/src/paginas/Inicio.tsx` (+ teste) | 11 | `/` |
| `site/src/paginas/Parlamentar.tsx` (+ teste) | 12 | `/parlamentar/:slug` |
| `site/src/paginas/Empresa.tsx` (+ teste) | 13 | `/empresa/:raiz` |
| `site/src/paginas/Alertas.tsx` (+ teste) | 14 | `/alertas` |
| `site/src/paginas/Sobre.tsx` (+ teste) | 15 | `/sobre` |
| `.github/workflows/ci.yml`, `.gitignore`, `site/README.md`, `AGENTS.md`, `docs/roteiro.md` | 16 | Job `site` no CI, ignorados, documentação |

## Como rodar (vale para todas as tarefas)

No diretório `site/` (Git Bash ou PowerShell, os comandos são iguais):

```bash
npm ci                                   # depois que o package-lock.json existir
npm run lint
npm run typecheck
npm test                                 # vitest run, a suíte inteira
npm test -- src/busca.test.ts            # um arquivo
npm test -- -t "falha de rede"           # um teste pelo nome
npm run dev                              # http://localhost:5173, dados de site/exemplos/
npm run build                            # tsc --noEmit + vite build em dist/
```

Para ver o site com os dados reais em desenvolvimento (depois que a regra de CORS do R2 incluir
`http://localhost:5173`):
`VITE_DADOS_URL=https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/site npm run dev`
(PowerShell: `$env:VITE_DADOS_URL = "https://..."; npm run dev`).

---

### Task 1: Esqueleto do projeto

**Files:**
- Create: `site/package.json`, `site/package-lock.json` (gerado), `site/tsconfig.json`,
  `site/vite.config.ts`, `site/eslint.config.js`, `site/index.html`, `site/public/_redirects`,
  `site/public/favicon.svg`, `site/src/main.tsx`, `site/src/Rotas.tsx` (esqueleto),
  `site/src/vite-env.d.ts`, `site/src/teste/setup.ts`, `site/src/estrutura.test.tsx`
- Modify: `.gitignore`

**Interfaces:**
- Produces: scripts `dev`, `build`, `preview`, `lint`, `typecheck`, `test`; `Rotas` (componente
  de rotas, sem roteador, para `BrowserRouter` em produção e `MemoryRouter` nos testes); o
  servidor de desenvolvimento responde `/exemplos/<caminho>` com `site/exemplos/<caminho>`.

- [ ] **Step 1: Ignore as pastas geradas**

Em `.gitignore` (raiz do repositório), ao fim:

```gitignore

# site (frontend)
site/node_modules/
site/dist/
```

- [ ] **Step 2: Crie `site/package.json`**

```json
{
  "name": "eleitorado-site",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "engines": {
    "node": ">=22.13.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "@fontsource/dm-sans": "^5.3.0",
    "@fontsource/geist": "^5.3.0",
    "@observablehq/plot": "^0.6.17",
    "react": "^19.3.0",
    "react-dom": "^19.3.0",
    "react-router": "^8.4.0"
  },
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@tailwindcss/vite": "^4.3.3",
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.7",
    "@types/node": "^22.20.5",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.2",
    "ajv": "^8.20.0",
    "eslint": "^10.12.0",
    "eslint-plugin-react-hooks": "^7.1.1",
    "globals": "^17.13.0",
    "jsdom": "^29.1.1",
    "tailwindcss": "^4.3.3",
    "typescript": "~6.0.3",
    "typescript-eslint": "^8.71.1",
    "vite": "^8.3.3",
    "vitest": "^5.0.3"
  }
}
```

Run: `cd site && npm install --no-audit --no-fund`
Expected: `added N packages`, sem `ERESOLVE`; `site/package-lock.json` criado. (Essas versões
foram instaladas juntas num protótipo em 2026-10-07, com Node 22.22.0 e npm 10.9.4, sem aviso
de engine.)

- [ ] **Step 3: Configurações**

`site/tsconfig.json` (no TypeScript 6 o padrão de `types` é vazio, por isso a lista explícita):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client", "node"]
  },
  "include": ["src", "vite.config.ts"]
}
```

`site/vite.config.ts`:

```ts
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

const EXEMPLOS = path.join(path.dirname(fileURLToPath(import.meta.url)), 'exemplos')

// Em desenvolvimento, /exemplos/<caminho> serve site/exemplos/<caminho> (os dados fictícios do
// contrato). Não entra no build: a pasta exemplos/ não é publicada.
function servirExemplos(): Plugin {
  return {
    name: 'servir-exemplos',
    apply: 'serve',
    configureServer(servidor) {
      servidor.middlewares.use('/exemplos', (pedido, resposta) => {
        const relativo = decodeURIComponent((pedido.url ?? '/').split('?')[0] ?? '/')
        const arquivo = path.resolve(EXEMPLOS, `.${relativo}`)
        const dentro = arquivo.startsWith(EXEMPLOS + path.sep) && arquivo.endsWith('.json')
        if (!dentro) {
          resposta.statusCode = 404
          resposta.end()
          return
        }
        readFile(arquivo).then(
          (conteudo) => {
            resposta.setHeader('Content-Type', 'application/json; charset=utf-8')
            resposta.end(conteudo)
          },
          () => {
            resposta.statusCode = 404
            resposta.end()
          },
        )
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), servirExemplos()],
  test: {
    environment: 'jsdom',
    setupFiles: ['src/teste/setup.ts'],
    env: { VITE_DADOS_URL: '/exemplos' },
    restoreMocks: true,
  },
})
```

`site/eslint.config.js`:

```js
import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import { defineConfig } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig(
  { ignores: ['dist', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.strict, reactHooks.configs.flat.recommended],
    languageOptions: { globals: globals.browser },
  },
)
```

`site/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Endereço da pasta site/ no R2 (sem barra no fim). Vazio: padrão de produção. */
  readonly VITE_DADOS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

- [ ] **Step 4: Página base, rotas de SPA e entrada**

`site/index.html`:

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta
      name="description"
      content="Gastos de parlamentares, emendas e contratos federais, com alertas automáticos explicados. Dados públicos oficiais."
    />
    <meta name="color-scheme" content="dark" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>Eleitorado</title>
  </head>
  <body>
    <div id="raiz"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`site/public/_redirects` (uma linha, com quebra de linha no fim):

```text
/* /index.html 200
```

`site/public/favicon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0a0a0a"/><circle cx="16" cy="16" r="7" fill="none" stroke="#ededed" stroke-width="2.5"/><circle cx="16" cy="16" r="2.5" fill="#f2a65a"/></svg>
```

`site/src/Rotas.tsx` (esqueleto; a tarefa 8 troca pelo definitivo):

```tsx
export function Rotas() {
  return <h1>Eleitorado</h1>
}
```

`site/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { Rotas } from './Rotas'

const raiz = document.getElementById('raiz')
if (!raiz) throw new Error('elemento #raiz não encontrado')

createRoot(raiz).render(
  <StrictMode>
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  </StrictMode>,
)
```

`site/src/teste/setup.ts` (a tarefa 4 acrescenta o dublê do `fetch`):

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
```

- [ ] **Step 5: Escreva o teste**

`site/src/estrutura.test.tsx` (no ambiente jsdom, `new URL(..., import.meta.url)` não serve para
`fileURLToPath`; por isso o caminho parte de `fileURLToPath(import.meta.url)`, como no protótipo):

```ts
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { Rotas } from './Rotas'

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ler = (relativo: string) => readFileSync(path.join(SITE, relativo), 'utf-8')

describe('estrutura do site', () => {
  it('a página base declara pt-BR', () => {
    expect(ler('index.html')).toMatch(/<html lang="pt-BR">/)
  })

  it('o HTML não carrega nada de fora', () => {
    expect(ler('index.html')).not.toMatch(/(src|href)="(https?:)?\/\//)
  })

  it('toda rota volta para o index.html (SPA no Cloudflare Pages)', () => {
    expect(ler('public/_redirects')).toBe('/* /index.html 200\n')
  })

  it('a aplicação renderiza', () => {
    render(
      <MemoryRouter>
        <Rotas />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Eleitorado' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Veja passar e confira o resto**

Run: `cd site && npm test && npm run lint && npm run typecheck && npx vite build`
Expected: 4 testes PASS; lint e tsc sem erro; `dist/` com `index.html`, `_redirects`,
`favicon.svg` e `assets/`. Com `npm run dev`, `http://localhost:5173/exemplos/resumo.json`
responde o JSON e `http://localhost:5173/exemplos/../package.json` responde 404.

- [ ] **Step 7: Prova de mutação**

Em `site/index.html`, troque `lang="pt-BR"` por `lang="en"`. Run:
`npm test -- -t "pt-BR"`. Expected: FAIL. Desfaça e confirme o PASS.

- [ ] **Step 8: Commit**

```bash
git add .gitignore site/package.json site/package-lock.json site/tsconfig.json \
  site/vite.config.ts site/eslint.config.js site/index.html site/public site/src
git commit -m "feat(site): esqueleto do frontend (Vite, React, TypeScript estrito, Vitest)"
```

---

### Task 2: Tipos e contrato

**Files:**
- Create: `site/src/tipos.ts`, `site/src/contrato.test.ts`

**Interfaces:**
- Produces: os tipos `Casa`, `Correspondencia`, `Alerta`, `Alertas`, `ParlamentarResumo`,
  `AlertaTipo`, `Fonte`, `FonteReduzida`, `Resumo`, `BuscaParlamentares`, `EmpresaNaBusca`,
  `BuscaEmpresas`, `Parlamentar`, `ArquivoParlamentar`, `Cadastro`, `Sancao`, `Empresa`,
  `BlocoEmpresas`, `PaginaAlertas`.

- [ ] **Step 1: Escreva o teste**

`site/src/contrato.test.ts`:

```ts
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import Ajv2020 from 'ajv/dist/2020'
import { describe, expect, it } from 'vitest'
import alertasJson from '../exemplos/alertas/cota_fornecedor_sancionado/1.json'
import pConJson from '../exemplos/busca/empresas/p_con.json'
import pEmpJson from '../exemplos/busca/empresas/p_emp.json'
import parlamentaresJson from '../exemplos/busca/parlamentares.json'
import blocoJson from '../exemplos/empresa/b_112.json'
import camaraJson from '../exemplos/parlamentar/camara-900001.json'
import senadoJson from '../exemplos/parlamentar/senado-900002.json'
import resumoJson from '../exemplos/resumo.json'
import type {
  ArquivoParlamentar,
  BlocoEmpresas,
  BuscaEmpresas,
  BuscaParlamentares,
  PaginaAlertas,
  Resumo,
} from './tipos'

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ESQUEMAS = path.join(SITE, 'esquemas')
const EXEMPLOS = path.join(SITE, 'exemplos')
const BASE = 'https://eleitorado.pages.dev/esquemas/'
const TIPOS = ['resumo', 'busca-parlamentares', 'busca-empresas', 'parlamentar', 'empresa', 'alertas']

function tipoDoCaminho(caminho: string): string {
  if (caminho === 'resumo.json') return 'resumo'
  if (caminho === 'busca/parlamentares.json') return 'busca-parlamentares'
  if (caminho.startsWith('busca/empresas/')) return 'busca-empresas'
  const pasta = caminho.split('/')[0] ?? ''
  if (['parlamentar', 'empresa', 'alertas'].includes(pasta)) return pasta
  throw new Error(`caminho sem tipo: ${caminho}`)
}

function criarAjv(): Ajv2020 {
  const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true })
  for (const nome of readdirSync(ESQUEMAS).filter((n) => n.endsWith('.schema.json'))) {
    ajv.addSchema(JSON.parse(readFileSync(path.join(ESQUEMAS, nome), 'utf-8')))
  }
  return ajv
}

function validar(tipo: string, documento: unknown): string[] {
  const validador = criarAjv().getSchema(`${BASE}${tipo}.schema.json`)
  if (!validador) throw new Error(`esquema ${tipo} não encontrado`)
  validador(documento)
  return (validador.errors ?? []).map((e) => `${e.instancePath} ${e.message ?? ''}`)
}

const exemplos = readdirSync(EXEMPLOS, { recursive: true, encoding: 'utf-8' })
  .map((c) => c.replaceAll('\\', '/'))
  .filter((c) => c.endsWith('.json'))
  .sort()

const lerExemplo = (caminho: string): unknown =>
  JSON.parse(readFileSync(path.join(EXEMPLOS, caminho), 'utf-8'))

describe('contrato com o pipeline (site/esquemas × site/exemplos)', () => {
  it.each(exemplos)('%s segue o esquema', (caminho) => {
    expect(validar(tipoDoCaminho(caminho), lerExemplo(caminho))).toEqual([])
  })

  it('todo tipo de arquivo tem exemplo', () => {
    expect(new Set(exemplos.map(tipoDoCaminho))).toEqual(new Set(TIPOS))
  })

  it('o esquema recusa campo a mais', () => {
    const documento = lerExemplo('parlamentar/camara-900001.json') as ArquivoParlamentar
    Object.assign(documento.cota, { inventado: 1 })
    expect(validar('parlamentar', documento)).not.toEqual([])
  })

  it('o esquema recusa outra versão', () => {
    const documento = { ...(lerExemplo('resumo.json') as Resumo), esquema: 2 }
    expect(validar('resumo', documento)).not.toEqual([])
  })
})

// Verificação em tempo de compilação (tsc --noEmit): cada exemplo cabe no tipo de src/tipos.ts.
// Os imports de JSON têm tipos amplos (`esquema: number`, `casa: string`), então o tipo é ampliado
// do mesmo jeito antes da comparação. Um campo do tipo que falte no exemplo (ou com outro nome)
// quebra o tsc.
type Ampliar<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends null
        ? null
        : T extends readonly (infer U)[]
          ? Ampliar<U>[]
          : T extends object
            ? { [K in keyof T]: Ampliar<T[K]> }
            : T

const exemplosCabemNosTipos: [
  Ampliar<Resumo>,
  Ampliar<BuscaParlamentares>,
  Ampliar<BuscaEmpresas>,
  Ampliar<BuscaEmpresas>,
  Ampliar<ArquivoParlamentar>,
  Ampliar<ArquivoParlamentar>,
  Ampliar<BlocoEmpresas>,
  Ampliar<PaginaAlertas>,
] = [resumoJson, parlamentaresJson, pEmpJson, pConJson, camaraJson, senadoJson, blocoJson, alertasJson]
void exemplosCabemNosTipos
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm run typecheck`
Expected: FAIL (`Cannot find module './tipos'`).

- [ ] **Step 3: Implemente**

`site/src/tipos.ts`:

```ts
/**
 * Tipos dos arquivos do site, espelho de site/esquemas/*.schema.json (esquema 1).
 * Datas: "AAAA-MM-DD"; instantes: "AAAA-MM-DDTHH:MM:SSZ"; valores em reais.
 */

export type Casa = 'camara' | 'senado'
export type Correspondencia = 'forte' | 'fraca'

export interface Alerta {
  alerta_id: string
  /** nome do mart sem o prefixo `alerta_` (ex.: `cota_fornecedor_sancionado`) */
  tipo: string
  data: string | null
  valor: number | null
  /** `camara:204554` ou `senado:5672` */
  parlamentar_id: string | null
  parlamentar_nome: string | null
  cnpj_raiz: string | null
  empresa_nome: string | null
  /** a segunda empresa, só em `licitacao_socios_em_comum` */
  cnpj_raiz_2: string | null
  empresa_nome_2: string | null
  descricao: string
  correspondencia: Correspondencia
  regra: string
}

/** alertas de um parlamentar ou empresa: os 200 mais recentes e o total */
export interface Alertas {
  total: number
  itens: Alerta[]
}

export interface ParlamentarResumo {
  id: string
  nome: string | null
  casa: Casa
  uf: string | null
  partido: string | null
  foto: string | null
  legislaturas: number[]
}

export interface AlertaTipo {
  tipo: string
  titulo: string
  explicacao: string
  cautela: string
  ordem: number
  quantidade: number
}

export interface Fonte {
  recurso_id: string
  cadencia: string | null
  ultimo_sucesso: string | null
  status: string | null
  atraso_horas: number | null
  situacao: 'ok' | 'aviso' | 'erro'
}

export interface FonteReduzida {
  recurso_id: string
  competencia: string | null
  coletada_em: string | null
  linhas_antes: number | null
  linhas_depois: number | null
  variacao_pct: number | null
}

/** resumo.json */
export interface Resumo {
  esquema: 1
  gerado_em: string
  dados_ate: {
    cota: string | null
    emendas: string | null
    contratos: string | null
    /** competência "AAAA-MM" */
    receita: string | null
  }
  totais: {
    cota: number
    emendas_pago: number
    contratos: number
    parlamentares: number
    empresas: number
  }
  alerta_tipos: AlertaTipo[]
  alertas_recentes: Alerta[]
  fontes: Fonte[]
  fontes_reduzidas: FonteReduzida[]
}

/** busca/parlamentares.json */
export interface BuscaParlamentares {
  esquema: 1
  parlamentares: ParlamentarResumo[]
}

export interface EmpresaNaBusca {
  raiz: string
  nome: string | null
  uf: string | null
  situacao: string | null
}

/** busca/empresas/p_<prefixo>.json */
export interface BuscaEmpresas {
  esquema: 1
  prefixo: string
  subdividido: boolean
  empresas: EmpresaNaBusca[]
}

export interface Parlamentar extends ParlamentarResumo {
  url_oficial: string
}

/** parlamentar/<casa>-<id>.json */
export interface ArquivoParlamentar {
  esquema: 1
  parlamentar: Parlamentar
  cota: {
    total: number
    por_ano: { ano: number; valor: number }[]
    por_categoria: { categoria: string | null; valor: number }[]
    fornecedores: {
      nome: string | null
      /** CNPJ completo ou CPF mascarado (`***.456.789-**`) */
      documento: string | null
      cnpj_raiz: string | null
      valor: number
      despesas: number
    }[]
  }
  emendas: {
    total_pago: number
    por_ano: { ano: number; pago: number }[]
    favorecidos: {
      nome: string | null
      documento: string | null
      cnpj_raiz: string | null
      pago: number
    }[]
  }
  alertas: Alertas
}

export interface Cadastro {
  razao_social: string | null
  natureza_juridica: string | null
  porte: string | null
  capital_social: number | null
  abertura: string | null
  situacao: string | null
  data_situacao: string | null
  motivo_situacao: string | null
  atividade: string | null
  municipio: string | null
  uf: string | null
  optante_simples: boolean | null
  optante_mei: boolean | null
  estabelecimentos: number | null
  /** só a contagem: os sócios nunca vão para o site */
  socios: number | null
  matriz_cnpj: string | null
  url_portal: string | null
  /** competência "AAAA-MM" da base da Receita */
  competencia_receita: string | null
}

export interface Sancao {
  sancao_id: string
  cadastro: string | null
  categoria: string | null
  orgao: string | null
  inicio: string | null
  fim: string | null
  vigente: boolean
}

export interface Empresa {
  cadastro: Cadastro
  cota: {
    total: number
    parlamentares: { parlamentar_id: string; nome: string | null; valor: number }[]
  }
  emendas: {
    total_pago: number
    autores: { autor: string | null; parlamentar_id: string | null; pago: number }[]
  }
  contratos: {
    total: number
    quantidade: number
    orgaos: { orgao: string | null; valor: number; contratos: number }[]
  }
  licitacoes: { vencidas: number }
  sancoes: Sancao[]
  alertas: Alertas
}

/** empresa/b_<bloco>.json: empresas cuja raiz começa pelo bloco, por raiz */
export interface BlocoEmpresas {
  esquema: 1
  bloco: string
  empresas: Record<string, Empresa>
}

/** alertas/<tipo>/<pagina>.json */
export interface PaginaAlertas {
  esquema: 1
  tipo: string
  pagina: number
  paginas: number
  total: number
  alertas: Alerta[]
}
```

- [ ] **Step 4: Veja passar**

Run: `cd site && npm run typecheck && npm test -- src/contrato.test.ts`
Expected: tsc sem erro; PASS (10 exemplos válidos e os 3 testes de recusa e cobertura).

- [ ] **Step 5: Prova de mutação**

(a) Em `src/tipos.ts`, renomeie `quantidade` de `AlertaTipo` para `quantidades`. Run:
`npm run typecheck`. Expected: FAIL (o `resumo.json` não cabe no tipo). Desfaça.
(b) Em `site/exemplos/busca/empresas/p_emp.json`, troque `"esquema": 1` por `"esquema": 2`. Run:
`npm test -- src/contrato.test.ts`. Expected: FAIL em `p_emp.json segue o esquema`. Desfaça
(`git checkout -- site/exemplos`) e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/tipos.ts site/src/contrato.test.ts
git commit -m "feat(site): tipos dos arquivos e teste do contrato (ajv e tsc)"
```

---

### Task 3: Formatação pt-BR

**Files:**
- Create: `site/src/formato.ts`, `site/src/formato.test.ts`

**Interfaces:**
- Produces: `TRACO`, `formatarReais`, `formatarReaisCurto`, `formatarInteiro`, `contar`,
  `formatarPercentual`, `formatarData`, `formatarInstante`, `formatarCompetencia`,
  `formatarCnpj`, `formatarSimNao`, `LIMITE_DESATUALIZADO_DIAS`, `dadosDesatualizados`.

O `Intl` usa espaço não separável (U+00A0) em `R$ 1.200,00`; os testes trocam por espaço comum.
O Testing Library e o `toHaveTextContent` já tratam U+00A0 como espaço.

- [ ] **Step 1: Escreva o teste**

`site/src/formato.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  TRACO,
  contar,
  dadosDesatualizados,
  formatarCnpj,
  formatarCompetencia,
  formatarData,
  formatarInstante,
  formatarInteiro,
  formatarPercentual,
  formatarReais,
  formatarReaisCurto,
  formatarSimNao,
} from './formato'

const comum = (texto: string) => texto.replace(/[\u00a0\u202f]/g, ' ')

describe('números', () => {
  it('reais', () => {
    expect(comum(formatarReais(1200))).toBe('R$ 1.200,00')
    expect(comum(formatarReais(1234567.891))).toBe('R$ 1.234.567,89')
    expect(comum(formatarReais(0))).toBe('R$ 0,00')
    expect(formatarReais(null)).toBe(TRACO)
  })

  it('reais em forma curta', () => {
    expect(comum(formatarReaisCurto(950))).toBe('R$ 950')
    expect(comum(formatarReaisCurto(1500))).toBe('R$ 1,5 mil')
    expect(comum(formatarReaisCurto(350000))).toBe('R$ 350 mil')
    expect(comum(formatarReaisCurto(1234567))).toBe('R$ 1,2 mi')
    expect(comum(formatarReaisCurto(2500000000))).toBe('R$ 2,5 bi')
  })

  it('inteiros e contagens', () => {
    expect(formatarInteiro(1234567)).toBe('1.234.567')
    expect(formatarInteiro(null)).toBe(TRACO)
    expect(contar(1, 'alerta', 'alertas')).toBe('1 alerta')
    expect(contar(0, 'alerta', 'alertas')).toBe('0 alertas')
    expect(contar(1234, 'alerta', 'alertas')).toBe('1.234 alertas')
  })

  it('percentual a partir de pontos percentuais, com sinal', () => {
    expect(comum(formatarPercentual(-15))).toBe('-15,0%')
    expect(comum(formatarPercentual(12.5))).toBe('+12,5%')
    expect(formatarPercentual(null)).toBe(TRACO)
  })
})

describe('datas', () => {
  it('data do fato, sem fuso (não pode virar o dia anterior)', () => {
    expect(formatarData('2026-08-14')).toBe('14/08/2026')
    expect(formatarData('2026-01-01')).toBe('01/01/2026')
    expect(formatarData(null)).toBe(TRACO)
    expect(formatarData('14/08/2026')).toBe(TRACO)
  })

  it('instante no horário de Brasília', () => {
    expect(formatarInstante('2026-10-07T11:02:13Z')).toBe('07/10/2026 às 08:02')
    expect(formatarInstante('2026-10-07T02:30:00Z')).toBe('06/10/2026 às 23:30')
    expect(formatarInstante(null)).toBe(TRACO)
    expect(formatarInstante('ontem')).toBe(TRACO)
  })

  it('competência da Receita', () => {
    expect(formatarCompetencia('2026-09')).toBe('setembro de 2026')
    expect(formatarCompetencia(null)).toBe(TRACO)
  })

  it('dados desatualizados: mais de 3 dias desde gerado_em', () => {
    const gerado = '2026-10-07T11:02:13Z'
    expect(dadosDesatualizados(gerado, new Date('2026-10-08T11:02:13Z'))).toBe(false)
    expect(dadosDesatualizados(gerado, new Date('2026-10-10T11:02:13Z'))).toBe(false)
    expect(dadosDesatualizados(gerado, new Date('2026-10-10T11:02:14Z'))).toBe(true)
    expect(dadosDesatualizados('inválido', new Date('2026-10-08T00:00:00Z'))).toBe(true)
  })
})

describe('documentos e textos', () => {
  it('CNPJ completo e raiz, inclusive alfanumérico', () => {
    expect(formatarCnpj('11222333000181')).toBe('11.222.333/0001-81')
    expect(formatarCnpj('11222333')).toBe('11.222.333')
    expect(formatarCnpj('1AB2C3D4E5F607')).toBe('1A.B2C.3D4/E5F6-07')
    expect(formatarCnpj('***.456.789-**')).toBe('***.456.789-**')
    expect(formatarCnpj(null)).toBe(TRACO)
  })

  it('sim ou não', () => {
    expect(formatarSimNao(true)).toBe('Sim')
    expect(formatarSimNao(false)).toBe('Não')
    expect(formatarSimNao(null)).toBe(TRACO)
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/formato.test.ts`
Expected: FAIL (`Failed to resolve import "./formato"`).

- [ ] **Step 3: Implemente**

`site/src/formato.ts`:

```ts
/** Formatação de números, datas e documentos em pt-BR (Intl). */

const LOCAL = 'pt-BR'
const FUSO = 'America/Sao_Paulo'

/** o que aparece no lugar de um valor que não existe */
export const TRACO = '—'

const reais = new Intl.NumberFormat(LOCAL, { style: 'currency', currency: 'BRL' })
const reaisCurto = new Intl.NumberFormat(LOCAL, {
  style: 'currency',
  currency: 'BRL',
  notation: 'compact',
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
})
const inteiro = new Intl.NumberFormat(LOCAL)
const percentual = new Intl.NumberFormat(LOCAL, {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})
const dia = new Intl.DateTimeFormat(LOCAL, {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: FUSO,
})
const hora = new Intl.DateTimeFormat(LOCAL, {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: FUSO,
})
const mesAno = new Intl.DateTimeFormat(LOCAL, { month: 'long', year: 'numeric', timeZone: 'UTC' })

export function formatarReais(valor: number | null | undefined): string {
  return valor == null ? TRACO : reais.format(valor)
}

/** "R$ 1,2 mi": para números grandes em destaque e eixos de gráfico */
export function formatarReaisCurto(valor: number | null | undefined): string {
  return valor == null ? TRACO : reaisCurto.format(valor)
}

export function formatarInteiro(valor: number | null | undefined): string {
  return valor == null ? TRACO : inteiro.format(valor)
}

/** "1 alerta", "2 alertas", "1.234 alertas" */
export function contar(quantidade: number, singular: string, plural: string): string {
  return `${inteiro.format(quantidade)} ${quantidade === 1 ? singular : plural}`
}

/** recebe pontos percentuais (-15.0) e devolve "-15,0%" */
export function formatarPercentual(pontos: number | null | undefined): string {
  return pontos == null ? TRACO : percentual.format(pontos / 100)
}

/** "2026-08-14" → "14/08/2026" (sem passar por Date: data sem hora não tem fuso) */
export function formatarData(iso: string | null | undefined): string {
  const partes = iso ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso) : null
  if (!partes) return TRACO
  const [, ano, mes, diaDoMes] = partes
  return `${diaDoMes}/${mes}/${ano}`
}

/** "2026-10-07T11:02:13Z" → "07/10/2026 às 08:02" (horário de Brasília) */
export function formatarInstante(iso: string | null | undefined): string {
  if (!iso) return TRACO
  const instante = new Date(iso)
  if (Number.isNaN(instante.getTime())) return TRACO
  return `${dia.format(instante)} às ${hora.format(instante)}`
}

/** "2026-09" → "setembro de 2026" */
export function formatarCompetencia(competencia: string | null | undefined): string {
  const partes = competencia ? /^(\d{4})-(\d{2})$/.exec(competencia) : null
  if (!partes) return TRACO
  return mesAno.format(new Date(Date.UTC(Number(partes[1]), Number(partes[2]) - 1, 1)))
}

/** CNPJ de 14 ou raiz de 8 caracteres (dígitos ou letras); qualquer outro texto volta igual */
export function formatarCnpj(documento: string | null | undefined): string {
  if (!documento) return TRACO
  const d = documento
  if (/^[0-9A-Z]{14}$/.test(d)) {
    return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`
  }
  if (/^[0-9A-Z]{8}$/.test(d)) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}`
  return d
}

export function formatarSimNao(valor: boolean | null | undefined): string {
  if (valor == null) return TRACO
  return valor ? 'Sim' : 'Não'
}

export const LIMITE_DESATUALIZADO_DIAS = 3

/** true quando os dados têm mais de 3 dias (ou a data não se lê) */
export function dadosDesatualizados(geradoEm: string, agora: Date = new Date()): boolean {
  const gerado = new Date(geradoEm).getTime()
  if (Number.isNaN(gerado)) return true
  return agora.getTime() - gerado > LIMITE_DESATUALIZADO_DIAS * 24 * 60 * 60 * 1000
}
```

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test -- src/formato.test.ts && npm run lint && npm run typecheck`
Expected: PASS (10 testes); lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Em `formatarInstante`, tire o `timeZone: FUSO` dos dois formatadores (`dia` e `hora`). Run:
`TZ=UTC npm test -- src/formato.test.ts` (PowerShell: `$env:TZ = "UTC"; npm test -- ...`).
Expected: FAIL em `instante no horário de Brasília`. Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/formato.ts site/src/formato.test.ts
git commit -m "feat(site): formatação pt-BR de valores, datas e CNPJ"
```

---
### Task 4: Caminhos e camada de dados

**Files:**
- Create: `site/src/caminhos.ts`, `site/src/dados.ts`, `site/src/teste/exemplos.ts`
- Create: `site/src/caminhos.test.ts`, `site/src/dados.test.ts`
- Modify: `site/src/teste/setup.ts`

**Interfaces:**
- Produces (`caminhos.ts`): `PADRAO_DADOS_URL`, `RE_RAIZ`, `slugDoParlamentar(id)`,
  `idDoSlug(slug) -> string | null`, `rotaParlamentar(id)`, `rotaEmpresa(raiz)`,
  `rotaAlertas(tipo?, pagina?)`, `arquivoParlamentar(slug)`, `arquivoEmpresa(raiz)`,
  `arquivoBuscaEmpresas(prefixo)`, `arquivoAlertas(tipo, pagina)`, `urlDaFoto(foto) -> string | null`.
- Produces (`dados.ts`): `ESQUEMA_SUPORTADO`, `MotivoErro`, `ErroDados`,
  `resolverUrlDosDados(env)`, `baixar<T>(caminho)`, `limparCache()`, `carregarResumo()`,
  `carregarParlamentares()`, `carregarBuscaEmpresas(prefixo)`, `carregarParlamentar(slug)`,
  `carregarEmpresa(raiz) -> Empresa`, `carregarAlertas(tipo, pagina)`.
- Produces (testes): `servir(alteracoes?)`, `REDE`, `exemplo<T>(caminho)`, `caminhosPedidos()`
  em `src/teste/exemplos.ts`; o setup limpa o cache e chama `servir()` antes de cada teste.

Erros: `rede` (falha de conexão, HTTP diferente de 200 e 404, JSON ilegível), `esquema`
(`esquema !== 1`) e `nao_encontrado` (HTTP 404, raiz fora do bloco, endereço inválido). Falhas
não ficam no cache, para que "Tentar de novo" baixe de novo.

- [ ] **Step 1: Escreva o dublê do `fetch` e atualize o setup**

`site/src/teste/exemplos.ts`:

```ts
/** Dublê do fetch para os testes: responde /exemplos/<caminho> com site/exemplos/<caminho>. */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { vi } from 'vitest'

const EXEMPLOS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../exemplos')
const PREFIXO = '/exemplos/'

/** alteração que simula falha de conexão */
export const REDE = Symbol('rede')

/** um exemplo de site/exemplos/, lido de novo a cada chamada (pode ser alterado no teste) */
export function exemplo<T>(caminho: string): T {
  return JSON.parse(readFileSync(path.join(EXEMPLOS, caminho), 'utf-8')) as T
}

/**
 * Troca o fetch global. Cada alteração vale para um caminho relativo a site/:
 * REDE (falha de conexão), um número (status HTTP sem corpo), uma Response (devolvida como está)
 * ou um objeto (servido como JSON). O resto vem de site/exemplos/; o que não existe é 404.
 */
export function servir(alteracoes: Record<string, unknown> = {}): void {
  const dublê = vi.fn(async (entrada: RequestInfo | URL): Promise<Response> => {
    const url = entrada instanceof Request ? entrada.url : String(entrada)
    if (!url.startsWith(PREFIXO)) return new Response(null, { status: 404 })
    const caminho = url.slice(PREFIXO.length)
    if (Object.hasOwn(alteracoes, caminho)) {
      const alteracao = alteracoes[caminho]
      if (alteracao === REDE) throw new TypeError('Failed to fetch')
      if (typeof alteracao === 'number') return new Response(null, { status: alteracao })
      if (alteracao instanceof Response) return alteracao.clone()
      return Response.json(alteracao)
    }
    try {
      return new Response(readFileSync(path.join(EXEMPLOS, caminho), 'utf-8'), {
        headers: { 'Content-Type': 'application/json' },
      })
    } catch {
      return new Response(null, { status: 404 })
    }
  })
  vi.stubGlobal('fetch', dublê)
}

/** caminhos (relativos a site/) pedidos ao fetch desde o último servir() */
export function caminhosPedidos(): string[] {
  return vi
    .mocked(fetch)
    .mock.calls.map(([entrada]) => String(entrada))
    .map((url) => url.replace(PREFIXO, ''))
}
```

Se o ESLint recusar o identificador `dublê` (não ASCII), use `duble`.

`site/src/teste/setup.ts` (substitua o conteúdo):

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { limparCache } from '../dados'
import { servir } from './exemplos'

beforeEach(() => {
  limparCache()
  servir()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
```

- [ ] **Step 2: Escreva os testes**

`site/src/caminhos.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  arquivoAlertas,
  arquivoBuscaEmpresas,
  arquivoEmpresa,
  arquivoParlamentar,
  idDoSlug,
  rotaAlertas,
  rotaEmpresa,
  rotaParlamentar,
  slugDoParlamentar,
  urlDaFoto,
} from './caminhos'

describe('caminhos', () => {
  it('id do parlamentar vira slug e volta', () => {
    expect(slugDoParlamentar('camara:204554')).toBe('camara-204554')
    expect(slugDoParlamentar('senado:5672')).toBe('senado-5672')
    expect(idDoSlug('camara-204554')).toBe('camara:204554')
    expect(idDoSlug('deputado-1')).toBeNull()
    expect(idDoSlug('camara-1/../x')).toBeNull()
    expect(() => slugDoParlamentar('204554')).toThrow()
  })

  it('rotas', () => {
    expect(rotaParlamentar('camara:900001')).toBe('/parlamentar/camara-900001')
    expect(rotaEmpresa('11222333')).toBe('/empresa/11222333')
    expect(rotaAlertas()).toBe('/alertas')
    expect(rotaAlertas('cota_fornecedor_sancionado')).toBe(
      '/alertas?tipo=cota_fornecedor_sancionado',
    )
    expect(rotaAlertas('cota_fornecedor_sancionado', 2)).toBe(
      '/alertas?tipo=cota_fornecedor_sancionado&pagina=2',
    )
  })

  it('arquivos, com os prefixos p_ e b_', () => {
    expect(arquivoParlamentar('camara-900001')).toBe('parlamentar/camara-900001.json')
    expect(arquivoEmpresa('11222333')).toBe('empresa/b_112.json')
    expect(arquivoEmpresa('1AB2C3D4')).toBe('empresa/b_1AB.json')
    expect(arquivoBuscaEmpresas('con')).toBe('busca/empresas/p_con.json')
    expect(arquivoAlertas('cota_fornecedor_sancionado', 3)).toBe(
      'alertas/cota_fornecedor_sancionado/3.json',
    )
  })

  it('foto: só das casas, sempre em https', () => {
    expect(urlDaFoto('https://www.camara.leg.br/internet/deputado/bandep/204554.jpg')).toBe(
      'https://www.camara.leg.br/internet/deputado/bandep/204554.jpg',
    )
    expect(urlDaFoto('http://www.senado.leg.br/senadores/img/fotos-oficiais/senador5672.jpg')).toBe(
      'https://www.senado.leg.br/senadores/img/fotos-oficiais/senador5672.jpg',
    )
    expect(urlDaFoto('https://exemplo.com/foto.jpg')).toBeNull()
    expect(urlDaFoto('https://camara.leg.br.exemplo.com/foto.jpg')).toBeNull()
    expect(urlDaFoto('javascript:alert(1)')).toBeNull()
    expect(urlDaFoto(null)).toBeNull()
  })
})
```

`site/src/dados.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  ErroDados,
  carregarAlertas,
  carregarBuscaEmpresas,
  carregarEmpresa,
  carregarParlamentar,
  carregarResumo,
  resolverUrlDosDados,
} from './dados'
import { PADRAO_DADOS_URL } from './caminhos'
import { REDE, caminhosPedidos, exemplo, servir } from './teste/exemplos'
import type { BlocoEmpresas } from './tipos'

async function motivo(promessa: Promise<unknown>): Promise<string> {
  try {
    await promessa
  } catch (erro) {
    if (erro instanceof ErroDados) return erro.motivo
    throw erro
  }
  throw new Error('a promessa deveria ter falhado')
}

describe('endereço dos dados', () => {
  it('produção usa o R2; desenvolvimento usa /exemplos; a variável vence os dois', () => {
    expect(resolverUrlDosDados({ DEV: false })).toBe(PADRAO_DADOS_URL)
    expect(resolverUrlDosDados({ DEV: true })).toBe('/exemplos')
    expect(resolverUrlDosDados({ DEV: false, VITE_DADOS_URL: 'https://x.exemplo/site/' })).toBe(
      'https://x.exemplo/site',
    )
    expect(resolverUrlDosDados({ DEV: false, VITE_DADOS_URL: '' })).toBe(PADRAO_DADOS_URL)
  })
})

describe('baixar', () => {
  it('lê o resumo dos exemplos', async () => {
    const resumo = await carregarResumo()
    expect(resumo.gerado_em).toBe('2026-10-07T11:02:13Z')
    expect(caminhosPedidos()).toEqual(['resumo.json'])
  })

  it('guarda na memória o que já baixou', async () => {
    await carregarResumo()
    await carregarResumo()
    expect(caminhosPedidos()).toEqual(['resumo.json'])
  })

  it('falha de rede não fica no cache', async () => {
    servir({ 'resumo.json': REDE })
    expect(await motivo(carregarResumo())).toBe('rede')
    servir()
    expect((await carregarResumo()).esquema).toBe(1)
  })

  it('HTTP 500 é falha de rede; 404 é não encontrado', async () => {
    servir({ 'resumo.json': 500 })
    expect(await motivo(carregarResumo())).toBe('rede')
    expect(await motivo(carregarParlamentar('camara-1'))).toBe('nao_encontrado')
  })

  it('JSON ilegível é falha de rede', async () => {
    servir({ 'resumo.json': new Response('{"esquema": 1, ') })
    expect(await motivo(carregarResumo())).toBe('rede')
  })

  it('esquema diferente de 1 é recusado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    expect(await motivo(carregarResumo())).toBe('esquema')
  })
})

describe('arquivos de cada tipo', () => {
  it('parlamentar pelo slug', async () => {
    const arquivo = await carregarParlamentar('camara-900001')
    expect(arquivo.parlamentar.nome).toBe('ANA EXEMPLO')
    expect(caminhosPedidos()).toEqual(['parlamentar/camara-900001.json'])
  })

  it('slug inválido não baixa nada', async () => {
    expect(await motivo(carregarParlamentar('deputado-900001'))).toBe('nao_encontrado')
    expect(await motivo(carregarParlamentar('camara-1%2F..%2Fresumo'))).toBe('nao_encontrado')
    expect(caminhosPedidos()).toEqual([])
  })

  it('empresa: baixa o bloco e devolve a raiz pedida', async () => {
    const empresa = await carregarEmpresa('11222333')
    expect(empresa.cadastro.razao_social).toBe('EMPRESA EXEMPLO LTDA')
    expect(caminhosPedidos()).toEqual(['empresa/b_112.json'])
  })

  it('empresa fora do bloco ou bloco que não existe: não encontrada', async () => {
    expect(await motivo(carregarEmpresa('11222399'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('99999999'))).toBe('nao_encontrado')
  })

  it('raiz inválida não baixa nada', async () => {
    expect(await motivo(carregarEmpresa('112223'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('1122233a'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('__proto__'))).toBe('nao_encontrado')
    expect(caminhosPedidos()).toEqual([])
  })

  it('CNPJ alfanumérico usa o bloco das 3 primeiras posições', async () => {
    const bloco = exemplo<BlocoEmpresas>('empresa/b_112.json')
    const empresa = bloco.empresas['11222333']
    servir({ 'empresa/b_1AB.json': { esquema: 1, bloco: '1AB', empresas: { '1AB2C3D4': empresa } } })
    expect((await carregarEmpresa('1AB2C3D4')).cadastro.uf).toBe('DF')
    expect(caminhosPedidos()).toEqual(['empresa/b_1AB.json'])
  })

  it('bloco de busca e página de alertas', async () => {
    expect((await carregarBuscaEmpresas('emp')).empresas).toHaveLength(2)
    expect((await carregarAlertas('cota_fornecedor_sancionado', 1)).total).toBe(1)
    expect(await motivo(carregarBuscaEmpresas('../x'))).toBe('nao_encontrado')
    expect(await motivo(carregarAlertas('../resumo', 1))).toBe('nao_encontrado')
    expect(await motivo(carregarAlertas('cota_fornecedor_sancionado', 0))).toBe('nao_encontrado')
  })
})
```

- [ ] **Step 3: Veja falhar**

Run: `cd site && npm test -- src/caminhos.test.ts src/dados.test.ts`
Expected: FAIL (módulos `./caminhos` e `./dados` não existem; o setup também quebra, porque
importa `../dados`).

- [ ] **Step 4: Implemente**

`site/src/caminhos.ts`:

```ts
/** Rotas do site e nomes dos arquivos de dados (spec do site, seção 4.2). */

export const PADRAO_DADOS_URL = 'https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/site'

/** raiz do CNPJ: 8 posições, dígitos ou letras maiúsculas (CNPJ alfanumérico desde 07/2026) */
export const RE_RAIZ = /^[0-9A-Z]{8}$/
const RE_ID = /^(camara|senado):([0-9A-Za-z]+)$/
const RE_SLUG = /^(camara|senado)-([0-9A-Za-z]+)$/

/** "camara:204554" → "camara-204554" */
export function slugDoParlamentar(id: string): string {
  const partes = RE_ID.exec(id)
  if (!partes) throw new Error(`id de parlamentar inválido: ${id}`)
  return `${partes[1]}-${partes[2]}`
}

/** "camara-204554" → "camara:204554"; null se o slug não tem esse formato */
export function idDoSlug(slug: string): string | null {
  const partes = RE_SLUG.exec(slug)
  return partes ? `${partes[1]}:${partes[2]}` : null
}

export function rotaParlamentar(id: string): string {
  return `/parlamentar/${slugDoParlamentar(id)}`
}

export function rotaEmpresa(raiz: string): string {
  return `/empresa/${raiz}`
}

export function rotaAlertas(tipo?: string, pagina = 1): string {
  const parametros = new URLSearchParams()
  if (tipo) parametros.set('tipo', tipo)
  if (pagina > 1) parametros.set('pagina', String(pagina))
  const consulta = parametros.toString()
  return consulta ? `/alertas?${consulta}` : '/alertas'
}

export function arquivoParlamentar(slug: string): string {
  return `parlamentar/${slug}.json`
}

export function arquivoEmpresa(raiz: string): string {
  return `empresa/b_${raiz.slice(0, 3)}.json`
}

export function arquivoBuscaEmpresas(prefixo: string): string {
  return `busca/empresas/p_${prefixo}.json`
}

export function arquivoAlertas(tipo: string, pagina: number): string {
  return `alertas/${tipo}/${pagina}.json`
}

/**
 * Foto oficial, só de *.camara.leg.br ou *.senado.leg.br (a CSP de public/_headers só libera
 * esses), sempre em https (o Senado publica as fotos com http://).
 */
export function urlDaFoto(foto: string | null): string | null {
  if (!foto) return null
  let url: URL
  try {
    url = new URL(foto)
  } catch {
    return null
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return null
  if (!/(^|\.)(camara|senado)\.leg\.br$/.test(url.hostname)) return null
  url.protocol = 'https:'
  return url.href
}
```

`site/src/dados.ts`:

```ts
/**
 * Camada de dados: baixa os arquivos JSON do site (R2, pasta site/), confere a versão do
 * esquema e guarda na memória o que já baixou na sessão. O R2 entrega os arquivos em gzip com
 * Content-Encoding: o navegador descomprime sozinho.
 */
import {
  PADRAO_DADOS_URL,
  RE_RAIZ,
  arquivoAlertas,
  arquivoBuscaEmpresas,
  arquivoEmpresa,
  arquivoParlamentar,
  idDoSlug,
} from './caminhos'
import type {
  ArquivoParlamentar,
  BlocoEmpresas,
  BuscaEmpresas,
  BuscaParlamentares,
  Empresa,
  PaginaAlertas,
  Resumo,
} from './tipos'

export const ESQUEMA_SUPORTADO = 1

/** rede: tentar de novo resolve; esquema: o site precisa ser atualizado; nao_encontrado: 404 */
export type MotivoErro = 'rede' | 'esquema' | 'nao_encontrado'

export class ErroDados extends Error {
  readonly motivo: MotivoErro

  constructor(motivo: MotivoErro, mensagem: string) {
    super(mensagem)
    this.name = 'ErroDados'
    this.motivo = motivo
  }
}

export function resolverUrlDosDados(env: { VITE_DADOS_URL?: string; DEV: boolean }): string {
  const configurada = env.VITE_DADOS_URL
  const url = configurada ? configurada : env.DEV ? '/exemplos' : PADRAO_DADOS_URL
  return url.replace(/\/+$/, '')
}

const cache = new Map<string, Promise<unknown>>()

export function limparCache(): void {
  cache.clear()
}

async function baixarSemCache(caminho: string): Promise<unknown> {
  const url = `${resolverUrlDosDados(import.meta.env)}/${caminho}`
  let resposta: Response
  try {
    resposta = await fetch(url)
  } catch {
    throw new ErroDados('rede', `falha de rede ao baixar ${caminho}`)
  }
  if (resposta.status === 404) throw new ErroDados('nao_encontrado', `${caminho} não existe`)
  if (!resposta.ok) throw new ErroDados('rede', `HTTP ${resposta.status} ao baixar ${caminho}`)
  let corpo: unknown
  try {
    corpo = await resposta.json()
  } catch {
    throw new ErroDados('rede', `${caminho} não é um JSON legível`)
  }
  const esquema =
    typeof corpo === 'object' && corpo !== null ? (corpo as { esquema?: unknown }).esquema : null
  if (esquema !== ESQUEMA_SUPORTADO) {
    throw new ErroDados('esquema', `${caminho} tem esquema ${String(esquema)}`)
  }
  return corpo
}

/** Baixa um arquivo (caminho relativo a site/). Falhas não ficam no cache. */
export function baixar<T>(caminho: string): Promise<T> {
  const guardada = cache.get(caminho)
  if (guardada) return guardada as Promise<T>
  const promessa = baixarSemCache(caminho)
  cache.set(caminho, promessa)
  promessa.catch(() => {
    if (cache.get(caminho) === promessa) cache.delete(caminho)
  })
  return promessa as Promise<T>
}

function naoEncontrado(oQue: string): Promise<never> {
  return Promise.reject(new ErroDados('nao_encontrado', `endereço inválido: ${oQue}`))
}

export function carregarResumo(): Promise<Resumo> {
  return baixar<Resumo>('resumo.json')
}

export function carregarParlamentares(): Promise<BuscaParlamentares> {
  return baixar<BuscaParlamentares>('busca/parlamentares.json')
}

export function carregarBuscaEmpresas(prefixo: string): Promise<BuscaEmpresas> {
  if (!/^[a-z0-9]{3,4}$/.test(prefixo)) return naoEncontrado(prefixo)
  return baixar<BuscaEmpresas>(arquivoBuscaEmpresas(prefixo))
}

export function carregarParlamentar(slug: string): Promise<ArquivoParlamentar> {
  if (!idDoSlug(slug)) return naoEncontrado(slug)
  return baixar<ArquivoParlamentar>(arquivoParlamentar(slug))
}

export async function carregarEmpresa(raiz: string): Promise<Empresa> {
  if (!RE_RAIZ.test(raiz)) return naoEncontrado(raiz)
  const bloco = await baixar<BlocoEmpresas>(arquivoEmpresa(raiz))
  const empresa = Object.hasOwn(bloco.empresas, raiz) ? bloco.empresas[raiz] : undefined
  if (!empresa) throw new ErroDados('nao_encontrado', `empresa ${raiz} não está nos dados`)
  return empresa
}

export function carregarAlertas(tipo: string, pagina: number): Promise<PaginaAlertas> {
  if (!/^[a-z_]+$/.test(tipo) || !Number.isInteger(pagina) || pagina < 1) {
    return naoEncontrado(`${tipo}/${pagina}`)
  }
  return baixar<PaginaAlertas>(arquivoAlertas(tipo, pagina))
}
```

- [ ] **Step 5: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS (inclusive os das tarefas anteriores); lint e tsc sem erro.

- [ ] **Step 6: Prova de mutação**

Em `baixar`, apague o bloco `promessa.catch(() => { ... })`. Run:
`npm test -- -t "falha de rede não fica no cache"`. Expected: FAIL (a segunda chamada devolve a
mesma falha). Desfaça e confirme o PASS.

- [ ] **Step 7: Commit**

```bash
git add site/src/caminhos.ts site/src/dados.ts site/src/teste site/src/caminhos.test.ts \
  site/src/dados.test.ts
git commit -m "feat(site): camada de dados com esquema, cache em memória e erros"
```

---

### Task 5: Busca

**Files:**
- Create: `site/src/busca.ts`, `site/src/busca.test.ts`

**Interfaces:**
- Consumes: `carregarParlamentares`, `carregarBuscaEmpresas`, `ErroDados` (tarefa 4).
- Produces: `PALAVRAS_IGNORADAS`, `MINIMO_LETRAS`, `MAXIMO_RESULTADOS`, `normalizar(texto)`,
  `raizDaConsulta(consulta) -> string | null`, `Consulta`, `ConsultaTexto`,
  `analisarConsulta(consulta) -> Consulta`, `consultaBuscavel(consulta) -> boolean`,
  `filtrarParlamentares`, `filtrarEmpresas`, `ResultadoBusca`, `buscarTexto(consulta)`.

Regras (spec, seção 4.2, e `dbt/models/site/site_arquivos_busca.sql`, que precisam continuar
iguais):
- Normalização: sem acento, minúsculas, palavras separadas por qualquer caractere fora de
  `[a-z0-9]`.
- Parlamentares: todas as palavras digitadas precisam ser começo de alguma palavra do nome. A
  busca só roda quando há uma palavra com 3 caracteres ou mais.
- Empresas: as palavras ignoradas saem; a "chave" é a primeira palavra restante com 3 ou mais
  caracteres. Sem chave, não há busca de empresa (e a tela explica). O bloco é o das 3
  primeiras letras da chave; se ele vier `subdividido`, com chave de 3 letras ficam as empresas
  do próprio bloco e o pedido de mais uma letra, e com 4 ou mais o site baixa o bloco das 4
  primeiras letras. Bloco que não existe (404) é resultado vazio, não erro. O filtro usa todas
  as palavras não ignoradas.
- CNPJ: só `[0-9A-Za-z]` e `.`, `/`, `-`, sem espaço no meio; sem a pontuação, 8 caracteres
  (raiz) ou 12 + 2 dígitos (CNPJ completo); a raiz precisa ter ao menos um dígito (senão
  `construt` seria lido como CNPJ). Letras viram maiúsculas.
- Até 50 resultados de cada grupo, com o total para a tela avisar do corte.

- [ ] **Step 1: Escreva o teste**

`site/src/busca.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  MAXIMO_RESULTADOS,
  type ConsultaTexto,
  analisarConsulta,
  buscarTexto,
  consultaBuscavel,
  normalizar,
  raizDaConsulta,
} from './busca'
import { ErroDados } from './dados'
import { REDE, caminhosPedidos, servir } from './teste/exemplos'

function texto(consulta: string): ConsultaTexto {
  const analise = analisarConsulta(consulta)
  if (analise.tipo !== 'texto') throw new Error(`não é texto: ${consulta}`)
  return analise
}

const nomes = (lista: { nome: string | null }[]) => lista.map((x) => x.nome)

describe('normalizar', () => {
  it('tira acentos, põe em minúsculas e separa palavras como o dbt', () => {
    expect(normalizar('Construção São-Paulo LTDA.')).toEqual(['construcao', 'sao', 'paulo', 'ltda'])
    expect(normalizar('S/A & Cia')).toEqual(['s', 'a', 'cia'])
    expect(normalizar('  ')).toEqual([])
  })
})

describe('raizDaConsulta', () => {
  it.each([
    ['11.222.333/0001-81', '11222333'],
    ['11222333000181', '11222333'],
    ['11.222.333', '11222333'],
    ['11222333', '11222333'],
    ['1ab2c3d4', '1AB2C3D4'],
    ['1A.B2C.3D4/E5F6-07', '1AB2C3D4'],
    ['  11222333  ', '11222333'],
  ])('%s vai direto à empresa %s', (consulta, raiz) => {
    expect(raizDaConsulta(consulta)).toBe(raiz)
  })

  it.each([
    'construt',
    'loja 1234',
    '123456789',
    '12345678909',
    '11222333000',
    '1AB2C3D4E5F6GH',
    'abc',
  ])('%s não é CNPJ', (consulta) => {
    expect(raizDaConsulta(consulta)).toBeNull()
  })
})

describe('analisarConsulta', () => {
  it('vazia, CNPJ ou texto', () => {
    expect(analisarConsulta('   ').tipo).toBe('vazia')
    expect(analisarConsulta('11.222.333/0001-81')).toEqual({ tipo: 'cnpj', raiz: '11222333' })
    expect(texto('de exemplo')).toEqual({
      tipo: 'texto',
      palavras: ['de', 'exemplo'],
      palavrasEmpresa: ['exemplo'],
      chave: 'exemplo',
    })
  })

  it('palavras ignoradas e curtas não viram chave', () => {
    expect(texto('ltda').chave).toBeNull()
    expect(texto('S/A comercio').chave).toBeNull()
    expect(texto('da ex').chave).toBeNull()
    expect(texto('ex construtora').chave).toBe('construtora')
  })

  it('só busca com uma palavra de 3 caracteres ou mais', () => {
    expect(consultaBuscavel(texto('ex'))).toBe(false)
    expect(consultaBuscavel(texto('ana'))).toBe(true)
  })
})

describe('buscarTexto (sobre site/exemplos)', () => {
  it('acha parlamentar e empresa pela mesma palavra, com ou sem acento', async () => {
    const resultado = await buscarTexto(texto('Exêmplo'))
    expect(nomes(resultado.parlamentares)).toEqual(['ANA EXEMPLO'])
    expect(nomes(resultado.empresas)).toEqual(['EMPRESA EXEMPLO LTDA'])
    expect(caminhosPedidos()).toContain('busca/empresas/p_exe.json')
  })

  it('usa o bloco da primeira palavra e filtra por todas', async () => {
    const resultado = await buscarTexto(texto('empresa exemplo'))
    expect(nomes(resultado.empresas)).toEqual(['EMPRESA EXEMPLO LTDA'])
    expect(caminhosPedidos()).toContain('busca/empresas/p_emp.json')
    expect(caminhosPedidos()).not.toContain('busca/empresas/p_exe.json')
  })

  it('bloco subdividido com 3 letras: as de palavra de 3 letras e o pedido de mais uma', async () => {
    const resultado = await buscarTexto(texto('con'))
    expect(nomes(resultado.empresas)).toEqual(['CON ENGENHARIA SA'])
    expect(resultado.pedeMaisLetras).toBe(true)
    expect(caminhosPedidos()).not.toContain('busca/empresas/p_cons.json')
  })

  it('bloco subdividido com 4 letras ou mais: usa o bloco de 4', async () => {
    for (const consulta of ['cons', 'construtora']) {
      const resultado = await buscarTexto(texto(consulta))
      expect(nomes(resultado.empresas)).toEqual(['CONSTRUTORA EXEMPLO LTDA'])
      expect(resultado.pedeMaisLetras).toBe(false)
    }
    expect(caminhosPedidos()).toContain('busca/empresas/p_cons.json')
  })

  it('bloco que não existe é resultado vazio', async () => {
    const resultado = await buscarTexto(texto('xyz'))
    expect(resultado.empresas).toEqual([])
    expect(resultado.parlamentares).toEqual([])
  })

  it('só palavras ignoradas: não baixa bloco de empresa', async () => {
    const resultado = await buscarTexto(texto('ltda'))
    expect(resultado.semChaveDeEmpresa).toBe(true)
    expect(caminhosPedidos().some((c) => c.startsWith('busca/empresas/'))).toBe(false)
  })

  it('corta em 50 e informa o total', async () => {
    const empresas = Array.from({ length: 60 }, (_, i) => ({
      raiz: String(10000000 + i),
      nome: `EXEMPLO ${i}`,
      uf: 'DF',
      situacao: 'ATIVA',
    }))
    servir({
      'busca/empresas/p_exe.json': { esquema: 1, prefixo: 'exe', subdividido: false, empresas },
    })
    const resultado = await buscarTexto(texto('exemplo'))
    expect(resultado.empresas).toHaveLength(MAXIMO_RESULTADOS)
    expect(resultado.totalEmpresas).toBe(60)
  })

  it('falha de rede vira ErroDados', async () => {
    servir({ 'busca/parlamentares.json': REDE })
    await expect(buscarTexto(texto('ana'))).rejects.toBeInstanceOf(ErroDados)
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/busca.test.ts`
Expected: FAIL (`./busca` não existe).

- [ ] **Step 3: Implemente**

`site/src/busca.ts`:

```ts
/**
 * Busca de parlamentar, empresa ou CNPJ (spec do site, seção 4.2). As regras de palavra
 * precisam ser as mesmas de dbt/models/site/site_arquivos_busca.sql, que monta os blocos.
 */
import { ErroDados, carregarBuscaEmpresas, carregarParlamentares } from './dados'
import type { BuscaEmpresas, EmpresaNaBusca, ParlamentarResumo } from './tipos'

export const PALAVRAS_IGNORADAS: ReadonlySet<string> = new Set([
  'ltda', 'me', 'epp', 'eireli', 'sa', 's/a', 'cia', 'de', 'da', 'do', 'das', 'dos', 'e',
  'comercio', 'servicos', 'industria',
])
export const MINIMO_LETRAS = 3
export const MAXIMO_RESULTADOS = 50

/** como o dbt: lower(strip_accents(texto)) dividido em [^a-z0-9]+ */
export function normalizar(texto: string): string[] {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((palavra) => palavra.length > 0)
}

/** raiz do CNPJ quando a consulta é um CNPJ (8 ou 14 caracteres, com ou sem pontuação) */
export function raizDaConsulta(consulta: string): string | null {
  const limpa = consulta.trim()
  if (!/^[0-9A-Za-z./-]+$/.test(limpa)) return null
  const documento = limpa.replace(/[./-]/g, '').toUpperCase()
  const raiz = documento.slice(0, 8)
  if (!/[0-9]/.test(raiz)) return null
  if (/^[0-9A-Z]{8}$/.test(documento)) return documento
  if (/^[0-9A-Z]{12}[0-9]{2}$/.test(documento)) return raiz
  return null
}

export interface ConsultaTexto {
  tipo: 'texto'
  /** todas as palavras (filtro de parlamentares) */
  palavras: string[]
  /** sem as palavras ignoradas (filtro de empresas) */
  palavrasEmpresa: string[]
  /** primeira palavra de empresa com 3+ caracteres: escolhe o bloco; null = sem busca de empresa */
  chave: string | null
}

export type Consulta = { tipo: 'vazia' } | { tipo: 'cnpj'; raiz: string } | ConsultaTexto

export function analisarConsulta(consulta: string): Consulta {
  const raiz = raizDaConsulta(consulta)
  if (raiz) return { tipo: 'cnpj', raiz }
  const palavras = normalizar(consulta)
  if (palavras.length === 0) return { tipo: 'vazia' }
  const palavrasEmpresa = palavras.filter((p) => !PALAVRAS_IGNORADAS.has(p))
  const chave = palavrasEmpresa.find((p) => p.length >= MINIMO_LETRAS) ?? null
  return { tipo: 'texto', palavras, palavrasEmpresa, chave }
}

export function consultaBuscavel(consulta: ConsultaTexto): boolean {
  return consulta.palavras.some((p) => p.length >= MINIMO_LETRAS)
}

function casa(nome: string | null, palavras: string[]): boolean {
  const doNome = normalizar(nome ?? '')
  return palavras.every((p) => doNome.some((n) => n.startsWith(p)))
}

export function filtrarParlamentares(
  lista: ParlamentarResumo[],
  palavras: string[],
): ParlamentarResumo[] {
  return lista.filter((p) => casa(p.nome, palavras))
}

export function filtrarEmpresas(lista: EmpresaNaBusca[], palavras: string[]): EmpresaNaBusca[] {
  return lista.filter((e) => casa(e.nome, palavras))
}

export interface ResultadoBusca {
  parlamentares: ParlamentarResumo[]
  totalParlamentares: number
  empresas: EmpresaNaBusca[]
  totalEmpresas: number
  /** bloco subdividido e a chave tem só 3 letras */
  pedeMaisLetras: boolean
  /** nenhuma palavra serve para buscar empresa (todas ignoradas ou curtas) */
  semChaveDeEmpresa: boolean
}

async function blocoDeBusca(prefixo: string): Promise<BuscaEmpresas | null> {
  try {
    return await carregarBuscaEmpresas(prefixo)
  } catch (erro) {
    if (erro instanceof ErroDados && erro.motivo === 'nao_encontrado') return null
    throw erro
  }
}

async function empresasDaChave(
  chave: string,
): Promise<{ empresas: EmpresaNaBusca[]; pedeMaisLetras: boolean }> {
  const bloco = await blocoDeBusca(chave.slice(0, 3))
  if (!bloco) return { empresas: [], pedeMaisLetras: false }
  if (!bloco.subdividido) return { empresas: bloco.empresas, pedeMaisLetras: false }
  if (chave.length === 3) return { empresas: bloco.empresas, pedeMaisLetras: true }
  const menor = await blocoDeBusca(chave.slice(0, 4))
  return { empresas: menor?.empresas ?? [], pedeMaisLetras: false }
}

/** Busca por texto; pressupõe consultaBuscavel(consulta). Falhas chegam como ErroDados. */
export async function buscarTexto(consulta: ConsultaTexto): Promise<ResultadoBusca> {
  const [arquivo, doBloco] = await Promise.all([
    carregarParlamentares(),
    consulta.chave
      ? empresasDaChave(consulta.chave)
      : Promise.resolve({ empresas: [], pedeMaisLetras: false }),
  ])
  const parlamentares = filtrarParlamentares(arquivo.parlamentares, consulta.palavras)
  const empresas = filtrarEmpresas(doBloco.empresas, consulta.palavrasEmpresa)
  return {
    parlamentares: parlamentares.slice(0, MAXIMO_RESULTADOS),
    totalParlamentares: parlamentares.length,
    empresas: empresas.slice(0, MAXIMO_RESULTADOS),
    totalEmpresas: empresas.length,
    pedeMaisLetras: doBloco.pedeMaisLetras,
    semChaveDeEmpresa: consulta.chave === null,
  }
}
```

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test -- src/busca.test.ts && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Em `analisarConsulta`, troque `palavras.filter((p) => !PALAVRAS_IGNORADAS.has(p))` por
`palavras`. Run: `npm test -- src/busca.test.ts`. Expected: FAIL em `palavras ignoradas e curtas
não viram chave` e em `só palavras ignoradas: não baixa bloco de empresa`. Desfaça e confirme o
PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/busca.ts site/src/busca.test.ts
git commit -m "feat(site): busca por nome e CNPJ nos blocos do índice"
```

---

### Task 6: Tema, contraste, privacidade e CSP

**Files:**
- Create: `site/src/index.css`, `site/public/_headers`, `site/src/teste/arquivos.ts`
- Create: `site/src/tema.test.ts`, `site/src/privacidade.test.ts`
- Modify: `site/src/main.tsx` (fontes e CSS)

**Interfaces:**
- Produces: utilitários do Tailwind a partir dos tokens (`bg-void-canvas`, `bg-graphite`,
  `text-bone`, `text-ash`, `text-slate`, `text-alerta`, `border-hairline`, `from-capa-inicio`,
  `to-capa-fim`, `font-geist`, `text-caption` … `text-display`, `text-display-celular`,
  `rounded-ui`, `rounded-cartao`, `rounded-painel`, `rounded-nav`) e o utilitário `selo-alerta`;
  `SITE` e `arquivosDoCodigo()` em `src/teste/arquivos.ts`.

Decisões (adaptações do DESIGN.md, que prevalecem):
- `--color-*: initial` remove a paleta padrão do Tailwind: só existem as cores do DESIGN.md,
  `--color-alerta` (âmbar) e as duas pontas do gradiente da capa. Sem vermelho por construção
  (`text-red-500` nem é gerado; conferido no protótipo).
- A capa usa um gradiente âmbar → cobalto escurecido (`#6b4423` → `#1e3a8a`), para o texto branco
  passar de 4,5:1 nas duas pontas (o âmbar puro dá ~2:1 com branco).
- Espaçamento: a escala do DESIGN.md (4 a 56px, múltiplos de 2 e 4) é a do Tailwind (`1` = 4px).
  Não declaramos `--spacing-4: 4px` etc., porque isso trocaria o sentido de `p-4` (16px no
  Tailwind) e misturaria as duas escalas.

- [ ] **Step 1: Escreva os testes**

`site/src/teste/arquivos.ts`:

```ts
import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** a pasta site/ */
export const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** código que vai para o navegador: index.html e src/ (sem testes nem src/teste/) */
export function arquivosDoCodigo(): string[] {
  const src = path.join(SITE, 'src')
  const doSrc = readdirSync(src, { recursive: true, encoding: 'utf-8' })
    .map((relativo) => relativo.replaceAll('\\', '/'))
    .filter((relativo) => /\.(ts|tsx|css)$/.test(relativo))
    .filter((relativo) => !relativo.includes('.test.') && !relativo.startsWith('teste/'))
    .map((relativo) => path.join(src, relativo))
  return [path.join(SITE, 'index.html'), ...doSrc]
}
```

`site/src/tema.test.ts`:

```ts
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { SITE, arquivosDoCodigo } from './teste/arquivos'

const css = readFileSync(path.join(SITE, 'src', 'index.css'), 'utf-8')

function cores(): Map<string, string> {
  const mapa = new Map<string, string>()
  for (const [, nome, valor] of css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    if (nome && valor) mapa.set(nome, valor.toLowerCase())
  }
  return mapa
}

function cor(nome: string): string {
  const valor = cores().get(nome)
  if (!valor) throw new Error(`a cor ${nome} não está no tema`)
  return valor
}

function canais(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number]
}

function luminancia(hex: string): number {
  const [r, g, b] = canais(hex).map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  ) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a: string, b: string): number {
  const [clara, escura] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number]
  return (clara + 0.05) / (escura + 0.05)
}

function matizESaturacao(hex: string): { matiz: number; saturacao: number } {
  const [r, g, b] = canais(hex)
  const maior = Math.max(r, g, b)
  const menor = Math.min(r, g, b)
  const delta = maior - menor
  const luz = (maior + menor) / 2
  const saturacao = delta === 0 ? 0 : delta / (1 - Math.abs(2 * luz - 1))
  let matiz = 0
  if (delta !== 0) {
    if (maior === r) matiz = 60 * (((g - b) / delta) % 6)
    else if (maior === g) matiz = 60 * ((b - r) / delta + 2)
    else matiz = 60 * ((r - g) / delta + 4)
  }
  return { matiz: (matiz + 360) % 360, saturacao }
}

describe('tema (site/DESIGN.md)', () => {
  it('a paleta padrão do Tailwind sai inteira', () => {
    expect(css).toMatch(/--color-\*:\s*initial;/)
  })

  it('tem os tokens do DESIGN.md e o âmbar de alerta', () => {
    expect(cor('void-canvas')).toBe('#0a0a0a')
    expect(cor('graphite')).toBe('#161616')
    expect(cor('bone')).toBe('#ededed')
    expect(cor('ash')).toBe('#c2c2c2')
    expect(cor('slate')).toBe('#686868')
    expect(cor('alerta')).toBe('#f2a65a')
  })

  it('nenhuma cor do tema é vermelha', () => {
    for (const [nome, valor] of cores()) {
      const { matiz, saturacao } = matizESaturacao(valor)
      const vermelha = saturacao > 0.3 && (matiz < 15 || matiz >= 345)
      expect(vermelha, `${nome}: ${valor}`).toBe(false)
    }
  })

  it.each([
    ['bone', 'void-canvas'],
    ['bone', 'graphite'],
    ['ash', 'void-canvas'],
    ['ash', 'graphite'],
    ['alerta', 'void-canvas'],
    ['alerta', 'graphite'],
    ['graphite', 'snow-white'],
    ['snow-white', 'capa-inicio'],
    ['snow-white', 'capa-fim'],
    ['bone', 'capa-inicio'],
    ['bone', 'capa-fim'],
  ])('texto %s sobre %s tem contraste AA (4,5:1)', (texto, fundo) => {
    expect(contraste(cor(texto), cor(fundo))).toBeGreaterThanOrEqual(4.5)
  })

  it('slate só serve para texto grande (3:1)', () => {
    expect(contraste(cor('slate'), cor('void-canvas'))).toBeGreaterThanOrEqual(3)
    expect(contraste(cor('slate'), cor('void-canvas'))).toBeLessThan(4.5)
  })

  it('nenhuma classe ou cor vermelha no código', () => {
    for (const arquivo of arquivosDoCodigo()) {
      const conteudo = readFileSync(arquivo, 'utf-8')
      expect(conteudo, arquivo).not.toMatch(
        /\b(?:text|bg|border|fill|stroke|outline|ring|decoration|from|via|to)-(?:red|rose|pink)-\d/,
      )
      expect(conteudo, arquivo).not.toMatch(/#(?:f00|ff0000)\b|:\s*red\b|['"]red['"]/i)
    }
  })
})
```

`site/src/privacidade.test.ts`:

```ts
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { PADRAO_DADOS_URL } from './caminhos'
import { SITE, arquivosDoCodigo } from './teste/arquivos'

const ler = (relativo: string) => readFileSync(path.join(SITE, relativo), 'utf-8')

const PROIBIDOS: [string, RegExp][] = [
  ['cookies', /document\.cookie/],
  ['armazenamento no navegador', /\b(?:localStorage|sessionStorage|indexedDB)\b/],
  ['fontes externas', /fonts\.(?:googleapis|gstatic)\.com|use\.typekit\.net|fonts\.bunny\.net/],
  [
    'analytics',
    /google-analytics|googletagmanager|gtag\(|plausible\.io|matomo|hotjar|segment\.(?:io|com)|clarity\.ms/,
  ],
]

describe('privacidade (spec, seção 7)', () => {
  it.each(PROIBIDOS)('sem %s', (_nome, padrao) => {
    for (const arquivo of arquivosDoCodigo()) {
      expect(readFileSync(arquivo, 'utf-8'), arquivo).not.toMatch(padrao)
    }
  })

  it('as fontes vêm empacotadas do @fontsource', () => {
    const main = ler('src/main.tsx')
    expect(main).toMatch(/@fontsource\/dm-sans/)
    expect(main).toMatch(/@fontsource\/geist/)
  })

  it('a CSP libera a origem dos dados e, fora isso, só as fotos oficiais', () => {
    const csp = /Content-Security-Policy: (.+)/.exec(ler('public/_headers'))?.[1] ?? ''
    const diretivas = new Map(
      csp
        .split(';')
        .map((d) => d.trim().split(/\s+/))
        .map(([nome, ...valores]): [string, string[]] => [nome ?? '', valores]),
    )
    expect(diretivas.get('default-src')).toEqual(["'self'"])
    expect(diretivas.get('script-src')).toEqual(["'self'"])
    expect(diretivas.get('font-src')).toEqual(["'self'"])
    expect(diretivas.get('connect-src')).toEqual(["'self'", new URL(PADRAO_DADOS_URL).origin])
    expect(diretivas.get('img-src')).toEqual([
      "'self'",
      'data:',
      'https://*.camara.leg.br',
      'https://*.senado.leg.br',
    ])
    expect(csp).not.toMatch(/unsafe-eval/)
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/tema.test.ts src/privacidade.test.ts`
Expected: FAIL (`index.css` e `_headers` não existem; `main.tsx` sem `@fontsource`).

- [ ] **Step 3: Implemente**

`site/src/index.css`:

```css
@import 'tailwindcss';

/*
 * Tokens de site/DESIGN.md, com as adaptações do topo daquele arquivo. A paleta padrão do
 * Tailwind sai inteira: só existem as cores abaixo, e nenhuma é vermelha (alerta é indício, não
 * acusação). O espaçamento é a escala padrão do Tailwind (1 = 4px), igual à do DESIGN.md.
 */
@theme {
  --color-*: initial;
  --color-void-canvas: #0a0a0a;
  --color-graphite: #161616;
  --color-frosted-glass: #d4d4d4;
  --color-ink-black: #000000;
  --color-snow-white: #ffffff;
  --color-bone: #ededed;
  --color-ash: #c2c2c2;
  --color-slate: #686868;
  --color-smoke: #b2b2b2;
  --color-hairline: #e5e5e5;
  --color-dusk-violet: #6b62f2;
  /* única cor de sinalização: selos e marcações pequenas, nunca fundo grande nem texto corrido */
  --color-alerta: #f2a65a;
  /* gradiente da capa (âmbar → cobalto), escurecido para o texto branco passar de 4,5:1 */
  --color-capa-inicio: #6b4423;
  --color-capa-fim: #1e3a8a;

  --font-sans: 'DM Sans', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-geist: 'Geist', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;

  --text-caption: 13px;
  --text-caption--line-height: 1.5;
  --text-caption--letter-spacing: 0.33px;
  --text-body: 16px;
  --text-body--line-height: 1.5;
  --text-subheading: 18px;
  --text-subheading--line-height: 1.5;
  --text-heading-sm: 24px;
  --text-heading-sm--line-height: 1.33;
  --text-heading: 36px;
  --text-heading--line-height: 1.11;
  --text-heading-lg: 48px;
  --text-heading-lg--line-height: 1;
  --text-display-celular: 40px;
  --text-display-celular--line-height: 1.05;
  --text-display-celular--letter-spacing: -0.035em;
  --text-display: 72px;
  --text-display--line-height: 1;
  --text-display--letter-spacing: -2.52px;

  --radius-icone: 4px;
  --radius-ui: 10px;
  --radius-nav: 19px;
  --radius-cartao: 24px;
  --radius-cartao-grande: 40px;
  --radius-painel: 42px;

  --shadow-sutil: rgba(255, 255, 255, 0.1) 0px 0px 0px 1px inset;
}

@layer base {
  html {
    background-color: var(--color-void-canvas);
    color: var(--color-bone);
    font-family: var(--font-sans);
    color-scheme: dark;
  }

  a {
    text-decoration-line: underline;
    text-underline-offset: 3px;
  }

  :focus-visible {
    outline: 2px solid var(--color-snow-white);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      transition: none !important;
      animation: none !important;
    }
  }
}

/* selo de alerta: a única marcação em âmbar */
@utility selo-alerta {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--color-alerta);
  border-radius: 9999px;
  color: var(--color-alerta);
  padding: 2px 10px;
  font-size: var(--text-caption);
  line-height: 1.5;
  letter-spacing: 0.33px;
}
```

`site/public/_headers` (Cloudflare Pages; o `style-src 'unsafe-inline'` é para os estilos que o
Observable Plot insere no SVG):

```text
/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.camara.leg.br https://*.senado.leg.br; font-src 'self'; connect-src 'self' https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
  Referrer-Policy: strict-origin-when-cross-origin
  X-Content-Type-Options: nosniff
  Permissions-Policy: camera=(), microphone=(), geolocation=(), browsing-topics=()
```

Em `site/src/main.tsx`, antes dos outros imports:

```tsx
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/geist/400.css'
import '@fontsource/geist/500.css'
import '@fontsource/geist/600.css'
import './index.css'
```

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck && npx vite build`
Expected: PASS; no `dist/assets/`, os `.woff2` das fontes e um `.css` sem `text-red`
(`grep -c "text-red" dist/assets/*.css` dá 0); `dist/_headers` presente.

- [ ] **Step 5: Prova de mutação**

Em `site/src/index.css`, acrescente `--color-perigo: #dc2626;` no `@theme`. Run:
`npm test -- src/tema.test.ts`. Expected: FAIL em `nenhuma cor do tema é vermelha`. Desfaça.
Depois, em `site/public/_headers`, apague a origem do R2 do `connect-src`. Run:
`npm test -- src/privacidade.test.ts`. Expected: FAIL na CSP. Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/index.css site/public/_headers site/src/teste/arquivos.ts site/src/main.tsx \
  site/src/tema.test.ts site/src/privacidade.test.ts
git commit -m "feat(site): tema do DESIGN.md sem vermelho, contraste AA, CSP e fontes locais"
```

---

### Task 7: Carregamento e caixa de busca

**Files:**
- Create: `site/src/useDados.ts`, `site/src/componentes/CaixaBusca.tsx`,
  `site/src/teste/rotas.tsx`, `site/src/componentes/CaixaBusca.test.tsx`

**Interfaces:**
- Consumes: `busca.ts` (tarefa 5), `caminhos.ts`, `formato.ts`, `ErroDados`.
- Produces: `useDados<T>(chave, carregar) -> EstadoDados<T> & { tentarDeNovo }`, com
  `EstadoDados<T> = { estado: 'carregando' } | { estado: 'ok'; dados: T } |
  { estado: 'erro'; erro: ErroDados }`; `CaixaBusca({ grande? })`;
  `renderizarComRotas(ui, rota?) -> { usuario, local(), ...render }`.

Comportamento da caixa de busca:
- Um `<form role="search">` com rótulo visível "Buscar parlamentar, empresa ou CNPJ", campo
  `type="search"` e botão "Buscar".
- Os resultados aparecem enquanto se digita, numa região `aria-live="polite"`:
  - CNPJ: link "Ver a empresa de CNPJ 11.222.333"; Enter (ou o botão) vai direto a
    `/empresa/<raiz>`.
  - Menos de 3 letras: "Digite pelo menos 3 letras."
  - Carregando: "Buscando…" (`role="status"`).
  - Listas `Parlamentares encontrados` (link com nome e "partido · UF · Câmara/Senado") e
    `Empresas encontradas` (link com razão social e "UF · situação").
  - Corte em 50: "Mostrando 50 de N …. Digite mais palavras para refinar."
  - Bloco subdividido com 3 letras: "Há muitas empresas com palavras começando por “con”.
    Digite mais uma letra para ver todas."
  - Sem chave de empresa: "Palavras comuns (como LTDA, COMERCIO e SERVICOS) e palavras com
    menos de 3 letras não entram na busca de empresas."
  - Nada achado: "Nenhum resultado para “xyz”."
  - Falha de rede: "Busca indisponível no momento." e botão "Tentar de novo"; esquema
    diferente: "Os dados mudaram de formato e este site precisa ser atualizado."

`useDados` não chama `setState` de forma síncrona dentro do efeito (regra
`react-hooks/set-state-in-effect` do plugin 7): o estado "carregando" é derivado de o resultado
guardado ser de outra chave ou de outra tentativa.

- [ ] **Step 1: Escreva a ajuda de rotas e o teste**

`site/src/teste/rotas.tsx`:

```tsx
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router'

function LocalAtual() {
  const local = useLocation()
  return (
    <span hidden data-testid="local">
      {local.pathname + local.search}
    </span>
  )
}

/** renderiza `ui` num roteador de memória em `rota`; `local()` diz onde a navegação parou */
export function renderizarComRotas(ui: ReactNode, rota = '/') {
  const usuario = userEvent.setup()
  const resultado = render(
    <MemoryRouter initialEntries={[rota]}>
      {ui}
      <LocalAtual />
    </MemoryRouter>,
  )
  return { usuario, ...resultado, local: () => resultado.getByTestId('local').textContent }
}
```

`site/src/componentes/CaixaBusca.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REDE, servir } from '../teste/exemplos'
import { renderizarComRotas } from '../teste/rotas'
import { CaixaBusca } from './CaixaBusca'

function preparar() {
  const tela = renderizarComRotas(<CaixaBusca />)
  const caixa = screen.getByRole('searchbox', { name: 'Buscar parlamentar, empresa ou CNPJ' })
  return { ...tela, caixa }
}

describe('caixa de busca', () => {
  it('acha parlamentar pelo nome', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ana')
    const lista = await screen.findByRole('list', { name: 'Parlamentares encontrados' })
    expect(within(lista).getByRole('link', { name: /ANA EXEMPLO/ })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
  })

  it('acha parlamentar e empresa pela mesma palavra, com acento', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'exêmplo')
    const empresas = await screen.findByRole('list', { name: 'Empresas encontradas' })
    expect(within(empresas).getByRole('link', { name: /EMPRESA EXEMPLO LTDA/ })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    const parlamentares = screen.getByRole('list', { name: 'Parlamentares encontrados' })
    expect(within(parlamentares).getByRole('link', { name: /ANA EXEMPLO/ })).toBeInTheDocument()
  })

  it('filtra por todas as palavras', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'empresa exemplo')
    const empresas = await screen.findByRole('list', { name: 'Empresas encontradas' })
    expect(within(empresas).getAllByRole('link').map((l) => l.textContent)).toEqual([
      expect.stringContaining('EMPRESA EXEMPLO LTDA'),
    ])
  })

  it('bloco subdividido: com 3 letras pede mais uma; com 4 mostra o bloco menor', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'con')
    expect(await screen.findByRole('link', { name: /CON ENGENHARIA SA/ })).toBeInTheDocument()
    expect(screen.getByText(/digite mais uma letra/i)).toBeInTheDocument()
    await usuario.type(caixa, 's')
    expect(await screen.findByRole('link', { name: /CONSTRUTORA EXEMPLO LTDA/ })).toBeInTheDocument()
    expect(screen.queryByText(/digite mais uma letra/i)).toBeNull()
  })

  it.each([
    ['11.222.333/0001-81', '/empresa/11222333'],
    ['11222333', '/empresa/11222333'],
    ['1ab2c3d4', '/empresa/1AB2C3D4'],
  ])('CNPJ %s com Enter vai direto à empresa', async (cnpj, rota) => {
    const { usuario, caixa, local } = preparar()
    await usuario.type(caixa, `${cnpj}{Enter}`)
    expect(local()).toBe(rota)
  })

  it('CNPJ mostra o link da empresa antes do Enter', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, '11222333')
    expect(screen.getByRole('link', { name: /Ver a empresa de CNPJ 11\.222\.333/ })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
  })

  it('explica as palavras comuns', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ltda')
    expect(await screen.findByText(/palavras comuns/i)).toBeInTheDocument()
  })

  it('avisa quando não acha nada', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'xyz')
    expect(await screen.findByText('Nenhum resultado para “xyz”.')).toBeInTheDocument()
  })

  it('pede 3 letras', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ex')
    expect(screen.getByText('Digite pelo menos 3 letras.')).toBeInTheDocument()
  })

  it('falha de rede: avisa e tenta de novo', async () => {
    servir({ 'busca/parlamentares.json': REDE })
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ana')
    expect(await screen.findByText('Busca indisponível no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('link', { name: /ANA EXEMPLO/ })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/componentes/CaixaBusca.test.tsx`
Expected: FAIL (`./CaixaBusca` não existe).

- [ ] **Step 3: Implemente**

`site/src/useDados.ts`:

```ts
import { useCallback, useEffect, useState } from 'react'
import { ErroDados } from './dados'

export type EstadoDados<T> =
  | { estado: 'carregando' }
  | { estado: 'ok'; dados: T }
  | { estado: 'erro'; erro: ErroDados }

interface Guardado<T> {
  chave: string
  tentativa: number
  valor: EstadoDados<T>
}

function comoErroDados(erro: unknown): ErroDados {
  return erro instanceof ErroDados ? erro : new ErroDados('rede', String(erro))
}

/**
 * Carrega dados para a tela. `chave` identifica o que carregar: quando ela muda, carrega de novo
 * (e respostas atrasadas da chave anterior são descartadas). `tentarDeNovo` repete a carga.
 */
export function useDados<T>(
  chave: string,
  carregar: () => Promise<T>,
): EstadoDados<T> & { tentarDeNovo: () => void } {
  const [tentativa, setTentativa] = useState(0)
  const [guardado, setGuardado] = useState<Guardado<T> | null>(null)

  useEffect(() => {
    let ativo = true
    carregar().then(
      (dados) => {
        if (ativo) setGuardado({ chave, tentativa, valor: { estado: 'ok', dados } })
      },
      (erro: unknown) => {
        if (ativo) {
          setGuardado({ chave, tentativa, valor: { estado: 'erro', erro: comoErroDados(erro) } })
        }
      },
    )
    return () => {
      ativo = false
    }
    // a chave identifica o que carregar; `carregar` muda a cada render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, tentativa])

  const tentarDeNovo = useCallback(() => setTentativa((t) => t + 1), [])
  const atual = guardado?.chave === chave && guardado.tentativa === tentativa
  const valor: EstadoDados<T> = atual ? guardado.valor : { estado: 'carregando' }
  return { ...valor, tentarDeNovo }
}
```

`site/src/componentes/CaixaBusca.tsx`:

```tsx
import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { MAXIMO_RESULTADOS, analisarConsulta, buscarTexto, consultaBuscavel } from '../busca'
import { rotaEmpresa, rotaParlamentar } from '../caminhos'
import { formatarCnpj, formatarInteiro } from '../formato'
import { useDados } from '../useDados'

const CASA = { camara: 'Câmara', senado: 'Senado' } as const

function Mensagem({ children }: { children: ReactNode }) {
  return <p className="text-ash">{children}</p>
}

const juntar = (partes: (string | null)[]) => partes.filter(Boolean).join(' · ')

export function CaixaBusca({ grande = false }: { grande?: boolean }) {
  const id = useId()
  const navegar = useNavigate()
  const [texto, setTexto] = useState('')
  const consulta = analisarConsulta(texto)
  const buscavel = consulta.tipo === 'texto' && consultaBuscavel(consulta)
  const estado = useDados(buscavel ? `busca:${consulta.palavras.join(' ')}` : 'busca:', () =>
    consulta.tipo === 'texto' && consultaBuscavel(consulta)
      ? buscarTexto(consulta)
      : Promise.resolve(null),
  )

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (consulta.tipo === 'cnpj') void navegar(rotaEmpresa(consulta.raiz))
  }

  function resultados(): ReactNode {
    if (consulta.tipo === 'vazia') return null
    if (consulta.tipo === 'cnpj') {
      return (
        <p>
          <Link to={rotaEmpresa(consulta.raiz)}>
            Ver a empresa de CNPJ {formatarCnpj(consulta.raiz)}
          </Link>
        </p>
      )
    }
    if (!buscavel) return <Mensagem>Digite pelo menos 3 letras.</Mensagem>
    if (estado.estado === 'carregando') return <p role="status">Buscando…</p>
    if (estado.estado === 'erro') {
      if (estado.erro.motivo === 'esquema') {
        return (
          <p role="alert">Os dados mudaram de formato e este site precisa ser atualizado.</p>
        )
      }
      return (
        <div role="alert" className="flex items-center gap-3">
          <p>Busca indisponível no momento.</p>
          <button
            type="button"
            onClick={estado.tentarDeNovo}
            className="rounded-full border border-hairline px-3.5 py-1.5"
          >
            Tentar de novo
          </button>
        </div>
      )
    }
    const r = estado.dados
    if (!r) return null
    const nada = r.parlamentares.length === 0 && r.empresas.length === 0
    return (
      <div className="flex flex-col gap-4">
        {r.parlamentares.length > 0 && (
          <div>
            <p className="font-medium">Parlamentares</p>
            <ul aria-label="Parlamentares encontrados" className="mt-2 flex flex-col gap-2">
              {r.parlamentares.map((p) => (
                <li key={p.id}>
                  <Link to={rotaParlamentar(p.id)}>
                    {p.nome ?? p.id}{' '}
                    <span className="text-ash">{juntar([p.partido, p.uf, CASA[p.casa]])}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {r.totalParlamentares > r.parlamentares.length && (
              <Mensagem>
                Mostrando {MAXIMO_RESULTADOS} de {formatarInteiro(r.totalParlamentares)}{' '}
                parlamentares. Digite mais palavras para refinar.
              </Mensagem>
            )}
          </div>
        )}
        {r.empresas.length > 0 && (
          <div>
            <p className="font-medium">Empresas</p>
            <ul aria-label="Empresas encontradas" className="mt-2 flex flex-col gap-2">
              {r.empresas.map((e) => (
                <li key={e.raiz}>
                  <Link to={rotaEmpresa(e.raiz)}>
                    {e.nome ?? formatarCnpj(e.raiz)}{' '}
                    <span className="text-ash">{juntar([e.uf, e.situacao])}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {r.totalEmpresas > r.empresas.length && (
              <Mensagem>
                Mostrando {MAXIMO_RESULTADOS} de {formatarInteiro(r.totalEmpresas)} empresas.
                Digite mais palavras para refinar.
              </Mensagem>
            )}
          </div>
        )}
        {r.pedeMaisLetras && (
          <Mensagem>
            Há muitas empresas com palavras começando por “{consulta.chave}”. Digite mais uma
            letra para ver todas.
          </Mensagem>
        )}
        {r.semChaveDeEmpresa && (
          <Mensagem>
            Palavras comuns (como LTDA, COMERCIO e SERVICOS) e palavras com menos de 3 letras não
            entram na busca de empresas.
          </Mensagem>
        )}
        {nada && !r.pedeMaisLetras && <Mensagem>Nenhum resultado para “{texto.trim()}”.</Mensagem>}
      </div>
    )
  }

  return (
    <div className="w-full">
      <form role="search" aria-label="Busca" onSubmit={enviar} className="flex flex-col gap-2">
        <label htmlFor={id} className="text-caption text-ash">
          Buscar parlamentar, empresa ou CNPJ
        </label>
        <div className="flex gap-2">
          <input
            id={id}
            type="search"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
            placeholder="Ex.: nome do deputado, razão social ou 00.000.000/0001-00"
            autoComplete="off"
            spellCheck={false}
            className={`min-w-0 flex-1 rounded-full border border-hairline/40 bg-graphite px-5 text-bone placeholder:text-ash ${grande ? 'h-14 text-subheading' : 'h-11'}`}
          />
          <button type="submit" className="rounded-full bg-snow-white px-5 text-graphite">
            Buscar
          </button>
        </div>
      </form>
      <div aria-live="polite" className="mt-4">
        {resultados()}
      </div>
    </div>
  )
}
```

(O nome com letra minúscula e o texto do `placeholder` podem mudar; os rótulos, nomes de lista e
mensagens acima são o que os testes leem.)

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test -- src/componentes/CaixaBusca.test.tsx && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro (o único `eslint-disable` é o do `useDados`, comentado).

- [ ] **Step 5: Prova de mutação**

Em `CaixaBusca`, apague a linha `if (consulta.tipo === 'cnpj') void navegar(...)` de `enviar`.
Run: `npm test -- src/componentes/CaixaBusca.test.tsx -t "com Enter"`. Expected: FAIL (o local
continua `/`). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/useDados.ts site/src/componentes site/src/teste/rotas.tsx
git commit -m "feat(site): caixa de busca e carregamento com tentar de novo"
```

---

### Task 8: Layout, rotas, erros e 404

**Files:**
- Create: `site/src/componentes/Layout.tsx`, `site/src/componentes/Navegacao.tsx`,
  `site/src/componentes/FaixaDesatualizada.tsx`, `site/src/componentes/Estados.tsx`,
  `site/src/useTitulo.ts`, `site/src/paginas/NaoEncontrada.tsx`,
  `site/src/paginas/{Inicio,Parlamentar,Empresa,Alertas,Sobre}.tsx` (provisórias)
- Create: `site/src/componentes/Layout.test.tsx`
- Modify: `site/src/Rotas.tsx` (definitivo), `site/src/teste/rotas.tsx` (`renderizarSite`),
  `site/src/teste/setup.ts` (`window.scrollTo`), `site/src/estrutura.test.tsx` (o teste
  `a aplicação renderiza` passa a procurar o link "Pular para o conteúdo")

**Interfaces:**
- Produces: `Rotas`; `Layout`; `Carregando()`; `AvisoErro({ erro, tentarDeNovo })`;
  `AvisoDadosAntigos({ geradoEm, agora? })`; `FaixaDesatualizada()`; `useTitulo(titulo?)`;
  `NaoEncontrada()`; `renderizarSite(rota)` nos testes.

Comportamento:
- Rotas (spec, seção 3): `/` → `Inicio`, `/parlamentar/:slug` → `PaginaParlamentar`,
  `/empresa/:raiz` → `PaginaEmpresa`, `/alertas` → `PaginaAlertas`, `/sobre` → `Sobre`,
  qualquer outra → `NaoEncontrada`; todas dentro do `Layout`.
- `Layout`: link "Pular para o conteúdo" (primeiro item focável, visível ao receber foco,
  leva a `#conteudo`); `Navegacao`; `FaixaDesatualizada`; `<main id="conteudo" tabIndex={-1}>`
  com o `Outlet`; rodapé "Dados públicos oficiais. Sem cookies e sem rastreamento." com link para
  "Sobre". Ao mudar de rota, volta ao topo (`window.scrollTo(0, 0)`). Largura máxima 1200px,
  margem lateral de 16px, espaço embaixo para a navegação flutuante.
- `Navegacao`: `<nav aria-label="Principal">` flutuante (Graphite, borda Hairline translúcida,
  `rounded-nav`, `backdrop-blur`), embaixo da tela no celular, a 16px das bordas, e no topo a
  partir de `sm`; links "Início" (`/`, `end`), "Alertas" e "Sobre" (`NavLink`, com
  `aria-current="page"` na rota atual) e o nome "Eleitorado" levando a `/`.
- `FaixaDesatualizada`: carrega o resumo (`useDados('resumo', carregarResumo)`); em erro ou
  carregando não mostra nada (as páginas cuidam do erro). `AvisoDadosAntigos` mostra, quando
  `dadosDesatualizados(geradoEm, agora)`, uma faixa `role="status"`: "Atenção: os dados não são
  atualizados desde 07/10/2026 às 08:02." (âmbar só num selo pequeno ao lado; o texto em Bone).
- `Carregando`: `<p role="status">Carregando…</p>`.
- `AvisoErro`: `nao_encontrado` → `NaoEncontrada`; `esquema` → `role="alert"` com "Os dados
  mudaram de formato e este site precisa ser atualizado. Tente recarregar a página mais tarde.";
  `rede` → `role="alert"` com "Dados indisponíveis no momento." e o botão "Tentar de novo".
- `NaoEncontrada`: `<h1>Página não encontrada</h1>`, a frase "O endereço não existe, ou o
  parlamentar ou a empresa não está nos dados publicados.", a `CaixaBusca` e o link "Voltar ao
  início"; título da aba "Página não encontrada · Eleitorado".
- `useTitulo(titulo)`: `document.title` = `"<titulo> · Eleitorado"` ou `"Eleitorado"`.
- Páginas provisórias: cada uma só com `<h1>` e o nome da página (as tarefas 11 a 15 trocam).

- [ ] **Step 1: Escreva o teste**

Acrescente em `site/src/teste/rotas.tsx`:

```tsx
import { Rotas } from '../Rotas'

/** o site inteiro, aberto em `rota` */
export function renderizarSite(rota: string) {
  return renderizarComRotas(<Rotas />, rota)
}
```

Em `site/src/teste/setup.ts`, dentro do `beforeEach`, acrescente
`window.scrollTo = vi.fn() as unknown as typeof window.scrollTo` (o jsdom não implementa a
rolagem e reclamaria no console).

`site/src/componentes/Layout.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { carregarResumo } from '../dados'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarComRotas, renderizarSite } from '../teste/rotas'
import { useDados } from '../useDados'
import { AvisoErro, Carregando } from './Estados'
import { AvisoDadosAntigos } from './FaixaDesatualizada'

function TesteResumo() {
  const estado = useDados('resumo', carregarResumo)
  if (estado.estado === 'carregando') return <Carregando />
  if (estado.estado === 'erro') {
    return <AvisoErro erro={estado.erro} tentarDeNovo={estado.tentarDeNovo} />
  }
  return <p>gerado em {estado.dados.gerado_em}</p>
}

describe('layout', () => {
  it('navegação principal com a página atual marcada', () => {
    renderizarSite('/sobre')
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getByRole('link', { name: 'Início' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Alertas' })).toHaveAttribute('href', '/alertas')
    const sobre = within(nav).getByRole('link', { name: 'Sobre' })
    expect(sobre).toHaveAttribute('href', '/sobre')
    expect(sobre).toHaveAttribute('aria-current', 'page')
  })

  it('a primeira tecla Tab vai para "Pular para o conteúdo"', async () => {
    const { usuario } = renderizarSite('/sobre')
    await usuario.tab()
    const pular = screen.getByRole('link', { name: 'Pular para o conteúdo' })
    expect(pular).toHaveFocus()
    expect(pular).toHaveAttribute('href', '#conteudo')
    expect(document.getElementById('conteudo')?.tagName).toBe('MAIN')
  })

  it('rota que não existe: 404 com a busca', () => {
    renderizarSite('/nada/aqui')
    expect(screen.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao início' })).toHaveAttribute('href', '/')
    expect(document.title).toBe('Página não encontrada · Eleitorado')
  })
})

describe('dados antigos', () => {
  const gerado = '2026-10-07T11:02:13Z'

  it('mostra a faixa com mais de 3 dias', () => {
    render(<AvisoDadosAntigos geradoEm={gerado} agora={new Date('2026-10-11T12:00:00Z')} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Atenção: os dados não são atualizados desde 07/10/2026 às 08:02.',
    )
  })

  it('não mostra nada com dados de ontem', () => {
    const { container } = render(
      <AvisoDadosAntigos geradoEm={gerado} agora={new Date('2026-10-08T12:00:00Z')} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('a faixa aparece no site quando o resumo é velho', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-20T12:00:00Z'))
    renderizarSite('/sobre')
    expect(await screen.findByText(/os dados não são atualizados desde 07\/10\/2026/)).toBeInTheDocument()
  })
})

describe('estados de erro', () => {
  it('rede: avisa e tenta de novo', async () => {
    servir({ 'resumo.json': REDE })
    const { usuario } = renderizarComRotas(<TesteResumo />)
    expect(screen.getByRole('status')).toHaveTextContent('Carregando…')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByText('gerado em 2026-10-07T11:02:13Z')).toBeInTheDocument()
  })

  it('esquema diferente: o site precisa ser atualizado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    renderizarComRotas(<TesteResumo />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/precisa ser atualizado/)
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).toBeNull()
  })

  it('não encontrado: a página 404', async () => {
    servir({ 'resumo.json': 404 })
    renderizarComRotas(<TesteResumo />)
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })
})
```

Em `site/src/estrutura.test.tsx`, troque o teste `a aplicação renderiza` por:

```tsx
  it('a aplicação renderiza', () => {
    render(
      <MemoryRouter>
        <Rotas />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Pular para o conteúdo' })).toBeInTheDocument()
  })
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/componentes/Layout.test.tsx`
Expected: FAIL (componentes não existem).

- [ ] **Step 3: Implemente**

Escreva os componentes pelo comportamento acima, com estas peças fixas:

`site/src/useTitulo.ts`:

```ts
import { useEffect } from 'react'

export function useTitulo(titulo?: string | null): void {
  useEffect(() => {
    document.title = titulo ? `${titulo} · Eleitorado` : 'Eleitorado'
  }, [titulo])
}
```

`site/src/Rotas.tsx`:

```tsx
import { Route, Routes } from 'react-router'
import { Layout } from './componentes/Layout'
import { PaginaAlertas } from './paginas/Alertas'
import { PaginaEmpresa } from './paginas/Empresa'
import { Inicio } from './paginas/Inicio'
import { NaoEncontrada } from './paginas/NaoEncontrada'
import { PaginaParlamentar } from './paginas/Parlamentar'
import { Sobre } from './paginas/Sobre'

export function Rotas() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route path="parlamentar/:slug" element={<PaginaParlamentar />} />
        <Route path="empresa/:raiz" element={<PaginaEmpresa />} />
        <Route path="alertas" element={<PaginaAlertas />} />
        <Route path="sobre" element={<Sobre />} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}
```

`site/src/componentes/Estados.tsx`:

```tsx
import type { ErroDados } from '../dados'
import { NaoEncontrada } from '../paginas/NaoEncontrada'

export function Carregando() {
  return (
    <p role="status" className="text-ash">
      Carregando…
    </p>
  )
}

export function AvisoErro({ erro, tentarDeNovo }: { erro: ErroDados; tentarDeNovo: () => void }) {
  if (erro.motivo === 'nao_encontrado') return <NaoEncontrada />
  if (erro.motivo === 'esquema') {
    return (
      <div role="alert" className="rounded-cartao bg-graphite p-7">
        <p>
          Os dados mudaram de formato e este site precisa ser atualizado. Tente recarregar a página
          mais tarde.
        </p>
      </div>
    )
  }
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-cartao bg-graphite p-7">
      <p>Dados indisponíveis no momento.</p>
      <button
        type="button"
        onClick={tentarDeNovo}
        className="rounded-full bg-snow-white px-3 py-2 text-graphite"
      >
        Tentar de novo
      </button>
    </div>
  )
}
```

`site/src/componentes/FaixaDesatualizada.tsx`:

```tsx
import { carregarResumo } from '../dados'
import { dadosDesatualizados, formatarInstante } from '../formato'
import { useDados } from '../useDados'

export function AvisoDadosAntigos({ geradoEm, agora }: { geradoEm: string; agora?: Date }) {
  if (!dadosDesatualizados(geradoEm, agora)) return null
  return (
    <div role="status" className="mx-auto mt-4 flex max-w-[1200px] items-center gap-3 px-4">
      <span className="selo-alerta" aria-hidden="true">
        Dados antigos
      </span>
      <p>Atenção: os dados não são atualizados desde {formatarInstante(geradoEm)}.</p>
    </div>
  )
}

export function FaixaDesatualizada() {
  const resumo = useDados('resumo', carregarResumo)
  if (resumo.estado !== 'ok') return null
  return <AvisoDadosAntigos geradoEm={resumo.dados.gerado_em} />
}
```

`Layout`, `Navegacao`, `NaoEncontrada` e as páginas provisórias ficam a cargo da execução,
seguindo o comportamento acima e o DESIGN.md (`NaoEncontrada` chama `useTitulo('Página não
encontrada')`).

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS (todos os arquivos de teste); lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Em `useDados`, tire `tentativa` da lista de dependências do `useEffect` (fica `[chave]`). Run:
`npm test -- src/componentes/Layout.test.tsx -t "rede: avisa e tenta de novo"`. Expected: FAIL
(o clique em "Tentar de novo" não baixa de novo e a tela fica em "Carregando…"). Desfaça e
confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src
git commit -m "feat(site): layout, navegação, faixa de dados antigos, erros e 404"
```

---

### Task 9: Alertas com cautela

**Files:**
- Create: `site/src/fontes.ts`, `site/src/componentes/Alertas.tsx`
- Create: `site/src/fontes.test.ts`, `site/src/componentes/Alertas.test.tsx`

**Interfaces:**
- Consumes: `tipos.ts`, `caminhos.ts`, `formato.ts`.
- Produces: `FonteOficial`, `fonteDoAlerta(alerta)`; `AVISO_ALERTA`, `AVISO_HOMONIMO`,
  `AVISO_RAIZ`, `avisoDaCorrespondencia(alerta)`, `CartaoAlerta({ alerta, tipo, geradoEm })`,
  `ListaAlertas({ alertas, total, tipos, geradoEm, verTodos? })`.

Cada cartão (`<article>`, com o título do tipo como nome acessível) mostra, nesta ordem: o selo
âmbar "Alerta"; o título do tipo (do `resumo.json`; se o tipo não estiver lá, o próprio `tipo`);
a `descricao`; a data do fato e o valor (quando houver); os links para o parlamentar e para as
empresas (`cnpj_raiz` e `cnpj_raiz_2`); em `fraca`, o aviso de correspondência; "O que é:" com a
`explicacao`; "Cuidado:" com a `cautela`; "Regra:" com a `regra` do mart; o aviso fixo; "Dados
de <gerado_em>" e o link para a fonte oficial (nova aba, `rel="noopener noreferrer"`).

A lista põe os `forte` primeiro (`<ul aria-label="Alertas">`) e os `fraca` depois, numa seção
própria com o título "Correspondência fraca" e a frase "Nestes alertas, a ligação entre a pessoa
e a empresa é menos certa. Leia o aviso de cada um." Se `total` for maior que a quantidade de
itens e `verTodos` não for `false`, avisa "Mostrando os N mais recentes de T alertas." com o link
"Ver todos os alertas" (`/alertas`). Sem itens: "Nenhum alerta automático."

- [ ] **Step 1: Escreva os testes**

`site/src/fontes.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { fonteDoAlerta } from './fontes'
import { exemplo } from './teste/exemplos'
import type { Alerta, Resumo } from './tipos'

const base = exemplo<Resumo>('resumo.json').alertas_recentes[0] as Alerta

describe('fonte oficial de cada alerta', () => {
  it.each(exemplo<Resumo>('resumo.json').alerta_tipos.map((t) => t.tipo))(
    '%s aponta para um site oficial em https',
    (tipo) => {
      const url = new URL(fonteDoAlerta({ ...base, tipo }).url)
      expect(url.protocol).toBe('https:')
      expect(url.hostname).toMatch(/\.(gov|leg)\.br$/)
    },
  )

  it('cota de senador aponta para o Senado; de deputado, para a Câmara', () => {
    const tipo = 'cota_fornecedor_sancionado'
    expect(fonteDoAlerta({ ...base, tipo, parlamentar_id: 'senado:1' }).url).toMatch(/senado\.leg\.br/)
    expect(fonteDoAlerta({ ...base, tipo, parlamentar_id: 'camara:1' }).url).toMatch(/camara\.leg\.br/)
  })

  it('tipo desconhecido cai no Portal da Transparência', () => {
    expect(fonteDoAlerta({ ...base, tipo: 'novo_tipo', cnpj_raiz: null }).url).toBe(
      'https://portaldatransparencia.gov.br',
    )
  })
})
```

`site/src/componentes/Alertas.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { exemplo } from '../teste/exemplos'
import { renderizarComRotas } from '../teste/rotas'
import type { BlocoEmpresas, Resumo } from '../tipos'
import { AVISO_ALERTA, AVISO_HOMONIMO, ListaAlertas } from './Alertas'

const resumo = exemplo<Resumo>('resumo.json')
const empresa = exemplo<BlocoEmpresas>('empresa/b_112.json').empresas['11222333']
if (!empresa) throw new Error('exemplo sem a empresa 11222333')
const { itens } = empresa.alertas

function renderizar(props: Partial<Parameters<typeof ListaAlertas>[0]> = {}) {
  return renderizarComRotas(
    <ListaAlertas
      alertas={itens}
      total={itens.length}
      tipos={resumo.alerta_tipos}
      geradoEm={resumo.gerado_em}
      {...props}
    />,
  )
}

describe('lista de alertas', () => {
  it('todo alerta traz o aviso fixo, a fonte e a data dos dados', () => {
    renderizar()
    const cartoes = screen.getAllByRole('article')
    expect(cartoes).toHaveLength(3)
    for (const cartao of cartoes) {
      expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
      expect(within(cartao).getByRole('link', { name: /Fonte oficial/ })).toHaveAttribute(
        'href',
        expect.stringMatching(/^https:\/\//),
      )
      expect(cartao).toHaveTextContent('Dados de 07/10/2026 às 08:02')
    }
  })

  it('o aviso fixo diz que é indício e não acusação', () => {
    expect(AVISO_ALERTA).toBe(
      'Indício gerado automaticamente a partir de dados públicos; não é acusação nem constatação de irregularidade.',
    )
  })

  it('título, explicação e cautela vêm do resumo, não do código', () => {
    const tipos = resumo.alerta_tipos.map((t) =>
      t.tipo === 'cota_fornecedor_sancionado'
        ? { ...t, titulo: 'TÍTULO DE TESTE', explicacao: 'EXPLICAÇÃO DE TESTE', cautela: 'CAUTELA DE TESTE' }
        : t,
    )
    renderizar({ tipos })
    const cartao = screen.getByRole('article', { name: 'TÍTULO DE TESTE' })
    expect(within(cartao).getByText('EXPLICAÇÃO DE TESTE')).toBeInTheDocument()
    expect(within(cartao).getByText('CAUTELA DE TESTE')).toBeInTheDocument()
    expect(cartao).toHaveTextContent(/Regra: Despesa de cota com fornecedor/)
  })

  it('fraca fica num grupo separado, depois das fortes, com o aviso de homônimo', () => {
    renderizar()
    const fortes = screen.getByRole('list', { name: 'Alertas' })
    const grupo = screen.getByRole('region', { name: 'Correspondência fraca' })
    expect(within(fortes).getAllByRole('article')).toHaveLength(2)
    const fraca = within(grupo).getByRole('article')
    expect(fraca).toHaveTextContent('JOAO MODELO')
    expect(within(fraca).getByText(AVISO_HOMONIMO)).toBeInTheDocument()
    expect(within(fortes).queryByText(AVISO_HOMONIMO)).toBeNull()
    expect(fortes.compareDocumentPosition(grupo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('liga o parlamentar e as duas empresas', () => {
    renderizar()
    expect(screen.getAllByRole('link', { name: 'ANA EXEMPLO' })[0]).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(screen.getAllByRole('link', { name: 'EMPRESA EXEMPLO LTDA' })[0]).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    expect(screen.getByRole('link', { name: 'EMPREITEIRA MODELO SA' })).toHaveAttribute(
      'href',
      '/empresa/44555666',
    )
  })

  it('data e valor do fato em pt-BR', () => {
    renderizar()
    const cartao = screen.getByRole('article', { name: 'Cota paga a fornecedor sancionado' })
    expect(cartao).toHaveTextContent('14/08/2026')
    expect(cartao).toHaveTextContent('R$ 1.200,00')
  })

  it('avisa quando há mais alertas do que os mostrados', () => {
    renderizar({ total: 250 })
    expect(screen.getByText(/Mostrando os 3 mais recentes de 250 alertas/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver todos os alertas' })).toHaveAttribute('href', '/alertas')
  })

  it('sem o aviso de corte quando verTodos é false', () => {
    renderizar({ total: 250, verTodos: false })
    expect(screen.queryByText(/mais recentes de/)).toBeNull()
  })

  it('lista vazia', () => {
    renderizar({ alertas: [], total: 0 })
    expect(screen.getByText('Nenhum alerta automático.')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/fontes.test.ts src/componentes/Alertas.test.tsx`
Expected: FAIL (módulos não existem).

- [ ] **Step 3: Implemente**

`site/src/fontes.ts`:

```ts
/** Fonte oficial de cada alerta, para o leitor conferir (spec do site, seção 6). */
import type { Alerta } from './tipos'

export interface FonteOficial {
  nome: string
  url: string
}

const PORTAL = 'https://portaldatransparencia.gov.br'

export function fonteDoAlerta(alerta: Alerta): FonteOficial {
  const { tipo } = alerta
  if (tipo.startsWith('cota_')) {
    return alerta.parlamentar_id?.startsWith('senado:')
      ? { nome: 'Senado Federal (cota parlamentar)', url: 'https://www6g.senado.leg.br/transparencia/sen/' }
      : {
          nome: 'Câmara dos Deputados (cota parlamentar)',
          url: 'https://www.camara.leg.br/transparencia/gastos-parlamentares',
        }
  }
  if (tipo.startsWith('emenda_')) return { nome: 'Portal da Transparência (emendas)', url: `${PORTAL}/emendas` }
  if (tipo.startsWith('contrato_')) return { nome: 'Portal da Transparência (contratos)', url: `${PORTAL}/contratos` }
  if (tipo.startsWith('licitacao_')) return { nome: 'Portal da Transparência (licitações)', url: `${PORTAL}/licitacoes` }
  if (alerta.cnpj_raiz) {
    return { nome: 'Portal da Transparência', url: `${PORTAL}/busca?termo=${alerta.cnpj_raiz}` }
  }
  return { nome: 'Portal da Transparência', url: PORTAL }
}
```

(Os endereços são conferidos no navegador na tarefa 16; se algum mudou, ajuste aqui e no teste.)

`site/src/componentes/Alertas.tsx`:

```tsx
import { useId } from 'react'
import { Link } from 'react-router'
import { rotaEmpresa, rotaParlamentar } from '../caminhos'
import { fonteDoAlerta } from '../fontes'
import { contar, formatarData, formatarInstante, formatarReais } from '../formato'
import type { Alerta, AlertaTipo } from '../tipos'

export const AVISO_ALERTA =
  'Indício gerado automaticamente a partir de dados públicos; não é acusação nem constatação de irregularidade.'
export const AVISO_HOMONIMO = 'Correspondência só pelo nome, pode ser homônimo.'
export const AVISO_RAIZ =
  'Correspondência só pela raiz do CNPJ (os 8 primeiros caracteres), não pelo CNPJ completo.'

export function avisoDaCorrespondencia(alerta: Alerta): string | null {
  if (alerta.correspondencia === 'forte') return null
  return alerta.tipo === 'parlamentar_socio_fornecedor' ? AVISO_HOMONIMO : AVISO_RAIZ
}

interface PropsCartao {
  alerta: Alerta
  tipo: AlertaTipo | undefined
  geradoEm: string
}

export function CartaoAlerta({ alerta, tipo, geradoEm }: PropsCartao) {
  const idTitulo = useId()
  const fonte = fonteDoAlerta(alerta)
  const aviso = avisoDaCorrespondencia(alerta)
  const empresas = [
    { raiz: alerta.cnpj_raiz, nome: alerta.empresa_nome },
    { raiz: alerta.cnpj_raiz_2, nome: alerta.empresa_nome_2 },
  ].filter((e): e is { raiz: string; nome: string | null } => e.raiz !== null)
  return (
    <article aria-labelledby={idTitulo} className="flex flex-col gap-3 rounded-cartao bg-graphite p-7">
      <p>
        <span className="selo-alerta">Alerta</span>
      </p>
      <h3 id={idTitulo} className="font-geist text-subheading font-medium">
        {tipo?.titulo ?? alerta.tipo}
      </h3>
      <p>{alerta.descricao}</p>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-ash">
        {alerta.data && (
          <div className="flex gap-1">
            <dt>Data do fato:</dt>
            <dd>{formatarData(alerta.data)}</dd>
          </div>
        )}
        {alerta.valor !== null && (
          <div className="flex gap-1">
            <dt>Valor:</dt>
            <dd>{formatarReais(alerta.valor)}</dd>
          </div>
        )}
      </dl>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {alerta.parlamentar_id && (
          <li>
            <Link to={rotaParlamentar(alerta.parlamentar_id)}>
              {alerta.parlamentar_nome ?? alerta.parlamentar_id}
            </Link>
          </li>
        )}
        {empresas.map((e) => (
          <li key={e.raiz}>
            <Link to={rotaEmpresa(e.raiz)}>{e.nome ?? e.raiz}</Link>
          </li>
        ))}
      </ul>
      {aviso && (
        <p>
          <strong>Atenção:</strong> <span>{aviso}</span>
        </p>
      )}
      {tipo && (
        <p className="text-ash">
          <strong className="text-bone">O que é:</strong> <span>{tipo.explicacao}</span>
        </p>
      )}
      {tipo && (
        <p className="text-ash">
          <strong className="text-bone">Cuidado:</strong> <span>{tipo.cautela}</span>
        </p>
      )}
      <p className="text-ash">Regra: {alerta.regra}</p>
      <p className="text-ash">{AVISO_ALERTA}</p>
      <p className="text-caption text-ash">
        Dados de {formatarInstante(geradoEm)} ·{' '}
        <a href={fonte.url} target="_blank" rel="noopener noreferrer">
          Fonte oficial: {fonte.nome}
        </a>
      </p>
    </article>
  )
}

interface PropsLista {
  alertas: Alerta[]
  total: number
  tipos: AlertaTipo[]
  geradoEm: string
  /** mostra o aviso de corte e o link para /alertas (padrão: sim) */
  verTodos?: boolean
}

export function ListaAlertas({ alertas, total, tipos, geradoEm, verTodos = true }: PropsLista) {
  const idFraca = useId()
  if (alertas.length === 0) return <p className="text-ash">Nenhum alerta automático.</p>
  const porTipo = new Map(tipos.map((t) => [t.tipo, t]))
  const fortes = alertas.filter((a) => a.correspondencia === 'forte')
  const fracas = alertas.filter((a) => a.correspondencia === 'fraca')
  const cartao = (a: Alerta) => (
    <li key={a.alerta_id}>
      <CartaoAlerta alerta={a} tipo={porTipo.get(a.tipo)} geradoEm={geradoEm} />
    </li>
  )
  return (
    <div className="flex flex-col gap-6">
      {fortes.length > 0 && (
        <ul aria-label="Alertas" className="flex flex-col gap-4">
          {fortes.map(cartao)}
        </ul>
      )}
      {fracas.length > 0 && (
        <section aria-labelledby={idFraca} className="flex flex-col gap-3">
          <h3 id={idFraca} className="font-geist text-subheading font-medium">
            Correspondência fraca
          </h3>
          <p className="text-ash">
            Nestes alertas, a ligação entre a pessoa e a empresa é menos certa. Leia o aviso de
            cada um.
          </p>
          <ul aria-label="Alertas de correspondência fraca" className="flex flex-col gap-4">
            {fracas.map(cartao)}
          </ul>
        </section>
      )}
      {verTodos && total > alertas.length && (
        <p className="text-ash">
          Mostrando os {alertas.length} mais recentes de {contar(total, 'alerta', 'alertas')}.{' '}
          <Link to="/alertas">Ver todos os alertas</Link>
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test -- src/fontes.test.ts src/componentes/Alertas.test.tsx && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Em `CartaoAlerta`, apague o parágrafo `<p className="text-ash">{AVISO_ALERTA}</p>`. Run:
`npm test -- src/componentes/Alertas.test.tsx`. Expected: FAIL em `todo alerta traz o aviso
fixo…`. Desfaça. Depois, em `ListaAlertas`, troque `fortes.map(cartao)` por
`alertas.map(cartao)`. Expected: FAIL em `fraca fica num grupo separado…`. Desfaça e confirme o
PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/fontes.ts site/src/fontes.test.ts site/src/componentes/Alertas.tsx \
  site/src/componentes/Alertas.test.tsx
git commit -m "feat(site): cartão e lista de alertas com aviso fixo e correspondência fraca à parte"
```

---

### Task 10: Gráfico de barras com tabela equivalente

**Files:**
- Create: `site/src/componentes/GraficoBarras.tsx`, `site/src/componentes/GraficoBarras.test.tsx`

**Interfaces:**
- Produces: `Barra { rotulo: string; valor: number }`;
  `GraficoBarras({ titulo, rotuloColuna, barras, horizontal?, destaque?, formatar?,
  formatarEixo? })`. `formatar` (tabela) é `formatarReais` por padrão; `formatarEixo`
  (eixo do gráfico) é `formatarReaisCurto`.

Visual (DESIGN.md, adaptação 2): barras em cinza `#b2b2b2`, a barra `destaque` em `#ffffff`,
eixos e grade em `#c2c2c2`, fundo transparente, fonte herdada; muitas categorias →
`horizontal` (barras ordenadas como chegam, rótulos cortados em 28 caracteres com "…"), sem
legenda colorida. O SVG do Plot fica `aria-hidden`; o contêiner tem `role="img"` e um
`aria-label` que diz que os números estão na tabela. O botão "Ver tabela: <título>" alterna a
tabela (`aria-expanded`, `aria-controls`); a tabela tem `<caption>` com o título. Sem barras:
"Sem dados." e nem gráfico nem botão.

- [ ] **Step 1: Escreva o teste**

`site/src/componentes/GraficoBarras.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GraficoBarras } from './GraficoBarras'

const barras = [
  { rotulo: '2025', valor: 300 },
  { rotulo: '2026', valor: 1200 },
]

describe('gráfico de barras', () => {
  it('desenha o gráfico e esconde a tabela até o clique', async () => {
    const usuario = userEvent.setup()
    const { container } = render(
      <GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} destaque="2026" />,
    )
    expect(screen.getByRole('img', { name: /Cota por ano/ })).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeNull()
    expect(screen.queryByRole('table')).toBeNull()

    const botao = screen.getByRole('button', { name: 'Ver tabela: Cota por ano' })
    expect(botao).toHaveAttribute('aria-expanded', 'false')
    await usuario.click(botao)
    expect(botao).toHaveAttribute('aria-expanded', 'true')

    const tabela = screen.getByRole('table', { name: 'Cota por ano' })
    const linhas = within(tabela).getAllByRole('row')
    expect(linhas[0]).toHaveTextContent('AnoValor')
    expect(linhas[1]).toHaveTextContent('2025R$ 300,00')
    expect(linhas[2]).toHaveTextContent('2026R$ 1.200,00')
  })

  it('funciona pelo teclado', async () => {
    const usuario = userEvent.setup()
    render(<GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} />)
    await usuario.tab()
    expect(screen.getByRole('button', { name: /Ver tabela/ })).toHaveFocus()
    await usuario.keyboard('{Enter}')
    expect(screen.getByRole('table', { name: 'Cota por ano' })).toBeInTheDocument()
  })

  it('a barra em destaque sai em branco e as outras em cinza', () => {
    const { container } = render(
      <GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} destaque="2026" />,
    )
    const cores = [...container.querySelectorAll('rect')].map((r) => r.getAttribute('fill'))
    expect(cores).toContain('#ffffff')
    expect(cores).toContain('#b2b2b2')
  })

  it('sem dados', () => {
    render(<GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={[]} />)
    expect(screen.getByText('Sem dados.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/componentes/GraficoBarras.test.tsx`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implemente**

`site/src/componentes/GraficoBarras.tsx`:

```tsx
import * as Plot from '@observablehq/plot'
import { useEffect, useId, useRef, useState } from 'react'
import { formatarReais, formatarReaisCurto } from '../formato'

export interface Barra {
  rotulo: string
  valor: number
}

interface Props {
  titulo: string
  /** cabeçalho da primeira coluna da tabela ("Ano", "Categoria") */
  rotuloColuna: string
  barras: Barra[]
  /** barras deitadas, para muitas categorias com nomes longos */
  horizontal?: boolean
  /** rótulo da barra em branco; as outras ficam em cinza */
  destaque?: string
  formatar?: (valor: number) => string
  formatarEixo?: (valor: number) => string
}

const CINZA = '#b2b2b2'
const BRANCO = '#ffffff'
const EIXO = '#c2c2c2'

function encurtar(texto: string): string {
  return texto.length > 28 ? `${texto.slice(0, 27)}…` : texto
}

export function GraficoBarras({
  titulo,
  rotuloColuna,
  barras,
  horizontal = false,
  destaque,
  formatar = formatarReais,
  formatarEixo = formatarReaisCurto,
}: Props) {
  const idTabela = useId()
  const [verTabela, setVerTabela] = useState(false)
  const alvo = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const elemento = alvo.current
    if (!elemento || barras.length === 0) return
    const cor = (b: Barra) => (b.rotulo === destaque ? BRANCO : CINZA)
    const estilo = { background: 'transparent', color: EIXO, fontFamily: 'inherit', fontSize: '13px' }
    const rotulos = barras.map((b) => b.rotulo)
    const grafico = horizontal
      ? Plot.plot({
          style: estilo,
          marginLeft: 200,
          height: 32 * barras.length + 40,
          x: { label: null, grid: true, tickFormat: (v: number) => formatarEixo(v) },
          y: { label: null, domain: rotulos, tickFormat: (t: string) => encurtar(t) },
          marks: [
            Plot.barX(barras, { x: 'valor', y: 'rotulo', fill: cor }),
            Plot.ruleX([0], { stroke: EIXO }),
          ],
        })
      : Plot.plot({
          style: estilo,
          marginLeft: 72,
          height: 240,
          x: { label: null, domain: rotulos },
          y: { label: null, grid: true, tickFormat: (v: number) => formatarEixo(v) },
          marks: [
            Plot.barY(barras, { x: 'rotulo', y: 'valor', fill: cor }),
            Plot.ruleY([0], { stroke: EIXO }),
          ],
        })
    grafico.setAttribute('aria-hidden', 'true')
    elemento.replaceChildren(grafico)
    return () => grafico.remove()
  }, [barras, horizontal, destaque, formatarEixo])

  if (barras.length === 0) return <p className="text-ash">Sem dados.</p>

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="font-geist text-subheading font-medium">{titulo}</figcaption>
      <div
        ref={alvo}
        role="img"
        aria-label={`${titulo}: gráfico de barras. Os mesmos números estão na tabela.`}
        className="overflow-x-auto"
      />
      <div>
        <button
          type="button"
          aria-expanded={verTabela}
          aria-controls={idTabela}
          onClick={() => setVerTabela((v) => !v)}
          className="rounded-full border border-hairline/40 px-3.5 py-1.5 text-caption"
        >
          {verTabela ? 'Esconder tabela' : 'Ver tabela'}
          <span className="sr-only">: {titulo}</span>
        </button>
      </div>
      <table id={idTabela} hidden={!verTabela} className="w-full text-left">
        <caption className="sr-only">{titulo}</caption>
        <thead>
          <tr>
            <th scope="col">{rotuloColuna}</th>
            <th scope="col" className="text-right">
              Valor
            </th>
          </tr>
        </thead>
        <tbody>
          {barras.map((b, i) => (
            <tr key={`${i}-${b.rotulo}`}>
              <th scope="row" className="font-normal">
                {b.rotulo}
              </th>
              <td className="text-right">{formatar(b.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
```

O nome acessível do botão aberto vira "Esconder tabela: <título>". Se o Plot recusar o `fill`
como função num tipo do TypeScript, use `fill: (b: Barra) => cor(b)`; não troque por uma escala
de cores com legenda.

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test -- src/componentes/GraficoBarras.test.tsx && npm run lint && npm run typecheck`
Expected: PASS (o Plot roda no jsdom; conferido no protótipo); lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Na `<table>`, apague `hidden={!verTabela}`. Run:
`npm test -- src/componentes/GraficoBarras.test.tsx`. Expected: FAIL em `desenha o gráfico e
esconde a tabela até o clique`. Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/componentes/GraficoBarras.tsx site/src/componentes/GraficoBarras.test.tsx
git commit -m "feat(site): gráfico de barras em cinza com tabela equivalente"
```

---

## Páginas (tarefas 11 a 15)

Nas tarefas 11 a 15, o plano dá o comportamento e os testes completos; o código das páginas é
escrito na execução até os testes passarem, seguindo o DESIGN.md e reaproveitando os componentes
das tarefas 7 a 10. Regras comuns:

- Cada página carrega o que precisa com `useDados` e, enquanto isso, mostra `Carregando`; em
  erro, `AvisoErro` (que vira a 404 em `nao_encontrado`).
- As páginas de parlamentar, empresa e alertas carregam também o `resumo.json` (tipos de alerta
  e `gerado_em` para os cartões), por exemplo com
  `useDados(\`parlamentar:${slug}\`, () => Promise.all([carregarParlamentar(slug), carregarResumo()]))`.
- Cada seção é um `<section aria-labelledby>` com `<h2>`, para virar região com nome; as tabelas
  têm `<caption>` (pode ser `sr-only`) e `<th scope>`.
- Valores com `formatarReais` nas tabelas e `formatarReaisCurto` nos números de destaque; datas
  com `formatarData`/`formatarInstante`; CNPJ com `formatarCnpj`.
- Links para fora (sites oficiais) abrem em nova aba com `rel="noopener noreferrer"`.
- `useTitulo` em toda página.
- Os exemplos são de 2026-10-07: depois de 2026-10-10, a faixa de dados antigos (`role="status"`)
  aparece em todos os testes de página. Por isso os testes de página não procuram `status`.

### Task 11: Página inicial (`/`)

**Files:**
- Modify: `site/src/paginas/Inicio.tsx` (troca a provisória)
- Create: `site/src/paginas/Inicio.test.tsx`

**Interfaces:**
- Consumes: `CaixaBusca`, `ListaAlertas`, `useDados`, `carregarResumo`, `formato.ts`,
  `rotaAlertas`.

Comportamento:
- Capa (sempre, mesmo sem o resumo): faixa de largura total com o gradiente
  `bg-linear-to-r from-capa-inicio to-capa-fim`, `<h1>` "Para onde vai o dinheiro público"
  (`text-display-celular sm:text-display`, peso 500), uma linha em Bone ("Gastos de
  parlamentares, emendas e contratos federais, com alertas automáticos explicados.") e a
  `CaixaBusca grande`.
- Com o resumo:
  - Região "Números gerais": Cota parlamentar (`totais.cota`), Emendas pagas
    (`totais.emendas_pago`), Contratos federais (`totais.contratos`), em `formatarReaisCurto`;
    Parlamentares e Empresas em `formatarInteiro`.
  - Região "Alertas por tipo": um link por tipo, na `ordem`, para `/alertas?tipo=<tipo>`, com
    o título e `contar(quantidade, 'alerta', 'alertas')`.
  - Região "Alertas recentes": `ListaAlertas` com `alertas_recentes` (total = tamanho da
    lista, `verTodos={false}`) e o link "Ver todos os alertas" (`/alertas`).
  - Parágrafo "Dados atualizados em 07/10/2026 às 08:02." e outro "Cota até 01/09/2026,
    emendas até 03/10/2026, contratos até 05/10/2026; Receita Federal: setembro de 2026."
    (cada data com `formatarData`; a da Receita com `formatarCompetencia`).
- Sem o resumo: a capa e a busca continuam; no lugar do resto, `AvisoErro`.
- `useTitulo()` (título "Eleitorado").

- [ ] **Step 1: Escreva o teste**

`site/src/paginas/Inicio.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA } from '../componentes/Alertas'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'

describe('página inicial', () => {
  it('capa com a busca, mesmo antes do resumo', () => {
    renderizarSite('/')
    expect(screen.getByRole('heading', { level: 1, name: 'Para onde vai o dinheiro público' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Buscar parlamentar, empresa ou CNPJ' })).toBeInTheDocument()
    expect(document.title).toBe('Eleitorado')
  })

  it('números gerais', async () => {
    renderizarSite('/')
    const numeros = await screen.findByRole('region', { name: 'Números gerais' })
    for (const texto of [
      'Cota parlamentar',
      'R$ 1,5 mil',
      'Emendas pagas',
      'R$ 250 mil',
      'Contratos federais',
      'R$ 350 mil',
      'Parlamentares',
      'Empresas',
    ]) {
      expect(numeros).toHaveTextContent(texto)
    }
  })

  it('alertas por tipo, na ordem, com link e quantidade', async () => {
    renderizarSite('/')
    const tipos = await screen.findByRole('region', { name: 'Alertas por tipo' })
    const links = within(tipos).getAllByRole('link')
    expect(links).toHaveLength(9)
    expect(links[0]).toHaveTextContent('Cota paga a fornecedor sancionado')
    expect(links[0]).toHaveTextContent('1 alerta')
    expect(links[0]).toHaveAttribute('href', '/alertas?tipo=cota_fornecedor_sancionado')
    expect(links[1]).toHaveTextContent('Cota com CPF ou CNPJ inválido')
    expect(links[1]).toHaveTextContent('0 alertas')
    expect(links[8]).toHaveAttribute('href', '/alertas?tipo=parlamentar_socio_fornecedor')
  })

  it('a ordem vem do campo ordem, não da posição no arquivo', async () => {
    const resumo = exemplo<{ alerta_tipos: unknown[] }>('resumo.json')
    servir({ 'resumo.json': { ...resumo, alerta_tipos: [...resumo.alerta_tipos].reverse() } })
    renderizarSite('/')
    const tipos = await screen.findByRole('region', { name: 'Alertas por tipo' })
    expect(within(tipos).getAllByRole('link')[0]).toHaveTextContent('Cota paga a fornecedor sancionado')
  })

  it('alertas recentes, todos com o aviso fixo', async () => {
    renderizarSite('/')
    const recentes = await screen.findByRole('region', { name: 'Alertas recentes' })
    const cartoes = within(recentes).getAllByRole('article')
    expect(cartoes).toHaveLength(2)
    for (const cartao of cartoes) expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
    expect(within(recentes).getByRole('link', { name: 'Ver todos os alertas' })).toHaveAttribute(
      'href',
      '/alertas',
    )
  })

  it('data da atualização e até quando vai cada fonte', async () => {
    renderizarSite('/')
    expect(await screen.findByText('Dados atualizados em 07/10/2026 às 08:02.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Cota até 01/09/2026, emendas até 03/10/2026, contratos até 05/10/2026; Receita Federal: setembro de 2026.',
      ),
    ).toBeInTheDocument()
  })

  it('sem o resumo, a busca continua e o resto avisa', async () => {
    servir({ 'resumo.json': REDE })
    renderizarSite('/')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
  })

  it('esquema novo: avisa que o site precisa ser atualizado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    renderizarSite('/')
    expect(await screen.findByText(/precisa ser atualizado/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/paginas/Inicio.test.tsx`
Expected: FAIL (a página provisória só tem o `<h1>`).

- [ ] **Step 3: Implemente** `site/src/paginas/Inicio.tsx` pelo comportamento acima.

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Na lista de tipos, tire a ordenação por `ordem` (use `alerta_tipos` como vem). Run:
`npm test -- src/paginas/Inicio.test.tsx -t "campo ordem"`. Expected: FAIL. Desfaça e confirme o
PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/paginas/Inicio.tsx site/src/paginas/Inicio.test.tsx
git commit -m "feat(site): página inicial com busca, números gerais e alertas recentes"
```

---

### Task 12: Página do parlamentar (`/parlamentar/:slug`)

**Files:**
- Modify: `site/src/paginas/Parlamentar.tsx` (troca a provisória)
- Create: `site/src/paginas/Parlamentar.test.tsx`

**Interfaces:**
- Consumes: `carregarParlamentar`, `carregarResumo`, `urlDaFoto`, `GraficoBarras`,
  `ListaAlertas`, `rotaEmpresa`, `formato.ts`.

Comportamento:
- Cabeçalho: foto (só se `urlDaFoto(foto)` não for nulo; `alt="Foto de <nome>"`,
  `loading="lazy"`, `referrerPolicy="no-referrer"`, cantos `rounded-cartao`); sem foto, nada
  (ou as iniciais num círculo `aria-hidden`); `<h1>` com o nome; a linha
  "PEX · DF · Câmara dos Deputados" (ou "Senado Federal"; partes nulas saem); legislaturas
  ("Legislaturas: 56 e 57", com `Intl.ListFormat('pt-BR')`); link "Página oficial na Câmara dos
  Deputados" ou "Página oficial no Senado Federal" (`url_oficial`, nova aba).
- Região "Cota parlamentar": total em reais; `GraficoBarras` "Cota por ano" (rótulo = ano,
  destaque = ano mais recente); `GraficoBarras horizontal` "Cota por categoria" (categoria nula
  vira "Sem categoria"); tabela "Maiores fornecedores" (Fornecedor, Documento, Despesas, Valor):
  o nome é link para `/empresa/<cnpj_raiz>` só quando `cnpj_raiz` existe; o documento sai com
  `formatarCnpj` (CPF já vem mascarado e fica como está). Sem despesas (`por_ano` vazio):
  "Nenhuma despesa de cota nos dados." no lugar dos gráficos e da tabela.
- Região "Emendas parlamentares": total pago; `GraficoBarras` "Emendas pagas por ano";
  tabela "Maiores favorecidos" (Favorecido, Documento, Pago), com link quando há `cnpj_raiz`.
  Vazio: "Nenhuma emenda paga nos dados."
- Região "Alertas": `ListaAlertas` com `alertas.itens`, `alertas.total`, os tipos e o
  `gerado_em` do resumo.
- `useTitulo(nome)`. Slug inválido ou arquivo inexistente → 404.

- [ ] **Step 1: Escreva o teste**

`site/src/paginas/Parlamentar.test.tsx`:

```tsx
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA, AVISO_HOMONIMO } from '../componentes/Alertas'
import { REDE, caminhosPedidos, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { ArquivoParlamentar } from '../tipos'

describe('página do parlamentar', () => {
  it('cabeçalho com partido, UF, casa e link oficial', async () => {
    renderizarSite('/parlamentar/camara-900001')
    expect(await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })).toBeInTheDocument()
    expect(screen.getByText('PEX · DF · Câmara dos Deputados')).toBeInTheDocument()
    expect(screen.getByText('Legislaturas: 56 e 57')).toBeInTheDocument()
    const oficial = screen.getByRole('link', { name: 'Página oficial na Câmara dos Deputados' })
    expect(oficial).toHaveAttribute('href', 'https://www.camara.leg.br/deputados/900001')
    expect(oficial).toHaveAttribute('rel', 'noopener noreferrer')
    await waitFor(() => expect(document.title).toBe('ANA EXEMPLO · Eleitorado'))
  })

  it('sem foto no arquivo, sem imagem', async () => {
    renderizarSite('/parlamentar/camara-900001')
    await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })
    expect(screen.queryByRole('img', { name: /Foto de/ })).toBeNull()
  })

  it('foto do Senado em http vira https; foto de outro site não aparece', async () => {
    const arquivo = exemplo<ArquivoParlamentar>('parlamentar/senado-900002.json')
    arquivo.parlamentar.foto = 'http://www.senado.leg.br/senadores/img/fotos-oficiais/senador900002.jpg'
    servir({ 'parlamentar/senado-900002.json': arquivo })
    renderizarSite('/parlamentar/senado-900002')
    expect(await screen.findByRole('img', { name: 'Foto de JOAO MODELO' })).toHaveAttribute(
      'src',
      'https://www.senado.leg.br/senadores/img/fotos-oficiais/senador900002.jpg',
    )
  })

  it('cota: total, gráficos com tabela e maiores fornecedores', async () => {
    const { usuario } = renderizarSite('/parlamentar/camara-900001')
    const cota = await screen.findByRole('region', { name: 'Cota parlamentar' })
    expect(cota).toHaveTextContent('R$ 1.500,00')
    await usuario.click(within(cota).getByRole('button', { name: 'Ver tabela: Cota por ano' }))
    expect(within(cota).getByRole('table', { name: 'Cota por ano' })).toHaveTextContent(
      '2026R$ 1.200,00',
    )
    expect(
      within(cota).getByRole('button', { name: 'Ver tabela: Cota por categoria' }),
    ).toBeInTheDocument()
    const fornecedores = within(cota).getByRole('table', { name: 'Maiores fornecedores' })
    expect(within(fornecedores).getByRole('link', { name: 'EMPRESA EXEMPLO LTDA' })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    expect(fornecedores).toHaveTextContent('11.222.333/0001-81')
    expect(fornecedores).toHaveTextContent('***.456.789-**')
    expect(fornecedores).toHaveTextContent('MARIA EXEMPLO')
    expect(within(fornecedores).queryByRole('link', { name: 'MARIA EXEMPLO' })).toBeNull()
  })

  it('emendas: total pago, por ano e maiores favorecidos', async () => {
    renderizarSite('/parlamentar/camara-900001')
    const emendas = await screen.findByRole('region', { name: 'Emendas parlamentares' })
    expect(emendas).toHaveTextContent('R$ 250.000,00')
    expect(
      within(emendas).getByRole('button', { name: 'Ver tabela: Emendas pagas por ano' }),
    ).toBeInTheDocument()
    const favorecidos = within(emendas).getByRole('table', { name: 'Maiores favorecidos' })
    expect(within(favorecidos).getByRole('link', { name: 'MUNICIPIO DE EXEMPLO' })).toHaveAttribute(
      'href',
      '/empresa/99888777',
    )
  })

  it('alertas do parlamentar, com o aviso fixo', async () => {
    renderizarSite('/parlamentar/camara-900001')
    const alertas = await screen.findByRole('region', { name: 'Alertas' })
    expect(within(within(alertas).getByRole('article')).getByText(AVISO_ALERTA)).toBeInTheDocument()
  })

  it('senador sem cota nem emendas; alerta fraco à parte', async () => {
    renderizarSite('/parlamentar/senado-900002')
    expect(await screen.findByText('Nenhuma despesa de cota nos dados.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma emenda paga nos dados.')).toBeInTheDocument()
    expect(screen.getByText('PMO · SP · Senado Federal')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Página oficial no Senado Federal' })).toBeInTheDocument()
    const grupo = screen.getByRole('region', { name: 'Correspondência fraca' })
    expect(within(grupo).getByText(AVISO_HOMONIMO)).toBeInTheDocument()
  })

  it('parlamentar que não está nos dados: 404', async () => {
    renderizarSite('/parlamentar/camara-1')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('endereço inválido: 404 sem baixar arquivo de parlamentar', async () => {
    renderizarSite('/parlamentar/qualquer-coisa')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
    expect(caminhosPedidos().filter((c) => c.startsWith('parlamentar/'))).toEqual([])
  })

  it('falha de rede: tentar de novo', async () => {
    servir({ 'parlamentar/camara-900001.json': REDE })
    const { usuario } = renderizarSite('/parlamentar/camara-900001')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/paginas/Parlamentar.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implemente** `site/src/paginas/Parlamentar.tsx` pelo comportamento acima
  (exporta `PaginaParlamentar`).

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Na tabela de fornecedores, faça o nome ser sempre link (`rotaEmpresa(f.cnpj_raiz ?? '')`). Run:
`npm test -- src/paginas/Parlamentar.test.tsx -t "maiores fornecedores"`. Expected: FAIL (MARIA
EXEMPLO vira link). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/paginas/Parlamentar.tsx site/src/paginas/Parlamentar.test.tsx
git commit -m "feat(site): página do parlamentar com cota, emendas e alertas"
```

---

### Task 13: Página da empresa (`/empresa/:raiz`)

**Files:**
- Modify: `site/src/paginas/Empresa.tsx` (troca a provisória)
- Create: `site/src/paginas/Empresa.test.tsx`

**Interfaces:**
- Consumes: `carregarEmpresa`, `carregarResumo`, `ListaAlertas`, `rotaParlamentar`,
  `rotaEmpresa`, `formato.ts`.

Comportamento:
- Se o parâmetro tiver letras minúsculas, `<Navigate replace>` para o endereço em maiúsculas
  (`/empresa/1ab2c3d4` → `/empresa/1AB2C3D4`).
- `<h1>` com a razão social (sem ela, "Empresa 11.222.333"); abaixo, "CNPJ da matriz
  11.222.333/0001-81" e o link "Ver no Portal da Transparência" (`url_portal`, nova aba).
- Região "Cadastro na Receita Federal" (`<dl>` com pares `<dt>`/`<dd>` dentro de `<div>`):
  Situação ("ATIVA desde 02/04/2018"; o motivo, se houver e não for "SEM MOTIVO"), Abertura,
  Porte, Natureza jurídica, Capital social, Atividade principal, Município ("BRASILIA/DF"),
  Optante pelo Simples (Sim/Não/—), MEI, Estabelecimentos, Sócios ("2 (os nomes não são
  publicados)"); no fim, "Cadastro da Receita Federal de setembro de 2026." Nunca nomes de
  sócios (os dados nem os têm).
- Região "O que recebeu do governo federal":
  - "Cota parlamentar": total; tabela "Cota parlamentar por parlamentar" (link para o
    parlamentar, valor). Vazio: "Nenhuma despesa de cota nos dados."
  - "Emendas": total pago; tabela "Emendas por autor" (link quando `parlamentar_id` existe;
    senão só o texto do autor). Vazio: "Nenhum pagamento de emenda nos dados."
  - "Contratos federais": total e `contar(quantidade, 'contrato', 'contratos')`; tabela
    "Contratos por órgão" (Órgão, Contratos, Valor). Vazio: "Nenhum contrato federal nos dados."
  - "Licitações": `contar(vencidas, 'licitação vencida', 'licitações vencidas')`.
- Região "Sanções (CEIS e CNEP)": `<h3>` "Vigentes" e "Encerradas" (só os grupos com itens);
  cada sanção com cadastro, categoria, órgão e período ("01/03/2025 a 01/03/2027"; sem fim,
  "desde 01/03/2025"). Texto neutro, sem cor de alerta. Vazio: "Nenhuma sanção no CEIS ou no
  CNEP nos dados."
- Região "Alertas": `ListaAlertas`.
- `useTitulo(razão social)`. Raiz inválida, bloco inexistente ou raiz fora do bloco → 404.

- [ ] **Step 1: Escreva o teste**

`site/src/paginas/Empresa.test.tsx`:

```tsx
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { BlocoEmpresas, Empresa } from '../tipos'

function blocoComEmpresa(): { bloco: BlocoEmpresas; empresa: Empresa } {
  const bloco = exemplo<BlocoEmpresas>('empresa/b_112.json')
  const empresa = bloco.empresas['11222333']
  if (!empresa) throw new Error('exemplo sem a empresa 11222333')
  return { bloco, empresa }
}

function valorDe(regiao: HTMLElement, rotulo: string): string | null {
  return within(regiao).getByText(rotulo).nextElementSibling?.textContent ?? null
}

describe('página da empresa', () => {
  it('cadastro da Receita, com a contagem de sócios e sem os nomes', async () => {
    renderizarSite('/empresa/11222333')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
    expect(screen.getByText('CNPJ da matriz 11.222.333/0001-81')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver no Portal da Transparência' })).toHaveAttribute(
      'href',
      'https://portaldatransparencia.gov.br/busca?termo=11222333000181',
    )
    const cadastro = screen.getByRole('region', { name: 'Cadastro na Receita Federal' })
    expect(valorDe(cadastro, 'Situação')).toBe('ATIVA desde 02/04/2018')
    expect(valorDe(cadastro, 'Abertura')).toBe('02/04/2018')
    expect(valorDe(cadastro, 'Porte')).toBe('MICRO EMPRESA')
    expect(valorDe(cadastro, 'Capital social')).toMatch(/R\$\s50\.000,00/)
    expect(valorDe(cadastro, 'Município')).toBe('BRASILIA/DF')
    expect(valorDe(cadastro, 'Optante pelo Simples')).toBe('Sim')
    expect(valorDe(cadastro, 'MEI')).toBe('Não')
    expect(valorDe(cadastro, 'Estabelecimentos')).toBe('1')
    expect(valorDe(cadastro, 'Sócios')).toBe('2 (os nomes não são publicados)')
    expect(cadastro).toHaveTextContent('Cadastro da Receita Federal de setembro de 2026.')
    await waitFor(() => expect(document.title).toBe('EMPRESA EXEMPLO LTDA · Eleitorado'))
  })

  it('o que recebeu: cota, contratos e licitações; emendas vazias', async () => {
    renderizarSite('/empresa/11222333')
    const recebeu = await screen.findByRole('region', { name: 'O que recebeu do governo federal' })
    const cota = within(recebeu).getByRole('table', { name: 'Cota parlamentar por parlamentar' })
    expect(within(cota).getByRole('link', { name: 'ANA EXEMPLO' })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(cota).toHaveTextContent('R$ 1.200,00')
    expect(recebeu).toHaveTextContent('Nenhum pagamento de emenda nos dados.')
    const contratos = within(recebeu).getByRole('table', { name: 'Contratos por órgão' })
    expect(contratos).toHaveTextContent('MINISTERIO EXEMPLO')
    expect(contratos).toHaveTextContent('R$ 350.000,00')
    expect(recebeu).toHaveTextContent('2 contratos')
    expect(recebeu).toHaveTextContent('1 licitação vencida')
  })

  it('emendas por autor, com link só quando o autor é parlamentar', async () => {
    const { bloco, empresa } = blocoComEmpresa()
    empresa.emendas = {
      total_pago: 5000,
      autores: [
        { autor: 'ANA EXEMPLO', parlamentar_id: 'camara:900001', pago: 3000 },
        { autor: 'BANCADA DO DF', parlamentar_id: null, pago: 2000 },
      ],
    }
    servir({ 'empresa/b_112.json': bloco })
    renderizarSite('/empresa/11222333')
    const emendas = await screen.findByRole('table', { name: 'Emendas por autor' })
    expect(within(emendas).getByRole('link', { name: 'ANA EXEMPLO' })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(emendas).toHaveTextContent('BANCADA DO DF')
    expect(within(emendas).queryByRole('link', { name: 'BANCADA DO DF' })).toBeNull()
  })

  it('sanções em grupos, sem grupo vazio', async () => {
    renderizarSite('/empresa/11222333')
    const sancoes = await screen.findByRole('region', { name: 'Sanções (CEIS e CNEP)' })
    expect(within(sancoes).getByRole('heading', { name: 'Vigentes' })).toBeInTheDocument()
    expect(within(sancoes).queryByRole('heading', { name: 'Encerradas' })).toBeNull()
    for (const texto of ['CEIS', 'MINISTERIO EXEMPLO', '01/03/2025 a 01/03/2027']) {
      expect(sancoes).toHaveTextContent(texto)
    }
  })

  it('sem sanções', async () => {
    const { bloco, empresa } = blocoComEmpresa()
    empresa.sancoes = []
    servir({ 'empresa/b_112.json': bloco })
    renderizarSite('/empresa/11222333')
    expect(
      await screen.findByText('Nenhuma sanção no CEIS ou no CNEP nos dados.'),
    ).toBeInTheDocument()
  })

  it('alertas da empresa: fortes e o fraco à parte', async () => {
    renderizarSite('/empresa/11222333')
    const alertas = await screen.findByRole('region', { name: 'Alertas' })
    expect(within(alertas).getAllByRole('article')).toHaveLength(3)
    expect(within(alertas).getByRole('region', { name: 'Correspondência fraca' })).toBeInTheDocument()
    expect(within(alertas).getByRole('link', { name: 'EMPREITEIRA MODELO SA' })).toHaveAttribute(
      'href',
      '/empresa/44555666',
    )
  })

  it('raiz em minúsculas vai para o endereço canônico (CNPJ alfanumérico)', async () => {
    const { empresa } = blocoComEmpresa()
    servir({ 'empresa/b_1AB.json': { esquema: 1, bloco: '1AB', empresas: { '1AB2C3D4': empresa } } })
    const { local } = renderizarSite('/empresa/1ab2c3d4')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
    expect(local()).toBe('/empresa/1AB2C3D4')
  })

  it.each(['11222399', '99999999', 'abc'])('empresa %s fora dos dados: 404', async (raiz) => {
    renderizarSite(`/empresa/${raiz}`)
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('falha de rede: tentar de novo', async () => {
    servir({ 'empresa/b_112.json': REDE })
    const { usuario } = renderizarSite('/empresa/11222333')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/paginas/Empresa.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implemente** `site/src/paginas/Empresa.tsx` pelo comportamento acima (exporta
  `PaginaEmpresa`).

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Tire o `<Navigate replace>` para a raiz em maiúsculas. Run:
`npm test -- src/paginas/Empresa.test.tsx -t "minúsculas"`. Expected: FAIL (a raiz minúscula
não passa na validação e a página vira 404). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/paginas/Empresa.tsx site/src/paginas/Empresa.test.tsx
git commit -m "feat(site): página da empresa com cadastro, recebimentos, sanções e alertas"
```

---

### Task 14: Página de alertas (`/alertas`)

**Files:**
- Modify: `site/src/paginas/Alertas.tsx` (troca a provisória)
- Create: `site/src/paginas/Alertas.test.tsx`

**Interfaces:**
- Consumes: `carregarResumo`, `carregarAlertas`, `ListaAlertas`, `rotaAlertas`,
  `useSearchParams`.

Comportamento:
- `<h1>` "Alertas automáticos"; parágrafo com o aviso fixo (`AVISO_ALERTA`).
- Região "Como cada alerta é gerado": um `<h3>` por tipo (na `ordem`), com a `explicacao`, a
  `cautela` e `contar(quantidade, 'alerta', 'alertas')`.
- `<nav aria-label="Tipos de alerta">`: um link por tipo (`rotaAlertas(tipo)`), com o título e
  a quantidade; o selecionado leva `aria-current="page"` (o `NavLink` não serve, porque a
  diferença está na query string).
- Tipo selecionado: o da query (`?tipo=`); sem ele, o primeiro (na `ordem`) com
  `quantidade > 0`; se nenhum tiver alertas, o primeiro. Tipo que não está no resumo → 404.
- Página: `?pagina=` inteiro ≥ 1 (o resto vira 1).
- Tipo com `quantidade === 0`: "Nenhum alerta deste tipo nos dados de 07/10/2026 às 08:02.",
  sem baixar arquivo (o pipeline não gera arquivo para tipo vazio).
- Senão: `carregarAlertas(tipo, pagina)` e `ListaAlertas` (`verTodos={false}`), com
  "Página 1 de 3" e os links "Página anterior" e "Próxima página"
  (`rotaAlertas(tipo, pagina ± 1)`) quando existem, dentro de `<nav aria-label="Paginação">`.
  Página além da última (404 do arquivo) → 404.
- `useTitulo('Alertas')`.

- [ ] **Step 1: Escreva o teste**

`site/src/paginas/Alertas.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA } from '../componentes/Alertas'
import { caminhosPedidos, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { PaginaAlertas, Resumo } from '../tipos'

describe('página de alertas', () => {
  it('explica cada regra, na ordem', async () => {
    renderizarSite('/alertas')
    const regras = await screen.findByRole('region', { name: 'Como cada alerta é gerado' })
    const titulos = within(regras)
      .getAllByRole('heading', { level: 3 })
      .map((h) => h.textContent)
    expect(titulos).toEqual(
      exemplo<Resumo>('resumo.json')
        .alerta_tipos.sort((a, b) => a.ordem - b.ordem)
        .map((t) => t.titulo),
    )
    expect(regras).toHaveTextContent('O parlamentar foi reembolsado pela cota')
    expect(regras).toHaveTextContent('Deputados são identificados pelo nome e por parte do CPF')
  })

  it('sem tipo na query: o primeiro com alertas, marcado no filtro', async () => {
    renderizarSite('/alertas')
    const filtro = await screen.findByRole('navigation', { name: 'Tipos de alerta' })
    const atual = within(filtro).getByRole('link', { current: 'page' })
    expect(atual).toHaveTextContent('Cota paga a fornecedor sancionado')
    expect(atual).toHaveAttribute('href', '/alertas?tipo=cota_fornecedor_sancionado')
    const cartao = await screen.findByRole('article')
    expect(cartao).toHaveTextContent('Despesa de cota com fornecedor sancionado no CEIS')
    expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
    expect(screen.getByText('Página 1 de 1')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Próxima página' })).toBeNull()
    expect(document.title).toBe('Alertas · Eleitorado')
  })

  it('tipo sem alertas: avisa sem baixar arquivo', async () => {
    renderizarSite('/alertas?tipo=cota_documento_invalido')
    expect(
      await screen.findByText('Nenhum alerta deste tipo nos dados de 07/10/2026 às 08:02.'),
    ).toBeInTheDocument()
    expect(caminhosPedidos().some((c) => c.startsWith('alertas/'))).toBe(false)
  })

  it('tipo desconhecido: 404', async () => {
    renderizarSite('/alertas?tipo=inventado')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('página além da última: 404', async () => {
    renderizarSite('/alertas?tipo=cota_fornecedor_sancionado&pagina=2')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('paginação', async () => {
    const pagina = exemplo<PaginaAlertas>('alertas/cota_fornecedor_sancionado/1.json')
    servir({
      'alertas/cota_fornecedor_sancionado/1.json': { ...pagina, paginas: 3, total: 1200 },
      'alertas/cota_fornecedor_sancionado/2.json': { ...pagina, pagina: 2, paginas: 3, total: 1200 },
    })
    const { usuario } = renderizarSite('/alertas?tipo=cota_fornecedor_sancionado')
    expect(await screen.findByText('Página 1 de 3')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Página anterior' })).toBeNull()
    await usuario.click(screen.getByRole('link', { name: 'Próxima página' }))
    expect(await screen.findByText('Página 2 de 3')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Página anterior' })).toHaveAttribute(
      'href',
      '/alertas?tipo=cota_fornecedor_sancionado',
    )
    expect(screen.getByRole('link', { name: 'Próxima página' })).toHaveAttribute(
      'href',
      '/alertas?tipo=cota_fornecedor_sancionado&pagina=3',
    )
  })

  it('trocar de tipo pelo filtro', async () => {
    const resumo = exemplo<Resumo>('resumo.json')
    const alerta = resumo.alertas_recentes.find((a) => a.tipo === 'licitacao_socios_em_comum')
    servir({
      'alertas/licitacao_socios_em_comum/1.json': {
        esquema: 1,
        tipo: 'licitacao_socios_em_comum',
        pagina: 1,
        paginas: 1,
        total: 1,
        alertas: [alerta],
      },
    })
    const { usuario, local } = renderizarSite('/alertas')
    const filtro = await screen.findByRole('navigation', { name: 'Tipos de alerta' })
    await usuario.click(within(filtro).getByRole('link', { name: /Concorrentes com sócios em comum/ }))
    expect(local()).toBe('/alertas?tipo=licitacao_socios_em_comum')
    expect(await screen.findByText(/Participantes da mesma licitação/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/paginas/Alertas.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implemente** `site/src/paginas/Alertas.tsx` pelo comportamento acima (exporta
  `PaginaAlertas`).

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

Tire o caso `quantidade === 0` (baixe sempre a página). Run:
`npm test -- src/paginas/Alertas.test.tsx -t "tipo sem alertas"`. Expected: FAIL (o arquivo é
pedido, dá 404 e a página vira "Página não encontrada"). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/paginas/Alertas.tsx site/src/paginas/Alertas.test.tsx
git commit -m "feat(site): página de alertas com regras explicadas, filtro e paginação"
```

---

### Task 15: Página sobre (`/sobre`)

**Files:**
- Modify: `site/src/paginas/Sobre.tsx` (troca a provisória)
- Create: `site/src/paginas/Sobre.test.tsx`

**Interfaces:**
- Consumes: `carregarResumo`, `PADRAO_DADOS_URL`, `AVISO_ALERTA`, `formato.ts`.

Comportamento (texto em linguagem simples; as seções fixas aparecem mesmo sem o resumo):
- `<h1>` "Sobre o Eleitorado".
- "De onde vêm os dados": Câmara dos Deputados e Senado Federal (cota e parlamentares), CGU e
  Portal da Transparência (emendas, contratos, licitações, sanções CEIS e CNEP), PNCP, IBGE e
  Receita Federal (cadastro de empresas); atualização diária; a base da Receita é mensal.
- "Como ler um alerta": o que é um alerta automático; o aviso fixo (`AVISO_ALERTA`, num
  elemento próprio); correspondência fraca (homônimo; só a raiz do CNPJ); a regra e a fonte em
  cada cartão.
- "Limitações conhecidas": a data de cada fonte (`dados_ate`); senadores ligados a empresas só
  pelo nome; sanção que pode valer só para o órgão que a aplicou; a Receita informa só a
  situação atual; o site mostra agregados e aponta para a fonte oficial em vez de listar cada
  despesa.
- "Privacidade e LGPD": CPF só mascarado; sócios só como contagem; o site não usa cookies,
  analytics nem fontes externas (a frase "O site não usa cookies, analytics nem fontes
  externas." aparece literalmente).
- "Baixar os dados": link "Modelos de dados" para
  `https://github.com/bonvenuto/eleitorado/blob/main/docs/modelos-de-dados.md` e link
  "Manifesto dos dados publicados" para `<origem de PADRAO_DADOS_URL>/manifesto.json`.
- "Situação das fontes": tabela "Situação das fontes" (Fonte, Cadência, Último sucesso,
  Situação), com `ok` → "Em dia", `aviso` → "Atrasada", `erro` → "Com erro" (as duas últimas
  com o selo âmbar ao lado; nada de vermelho) e `ultimo_sucesso` nulo → "nunca"; tabela
  "Fontes que encolheram" (Fonte, Competência, Coletada em, Linhas antes, Linhas depois,
  Variação); vazia: "Nenhuma fonte encolheu na última coleta." Sem o resumo: `AvisoErro` no
  lugar das tabelas.
- `useTitulo('Sobre')`.

- [ ] **Step 1: Escreva o teste**

`site/src/paginas/Sobre.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA } from '../componentes/Alertas'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'

const SECOES = [
  'De onde vêm os dados',
  'Como ler um alerta',
  'Limitações conhecidas',
  'Privacidade e LGPD',
  'Baixar os dados',
  'Situação das fontes',
]

describe('página sobre', () => {
  it('seções fixas, aviso fixo e privacidade', () => {
    renderizarSite('/sobre')
    expect(screen.getByRole('heading', { level: 1, name: 'Sobre o Eleitorado' })).toBeInTheDocument()
    for (const titulo of SECOES) {
      expect(screen.getByRole('heading', { level: 2, name: titulo })).toBeInTheDocument()
    }
    expect(screen.getByText(AVISO_ALERTA)).toBeInTheDocument()
    expect(screen.getByText('O site não usa cookies, analytics nem fontes externas.')).toBeInTheDocument()
    expect(document.title).toBe('Sobre · Eleitorado')
  })

  it('links para baixar os dados', () => {
    renderizarSite('/sobre')
    expect(screen.getByRole('link', { name: 'Modelos de dados' })).toHaveAttribute(
      'href',
      'https://github.com/bonvenuto/eleitorado/blob/main/docs/modelos-de-dados.md',
    )
    expect(screen.getByRole('link', { name: 'Manifesto dos dados publicados' })).toHaveAttribute(
      'href',
      'https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/manifesto.json',
    )
  })

  it('situação das fontes', async () => {
    renderizarSite('/sobre')
    const tabela = await screen.findByRole('table', { name: 'Situação das fontes' })
    const [, camara, receita] = within(tabela).getAllByRole('row')
    expect(camara).toHaveTextContent('camara.cota')
    expect(camara).toHaveTextContent('diaria')
    expect(camara).toHaveTextContent('07/10/2026 às 07:40')
    expect(camara).toHaveTextContent('Em dia')
    expect(receita).toHaveTextContent('rfb.empresas')
    expect(receita).toHaveTextContent('nunca')
    expect(receita).toHaveTextContent('Com erro')
  })

  it('fontes que encolheram', async () => {
    renderizarSite('/sobre')
    const tabela = await screen.findByRole('table', { name: 'Fontes que encolheram' })
    for (const texto of ['camara.cota', '2015', '05/10/2026 às 08:00', '1.000', '850', '-15,0%']) {
      expect(tabela).toHaveTextContent(texto)
    }
  })

  it('nenhuma fonte encolheu', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), fontes_reduzidas: [] } })
    renderizarSite('/sobre')
    expect(await screen.findByText('Nenhuma fonte encolheu na última coleta.')).toBeInTheDocument()
  })

  it('sem o resumo, as seções fixas continuam', async () => {
    servir({ 'resumo.json': REDE })
    renderizarSite('/sobre')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Como ler um alerta' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Veja falhar**

Run: `cd site && npm test -- src/paginas/Sobre.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implemente** `site/src/paginas/Sobre.tsx` pelo comportamento acima.

- [ ] **Step 4: Veja passar**

Run: `cd site && npm test && npm run lint && npm run typecheck`
Expected: PASS; lint e tsc sem erro.

- [ ] **Step 5: Prova de mutação**

No mapa de situação, troque `erro: 'Com erro'` por `erro: 'Em dia'`. Run:
`npm test -- src/paginas/Sobre.test.tsx -t "situação das fontes"`. Expected: FAIL. Desfaça e
confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add site/src/paginas/Sobre.tsx site/src/paginas/Sobre.test.tsx
git commit -m "feat(site): página sobre com fontes, leitura dos alertas, LGPD e situação das fontes"
```

---

### Task 16: CI, documentação e verificação final

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `site/README.md`
- Modify: `AGENTS.md`, `docs/roteiro.md`

**Interfaces:**
- Consumes: os scripts do `site/package.json` (tarefa 1).

- [ ] **Step 1: Job `site` no CI**

Em `.github/workflows/ci.yml`, acrescente ao fim de `jobs:` (no mesmo nível de `testes:`):

```yaml
  site:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: site
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npx vite build
```

(O `npm run build` repetiria o `tsc`; o passo `typecheck` já roda antes. O `permissions:
contents: read` do topo vale para o job novo. Se a entrada `cache` tiver mudado no setup-node
v7, confira o `action.yml` da tag; em 2026-10-07 ela existia com `npm`, `yarn` e `pnpm`.)

- [ ] **Step 2: Documentação**

`site/README.md`:

````markdown
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
````

Em `AGENTS.md`:
- Em "O projeto", troque o item de `site/` por:

```markdown
- `site/`: o site público (Vite + React + TypeScript, `site/README.md`), publicado pelo
  Cloudflare Pages, e o contrato dos seus dados (`site/esquemas/`, JSON Schemas;
  `site/exemplos/`). Os modelos `dbt/models/site/` montam os arquivos e o `coletor site` os
  grava em `publico/site/`, que o `coletor publicar` envia ao R2.
```

- Em "Como trabalhamos", depois do bloco PowerShell do dbt, acrescente:

```markdown
Se o PR mexe em `site/`, também (em `site/`): `npm ci`, `npm run lint`, `npm run typecheck`,
`npm test` e `npm run build`. O CI roda isso no job `site`.
```

- Em "Convenções", no item "Mudança no formato de um arquivo do site", troque
  "(e o frontend, se ele usa o campo)" por "(e `site/src/tipos.ts` e as telas que usam o campo)".

Em `docs/roteiro.md`, no item 8 (Produto público), troque o parágrafo por:

```markdown
Spec em `docs/superpowers/specs/2026-10-07-site-publico-design.md`. Plano 10 (dados do site:
modelos `site_*`, `coletor site`, publicação incremental) em
`docs/superpowers/plans/2026-10-07-plano-10-dados-do-site.md`; plano 11 (frontend em `site/`,
Cloudflare Pages) em `docs/superpowers/plans/2026-10-07-plano-11-frontend-do-site.md`.
**Usuário:** criar o projeto no Cloudflare Pages, a regra de CORS do bucket R2 (spec, seção 9)
e decidir se o job `site` do CI entra no ruleset da `main`.
```

- [ ] **Step 3: Verificação completa**

Run (em `site/`):

```bash
npm ci && npm run lint && npm run typecheck && npm test && npm run build
ls dist dist/assets
grep -c "text-red" dist/assets/*.css
grep -rl "ANA EXEMPLO" dist || echo "sem dados de exemplo no build"
```

Expected: tudo verde; `dist/` com `index.html`, `_redirects`, `_headers`, `favicon.svg` e
`assets/` (JS, CSS e as `.woff2`); `0` para `text-red`; "sem dados de exemplo no build" (a
pasta `exemplos/` não entra no pacote; o texto `/exemplos` continua no JS, mas só é usado com
`DEV` verdadeiro). No protótipo, o JS saiu com ~540 KB (~180 KB em gzip, a maior parte do Plot e
do d3) e o Vite avisa que passou de 500 KB: é esperado nesta versão; não suba o
`chunkSizeWarningLimit` para esconder o aviso.

Na raiz do repositório (o PR não muda Python, mas o check `testes` continua obrigatório):

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

Expected: limpo e verde.

- [ ] **Step 4: Conferência no navegador**

Run: `cd site && npm run dev` e abra `http://localhost:5173` no Chromium (na nuvem, o do
Playwright em `/opt/pw-browsers`; uma captura por página serve de registro no PR).
Confira, com os dados de `exemplos/`:
- `/`: capa com gradiente, busca; digitar "exemplo" mostra ANA EXEMPLO e EMPRESA EXEMPLO LTDA;
  "11.222.333/0001-81" + Enter abre a empresa.
- `/parlamentar/camara-900001`, `/parlamentar/senado-900002`, `/empresa/11222333`, `/alertas`,
  `/sobre` e `/qualquer`: sem erro no console; gráficos em cinza com a barra em destaque branca;
  "Ver tabela" funciona com Tab + Enter; foco sempre visível.
- Largura de 375px (celular): navegação flutuante embaixo, a 16px das bordas; título da capa em
  ~40px; nada transborda na horizontal.
- `npm run build && npx vite preview`: as mesmas rotas abertas direto pela barra de endereço
  (o `vite preview` não lê `_redirects`; a volta para o `index.html` em rota profunda é
  conferida na prévia do Cloudflare Pages, depois do merge).

- [ ] **Step 5: Links oficiais**

No navegador, abra os endereços de `src/fontes.ts`, o link oficial de um deputado
(`https://www.camara.leg.br/deputados/204554`) e de um senador
(`https://www25.senado.leg.br/web/senadores/senador/-/perfil/5672`), e
`https://portaldatransparencia.gov.br/busca?termo=<um CNPJ real>`. Se algum endereço de
`fontes.ts` não abrir a página certa, corrija-o (e o teste). Registre o resultado no PR.

- [ ] **Step 6: Commit, push e PR**

```bash
git add .github/workflows/ci.yml site/README.md AGENTS.md docs/roteiro.md
git commit -m "ci: job site (lint, tsc, vitest, build); docs do frontend"
git push -u origin feat/site-frontend
```

Abra o PR para a `main` com o título "Site público: frontend (plano 11)" e um corpo que liste o
que entrou, as capturas do passo 4, o resultado do passo 5, qualquer versão trocada no
`package.json` e os passos do usuário abaixo. Expected: checks `testes` e `site` verdes. O merge
é do usuário.

## Depois do merge (usuário)

- **Cloudflare Pages** (spec, seção 9): projeto `eleitorado` com integração Git, diretório
  raiz `site`, comando `npm ci && npm run build`, saída `dist`, variável `NODE_VERSION=22`
  (ou `22.13.0` ou mais nova). Sem `VITE_DADOS_URL` (o padrão já é o R2). Nenhum token da
  Cloudflare no GitHub.
- **CORS do bucket R2:** `GET` e `HEAD` para `https://eleitorado.pages.dev`,
  `https://*.eleitorado.pages.dev` e `http://localhost:5173`.
- Na prévia do PR e depois em `https://eleitorado.pages.dev`:
  - abrir uma rota profunda direto (`/empresa/<raiz real>`) e conferir que o `_redirects`
    devolve o site;
  - conferir no console que a CSP não bloqueia nada (dados do R2, fotos, estilos do Plot);
  - abrir um parlamentar que não existe (`/parlamentar/camara-1`): deve aparecer a 404, e não
    "Dados indisponíveis" (o 404 do R2 precisa vir com os cabeçalhos de CORS; se não vier, o
    navegador vê falha de rede);
  - conferir que os JSON chegam com `Content-Encoding: gzip` e são lidos.
- Decidir se o job `site` entra no ruleset da `main` (spec, seção 8).
- Quando houver domínio próprio: mudar o `connect-src` de `site/public/_headers` (e o
  `PADRAO_DADOS_URL`, se o bucket passar a ser servido pelo domínio).
