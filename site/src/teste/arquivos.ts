import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** a pasta site/ */
export const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** código que vai para o navegador: index.html e src/ (sem testes nem src/teste/) */
export function arquivosDoCodigo(): string[] {
  const src = path.join(SITE, 'src')
  const doSrc = readdirSync(src, { recursive: true, encoding: 'utf-8' })
    .map((relativo) => relativo.replaceAll('\\', '/'))
    .filter((relativo) => /\.(ts|tsx|css)$/.test(relativo))
    .filter((relativo) => !relativo.includes('.test.') && !relativo.startsWith('teste/'))
    .map((relativo) => path.join(src, relativo))
  return [path.join(SITE, 'index.html'), ...doSrc]
}
