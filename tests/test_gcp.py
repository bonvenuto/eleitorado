import google.auth.credentials
import google.oauth2.credentials

from coletor.gcp import credenciais_do_ambiente


class _ContaDeServico(google.auth.credentials.Credentials):
    """Credenciais que não são de usuário (Cloud Run, WIF)."""

    def refresh(self, request):  # pragma: no cover - não usado
        pass


def test_credencial_de_usuario_recebe_o_quota_project():
    usuario = google.oauth2.credentials.Credentials(token="x")
    credenciais = credenciais_do_ambiente("meu-projeto", obter=lambda **_: (usuario, None))
    assert credenciais.quota_project_id == "meu-projeto"


def test_conta_de_servico_e_wif_nao_recebem_quota_project():
    conta = _ContaDeServico()
    credenciais = credenciais_do_ambiente("meu-projeto", obter=lambda **_: (conta, None))
    assert credenciais is conta
    assert getattr(credenciais, "quota_project_id", None) is None


def test_dependencias_reais_restringem_hosts(monkeypatch, config):
    from coletor import gcp
    from coletor.http import SUFIXOS_OFICIAIS

    monkeypatch.setattr(gcp, "credenciais_do_ambiente", lambda projeto: None)
    monkeypatch.setattr(gcp, "GcsArmazenamento", lambda *args, **kwargs: None)
    deps = gcp.montar_dependencias(config)
    assert deps.http.sufixos_permitidos == SUFIXOS_OFICIAIS
    deps.http.fechar()
