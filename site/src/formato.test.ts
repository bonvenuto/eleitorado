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
