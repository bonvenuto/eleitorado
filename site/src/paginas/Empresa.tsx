import type { ReactNode } from 'react'
import { Link, Navigate, useParams } from 'react-router'
import { ListaAlertas } from '../componentes/Alertas'
import { AvisoErro, Carregando } from '../componentes/Estados'
import { Secao, Subtitulo, Tabela } from '../componentes/Secao'
import { rotaEmpresa, rotaParlamentar } from '../caminhos'
import { carregarEmpresa, carregarResumo } from '../dados'
import {
  TRACO,
  contar,
  formatarCnpj,
  formatarCompetencia,
  formatarData,
  formatarInteiro,
  formatarReais,
  formatarSimNao,
} from '../formato'
import type { Cadastro, Empresa, Resumo, Sancao } from '../tipos'
import { useDados } from '../useDados'
import { useTitulo } from '../useTitulo'

function Par({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-b border-hairline/10 py-2 sm:flex-row sm:gap-4">
      <dt className="text-ash sm:w-56 sm:shrink-0">{rotulo}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function situacao(c: Cadastro): string {
  const desde = c.data_situacao ? ` desde ${formatarData(c.data_situacao)}` : ''
  const motivo = c.motivo_situacao && c.motivo_situacao !== 'SEM MOTIVO' ? ` (${c.motivo_situacao})` : ''
  return `${c.situacao ?? TRACO}${desde}${motivo}`
}

function CadastroReceita({ c }: { c: Cadastro }) {
  return (
    <Secao titulo="Cadastro na Receita Federal">
      <dl>
        <Par rotulo="Situação">{situacao(c)}</Par>
        <Par rotulo="Abertura">{formatarData(c.abertura)}</Par>
        <Par rotulo="Porte">{c.porte ?? TRACO}</Par>
        <Par rotulo="Natureza jurídica">{c.natureza_juridica ?? TRACO}</Par>
        <Par rotulo="Capital social">{formatarReais(c.capital_social)}</Par>
        <Par rotulo="Atividade principal">{c.atividade ?? TRACO}</Par>
        <Par rotulo="Município">{[c.municipio, c.uf].filter(Boolean).join('/') || TRACO}</Par>
        <Par rotulo="Optante pelo Simples">{formatarSimNao(c.optante_simples)}</Par>
        <Par rotulo="MEI">{formatarSimNao(c.optante_mei)}</Par>
        <Par rotulo="Estabelecimentos">{formatarInteiro(c.estabelecimentos)}</Par>
        <Par rotulo="Sócios">{`${formatarInteiro(c.socios)} (os nomes não são publicados)`}</Par>
      </dl>
      <p className="text-caption text-ash">
        Cadastro da Receita Federal de {formatarCompetencia(c.competencia_receita)}.
      </p>
    </Secao>
  )
}

function Recebimentos({ e }: { e: Empresa }) {
  return (
    <Secao titulo="O que recebeu do governo federal">
      <Subtitulo>Cota parlamentar</Subtitulo>
      {e.cota.parlamentares.length === 0 ? (
        <p className="text-ash">Nenhuma despesa de cota nos dados.</p>
      ) : (
        <>
          <p>
            Total: <strong className="font-medium">{formatarReais(e.cota.total)}</strong>
          </p>
          <Tabela
            titulo="Cota parlamentar por parlamentar"
            colunas={['Parlamentar', 'Valor']}
            direita={[1]}
            linhas={e.cota.parlamentares.map((p) => ({
              chave: p.parlamentar_id,
              celulas: [
                <Link to={rotaParlamentar(p.parlamentar_id)}>{p.nome ?? p.parlamentar_id}</Link>,
                formatarReais(p.valor),
              ],
            }))}
          />
        </>
      )}

      <Subtitulo>Emendas</Subtitulo>
      {e.emendas.autores.length === 0 ? (
        <p className="text-ash">Nenhum pagamento de emenda nos dados.</p>
      ) : (
        <>
          <p>
            Total pago: <strong className="font-medium">{formatarReais(e.emendas.total_pago)}</strong>
          </p>
          <Tabela
            titulo="Emendas por autor"
            colunas={['Autor', 'Pago']}
            direita={[1]}
            linhas={e.emendas.autores.map((a, i) => ({
              chave: `${i}`,
              celulas: [
                a.parlamentar_id ? (
                  <Link to={rotaParlamentar(a.parlamentar_id)}>{a.autor ?? a.parlamentar_id}</Link>
                ) : (
                  (a.autor ?? TRACO)
                ),
                formatarReais(a.pago),
              ],
            }))}
          />
        </>
      )}

      <Subtitulo>Contratos federais</Subtitulo>
      {e.contratos.quantidade === 0 ? (
        <p className="text-ash">Nenhum contrato federal nos dados.</p>
      ) : (
        <>
          <p>
            <strong className="font-medium">{formatarReais(e.contratos.total)}</strong> em{' '}
            {contar(e.contratos.quantidade, 'contrato', 'contratos')}
          </p>
          <Tabela
            titulo="Contratos por órgão"
            colunas={['Órgão', 'Contratos', 'Valor']}
            direita={[1, 2]}
            linhas={e.contratos.orgaos.map((o, i) => ({
              chave: `${i}`,
              celulas: [o.orgao ?? TRACO, formatarInteiro(o.contratos), formatarReais(o.valor)],
            }))}
          />
        </>
      )}

      <Subtitulo>Licitações</Subtitulo>
      <p>{contar(e.licitacoes.vencidas, 'licitação vencida', 'licitações vencidas')}</p>
    </Secao>
  )
}

function periodo(s: Sancao): string {
  if (s.fim) return `${formatarData(s.inicio)} a ${formatarData(s.fim)}`
  return `desde ${formatarData(s.inicio)}`
}

function GrupoSancoes({ titulo, sancoes }: { titulo: string; sancoes: Sancao[] }) {
  if (sancoes.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      <Subtitulo>{titulo}</Subtitulo>
      <ul className="flex flex-col gap-3">
        {sancoes.map((s) => (
          <li key={s.sancao_id} className="rounded-cartao bg-graphite p-7">
            <p className="font-medium">
              {s.cadastro ?? TRACO} · {s.categoria ?? TRACO}
            </p>
            <p className="text-ash">
              {s.orgao ?? TRACO} · {periodo(s)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Conteudo({ raiz, e, resumo }: { raiz: string; e: Empresa; resumo: Resumo }) {
  const c = e.cadastro
  return (
    <>
      <header className="flex flex-col gap-2">
        <h1 className="text-heading-sm font-medium sm:text-heading-lg">
          {c.razao_social ?? `Empresa ${formatarCnpj(raiz)}`}
        </h1>
        {c.matriz_cnpj && <p className="text-subheading">CNPJ da matriz {formatarCnpj(c.matriz_cnpj)}</p>}
        {c.url_portal && (
          <p>
            <a href={c.url_portal} target="_blank" rel="noopener noreferrer">
              Ver no Portal da Transparência
            </a>
          </p>
        )}
      </header>
      <CadastroReceita c={c} />
      <Recebimentos e={e} />
      <Secao titulo="Sanções (CEIS e CNEP)">
        {e.sancoes.length === 0 ? (
          <p className="text-ash">Nenhuma sanção no CEIS ou no CNEP nos dados.</p>
        ) : (
          <>
            <GrupoSancoes titulo="Vigentes" sancoes={e.sancoes.filter((s) => s.vigente)} />
            <GrupoSancoes titulo="Encerradas" sancoes={e.sancoes.filter((s) => !s.vigente)} />
          </>
        )}
      </Secao>
      <Secao titulo="Alertas">
        <ListaAlertas
          alertas={e.alertas.itens}
          total={e.alertas.total}
          tipos={resumo.alerta_tipos}
          geradoEm={resumo.gerado_em}
        />
      </Secao>
    </>
  )
}

export function PaginaEmpresa() {
  const { raiz = '' } = useParams()
  const estado = useDados(`empresa:${raiz}`, () =>
    Promise.all([carregarEmpresa(raiz), carregarResumo()]),
  )
  useTitulo(estado.estado === 'ok' ? estado.dados[0].cadastro.razao_social : null)
  // CNPJ alfanumérico: o endereço canônico é em maiúsculas
  if (raiz !== raiz.toUpperCase()) return <Navigate replace to={rotaEmpresa(raiz.toUpperCase())} />
  if (estado.estado === 'carregando') return <Carregando />
  if (estado.estado === 'erro') {
    return <AvisoErro erro={estado.erro} tentarDeNovo={estado.tentarDeNovo} />
  }
  const [empresa, resumo] = estado.dados
  return <Conteudo raiz={raiz} e={empresa} resumo={resumo} />
}
