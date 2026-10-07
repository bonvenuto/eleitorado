import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { Rotas } from './Rotas'

const raiz = document.getElementById('raiz')
if (!raiz) throw new Error('elemento #raiz não encontrado')

createRoot(raiz).render(
  <StrictMode>
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  </StrictMode>,
)
