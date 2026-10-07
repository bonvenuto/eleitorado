import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { SITE, arquivosDoCodigo } from './teste/arquivos'

const css = readFileSync(path.join(SITE, 'src', 'index.css'), 'utf-8')

function cores(): Map<string, string> {
  const mapa = new Map<string, string>()
  for (const [, nome, valor] of css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    if (nome && valor) mapa.set(nome, valor.toLowerCase())
  }
  return mapa
}

function cor(nome: string): string {
  const valor = cores().get(nome)
  if (!valor) throw new Error(`a cor ${nome} não está no tema`)
  return valor
}

function canais(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number]
}

function luminancia(hex: string): number {
  const [r, g, b] = canais(hex).map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  ) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a: string, b: string): number {
  const [clara, escura] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number]
  return (clara + 0.05) / (escura + 0.05)
}

function matizESaturacao(hex: string): { matiz: number; saturacao: number } {
  const [r, g, b] = canais(hex)
  const maior = Math.max(r, g, b)
  const menor = Math.min(r, g, b)
  const delta = maior - menor
  const luz = (maior + menor) / 2
  const saturacao = delta === 0 ? 0 : delta / (1 - Math.abs(2 * luz - 1))
  let matiz = 0
  if (delta !== 0) {
    if (maior === r) matiz = 60 * (((g - b) / delta) % 6)
    else if (maior === g) matiz = 60 * ((b - r) / delta + 2)
    else matiz = 60 * ((r - g) / delta + 4)
  }
  return { matiz: (matiz + 360) % 360, saturacao }
}

describe('tema (site/DESIGN.md)', () => {
  it('a paleta padrão do Tailwind sai inteira', () => {
    expect(css).toMatch(/--color-\*:\s*initial;/)
  })

  it('tem os tokens do DESIGN.md e o âmbar de alerta', () => {
    expect(cor('void-canvas')).toBe('#0a0a0a')
    expect(cor('graphite')).toBe('#161616')
    expect(cor('bone')).toBe('#ededed')
    expect(cor('ash')).toBe('#c2c2c2')
    expect(cor('slate')).toBe('#686868')
    expect(cor('alerta')).toBe('#f2a65a')
  })

  it('nenhuma cor do tema é vermelha', () => {
    for (const [nome, valor] of cores()) {
      const { matiz, saturacao } = matizESaturacao(valor)
      const vermelha = saturacao > 0.3 && (matiz < 15 || matiz >= 345)
      expect(vermelha, `${nome}: ${valor}`).toBe(false)
    }
  })

  it.each([
    ['bone', 'void-canvas'],
    ['bone', 'graphite'],
    ['ash', 'void-canvas'],
    ['ash', 'graphite'],
    ['alerta', 'void-canvas'],
    ['alerta', 'graphite'],
    ['graphite', 'snow-white'],
    ['snow-white', 'capa-inicio'],
    ['snow-white', 'capa-fim'],
    ['bone', 'capa-inicio'],
    ['bone', 'capa-fim'],
  ])('texto %s sobre %s tem contraste AA (4,5:1)', (texto, fundo) => {
    expect(contraste(cor(texto), cor(fundo))).toBeGreaterThanOrEqual(4.5)
  })

  it('slate só serve para texto grande (3:1)', () => {
    expect(contraste(cor('slate'), cor('void-canvas'))).toBeGreaterThanOrEqual(3)
    expect(contraste(cor('slate'), cor('void-canvas'))).toBeLessThan(4.5)
  })

  it('nenhuma classe ou cor vermelha no código', () => {
    for (const arquivo of arquivosDoCodigo()) {
      const conteudo = readFileSync(arquivo, 'utf-8')
      expect(conteudo, arquivo).not.toMatch(
        /\b(?:text|bg|border|fill|stroke|outline|ring|decoration|from|via|to)-(?:red|rose|pink)-\d/,
      )
      expect(conteudo, arquivo).not.toMatch(/#(?:f00|ff0000)\b|:\s*red\b|['"]red['"]/i)
    }
  })
})
