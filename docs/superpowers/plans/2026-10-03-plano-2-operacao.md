# Plano 2: operação na nuvem

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** colocar o coletor para rodar sozinho todo dia às 07:30 (Brasília) num Cloud Run Job, com deploy automático pelo GitHub Actions, aviso de falha sem custo (vigia) e travas de custo.

**Arquitetura:** a CLI ganha dois comandos:
- `coletor pipeline`: coleta o que está vencido, roda `dbt build` (por enquanto num esqueleto dbt sem modelos) e grava uma linha em `meta.execucoes`;
- `coletor vigia`: verifica se a execução agendada do dia teve sucesso.

A imagem Docker leva o coletor e o projeto dbt. O Terraform cria Artifact Registry, contas de serviço com permissão mínima, Cloud Run Job, Cloud Scheduler, Workload Identity Federation para o GitHub e o orçamento. Três workflows completam a operação: `ci.yml`, `deploy.yml` e `vigia.yml`.

**Stack:** Python 3.12, uv, dbt-core 1.12 e dbt-bigquery 1.12, Docker, Terraform (provider google ≥ 6), GitHub Actions (`google-github-actions/auth@v2`, `astral-sh/setup-uv@v6`).

**Spec:** [docs/superpowers/specs/2026-10-03-ingestao-onda-a-design.md](../specs/2026-10-03-ingestao-onda-a-design.md). Este plano cobre as seções 6.6 (`coletor pipeline`), 7.1 (esqueleto do projeto dbt), 8.1, 8.2, 8.3, 8.5 e 10.

**Ponto de partida:** branch `feat/plano-1-coletor` (PR #1). Este plano roda em `feat/plano-2-operacao`, criado a partir dele.

## Restrições globais

- **Região:** `southamerica-east1` para tudo. Projeto `dados-publicos-prd`, conta de faturamento `01A56D-15D9DD-C83237` (em BRL), repositório `bonvenuto/eleitorado` (privado).
- **Agendamento:** Cloud Scheduler `pipeline-diario`, `30 7 * * *`, fuso `America/Sao_Paulo`.
- **Cloud Run Job `pipeline`:** 1 tarefa, 1 vCPU, 2 GiB, timeout de 3.600 s, 1 retentativa, conta `pipeline`, comando `coletor pipeline`.
- **Vigia:** diário às 10:00 de Brasília (`0 13 * * *` em UTC). Falha se não houver, no dia, nenhuma execução de origem `agendada` com status `sucesso`.
- **Travas de custo:**
  - orçamento mensal com alertas em 50%, 90% e 100%, calculado sem créditos;
  - cota de 30 GiB consultados por dia no BigQuery (30720 MiB);
  - `maximum_bytes_billed` de 10 GiB por consulta no profile do dbt.
- **Credenciais:** nenhuma chave de conta de serviço. O GitHub autentica por Workload Identity Federation, e o deployer só a partir de `refs/heads/main`.
- **Ambiente local:** o gcloud deste projeto fica isolado (`CLOUDSDK_CONFIG` do `.env`). Nunca alterar a configuração `prod` da máquina.
- **Antes de cada commit:** `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest` passando.
- **Commits:** mensagens em português, terminadas com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Foco de revisão

1. **O dbt explode ou não está instalado na imagem.** A execução precisa ser registrada como `falha`, e o vigia avisa. Teste `test_pipeline_registra_a_execucao_mesmo_se_o_dbt_explodir` (Tarefa 3).
2. **Coleta com falha num dia.** O dbt roda mesmo assim, sobre o último dado bom, e a execução termina como `falha`. Teste `test_pipeline_roda_o_dbt_mesmo_com_falha_de_coleta` (Tarefa 3).
3. **O vigia roda com uma conta só de leitura.** Ele não pode tentar criar tabelas. Teste `test_vigia_aprova_quando_ha_execucao_agendada_com_sucesso_hoje`, que confere que `preparar()` não é chamado (Tarefa 3).
4. **O dia do vigia é o de Brasília, não o de UTC.** A consulta usa `DATE(iniciada_em, 'America/Sao_Paulo')`. Teste `test_consulta_do_vigia_filtra_dia_origem_e_status` (Tarefa 3).
5. **Retentativa do job no mesmo dia** (a 1ª tentativa falha e a 2ª dá certo). O vigia aprova porque conta qualquer execução com sucesso no dia. Coberto pela mesma consulta (Tarefa 3) e conferido de ponta a ponta na Tarefa 8.

## Decisões de implementação que refinam a spec

- **Piso do `google-cloud-storage` reduzido para `>=2.18`.** O dbt-bigquery 1.12 exige `<3.2`, e as APIs do GCS que o coletor usa existem desde a 2.x. Os 95 testes do Plano 1 continuam passando.
- **Imagem inicial do job.** O job nasce com a imagem pública de exemplo do Cloud Run (`us-docker.pkg.dev/cloudrun/container/job:latest`). A imagem real chega pelo `deploy.yml` no primeiro merge em `main`, e o Terraform ignora mudanças de imagem a partir daí. Assim não é preciso Docker local nem Cloud Build. O Dockerfile é validado antes, por um build no `ci.yml` de cada PR.
- **Vigia como comando da CLI.** O `vigia.yml` só roda `coletor vigia`, e a lógica fica testável em Python.
- **Orçamento em reais.** A conta de faturamento é em BRL, então o orçamento é de R$ 30/mês, cerca dos US$ 5 da spec.
- **Conta de serviço do CI.** A spec chama a conta de `ci`, mas o GCP exige ids de pelo menos 6 caracteres. O id fica `ci-github`.
- **Cota diária por comando.** É aplicada com `gcloud alpha services quota update`, porque o recurso do Terraform para cotas exige ids codificados e frágeis.
- **Testes unitários do dbt no CI.** Ficam para o Plano 3, que cria os modelos. Por enquanto o CI roda `dbt parse`.
- **Origem `agendada` em execuções manuais.** O job sempre registra a origem `agendada`, inclusive quando é executado à mão com `gcloud run jobs execute`. Isso é intencional, porque testa exatamente o caminho que o vigia confere.

## Estrutura de arquivos

```
pyproject.toml, uv.lock          + dbt-bigquery; google-cloud-storage>=2.18
dbt/dbt_project.yml              projeto dbt (sem modelos até o Plano 3)
dbt/profiles.yml                 targets dev/prod/ci, oauth, maximum_bytes_billed
dbt/macros/generate_schema_name.sql
dbt/models/.gitkeep, dbt/tests/.gitkeep
coletor/dbt.py                   rodar_dbt() e ResultadoDbt
coletor/execucao.py              registro_execucao() recebe o resultado do dbt
coletor/meta.py                  + execucao_agendada_com_sucesso()
coletor/cli.py                   + comandos pipeline e vigia
Dockerfile, .dockerignore
.github/workflows/ci.yml, deploy.yml, vigia.yml
infra/main.tf                    + APIs
infra/variables.tf               + github_repo, conta_faturamento, orcamento_mensal_brl, imagem_inicial
infra/armazenamento.tf           + dataset ci
infra/execucao.tf                Artifact Registry, contas de serviço, IAM, job, scheduler
infra/github.tf                  Workload Identity Federation e permissões do GitHub
infra/custos.tf                  orçamento
tests/test_dbt_projeto.py, tests/test_dbt.py, tests/test_pipeline.py
README.md                        seção de operação
```

---

### Tarefa 1: dependência do dbt e esqueleto do projeto

**Arquivos:**
- Modificar: `pyproject.toml` e `uv.lock` (via `uv add`)
- Criar: `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/macros/generate_schema_name.sql`, `dbt/models/.gitkeep`, `dbt/tests/.gitkeep`, `tests/test_dbt_projeto.py`

**Interfaces:**
- Consome: `tests.amostras.RAIZ` (Plano 1).
- Produz: o projeto dbt `eleitorado` em `dbt/`, com os targets `dev`, `prod` e `ci`. Em `prod`, os schemas são os configurados; em `dev` e `ci`, recebem o prefixo `<dataset do target>_`.

- [ ] **Passo 1: criar o branch e instalar o dbt**

```bash
git checkout feat/plano-1-coletor
git checkout -b feat/plano-2-operacao
uv add "google-cloud-storage>=2.18" dbt-bigquery
uv run dbt --version
```

Esperado: `dbt-core` 1.12.x e o plugin `bigquery` 1.12.x instalados.

- [ ] **Passo 2: escrever o teste que falha**

`tests/test_dbt_projeto.py`:

```python
"""O projeto dbt resolve os schemas como a spec pede (sem conexão com o BigQuery)."""

import json
import shutil
import subprocess

import pytest

from tests.amostras import RAIZ


@pytest.fixture
def projeto(tmp_path):
    destino = tmp_path / "dbt"
    shutil.copytree(RAIZ / "dbt", destino, ignore=shutil.ignore_patterns("target", "logs"))
    modelos = destino / "models"
    (modelos / "com_schema.sql").write_text("{{ config(schema='staging') }} select 1 as a\n")
    (modelos / "sem_schema.sql").write_text("select 1 as a\n")
    return destino


def _schemas(projeto, target: str) -> dict[str, str]:
    saida = subprocess.run(
        [
            "dbt",
            "ls",
            "--project-dir",
            str(projeto),
            "--profiles-dir",
            str(projeto),
            "--target",
            target,
            "--resource-type",
            "model",
            "--output",
            "json",
            "--output-keys",
            "name",
            "schema",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**__import__("os").environ, "ELEITORADO_PROJETO": "projeto-teste"},
    )
    linhas = [json.loads(linha) for linha in saida.stdout.splitlines() if linha.startswith("{")]
    return {linha["name"]: linha["schema"] for linha in linhas}


def test_schemas_em_producao_sao_os_configurados(projeto):
    assert _schemas(projeto, "prod") == {"com_schema": "staging", "sem_schema": "marts"}


def test_schemas_em_dev_levam_o_prefixo_do_usuario(projeto, monkeypatch):
    monkeypatch.setenv("ELEITORADO_USUARIO_DBT", "angelo")
    assert _schemas(projeto, "dev") == {
        "com_schema": "dev_angelo_staging",
        "sem_schema": "dev_angelo",
    }
```

- [ ] **Passo 3: criar o projeto sem a macro e confirmar a falha**

`dbt/dbt_project.yml`:

```yaml
name: eleitorado
version: "0.1.0"
config-version: 2
profile: eleitorado

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]
clean-targets: ["target", "dbt_packages"]
```

`dbt/profiles.yml`:

```yaml
# Sem segredos: autenticação por ADC (local) ou pela conta de serviço (Cloud Run).
eleitorado:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: "{{ env_var('ELEITORADO_PROJETO') }}"
      quota_project: "{{ env_var('ELEITORADO_PROJETO') }}"
      dataset: "dev_{{ env_var('ELEITORADO_USUARIO_DBT', 'local') }}"
      location: southamerica-east1
      threads: 4
      maximum_bytes_billed: 10737418240
      job_execution_timeout_seconds: 900
    prod:
      type: bigquery
      method: oauth
      project: "{{ env_var('ELEITORADO_PROJETO') }}"
      quota_project: "{{ env_var('ELEITORADO_PROJETO') }}"
      dataset: marts
      location: southamerica-east1
      threads: 4
      maximum_bytes_billed: 10737418240
      job_execution_timeout_seconds: 900
    ci:
      type: bigquery
      method: oauth
      project: "{{ env_var('ELEITORADO_PROJETO') }}"
      quota_project: "{{ env_var('ELEITORADO_PROJETO') }}"
      dataset: ci
      location: southamerica-east1
      threads: 4
      maximum_bytes_billed: 10737418240
      job_execution_timeout_seconds: 900
```

Crie também `dbt/models/.gitkeep` e `dbt/tests/.gitkeep` vazios.

Executar: `uv run pytest tests/test_dbt_projeto.py -v`
Esperado: `1 failed, 1 passed`. Sem a macro, o dbt gera `marts_staging` em prod, e por isso o teste de prod falha. Em dev ele já gera `dev_angelo_staging`, que é o esperado.

- [ ] **Passo 4: implementar a macro**

`dbt/macros/generate_schema_name.sql`:

```sql
{#- prod: o schema configurado (staging, intermediate, marts); dev/ci: <dataset do target>_<schema> -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

- [ ] **Passo 5: rodar e confirmar que passa**

Executar: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Esperado: `97 passed, 2 deselected` e o lint limpo.

- [ ] **Passo 6: commit**

```bash
git add pyproject.toml uv.lock dbt/ tests/test_dbt_projeto.py
git commit -m "feat(dbt): esqueleto do projeto dbt e dependência dbt-bigquery" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 2: execução do dbt pelo coletor

**Arquivos:**
- Criar: `coletor/dbt.py` e `tests/test_dbt.py`

**Interfaces:**
- Consome: nada além da biblioteca padrão.
- Produz:
  - `ResultadoDbt(status: str, testes_com_erro: int | None)`;
  - `rodar_dbt(diretorio: Path, target: str, executar: Callable[[list[str]], int] = subprocess) -> ResultadoDbt`. Ela roda `dbt build --project-dir D --profiles-dir D --target T` e conta os testes com status `fail` ou `error` em `target/run_results.json`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_dbt.py`:

```python
import json

from coletor.dbt import ResultadoDbt, rodar_dbt


def _executor_que_grava(resultados: list[dict], codigo: int, chamadas: list[list[str]]):
    def executar(comando: list[str]) -> int:
        chamadas.append(comando)
        destino = comando[comando.index("--project-dir") + 1]
        alvo = __import__("pathlib").Path(destino) / "target"
        alvo.mkdir(parents=True, exist_ok=True)
        (alvo / "run_results.json").write_text(
            json.dumps({"results": resultados}), encoding="utf-8"
        )
        return codigo

    return executar


def test_build_com_sucesso(tmp_path):
    chamadas: list[list[str]] = []
    resultados = [{"unique_id": "model.eleitorado.a", "status": "success"}]
    resultado = rodar_dbt(tmp_path, "prod", _executor_que_grava(resultados, 0, chamadas))
    assert resultado == ResultadoDbt("sucesso", 0)
    assert chamadas[0][:2] == ["dbt", "build"]
    assert chamadas[0][-2:] == ["--target", "prod"]


def test_build_com_testes_falhando_conta_os_erros(tmp_path):
    resultados = [
        {"unique_id": "test.eleitorado.unico", "status": "fail"},
        {"unique_id": "test.eleitorado.nao_nulo", "status": "error"},
        {"unique_id": "test.eleitorado.aviso", "status": "warn"},
        {"unique_id": "model.eleitorado.a", "status": "error"},
    ]
    resultado = rodar_dbt(tmp_path, "prod", _executor_que_grava(resultados, 1, []))
    assert resultado == ResultadoDbt("falha", 2)


def test_resultado_antigo_nao_e_reaproveitado(tmp_path):
    antigo = tmp_path / "target" / "run_results.json"
    antigo.parent.mkdir()
    antigo.write_text(json.dumps({"results": [{"unique_id": "test.x", "status": "fail"}]}))
    resultado = rodar_dbt(tmp_path, "prod", lambda comando: 2)
    assert resultado == ResultadoDbt("falha", None)
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_dbt.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.dbt'`.

- [ ] **Passo 3: implementar**

`coletor/dbt.py`:

```python
"""Execução do `dbt build` pelo comando `coletor pipeline`."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Executor = Callable[[list[str]], int]


@dataclass(frozen=True)
class ResultadoDbt:
    status: str  # "sucesso" ou "falha"
    testes_com_erro: int | None  # None quando o dbt não chegou a gravar run_results.json


def _executar_subprocesso(comando: list[str]) -> int:
    return subprocess.run(comando, check=False).returncode


def _testes_com_erro(caminho: Path) -> int | None:
    if not caminho.exists():
        return None
    resultados = json.loads(caminho.read_text(encoding="utf-8")).get("results", [])
    return sum(
        1
        for resultado in resultados
        if str(resultado.get("unique_id", "")).startswith("test.")
        and resultado.get("status") in ("fail", "error")
    )


def rodar_dbt(
    diretorio: Path, target: str, executar: Executor = _executar_subprocesso
) -> ResultadoDbt:
    resultados = diretorio / "target" / "run_results.json"
    resultados.unlink(missing_ok=True)
    codigo = executar(
        [
            "dbt",
            "build",
            "--project-dir",
            str(diretorio),
            "--profiles-dir",
            str(diretorio),
            "--target",
            target,
        ]
    )
    return ResultadoDbt("sucesso" if codigo == 0 else "falha", _testes_com_erro(resultados))
```

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Esperado: `100 passed, 2 deselected`.

- [ ] **Passo 5: commit**

```bash
git add coletor/dbt.py tests/test_dbt.py
git commit -m "feat(coletor): execução do dbt build com contagem de testes com erro" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 3: comandos `pipeline` e `vigia`

**Arquivos:**
- Modificar: `coletor/meta.py` (novo método), `coletor/execucao.py` e `coletor/cli.py` (conteúdo completo abaixo)
- Criar: `tests/test_pipeline.py`

**Interfaces:**
- Consome: `rodar_dbt`/`ResultadoDbt` (Tarefa 2), e `rodar`, `ResumoColetas`, `RepositorioMeta`, `tarefas_pendentes` e `data_brasilia` (Plano 1).
- Produz:
  - `RepositorioMeta.execucao_agendada_com_sucesso(dia: date) -> bool`;
  - `registro_execucao(..., dbt: ResultadoDbt | None = None)`;
  - `main(argv=None, fabrica=None, env=None, dbt=None) -> int`;
  - o comando `coletor pipeline [--recursos] [--dbt-dir dbt] [--target prod]`;
  - o comando `coletor vigia`, que sai com 0 quando há execução agendada com sucesso hoje e com 1 quando não há.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_pipeline.py`:

```python
from datetime import date

import httpx

from coletor.cli import main
from coletor.dbt import ResultadoDbt
from coletor.meta import RepositorioMeta
from tests.amostras import CNEP_CSV, PAGINA_CGU, RAIZ, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
ENV = {"ELEITORADO_PROJETO": "projeto-teste", "ELEITORADO_BUCKET": "bucket-teste"}


def _rodar(argumentos, deps, dbt) -> int:
    return main(
        ["--fontes", str(RAIZ / "fontes"), *argumentos],
        fabrica=lambda config: deps,
        env=ENV,
        dbt=dbt,
    )


def _mock_tudo_sem_alteracao(respx_mock):
    """Só o CNEP responde; o resto não está vencido porque o histórico já tem tudo."""
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")})
        )
    )


def test_pipeline_coleta_roda_dbt_e_registra_uma_execucao(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)
    chamadas = []

    def dbt(diretorio, target):
        chamadas.append((diretorio.name, target))
        return ResultadoDbt("sucesso", 0)

    codigo = _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt)
    assert codigo == 0
    assert chamadas == [("dbt", "prod")]
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("sucesso", "sucesso")
    assert execucao["dbt_testes_com_erro"] == 0


def test_pipeline_com_dbt_falhando_termina_com_erro(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)
    codigo = _rodar(
        ["pipeline", "--recursos", "cgu.cnep"], deps, lambda d, t: ResultadoDbt("falha", 3)
    )
    assert codigo == 1
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"], execucao["dbt_testes_com_erro"]) == (
        "falha",
        "falha",
        3,
    )


def test_pipeline_roda_o_dbt_mesmo_com_falha_de_coleta(respx_mock, deps, warehouse):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))
    chamadas = []

    def dbt(diretorio, target):
        chamadas.append(target)
        return ResultadoDbt("sucesso", 0)

    assert _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 1
    assert chamadas == ["prod"]
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["coletas_falha"], execucao["dbt_status"]) == (
        "falha",
        1,
        "sucesso",
    )


def test_pipeline_registra_a_execucao_mesmo_se_o_dbt_explodir(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)

    def dbt(diretorio, target):
        raise FileNotFoundError("dbt não instalado")

    assert _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 1
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("falha", "falha")


def test_vigia_aprova_quando_ha_execucao_agendada_com_sucesso_hoje(deps, warehouse):
    warehouse.resposta_consulta = [{"n": 1}]
    assert _rodar(["vigia"], deps, None) == 0
    assert warehouse.tabelas == set()  # não tenta criar tabelas: a conta do vigia só lê


def test_vigia_reprova_sem_execucao_agendada_com_sucesso(deps, warehouse, capsys):
    warehouse.resposta_consulta = [{"n": 0}]
    assert _rodar(["vigia"], deps, None) == 1
    assert "2026-10-03" in capsys.readouterr().err


def test_consulta_do_vigia_filtra_dia_origem_e_status(warehouse, config):
    consultas = []
    warehouse.consultar = lambda sql: consultas.append(sql) or [{"n": 2}]
    assert RepositorioMeta(warehouse, config).execucao_agendada_com_sucesso(date(2026, 10, 3))
    [sql] = consultas
    assert "origem = 'agendada'" in sql
    assert "status = 'sucesso'" in sql
    assert "DATE(iniciada_em, 'America/Sao_Paulo') = '2026-10-03'" in sql
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_pipeline.py -v`
Esperado: 7 falhas. A causa é `main() got an unexpected keyword argument 'dbt'`, e em `test_consulta_do_vigia…` falta o método `execucao_agendada_com_sucesso`.

- [ ] **Passo 3: implementar a consulta do vigia**

Em `coletor/meta.py`, dentro de `RepositorioMeta`, logo antes de `buscar_coleta`:

```python
    def execucao_agendada_com_sucesso(self, dia: date) -> bool:
        sql = (
            f"SELECT COUNT(*) AS n FROM `{self._config.projeto}.{self.tabela_execucoes}` "
            "WHERE origem = 'agendada' AND status = 'sucesso' "
            f"AND DATE(iniciada_em, 'America/Sao_Paulo') = '{dia.isoformat()}'"
        )
        linhas = self._warehouse.consultar(sql)
        return bool(linhas) and int(linhas[0]["n"]) > 0
```

- [ ] **Passo 4: registrar o resultado do dbt na execução**

Substituir `coletor/execucao.py` por:

```python
"""Execução de uma lista de tarefas, com registro em `meta`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from coletor.agenda import Tarefa
from coletor.coleta import Dependencias, coletar
from coletor.dbt import ResultadoDbt
from coletor.meta import HistoricoColetas, RegistroColeta, RegistroExecucao, RepositorioMeta

log = logging.getLogger(__name__)


@dataclass
class ResumoColetas:
    carregadas: int = 0
    sem_alteracao: int = 0
    nao_publicadas: int = 0
    falhas: int = 0

    def contar(self, status: str) -> None:
        if status == "carregada":
            self.carregadas += 1
        elif status == "sem_alteracao":
            self.sem_alteracao += 1
        elif status == "nao_publicada":
            self.nao_publicadas += 1
        else:
            self.falhas += 1

    @property
    def sucesso(self) -> bool:
        return self.falhas == 0


def _registrar_com_retentativa(repositorio: RepositorioMeta, registro: RegistroColeta) -> bool:
    for tentativa in (1, 2):
        try:
            repositorio.registrar_coleta(registro)
            return True
        except Exception:  # noqa: BLE001 - a falha em meta não pode parar as demais coletas
            log.exception(
                "falha ao gravar %s em meta.coletas (tentativa %d)", registro.coleta_id, tentativa
            )
    return False


def rodar(
    tarefas: list[Tarefa],
    historico: HistoricoColetas,
    deps: Dependencias,
    repositorio: RepositorioMeta,
    execucao_id: str,
    forcar: bool = False,
) -> ResumoColetas:
    resumo = ResumoColetas()
    for tarefa in tarefas:
        registro = coletar(tarefa.recurso, tarefa.competencia, historico, deps, execucao_id, forcar)
        historico.registrar(registro)
        if _registrar_com_retentativa(repositorio, registro):
            resumo.contar(registro.status)
        else:
            resumo.contar("falha")
        log.info(
            "%s competencia=%s status=%s linhas=%s%s",
            registro.recurso_id,
            registro.competencia,
            registro.status,
            registro.linhas,
            f" erro={registro.erro}" if registro.erro else "",
        )
    return resumo


def registro_execucao(
    execucao_id: str,
    origem: str,
    deps: Dependencias,
    inicio: datetime,
    resumo: ResumoColetas,
    dbt: ResultadoDbt | None = None,
) -> RegistroExecucao:
    sucesso = resumo.sucesso and (dbt is None or dbt.status == "sucesso")
    return RegistroExecucao(
        execucao_id=execucao_id,
        origem=origem,
        iniciada_em=inicio,
        finalizada_em=deps.agora(),
        status="sucesso" if sucesso else "falha",
        coletas_carregadas=resumo.carregadas,
        coletas_sem_alteracao=resumo.sem_alteracao,
        coletas_nao_publicadas=resumo.nao_publicadas,
        coletas_falha=resumo.falhas,
        versao=deps.config.versao,
        dbt_status=dbt.status if dbt else None,
        dbt_testes_com_erro=dbt.testes_com_erro if dbt else None,
    )
```

- [ ] **Passo 5: comandos na CLI**

Substituir `coletor/cli.py` por:

```python
"""CLI `coletor`: fontes, executar, coletar e recarregar."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from coletor.agenda import Tarefa, tarefa_snapshot, tarefas_pendentes
from coletor.coleta import EXPIRACAO_SNAPSHOT_DIAS, Dependencias, recarregar
from coletor.competencias import Competencia, data_brasilia
from coletor.config import Config, ErroConfig, carregar_config
from coletor.dbt import ResultadoDbt, rodar_dbt
from coletor.execucao import ResumoColetas, registro_execucao, rodar
from coletor.manifesto import ErroManifesto, Manifesto, carregar_manifesto
from coletor.meta import HistoricoColetas, RepositorioMeta

log = logging.getLogger("coletor")

Fabrica = Callable[[Config], Dependencias]
RodarDbt = Callable[[Path, str], ResultadoDbt]


class ErroUso(Exception):
    """Uso incorreto da CLI; sai com código 2."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coletor", description="Coletor de dados públicos")
    parser.add_argument(
        "--fontes", type=Path, default=Path("fontes"), help="diretório do manifesto"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("fontes", help="lista os recursos e a última coleta bem-sucedida")

    executar = sub.add_parser("executar", help="coleta o que está com o prazo vencido")
    executar.add_argument("--recursos", help="ids separados por vírgula (padrão: todos)")
    executar.add_argument("--forcar", action="store_true", help="ignora a deduplicação por hash")

    coletar = sub.add_parser("coletar", help="coleta manual e backfill de um recurso")
    coletar.add_argument("recurso")
    grupo = coletar.add_mutually_exclusive_group()
    grupo.add_argument("--competencia", help="ano, para recursos por competência")
    grupo.add_argument("--de", type=int, help="primeiro ano do intervalo")
    coletar.add_argument("--ate", type=int, help="último ano do intervalo (padrão: ano atual)")
    coletar.add_argument("--forcar", action="store_true")

    pipeline = sub.add_parser("pipeline", help="coleta o que está vencido e roda o dbt build")
    pipeline.add_argument("--recursos", help="ids separados por vírgula (padrão: todos)")
    pipeline.add_argument("--dbt-dir", type=Path, default=Path("dbt"), help="projeto dbt")
    pipeline.add_argument("--target", default="prod", help="target do dbt")

    sub.add_parser("vigia", help="falha se a execução agendada de hoje não teve sucesso")

    recarga = sub.add_parser("recarregar", help="refaz a carga a partir do original no GCS")
    recarga.add_argument("recurso")
    recarga.add_argument("--competencia", required=True)
    recarga.add_argument("--coleta-id")
    recarga.add_argument("--destino", choices=["raw", "replay"], default="raw")
    return parser


def _rodar_tarefas(
    tarefas: list[Tarefa],
    historico: HistoricoColetas,
    deps: Dependencias,
    repo: RepositorioMeta,
    inicio: datetime,
    forcar: bool,
    dbt: Callable[[], ResultadoDbt] | None = None,
) -> int:
    """Roda as coletas e, se pedido, o dbt; a execução é sempre registrada."""
    execucao_id = str(uuid.uuid4())
    resumo = ResumoColetas()
    resultado_dbt: ResultadoDbt | None = None
    try:
        resumo = rodar(tarefas, historico, deps, repo, execucao_id, forcar)
    except Exception:
        log.exception("coletas interrompidas")
        resumo.contar("falha")
    try:
        if dbt is not None:
            resultado_dbt = ResultadoDbt("falha", None)
            resultado_dbt = dbt()
    except Exception:
        log.exception("dbt interrompido")
    finally:
        repo.registrar_execucao(
            registro_execucao(execucao_id, deps.config.origem, deps, inicio, resumo, resultado_dbt)
        )
    log.info("resumo: %s dbt: %s", resumo, resultado_dbt)
    dbt_ok = resultado_dbt is None or resultado_dbt.status == "sucesso"
    return 0 if resumo.sucesso and dbt_ok else 1


def _fontes(manifesto: Manifesto, repo: RepositorioMeta) -> int:
    historico = repo.carregar_historico()
    for rc in manifesto.todos():
        ultima = historico.ultima_data_sucesso(rc.id)
        regra = rc.recurso
        print(f"{rc.id:20} {regra.publicacao:16} {regra.cadencia.corrente:8} {ultima or '-'}")
    return 0


def _executar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    if args.recursos:
        recursos = [manifesto.obter(item.strip()) for item in args.recursos.split(",")]
    else:
        recursos = manifesto.todos()
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(recursos, historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _pipeline(
    args: argparse.Namespace,
    manifesto: Manifesto,
    deps: Dependencias,
    repo: RepositorioMeta,
    rodar_dbt_: RodarDbt,
) -> int:
    if args.recursos:
        recursos = [manifesto.obter(item.strip()) for item in args.recursos.split(",")]
    else:
        recursos = manifesto.todos()
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(recursos, historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))
    return _rodar_tarefas(
        tarefas,
        historico,
        deps,
        repo,
        inicio,
        False,
        dbt=lambda: rodar_dbt_(args.dbt_dir, args.target),
    )


def _vigia(deps: Dependencias, repo: RepositorioMeta) -> int:
    hoje = data_brasilia(deps.agora())
    if repo.execucao_agendada_com_sucesso(hoje):
        log.info("execução agendada de %s terminou com sucesso", hoje.isoformat())
        return 0
    print(f"erro: nenhuma execução agendada com sucesso em {hoje.isoformat()}", file=sys.stderr)
    return 1


def _coletar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    rc = manifesto.obter(args.recurso)
    inicio = deps.agora()
    hoje = data_brasilia(inicio)
    if rc.recurso.publicacao == "snapshot":
        if args.competencia or args.de is not None or args.ate is not None:
            raise ErroUso(f"{rc.id} é snapshot: não aceita --competencia, --de ou --ate")
        tarefas = [tarefa_snapshot(rc, hoje)]
    else:
        if args.ate is not None and args.de is None:
            raise ErroUso("--ate exige --de")
        if args.competencia:
            if not (len(args.competencia) == 4 and args.competencia.isdigit()):
                raise ErroUso("--competencia deve ser um ano, como 2025")
            anos_alvo = [int(args.competencia)]
        elif args.de is not None:
            anos_alvo = list(range(args.de, (args.ate or hoje.year) + 1))
        else:
            raise ErroUso(f"{rc.id}: informe --competencia ou --de/--ate")
        tarefas = [Tarefa(rc, Competencia.de_ano(ano)) for ano in anos_alvo]
    historico = repo.carregar_historico()
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _recarregar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    rc = manifesto.obter(args.recurso)
    try:
        competencia = Competencia.de_rotulo(args.competencia)
    except ValueError:
        raise ErroUso(f"competência inválida: {args.competencia}") from None
    hoje = data_brasilia(deps.agora())
    antiga = (hoje - competencia.data).days >= EXPIRACAO_SNAPSHOT_DIAS
    if args.destino == "raw" and rc.recurso.publicacao == "snapshot" and antiga:
        raise ErroUso(
            f"snapshot com {EXPIRACAO_SNAPSHOT_DIAS} dias ou mais expiraria no raw: "
            "use --destino replay"
        )
    if args.coleta_id:
        coleta = repo.buscar_coleta(args.coleta_id)
        if coleta is None:
            raise ErroUso(f"coleta {args.coleta_id} não encontrada")
        origem = (f"{coleta['orgao']}.{coleta['recurso']}", coleta["competencia"])
        if origem != (rc.id, competencia.rotulo):
            raise ErroUso(
                f"coleta {args.coleta_id} é de {origem[0]} competência {origem[1]}, "
                f"não de {rc.id} competência {competencia.rotulo}"
            )
        if not coleta["arquivo_original"]:
            raise ErroUso(f"coleta {args.coleta_id} ({coleta['status']}) está sem original no GCS")
        uri = coleta["arquivo_original"]
    else:
        prefixo = (
            f"{deps.config.prefixo_gcs}originais/{rc.orgao}/{rc.recurso.id}/"
            f"competencia={competencia.rotulo}/"
        )
        objetos = deps.armazenamento.listar(prefixo)
        if not objetos:
            raise ErroUso(f"nenhum original em gs://{deps.config.bucket}/{prefixo}")
        uri = f"gs://{deps.config.bucket}/{objetos[-1]}"
    historico = repo.carregar_historico()
    registro = recarregar(rc, competencia, uri, historico, deps, str(uuid.uuid4()), args.destino)
    repo.registrar_coleta(registro)
    log.info(
        "%s %s status=%s linhas=%s", rc.id, competencia.rotulo, registro.status, registro.linhas
    )
    if registro.erro:
        log.error(registro.erro)
    return 0 if registro.status == "recarregada" else 1


def main(
    argv: list[str] | None = None,
    fabrica: Fabrica | None = None,
    env: Mapping[str, str] | None = None,
    dbt: RodarDbt | None = None,
) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    deps: Dependencias | None = None
    try:
        config = carregar_config(env)
        log.info("ambiente=%s projeto=%s", config.ambiente, config.projeto)
        manifesto = carregar_manifesto(args.fontes)
        if fabrica is None:
            from coletor.gcp import montar_dependencias

            fabrica = montar_dependencias
        deps = fabrica(config)
        repo = RepositorioMeta(deps.warehouse, config)
        if args.comando == "vigia":
            return _vigia(deps, repo)  # conta do vigia só lê: não cria tabelas
        repo.preparar()
        if args.comando == "pipeline":
            return _pipeline(args, manifesto, deps, repo, dbt or rodar_dbt)
        if args.comando == "fontes":
            return _fontes(manifesto, repo)
        if args.comando == "executar":
            return _executar(args, manifesto, deps, repo)
        if args.comando == "coletar":
            return _coletar(args, manifesto, deps, repo)
        return _recarregar(args, manifesto, deps, repo)
    except (ErroConfig, ErroManifesto, ErroUso) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    finally:
        if deps is not None:
            deps.http.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Passo 6: rodar e confirmar que passa**

Executar: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Esperado: `107 passed, 2 deselected`.

Depois, conferir o `dbt build` vazio pela CLI, sem nuvem:

```bash
ELEITORADO_PROJETO=x uv run dbt build --project-dir dbt --profiles-dir dbt --target prod
```

Esperado: `Nothing to do` e código de saída 0.

- [ ] **Passo 7: commit**

```bash
git add coletor/meta.py coletor/execucao.py coletor/cli.py tests/test_pipeline.py
git commit -m "feat(coletor): comandos pipeline (coleta + dbt) e vigia" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 4: imagem Docker e CI

**Arquivos:**
- Criar: `Dockerfile`, `.dockerignore` e `.github/workflows/ci.yml`

**Interfaces:**
- Consome: `coletor pipeline` (Tarefa 3) e o projeto `dbt/` (Tarefa 1).
- Produz:
  - a imagem com `ENTRYPOINT ["coletor"]`, `CMD ["pipeline"]` e `ELEITORADO_VERSAO`, vinda do build-arg `VERSAO`;
  - o CI com os jobs `testes` e `imagem`.

- [ ] **Passo 1: escrever os arquivos**

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependências primeiro, para aproveitar o cache de camadas
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY coletor ./coletor
COPY fontes ./fontes
COPY dbt ./dbt
RUN uv sync --frozen --no-dev

ARG VERSAO=local
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ELEITORADO_VERSAO=$VERSAO

ENTRYPOINT ["coletor"]
CMD ["pipeline"]
```

`.dockerignore`:

```
.git
.venv
.env*
.gcloud
.superpowers
**/__pycache__
.pytest_cache
.ruff_cache
dbt/target
dbt/logs
dbt/dbt_packages
docs
infra
tests
scripts
```

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  testes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest
      - name: dbt parse (sem conexão)
        run: uv run dbt parse --project-dir dbt --profiles-dir dbt --target ci
        env:
          ELEITORADO_PROJETO: ci-sem-conexao

  imagem:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: build da imagem (sem publicar)
        run: docker build --build-arg VERSAO=${{ github.sha }} -t pipeline:ci .
      - name: a imagem responde
        run: docker run --rm pipeline:ci --help
```

- [ ] **Passo 2: commit e PR para validar no GitHub**

O Docker local está desligado, então o build é validado pelo CI.

```bash
git add Dockerfile .dockerignore .github/workflows/ci.yml
git commit -m "ci: imagem Docker do pipeline e workflow de testes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin feat/plano-2-operacao
gh pr create --base feat/plano-1-coletor --head feat/plano-2-operacao --title "Plano 2: operação na nuvem" --body "Implementa docs/superpowers/plans/2026-10-03-plano-2-operacao.md (em andamento)."
gh pr checks --watch
```

Esperado: os jobs `testes` e `imagem` passam. O passo `docker run --rm pipeline:ci --help` mostra os comandos `fontes`, `executar`, `coletar`, `pipeline`, `vigia` e `recarregar`. Se o `imagem` falhar, corrija o Dockerfile e faça novo push até ficar verde.

---

### Tarefa 5: infraestrutura de execução

**Arquivos:**
- Modificar: `infra/main.tf` (APIs), `infra/variables.tf` (variáveis novas) e `infra/armazenamento.tf` (dataset `ci`)
- Criar: `infra/execucao.tf`, `infra/github.tf` e `infra/custos.tf`

**Interfaces:**
- Consome: `google_storage_bucket.dados`, `google_bigquery_dataset.prod` e `local.datasets` (Plano 1).
- Produz:
  - o Artifact Registry `eleitorado`;
  - as contas `pipeline@`, `scheduler@`, `deployer@` e `ci-github@`;
  - o job `pipeline` e o scheduler `pipeline-diario`;
  - o pool `github` com o provider `github-oidc`;
  - o orçamento `eleitorado-mensal`;
  - os outputs `wif_provider`, `sa_deployer` e `sa_ci`.

- [ ] **Passo 1: APIs, variáveis e dataset `ci`**

Em `infra/main.tf`, a lista de `google_project_service.apis` passa a ser:

```hcl
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])
```

Acrescentar ao final de `infra/variables.tf`:

```hcl
variable "github_repo" {
  description = "Repositorio autorizado a autenticar no GCP pelo GitHub Actions (dono/nome)"
  type        = string
  default     = "bonvenuto/eleitorado"
}

variable "conta_faturamento" {
  description = "ID da conta de faturamento, usado no orcamento"
  type        = string
}

variable "orcamento_mensal_brl" {
  description = "Orcamento mensal em reais; a conta de faturamento e em BRL (R$ 30 sao cerca de US$ 5)"
  type        = number
  default     = 30
}

variable "imagem_inicial" {
  description = "Imagem usada so na criacao do job; o deploy do GitHub Actions troca pela imagem real"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/job:latest"
}
```

Em `infra/armazenamento.tf`, antes de `output "bucket_dados"`:

```hcl
resource "google_bigquery_dataset" "ci" {
  dataset_id                  = "ci"
  location                    = var.regiao
  description                 = "Eleitorado: relacoes temporarias dos testes unitarios do dbt"
  default_table_expiration_ms = 86400000 # 1 dia
  depends_on                  = [google_project_service.apis]
}
```

- [ ] **Passo 2: execução, GitHub e custos**

`infra/execucao.tf`:

```hcl
# Imagem, contas de serviço, Cloud Run Job e agendamento diário.

resource "google_artifact_registry_repository" "eleitorado" {
  location      = var.regiao
  repository_id = "eleitorado"
  format        = "DOCKER"

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "manter-2-recentes"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }
  cleanup_policies {
    id     = "apagar-antigas"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "86400s"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "pipeline" {
  account_id   = "pipeline"
  display_name = "Pipeline diario (coleta + dbt)"
}

resource "google_service_account" "scheduler" {
  account_id   = "scheduler"
  display_name = "Cloud Scheduler: dispara o job"
}

resource "google_service_account" "deployer" {
  account_id   = "deployer"
  display_name = "GitHub Actions: publica a imagem e atualiza o job"
}

resource "google_service_account" "ci" {
  account_id   = "ci-github"
  display_name = "GitHub Actions: vigia e testes do dbt"
}

# pipeline: grava nos datasets de produção e só cria objetos no bucket (sem apagar nem sobrescrever)
resource "google_project_iam_member" "pipeline_job_user" {
  project = var.projeto
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_editor" {
  for_each   = toset(local.datasets)
  dataset_id = google_bigquery_dataset.prod[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_cria_objetos" {
  bucket = google_storage_bucket.dados.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_le_objetos" {
  bucket = google_storage_bucket.dados.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_cloud_run_v2_job" "pipeline" {
  name                = "pipeline"
  location            = var.regiao
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.pipeline.email
      timeout         = "3600s"
      max_retries     = 1
      containers {
        image = var.imagem_inicial
        args  = ["pipeline"]
        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
        env {
          name  = "ELEITORADO_PROJETO"
          value = var.projeto
        }
        env {
          name  = "ELEITORADO_BUCKET"
          value = google_storage_bucket.dados.name
        }
        env {
          name  = "ELEITORADO_REGIAO"
          value = var.regiao
        }
        env {
          name  = "ELEITORADO_AMBIENTE"
          value = "prod"
        }
        env {
          name  = "ELEITORADO_ORIGEM"
          value = "agendada"
        }
      }
    }
  }

  # A imagem é trocada pelo workflow de deploy; o Terraform não a reverte.
  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoca" {
  name     = google_cloud_run_v2_job.pipeline.name
  location = var.regiao
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "pipeline_diario" {
  name             = "pipeline-diario"
  region           = var.regiao
  schedule         = "30 7 * * *"
  time_zone        = "America/Sao_Paulo"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.projeto}/locations/${var.regiao}/jobs/${google_cloud_run_v2_job.pipeline.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoca]
}
```

`infra/github.tf`:

```hcl
# Autenticação do GitHub Actions sem chave (Workload Identity Federation).

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# deployer: só a partir da branch principal (o provider já restringe ao repositório)
resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.ref/refs/heads/main"
}

resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_publica" {
  location   = var.regiao
  repository = google_artifact_registry_repository.eleitorado.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_cloud_run_v2_job_iam_member" "deployer_atualiza" {
  name     = google_cloud_run_v2_job.pipeline.name
  location = var.regiao
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_age_como_pipeline" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# ci: lê meta (vigia) e grava no dataset ci (testes unitários do dbt, Plano 3)
resource "google_project_iam_member" "ci_job_user" {
  project = var.projeto
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_bigquery_dataset_iam_member" "ci_le_meta" {
  dataset_id = google_bigquery_dataset.prod["meta"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_bigquery_dataset_iam_member" "ci_edita_ci" {
  dataset_id = google_bigquery_dataset.ci.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ci.email}"
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "sa_deployer" {
  value = google_service_account.deployer.email
}

output "sa_ci" {
  value = google_service_account.ci.email
}
```

`infra/custos.tf`:

```hcl
# Orçamento mensal com alertas por e-mail aos administradores da conta de faturamento.

data "google_project" "atual" {}

resource "google_billing_budget" "mensal" {
  billing_account = var.conta_faturamento
  display_name    = "eleitorado-mensal"

  budget_filter {
    projects               = ["projects/${data.google_project.atual.number}"]
    credit_types_treatment = "EXCLUDE_ALL_CREDITS" # custo bruto, antes do crédito de desenvolvedor
  }

  amount {
    specified_amount {
      currency_code = "BRL"
      units         = tostring(var.orcamento_mensal_brl)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.apis]
}
```

- [ ] **Passo 3: validar e planejar**

No PowerShell, com `. .\scripts\ambiente.ps1`:

```powershell
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
terraform -chdir=infra plan "-var=projeto=$env:ELEITORADO_PROJETO" "-var=conta_faturamento=01A56D-15D9DD-C83237"
```

Esperado: `Plan: 35 to add, 0 to change, 0 to destroy.` Nada do Plano 1 é alterado.

- [ ] **Passo 4: aplicar**

```powershell
terraform -chdir=infra apply -auto-approve "-var=projeto=$env:ELEITORADO_PROJETO" "-var=conta_faturamento=01A56D-15D9DD-C83237"
terraform -chdir=infra output
```

Esperado: `Apply complete! Resources: 35 added`. Os outputs são `wif_provider = "projects/<número>/locations/global/workloadIdentityPools/github/providers/github-oidc"`, `sa_deployer = "deployer@dados-publicos-prd.iam.gserviceaccount.com"` e `sa_ci = "ci-github@dados-publicos-prd.iam.gserviceaccount.com"`.

- [ ] **Passo 5: conferir**

```bash
gcloud run jobs describe pipeline --region southamerica-east1 --format="value(template.template.serviceAccount,template.template.timeout)"
gcloud scheduler jobs describe pipeline-diario --location southamerica-east1 --format="value(schedule,timeZone,state)"
```

Esperado: `pipeline@dados-publicos-prd.iam.gserviceaccount.com  3600s` e `30 7 * * *  America/Sao_Paulo  ENABLED`.

- [ ] **Passo 6: commit**

```bash
git add infra/
git commit -m "feat(infra): Cloud Run Job, Scheduler, contas de serviço, WIF do GitHub e orçamento" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 6: deploy e vigia no GitHub Actions

**Arquivos:**
- Criar: `.github/workflows/deploy.yml` e `.github/workflows/vigia.yml`
- Configurar: as variáveis do repositório `GCP_PROJETO`, `GCP_WIF_PROVIDER`, `GCP_SA_DEPLOYER` e `GCP_SA_CI`

**Interfaces:**
- Consome: os outputs da Tarefa 5 e o comando `coletor vigia` (Tarefa 3).
- Produz: deploy a cada push em `main` e vigia diário às 10:00 de Brasília.

- [ ] **Passo 1: escrever os workflows**

`.github/workflows/deploy.yml`:

```yaml
name: deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

concurrency:
  group: deploy
  cancel-in-progress: false

env:
  REGIAO: southamerica-east1
  IMAGEM: southamerica-east1-docker.pkg.dev/${{ vars.GCP_PROJETO }}/eleitorado/pipeline:${{ github.sha }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_SA_DEPLOYER }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker "$REGIAO-docker.pkg.dev" --quiet
      - run: docker build --build-arg VERSAO=${{ github.sha }} -t "$IMAGEM" .
      - run: docker push "$IMAGEM"
      - run: >-
          gcloud run jobs update pipeline
          --project "${{ vars.GCP_PROJETO }}" --region "$REGIAO" --image "$IMAGEM"
```

`.github/workflows/vigia.yml`:

```yaml
name: vigia

on:
  schedule:
    - cron: "0 13 * * *" # 10:00 em Brasília
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  vigia:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen --no-dev
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_SA_CI }}
      - name: execução agendada de hoje terminou com sucesso?
        run: uv run coletor vigia
        env:
          ELEITORADO_PROJETO: ${{ vars.GCP_PROJETO }}
          ELEITORADO_BUCKET: ${{ vars.GCP_PROJETO }}-dados
          ELEITORADO_AMBIENTE: prod
```

- [ ] **Passo 2: variáveis do repositório**

Usar os valores de `terraform -chdir=infra output`:

```bash
gh variable set GCP_PROJETO --body dados-publicos-prd
gh variable set GCP_WIF_PROVIDER --body "$(terraform -chdir=infra output -raw wif_provider)"
gh variable set GCP_SA_DEPLOYER --body "$(terraform -chdir=infra output -raw sa_deployer)"
gh variable set GCP_SA_CI --body "$(terraform -chdir=infra output -raw sa_ci)"
gh variable list
```

Esperado: as quatro variáveis listadas.

- [ ] **Passo 3: commit e push**

```bash
git add .github/workflows/deploy.yml .github/workflows/vigia.yml
git commit -m "ci: deploy da imagem e vigia diário da execução agendada" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
gh pr checks --watch
```

Esperado: o CI do PR continua verde. O deploy e o vigia só passam a rodar quando estiverem em `main` (Tarefa 8).

---

### Tarefa 7: cota diária do BigQuery

**Arquivos:** nenhum. É uma configuração do projeto, registrada no README na Tarefa 8.

**Interfaces:**
- Consome: o projeto `dados-publicos-prd`.
- Produz: o limite de 30720 MiB (30 GiB) consultados por dia no projeto.

- [ ] **Passo 1: aplicar**

O limite padrão é 209715200 MiB (200 TiB por dia). A redução exige `--force`.

```bash
gcloud alpha services quota update --service=bigquery.googleapis.com --consumer=projects/dados-publicos-prd --metric=bigquery.googleapis.com/quota/query/usage --unit='1/d/{project}' --value=30720 --force
```

- [ ] **Passo 2: conferir**

```bash
gcloud alpha services quota list --service=bigquery.googleapis.com --consumer=projects/dados-publicos-prd --filter="metric=bigquery.googleapis.com/quota/query/usage" --format="json(consumerQuotaLimits)"
```

Esperado: no limite `1/d/{project}`, o `effectiveLimit` é `30720`.

---

### Tarefa 8: entrada em operação

**Os merges são decisão do usuário: peça o ok antes do Passo 1.**

**Arquivos:**
- Modificar: `README.md`

**Interfaces:**
- Consome: tudo o que veio antes.
- Produz: o job diário rodando a imagem real, o vigia ativo e o critério 9 da spec (aviso de falha) verificado.

- [ ] **Passo 1: README**

Substituir a seção `### Até a coleta agendada (Plano 2)` do `README.md` por:

```markdown
## Operação

- **Execução diária:** Cloud Scheduler `pipeline-diario` às 07:30 (Brasília) dispara o Cloud Run Job
  `pipeline`, que roda `coletor pipeline` (coleta + `dbt build`) e grava `meta.execucoes`.
- **Deploy:** cada push em `main` publica a imagem no Artifact Registry e atualiza o job
  (`.github/workflows/deploy.yml`).
- **Vigia:** às 10:00 (Brasília), `.github/workflows/vigia.yml` roda `coletor vigia`; se não houve
  execução agendada com sucesso no dia, o workflow falha e o GitHub avisa por e-mail.
- **Travas de custo:** orçamento de R$ 30/mês com alertas em 50/90/100% (sem créditos), cota de
  30 GiB consultados por dia no BigQuery e `maximum_bytes_billed` de 10 GiB no dbt.
- **Rodar o job à mão:** `gcloud run jobs execute pipeline --region southamerica-east1 --wait`.
```

```bash
git add README.md
git commit -m "docs: operação na nuvem no README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

- [ ] **Passo 2 (com o ok do usuário): merges**

```bash
gh pr merge 1 --merge
gh pr edit 2 --base main
gh pr checks 2 --watch
gh pr merge 2 --merge
gh run watch "$(gh run list --workflow deploy.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

Esperado: o deploy termina com sucesso, e a imagem do job passa a ser `southamerica-east1-docker.pkg.dev/dados-publicos-prd/eleitorado/pipeline:<sha>`.

Confira com:

```bash
gcloud run jobs describe pipeline --region southamerica-east1 --format="value(template.template.containers[0].image)"
```

- [ ] **Passo 3: o vigia avisa quando não houve execução**

Rode antes de qualquer execução agendada do dia:

```bash
gh workflow run vigia.yml && sleep 5 && gh run watch "$(gh run list --workflow vigia.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

Esperado: o run falha com `nenhuma execução agendada com sucesso em <hoje>`, e o GitHub manda e-mail ao usuário. Peça ao usuário que confirme o recebimento.

- [ ] **Passo 4: executar o job e conferir**

```bash
gcloud run jobs execute pipeline --region southamerica-east1 --wait
bq query --use_legacy_sql=false --format=pretty "SELECT origem, status, coletas_carregadas, coletas_sem_alteracao, coletas_falha, dbt_status, versao FROM \`dados-publicos-prd.meta.execucoes\` ORDER BY iniciada_em DESC LIMIT 1"
```

Esperado: a execução termina com sucesso, com `origem=agendada`, `status=sucesso`, `coletas_falha=0`, `dbt_status=sucesso` e `versao` igual ao SHA do merge.

- [ ] **Passo 5: o vigia aprova**

```bash
gh workflow run vigia.yml && sleep 5 && gh run watch "$(gh run list --workflow vigia.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

Esperado: o run passa.

- [ ] **Passo 6: o Scheduler consegue disparar o job**

```bash
gcloud scheduler jobs run pipeline-diario --location southamerica-east1
sleep 60
gcloud run jobs executions list --job pipeline --region southamerica-east1 --limit 2
```

Esperado: uma nova execução aparece, disparada pelo Scheduler. Ela termina com quase tudo `sem_alteracao`.

- [ ] **Passo 7: acompanhamento**

O critério 1 da spec pede 7 dias seguidos de execuções agendadas. Confira depois com:

```bash
bq query --use_legacy_sql=false "SELECT DATE(iniciada_em, 'America/Sao_Paulo') AS dia, status FROM \`dados-publicos-prd.meta.execucoes\` WHERE origem = 'agendada' ORDER BY 1"
```

## Depois deste plano

O Plano 3 cobre a modelagem dbt:
- datasets `staging`, `intermediate` e `marts`, e as permissões da conta `pipeline` neles;
- modelos, históricos SCD2, alertas e `monitor_fontes`;
- testes da seção 7.7 da spec e testes unitários do dbt no CI.
