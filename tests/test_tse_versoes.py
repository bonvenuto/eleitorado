"""Versões TSE sintéticas: preservação física, proveniência e repetição segura."""

import json
from dataclasses import replace

import httpx
import pyarrow.parquet as pq
import pytest

from coletor.adaptadores.base import ErroColeta, Extracao
from coletor.adaptadores.tse_zip import preparar_familias
from coletor.coleta import coletar
from coletor.competencias import Competencia
from coletor.conversao import Controle
from coletor.hashes import sha256_arquivo
from coletor.lago import LagoWarehouse
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas
from coletor.tse.versoes import gravar_versao
from tests.amostras import AGORA
from tests.amostras_tse import recurso_tse, zip_tse
from tests.test_tse_zip import CABECALHOS, csv_sintetico


def entrada(tmp_path, geracao="01/10/2026", duplicatas=1, recurso_id="bens"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    recurso = RecursoCompleto("tse", recurso_tse(recurso_id))
    membros = {}
    for template in recurso.recurso.familias.values():
        nome = template.format(ano=2024)
        header = CABECALHOS[2024, nome]
        linha = ["sintético"] * len(header)
        linha[header.index("DT_GERACAO")] = geracao
        linha[header.index("HH_GERACAO")] = "12:00:00"
        membros[nome] = csv_sintetico(header, [linha] * duplicatas)
    original = tmp_path / "original.zip"
    original.write_bytes(zip_tse(membros))
    comp = Competencia.de_ano(2024)
    extracao = Extracao(
        comp,
        original,
        "zip",
        recurso.recurso.url.format(ano=2024),
        200,
        original.stat().st_size,
        sha256_arquivo(original),
    )
    familias = preparar_familias(recurso.recurso, comp, original, tmp_path)
    controle = Controle("coleta-1", "2024", comp.data, "gs://teste/original.zip", AGORA)
    return recurso, extracao, familias, controle


def test_duas_versoes_preservadas(tmp_path):
    lago = tmp_path / "lago"
    primeira = gravar_versao(lago, *entrada(tmp_path / "a"))
    antigo = lago / primeira.familias["bens"]
    conteudo = antigo.read_bytes()
    segunda = gravar_versao(lago, *entrada(tmp_path / "b", "02/10/2026"))
    assert primeira.versao_id != segunda.versao_id
    assert primeira.sha256_zip != segunda.sha256_zip
    assert primeira.sha256_semantico == segunda.sha256_semantico
    assert antigo.read_bytes() == conteudo
    assert len(list(lago.glob("raw/tse/bens/2024/*/dados.parquet"))) == 2
    assert pq.read_table(antigo).column("dt_geracao").to_pylist() == ["01/10/2026"]
    assert len(list(lago.glob("estado/tse/versoes/*.json"))) == 2


def test_mesmo_hash_nao_regrava(tmp_path, monkeypatch):
    from coletor.tse import versoes

    gravacoes = 0
    converter = versoes.csv_para_parquet

    def contar(*args, **kwargs):
        nonlocal gravacoes
        gravacoes += 1
        return converter(*args, **kwargs)

    monkeypatch.setattr(versoes, "csv_para_parquet", contar)
    args = entrada(tmp_path / "entrada")
    primeira = gravar_versao(tmp_path / "lago", *args)
    descritor = tmp_path / "lago/estado/tse/versoes" / f"{primeira.versao_id}.json"
    conteudo = descritor.read_bytes()
    segunda = gravar_versao(tmp_path / "lago", *args[:-1], replace(args[-1], coleta_id="outra"))
    assert primeira == segunda
    assert gravacoes == 1
    assert descritor.read_bytes() == conteudo


def test_colisao_raw_falha_sem_sobrescrever(tmp_path):
    lago = tmp_path / "lago"
    args = entrada(tmp_path / "entrada")
    versao = gravar_versao(lago, *args)
    destino = lago / versao.familias["bens"]
    destino.write_bytes(b"corrupcao")
    with pytest.raises(ErroColeta, match="integridade|colisão"):
        gravar_versao(lago, *args)
    assert destino.read_bytes() == b"corrupcao"


def test_hash_declarado_divergente_falha(tmp_path):
    recurso, extracao, familias, controle = entrada(tmp_path / "entrada")
    with pytest.raises(ErroColeta, match="hash"):
        gravar_versao(
            tmp_path / "lago",
            recurso,
            replace(extracao, sha256_arquivo="0" * 64),
            familias,
            controle,
        )
    assert not list((tmp_path / "lago").rglob("*.parquet"))


def test_semantico_preserva_multiplicidade(tmp_path):
    a = gravar_versao(tmp_path / "lago", *entrada(tmp_path / "a"))
    b = gravar_versao(tmp_path / "lago", *entrada(tmp_path / "b", duplicatas=2))
    assert a.sha256_semantico != b.sha256_semantico
    assert pq.read_table(tmp_path / "lago" / b.familias["bens"]).num_rows == 2


def test_contas_um_arquivo_quatro_familias_e_repeticao(tmp_path, deps, respx_mock):
    recurso, extracao, _, _ = entrada(tmp_path / "entrada", recurso_id="contas")
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    deps.warehouse = LagoWarehouse(deps.config.lago)
    rota = respx_mock.get(extracao.url).mock(
        return_value=httpx.Response(200, content=extracao.arquivo_original.read_bytes())
    )
    chamadas = []
    enviar = deps.armazenamento.enviar

    def contar(origem, caminho):
        chamadas.append(caminho)
        return enviar(origem, caminho)

    deps.armazenamento.enviar = contar
    historico = HistoricoColetas()
    primeiro = coletar(recurso, extracao.competencia, historico, deps, "exec-1")
    assert primeiro.status == "carregada", primeiro.erro
    historico.registrar(primeiro)
    segundo = coletar(recurso, extracao.competencia, historico, deps, "exec-2", forcar=True)
    assert segundo.status == "sem_alteracao", segundo.erro
    assert len(chamadas) == 1
    assert rota.call_count == 2
    assert len(primeiro.parametros["familias"]) == 4
    versao_id = primeiro.parametros["versao_id"]
    assert len(versao_id) == 64 and int(versao_id, 16)
    descritor = json.loads(
        (deps.config.lago / "estado/tse/versoes" / f"{versao_id}.json").read_text(encoding="utf-8")
    )
    assert descritor["url"] == extracao.url
    assert descritor["arquivo_original"] == primeiro.arquivo_original
    assert descritor["contagens"] == {
        "receitas": 1,
        "contratadas": 1,
        "pagamentos": 1,
        "doador_originario": 1,
    }
    assert descritor["geracoes"]["receitas"] == [["01/10/2026", "12:00:00"]]


def test_repeticao_revalida_csv_invalido(tmp_path, deps, respx_mock):
    recurso = RecursoCompleto("tse", recurso_tse("bens"))
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    corpo = zip_tse({"bem_candidato_2024_BRASIL.csv": b"invalido"})
    respx_mock.get(recurso.recurso.url.format(ano=2024)).mock(
        return_value=httpx.Response(200, content=corpo)
    )
    historico = HistoricoColetas()
    for _ in range(2):
        registro = coletar(recurso, Competencia.de_ano(2024), historico, deps, "exec")
        historico.registrar(registro)
        assert registro.status == "falha"
    assert not list(deps.config.lago.rglob("*.parquet"))


def test_rejeicao_persistida_nao_vira_sucesso_por_hash(tmp_path, deps, respx_mock):
    from coletor.adaptadores import tse_zip

    recurso, extracao, _, _ = entrada(tmp_path / "entrada")
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    respx_mock.get(extracao.url).mock(
        return_value=httpx.Response(200, content=extracao.arquivo_original.read_bytes())
    )
    primeiro = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec-1")
    assert primeiro.status == "carregada", primeiro.erro
    preparar = tse_zip.preparar_familias

    def rejeitar(*args, **kwargs):
        raise ErroColeta("layout incompatível comprovado")

    # Simula a descoberta de incompatibilidade com o contrato de validação vigente.
    tse_zip.preparar_familias = rejeitar
    try:
        rejeitado = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec-2")
    finally:
        tse_zip.preparar_familias = preparar
    assert rejeitado.status == "falha"
    repetido = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec-3")
    assert repetido.status == "falha"
    assert "rejeição" in repetido.erro
    avaliacoes = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in deps.config.lago.glob("estado/tse/validacoes/*.json")
    ]
    assert any(a["resultado"] == "rejeitada" for a in avaliacoes)


def test_falha_transitoria_permite_recuperar(tmp_path, deps, respx_mock):
    recurso, extracao, _, _ = entrada(tmp_path / "entrada")
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    respx_mock.get(extracao.url).mock(
        return_value=httpx.Response(200, content=extracao.arquivo_original.read_bytes())
    )
    enviar = deps.armazenamento.enviar

    def falhar(*args, **kwargs):
        raise OSError("disco temporariamente indisponível")

    deps.armazenamento.enviar = falhar
    falha = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec-1")
    assert falha.status == "falha"
    deps.armazenamento.enviar = enviar
    recuperado = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec-2")
    assert recuperado.status == "carregada", recuperado.erro
    avaliacoes = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in deps.config.lago.glob("estado/tse/validacoes/*.json")
    ]
    assert not any(a["resultado"] == "rejeitada" for a in avaliacoes)


def test_falha_ao_preparar_tentativa_preserva_raw_e_permite_repetir(tmp_path, monkeypatch):
    from coletor.tse import versoes

    lago = tmp_path / "lago"
    anterior = gravar_versao(lago, *entrada(tmp_path / "anterior"))
    preservado = (lago / anterior.familias["bens"]).read_bytes()
    args = entrada(tmp_path / "entrada", recurso_id="contas")
    copiar = versoes.shutil.copyfileobj
    chamadas = 0

    def falhar(origem, destino):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 2:
            raise OSError("disco indisponível")
        copiar(origem, destino)

    monkeypatch.setattr(versoes.shutil, "copyfileobj", falhar)
    with pytest.raises(OSError, match="disco indisponível"):
        gravar_versao(lago, *args)
    assert len(list(lago.glob("raw/**/*.parquet"))) == 1
    assert (lago / anterior.familias["bens"]).read_bytes() == preservado
    monkeypatch.setattr(versoes.shutil, "copyfileobj", copiar)
    recuperada = gravar_versao(lago, *args)
    assert len(recuperada.familias) == 4


def test_aprovacao_antiga_nao_supera_rejeicao_sem_referencias(tmp_path):
    from coletor.tse.validacoes import gravar_avaliacao, rejeicoes_pendentes

    chave = dict(
        escopo="versao", identidade="a" * 64, entradas_digest="b" * 64, contrato="tse:estrutura:v1"
    )
    rejeitada = gravar_avaliacao(
        tmp_path,
        **chave,
        execucao_id="exec-1",
        resultado="rejeitada",
        motivos=[{"codigo": "layout"}],
    )
    gravar_avaliacao(
        tmp_path,
        **chave,
        execucao_id="exec-2",
        resultado="aprovada",
        motivos=[],
        evidencia="avaliação completa",
    )
    assert rejeicoes_pendentes(tmp_path, **chave) == [rejeitada]
    gravar_avaliacao(
        tmp_path,
        **chave,
        execucao_id="exec-3",
        resultado="aprovada",
        motivos=[],
        evidencia="nova avaliação completa",
        superadas=(rejeitada,),
    )
    assert rejeicoes_pendentes(tmp_path, **chave) == []
    assert len(list(tmp_path.glob("estado/tse/validacoes/*.json"))) == 3
    outra_selecao = dict(chave, escopo="selecao", identidade="c" * 64)
    gravar_avaliacao(
        tmp_path,
        **outra_selecao,
        execucao_id="exec-4",
        resultado="rejeitada",
        motivos=[{"codigo": "conjunto_incoerente"}],
    )
    assert rejeicoes_pendentes(tmp_path, **chave) == []


@pytest.mark.parametrize("defeito", ["inexistente", "outra_identidade", "digest_invalido"])
def test_avaliacao_impede_referencia_alheia_ou_inexistente(tmp_path, defeito):
    from coletor.tse.validacoes import gravar_avaliacao

    chave = dict(
        escopo="versao", identidade="a" * 64, entradas_digest="b" * 64, contrato="tse:estrutura:v1"
    )
    rejeitada = gravar_avaliacao(
        tmp_path,
        **chave,
        execucao_id="exec-1",
        resultado="rejeitada",
        motivos=[{"codigo": "layout"}],
    )
    if defeito == "inexistente":
        rejeitada = "0" * 64
    elif defeito == "outra_identidade":
        chave["identidade"] = "c" * 64
    else:
        chave["entradas_digest"] = "../invalido"
    with pytest.raises(ValueError):
        gravar_avaliacao(
            tmp_path,
            **chave,
            execucao_id="exec-2",
            resultado="aprovada",
            motivos=[],
            evidencia="avaliação completa",
            superadas=(rejeitada,),
        )


def test_raw_orfao_sem_descritor_falha_preservando_bytes(tmp_path, deps, respx_mock):
    recurso, extracao, _, _ = entrada(tmp_path / "entrada")
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    orfao = deps.config.lago / f"raw/tse/bens/2024/{extracao.sha256_arquivo}/dados.parquet"
    orfao.parent.mkdir(parents=True)
    orfao.write_bytes(b"copia interrompida")
    respx_mock.get(extracao.url).mock(
        return_value=httpx.Response(200, content=extracao.arquivo_original.read_bytes())
    )
    registro = coletar(recurso, extracao.competencia, HistoricoColetas(), deps, "exec")
    assert registro.status == "falha"
    assert "colisão de caminho raw" in registro.erro
    assert orfao.read_bytes() == b"copia interrompida"
    assert not list(deps.config.lago.glob("estado/tse/versoes/*.json"))
    assert not list(deps.config.lago.glob("estado/tse/validacoes/*.json"))


@pytest.mark.parametrize(
    "momento", ["antes_raw", "entre_familias", "antes_descritor", "depois_descritor"]
)
def test_interrupcao_retoma_tentativa_duravel(tmp_path, monkeypatch, momento):
    from coletor.tse import versoes

    lago = tmp_path / "lago"
    anterior = gravar_versao(lago, *entrada(tmp_path / "anterior"))
    preservado = (lago / anterior.familias["bens"]).read_bytes()
    args = entrada(tmp_path / "entrada", recurso_id="contas")
    link = versoes.os.link
    instalados = 0

    class Interrupcao(BaseException):
        pass

    def interromper(origem, destino):
        nonlocal instalados
        destino = str(destino).replace("\\", "/")
        if "/raw/tse/" in destino:
            instalados += 1
            if (momento == "entre_familias" and instalados == 2) or momento == "antes_raw":
                raise Interrupcao()
        if "/estado/tse/versoes/" in destino and momento == "antes_descritor":
            raise Interrupcao()
        link(origem, destino)
        if "/estado/tse/versoes/" in destino and momento == "depois_descritor":
            raise Interrupcao()

    monkeypatch.setattr(versoes.os, "link", interromper)
    with pytest.raises(Interrupcao):
        gravar_versao(lago, *args)
    monkeypatch.setattr(versoes.os, "link", link)
    recuperada = gravar_versao(lago, *args[:-1], replace(args[-1], coleta_id="retomada"))
    assert len(recuperada.familias) == 4
    for caminho in recuperada.familias.values():
        tabela = pq.read_table(lago / caminho)
        assert tabela.column("_coleta_id").to_pylist() == ["coleta-1"]
    assert (lago / anterior.familias["bens"]).read_bytes() == preservado
    assert len(list(lago.glob("estado/tse/tentativas/*/manifesto.json"))) == 2


def test_zip_rejeitado_arquivado_sem_duplicacao(tmp_path, deps, respx_mock):
    recurso = RecursoCompleto("tse", recurso_tse("bens"))
    deps.config = replace(deps.config, lago=tmp_path / "lago")
    corpo = zip_tse({"bem_candidato_2024_BRASIL.csv": b"layout invalido"})
    respx_mock.get(recurso.recurso.url.format(ano=2024)).mock(
        return_value=httpx.Response(200, content=corpo)
    )
    enviar = deps.armazenamento.enviar
    chamadas = []

    def contar(origem, caminho):
        chamadas.append(caminho)
        return enviar(origem, caminho)

    deps.armazenamento.enviar = contar
    for execucao in ("exec-1", "exec-2"):
        registro = coletar(recurso, Competencia.de_ano(2024), HistoricoColetas(), deps, execucao)
        assert registro.status == "falha"
        assert registro.arquivo_original.startswith("gs://bucket-teste/")
    assert len(chamadas) == 1
    assert len(deps.armazenamento.objetos) == 1
    assert next(iter(deps.armazenamento.objetos.values())).read_bytes() == corpo
    assert not list(deps.config.lago.glob("estado/tse/versoes/*.json"))
    assert not list(deps.config.lago.glob("raw/**/*.parquet"))
    for caminho in deps.config.lago.glob("estado/tse/validacoes/*.json"):
        avaliacao = json.loads(caminho.read_text(encoding="utf-8"))
        assert avaliacao["evidencia"] == registro.arquivo_original


@pytest.mark.parametrize("defeito", ["manifesto", "parquet"])
def test_tentativa_duravel_corrompida_nao_adota_raw(tmp_path, monkeypatch, defeito):
    from coletor.tse import versoes

    lago = tmp_path / "lago"
    args = entrada(tmp_path / "entrada", recurso_id="contas")
    link = versoes.os.link

    class Interrupcao(BaseException):
        pass

    def interromper(origem, destino):
        if "/raw/tse/" in str(destino).replace("\\", "/"):
            raise Interrupcao()
        link(origem, destino)

    monkeypatch.setattr(versoes.os, "link", interromper)
    with pytest.raises(Interrupcao):
        gravar_versao(lago, *args)
    monkeypatch.setattr(versoes.os, "link", link)
    tentativa = next((lago / "estado/tse/tentativas").iterdir())
    if defeito == "manifesto":
        manifesto = tentativa / "manifesto.json"
        envelope = json.loads(manifesto.read_text(encoding="utf-8"))
        envelope["dados"]["controle"]["coleta_id"] = "alheia"
        manifesto.write_text(json.dumps(envelope), encoding="utf-8")
    else:
        next(tentativa.glob("*.parquet")).write_bytes(b"corrompido")
    with pytest.raises(ErroColeta, match="integridade"):
        gravar_versao(lago, *args)
    assert not list(lago.glob("raw/**/*.parquet"))
    assert not list(lago.glob("estado/tse/versoes/*.json"))


def test_interrupcao_apos_instalar_tentativa_retoma(tmp_path, monkeypatch):
    from coletor.tse import versoes

    lago = tmp_path / "lago"
    args = entrada(tmp_path / "entrada")
    renomear = versoes.os.rename

    class Interrupcao(BaseException):
        pass

    def interromper(origem, destino):
        renomear(origem, destino)
        raise Interrupcao()

    monkeypatch.setattr(versoes.os, "rename", interromper)
    with pytest.raises(Interrupcao):
        gravar_versao(lago, *args)
    monkeypatch.setattr(versoes.os, "rename", renomear)
    assert not list(lago.glob("raw/**/*.parquet"))
    recuperada = gravar_versao(lago, *args)
    assert pq.read_table(lago / recuperada.familias["bens"]).num_rows == 1
