"""Sincronia TSE privada sem rede, com restauro conservador."""

import json
from dataclasses import asdict

import pytest

from coletor import estado
from coletor.tse.selecao import promover_selecao
from tests.fakes import FakeArmazenamento
from tests.test_estado import _arquivo
from tests.test_tse_selecao import execucao, montar_vetor

PREFIXO = "privado/"


def operacoes():
    from coletor.tse.estado import restaurar_tse, salvar_tse

    return salvar_tse, restaurar_tse


def remoto(tmp_path):
    lago, selecao = montar_vetor(tmp_path)
    promover_selecao(lago, selecao, execucao(lago, selecao))
    gcs = FakeArmazenamento(tmp_path / "bucket")
    for arquivo in lago.rglob("*"):
        if arquivo.is_file():
            gcs.enviar(arquivo, PREFIXO + arquivo.relative_to(lago).as_posix())
    return lago, selecao, gcs


def test_espelho_legado_preserva_tse(tmp_path):
    gcs = FakeArmazenamento(tmp_path / "bucket")
    anterior = tmp_path / "anterior"
    caminhos = [
        "raw/tse/bens/2024/hash/dados.parquet",
        "estado/tse/vigente.json",
        "estado/tse/inicializado.json",
        "estado/tse/tentativas/id/manifesto.json",
    ]
    for caminho in caminhos:
        gcs.enviar(_arquivo(anterior, caminho), PREFIXO + caminho)
    incompleto = tmp_path / "incompleto"
    _arquivo(incompleto, caminhos[0], b"divergente")
    estado.salvar(gcs, PREFIXO, incompleto, tmp_path / "ausente.duckdb")
    apagados_tse = [c for c in caminhos if PREFIXO + c not in gcs.objetos]
    assert apagados_tse == []
    assert gcs.objetos[PREFIXO + caminhos[0]].read_bytes() == b"x"


@pytest.mark.parametrize("defeito", ["hash", "dependencia", "marcador", "selecao", "download"])
def test_restauro_parcial_conserva_seletor(tmp_path, defeito):
    _, restaurar_tse = operacoes()
    lago, selecao, gcs = remoto(tmp_path)
    local = tmp_path / "local"
    anterior = _arquivo(local, "estado/tse/vigente.json", b"seletor anterior")
    _arquivo(local, "estado/tse/inicializado.json", b"marcador anterior")
    if defeito == "hash":
        raw = next(c for c in gcs.objetos if c.startswith(PREFIXO + "raw/"))
        gcs.objetos[raw].write_bytes(b"corrompido")
    elif defeito == "dependencia":
        del gcs.objetos[next(c for c in gcs.objetos if c.startswith(PREFIXO + "raw/"))]
    elif defeito == "marcador":
        del gcs.objetos[PREFIXO + "estado/tse/vigente.json"]
    elif defeito == "selecao":
        del gcs.objetos[PREFIXO + f"estado/tse/selecoes/{selecao.selecao_id}.json"]
    else:

        def falhar(caminho, destino):
            destino.write_bytes(b"parcial")
            raise OSError("download interrompido")

        gcs.baixar = falhar
    with pytest.raises((ValueError, OSError)):
        restaurar_tse(gcs, PREFIXO, local)
    assert anterior.read_bytes() == b"seletor anterior"
    assert (local / "estado/tse/inicializado.json").read_bytes() == b"marcador anterior"
    assert sorted(p.relative_to(local).as_posix() for p in local.rglob("*") if p.is_file()) == [
        "estado/tse/inicializado.json",
        "estado/tse/vigente.json",
    ]


def test_salvar_restaurar_idempotente_sem_publicacao_preparada(tmp_path):
    salvar_tse, restaurar_tse = operacoes()
    lago, selecao, _ = remoto(tmp_path)
    import shutil

    pasta = lago / "estado/tse/publicacoes/preparadas/execucao-1"
    for p in pasta.iterdir():
        if p.name == "recibo.json":
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    _arquivo(lago, "estado/tse/tentativas/.preparacao-abc/incompleto.parquet")
    gcs = FakeArmazenamento(tmp_path / "outro-bucket")
    assert salvar_tse(gcs, PREFIXO, lago).enviados > 0
    assert salvar_tse(gcs, PREFIXO, lago).enviados == 0
    assert not any(".preparacao-" in c for c in gcs.objetos)
    local = tmp_path / "restaurado"
    assert restaurar_tse(gcs, PREFIXO, local).baixados > 0
    assert json.loads((local / "estado/tse/vigente.json").read_bytes()) == asdict(selecao)
    antes = {
        p.relative_to(local).as_posix(): p.read_bytes() for p in local.rglob("*") if p.is_file()
    }
    assert restaurar_tse(gcs, PREFIXO, local).baixados == len(gcs.objetos)
    assert {
        p.relative_to(local).as_posix(): p.read_bytes() for p in local.rglob("*") if p.is_file()
    } == antes


def test_salvar_colisao_imutavel_nao_altera_bucket(tmp_path):
    salvar_tse, _ = operacoes()
    lago, _, gcs = remoto(tmp_path)
    raw = next(lago.glob("raw/tse/*/*/*/dados.parquet"))
    raw.write_bytes(b"divergente")
    antes = {c: p.read_bytes() for c, p in gcs.objetos.items()}
    with pytest.raises(ValueError):
        salvar_tse(gcs, PREFIXO, lago)
    assert {c: p.read_bytes() for c, p in gcs.objetos.items()} == antes


def test_restauro_generico_nao_sobrescreve_tse(tmp_path):
    gcs = FakeArmazenamento(tmp_path / "bucket")
    gcs.enviar(
        _arquivo(tmp_path / "origem", "estado/tse/vigente.json", b"remoto"),
        PREFIXO + "estado/tse/vigente.json",
    )
    local = tmp_path / "local"
    _arquivo(local, "estado/tse/vigente.json", b"anterior")
    estado.restaurar(gcs, PREFIXO, local, tmp_path / "banco.duckdb")
    assert (local / "estado/tse/vigente.json").read_bytes() == b"anterior"


@pytest.mark.parametrize("aditivo", [False, True])
def test_generico_nunca_envia_tse(tmp_path, aditivo):
    lago = tmp_path / "lago"
    _arquivo(lago, "raw/tse/bens/2024/hash/dados.parquet")
    _arquivo(lago, "estado/tse/vigente.json")
    _arquivo(lago, "raw/rfb/empresas/2026/dados.parquet")
    gcs = FakeArmazenamento(tmp_path / "bucket")
    estado.salvar(gcs, PREFIXO, lago, tmp_path / "ausente.duckdb", aditivo=aditivo)
    assert sorted(gcs.objetos) == [PREFIXO + "raw/rfb/empresas/2026/dados.parquet"]


def test_salvar_imutaveis_antes_seletor_e_marcador(tmp_path):
    salvar_tse, _ = operacoes()
    lago, _, _ = remoto(tmp_path)

    class FalhaNoSeletor(FakeArmazenamento):
        def substituir(self, origem, caminho):
            if caminho.endswith("/vigente.json"):
                raise OSError("interrompido antes do seletor")
            super().substituir(origem, caminho)

    gcs = FalhaNoSeletor(tmp_path / "bucket-ordem")
    with pytest.raises(OSError):
        salvar_tse(gcs, PREFIXO, lago)
    assert any("/selecoes/" in c for c in gcs.objetos)
    assert any("/validacoes/" in c for c in gcs.objetos)
    assert not any(c.endswith(("/vigente.json", "/inicializado.json")) for c in gcs.objetos)


def test_restauro_colisao_local_preserva_hardlink(tmp_path):
    import os

    _, restaurar_tse = operacoes()
    _, _, gcs = remoto(tmp_path)
    local = tmp_path / "local"
    relativo = next(c.removeprefix(PREFIXO) for c in gcs.objetos if "/raw/tse/" in c)
    raw = _arquivo(local, relativo, b"raw local anterior")
    link = tmp_path / "tentativa-link.parquet"
    os.link(raw, link)
    with pytest.raises(ValueError, match="imutável"):
        restaurar_tse(gcs, PREFIXO, local)
    assert raw.read_bytes() == link.read_bytes() == b"raw local anterior"


@pytest.mark.parametrize("defeito", ["ausente", "corrompido", "referencia"])
def test_recibo_integro_obrigatorio_para_restauro(tmp_path, defeito):
    _, restaurar_tse = operacoes()
    _, _, gcs = remoto(tmp_path)
    caminho = PREFIXO + "estado/tse/publicacoes/preparadas/execucao-1/recibo.json"
    if defeito == "ausente":
        del gcs.objetos[caminho]
    else:
        dados = json.loads(gcs.objetos[caminho].read_bytes())
        if defeito == "corrompido":
            dados["recibo"]["entradas_digest"] = "0" * 64
        else:
            dados["superadas"] = ["0" * 64]
        gcs.objetos[caminho].write_text(json.dumps(dados), encoding="utf-8")
    local = tmp_path / "local"
    with pytest.raises(ValueError):
        restaurar_tse(gcs, PREFIXO, local)
    assert not local.exists()


def test_backup_antigo_nao_ignora_rejeicao_local(tmp_path):
    from coletor.tse.selecao import digest_entradas
    from coletor.tse.validacoes import gravar_avaliacao

    _, restaurar_tse = operacoes()
    lago, selecao, gcs = remoto(tmp_path)
    anterior = (lago / "estado/tse/vigente.json").read_bytes()
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(lago, selecao),
        contrato="tse:selecao:v1",
        execucao_id="posterior",
        resultado="rejeitada",
        motivos=[],
    )
    with pytest.raises(ValueError):
        restaurar_tse(gcs, PREFIXO, lago)
    assert (lago / "estado/tse/vigente.json").read_bytes() == anterior
    assert (lago / f"estado/tse/validacoes/{rejeicao}.json").is_file()


def test_marcador_local_nao_pode_ser_substituido(tmp_path):
    _, restaurar_tse = operacoes()
    lago, _, gcs = remoto(tmp_path)
    marcador = lago / "estado/tse/inicializado.json"
    anterior = b'{"protocolo":"tse:inicializado:v1","primeira_selecao_id":"outra"}'
    marcador.write_bytes(anterior)
    with pytest.raises(ValueError):
        restaurar_tse(gcs, PREFIXO, lago)
    assert marcador.read_bytes() == anterior


def test_salvar_nao_ignora_rejeicao_remota(tmp_path):
    from coletor.tse.selecao import digest_entradas
    from coletor.tse.validacoes import gravar_avaliacao

    salvar_tse, _ = operacoes()
    lago, selecao, gcs = remoto(tmp_path)
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(lago, selecao),
        contrato="tse:selecao:v1",
        execucao_id="posterior",
        resultado="rejeitada",
        motivos=[],
    )
    caminho = lago / f"estado/tse/validacoes/{rejeicao}.json"
    gcs.enviar(caminho, PREFIXO + caminho.relative_to(lago).as_posix())
    caminho.unlink()
    with pytest.raises(ValueError):
        salvar_tse(gcs, PREFIXO, lago)


@pytest.mark.parametrize("defeito", [None, "manifesto", "hash", "referencia"])
def test_estado_preparado_privado_verificavel(tmp_path, defeito):
    from coletor.hashes import sha256_arquivo
    from coletor.tse.durabilidade import gravar_json
    from coletor.tse.validacoes import gravar_avaliacao

    salvar_tse, restaurar_tse = operacoes()
    lago = tmp_path / "lago"
    identidade = "a" * 64
    tentativa = lago / f"estado/tse/tentativas/{identidade}"
    parquet = _arquivo(lago, f"estado/tse/tentativas/{identidade}/bens.parquet", b"privado")
    gravar_json(
        tentativa / "manifesto.json",
        {
            "protocolo": "tse:tentativa:v1",
            "descritor": {
                "versao_id": identidade,
                "hashes_parquet": {"bens": sha256_arquivo(parquet)},
            },
            "controle": {},
        },
        checksum=True,
    )
    gravar_json(
        lago / f"estado/tse/originais/{identidade}.json",
        {"versao_id": identidade, "arquivo_original": "gs://teste/rejeitado.zip"},
        checksum=True,
    )
    gcs = FakeArmazenamento(tmp_path / "bucket")
    salvar_tse(gcs, PREFIXO, lago)
    if defeito == "manifesto":
        del gcs.objetos[PREFIXO + f"estado/tse/tentativas/{identidade}/manifesto.json"]
    elif defeito == "hash":
        gcs.objetos[PREFIXO + f"estado/tse/tentativas/{identidade}/bens.parquet"].write_bytes(
            b"dano"
        )
    elif defeito == "referencia":
        rejeicao = gravar_avaliacao(
            lago,
            escopo="versao",
            identidade=identidade,
            entradas_digest="b" * 64,
            contrato="tse:estrutura:v1",
            execucao_id="rejeitada",
            resultado="rejeitada",
            motivos=[],
        )
        aprovacao = gravar_avaliacao(
            lago,
            escopo="versao",
            identidade=identidade,
            entradas_digest="b" * 64,
            contrato="tse:estrutura:v1",
            execucao_id="aprovada",
            resultado="aprovada",
            motivos=[],
            superadas=(rejeicao,),
            evidencia="evidencia",
        )
        caminho = lago / f"estado/tse/validacoes/{aprovacao}.json"
        gcs.enviar(caminho, PREFIXO + caminho.relative_to(lago).as_posix())
    local = tmp_path / "restaurado"
    if defeito:
        with pytest.raises((ValueError, OSError)):
            restaurar_tse(gcs, PREFIXO, local)
        assert not local.exists()
    else:
        restaurar_tse(gcs, PREFIXO, local)
        assert (
            local / f"estado/tse/tentativas/{identidade}/bens.parquet"
        ).read_bytes() == b"privado"
        assert (local / f"estado/tse/originais/{identidade}.json").exists()
        assert not (local / "estado/tse/vigente.json").exists()


def test_versao_nao_vigente_tambem_confere_raw(tmp_path):
    salvar_tse, _ = operacoes()
    lago, _ = montar_vetor(tmp_path)
    next(lago.glob("raw/tse/*/*/*/dados.parquet")).write_bytes(b"dano")
    gcs = FakeArmazenamento(tmp_path / "bucket")
    with pytest.raises(ValueError):
        salvar_tse(gcs, PREFIXO, lago)
    assert gcs.objetos == {}


def test_aprovacao_isolada_nao_reabilita_backup_antigo(tmp_path):
    from coletor.tse.selecao import digest_entradas
    from coletor.tse.validacoes import gravar_avaliacao

    _, restaurar_tse = operacoes()
    lago, selecao, gcs = remoto(tmp_path)
    recibo = json.loads(
        (lago / "estado/tse/publicacoes/preparadas/execucao-1/recibo.json").read_bytes()
    )
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(lago, selecao),
        contrato="tse:selecao:v1",
        execucao_id="posterior",
        resultado="rejeitada",
        motivos=[],
    )
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(lago, selecao),
        contrato="tse:selecao:v1",
        execucao_id="isolada",
        resultado="aprovada",
        motivos=[],
        superadas=(rejeicao,),
        evidencia=recibo["evidencia"],
    )
    anterior = (lago / "estado/tse/vigente.json").read_bytes()
    with pytest.raises(ValueError):
        restaurar_tse(gcs, PREFIXO, lago)
    assert (lago / "estado/tse/vigente.json").read_bytes() == anterior


def test_marcador_confere_identidade_do_vetor_historico(tmp_path):
    from coletor.tse.selecao import criar_selecao

    _, restaurar_tse = operacoes()
    lago, atual, gcs = remoto(tmp_path)
    historica = criar_selecao({**atual.versoes, "tse.bens:2024": "f" * 64})
    historica.versoes["tse.bens:2024"] = "e" * 64
    arquivo = _arquivo(
        lago,
        f"estado/tse/selecoes/{historica.selecao_id}.json",
        json.dumps(asdict(historica)).encode(),
    )
    gcs.enviar(arquivo, PREFIXO + arquivo.relative_to(lago).as_posix())
    marcador = _arquivo(
        lago,
        "estado/tse/inicializado.json",
        json.dumps(
            {"protocolo": "tse:inicializado:v1", "primeira_selecao_id": historica.selecao_id}
        ).encode(),
    )
    gcs.substituir(marcador, PREFIXO + "estado/tse/inicializado.json")
    local = tmp_path / "restaurado"
    with pytest.raises(ValueError):
        restaurar_tse(gcs, PREFIXO, local)
    assert not local.exists()


def retificacao_sintetica(lago, selecao):
    import hashlib
    import shutil

    from coletor.hashes import json_canonico
    from coletor.tse.selecao import criar_selecao

    anterior = lago / f"estado/tse/versoes/{selecao.versoes['tse.bens:2024']}.json"
    dados = json.loads(anterior.read_bytes())
    dados["sha256_zip"] = hashlib.sha256(b"retificacao privada").hexdigest()
    dados["versao_id"] = hashlib.sha256(
        json_canonico(["tse.bens", 2024, dados["sha256_zip"]]).encode()
    ).hexdigest()
    raw = f"raw/tse/bens/2024/{dados['sha256_zip']}/dados.parquet"
    (lago / raw).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(lago / dados["familias"]["bens"], lago / raw)
    dados["familias"]["bens"] = raw
    (lago / f"estado/tse/versoes/{dados['versao_id']}.json").write_text(
        json_canonico(dados), encoding="utf-8"
    )
    return criar_selecao({**selecao.versoes, "tse.bens:2024": dados["versao_id"]})


def remoto_retificado(tmp_path):
    import shutil

    lago, primeira, gcs = remoto(tmp_path)
    local = tmp_path / "local"
    shutil.copytree(lago, local)
    segunda = retificacao_sintetica(lago, primeira)
    promover_selecao(lago, segunda, execucao(lago, segunda, "retificacao"))
    for arquivo in lago.rglob("*"):
        if arquivo.is_file():
            caminho = PREFIXO + arquivo.relative_to(lago).as_posix()
            if caminho.endswith("/vigente.json"):
                gcs.substituir(arquivo, caminho)
            else:
                gcs.enviar(arquivo, caminho)
    return local, primeira, segunda, gcs


def falhar_sync_apos_vigente(monkeypatch, lago):
    from coletor.tse import durabilidade
    from coletor.tse import estado as estado_tse
    from coletor.tse import selecao as modulo_selecao

    estado_local = lago / "estado/tse"
    anterior = (estado_local / "vigente.json").read_bytes()
    original = durabilidade.sincronizar_pasta
    falhou = False

    def sincronizar(pasta):
        nonlocal falhou
        vigente = estado_local / "vigente.json"
        if (
            not falhou
            and pasta == estado_local
            and vigente.exists()
            and vigente.read_bytes() != anterior
        ):
            falhou = True
            raise OSError("fsync apos trocar vigente")
        original(pasta)

    for modulo in (durabilidade, estado_tse, modulo_selecao):
        monkeypatch.setattr(modulo, "sincronizar_pasta", sincronizar, raising=False)


def test_fsync_pos_troca_restaura_ponteiro_e_estado_operavel(tmp_path, monkeypatch):
    salvar_tse, restaurar_tse = operacoes()
    local, _, _, gcs = remoto_retificado(tmp_path)
    anterior = (local / "estado/tse/vigente.json").read_bytes()
    falhar_sync_apos_vigente(monkeypatch, local)
    with pytest.raises(OSError, match="fsync apos"):
        restaurar_tse(gcs, PREFIXO, local)
    assert (local / "estado/tse/vigente.json").read_bytes() == anterior
    salvar_tse(FakeArmazenamento(tmp_path / "backup-anterior"), PREFIXO, local)


@pytest.mark.parametrize("fronteira", ["raw", "tentativa"])
def test_instalacao_parcial_compensa_e_preserva_operacao(tmp_path, monkeypatch, fronteira):
    import os

    from coletor.hashes import sha256_arquivo
    from coletor.tse.durabilidade import gravar_json

    salvar_tse, restaurar_tse = operacoes()
    local, _, segunda, gcs = remoto_retificado(tmp_path)
    versao_id = segunda.versoes["tse.bens:2024"]
    descritor = json.loads(
        gcs.objetos[PREFIXO + f"estado/tse/versoes/{versao_id}.json"].read_bytes()
    )
    tentativa = tmp_path / "extra" / versao_id
    tentativa.mkdir(parents=True)
    (tentativa / "bens.parquet").write_bytes(b"tentativa privada")
    gravar_json(
        tentativa / "manifesto.json",
        {
            "protocolo": "tse:tentativa:v1",
            "descritor": {
                "versao_id": versao_id,
                "hashes_parquet": {"bens": sha256_arquivo(tentativa / "bens.parquet")},
            },
            "controle": {},
        },
        checksum=True,
    )
    for p in tentativa.iterdir():
        gcs.enviar(p, PREFIXO + f"estado/tse/tentativas/{versao_id}/{p.name}")
    antes = {
        p.relative_to(local).as_posix(): p.read_bytes() for p in local.rglob("*") if p.is_file()
    }
    alvo = (
        local / descritor["familias"]["bens"]
        if fronteira == "raw"
        else local / f"estado/tse/tentativas/{versao_id}/manifesto.json"
    )
    original = os.replace

    def substituir(origem, destino):
        if Path(destino) == alvo:
            raise OSError("instalacao parcial")
        original(origem, destino)

    from pathlib import Path

    monkeypatch.setattr(os, "replace", substituir)
    with pytest.raises(OSError, match="instalacao parcial"):
        restaurar_tse(gcs, PREFIXO, local)
    assert {
        p.relative_to(local).as_posix(): p.read_bytes() for p in local.rglob("*") if p.is_file()
    } == antes
    salvar_tse(FakeArmazenamento(tmp_path / "backup-anterior"), PREFIXO, local)


def test_salvar_conta_downloads_de_validacao(tmp_path):
    salvar_tse, _ = operacoes()
    lago, _, gcs = remoto(tmp_path)
    resumo = salvar_tse(gcs, PREFIXO, lago)
    assert resumo.enviados == 0
    assert resumo.baixados == len(gcs.objetos) - 2  # vigente/marcador não são baixados no envio


def test_compensacao_falha_preserva_backup_e_bloqueia_consumidores(tmp_path, monkeypatch):
    import os
    from pathlib import Path

    from coletor.tse.durabilidade import ErroCompensacaoTse, ErroRecuperacaoTse
    from coletor.tse.selecao import validar_selecao

    salvar_tse, restaurar_tse = operacoes()
    local, primeira, _, gcs = remoto_retificado(tmp_path)
    anterior = (local / "estado/tse/vigente.json").read_bytes()
    falhar_sync_apos_vigente(monkeypatch, local)
    original = os.replace

    def substituir(origem, destino):
        if Path(origem).name.startswith(".repor-"):
            raise OSError("compensacao indisponivel")
        original(origem, destino)

    monkeypatch.setattr(os, "replace", substituir)
    with pytest.raises(ErroCompensacaoTse) as falha:
        restaurar_tse(gcs, PREFIXO, local)
    area = falha.value.area
    assert area.is_dir()
    assert (area / "plano.json").is_file()
    assert anterior in [p.read_bytes() for p in (area / "anteriores").iterdir()]
    assert validar_selecao(local, primeira)
    with pytest.raises(ErroRecuperacaoTse):
        salvar_tse(gcs, PREFIXO, local)
    with pytest.raises(ErroRecuperacaoTse):
        restaurar_tse(gcs, PREFIXO, local)
    with pytest.raises(ErroRecuperacaoTse):
        promover_selecao(local, primeira, None)


def test_instalacao_prepara_replace_no_diretorio_destino(tmp_path, monkeypatch):
    import os
    from pathlib import Path

    from coletor.tse.durabilidade import instalar_com_compensacao

    lago = tmp_path / "lago"
    origem = _arquivo(tmp_path / "outro-volume", "novo.json", b"novo")
    destino = _arquivo(lago, "estado/tse/vigente.json", b"anterior")
    original = os.replace

    def substituir(de, para):
        if Path(de).parent != Path(para).parent:
            raise OSError("replace entre volumes proibido")
        original(de, para)

    monkeypatch.setattr(os, "replace", substituir)
    instalar_com_compensacao(lago, [(origem, destino)])
    assert destino.read_bytes() == b"novo"
    assert origem.read_bytes() == b"novo"


def test_limpeza_pos_commit_avisa_sem_bloquear_estado(tmp_path, monkeypatch, caplog):
    import shutil
    from pathlib import Path

    from coletor.tse.durabilidade import conferir_recuperacao, instalar_com_compensacao

    lago = tmp_path / "lago"
    origem = _arquivo(tmp_path / "origem", "novo.json", b"novo")
    destino = _arquivo(lago, "estado/tse/vigente.json", b"anterior")
    original = shutil.rmtree

    def remover(pasta, *args, **kwargs):
        if Path(pasta).name.startswith(".limpeza-"):
            raise OSError("limpeza indisponivel")
        return original(pasta, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", remover)
    instalar_com_compensacao(lago, [(origem, destino)])
    assert destino.read_bytes() == b"novo"
    assert list((lago / "estado/tse").glob(".limpeza-*/concluida.json"))
    conferir_recuperacao(lago)
    assert "limpeza" in caplog.text


@pytest.mark.parametrize("compensacao_falha", [False, True])
def test_conclusao_criada_sem_fsync_nao_prova_commit(tmp_path, monkeypatch, compensacao_falha):
    import os
    from pathlib import Path

    from coletor.tse import durabilidade

    lago = tmp_path / "lago"
    origem = _arquivo(tmp_path / "origem", "novo.json", b"novo")
    destino = _arquivo(lago, "estado/tse/vigente.json", b"anterior")
    sincronizar_original = durabilidade.sincronizar_pasta
    substituir_original = os.replace
    falhou = False

    def sincronizar(pasta):
        nonlocal falhou
        if not falhou and (pasta / "concluida.json").exists():
            falhou = True
            raise OSError("fsync conclusao")
        sincronizar_original(pasta)

    def substituir(de, para):
        if compensacao_falha and Path(de).name.startswith(".repor-"):
            raise OSError("compensacao indisponivel")
        substituir_original(de, para)

    monkeypatch.setattr(durabilidade, "sincronizar_pasta", sincronizar)
    monkeypatch.setattr(os, "replace", substituir)
    with pytest.raises(OSError):
        durabilidade.instalar_com_compensacao(lago, [(origem, destino)])
    if compensacao_falha:
        area = next((lago / "estado/tse").glob(".recuperacao-*"))
        assert (area / "concluida.json").exists()
        assert not (area / "confirmada.json").exists()
        assert (area / "compensacao.json").exists()
        with pytest.raises(durabilidade.ErroRecuperacaoTse):
            durabilidade.conferir_recuperacao(lago)
    else:
        assert destino.read_bytes() == b"anterior"
        durabilidade.conferir_recuperacao(lago)


def test_journal_incompleto_bloqueia_mesmo_sem_vigente(tmp_path):
    from coletor.tse.durabilidade import ErroRecuperacaoTse
    from coletor.tse.selecao import criar_selecao, validar_selecao

    salvar_tse, restaurar_tse = operacoes()
    lago = tmp_path / "lago"
    (lago / "estado/tse/.recuperacao-incompleta").mkdir(parents=True)
    assert "recuperação" in validar_selecao(lago, criar_selecao({}))[0]
    gcs = FakeArmazenamento(tmp_path / "bucket")
    with pytest.raises(ErroRecuperacaoTse):
        salvar_tse(gcs, PREFIXO, lago)
    with pytest.raises(ErroRecuperacaoTse):
        restaurar_tse(gcs, PREFIXO, lago)


def test_journal_concluido_historico_nao_confere_destino_atual(tmp_path, monkeypatch, caplog):
    import os
    from pathlib import Path

    from coletor.tse import durabilidade

    lago = tmp_path / "lago"
    origem = _arquivo(tmp_path / "origem", "novo.json", b"novo")
    destino = _arquivo(lago, "estado/tse/vigente.json", b"anterior")
    original = os.rename

    def renomear(de, para):
        if Path(de).name.startswith(".recuperacao-"):
            raise OSError("limpeza indisponivel")
        original(de, para)

    monkeypatch.setattr(os, "rename", renomear)
    durabilidade.instalar_com_compensacao(lago, [(origem, destino)])
    assert list((lago / "estado/tse").glob(".recuperacao-*/confirmada.json"))
    segunda = _arquivo(tmp_path / "origem", "outra.json", b"outra")
    durabilidade.instalar_com_compensacao(lago, [(segunda, destino)])
    assert destino.read_bytes() == b"outra"
    durabilidade.conferir_recuperacao(lago)
    assert "limpeza" in caplog.text
    area = next((lago / "estado/tse").glob(".recuperacao-*"))
    (area / "compensacao.json").write_bytes(b"pendencia prevalece")
    with pytest.raises(durabilidade.ErroRecuperacaoTse):
        durabilidade.conferir_recuperacao(lago)


def test_fsync_preparo_nao_deixa_arquivo_novo_parcial(tmp_path, monkeypatch):
    import os

    from coletor.tse.durabilidade import instalar_com_compensacao

    lago = tmp_path / "lago"
    origem = _arquivo(tmp_path / "origem", "novo.json", b"novo")
    destino = _arquivo(lago, "estado/tse/vigente.json", b"anterior")
    original = os.fsync
    falhou = False

    def sincronizar(descritor):
        nonlocal falhou
        if not falhou:
            falhou = True
            raise OSError("preparo indisponivel")
        original(descritor)

    monkeypatch.setattr(os, "fsync", sincronizar)
    with pytest.raises(OSError, match="preparo indisponivel"):
        instalar_com_compensacao(lago, [(origem, destino)])
    assert destino.read_bytes() == b"anterior"
    assert not list(lago.rglob(".instalacao-*"))
    assert not list(lago.rglob(".recuperacao-*"))


@pytest.mark.parametrize("operacao", ["restauro", "promocao"])
def test_limpeza_temporario_pos_commit_nao_gera_falha_ambigua(
    tmp_path, monkeypatch, caplog, operacao
):
    import shutil
    from pathlib import Path

    if operacao == "restauro":
        local, _, segunda, gcs = remoto_retificado(tmp_path)

        def acao():
            return operacoes()[1](gcs, PREFIXO, local)
    else:
        local, primeira = montar_vetor(tmp_path)
        promover_selecao(local, primeira, execucao(local, primeira))
        segunda = retificacao_sintetica(local, primeira)
        recibo = execucao(local, segunda, "segunda")

        def acao():
            return promover_selecao(local, segunda, recibo)

    original = shutil.rmtree

    def remover(pasta, *args, **kwargs):
        if Path(pasta).name.startswith(("tse-restauro-", "tse-seletor-")):
            raise OSError("limpeza temporaria indisponivel")
        return original(pasta, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", remover)
    acao()
    assert json.loads((local / "estado/tse/vigente.json").read_bytes()) == asdict(segunda)
    assert "limpeza" in caplog.text


def test_limpeza_temporario_falho_preserva_erro_original(tmp_path, monkeypatch):
    import shutil

    from coletor.tse.durabilidade import pasta_temporaria

    def remover(*args, **kwargs):
        raise OSError("limpeza indisponivel")

    monkeypatch.setattr(shutil, "rmtree", remover)
    with pytest.raises(ValueError, match="erro original"):
        with pasta_temporaria("tse-preparo-", tmp_path):
            raise ValueError("erro original")
