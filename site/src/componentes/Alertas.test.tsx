import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { exemplo } from '../teste/exemplos'
import { renderizarComRotas } from '../teste/rotas'
import type { BlocoEmpresas, Resumo } from '../tipos'
import { AVISO_ALERTA, AVISO_HOMONIMO, ListaAlertas } from './Alertas'

const resumo = exemplo<Resumo>('resumo.json')
const empresa = exemplo<BlocoEmpresas>('empresa/b_112.json').empresas['11222333']
if (!empresa) throw new Error('exemplo sem a empresa 11222333')
const { itens } = empresa.alertas

function renderizar(props: Partial<Parameters<typeof ListaAlertas>[0]> = {}) {
  return renderizarComRotas(
    <ListaAlertas
      alertas={itens}
      total={itens.length}
      tipos={resumo.alerta_tipos}
      geradoEm={resumo.gerado_em}
      {...props}
    />,
  )
}

describe('lista de alertas', () => {
  it('todo alerta traz o aviso fixo, a fonte e a data dos dados', () => {
    renderizar()
    const cartoes = screen.getAllByRole('article')
    expect(cartoes).toHaveLength(3)
    for (const cartao of cartoes) {
      expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
      expect(within(cartao).getByRole('link', { name: /Fonte oficial/ })).toHaveAttribute(
        'href',
        expect.stringMatching(/^https:\/\//),
      )
      expect(cartao).toHaveTextContent('Dados de 07/10/2026 às 08:02')
    }
  })

  it('o aviso fixo diz que é indício e não acusação', () => {
    expect(AVISO_ALERTA).toBe(
      'Indício gerado automaticamente a partir de dados públicos; não é acusação nem constatação de irregularidade.',
    )
  })

  it('título, explicação e cautela vêm do resumo, não do código', () => {
    const tipos = resumo.alerta_tipos.map((t) =>
      t.tipo === 'cota_fornecedor_sancionado'
        ? { ...t, titulo: 'TÍTULO DE TESTE', explicacao: 'EXPLICAÇÃO DE TESTE', cautela: 'CAUTELA DE TESTE' }
        : t,
    )
    renderizar({ tipos })
    const cartao = screen.getByRole('article', { name: 'TÍTULO DE TESTE' })
    expect(within(cartao).getByText('EXPLICAÇÃO DE TESTE')).toBeInTheDocument()
    expect(within(cartao).getByText('CAUTELA DE TESTE')).toBeInTheDocument()
    expect(cartao).toHaveTextContent(/Regra: Despesa de cota com fornecedor/)
  })

  it('fraca fica num grupo separado, depois das fortes, com o aviso de homônimo', () => {
    renderizar()
    const fortes = screen.getByRole('list', { name: 'Alertas' })
    const grupo = screen.getByRole('region', { name: 'Correspondência fraca' })
    expect(within(fortes).getAllByRole('article')).toHaveLength(2)
    const fraca = within(grupo).getByRole('article')
    expect(fraca).toHaveTextContent('JOAO MODELO')
    expect(within(fraca).getByText(AVISO_HOMONIMO)).toBeInTheDocument()
    expect(within(fortes).queryByText(AVISO_HOMONIMO)).toBeNull()
    expect(fortes.compareDocumentPosition(grupo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('liga o parlamentar e as duas empresas', () => {
    renderizar()
    expect(screen.getAllByRole('link', { name: 'ANA EXEMPLO' })[0]).toHaveAttribute(
      'href',
      '/parlamentar/camara-900001',
    )
    expect(screen.getAllByRole('link', { name: 'EMPRESA EXEMPLO LTDA' })[0]).toHaveAttribute(
      'href',
      '/empresa/11222333',
    )
    expect(screen.getByRole('link', { name: 'EMPREITEIRA MODELO SA' })).toHaveAttribute(
      'href',
      '/empresa/44555666',
    )
  })

  it('data e valor do fato em pt-BR', () => {
    renderizar()
    const cartao = screen.getByRole('article', { name: 'Cota paga a fornecedor sancionado' })
    expect(cartao).toHaveTextContent('14/08/2026')
    expect(cartao).toHaveTextContent('R$ 1.200,00')
  })

  it('avisa quando há mais alertas do que os mostrados', () => {
    renderizar({ total: 250 })
    expect(screen.getByText(/Mostrando os 3 mais recentes de 250 alertas/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver todos os alertas' })).toHaveAttribute('href', '/alertas')
  })

  it('sem o aviso de corte quando verTodos é false', () => {
    renderizar({ total: 250, verTodos: false })
    expect(screen.queryByText(/mais recentes de/)).toBeNull()
  })

  it('lista vazia', () => {
    renderizar({ alertas: [], total: 0 })
    expect(screen.getByText('Nenhum alerta automático.')).toBeInTheDocument()
  })
})
