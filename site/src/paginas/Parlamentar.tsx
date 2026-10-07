import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ListaAlertas } from '../componentes/Alertas'
import { AvisoErro, Carregando } from '../componentes/Estados'
import { GraficoBarras } from '../componentes/GraficoBarras'
import { Secao, Tabela } from '../componentes/Secao'
import { rotaEmpresa, urlDaFoto } from '../caminhos'
import { carregarParlamentar, carregarResumo } from '../dados'
import { formatarCnpj, formatarInteiro, formatarReais } from '../formato'
import type { ArquivoParlamentar, Resumo } from '../tipos'
import { useDados } from '../useDados'
import { useTitulo } from '../useTitulo'

const CASA = { camara: 'Câmara dos Deputados', senado: 'Senado Federal' } as const
const OFICIAL = {
  camara: 'Página oficial na Câmara dos Deputados',
  senado: 'Página oficial no Senado Federal',
} as const
const lista = new Intl.ListFormat('pt-BR', { type: 'conjunction' })

/** nome que leva à empresa quando há raiz de CNPJ (CPF de pessoa física fica só como texto) */
function nomeComLink(nome: string | null, raiz: string | null): ReactNode {
  const texto = nome ?? formatarCnpj(raiz)
  return raiz ? <Link to={rotaEmpresa(raiz)}>{texto}</Link> : texto
}

function iniciais(nome: string | null): string {
  return (nome ?? '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
}

function Cabecalho({ arquivo }: { arquivo: ArquivoParlamentar }) {
  const p = arquivo.parlamentar
  const foto = urlDaFoto(p.foto)
  return (
    <header className="flex flex-col gap-6 sm:flex-row sm:items-center">
      {foto ? (
        <img
          src={foto}
          alt={`Foto de ${p.nome ?? ''}`}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="h-32 w-24 rounded-cartao object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          className="flex h-24 w-24 items-center justify-center rounded-full bg-graphite font-geist text-heading-sm text-ash"
        >
          {iniciais(p.nome)}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-sm font-medium sm:text-heading-lg">{p.nome ?? p.id}</h1>
        <p className="text-subheading">{[p.partido, p.uf, CASA[p.casa]].filter(Boolean).join(' · ')}</p>
        {p.legislaturas.length > 0 && (
          <p className="text-ash">Legislaturas: {lista.format(p.legislaturas.map(String))}</p>
        )}
        <p>
          <a href={p.url_oficial} target="_blank" rel="noopener noreferrer">
            {OFICIAL[p.casa]}
          </a>
        </p>
      </div>
    </header>
  )
}

function Cota({ cota }: { cota: ArquivoParlamentar['cota'] }) {
  if (cota.por_ano.length === 0) return <p className="text-ash">Nenhuma despesa de cota nos dados.</p>
  const ultimo = cota.por_ano.at(-1)
  return (
    <>
      <p>
        Total: <strong className="font-medium">{formatarReais(cota.total)}</strong>
      </p>
      <GraficoBarras
        titulo="Cota por ano"
        rotuloColuna="Ano"
        barras={cota.por_ano.map((a) => ({ rotulo: String(a.ano), valor: a.valor }))}
        {...(ultimo ? { destaque: String(ultimo.ano) } : {})}
      />
      <GraficoBarras
        titulo="Cota por categoria"
        rotuloColuna="Categoria"
        horizontal
        barras={cota.por_categoria.map((c) => ({
          rotulo: c.categoria ?? 'Sem categoria',
          valor: c.valor,
        }))}
      />
      <Tabela
        titulo="Maiores fornecedores"
        colunas={['Fornecedor', 'Documento', 'Despesas', 'Valor']}
        direita={[2, 3]}
        linhas={cota.fornecedores.map((f, i) => ({
          chave: `${i}`,
          celulas: [
            nomeComLink(f.nome, f.cnpj_raiz),
            formatarCnpj(f.documento),
            formatarInteiro(f.despesas),
            formatarReais(f.valor),
          ],
        }))}
      />
    </>
  )
}

function Emendas({ emendas }: { emendas: ArquivoParlamentar['emendas'] }) {
  if (emendas.por_ano.length === 0) return <p className="text-ash">Nenhuma emenda paga nos dados.</p>
  const ultimo = emendas.por_ano.at(-1)
  return (
    <>
      <p>
        Total pago: <strong className="font-medium">{formatarReais(emendas.total_pago)}</strong>
      </p>
      <GraficoBarras
        titulo="Emendas pagas por ano"
        rotuloColuna="Ano"
        barras={emendas.por_ano.map((a) => ({ rotulo: String(a.ano), valor: a.pago }))}
        {...(ultimo ? { destaque: String(ultimo.ano) } : {})}
      />
      <Tabela
        titulo="Maiores favorecidos"
        colunas={['Favorecido', 'Documento', 'Pago']}
        direita={[2]}
        linhas={emendas.favorecidos.map((f, i) => ({
          chave: `${i}`,
          celulas: [nomeComLink(f.nome, f.cnpj_raiz), formatarCnpj(f.documento), formatarReais(f.pago)],
        }))}
      />
    </>
  )
}

function Conteudo({ arquivo, resumo }: { arquivo: ArquivoParlamentar; resumo: Resumo }) {
  return (
    <>
      <Cabecalho arquivo={arquivo} />
      <Secao titulo="Cota parlamentar">
        <Cota cota={arquivo.cota} />
      </Secao>
      <Secao titulo="Emendas parlamentares">
        <Emendas emendas={arquivo.emendas} />
      </Secao>
      <Secao titulo="Alertas">
        <ListaAlertas
          alertas={arquivo.alertas.itens}
          total={arquivo.alertas.total}
          tipos={resumo.alerta_tipos}
          geradoEm={resumo.gerado_em}
        />
      </Secao>
    </>
  )
}

export function PaginaParlamentar() {
  const { slug = '' } = useParams()
  const estado = useDados(`parlamentar:${slug}`, () =>
    Promise.all([carregarParlamentar(slug), carregarResumo()]),
  )
  useTitulo(estado.estado === 'ok' ? estado.dados[0].parlamentar.nome : null)
  if (estado.estado === 'carregando') return <Carregando />
  if (estado.estado === 'erro') {
    return <AvisoErro erro={estado.erro} tentarDeNovo={estado.tentarDeNovo} />
  }
  const [arquivo, resumo] = estado.dados
  return <Conteudo arquivo={arquivo} resumo={resumo} />
}
