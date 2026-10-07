import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router'

function LocalAtual() {
  const local = useLocation()
  return (
    <span hidden data-testid="local">
      {local.pathname + local.search}
    </span>
  )
}

/** renderiza `ui` num roteador de memória em `rota`; `local()` diz onde a navegação parou */
export function renderizarComRotas(ui: ReactNode, rota = '/') {
  const usuario = userEvent.setup()
  const resultado = render(
    <MemoryRouter initialEntries={[rota]}>
      {ui}
      <LocalAtual />
    </MemoryRouter>,
  )
  return { usuario, ...resultado, local: () => resultado.getByTestId('local').textContent }
}
