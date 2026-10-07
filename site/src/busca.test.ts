import { describe, expect, it } from 'vitest'
import {
  MAXIMO_RESULTADOS,
  type ConsultaTexto,
  analisarConsulta,
  buscarTexto,
  consultaBuscavel,
  normalizar,
  raizDaConsulta,
} from './busca'
import { ErroDados } from './dados'
import { REDE, caminhosPedidos, servir } from './teste/exemplos'

function texto(consulta: string): ConsultaTexto {
  const analise = analisarConsulta(consulta)
  if (analise.tipo !== 'texto') throw new Error(`não é texto: ${consulta}`)
  return analise
}

const nomes = (lista: { nome: string | null }[]) => lista.map((x) => x.nome)

describe('normalizar', () => {
  it('tira acentos, põe em minúsculas e separa palavras como o dbt', () => {
    expect(normalizar('Construção São-Paulo LTDA.')).toEqual(['construcao', 'sao', 'paulo', 'ltda'])
    expect(normalizar('S/A & Cia')).toEqual(['s', 'a', 'cia'])
    expect(normalizar('  ')).toEqual([])
  })
})

describe('raizDaConsulta', () => {
  it.each([
    ['11.222.333/0001-81', '11222333'],
    ['11222333000181', '11222333'],
    ['11.222.333', '11222333'],
    ['11222333', '11222333'],
    ['1ab2c3d4', '1AB2C3D4'],
    ['1A.B2C.3D4/E5F6-07', '1AB2C3D4'],
    ['  11222333  ', '11222333'],
  ])('%s vai direto à empresa %s', (consulta, raiz) => {
    expect(raizDaConsulta(consulta)).toBe(raiz)
  })

  it.each([
    'construt',
    'loja 1234',
    '123456789',
    '12345678909',
    '11222333000',
    '1AB2C3D4E5F6GH',
    'abc',
  ])('%s não é CNPJ', (consulta) => {
    expect(raizDaConsulta(consulta)).toBeNull()
  })
})

describe('analisarConsulta', () => {
  it('vazia, CNPJ ou texto', () => {
    expect(analisarConsulta('   ').tipo).toBe('vazia')
    expect(analisarConsulta('11.222.333/0001-81')).toEqual({ tipo: 'cnpj', raiz: '11222333' })
    expect(texto('de exemplo')).toEqual({
      tipo: 'texto',
      palavras: ['de', 'exemplo'],
      palavrasEmpresa: ['exemplo'],
      chave: 'exemplo',
    })
  })

  it('palavras ignoradas e curtas não viram chave', () => {
    expect(texto('ltda').chave).toBeNull()
    expect(texto('S/A comercio').chave).toBeNull()
    expect(texto('da ex').chave).toBeNull()
    expect(texto('ex construtora').chave).toBe('construtora')
  })

  it('só busca com uma palavra de 3 caracteres ou mais', () => {
    expect(consultaBuscavel(texto('ex'))).toBe(false)
    expect(consultaBuscavel(texto('ana'))).toBe(true)
  })
})

describe('buscarTexto (sobre site/exemplos)', () => {
  it('acha parlamentar e empresa pela mesma palavra, com ou sem acento', async () => {
    const resultado = await buscarTexto(texto('Exêmplo'))
    expect(nomes(resultado.parlamentares)).toEqual(['ANA EXEMPLO'])
    expect(nomes(resultado.empresas)).toEqual(['EMPRESA EXEMPLO LTDA'])
    expect(caminhosPedidos()).toContain('busca/empresas/p_exe.json')
  })

  it('usa o bloco da primeira palavra e filtra por todas', async () => {
    const resultado = await buscarTexto(texto('empresa exemplo'))
    expect(nomes(resultado.empresas)).toEqual(['EMPRESA EXEMPLO LTDA'])
    expect(caminhosPedidos()).toContain('busca/empresas/p_emp.json')
    expect(caminhosPedidos()).not.toContain('busca/empresas/p_exe.json')
  })

  it('bloco subdividido com 3 letras: as de palavra de 3 letras e o pedido de mais uma', async () => {
    const resultado = await buscarTexto(texto('con'))
    expect(nomes(resultado.empresas)).toEqual(['CON ENGENHARIA SA'])
    expect(resultado.pedeMaisLetras).toBe(true)
    expect(caminhosPedidos()).not.toContain('busca/empresas/p_cons.json')
  })

  it('bloco subdividido com 4 letras ou mais: usa o bloco de 4', async () => {
    for (const consulta of ['cons', 'construtora']) {
      const resultado = await buscarTexto(texto(consulta))
      expect(nomes(resultado.empresas)).toEqual(['CONSTRUTORA EXEMPLO LTDA'])
      expect(resultado.pedeMaisLetras).toBe(false)
    }
    expect(caminhosPedidos()).toContain('busca/empresas/p_cons.json')
  })

  it('bloco que não existe é resultado vazio', async () => {
    const resultado = await buscarTexto(texto('xyz'))
    expect(resultado.empresas).toEqual([])
    expect(resultado.parlamentares).toEqual([])
  })

  it('só palavras ignoradas: não baixa bloco de empresa', async () => {
    const resultado = await buscarTexto(texto('ltda'))
    expect(resultado.semChaveDeEmpresa).toBe(true)
    expect(caminhosPedidos().some((c) => c.startsWith('busca/empresas/'))).toBe(false)
  })

  it('corta em 50 e informa o total', async () => {
    const empresas = Array.from({ length: 60 }, (_, i) => ({
      raiz: String(10000000 + i),
      nome: `EXEMPLO ${i}`,
      uf: 'DF',
      situacao: 'ATIVA',
    }))
    servir({
      'busca/empresas/p_exe.json': { esquema: 1, prefixo: 'exe', subdividido: false, empresas },
    })
    const resultado = await buscarTexto(texto('exemplo'))
    expect(resultado.empresas).toHaveLength(MAXIMO_RESULTADOS)
    expect(resultado.totalEmpresas).toBe(60)
  })

  it('falha de rede vira ErroDados', async () => {
    servir({ 'busca/parlamentares.json': REDE })
    await expect(buscarTexto(texto('ana'))).rejects.toBeInstanceOf(ErroDados)
  })
})
