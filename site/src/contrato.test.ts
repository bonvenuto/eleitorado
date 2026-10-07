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
