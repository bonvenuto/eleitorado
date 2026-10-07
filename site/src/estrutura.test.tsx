import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { Rotas } from './Rotas'

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ler = (relativo: string) => readFileSync(path.join(SITE, relativo), 'utf-8')

describe('estrutura do site', () => {
  it('a página base declara pt-BR', () => {
    expect(ler('index.html')).toMatch(/<html lang="pt-BR">/)
  })

  it('o HTML não carrega nada de fora', () => {
    expect(ler('index.html')).not.toMatch(/(src|href)="(https?:)?\/\//)
  })

  it('toda rota volta para o index.html (SPA no Cloudflare Pages)', () => {
    expect(ler('public/_redirects')).toBe('/* /index.html 200\n')
  })

  it('a aplicação renderiza', () => {
    render(
      <MemoryRouter>
        <Rotas />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Pular para o conteúdo' })).toBeInTheDocument()
  })
})
