import type { ErroDados } from '../dados'
import { NaoEncontrada } from '../paginas/NaoEncontrada'

export function Carregando() {
  return (
    <p role="status" className="text-ash">
      Carregando…
    </p>
  )
}

export function AvisoErro({ erro, tentarDeNovo }: { erro: ErroDados; tentarDeNovo: () => void }) {
  if (erro.motivo === 'nao_encontrado') return <NaoEncontrada />
  if (erro.motivo === 'esquema') {
    return (
      <div role="alert" className="rounded-cartao bg-graphite p-7">
        <p>
          Os dados mudaram de formato e este site precisa ser atualizado. Tente recarregar a página
          mais tarde.
        </p>
      </div>
    )
  }
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-cartao bg-graphite p-7">
      <p>Dados indisponíveis no momento.</p>
      <button
        type="button"
        onClick={tentarDeNovo}
        className="rounded-full bg-snow-white px-3 py-2 text-graphite"
      >
        Tentar de novo
      </button>
    </div>
  )
}
