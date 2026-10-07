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
