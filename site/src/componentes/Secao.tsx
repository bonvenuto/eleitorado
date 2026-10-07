import { useId, type ReactNode } from 'react'

/** seção de página: vira região com o nome do título (h2) */
export function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  const id = useId()
  return (
    <section aria-labelledby={id} className="mt-16 flex flex-col gap-6">
      <h2 id={id} className="font-geist text-heading-sm font-semibold">
        {titulo}
      </h2>
      {children}
    </section>
  )
}

/** subtítulo dentro de uma seção */
export function Subtitulo({ children }: { children: ReactNode }) {
  return <h3 className="font-geist text-subheading font-medium">{children}</h3>
}

interface PropsTabela {
  titulo: string
  colunas: string[]
  /** colunas alinhadas à direita (números), pelo índice */
  direita?: number[]
  linhas: { chave: string; celulas: ReactNode[] }[]
}

/** tabela com legenda (para leitores de tela) e cabeçalhos com escopo */
export function Tabela({ titulo, colunas, direita = [], linhas }: PropsTabela) {
  const alinhar = (i: number) => (direita.includes(i) ? 'text-right' : 'text-left')
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <caption className="sr-only">{titulo}</caption>
        <thead>
          <tr className="border-b border-hairline/20 text-caption text-ash">
            {colunas.map((c, i) => (
              <th key={c} scope="col" className={`py-2 pr-4 font-normal ${alinhar(i)}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((linha) => (
            <tr key={linha.chave} className="border-b border-hairline/10">
              {linha.celulas.map((celula, i) => (
                <td key={i} className={`py-2 pr-4 align-top ${alinhar(i)} ${i > 0 ? 'whitespace-nowrap' : ''}`}>
                  {celula}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** número em destaque com rótulo */
export function Numero({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-cartao bg-graphite p-7">
      <dt className="text-caption text-ash">{rotulo}</dt>
      <dd className="font-geist text-heading-sm font-medium">{valor}</dd>
    </div>
  )
}
