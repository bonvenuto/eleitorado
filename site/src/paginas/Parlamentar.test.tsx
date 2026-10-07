import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA, AVISO_HOMONIMO } from '../componentes/Alertas'
import { REDE, caminhosPedidos, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { ArquivoParlamentar } from '../tipos'

describe('página do parlamentar', () => {
  it('cabeçalho com partido, UF, casa e link oficial', async () => {
    renderizarSite('/parlamentar/camara-900001')
    expect(await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })).toBeInTheDocument()
    expect(screen.getByText('PEX · DF · Câmara dos Deputados')).toBeInTheDocument()
    expect(screen.getByText('Legislaturas: 56 e 57')).toBeInTheDocument()
    const oficial = screen.getByRole('link', { name: 'Página oficial na Câmara dos Deputados' })
    expect(oficial).toHaveAttribute('href', 'https://www.camara.leg.br/deputados/900001')
    expect(oficial).toHaveAttribute('rel', 'noopener noreferrer')
    await waitFor(() => expect(document.title).toBe('ANA EXEMPLO · Eleitorado'))
  })

  it('sem foto no arquivo, sem imagem', async () => {
    renderizarSite('/parlamentar/camara-900001')
    await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })
    expect(screen.queryByRole('img', { name: /Foto de/ })).toBeNull()
  })

  it('foto do Senado em http vira https; foto de outro site não aparece', async () => {
    const arquivo = exemplo<ArquivoParlamentar>('parlamentar/senado-900002.json')
    arquivo.parlamentar.foto = 'http://www.senado.leg.br/senadores/img/fotos-oficiais/senador900002.jpg'
    servir({ 'parlamentar/senado-900002.json': arquivo })
    renderizarSite('/parlamentar/senado-900002')
    expect(await screen.findByRole('img', { name: 'Foto de JOAO MODELO' })).toHaveAttribute(
      'src',
      'https://www.senado.leg.br/senadores/img/fotos-oficiais/senador900002.jpg',
    )
  })

  it('cota: total, gráficos com tabela e maiores fornecedores', async () => {
    const { usuario } = renderizarSite('/parlamentar/camara-900001')
    const cota = await screen.findByRole('region', { name: 'Cota parlamentar' })
    expect(cota).toHaveTextContent('R$ 1.500,00')
    await usuario.click(within(cota).getByRole('button', { name: 'Ver tabela: Cota por ano' }))
    expect(within(cota).getByRole('table', { name: 'Cota por ano' })).toHaveTextContent(
      '2026R$ 1.200,00',
    )
    expect(
      within(cota).getByRole('button', { name: 'Ver tabela: Cota por categoria' }),
    ).toBeInTheDocument()
    const fornecedores = within(cota).getByRole('table', { name: 'Maiores fornecedores' })
    expect(within(fornecedores).getByRole('link', { name: 'EMPRESA EXEMPLO LTDA' })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    expect(fornecedores).toHaveTextContent('11.222.333/0001-81')
    expect(fornecedores).toHaveTextContent('***.456.789-**')
    expect(fornecedores).toHaveTextContent('MARIA EXEMPLO')
    expect(within(fornecedores).queryByRole('link', { name: 'MARIA EXEMPLO' })).toBeNull()
  })

  it('emendas: total pago, por ano e maiores favorecidos', async () => {
    renderizarSite('/parlamentar/camara-900001')
    const emendas = await screen.findByRole('region', { name: 'Emendas parlamentares' })
    expect(emendas).toHaveTextContent('R$ 250.000,00')
    expect(
      within(emendas).getByRole('button', { name: 'Ver tabela: Emendas pagas por ano' }),
    ).toBeInTheDocument()
    const favorecidos = within(emendas).getByRole('table', { name: 'Maiores favorecidos' })
    expect(within(favorecidos).getByRole('link', { name: 'MUNICIPIO DE EXEMPLO' })).toHaveAttribute(
      'href',
      '/empresa/99888777',
    )
  })

  it('alertas do parlamentar, com o aviso fixo', async () => {
    renderizarSite('/parlamentar/camara-900001')
    const alertas = await screen.findByRole('region', { name: 'Alertas' })
    expect(within(within(alertas).getByRole('article')).getByText(AVISO_ALERTA)).toBeInTheDocument()
  })

  it('senador sem cota nem emendas; alerta fraco à parte', async () => {
    renderizarSite('/parlamentar/senado-900002')
    expect(await screen.findByText('Nenhuma despesa de cota nos dados.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma emenda paga nos dados.')).toBeInTheDocument()
    expect(screen.getByText('PMO · SP · Senado Federal')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Página oficial no Senado Federal' })).toBeInTheDocument()
    const grupo = screen.getByRole('region', { name: 'Correspondência fraca' })
    expect(within(grupo).getByText(AVISO_HOMONIMO)).toBeInTheDocument()
  })

  it('parlamentar que não está nos dados: 404', async () => {
    renderizarSite('/parlamentar/camara-1')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('endereço inválido: 404 sem baixar arquivo de parlamentar', async () => {
    renderizarSite('/parlamentar/qualquer-coisa')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
    expect(caminhosPedidos().filter((c) => c.startsWith('parlamentar/'))).toEqual([])
  })

  it('falha de rede: tentar de novo', async () => {
    servir({ 'parlamentar/camara-900001.json': REDE })
    const { usuario } = renderizarSite('/parlamentar/camara-900001')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'ANA EXEMPLO' })).toBeInTheDocument()
  })
})
