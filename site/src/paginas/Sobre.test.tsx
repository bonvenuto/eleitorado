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
