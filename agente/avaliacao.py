"""Avaliação do agente com casos plantados (manual: consome a assinatura do Claude).

Um lago pequeno, com o esquema dos marts reais, traz três situações:

- caso sancionado: a CONSTRUTORA ACME recebe pagamentos de emenda durante uma sanção do CEIS
  (deve ser confirmado);
- fora da curva: uma despesa de cota da GRÁFICA DELTA muito acima do normal (deve aparecer como
  achado);
- armadilha de homônimo: a ALFA SERVIÇOS da cota tem o mesmo nome de uma empresa sancionada com
  outro CNPJ (não pode ser confirmada); e dois parlamentares se chamam JOSÉ DA SILVA;
- empresa baixada: a BETA ENGENHARIA, baixada na Receita em 2024, recebe pagamentos de emenda em
  2025 (deve ser confirmado).

Os dados são fictícios mas verossímeis (nomes plausíveis, CNPJs com dígitos verificadores válidos),
e o contexto avisa o agente: na primeira avaliação, com nomes como "FORNECEDOR 1" e CNPJs inválidos,
ele concluiu, com razão, que a base era de teste e descartou os casos.
"""

from __future__ import annotations

import random
import shutil
from datetime import date, timedelta
from pathlib import Path

import duckdb

from agente.modelos import Estado, RegistroAchado

CONFIG = """[caminhos]
lago = "avaliacao/lago"
investigacoes = "avaliacao/investigacoes"

[coleta]
prefixo_gcs = ""

[modelo]
nome = "{modelo}"

[consulta]
tempo_maximo_s = 60
linhas_exibidas = 200
linhas_salvas = 100000

[orcamento.livre]
ciclos = 100
minutos = 60
hipoteses = 4
rodadas_validacao = 2

[orcamento.tema]
ciclos = 100
minutos = 60
hipoteses = 4
rodadas_validacao = 2
"""

AVISO = """
## Aviso: ambiente de avaliação

Esta investigação roda sobre um lago de AVALIAÇÃO com dados fictícios (empresas, CNPJs e
parlamentares inventados, com nomes plausíveis). Analise os dados como se fossem reais, com o mesmo
rigor de evidência e validação. Não use a web para checar se as empresas ou os CNPJs existem (não
existem): use a web só para regras gerais (por exemplo, o que significa uma sanção do CEIS).
"""


def _digitos_cnpj(base: str) -> str:
    """CNPJ completo (matriz 0001) a partir dos 8 dígitos da raiz, com dígitos verificadores."""
    numero = base + "0001"
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(int(d) * p for d, p in zip(numero, pesos, strict=True)) % 11
        numero += str(0 if resto < 2 else 11 - resto)
    return numero


ACME = (_digitos_cnpj("41738295"), "CONSTRUTORA ACME DO NORDESTE LTDA")
DELTA = (_digitos_cnpj("52906713"), "GRAFICA DELTA EDITORA LTDA")
ALFA_COTA = (_digitos_cnpj("63184027"), "ALFA SERVICOS DE TELECOMUNICACOES LTDA")
ALFA_SANCIONADA = (_digitos_cnpj("74019362"), "ALFA SERVICOS DE TELECOMUNICACOES LTDA")
BETA = (_digitos_cnpj("85273641"), "BETA ENGENHARIA E SERVICOS LTDA")
ATIVIDADES = [
    "COMERCIAL", "DISTRIBUIDORA", "SERVICOS", "CONSTRUTORA", "TRANSPORTES", "INFORMATICA",
    "ALIMENTOS", "ENGENHARIA", "CONSULTORIA", "LOCADORA",
]  # fmt: skip
NOMES = [
    "ALVORADA", "PAMPA", "SERTAO", "LITORAL", "CERRADO", "PLANALTO", "AURORA", "HORIZONTE",
    "SAO JORGE", "BOA VISTA", "TRES RIOS", "SANTA LUZIA", "NOVA ERA", "VALE VERDE", "PIONEIRA",
]  # fmt: skip
ORGAOS = [
    "Ministério da Saúde", "Ministério da Educação", "Ministério da Integração",
    "Ministério do Esporte", "Ministério da Agricultura",
]  # fmt: skip
PARLAMENTARES = [
    "MARIA APARECIDA SOUZA", "CARLOS EDUARDO LIMA", "ANA PAULA FERREIRA", "ROBERTO ALVES COSTA",
    "FERNANDA RIBEIRO", "PAULO HENRIQUE MOURA", "LUCIANA MARTINS", "ANTONIO CARLOS NUNES",
]  # fmt: skip


def contexto_de_avaliacao(contexto: str) -> str:
    return AVISO.strip() + "\n\n" + contexto


def _cnpj(gerador: random.Random) -> str:
    return _digitos_cnpj("".join(str(gerador.randint(0, 9)) for _ in range(8)))


def _empresa(gerador: random.Random) -> str:
    sufixo = gerador.choice(["LTDA", "LTDA", "EIRELI", "ME", "S.A."])
    return f"{gerador.choice(ATIVIDADES)} {gerador.choice(NOMES)} {sufixo}"


def _inserir(conexao: duckdb.DuckDBPyConnection, tabela: str, linhas: list[tuple]) -> None:
    """Insere de uma vez, por uma tabela Arrow (executemany do DuckDB vai linha a linha)."""
    import pyarrow as pa

    colunas = [d[0] for d in conexao.execute(f"select * from {tabela} limit 0").description]
    dados = pa.table(
        {
            nome: list(valores)
            for nome, valores in zip(colunas, zip(*linhas, strict=True), strict=True)
        }
    )
    conexao.register("novas_linhas", dados)
    conexao.execute(f"insert into {tabela} select * from novas_linhas")
    conexao.unregister("novas_linhas")


def criar_lago(lago: Path, semente: int = 42) -> None:
    """Banco de avaliação com as tabelas e colunas dos marts que os casos usam."""
    gerador = random.Random(semente)
    for pasta in ("raw", "meta", "publico"):
        (lago / pasta).mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(lago / "agente.duckdb"))
    try:
        conexao.execute("create schema marts")
        conexao.execute(
            "create table marts.dim_parlamentar (parlamentar_id varchar, casa varchar, "
            "nome varchar, uf_sigla varchar, partido_sigla varchar)"
        )
        parlamentares = [
            ("camara:10", "camara", "JOSE DA SILVA", "SP", "PA"),
            ("senado:20", "senado", "JOSE DA SILVA", "BA", "PB"),
        ] + [
            (f"camara:{i}", "camara", nome, gerador.choice(["MG", "RJ", "PE", "RS", "GO"]), "PC")
            for i, nome in enumerate(PARLAMENTARES, start=11)
        ]
        _inserir(conexao, "marts.dim_parlamentar", parlamentares)

        conexao.execute(
            "create table marts.fct_sancao (sancao_id varchar, cadastro varchar, "
            "tipo_pessoa varchar, sancionado_documento varchar, sancionado_cnpj_raiz varchar, "
            "sancionado_nome varchar, categoria varchar, abrangencia varchar, "
            "orgao_sancionador varchar, data_inicio date, data_fim date)"
        )
        sancoes = [
            ("CEIS:1", "CEIS", "J", ACME[0], ACME[0][:8], ACME[1],
             "Impedimento/proibição de contratar com prazo determinado",
             "Todas as Esferas em todos os Poderes", "CGU", date(2024, 1, 1), date(2026, 12, 31)),
            ("CEIS:2", "CEIS", "J", ALFA_SANCIONADA[0], ALFA_SANCIONADA[0][:8], ALFA_SANCIONADA[1],
             "Inidoneidade", "Todas as Esferas em todos os Poderes", "TCU",
             date(2023, 6, 1), date(2027, 6, 1)),
        ]  # fmt: skip
        for i in range(3, 13):
            documento = _cnpj(gerador)
            sancoes.append(
                (f"CEIS:{i}", "CEIS", "J", documento, documento[:8], _empresa(gerador),
                 "Suspensão", "No órgão sancionador", "Ministério X",
                 date(2022, 1, 1), date(2023, 1, 1))
            )  # fmt: skip
        _inserir(conexao, "marts.fct_sancao", sancoes)

        conexao.execute(
            "create table marts.fct_emenda_pagamento (pagamento_linha_id varchar, "
            "emenda_codigo varchar, autor_codigo varchar, data_documento date, "
            "fase_despesa varchar, valor_pago decimal(38, 2), favorecido_documento varchar, "
            "favorecido_tipo_documento varchar, favorecido_cnpj_raiz varchar, "
            "favorecido_nome varchar, orgao_nome varchar, uf_sigla varchar)"
        )
        pagamentos = []
        for i in range(300):
            documento = _cnpj(gerador)
            pagamentos.append(
                (f"p{i}", f"2025{gerador.randint(1, 80):04d}", f"A{gerador.randint(1, 30)}",
                 date(2025, 1, 1) + timedelta(days=gerador.randint(0, 270)), "Pagamento",
                 round(gerador.uniform(10_000, 500_000), 2), documento, "CNPJ", documento[:8],
                 _empresa(gerador), gerador.choice(ORGAOS), "MG")
            )  # fmt: skip
        for i in range(6):
            pagamentos.append(
                (f"acme{i}", "20250042", "A7", date(2025, 3 + i, 10), "Pagamento",
                 round(gerador.uniform(300_000, 500_000), 2), ACME[0], "CNPJ", ACME[0][:8],
                 ACME[1], "Ministério da Integração", "PI")
            )  # fmt: skip
        _inserir(conexao, "marts.fct_emenda_pagamento", pagamentos)
        conexao.execute(
            """
            create table marts.alerta_emenda_favorecido_sancionado as
            select
                md5('emenda_favorecido_sancionado|' || p.pagamento_linha_id || '|' || s.sancao_id)
                    as alerta_id,
                p.pagamento_linha_id, s.sancao_id, 'cnpj' as tipo_correspondencia,
                p.emenda_codigo, p.autor_codigo, p.data_documento, p.valor_pago,
                p.favorecido_nome, p.favorecido_documento, s.cadastro,
                s.categoria as categoria_sancao, s.abrangencia,
                s.data_inicio as sancao_data_inicio, s.data_fim as sancao_data_fim,
                'Documento de despesa de emenda a favorecido com sanção vigente' as regra
            from marts.fct_emenda_pagamento as p
            join marts.fct_sancao as s
                on s.sancionado_cnpj_raiz = p.favorecido_cnpj_raiz
                and p.data_documento between s.data_inicio and s.data_fim
            """
        )

        conexao.execute(
            "create table marts.dim_empresa (cnpj_raiz varchar, razao_social varchar, "
            "situacao varchar, data_situacao date, motivo_situacao varchar, data_abertura date)"
        )
        empresas = [
            (p[6][:8], p[9], "ATIVA", date(2010, 1, 1), "SEM MOTIVO", date(2005, 3, 1))
            for p in pagamentos[:40]
        ] + [
            (BETA[0][:8], BETA[1], "BAIXADA", date(2024, 11, 4),
             "EXTINCAO POR ENCERRAMENTO LIQUIDACAO VOLUNTARIA", date(2016, 8, 1)),
        ]  # fmt: skip
        _inserir(conexao, "marts.dim_empresa", empresas)
        beta = [
            (f"beta{i}", "20250051", "A12", date(2025, 2 + 2 * i, 15), "Pagamento",
             round(gerador.uniform(150_000, 250_000), 2), BETA[0], "CNPJ", BETA[0][:8],
             BETA[1], "Ministério da Saúde", "MA")
            for i in range(4)
        ]  # fmt: skip
        _inserir(conexao, "marts.fct_emenda_pagamento", beta)
        conexao.execute(
            """
            create table marts.alerta_pagamento_empresa_irregular as
            select
                md5('pagamento_empresa_irregular|emenda|' || p.pagamento_linha_id) as alerta_id,
                'emenda' as origem, p.pagamento_linha_id as fato_id,
                p.data_documento as data_fato, p.valor_pago as valor,
                p.favorecido_documento as cnpj, e.razao_social, e.situacao, e.data_situacao,
                e.motivo_situacao, p.data_documento - e.data_situacao as dias_desde_a_situacao,
                'Fato com empresa baixada, inapta, suspensa ou nula na Receita' as regra
            from marts.fct_emenda_pagamento as p
            join marts.dim_empresa as e on e.cnpj_raiz = p.favorecido_cnpj_raiz
            where e.situacao != 'ATIVA' and e.data_situacao <= p.data_documento
            """
        )

        conexao.execute(
            "create table marts.fct_despesa_cota_parlamentar (despesa_id varchar, casa varchar, "
            "ano integer, parlamentar_id varchar, nome_beneficiario varchar, uf_sigla varchar, "
            "data_emissao date, categoria varchar, fornecedor_nome varchar, "
            "fornecedor_documento varchar, fornecedor_tipo_documento varchar, "
            "fornecedor_cnpj_raiz varchar, valor_reembolsado decimal(38, 2))"
        )
        categorias = ["COMBUSTÍVEIS", "PASSAGEM AÉREA", "DIVULGAÇÃO", "ALIMENTAÇÃO", "TELEFONIA"]
        fornecedores = [(_cnpj(gerador), _empresa(gerador)) for _ in range(90)]
        despesas = []
        for i in range(600):
            parlamentar = gerador.choice(parlamentares)
            documento, nome = gerador.choice(fornecedores)
            despesas.append(
                (f"camara:d{i}", parlamentar[1], 2025, parlamentar[0], parlamentar[2],
                 parlamentar[3], date(2025, 1, 1) + timedelta(days=gerador.randint(0, 270)),
                 gerador.choice(categorias), nome, documento, "CNPJ",
                 documento[:8], round(gerador.uniform(100, 5_000), 2))
            )  # fmt: skip
        despesas.append(
            ("camara:delta", "camara", 2025, "camara:10", "JOSE DA SILVA", "SP", date(2025, 5, 20),
             "DIVULGAÇÃO", DELTA[1], DELTA[0], "CNPJ", DELTA[0][:8], 95_000.00)
        )  # fmt: skip
        for i in range(20):
            despesas.append(
                (f"camara:alfa{i}", "camara", 2025, "camara:11", PARLAMENTARES[0], "MG",
                 date(2025, 2, 1) + timedelta(days=10 * i), "TELEFONIA", ALFA_COTA[1],
                 ALFA_COTA[0], "CNPJ", ALFA_COTA[0][:8], round(gerador.uniform(200, 800), 2))
            )  # fmt: skip
        _inserir(conexao, "marts.fct_despesa_cota_parlamentar", despesas)
        conexao.execute(
            "create table marts.monitor_fontes as select 'cgu.ceis' as recurso_id, "
            "now() as ultimo_sucesso, 'carregada' as status_ultima_coleta, 1 as atraso_horas"
        )
    finally:
        conexao.close()


def _menciona(registro: RegistroAchado, termo: str) -> bool:
    texto = (registro.achado.titulo + registro.achado.model_dump_json()).upper()
    return termo.upper() in texto


def verificar(estado: Estado) -> dict[str, bool]:
    achados = estado.achados
    return {
        "caso sancionado confirmado": any(
            r.situacao == "confirmado" and _menciona(r, ACME[0][:8]) for r in achados
        ),
        "caso de empresa baixada confirmado": any(
            r.situacao == "confirmado" and _menciona(r, BETA[0][:8]) for r in achados
        ),
        "despesa fora da curva encontrada": any(
            _menciona(r, DELTA[0][:8]) or _menciona(r, "GRAFICA DELTA") for r in achados
        ),
        # apontar o homônimo como problema de qualidade de dado é o comportamento certo; a falha é
        # confirmá-lo como situação suspeita (a empresa da cota não é a sancionada)
        "armadilha de homônimo não confirmada": not any(
            r.situacao == "confirmado"
            and r.achado.tipo == "situação suspeita"
            and _menciona(r, ALFA_COTA[0][:8])
            for r in achados
        ),
    }


def preparar_avaliacao(raiz: Path, modelo: str | None) -> Path:
    """Recria avaliacao/ (lago, investigações e config.toml); devolve o config.toml."""
    base = raiz / "avaliacao"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    arquivo = base / "config.toml"
    arquivo.write_text(CONFIG.format(modelo=modelo or ""), encoding="utf-8")
    criar_lago(base / "lago")
    return arquivo
