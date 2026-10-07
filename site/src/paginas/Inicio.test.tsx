import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA } from '../componentes/Alertas'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'

describe('página inicial', () => {
  it('capa com a busca, mesmo antes do resumo', () => {
    renderizarSite('/')
    expect(screen.getByRole('heading', { level: 1, name: 'Para onde vai o dinheiro público' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Buscar parlamentar, empresa ou CNPJ' })).toBeInTheDocument()
    expect(document.title).toBe('Eleitorado')
  })

  it('números gerais', async () => {
    renderizarSite('/')
    const numeros = await screen.findByRole('region', { name: 'Números gerais' })
    for (const texto of [
      'Cota parlamentar',
      'R$ 1,5 mil',
      'Emendas pagas',
      'R$ 250 mil',
      'Contratos federais',
      'R$ 350 mil',
      'Parlamentares',
      'Empresas',
    ]) {
      expect(numeros).toHaveTextContent(texto)
    }
  })

  it('alertas por tipo, na ordem, com link e quantidade', async () => {
    renderizarSite('/')
    const tipos = await screen.findByRole('region', { name: 'Alertas por tipo' })
    const links = within(tipos).getAllByRole('link')
    expect(links).toHaveLength(9)
    expect(links[0]).toHaveTextContent('Cota paga a fornecedor sancionado')
    expect(links[0]).toHaveTextContent('1 alerta')
    expect(links[0]).toHaveAttribute('href', '/alertas?tipo=cota_fornecedor_sancionado')
    expect(links[1]).toHaveTextContent('Cota com CPF ou CNPJ inválido')
    expect(links[1]).toHaveTextContent('0 alertas')
    expect(links[8]).toHaveAttribute('href', '/alertas?tipo=parlamentar_socio_fornecedor')
  })

  it('a ordem vem do campo ordem, não da posição no arquivo', async () => {
    const resumo = exemplo<{ alerta_tipos: unknown[] }>('resumo.json')
    servir({ 'resumo.json': { ...resumo, alerta_tipos: [...resumo.alerta_tipos].reverse() } })
    renderizarSite('/')
    const tipos = await screen.findByRole('region', { name: 'Alertas por tipo' })
    expect(within(tipos).getAllByRole('link')[0]).toHaveTextContent('Cota paga a fornecedor sancionado')
  })

  it('alertas recentes, todos com o aviso fixo', async () => {
    renderizarSite('/')
    const recentes = await screen.findByRole('region', { name: 'Alertas recentes' })
    const cartoes = within(recentes).getAllByRole('article')
    expect(cartoes).toHaveLength(2)
    for (const cartao of cartoes) expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
    expect(within(recentes).getByRole('link', { name: 'Ver todos os alertas' })).toHaveAttribute(
      'href',
      '/alertas',
    )
  })

  it('data da atualização e até quando vai cada fonte', async () => {
    renderizarSite('/')
    expect(await screen.findByText('Dados atualizados em 07/10/2026 às 08:02.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Cota até 01/09/2026, emendas até 03/10/2026, contratos até 05/10/2026; Receita Federal: setembro de 2026.',
      ),
    ).toBeInTheDocument()
  })

  it('sem o resumo, a busca continua e o resto avisa', async () => {
    servir({ 'resumo.json': REDE })
    renderizarSite('/')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
  })

  it('esquema novo: avisa que o site precisa ser atualizado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    renderizarSite('/')
    expect(await screen.findByText(/precisa ser atualizado/)).toBeInTheDocument()
  })
})
