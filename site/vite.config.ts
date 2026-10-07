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
