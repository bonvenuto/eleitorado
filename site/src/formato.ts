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
