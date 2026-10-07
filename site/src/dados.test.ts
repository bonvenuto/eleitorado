import { describe, expect, it } from 'vitest'
import {
  ErroDados,
  carregarAlertas,
  carregarBuscaEmpresas,
  carregarEmpresa,
  carregarParlamentar,
  carregarResumo,
  resolverUrlDosDados,
} from './dados'
import { PADRAO_DADOS_URL } from './caminhos'
import { REDE, caminhosPedidos, exemplo, servir } from './teste/exemplos'
import type { BlocoEmpresas } from './tipos'

async function motivo(promessa: Promise<unknown>): Promise<string> {
  try {
    await promessa
  } catch (erro) {
    if (erro instanceof ErroDados) return erro.motivo
    throw erro
  }
  throw new Error('a promessa deveria ter falhado')
}

describe('endereço dos dados', () => {
  it('produção usa o R2; desenvolvimento usa /exemplos; a variável vence os dois', () => {
    expect(resolverUrlDosDados({ DEV: false })).toBe(PADRAO_DADOS_URL)
    expect(resolverUrlDosDados({ DEV: true })).toBe('/exemplos')
    expect(resolverUrlDosDados({ DEV: false, VITE_DADOS_URL: 'https://x.exemplo/site/' })).toBe(
      'https://x.exemplo/site',
    )
    expect(resolverUrlDosDados({ DEV: false, VITE_DADOS_URL: '' })).toBe(PADRAO_DADOS_URL)
  })
})

describe('baixar', () => {
  it('lê o resumo dos exemplos', async () => {
    const resumo = await carregarResumo()
    expect(resumo.gerado_em).toBe('2026-10-07T11:02:13Z')
    expect(caminhosPedidos()).toEqual(['resumo.json'])
  })

  it('guarda na memória o que já baixou', async () => {
    await carregarResumo()
    await carregarResumo()
    expect(caminhosPedidos()).toEqual(['resumo.json'])
  })

  it('falha de rede não fica no cache', async () => {
    servir({ 'resumo.json': REDE })
    expect(await motivo(carregarResumo())).toBe('rede')
    servir()
    expect((await carregarResumo()).esquema).toBe(1)
  })

  it('HTTP 500 é falha de rede; 404 é não encontrado', async () => {
    servir({ 'resumo.json': 500 })
    expect(await motivo(carregarResumo())).toBe('rede')
    expect(await motivo(carregarParlamentar('camara-1'))).toBe('nao_encontrado')
  })

  it('JSON ilegível é falha de rede', async () => {
    servir({ 'resumo.json': new Response('{"esquema": 1, ') })
    expect(await motivo(carregarResumo())).toBe('rede')
  })

  it('esquema diferente de 1 é recusado', async () => {
    servir({ 'resumo.json': { ...exemplo<object>('resumo.json'), esquema: 2 } })
    expect(await motivo(carregarResumo())).toBe('esquema')
  })
})

describe('arquivos de cada tipo', () => {
  it('parlamentar pelo slug', async () => {
    const arquivo = await carregarParlamentar('camara-900001')
    expect(arquivo.parlamentar.nome).toBe('ANA EXEMPLO')
    expect(caminhosPedidos()).toEqual(['parlamentar/camara-900001.json'])
  })

  it('slug inválido não baixa nada', async () => {
    expect(await motivo(carregarParlamentar('deputado-900001'))).toBe('nao_encontrado')
    expect(await motivo(carregarParlamentar('camara-1%2F..%2Fresumo'))).toBe('nao_encontrado')
    expect(caminhosPedidos()).toEqual([])
  })

  it('empresa: baixa o bloco e devolve a raiz pedida', async () => {
    const empresa = await carregarEmpresa('11222333')
    expect(empresa.cadastro.razao_social).toBe('EMPRESA EXEMPLO LTDA')
    expect(caminhosPedidos()).toEqual(['empresa/b_112.json'])
  })

  it('empresa fora do bloco ou bloco que não existe: não encontrada', async () => {
    expect(await motivo(carregarEmpresa('11222399'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('99999999'))).toBe('nao_encontrado')
  })

  it('raiz inválida não baixa nada', async () => {
    expect(await motivo(carregarEmpresa('112223'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('1122233a'))).toBe('nao_encontrado')
    expect(await motivo(carregarEmpresa('__proto__'))).toBe('nao_encontrado')
    expect(caminhosPedidos()).toEqual([])
  })

  it('CNPJ alfanumérico usa o bloco das 3 primeiras posições', async () => {
    const bloco = exemplo<BlocoEmpresas>('empresa/b_112.json')
    const empresa = bloco.empresas['11222333']
    servir({ 'empresa/b_1AB.json': { esquema: 1, bloco: '1AB', empresas: { '1AB2C3D4': empresa } } })
    expect((await carregarEmpresa('1AB2C3D4')).cadastro.uf).toBe('DF')
    expect(caminhosPedidos()).toEqual(['empresa/b_1AB.json'])
  })

  it('bloco de busca e página de alertas', async () => {
    expect((await carregarBuscaEmpresas('emp')).empresas).toHaveLength(2)
    expect((await carregarAlertas('cota_fornecedor_sancionado', 1)).total).toBe(1)
    expect(await motivo(carregarBuscaEmpresas('../x'))).toBe('nao_encontrado')
    expect(await motivo(carregarAlertas('../resumo', 1))).toBe('nao_encontrado')
    expect(await motivo(carregarAlertas('cota_fornecedor_sancionado', 0))).toBe('nao_encontrado')
  })
})
