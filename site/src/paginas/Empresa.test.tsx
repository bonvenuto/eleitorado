import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { BlocoEmpresas, Empresa } from '../tipos'

function blocoComEmpresa(): { bloco: BlocoEmpresas; empresa: Empresa } {
  const bloco = exemplo<BlocoEmpresas>('empresa/b_112.json')
  const empresa = bloco.empresas['11222333']
  if (!empresa) throw new Error('exemplo sem a empresa 11222333')
  return { bloco, empresa }
}

function valorDe(regiao: HTMLElement, rotulo: string): string | null {
  return within(regiao).getByText(rotulo).nextElementSibling?.textContent ?? null
}

describe('página da empresa', () => {
  it('cadastro da Receita, com a contagem de sócios e sem os nomes', async () => {
    renderizarSite('/empresa/11222333')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
    expect(screen.getByText('CNPJ da matriz 11.222.333/0001-81')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver no Portal da Transparência' })).toHaveAttribute(
      'href',
      'https://portaldatransparencia.gov.br/busca?termo=11222333000181',
    )
    const cadastro = screen.getByRole('region', { name: 'Cadastro na Receita Federal' })
    expect(valorDe(cadastro, 'Situação')).toBe('ATIVA desde 02/04/2018')
    expect(valorDe(cadastro, 'Abertura')).toBe('02/04/2018')
    expect(valorDe(cadastro, 'Porte')).toBe('MICRO EMPRESA')
    expect(valorDe(cadastro, 'Capital social')).toMatch(/R\$\s50\.000,00/)
    expect(valorDe(cadastro, 'Município')).toBe('BRASILIA/DF')
    expect(valorDe(cadastro, 'Optante pelo Simples')).toBe('Sim')
    expect(valorDe(cadastro, 'MEI')).toBe('Não')
    expect(valorDe(cadastro, 'Estabelecimentos')).toBe('1')
    expect(valorDe(cadastro, 'Sócios')).toBe('2 (os nomes não são publicados)')
    expect(cadastro).toHaveTextContent('Cadastro da Receita Federal de setembro de 2026.')
    await waitFor(() => expect(document.title).toBe('EMPRESA EXEMPLO LTDA · Eleitorado'))
  })

  it('o que recebeu: cota, contratos e licitações; emendas vazias', async () => {
    renderizarSite('/empresa/11222333')
    const recebeu = await screen.findByRole('region', { name: 'O que recebeu do governo federal' })
    const cota = within(recebeu).getByRole('table', { name: 'Cota parlamentar por parlamentar' })
    expect(within(cota).getByRole('link', { name: 'ANA EXEMPLO' })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(cota).toHaveTextContent('R$ 1.200,00')
    expect(recebeu).toHaveTextContent('Nenhum pagamento de emenda nos dados.')
    const contratos = within(recebeu).getByRole('table', { name: 'Contratos por órgão' })
    expect(contratos).toHaveTextContent('MINISTERIO EXEMPLO')
    expect(contratos).toHaveTextContent('R$ 350.000,00')
    expect(recebeu).toHaveTextContent('2 contratos')
    expect(recebeu).toHaveTextContent('1 licitação vencida')
  })

  it('emendas por autor, com link só quando o autor é parlamentar', async () => {
    const { bloco, empresa } = blocoComEmpresa()
    empresa.emendas = {
      total_pago: 5000,
      autores: [
        { autor: 'ANA EXEMPLO', parlamentar_id: 'camara:900001', pago: 3000 },
        { autor: 'BANCADA DO DF', parlamentar_id: null, pago: 2000 },
      ],
    }
    servir({ 'empresa/b_112.json': bloco })
    renderizarSite('/empresa/11222333')
    const emendas = await screen.findByRole('table', { name: 'Emendas por autor' })
    expect(within(emendas).getByRole('link', { name: 'ANA EXEMPLO' })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(emendas).toHaveTextContent('BANCADA DO DF')
    expect(within(emendas).queryByRole('link', { name: 'BANCADA DO DF' })).toBeNull()
  })

  it('sanções em grupos, sem grupo vazio', async () => {
    renderizarSite('/empresa/11222333')
    const sancoes = await screen.findByRole('region', { name: 'Sanções (CEIS e CNEP)' })
    expect(within(sancoes).getByRole('heading', { name: 'Vigentes' })).toBeInTheDocument()
    expect(within(sancoes).queryByRole('heading', { name: 'Encerradas' })).toBeNull()
    for (const texto of ['CEIS', 'MINISTERIO EXEMPLO', '01/03/2025 a 01/03/2027']) {
      expect(sancoes).toHaveTextContent(texto)
    }
  })

  it('sem sanções', async () => {
    const { bloco, empresa } = blocoComEmpresa()
    empresa.sancoes = []
    servir({ 'empresa/b_112.json': bloco })
    renderizarSite('/empresa/11222333')
    expect(
      await screen.findByText('Nenhuma sanção no CEIS ou no CNEP nos dados.'),
    ).toBeInTheDocument()
  })

  it('alertas da empresa: fortes e o fraco à parte', async () => {
    renderizarSite('/empresa/11222333')
    const alertas = await screen.findByRole('region', { name: 'Alertas' })
    expect(within(alertas).getAllByRole('article')).toHaveLength(3)
    expect(within(alertas).getByRole('region', { name: 'Correspondência fraca' })).toBeInTheDocument()
    expect(within(alertas).getByRole('link', { name: 'EMPREITEIRA MODELO SA' })).toHaveAttribute(
      'href',
      '/empresa/44555666',
    )
  })

  it('raiz em minúsculas vai para o endereço canônico (CNPJ alfanumérico)', async () => {
    const { empresa } = blocoComEmpresa()
    servir({ 'empresa/b_1AB.json': { esquema: 1, bloco: '1AB', empresas: { '1AB2C3D4': empresa } } })
    const { local } = renderizarSite('/empresa/1ab2c3d4')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
    expect(local()).toBe('/empresa/1AB2C3D4')
  })

  it.each(['11222399', '99999999', 'abc'])('empresa %s fora dos dados: 404', async (raiz) => {
    renderizarSite(`/empresa/${raiz}`)
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('falha de rede: tentar de novo', async () => {
    servir({ 'empresa/b_112.json': REDE })
    const { usuario } = renderizarSite('/empresa/11222333')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'EMPRESA EXEMPLO LTDA' }),
    ).toBeInTheDocument()
  })
})
