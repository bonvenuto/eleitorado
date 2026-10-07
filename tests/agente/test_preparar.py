from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from agente.caderno import Caderno, Caso, ConsultaChave
from agente.config import ConfigAgente, Orcamento
from agente.preparar import (
    ErroPreparo,
    ambiente,
    gerar_contexto,
    impressao_lago,
    ler_env,
    preparar,
    revisar_caderno,
)

ORCAMENTO = Orcamento(ciclos=10, minutos=10, hipoteses=2, rodadas_validacao=2)
AGORA = datetime(2026, 10, 6, 12, tzinfo=UTC)


@pytest.fixture
def config(lago, tmp_path):
    (tmp_path / ".env").write_text(
        "# comentário\nELEITORADO_PROJETO=proj\nELEITORADO_AMBIENTE=dev\nCLOUDSDK_CONFIG='c:/x'\n",
        encoding="utf-8",
    )
    return ConfigAgente(
        raiz=tmp_path,
        lago=lago,
        investigacoes=tmp_path / "investigacoes",
        prefixo_gcs="paralelo/",
        modelo=None,
        tempo_consulta_s=30,
        linhas_exibidas=20,
        linhas_salvas=1000,
        livre=ORCAMENTO,
        tema=ORCAMENTO,
    )


def test_ler_env(tmp_path, config):
    assert ler_env(tmp_path / ".env") == {
        "ELEITORADO_PROJETO": "proj",
        "ELEITORADO_AMBIENTE": "dev",
        "CLOUDSDK_CONFIG": "c:/x",
    }
    assert ler_env(tmp_path / "nao_existe") == {}


def test_ambiente_le_o_lago_de_producao(config):
    env = ambiente(config, {"PATH": "p"})
    assert env["PATH"] == "p" and env["ELEITORADO_PROJETO"] == "proj"
    assert env["ELEITORADO_AMBIENTE"] == "prod"
    assert env["ELEITORADO_PREFIXO"] == "paralelo/"
    assert env["ELEITORADO_LAGO"] == str(config.lago)


def test_impressao_muda_quando_o_lago_muda(config):
    antes = impressao_lago(config.lago)
    assert antes == impressao_lago(config.lago)
    (config.lago / "raw" / "cgu" / "novo.parquet").write_bytes(b"x")
    assert impressao_lago(config.lago) != antes


def test_contexto_lista_tabelas_colunas_e_linhas(config):
    texto = gerar_contexto(config)
    assert "## marts" in texto
    assert "`marts.fornecedores` (300 linhas): id BIGINT, nome VARCHAR" in texto


def test_preparar_roda_restaurar_e_dbt_so_quando_muda(config):
    chamadas = []

    def rodar(comando, env, cwd):
        assert cwd == config.raiz  # sempre da raiz, de qualquer pasta que o usuário rode
        chamadas.append(comando[3] if comando[2] == "coletor" else comando[2])
        assert env["ELEITORADO_AMBIENTE"] == "prod"
        return construtor_c2(config, [])(comando, env, cwd)

    primeiro = preparar(config, {}, rodar, lambda: AGORA)
    assert chamadas == ["--target", "dbt"]  # restaurar (com --target agente) e dbt
    assert primeiro.dbt_rodou and primeiro.versao_dados["dbt"] == "sucesso"
    assert (config.investigacoes / "contexto.md").exists()
    chamadas.clear()
    segundo = preparar(config, {}, rodar, lambda: AGORA)
    assert chamadas == ["--target"] and not segundo.dbt_rodou
    assert segundo.versao_dados["lago"] == primeiro.versao_dados["lago"]


def test_preparar_cria_parquet_vazio_para_fonte_ainda_sem_coleta(config):
    esquemas = config.raiz / "dbt" / "tests" / "lago_vazio" / "esquemas.json"
    esquemas.parent.mkdir(parents=True)
    esquemas.write_text('{"raw/rfb/empresas": {"cnpj_basico": "VARCHAR"}}', encoding="utf-8")
    preparar(config, {}, construtor_c2(config, []), lambda: AGORA)
    vazio = config.lago / "raw" / "rfb" / "empresas" / "vazio" / "vazio.parquet"
    assert duckdb.sql(f"select count(*) from '{vazio.as_posix()}'").fetchone() == (0,)


def test_preparar_falha_se_o_restaurar_falha(config):
    with pytest.raises(ErroPreparo, match="restaurar"):
        preparar(config, {}, lambda comando, env, cwd: 1, lambda: AGORA)


def test_revisar_caderno_acha_casos_que_mudaram(config):
    caderno = Caderno(config.caderno)
    sql = "select id, valor from marts.fornecedores where id < 10"
    for identificador, situacao, linhas in (
        ("igual", "confirmado", 10),
        ("mudou", "descartado", 9),
        ("aberto", "inconclusivo", 1),
    ):
        caderno.salvar(
            Caso(
                caso_id=identificador,
                titulo=identificador,
                tipo="insight estratégico",
                padrao="p",
                entidades={"x": [identificador]},
                situacao=situacao,
                consultas_chave=[ConsultaChave(sql=sql, linhas=linhas, soma=472.5 + 45)],
                atualizado_em=AGORA,
            )
        )
    revisar = revisar_caderno(config, caderno)
    assert [c.caso_id for c in revisar] == ["mudou"]


def test_tabela_do_banco_continua_so_de_leitura(config):
    gerar_contexto(config)
    conexao = duckdb.connect(str(config.banco))  # o contexto não deixou o banco travado
    conexao.close()


def test_corrigir_particoes_devolve_as_colunas_de_particao(tmp_path):
    from agente.preparar import corrigir_particoes

    pasta = tmp_path / "marts" / "fct_x"
    pasta.parent.mkdir(parents=True)  # o DuckDB não cria a pasta-mãe
    duckdb.sql(
        f"copy (select 'camara' as casa, 2024 as ano, 1.5 as valor) to '{pasta.as_posix()}' "
        "(format parquet, partition_by (casa, ano))"
    )
    banco = tmp_path / "b.duckdb"
    conexao = duckdb.connect(str(banco))
    conexao.execute("create schema marts")
    conexao.execute(
        f"create view marts.fct_x as select * from read_parquet('{pasta.as_posix()}/*/*/*.parquet')"
    )
    conexao.execute("create view marts.fct_y as select 1 as um")
    conexao.close()
    assert corrigir_particoes(banco) == ["fct_x"]
    conexao = duckdb.connect(str(banco))
    assert conexao.sql("select casa, ano, valor from marts.fct_x").fetchall() == [
        ("camara", 2024, 1.5)
    ]
    conexao.close()


def test_somar_colunas_decimais_e_float():
    from decimal import Decimal

    import pyarrow as pa

    from agente.preparar import _somar

    tabela = pa.table(
        {
            "valor": pa.array([Decimal("1.50"), Decimal("2.00")], pa.decimal128(38, 2)),
            "fator": [0.25, 0.25],
            "nome": ["a", "b"],
        }
    )
    assert _somar(tabela) == 4.0
    assert _somar(pa.table({"nome": ["a"]})) is None


@pytest.fixture
def c2(config, tmp_path):
    import shutil

    from coletor.tse.selecao import promover_selecao
    from tests.test_tse_selecao import execucao, montar_vetor

    lago, selecao = montar_vetor(tmp_path / "vetor")
    shutil.copytree(lago, config.lago, dirs_exist_ok=True)
    promover_selecao(config.lago, selecao, execucao(config.lago, selecao))
    return config, selecao


def construtor_c2(config, chamadas, codigo=0):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    def rodar(comando, env, cwd):
        if "build" in comando:
            chamadas.append(comando)
            if "--vars" in comando:
                variaveis = json.loads(comando[comando.index("--vars") + 1])
                saida = Path(variaveis["tse_saida"])
                pq.write_table(pa.table({"valor": [7]}), saida / "c2.parquet")
                conexao = duckdb.connect(str(config.banco))
                conexao.execute("create schema if not exists marts")
                conexao.execute(
                    "create or replace view marts.c2 as select * from "
                    f"'{saida.as_posix()}/c2.parquet'"
                )
                conexao.close()
            return codigo
        return 0

    return rodar


def test_rollback_mesmo_tamanho_refaz_dbt(c2, tmp_path):
    from coletor.tse.selecao import criar_selecao, promover_selecao
    from tests.test_tse_selecao import execucao, versao

    config, selecao = c2
    alternativa = versao(config.lago, tmp_path / "alternativa", "bens", 2024, total=200)
    vetor = dict(selecao.versoes)
    vetor["tse.bens:2024"] = alternativa.versao_id
    outra = criar_selecao(vetor)
    recibo_original = execucao(config.lago, selecao, "retorno")
    promover_selecao(config.lago, outra, execucao(config.lago, outra, "outra"))
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    antes = impressao_lago(config.lago)
    caminhos = {
        p.relative_to(config.lago): p.stat().st_size
        for pasta in ("raw", "meta", "estado")
        for p in (config.lago / pasta).rglob("*")
        if p.is_file()
    }
    promover_selecao(config.lago, selecao, recibo_original)
    # A troca do seletor tem mesmo tamanho; os arquivos de entrada antigos continuam presentes.
    assert (config.lago / "estado/tse/vigente.json").stat().st_size == caminhos[
        Path("estado/tse/vigente.json")
    ]
    assert caminhos == {
        p.relative_to(config.lago): p.stat().st_size
        for pasta in ("raw", "meta", "estado")
        for p in (config.lago / pasta).rglob("*")
        if p.is_file()
    }
    assert impressao_lago(config.lago) != antes
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2


def test_dbt_falho_nao_marca_preparo_c2(c2):
    from agente.controlador import Controlador, Dependencias
    from tests.agente.test_controlador import ExecutorFalso

    config, _ = c2
    marca = config.lago / "preparo.json"
    marca.write_bytes(b'{"impressao":"anterior"}')
    executor = ExecutorFalso(config, {})
    deps = Dependencias(
        config, executor, lambda: preparar(config, {}, construtor_c2(config, [], 1)), lambda: AGORA
    )
    controlador = Controlador(deps)
    with pytest.raises(ErroPreparo, match="dbt"):
        controlador.executar(controlador.nova(None))
    assert marca.read_bytes() == b'{"impressao":"anterior"}'
    assert executor.pedidos == []


def test_seletor_restaurado_invalido_bloqueia_c2(c2):
    config, _ = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = (config.lago / "preparo.json").read_bytes()
    (config.lago / "estado/tse/vigente.json").write_bytes(b"{}")
    with pytest.raises(ErroPreparo):
        preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    assert (config.lago / "preparo.json").read_bytes() == marca
    assert len(chamadas) == 1


def test_cache_c2_reutiliza_saida_sem_auto_invalidacao(c2):
    import json

    config, _ = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = json.loads((config.lago / "preparo.json").read_bytes())
    pastas = set((config.lago / "estado/tse/publicacoes/preparadas").iterdir())
    assert not preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 1
    assert set((config.lago / "estado/tse/publicacoes/preparadas").iterdir()) == pastas
    assert json.loads(chamadas[0][chamadas[0].index("--vars") + 1]) == marca["tse"]["vars"]
    assert "`marts.c2` (1 linhas)" in (config.investigacoes / "contexto.md").read_text(
        encoding="utf8"
    )


@pytest.mark.parametrize("defeito", ["ausente", "adulterada", "regra"])
def test_cache_c2_reconstroi_saida_ou_regra_alterada(c2, defeito):
    import json

    config, _ = c2
    regra = config.raiz / "dbt/models/staging/tse/exemplo.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("select 1")
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = json.loads((config.lago / "preparo.json").read_bytes())
    arquivo = Path(marca["tse"]["saida"]) / "c2.parquet"
    if defeito == "ausente":
        arquivo.unlink()
    elif defeito == "adulterada":
        arquivo.write_bytes(b"adulterado")
    else:
        regra.write_text("select 2")
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2


def test_bootstrap_vars_e_falha_impede_sessoes(config):
    chamadas = []
    marca = config.lago / "preparo.json"
    marca.write_bytes(b'{"impressao":"anterior"}')
    with pytest.raises(ErroPreparo, match="dbt"):
        preparar(config, {}, construtor_c2(config, chamadas, 1), lambda: AGORA)
    import json

    variaveis = json.loads(chamadas[0][chamadas[0].index("--vars") + 1])
    assert set(variaveis) >= {"tse_fontes", "tse_saida", "tse_proveniencia"}
    assert len(variaveis["tse_fontes"]) == 6
    assert marca.read_bytes() == b'{"impressao":"anterior"}'
    assert not (config.lago / "estado/tse/vigente.json").exists()


def test_rejeicao_posterior_bloqueia_mesmo_cache_c2(c2):
    from coletor.tse.selecao import CONTRATO, digest_entradas
    from coletor.tse.validacoes import gravar_avaliacao

    config, selecao = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = (config.lago / "preparo.json").read_bytes()
    gravar_avaliacao(
        config.lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(config.lago, selecao),
        contrato=CONTRATO,
        execucao_id="rejeicao",
        resultado="rejeitada",
        motivos=["posterior"],
    )
    with pytest.raises(ErroPreparo):
        preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    assert len(chamadas) == 1
    assert (config.lago / "preparo.json").read_bytes() == marca


def test_consulta_c2_permitida_irma_e_recibo_negados(c2):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from agente.consulta import abrir

    config, _ = c2
    preparar(config, {}, construtor_c2(config, []), lambda: AGORA)
    marca = json.loads((config.lago / "preparo.json").read_bytes())
    saida = Path(marca["tse"]["saida"])
    irma = saida.parents[1] / "irma/marts"
    irma.mkdir(parents=True)
    pq.write_table(pa.table({"valor": [99]}), irma / "negado.parquet")
    recibo = saida.parent / "privado.parquet"
    pq.write_table(pa.table({"valor": [88]}), recibo)
    conexao = abrir(config.banco, config.diretorios_permitidos())
    try:
        assert conexao.sql("select valor from marts.c2").fetchall() == [(7,)]
        for arquivo in (irma / "negado.parquet", recibo):
            with pytest.raises(duckdb.Error, match="[Pp]ermission|[Dd]isabled|[Aa]ccess"):
                conexao.sql(f"select * from '{arquivo.as_posix()}'").fetchall()
        for caminhos in marca["tse"]["vars"]["tse_fontes"].values():
            # A seleção C2 real usa raw, que já era permitido.
            assert conexao.sql(f"select count(*) from '{caminhos[0]}'").fetchone()[0] >= 0
    finally:
        conexao.close()


def test_bootstrap_consulta_vazios_e_saida_com_cache(config):
    import json

    from agente.consulta import abrir

    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = json.loads((config.lago / "preparo.json").read_bytes())
    conexao = abrir(config.banco, config.diretorios_permitidos())
    try:
        for caminhos in marca["tse"]["vars"]["tse_fontes"].values():
            assert conexao.sql(f"select count(*) from '{caminhos[0]}'").fetchone() == (0,)
        assert conexao.sql("select valor from marts.c2").fetchall() == [(7,)]
    finally:
        conexao.close()
    assert not preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 1
    assert not (config.lago / "estado/tse/vigente.json").exists()


def test_bootstrap_falho_inicia_zero_sessoes(config):
    from agente.controlador import Controlador, Dependencias
    from tests.agente.test_controlador import ExecutorFalso

    executor = ExecutorFalso(config, {})
    deps = Dependencias(
        config, executor, lambda: preparar(config, {}, construtor_c2(config, [], 1)), lambda: AGORA
    )
    controlador = Controlador(deps)
    with pytest.raises(ErroPreparo):
        controlador.executar(controlador.nova(None))
    assert executor.pedidos == []


def test_falha_banco_parcial_nao_reutiliza_marca_antiga(c2):
    from agente.controlador import Controlador, Dependencias
    from tests.agente.test_controlador import ExecutorFalso

    config, _ = c2
    regra = config.raiz / "dbt/models/staging/tse/exemplo.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("select 1")
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = (config.lago / "preparo.json").read_bytes()
    regra.write_text("select 2")
    with pytest.raises(ErroPreparo):
        preparar(config, {}, construtor_c2(config, chamadas, 1), lambda: AGORA)
    assert (config.lago / "preparo.json").read_bytes() == marca
    # Regras/dados/saída antiga íntegros novamente, mas o banco foi alterado pelo build falho.
    regra.write_text("select 1")
    executor = ExecutorFalso(config, {})
    deps = Dependencias(
        config,
        executor,
        lambda: preparar(config, {}, construtor_c2(config, chamadas, 1)),
        lambda: AGORA,
    )
    controlador = Controlador(deps)
    with pytest.raises(ErroPreparo):
        controlador.executar(controlador.nova(None))
    assert len(chamadas) == 3
    assert executor.pedidos == []
    assert (config.lago / "preparo.json").read_bytes() == marca
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 4
    assert not preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou


def test_falha_escrita_trava_nao_inicia_build(c2, monkeypatch):
    import agente.preparar as modulo

    config, _ = c2
    chamadas = []
    original = modulo._gravar_marca

    def falhar(caminho, dados):
        if caminho.name == "preparo-c2-pendente.json":
            raise OSError("disco indisponível")
        original(caminho, dados)

    monkeypatch.setattr(modulo, "_gravar_marca", falhar)
    with pytest.raises(ErroPreparo, match="disco"):
        preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    assert chamadas == []
    assert not (config.lago / "preparo.json").exists()


def test_crash_antes_marca_exige_rebuild(c2, monkeypatch):
    import agente.preparar as modulo

    config, _ = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = (config.lago / "preparo.json").read_bytes()
    import json

    saida = Path(json.loads(marca)["tse"]["saida"]) / "c2.parquet"
    original_saida = saida.read_bytes()
    saida.unlink()
    original = modulo._gravar_marca

    def interromper(caminho, dados):
        if caminho.name == "preparo.json":
            raise KeyboardInterrupt("crash antes da marca")
        original(caminho, dados)

    with monkeypatch.context() as contexto:
        contexto.setattr(modulo, "_gravar_marca", interromper)
        with pytest.raises(KeyboardInterrupt):
            preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    assert (config.lago / "preparo.json").read_bytes() == marca
    # Mesmo restaurando os bytes antigos, o banco parcialmente alterado não fica autorizado.
    saida.write_bytes(original_saida)
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 3


@pytest.mark.parametrize("fase", ["contexto", "revisao"])
def test_falha_contexto_revisao_conserva_marca_e_pendencia(c2, monkeypatch, fase):
    import agente.preparar as modulo

    config, _ = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    marca = (config.lago / "preparo.json").read_bytes()
    regra = config.raiz / "dbt/models/staging/tse/novo.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("select 1")

    def falhar(*args, **kwargs):
        raise OSError("falha " + fase)

    monkeypatch.setattr(
        modulo, "gerar_contexto" if fase == "contexto" else "revisar_caderno", falhar
    )
    with pytest.raises((ErroPreparo, OSError)):
        preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    assert (config.lago / "preparo.json").read_bytes() == marca
    assert (config.lago / "preparo-c2-pendente.json").exists()


def test_falha_limpeza_pos_commit_mantem_bloqueio(c2, monkeypatch):
    import json

    config, _ = c2
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    antiga = (config.lago / "preparo.json").read_bytes()
    regra = config.raiz / "dbt/models/staging/tse/nova.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("select 2")
    original = Path.unlink

    def falhar(caminho, *args, **kwargs):
        if caminho.name == "preparo-c2-pendente.json":
            raise OSError("limpeza indisponível")
        return original(caminho, *args, **kwargs)

    with monkeypatch.context() as contexto:
        contexto.setattr(Path, "unlink", falhar)
        with pytest.raises(ErroPreparo, match="limpeza"):
            preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    nova = (config.lago / "preparo.json").read_bytes()
    assert nova != antiga and json.loads(nova)["dbt"] == "sucesso"
    with pytest.raises(ValueError, match="pendente"):
        config.diretorios_permitidos()
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 3


def test_pendencia_local_nao_entra_impressao(c2):
    config, _ = c2
    antes = impressao_lago(config.lago)
    (config.lago / "preparo-c2-pendente.json").write_bytes(b"qualquer conteudo")
    assert impressao_lago(config.lago) == antes


def test_macro_compartilhada_alterada_refaz_c2(c2):
    config, _ = c2
    macro = config.raiz / "dbt/macros/documentos.sql"
    macro.parent.mkdir(parents=True, exist_ok=True)
    macro.write_text("macro vigente")
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    macro.write_text("macro alterada")
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2


def test_teste_generico_privacidade_alterado_refaz_c2(c2):
    config, _ = c2
    regra = config.raiz / "dbt/tests/generic/sem_cpf_completo.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("regra vigente")
    chamadas = []
    preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA)
    regra.write_text("regra alterada")
    assert preparar(config, {}, construtor_c2(config, chamadas), lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2


def test_sync_diretorio_apos_replace_antes_build_e_liberacao(c2, monkeypatch):
    import agente.preparar as modulo

    config, _ = c2
    eventos = []
    original_replace = modulo.os.replace
    original_unlink = Path.unlink

    def substituir(origem, destino):
        original_replace(origem, destino)
        if Path(destino).name in ("preparo-c2-pendente.json", "preparo.json"):
            eventos.append(("replace", Path(destino).name))

    def sincronizar(pasta):
        assert pasta == config.lago
        eventos.append(("sync", "lago"))

    def remover(caminho, *args, **kwargs):
        if caminho.name == "preparo-c2-pendente.json":
            eventos.append(("unlink", caminho.name))
        return original_unlink(caminho, *args, **kwargs)

    construtor = construtor_c2(config, [])

    def rodar(comando, env, cwd):
        if "build" in comando:
            eventos.append(("build", "agente"))
        return construtor(comando, env, cwd)

    monkeypatch.setattr(modulo.os, "replace", substituir)
    monkeypatch.setattr(modulo, "sincronizar_pasta", sincronizar, raising=False)
    monkeypatch.setattr(Path, "unlink", remover)
    preparar(config, {}, rodar, lambda: AGORA)
    assert eventos == [
        ("replace", "preparo-c2-pendente.json"),
        ("sync", "lago"),
        ("build", "agente"),
        ("replace", "preparo.json"),
        ("sync", "lago"),
        ("unlink", "preparo-c2-pendente.json"),
    ]


@pytest.mark.parametrize("etapa", ["pendencia", "marca"])
def test_falha_sync_diretorio_bloqueia_build_ou_liberacao(c2, monkeypatch, etapa):
    import json

    import agente.preparar as modulo
    from agente.controlador import Controlador, Dependencias
    from tests.agente.test_controlador import ExecutorFalso

    config, _ = c2
    marca = config.lago / "preparo.json"
    antiga = b'{"impressao":"anterior"}'
    marca.write_bytes(antiga)
    sincronizacoes = []

    def falhar(pasta):
        sincronizacoes.append(pasta)
        if len(sincronizacoes) == (1 if etapa == "pendencia" else 2):
            raise OSError("falha sync " + etapa)

    monkeypatch.setattr(modulo, "sincronizar_pasta", falhar, raising=False)
    chamadas = []
    executor = ExecutorFalso(config, {})
    deps = Dependencias(
        config,
        executor,
        lambda: preparar(config, {}, construtor_c2(config, chamadas)),
        lambda: AGORA,
    )
    controlador = Controlador(deps)
    with pytest.raises(ErroPreparo, match="falha sync " + etapa):
        controlador.executar(controlador.nova(None))
    assert executor.pedidos == []
    assert (config.lago / "preparo-c2-pendente.json").exists()
    with pytest.raises(ValueError, match="pendente"):
        config.diretorios_permitidos()
    if etapa == "pendencia":
        assert chamadas == []
        assert marca.read_bytes() == antiga
    else:
        assert len(chamadas) == 1
        # Rename já ocorreu: nova marca visível não prova persistência após falha de fsync.
        assert marca.read_bytes() != antiga
        assert json.loads(marca.read_bytes())["dbt"] == "sucesso"


def test_meta_coletas_alterado_invalida_cache_c2_causalmente(c2):
    import json

    from agente.preparar import _regras_c2

    config, _ = c2
    regra = config.raiz / "dbt/models/staging/stg_meta__coletas.sql"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("select sha256_arquivo from fonte", encoding="utf-8")
    chamadas = []
    construtor = construtor_c2(config, chamadas)
    assert preparar(config, {}, construtor, lambda: AGORA).dbt_rodou
    assert not preparar(config, {}, construtor, lambda: AGORA).dbt_rodou
    assert len(chamadas) == 1
    marca = config.lago / "preparo.json"
    marca_antes = marca.read_bytes()
    saida = Path(json.loads(marca_antes)["tse"]["saida"]) / "c2.parquet"
    saida_antes = saida.read_bytes()
    lago_antes = impressao_lago(config.lago)
    regras_antes = _regras_c2(config.raiz)
    regra.write_text("select sha256_conteudo from fonte", encoding="utf-8")
    assert marca.read_bytes() == marca_antes
    assert saida.read_bytes() == saida_antes
    assert impressao_lago(config.lago) == lago_antes
    assert _regras_c2(config.raiz) != regras_antes
    assert preparar(config, {}, construtor, lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2
    assert not preparar(config, {}, construtor, lambda: AGORA).dbt_rodou
    assert len(chamadas) == 2
