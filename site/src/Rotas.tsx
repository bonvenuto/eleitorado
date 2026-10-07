import { Route, Routes } from 'react-router'
import { Layout } from './componentes/Layout'
import { PaginaAlertas } from './paginas/Alertas'
import { PaginaEmpresa } from './paginas/Empresa'
import { Inicio } from './paginas/Inicio'
import { NaoEncontrada } from './paginas/NaoEncontrada'
import { PaginaParlamentar } from './paginas/Parlamentar'
import { Sobre } from './paginas/Sobre'

export function Rotas() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route path="parlamentar/:slug" element={<PaginaParlamentar />} />
        <Route path="empresa/:raiz" element={<PaginaEmpresa />} />
        <Route path="alertas" element={<PaginaAlertas />} />
        <Route path="sobre" element={<Sobre />} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}
