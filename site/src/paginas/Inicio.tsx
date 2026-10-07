import { Link } from 'react-router'
import { ListaAlertas } from '../componentes/Alertas'
import { CaixaBusca } from '../componentes/CaixaBusca'
import { AvisoErro, Carregando } from '../componentes/Estados'
import { Numero, Secao } from '../componentes/Secao'
import { rotaAlertas } from '../caminhos'
import { carregarResumo } from '../dados'
import {
  contar,
  formatarCompetencia,
  formatarData,
  formatarInstante,
  formatarInteiro,
  formatarReaisCurto,
} from '../formato'
import type { Resumo } from '../tipos'
import { useDados } from '../useDados'
import { useTitulo } from '../useTitulo'

function Conteudo({ resumo }: { resumo: Resumo }) {
  const { totais, dados_ate: ate } = resumo
  const tipos = [...resumo.alerta_tipos].sort((a, b) => a.ordem - b.ordem)
  return (
    <>
      <Secao titulo="Números gerais">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Numero rotulo="Cota parlamentar" valor={formatarReaisCurto(totais.cota)} />
          <Numero rotulo="Emendas pagas" valor={formatarReaisCurto(totais.emendas_pago)} />
          <Numero rotulo="Contratos federais" valor={formatarReaisCurto(totais.contratos)} />
          <Numero rotulo="Parlamentares" valor={formatarInteiro(totais.parlamentares)} />
          <Numero rotulo="Empresas" valor={formatarInteiro(totais.empresas)} />
        </dl>
      </Secao>

      <Secao titulo="Alertas por tipo">
        <ul className="flex flex-col">
          {tipos.map((t, i) => (
            <li key={t.tipo} className="border-b border-hairline/10">
              <Link
                to={rotaAlertas(t.tipo)}
                className="flex items-baseline justify-between gap-4 py-3 no-underline hover:underline"
              >
                <span>{t.titulo}</span>
                <span className="shrink-0 text-ash">
                  {contar(t.quantidade, 'alerta', 'alertas')}
                  <span aria-hidden="true" className="ml-4">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Secao>

      <Secao titulo="Alertas recentes">
        <ListaAlertas
          alertas={resumo.alertas_recentes}
          total={resumo.alertas_recentes.length}
          tipos={resumo.alerta_tipos}
          geradoEm={resumo.gerado_em}
          verTodos={false}
        />
        <p>
          <Link to="/alertas">Ver todos os alertas</Link>
        </p>
      </Secao>

      <div className="mt-16 flex flex-col gap-1 text-caption text-ash">
        <p>Dados atualizados em {formatarInstante(resumo.gerado_em)}.</p>
        <p>
          Cota até {formatarData(ate.cota)}, emendas até {formatarData(ate.emendas)}, contratos
          até {formatarData(ate.contratos)}; Receita Federal: {formatarCompetencia(ate.receita)}.
        </p>
      </div>
    </>
  )
}

export function Inicio() {
  useTitulo()
  const resumo = useDados('resumo', carregarResumo)
  return (
    <>
      <section className="-mx-4 flex flex-col gap-6 bg-linear-to-r from-capa-inicio to-capa-fim px-4 py-12 sm:mx-0 sm:rounded-painel sm:px-12 sm:py-16">
        <h1 className="max-w-3xl text-display-celular font-medium text-snow-white sm:text-display">
          Para onde vai o dinheiro público
        </h1>
        <p className="max-w-2xl text-subheading text-bone">
          Gastos de parlamentares, emendas e contratos federais, com alertas automáticos
          explicados.
        </p>
        <div className="max-w-2xl">
          <CaixaBusca grande />
        </div>
      </section>
      {resumo.estado === 'carregando' && (
        <div className="mt-16">
          <Carregando />
        </div>
      )}
      {resumo.estado === 'erro' && (
        <div className="mt-16">
          <AvisoErro erro={resumo.erro} tentarDeNovo={resumo.tentarDeNovo} />
        </div>
      )}
      {resumo.estado === 'ok' && <Conteudo resumo={resumo.dados} />}
    </>
  )
}
