import { Link } from 'react-router'
import { CaixaBusca } from '../componentes/CaixaBusca'
import { useTitulo } from '../useTitulo'

export function NaoEncontrada() {
  useTitulo('Página não encontrada')
  return (
    <div className="flex max-w-2xl flex-col gap-6 py-8">
      <h1 className="font-medium text-heading-sm sm:text-heading">Página não encontrada</h1>
      <p className="text-ash">
        O endereço não existe, ou o parlamentar ou a empresa não está nos dados publicados.
      </p>
      <CaixaBusca />
      <p>
        <Link to="/">Voltar ao início</Link>
      </p>
    </div>
  )
}
