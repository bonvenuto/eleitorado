import { Link, NavLink } from 'react-router'

const estiloLink = ({ isActive }: { isActive: boolean }) =>
  `rounded-full border px-3.5 py-1.5 no-underline ${
    isActive ? 'border-hairline/60 text-snow-white' : 'border-transparent text-snow-white/85'
  }`

/** navegação flutuante: embaixo da tela no celular, no topo a partir de `sm` */
export function Navegacao() {
  return (
    <nav
      aria-label="Principal"
      className="fixed inset-x-4 bottom-4 z-40 mx-auto flex max-w-xl items-center justify-between gap-2 rounded-nav border border-hairline/20 bg-graphite/90 px-3.5 py-1.5 backdrop-blur sm:top-4 sm:bottom-auto"
    >
      <Link to="/" className="font-medium text-bone no-underline">
        Eleitorado
      </Link>
      <ul className="flex gap-1">
        <li>
          <NavLink to="/" end className={estiloLink}>
            Início
          </NavLink>
        </li>
        <li>
          <NavLink to="/alertas" className={estiloLink}>
            Alertas
          </NavLink>
        </li>
        <li>
          <NavLink to="/sobre" className={estiloLink}>
            Sobre
          </NavLink>
        </li>
      </ul>
    </nav>
  )
}
