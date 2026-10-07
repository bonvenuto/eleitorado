/** Fonte oficial de cada alerta, para o leitor conferir (spec do site, seção 6). */
import type { Alerta } from './tipos'

export interface FonteOficial {
  nome: string
  url: string
}

const PORTAL = 'https://portaldatransparencia.gov.br'

export function fonteDoAlerta(alerta: Alerta): FonteOficial {
  const { tipo } = alerta
  if (tipo.startsWith('cota_')) {
    return alerta.parlamentar_id?.startsWith('senado:')
      ? { nome: 'Senado Federal (cota parlamentar)', url: 'https://www6g.senado.leg.br/transparencia/sen/' }
      : {
          nome: 'Câmara dos Deputados (cota parlamentar)',
          url: 'https://www.camara.leg.br/transparencia/gastos-parlamentares',
        }
  }
  if (tipo.startsWith('emenda_')) return { nome: 'Portal da Transparência (emendas)', url: `${PORTAL}/emendas` }
  if (tipo.startsWith('contrato_')) return { nome: 'Portal da Transparência (contratos)', url: `${PORTAL}/contratos` }
  if (tipo.startsWith('licitacao_')) return { nome: 'Portal da Transparência (licitações)', url: `${PORTAL}/licitacoes` }
  if (alerta.cnpj_raiz) {
    return { nome: 'Portal da Transparência', url: `${PORTAL}/busca?termo=${alerta.cnpj_raiz}` }
  }
  return { nome: 'Portal da Transparência', url: PORTAL }
}
