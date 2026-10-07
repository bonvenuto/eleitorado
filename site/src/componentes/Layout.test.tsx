import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { carregarResumo } from '../dados'
import { REDE, exemplo, servir } from '../teste/exemplos'
import { renderizarComRotas, renderizarSite } from '../teste/rotas'
import { useDados } from '../useDados'
import { AvisoErro, Carregando } from './Estados'
import { AvisoDadosAntigos } from './FaixaDesatualizada'

function TesteResumo() {
  const estado = useDados('resumo', carregarResumo)
  if (estado.estado === 'carregando') return <Carregando />
  if (estado.estado === 'erro') {
    return <AvisoErro erro={estado.erro} tentarDeNovo={estado.tentarDeNovo} />
  }
  return <p>gerado em {estado.dados.gerado_em}</p>
}

describe('layout', () => {
  it('navegação principal com a página atual marcada', () => {
    renderizarSite('/sobre')
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getByRole('link', { name: 'Início' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Alertas' })).toHaveAttribute('href', '/alertas')
    const sobre = within(nav).getByRole('link', { name: 'Sobre' })
    expect(sobre).toHaveAttribute('href', '/sobre')
    expect(sobre).toHaveAttribute('aria-current', 'page')
  })

  it('a primeira tecla Tab vai para "Pular para o conteúdo"', async () => {
    const { usuario } = renderizarSite('/sobre')
    await usuario.tab()
    const pular = screen.getByRole('link', { name: 'Pular para o conteúdo' })
    expect(pular).toHaveFocus()
    expect(pular).toHaveAttribute('href', '#conteudo')
    expect(document.getElementById('conteudo')?.tagName).toBe('MAIN')
  })

  it('rota que não existe: 404 com a busca', () => {
    renderizarSite('/nada/aqui')
    expect(screen.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao início' })).toHaveAttribute('href', '/')
    expect(document.title).toBe('Página não encontrada · Eleitorado')
  })
})

describe('dados antigos', () => {
  const gerado = '2026-10-07T11:02:13Z'

  it('mostra a faixa com mais de 3 dias', () => {
    render(<AvisoDadosAntigos geradoEm={gerado} agora={new Date('2026-10-11T12:00:00Z')} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Atenção: os dados não são atualizados desde 07/10/2026 às 08:02.',
    )
  })

  it('não mostra nada com dados de ontem', () => {
    const { container } = render(
      <AvisoDadosAntigos geradoEm={gerado} agora={new Date('2026-10-08T12:00:00Z')} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('a faixa aparece no site quando o resumo é velho', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-20T12:00:00Z'))
    renderizarSite('/sobre')
    expect(await screen.findByText(/os dados não são atualizados desde 07\/10\/2026/)).toBeInTheDocument()
  })
})

describe('estados de erro', () => {
  it('rede: avisa e tenta de novo', async () => {
    servir({ 'resumo.json': REDE })
    const { usuario } = renderizarComRotas(<TesteResumo />)
    expect(screen.getByRole('status')).toHaveTextContent('Carregando…')
    expect(await screen.findByText('Dados indisponíveis no momento.')).toBeInTheDocument()
    servir()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByText('gerado em 2026-10-07T11:02:13Z')).toBeInTheDocument()
  })

  it('esquema diferente: o site precisa ser atualizado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    renderizarComRotas(<TesteResumo />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/precisa ser atualizado/)
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).toBeNull()
  })

  it('não encontrado: a página 404', async () => {
    servir({ 'resumo.json': 404 })
    renderizarComRotas(<TesteResumo />)
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })
})
