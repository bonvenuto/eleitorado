import { carregarResumo } from '../dados'
import { dadosDesatualizados, formatarInstante } from '../formato'
import { useDados } from '../useDados'

export function AvisoDadosAntigos({ geradoEm, agora }: { geradoEm: string; agora?: Date }) {
  if (!dadosDesatualizados(geradoEm, agora)) return null
  return (
    <div role="status" className="mx-auto mt-4 flex max-w-[1200px] items-center gap-3 px-4">
      <span className="selo-alerta" aria-hidden="true">
        Dados antigos
      </span>
      <p>Atenção: os dados não são atualizados desde {formatarInstante(geradoEm)}.</p>
    </div>
  )
}

export function FaixaDesatualizada() {
  const resumo = useDados('resumo', carregarResumo)
  if (resumo.estado !== 'ok') return null
  return <AvisoDadosAntigos geradoEm={resumo.dados.gerado_em} />
}
