import { Link, useSearchParams } from 'react-router'
import { AVISO_ALERTA, ListaAlertas } from '../componentes/Alertas'
import { AvisoErro, Carregando } from '../componentes/Estados'
import { Secao } from '../componentes/Secao'
import { rotaAlertas } from '../caminhos'
import { carregarAlertas, carregarResumo } from '../dados'
import { contar, formatarInstante } from '../formato'
import type { AlertaTipo } from '../tipos'
import { useDados } from '../useDados'
import { useTitulo } from '../useTitulo'
import { NaoEncontrada } from './NaoEncontrada'

interface PropsPagina {
  tipo: AlertaTipo
  pagina: number
  tipos: AlertaTipo[]
  geradoEm: string
}

function PaginaDoTipo({ tipo, pagina, tipos, geradoEm }: PropsPagina) {
  // tipo sem alertas não tem arquivo (o pipeline só gera páginas com itens)
  const vazio = tipo.quantidade === 0
  const estado = useDados(`alertas:${tipo.tipo}:${pagina}`, () =>
    vazio ? Promise.resolve(null) : carregarAlertas(tipo.tipo, pagina),
  )
  if (vazio) {
    return <p className="text-ash">Nenhum alerta deste tipo nos dados de {formatarInstante(geradoEm)}.</p>
  }
  if (estado.estado === 'carregando') return <Carregando />
  if (estado.estado === 'erro') {
    return <AvisoErro erro={estado.erro} tentarDeNovo={estado.tentarDeNovo} />
  }
  const atual = estado.dados
  if (!atual) return null
  return (
    <div className="flex flex-col gap-6">
      <p className="text-ash">{contar(atual.total, 'alerta', 'alertas')} deste tipo.</p>
      <ListaAlertas
        alertas={atual.alertas}
        total={atual.total}
        tipos={tipos}
        geradoEm={geradoEm}
        verTodos={false}
      />
      <nav aria-label="Paginação" className="flex flex-wrap items-center gap-4">
        {atual.pagina > 1 && (
          <Link
            to={rotaAlertas(tipo.tipo, atual.pagina - 1)}
            className="rounded-full border border-hairline/40 px-3.5 py-1.5 no-underline"
          >
            Página anterior
          </Link>
        )}
        <p className="text-ash">
          Página {atual.pagina} de {atual.paginas}
        </p>
        {atual.pagina < atual.paginas && (
          <Link
            to={rotaAlertas(tipo.tipo, atual.pagina + 1)}
            className="rounded-full border border-hairline/40 px-3.5 py-1.5 no-underline"
          >
            Próxima página
          </Link>
        )}
      </nav>
    </div>
  )
}

function numeroDaPagina(valor: string | null): number {
  const n = Number(valor ?? '1')
  return Number.isInteger(n) && n >= 1 ? n : 1
}

export function PaginaAlertas() {
  useTitulo('Alertas')
  const [parametros] = useSearchParams()
  const resumo = useDados('resumo', carregarResumo)
  if (resumo.estado === 'carregando') return <Carregando />
  if (resumo.estado === 'erro') {
    return <AvisoErro erro={resumo.erro} tentarDeNovo={resumo.tentarDeNovo} />
  }
  const tipos = [...resumo.dados.alerta_tipos].sort((a, b) => a.ordem - b.ordem)
  const pedido = parametros.get('tipo')
  const tipo = pedido
    ? tipos.find((t) => t.tipo === pedido)
    : (tipos.find((t) => t.quantidade > 0) ?? tipos[0])
  if (!tipo) return <NaoEncontrada />
  const pagina = numeroDaPagina(parametros.get('pagina'))

  return (
    <>
      <header className="flex max-w-3xl flex-col gap-4">
        <h1 className="text-heading-sm font-medium sm:text-heading-lg">Alertas automáticos</h1>
        <p className="text-ash">{AVISO_ALERTA}</p>
      </header>

      <Secao titulo="Como cada alerta é gerado">
        <div className="grid gap-4 sm:grid-cols-2">
          {tipos.map((t) => (
            <div key={t.tipo} className="flex flex-col gap-2 rounded-cartao bg-graphite p-7">
              <h3 className="font-geist text-subheading font-medium">{t.titulo}</h3>
              <p>{t.explicacao}</p>
              <p className="text-ash">
                <strong className="text-bone">Cuidado:</strong> {t.cautela}
              </p>
              <p className="text-caption text-ash">{contar(t.quantidade, 'alerta', 'alertas')}</p>
            </div>
          ))}
        </div>
      </Secao>

      <Secao titulo={tipo.titulo}>
        <nav aria-label="Tipos de alerta">
          <ul className="flex flex-wrap gap-2">
            {tipos.map((t) => {
              const atual = t.tipo === tipo.tipo
              return (
                <li key={t.tipo}>
                  <Link
                    to={rotaAlertas(t.tipo)}
                    aria-current={atual ? 'page' : undefined}
                    className={`inline-block rounded-full border px-3.5 py-1.5 text-caption no-underline ${
                      atual ? 'border-snow-white bg-snow-white text-graphite' : 'border-hairline/40'
                    }`}
                  >
                    {t.titulo} ({contar(t.quantidade, 'alerta', 'alertas')})
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        <PaginaDoTipo
          key={tipo.tipo}
          tipo={tipo}
          pagina={pagina}
          tipos={tipos}
          geradoEm={resumo.dados.gerado_em}
        />
      </Secao>
    </>
  )
}
