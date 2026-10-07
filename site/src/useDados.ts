import { useCallback, useEffect, useState } from 'react'
import { ErroDados } from './dados'

export type EstadoDados<T> =
  | { estado: 'carregando' }
  | { estado: 'ok'; dados: T }
  | { estado: 'erro'; erro: ErroDados }

interface Guardado<T> {
  chave: string
  tentativa: number
  valor: EstadoDados<T>
}

function comoErroDados(erro: unknown): ErroDados {
  return erro instanceof ErroDados ? erro : new ErroDados('rede', String(erro))
}

/**
 * Carrega dados para a tela. `chave` identifica o que carregar: quando ela muda, carrega de novo
 * (e respostas atrasadas da chave anterior são descartadas). `tentarDeNovo` repete a carga.
 */
export function useDados<T>(
  chave: string,
  carregar: () => Promise<T>,
): EstadoDados<T> & { tentarDeNovo: () => void } {
  const [tentativa, setTentativa] = useState(0)
  const [guardado, setGuardado] = useState<Guardado<T> | null>(null)

  useEffect(() => {
    let ativo = true
    carregar().then(
      (dados) => {
        if (ativo) setGuardado({ chave, tentativa, valor: { estado: 'ok', dados } })
      },
      (erro: unknown) => {
        if (ativo) {
          setGuardado({ chave, tentativa, valor: { estado: 'erro', erro: comoErroDados(erro) } })
        }
      },
    )
    return () => {
      ativo = false
    }
    // a chave identifica o que carregar; `carregar` muda a cada render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, tentativa])

  const tentarDeNovo = useCallback(() => setTentativa((t) => t + 1), [])
  const atual = guardado?.chave === chave && guardado.tentativa === tentativa
  const valor: EstadoDados<T> = atual ? guardado.valor : { estado: 'carregando' }
  return { ...valor, tentarDeNovo }
}
