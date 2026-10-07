import { describe, expect, it } from 'vitest'
import {
  arquivoAlertas,
  arquivoBuscaEmpresas,
  arquivoEmpresa,
  arquivoParlamentar,
  idDoSlug,
  rotaAlertas,
  rotaEmpresa,
  rotaParlamentar,
  slugDoParlamentar,
  urlDaFoto,
} from './caminhos'

describe('caminhos', () => {
  it('id do parlamentar vira slug e volta', () => {
    expect(slugDoParlamentar('camara:204554')).toBe('camara-204554')
    expect(slugDoParlamentar('senado:5672')).toBe('senado-5672')
    expect(idDoSlug('camara-204554')).toBe('camara:204554')
    expect(idDoSlug('deputado-1')).toBeNull()
    expect(idDoSlug('camara-1/../x')).toBeNull()
    expect(() => slugDoParlamentar('204554')).toThrow()
  })

  it('rotas', () => {
    expect(rotaParlamentar('camara:900001')).toBe('/parlamentar/camara-900001')
    expect(rotaEmpresa('11222333')).toBe('/empresa/11222333')
    expect(rotaAlertas()).toBe('/alertas')
    expect(rotaAlertas('cota_fornecedor_sancionado')).toBe(
      '/alertas?tipo=cota_fornecedor_sancionado',
    )
    expect(rotaAlertas('cota_fornecedor_sancionado', 2)).toBe(
      '/alertas?tipo=cota_fornecedor_sancionado&pagina=2',
    )
  })

  it('arquivos, com os prefixos p_ e b_', () => {
    expect(arquivoParlamentar('camara-900001')).toBe('parlamentar/camara-900001.json')
    expect(arquivoEmpresa('11222333')).toBe('empresa/b_112.json')
    expect(arquivoEmpresa('1AB2C3D4')).toBe('empresa/b_1AB.json')
    expect(arquivoBuscaEmpresas('con')).toBe('busca/empresas/p_con.json')
    expect(arquivoAlertas('cota_fornecedor_sancionado', 3)).toBe(
      'alertas/cota_fornecedor_sancionado/3.json',
    )
  })

  it('foto: só das casas, sempre em https', () => {
    expect(urlDaFoto('https://www.camara.leg.br/internet/deputado/bandep/204554.jpg')).toBe(
      'https://www.camara.leg.br/internet/deputado/bandep/204554.jpg',
    )
    expect(urlDaFoto('http://www.senado.leg.br/senadores/img/fotos-oficiais/senador5672.jpg')).toBe(
      'https://www.senado.leg.br/senadores/img/fotos-oficiais/senador5672.jpg',
    )
    expect(urlDaFoto('https://exemplo.com/foto.jpg')).toBeNull()
    expect(urlDaFoto('https://camara.leg.br.exemplo.com/foto.jpg')).toBeNull()
    expect(urlDaFoto('javascript:alert(1)')).toBeNull()
    expect(urlDaFoto(null)).toBeNull()
  })
})
