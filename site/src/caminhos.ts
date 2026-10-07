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
