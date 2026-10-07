import { useEffect } from 'react'

export function useTitulo(titulo?: string | null): void {
  useEffect(() => {
    document.title = titulo ? `${titulo} · Eleitorado` : 'Eleitorado'
  }, [titulo])
}
