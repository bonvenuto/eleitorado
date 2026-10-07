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
