import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GraficoBarras } from './GraficoBarras'

const barras = [
  { rotulo: '2025', valor: 300 },
  { rotulo: '2026', valor: 1200 },
]

describe('gráfico de barras', () => {
  it('desenha o gráfico e esconde a tabela até o clique', async () => {
    const usuario = userEvent.setup()
    const { container } = render(
      <GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} destaque="2026" />,
    )
    expect(screen.getByRole('img', { name: /Cota por ano/ })).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeNull()
    expect(screen.queryByRole('table')).toBeNull()

    const botao = screen.getByRole('button', { name: 'Ver tabela: Cota por ano' })
    expect(botao).toHaveAttribute('aria-expanded', 'false')
    await usuario.click(botao)
    expect(botao).toHaveAttribute('aria-expanded', 'true')

    const tabela = screen.getByRole('table', { name: 'Cota por ano' })
    const linhas = within(tabela).getAllByRole('row')
    expect(linhas[0]).toHaveTextContent('AnoValor')
    expect(linhas[1]).toHaveTextContent('2025R$ 300,00')
    expect(linhas[2]).toHaveTextContent('2026R$ 1.200,00')
  })

  it('funciona pelo teclado', async () => {
    const usuario = userEvent.setup()
    render(<GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} />)
    await usuario.tab()
    expect(screen.getByRole('button', { name: /Ver tabela/ })).toHaveFocus()
    await usuario.keyboard('{Enter}')
    expect(screen.getByRole('table', { name: 'Cota por ano' })).toBeInTheDocument()
  })

  it('a barra em destaque sai em branco e as outras em cinza', () => {
    const { container } = render(
      <GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={barras} destaque="2026" />,
    )
    const cores = [...container.querySelectorAll('rect')].map((r) => r.getAttribute('fill'))
    expect(cores).toContain('#ffffff')
    expect(cores).toContain('#b2b2b2')
  })

  it('sem dados', () => {
    render(<GraficoBarras titulo="Cota por ano" rotuloColuna="Ano" barras={[]} />)
    expect(screen.getByText('Sem dados.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
