import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { PADRAO_DADOS_URL } from './caminhos'
import { SITE, arquivosDoCodigo } from './teste/arquivos'

const ler = (relativo: string) => readFileSync(path.join(SITE, relativo), 'utf-8')

const PROIBIDOS: [string, RegExp][] = [
  ['cookies', /document\.cookie/],
  ['armazenamento no navegador', /\b(?:localStorage|sessionStorage|indexedDB)\b/],
  ['fontes externas', /fonts\.(?:googleapis|gstatic)\.com|use\.typekit\.net|fonts\.bunny\.net/],
  [
    'analytics',
    /google-analytics|googletagmanager|gtag\(|plausible\.io|matomo|hotjar|segment\.(?:io|com)|clarity\.ms/,
  ],
]

describe('privacidade (spec, seção 7)', () => {
  it.each(PROIBIDOS)('sem %s', (_nome, padrao) => {
    for (const arquivo of arquivosDoCodigo()) {
      expect(readFileSync(arquivo, 'utf-8'), arquivo).not.toMatch(padrao)
    }
  })

  it('as fontes vêm empacotadas do @fontsource', () => {
    const main = ler('src/main.tsx')
    expect(main).toMatch(/@fontsource\/dm-sans/)
    expect(main).toMatch(/@fontsource\/geist/)
  })

  it('a CSP libera a origem dos dados e, fora isso, só as fotos oficiais', () => {
    const csp = /Content-Security-Policy: (.+)/.exec(ler('public/_headers'))?.[1] ?? ''
    const diretivas = new Map(
      csp
        .split(';')
        .map((d) => d.trim().split(/\s+/))
        .map(([nome, ...valores]): [string, string[]] => [nome ?? '', valores]),
    )
    expect(diretivas.get('default-src')).toEqual(["'self'"])
    expect(diretivas.get('script-src')).toEqual(["'self'"])
    expect(diretivas.get('font-src')).toEqual(["'self'"])
    expect(diretivas.get('connect-src')).toEqual(["'self'", new URL(PADRAO_DADOS_URL).origin])
    expect(diretivas.get('img-src')).toEqual([
      "'self'",
      'data:',
      'https://*.camara.leg.br',
      'https://*.senado.leg.br',
    ])
    expect(csp).not.toMatch(/unsafe-eval/)
  })
})
