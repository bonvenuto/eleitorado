import { useEffect } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { FaixaDesatualizada } from './FaixaDesatualizada'
import { Navegacao } from './Navegacao'

export function Layout() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="min-h-dvh bg-void-canvas text-bone">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-full focus:bg-snow-white focus:px-3 focus:py-2 focus:text-graphite"
      >
        Pular para o conteúdo
      </a>
      <Navegacao />
      <div className="sm:pt-20">
        <FaixaDesatualizada />
      </div>
      <main id="conteudo" tabIndex={-1} className="mx-auto max-w-[1200px] px-4 pt-8 pb-16 outline-none">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-[1200px] px-4 pb-32 text-caption text-ash sm:pb-12">
        <p>
          Dados públicos oficiais. Sem cookies e sem rastreamento. <Link to="/sobre">Sobre</Link>
        </p>
      </footer>
    </div>
  )
}
