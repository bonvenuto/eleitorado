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
