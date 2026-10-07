/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Endereço da pasta site/ no R2 (sem barra no fim). Vazio: padrão de produção. */
  readonly VITE_DADOS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
