/**
 * Tipos dos arquivos do site, espelho de site/esquemas/*.schema.json (esquema 1).
 * Datas: "AAAA-MM-DD"; instantes: "AAAA-MM-DDTHH:MM:SSZ"; valores em reais.
 */

export type Casa = 'camara' | 'senado'
export type Correspondencia = 'forte' | 'fraca'

export interface Alerta {
  alerta_id: string
  /** nome do mart sem o prefixo `alerta_` (ex.: `cota_fornecedor_sancionado`) */
  tipo: string
  data: string | null
  valor: number | null
  /** `camara:204554` ou `senado:5672` */
  parlamentar_id: string | null
  parlamentar_nome: string | null
  cnpj_raiz: string | null
  empresa_nome: string | null
  /** a segunda empresa, só em `licitacao_socios_em_comum` */
  cnpj_raiz_2: string | null
  empresa_nome_2: string | null
  descricao: string
  correspondencia: Correspondencia
  regra: string
}

/** alertas de um parlamentar ou empresa: os 200 mais recentes e o total */
export interface Alertas {
  total: number
  itens: Alerta[]
}

export interface ParlamentarResumo {
  id: string
  nome: string | null
  casa: Casa
  uf: string | null
  partido: string | null
  foto: string | null
  legislaturas: number[]
}

export interface AlertaTipo {
  tipo: string
  titulo: string
  explicacao: string
  cautela: string
  ordem: number
  quantidade: number
}

export interface Fonte {
  recurso_id: string
  cadencia: string | null
  ultimo_sucesso: string | null
  status: string | null
  atraso_horas: number | null
  situacao: 'ok' | 'aviso' | 'erro'
}

export interface FonteReduzida {
  recurso_id: string
  competencia: string | null
  coletada_em: string | null
  linhas_antes: number | null
  linhas_depois: number | null
  variacao_pct: number | null
}

/** resumo.json */
export interface Resumo {
  esquema: 1
  gerado_em: string
  dados_ate: {
    cota: string | null
    emendas: string | null
    contratos: string | null
    /** competência "AAAA-MM" */
    receita: string | null
  }
  totais: {
    cota: number
    emendas_pago: number
    contratos: number
    parlamentares: number
    empresas: number
  }
  alerta_tipos: AlertaTipo[]
  alertas_recentes: Alerta[]
  fontes: Fonte[]
  fontes_reduzidas: FonteReduzida[]
}

/** busca/parlamentares.json */
export interface BuscaParlamentares {
  esquema: 1
  parlamentares: ParlamentarResumo[]
}

export interface EmpresaNaBusca {
  raiz: string
  nome: string | null
  uf: string | null
  situacao: string | null
}

/** busca/empresas/p_<prefixo>.json */
export interface BuscaEmpresas {
  esquema: 1
  prefixo: string
  subdividido: boolean
  empresas: EmpresaNaBusca[]
}

export interface Parlamentar extends ParlamentarResumo {
  url_oficial: string
}

/** parlamentar/<casa>-<id>.json */
export interface ArquivoParlamentar {
  esquema: 1
  parlamentar: Parlamentar
  cota: {
    total: number
    por_ano: { ano: number; valor: number }[]
    por_categoria: { categoria: string | null; valor: number }[]
    fornecedores: {
      nome: string | null
      /** CNPJ completo ou CPF mascarado (`***.456.789-**`) */
      documento: string | null
      cnpj_raiz: string | null
      valor: number
      despesas: number
    }[]
  }
  emendas: {
    total_pago: number
    por_ano: { ano: number; pago: number }[]
    favorecidos: {
      nome: string | null
      documento: string | null
      cnpj_raiz: string | null
      pago: number
    }[]
  }
  alertas: Alertas
}

export interface Cadastro {
  razao_social: string | null
  natureza_juridica: string | null
  porte: string | null
  capital_social: number | null
  abertura: string | null
  situacao: string | null
  data_situacao: string | null
  motivo_situacao: string | null
  atividade: string | null
  municipio: string | null
  uf: string | null
  optante_simples: boolean | null
  optante_mei: boolean | null
  estabelecimentos: number | null
  /** só a contagem: os sócios nunca vão para o site */
  socios: number | null
  matriz_cnpj: string | null
  url_portal: string | null
  /** competência "AAAA-MM" da base da Receita */
  competencia_receita: string | null
}

export interface Sancao {
  sancao_id: string
  cadastro: string | null
  categoria: string | null
  orgao: string | null
  inicio: string | null
  fim: string | null
  vigente: boolean
}

export interface Empresa {
  cadastro: Cadastro
  cota: {
    total: number
    parlamentares: { parlamentar_id: string; nome: string | null; valor: number }[]
  }
  emendas: {
    total_pago: number
    autores: { autor: string | null; parlamentar_id: string | null; pago: number }[]
  }
  contratos: {
    total: number
    quantidade: number
    orgaos: { orgao: string | null; valor: number; contratos: number }[]
  }
  licitacoes: { vencidas: number }
  sancoes: Sancao[]
  alertas: Alertas
}

/** empresa/b_<bloco>.json: empresas cuja raiz começa pelo bloco, por raiz */
export interface BlocoEmpresas {
  esquema: 1
  bloco: string
  empresas: Record<string, Empresa>
}

/** alertas/<tipo>/<pagina>.json */
export interface PaginaAlertas {
  esquema: 1
  tipo: string
  pagina: number
  paginas: number
  total: number
  alertas: Alerta[]
}
