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
