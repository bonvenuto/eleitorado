import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REDE, servir } from '../teste/exemplos'
import { renderizarComRotas } from '../teste/rotas'
import { CaixaBusca } from './CaixaBusca'

function preparar() {
  const tela = renderizarComRotas(<CaixaBusca />)
  const caixa = screen.getByRole('searchbox', { name: 'Buscar parlamentar, empresa ou CNPJ' })
  return { ...tela, caixa }
}

describe('caixa de busca', () => {
  it('acha parlamentar pelo nome', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ana')
    const lista = await screen.findByRole('list', { name: 'Parlamentares encontrados' })
    expect(within(lista).getByRole('link', { name: /ANA EXEMPLO/ })).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
  })

  it('acha parlamentar e empresa pela mesma palavra, com acento', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'exêmplo')
    const empresas = await screen.findByRole('list', { name: 'Empresas encontradas' })
    expect(within(empresas).getByRole('link', { name: /EMPRESA EXEMPLO LTDA/ })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    const parlamentares = screen.getByRole('list', { name: 'Parlamentares encontrados' })
    expect(within(parlamentares).getByRole('link', { name: /ANA EXEMPLO/ })).toBeInTheDocument()
  })

  it('filtra por todas as palavras', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'empresa exemplo')
    const empresas = await screen.findByRole('list', { name: 'Empresas encontradas' })
    expect(within(empresas).getAllByRole('link').map((l) => l.textContent)).toEqual([
      expect.stringContaining('EMPRESA EXEMPLO LTDA'),
    ])
  })

  it('bloco subdividido: com 3 letras pede mais uma; com 4 mostra o bloco menor', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'con')
    expect(await screen.findByRole('link', { name: /CON ENGENHARIA SA/ })).toBeInTheDocument()
    expect(screen.getByText(/digite mais uma letra/i)).toBeInTheDocument()
    await usuario.type(caixa, 's')
    expect(await screen.findByRole('link', { name: /CONSTRUTORA EXEMPLO LTDA/ })).toBeInTheDocument()
    expect(screen.queryByText(/digite mais uma letra/i)).toBeNull()
  })

  it.each([
    ['11.222.333/0001-81', '/empresa/11222333'],
    ['11222333', '/empresa/11222333'],
    ['1ab2c3d4', '/empresa/1AB2C3D4'],
  ])('CNPJ %s com Enter vai direto à empresa', async (cnpj, rota) => {
    const { usuario, caixa, local } = preparar()
    await usuario.type(caixa, `${cnpj}{Enter}`)
    expect(local()).toBe(rota)
  })

  it('CNPJ mostra o link da empresa antes do Enter', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, '11222333')
    expect(screen.getByRole('link', { name: /Ver a empresa de CNPJ 11\.222\.333/ })).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
  })

  it('explica as palavras comuns', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ltda')
    expect(await screen.findByText(/palavras comuns/i)).toBeInTheDocument()
  })

  it('avisa quando não acha nada', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'xyz')
    expect(await screen.findByText('Nenhum resultado para “xyz”.')).toBeInTheDocument()
  })

  it('pede 3 letras', async () => {
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ex')
    expect(screen.getByText('Digite pelo menos 3 letras.')).toBeInTheDocument()
  })

  it('falha de rede: avisa e tenta de novo', async () => {
    servir({ 'busca/parlamentares.json': REDE })
    const { usuario, caixa } = preparar()
    await usuario.type(caixa, 'ana')
    expect(await screen.findByText('Busca indisponível no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('link', { name: /ANA EXEMPLO/ })).toBeInTheDocument()
  })
})
