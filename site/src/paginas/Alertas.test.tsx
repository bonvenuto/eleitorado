import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AVISO_ALERTA } from '../componentes/Alertas'
import { caminhosPedidos, exemplo, servir } from '../teste/exemplos'
import { renderizarSite } from '../teste/rotas'
import type { PaginaAlertas, Resumo } from '../tipos'

describe('página de alertas', () => {
  it('explica cada regra, na ordem', async () => {
    renderizarSite('/alertas')
    const regras = await screen.findByRole('region', { name: 'Como cada alerta é gerado' })
    const titulos = within(regras)
      .getAllByRole('heading', { level: 3 })
      .map((h) => h.textContent)
    expect(titulos).toEqual(
      exemplo<Resumo>('resumo.json')
        .alerta_tipos.sort((a, b) => a.ordem - b.ordem)
        .map((t) => t.titulo),
    )
    expect(regras).toHaveTextContent('O parlamentar foi reembolsado pela cota')
    expect(regras).toHaveTextContent('Deputados são identificados pelo nome e por parte do CPF')
  })

  it('sem tipo na query: o primeiro com alertas, marcado no filtro', async () => {
    renderizarSite('/alertas')
    const filtro = await screen.findByRole('navigation', { name: 'Tipos de alerta' })
    const atual = within(filtro).getByRole('link', { current: 'page' })
    expect(atual).toHaveTextContent('Cota paga a fornecedor sancionado')
    expect(atual).toHaveAttribute('href', '/alertas?tipo=cota_fornecedor_sancionado')
    const cartao = await screen.findByRole('article')
    expect(cartao).toHaveTextContent('Despesa de cota com fornecedor sancionado no CEIS')
    expect(within(cartao).getByText(AVISO_ALERTA)).toBeInTheDocument()
    expect(screen.getByText('Página 1 de 1')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Próxima página' })).toBeNull()
    expect(document.title).toBe('Alertas · Eleitorado')
  })

  it('tipo sem alertas: avisa sem baixar arquivo', async () => {
    renderizarSite('/alertas?tipo=cota_documento_invalido')
    expect(
      await screen.findByText('Nenhum alerta deste tipo nos dados de 07/10/2026 às 08:02.'),
    ).toBeInTheDocument()
    expect(caminhosPedidos().some((c) => c.startsWith('alertas/'))).toBe(false)
  })

  it('tipo desconhecido: 404', async () => {
    renderizarSite('/alertas?tipo=inventado')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('página além da última: 404', async () => {
    renderizarSite('/alertas?tipo=cota_fornecedor_sancionado&pagina=2')
    expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  })

  it('paginação', async () => {
    const pagina = exemplo<PaginaAlertas>('alertas/cota_fornecedor_sancionado/1.json')
    servir({
      'alertas/cota_fornecedor_sancionado/1.json': { ...pagina, paginas: 3, total: 1200 },
      'alertas/cota_fornecedor_sancionado/2.json': { ...pagina, pagina: 2, paginas: 3, total: 1200 },
    })
    const { usuario } = renderizarSite('/alertas?tipo=cota_fornecedor_sancionado')
    expect(await screen.findByText('Página 1 de 3')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Página anterior' })).toBeNull()
    await usuario.click(screen.getByRole('link', { name: 'Próxima página' }))
    expect(await screen.findByText('Página 2 de 3')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Página anterior' })).toHaveAttribute(
      'href',
      '/alertas?tipo=cota_fornecedor_sancionado',
    )
    expect(screen.getByRole('link', { name: 'Próxima página' })).toHaveAttribute(
      'href',
      '/alertas?tipo=cota_fornecedor_sancionado&pagina=3',
    )
  })

  it('trocar de tipo pelo filtro', async () => {
    const resumo = exemplo<Resumo>('resumo.json')
    const alerta = resumo.alertas_recentes.find((a) => a.tipo === 'licitacao_socios_em_comum')
    servir({
      'alertas/licitacao_socios_em_comum/1.json': {
        esquema: 1,
        tipo: 'licitacao_socios_em_comum',
        pagina: 1,
        paginas: 1,
        total: 1,
        alertas: [alerta],
      },
    })
    const { usuario, local } = renderizarSite('/alertas')
    const filtro = await screen.findByRole('navigation', { name: 'Tipos de alerta' })
    await usuario.click(within(filtro).getByRole('link', { name: /Concorrentes com sócios em comum/ }))
    expect(local()).toBe('/alertas?tipo=licitacao_socios_em_comum')
    expect(await screen.findByText(/Participantes da mesma licitação/)).toBeInTheDocument()
  })
})
