import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { MAXIMO_RESULTADOS, analisarConsulta, buscarTexto, consultaBuscavel } from '../busca'
import { rotaEmpresa, rotaParlamentar } from '../caminhos'
import { formatarCnpj, formatarInteiro } from '../formato'
import { useDados } from '../useDados'

const CASA = { camara: 'Câmara', senado: 'Senado' } as const

function Mensagem({ children }: { children: ReactNode }) {
  return <p className="text-ash">{children}</p>
}

const juntar = (partes: (string | null)[]) => partes.filter(Boolean).join(' · ')

export function CaixaBusca({ grande = false }: { grande?: boolean }) {
  const id = useId()
  const navegar = useNavigate()
  const [texto, setTexto] = useState('')
  const consulta = analisarConsulta(texto)
  const buscavel = consulta.tipo === 'texto' && consultaBuscavel(consulta)
  const estado = useDados(buscavel ? `busca:${consulta.palavras.join(' ')}` : 'busca:', () =>
    consulta.tipo === 'texto' && consultaBuscavel(consulta)
      ? buscarTexto(consulta)
      : Promise.resolve(null),
  )

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (consulta.tipo === 'cnpj') void navegar(rotaEmpresa(consulta.raiz))
  }

  function resultados(): ReactNode {
    if (consulta.tipo === 'vazia') return null
    if (consulta.tipo === 'cnpj') {
      return (
        <p>
          <Link to={rotaEmpresa(consulta.raiz)}>
            Ver a empresa de CNPJ {formatarCnpj(consulta.raiz)}
          </Link>
        </p>
      )
    }
    if (!buscavel) return <Mensagem>Digite pelo menos 3 letras.</Mensagem>
    if (estado.estado === 'carregando') return <p role="status">Buscando…</p>
    if (estado.estado === 'erro') {
      if (estado.erro.motivo === 'esquema') {
        return (
          <p role="alert">Os dados mudaram de formato e este site precisa ser atualizado.</p>
        )
      }
      return (
        <div role="alert" className="flex items-center gap-3">
          <p>Busca indisponível no momento.</p>
          <button
            type="button"
            onClick={estado.tentarDeNovo}
            className="rounded-full border border-hairline px-3.5 py-1.5"
          >
            Tentar de novo
          </button>
        </div>
      )
    }
    const r = estado.dados
    if (!r) return null
    const nada = r.parlamentares.length === 0 && r.empresas.length === 0
    return (
      <div className="flex flex-col gap-4">
        {r.parlamentares.length > 0 && (
          <div>
            <p className="font-medium">Parlamentares</p>
            <ul aria-label="Parlamentares encontrados" className="mt-2 flex flex-col gap-2">
              {r.parlamentares.map((p) => (
                <li key={p.id}>
                  <Link to={rotaParlamentar(p.id)}>
                    {p.nome ?? p.id}{' '}
                    <span className="text-ash">{juntar([p.partido, p.uf, CASA[p.casa]])}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {r.totalParlamentares > r.parlamentares.length && (
              <Mensagem>
                Mostrando {MAXIMO_RESULTADOS} de {formatarInteiro(r.totalParlamentares)}{' '}
                parlamentares. Digite mais palavras para refinar.
              </Mensagem>
            )}
          </div>
        )}
        {r.empresas.length > 0 && (
          <div>
            <p className="font-medium">Empresas</p>
            <ul aria-label="Empresas encontradas" className="mt-2 flex flex-col gap-2">
              {r.empresas.map((e) => (
                <li key={e.raiz}>
                  <Link to={rotaEmpresa(e.raiz)}>
                    {e.nome ?? formatarCnpj(e.raiz)}{' '}
                    <span className="text-ash">{juntar([e.uf, e.situacao])}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {r.totalEmpresas > r.empresas.length && (
              <Mensagem>
                Mostrando {MAXIMO_RESULTADOS} de {formatarInteiro(r.totalEmpresas)} empresas.
                Digite mais palavras para refinar.
              </Mensagem>
            )}
          </div>
        )}
        {r.pedeMaisLetras && (
          <Mensagem>
            Há muitas empresas com palavras começando por “{consulta.chave}”. Digite mais uma
            letra para ver todas.
          </Mensagem>
        )}
        {r.semChaveDeEmpresa && (
          <Mensagem>
            Palavras comuns (como LTDA, COMERCIO e SERVICOS) e palavras com menos de 3 letras não
            entram na busca de empresas.
          </Mensagem>
        )}
        {nada && !r.pedeMaisLetras && <Mensagem>Nenhum resultado para “{texto.trim()}”.</Mensagem>}
      </div>
    )
  }

  return (
    <div className="w-full">
      <form role="search" aria-label="Busca" onSubmit={enviar} className="flex flex-col gap-2">
        <label htmlFor={id} className="text-caption text-ash">
          Buscar parlamentar, empresa ou CNPJ
        </label>
        <div className="flex gap-2">
          <input
            id={id}
            type="search"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
            placeholder="Ex.: nome do deputado, razão social ou 00.000.000/0001-00"
            autoComplete="off"
            spellCheck={false}
            className={`min-w-0 flex-1 rounded-full border border-hairline/40 bg-graphite px-5 text-bone placeholder:text-ash ${grande ? 'h-14 text-subheading' : 'h-11'}`}
          />
          <button type="submit" className="rounded-full bg-snow-white px-5 text-graphite">
            Buscar
          </button>
        </div>
      </form>
      <div aria-live="polite" className="mt-4">
        {resultados()}
      </div>
    </div>
  )
}
