import * as Plot from '@observablehq/plot'
import { useEffect, useId, useRef, useState, type RefObject } from 'react'
import { formatarReais, formatarReaisCurto } from '../formato'

export interface Barra {
  rotulo: string
  valor: number
}

interface Props {
  titulo: string
  /** cabeçalho da primeira coluna da tabela ("Ano", "Categoria") */
  rotuloColuna: string
  barras: Barra[]
  /** barras deitadas, para muitas categorias com nomes longos */
  horizontal?: boolean
  /** rótulo da barra em branco; as outras ficam em cinza */
  destaque?: string
  formatar?: (valor: number) => string
  formatarEixo?: (valor: number) => string
}

const CINZA = '#b2b2b2'
const BRANCO = '#ffffff'
const EIXO = '#c2c2c2'

function encurtar(texto: string, limite: number): string {
  return texto.length > limite ? `${texto.slice(0, limite - 1)}…` : texto
}

/** largura do contêiner, acompanhando mudanças (o jsdom não mede: fica no padrão do Plot) */
function useLargura(alvo: RefObject<HTMLDivElement | null>): number {
  const [largura, setLargura] = useState(640)
  useEffect(() => {
    const elemento = alvo.current
    if (!elemento || typeof ResizeObserver === 'undefined') return
    const observador = new ResizeObserver(([entrada]) => {
      const medida = Math.floor(entrada?.contentRect.width ?? 0)
      if (medida > 0) setLargura(medida)
    })
    observador.observe(elemento)
    return () => observador.disconnect()
  }, [alvo])
  return largura
}

export function GraficoBarras({
  titulo,
  rotuloColuna,
  barras,
  horizontal = false,
  destaque,
  formatar = formatarReais,
  formatarEixo = formatarReaisCurto,
}: Props) {
  const idTabela = useId()
  const [verTabela, setVerTabela] = useState(false)
  const alvo = useRef<HTMLDivElement>(null)
  const largura = useLargura(alvo)

  useEffect(() => {
    const elemento = alvo.current
    if (!elemento || barras.length === 0) return
    const cor = (b: Barra) => (b.rotulo === destaque ? BRANCO : CINZA)
    const estilo = { background: 'transparent', color: EIXO, fontFamily: 'inherit', fontSize: '13px' }
    const rotulos = barras.map((b) => b.rotulo)
    // no celular, a margem dos rótulos encolhe e eles são cortados mais cedo
    const margem = Math.min(200, Math.round(largura * 0.4))
    const limite = Math.max(10, Math.floor(margem / 7))
    const grafico = horizontal
      ? Plot.plot({
          style: estilo,
          width: largura,
          marginLeft: margem,
          height: 32 * barras.length + 40,
          x: { label: null, grid: true, tickFormat: (v: number) => formatarEixo(v) },
          y: { label: null, domain: rotulos, tickFormat: (t: string) => encurtar(t, limite) },
          marks: [
            Plot.barX(barras, { x: 'valor', y: 'rotulo', fill: cor }),
            Plot.ruleX([0], { stroke: EIXO }),
          ],
        })
      : Plot.plot({
          style: estilo,
          width: largura,
          marginLeft: 72,
          height: 240,
          x: { label: null, domain: rotulos },
          y: { label: null, grid: true, tickFormat: (v: number) => formatarEixo(v) },
          marks: [
            Plot.barY(barras, { x: 'rotulo', y: 'valor', fill: cor }),
            Plot.ruleY([0], { stroke: EIXO }),
          ],
        })
    grafico.setAttribute('aria-hidden', 'true')
    elemento.replaceChildren(grafico)
    return () => grafico.remove()
  }, [barras, horizontal, destaque, formatarEixo, largura])

  if (barras.length === 0) return <p className="text-ash">Sem dados.</p>

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="font-geist text-subheading font-medium">{titulo}</figcaption>
      <div
        ref={alvo}
        role="img"
        aria-label={`${titulo}: gráfico de barras. Os mesmos números estão na tabela.`}
        className="w-full overflow-x-auto"
      />
      <div>
        <button
          type="button"
          aria-expanded={verTabela}
          aria-controls={idTabela}
          onClick={() => setVerTabela((v) => !v)}
          className="rounded-full border border-hairline/40 px-3.5 py-1.5 text-caption"
        >
          {verTabela ? 'Esconder tabela' : 'Ver tabela'}
          <span className="sr-only">: {titulo}</span>
        </button>
      </div>
      <table id={idTabela} hidden={!verTabela} className="w-full text-left">
        <caption className="sr-only">{titulo}</caption>
        <thead>
          <tr>
            <th scope="col">{rotuloColuna}</th>
            <th scope="col" className="text-right">
              Valor
            </th>
          </tr>
        </thead>
        <tbody>
          {barras.map((b, i) => (
            <tr key={`${i}-${b.rotulo}`}>
              <th scope="row" className="font-normal">
                {b.rotulo}
              </th>
              <td className="text-right">{formatar(b.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
