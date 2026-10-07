import { useId } from 'react'
import { Link } from 'react-router'
import { rotaEmpresa, rotaParlamentar } from '../caminhos'
import { fonteDoAlerta } from '../fontes'
import { contar, formatarData, formatarInstante, formatarReais } from '../formato'
import type { Alerta, AlertaTipo } from '../tipos'

export const AVISO_ALERTA =
  'Indício gerado automaticamente a partir de dados públicos; não é acusação nem constatação de irregularidade.'
export const AVISO_HOMONIMO = 'Correspondência só pelo nome, pode ser homônimo.'
export const AVISO_RAIZ =
  'Correspondência só pela raiz do CNPJ (os 8 primeiros caracteres), não pelo CNPJ completo.'

export function avisoDaCorrespondencia(alerta: Alerta): string | null {
  if (alerta.correspondencia === 'forte') return null
  return alerta.tipo === 'parlamentar_socio_fornecedor' ? AVISO_HOMONIMO : AVISO_RAIZ
}

interface PropsCartao {
  alerta: Alerta
  tipo: AlertaTipo | undefined
  geradoEm: string
}

export function CartaoAlerta({ alerta, tipo, geradoEm }: PropsCartao) {
  const idTitulo = useId()
  const fonte = fonteDoAlerta(alerta)
  const aviso = avisoDaCorrespondencia(alerta)
  const empresas = [
    { raiz: alerta.cnpj_raiz, nome: alerta.empresa_nome },
    { raiz: alerta.cnpj_raiz_2, nome: alerta.empresa_nome_2 },
  ].filter((e): e is { raiz: string; nome: string | null } => e.raiz !== null)
  return (
    <article aria-labelledby={idTitulo} className="flex flex-col gap-3 rounded-cartao bg-graphite p-7">
      <p>
        <span className="selo-alerta">Alerta</span>
      </p>
      <h3 id={idTitulo} className="font-geist text-subheading font-medium">
        {tipo?.titulo ?? alerta.tipo}
      </h3>
      <p>{alerta.descricao}</p>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-ash">
        {alerta.data && (
          <div className="flex gap-1">
            <dt>Data do fato:</dt>
            <dd>{formatarData(alerta.data)}</dd>
          </div>
        )}
        {alerta.valor !== null && (
          <div className="flex gap-1">
            <dt>Valor:</dt>
            <dd>{formatarReais(alerta.valor)}</dd>
          </div>
        )}
      </dl>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {alerta.parlamentar_id && (
          <li>
            <Link to={rotaParlamentar(alerta.parlamentar_id)}>
              {alerta.parlamentar_nome ?? alerta.parlamentar_id}
            </Link>
          </li>
        )}
        {empresas.map((e) => (
          <li key={e.raiz}>
            <Link to={rotaEmpresa(e.raiz)}>{e.nome ?? e.raiz}</Link>
          </li>
        ))}
      </ul>
      {aviso && (
        <p>
          <strong>Atenção:</strong> <span>{aviso}</span>
        </p>
      )}
      {tipo && (
        <p className="text-ash">
          <strong className="text-bone">O que é:</strong> <span>{tipo.explicacao}</span>
        </p>
      )}
      {tipo && (
        <p className="text-ash">
          <strong className="text-bone">Cuidado:</strong> <span>{tipo.cautela}</span>
        </p>
      )}
      <p className="text-ash">Regra: {alerta.regra}</p>
      <p className="text-ash">{AVISO_ALERTA}</p>
      <p className="text-caption text-ash">
        Dados de {formatarInstante(geradoEm)} ·{' '}
        <a href={fonte.url} target="_blank" rel="noopener noreferrer">
          Fonte oficial: {fonte.nome}
        </a>
      </p>
    </article>
  )
}

interface PropsLista {
  alertas: Alerta[]
  total: number
  tipos: AlertaTipo[]
  geradoEm: string
  /** mostra o aviso de corte e o link para /alertas (padrão: sim) */
  verTodos?: boolean
}

export function ListaAlertas({ alertas, total, tipos, geradoEm, verTodos = true }: PropsLista) {
  const idFraca = useId()
  if (alertas.length === 0) return <p className="text-ash">Nenhum alerta automático.</p>
  const porTipo = new Map(tipos.map((t) => [t.tipo, t]))
  const fortes = alertas.filter((a) => a.correspondencia === 'forte')
  const fracas = alertas.filter((a) => a.correspondencia === 'fraca')
  const cartao = (a: Alerta) => (
    <li key={a.alerta_id}>
      <CartaoAlerta alerta={a} tipo={porTipo.get(a.tipo)} geradoEm={geradoEm} />
    </li>
  )
  return (
    <div className="flex flex-col gap-6">
      {fortes.length > 0 && (
        <ul aria-label="Alertas" className="flex flex-col gap-4">
          {fortes.map(cartao)}
        </ul>
      )}
      {fracas.length > 0 && (
        <section aria-labelledby={idFraca} className="flex flex-col gap-3">
          <h3 id={idFraca} className="font-geist text-subheading font-medium">
            Correspondência fraca
          </h3>
          <p className="text-ash">
            Nestes alertas, a ligação entre a pessoa e a empresa é menos certa. Leia o aviso de
            cada um.
          </p>
          <ul aria-label="Alertas de correspondência fraca" className="flex flex-col gap-4">
            {fracas.map(cartao)}
          </ul>
        </section>
      )}
      {verTodos && total > alertas.length && (
        <p className="text-ash">
          Mostrando os {alertas.length} mais recentes de {contar(total, 'alerta', 'alertas')}.{' '}
          <Link to="/alertas">Ver todos os alertas</Link>
        </p>
      )}
    </div>
  )
}
