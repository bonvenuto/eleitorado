# Plano 1: coletor e camada raw

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** construir o coletor Python (CLI `coletor`). Ele baixa as sete fontes da onda A, arquiva os originais no GCS e carrega o raw no BigQuery em `southamerica-east1`, registrando cada coleta em `meta`. Ao final do plano, o coletor roda localmente e o histórico completo está carregado em produção.

**Arquitetura:** cada recurso é declarado em `fontes/*.yaml`, e o adaptador (`arquivo` ou `api_json`) é escolhido pelo manifesto. O fluxo de cada coleta é:
1. baixar e calcular o hash do conteúdo;
2. deduplicar contra `meta.coletas`;
3. gravar o original imutável no GCS;
4. converter para Parquet, com todas as colunas como texto mais as colunas de controle;
5. substituir só a partição alvo no BigQuery, por load job.

GCS e BigQuery ficam atrás de duas interfaces pequenas (`Armazenamento` e `Warehouse`), que nos testes são substituídas por dublês em memória.

**Stack:** Python 3.12, uv, httpx, pyarrow, pydantic 2, PyYAML, google-cloud-bigquery, google-cloud-storage, pytest, respx, ruff e Terraform (provider google ≥ 6).

**Spec:** [docs/superpowers/specs/2026-10-03-ingestao-onda-a-design.md](../specs/2026-10-03-ingestao-onda-a-design.md). Este plano cobre as seções 3, 5, 6 e a parte de armazenamento da 8.2.

Próximos planos:
- **Plano 2, operação na nuvem:** imagem, Cloud Run Job, Scheduler, CI/CD, vigia e travas de custo.
- **Plano 3:** modelagem dbt.

## Restrições globais

- **Região:** `southamerica-east1` para o bucket, os datasets e qualquer outro recurso.
- **Ambiente Python:** Python ≥ 3.12, com dependências gerenciadas pelo `uv`. Pisos testados: `google-cloud-bigquery>=3.46.1`, `google-cloud-storage>=3.16.0`, `httpx>=0.28.1`, `pyarrow>=25.0.1`, `pydantic>=2.13.5`, `pyyaml>=6.0.3`, `tzdata>=2026.5`; para desenvolvimento, `pytest>=9.1.1`, `respx>=0.23.1` e `ruff>=0.16.10`.
- **Colunas do raw:**
  - todas as colunas de dados são STRING;
  - colunas de controle: `_coleta_id`, `_competencia`, `_competencia_data`, `_linha`, `_arquivo_original` e `_carregado_em`.
- **Partições:**
  - snapshot: partição diária por `_competencia_data`, com expiração de 60 dias;
  - por competência: partição anual, sem expiração.
- **Caminhos no GCS:**
  - originais: `originais/<órgão>/<recurso>/competencia=<c>/<AAAAMMDDTHHMMSS>_<sha256_conteudo[:12]>.<ext>`. Nunca são sobrescritos;
  - Parquet de carga: `carga/<órgão>/<recurso>/competencia=<c>/<coleta_id>.parquet`.
- **Datasets:** `meta`, `raw_camara`, `raw_senado`, `raw_cgu`, `raw_ibge` e `replay`. Em desenvolvimento, os mesmos nomes com sufixo `_dev`, e o prefixo `dev/` no bucket.
- **HTTP:** 5 tentativas, com espera exponencial e jitter, respeitando `Retry-After`. Timeout de 10 s para conexão e 120 s para leitura.
- **Credenciais isoladas:** nunca alterar a configuração `prod` do gcloud nem o ADC global da máquina. Este projeto usa `CLOUDSDK_CONFIG` e `GOOGLE_APPLICATION_CREDENTIALS` próprios, definidos em `.env`.
- **Segredos:** nenhum segredo vai para o git, nem `.env` ou `.env.prod`.
- **Nomes:** módulos, funções e colunas em português, em snake_case.
- **Antes de cada commit:** `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest` precisam passar.
- **Commits:** mensagens em português, terminadas com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Foco de revisão

Situações que a spec implica, mas que os fluxos principais não exercitam. Cada uma tem um teste na tarefa responsável:

1. **Coleta repetida no mesmo segundo** (por exemplo, `--forcar` duas vezes seguidas). O caminho do original colide. Esperado: reaproveitar o objeto existente e carregar normalmente. Coberto na Tarefa 8 (`GcsArmazenamento.enviar`) e na Tarefa 9 (`test_coleta_forcada_duas_vezes_no_mesmo_segundo_reaproveita_o_original`).
2. **Fonte responde 200 com uma página HTML de erro** no lugar do ZIP ou do JSON. Esperado: `falha` com mensagem clara e nada carregado. Coberto na Tarefa 9 (`test_html_de_erro_no_lugar_do_zip_vira_falha`, `test_json_invalido_na_api_vira_falha`).
3. **Execução interrompida** depois de arquivar o original e antes de carregar. Esperado: a próxima execução refaz a coleta sem conflito de nomes. Coberto na Tarefa 9 (`test_execucao_interrompida_antes_da_carga_e_refeita_na_seguinte`).
4. **CSV maior que um bloco de leitura**, como a CEAP do ano corrente, com dezenas de MB. Esperado: `_linha` contínua entre blocos e contagem exata. Coberto na Tarefa 5 (`test_csv_maior_que_um_bloco_numera_linhas_sem_saltos`).
5. **Coluna nova e coluna ausente** entre cargas da mesma tabela. Esperado: a carga funciona, a coluna nova é adicionada e a ausente fica nula. Coberto na Tarefa 12 (`test_coluna_nova_e_coluna_ausente_entre_cargas`, integração).

## Decisões de implementação que refinam a spec

- **`payload` como texto:** nas APIs, `payload` é STRING com JSON canônico. O staging do dbt lê com `JSON_VALUE` e `PARSE_JSON`. Assim há um caminho único de carga, via Parquet.
- **JSON em `meta.coletas`:** `parametros` e `colunas` são STRING com JSON.
- **Status novos:**
  - `nao_publicada`: HTTP 404 no ano corrente, no primeiro trimestre. Confirmado em 03/10/2026: `Ano-2027.csv.zip` e a CEAPS de 2027 retornam 404;
  - `recarregada`: cargas feitas por `coletor recarregar`.
- **Colunas extras:** `meta.coletas` ganha `competencia_data` e `destino`; `meta.execucoes` ganha `coletas_nao_publicadas`.
- **Deduplicação por competência:** os snapshots por data de coleta (deputados, senadores, municípios) geram uma partição por coleta. Como a spec diz, a deduplicação por hash vale dentro da mesma competência.
- **`coletor pipeline`:** a coleta seguida do dbt fica para o Plano 2. Aqui, `coletor executar` registra a execução com `dbt_status` nulo.
- **Objeto existente no GCS:** `GcsArmazenamento.enviar` reaproveita o objeto se ele já existir. Os caminhos são endereçados por conteúdo ou pelo id da coleta.
- **Datasets `_dev`:** as tabelas expiram em 30 dias, para dados de teste não se acumularem.
- **Isolamento do gcloud:** em vez de `gcloud config configurations create`, o projeto usa um diretório de configuração próprio (`CLOUDSDK_CONFIG=.gcloud/`) e o ADC desse diretório (`GOOGLE_APPLICATION_CREDENTIALS`). Assim, nem a configuração `prod` nem o ADC global da máquina são tocados.
- **Log de ambiente:** a CLI registra o ambiente e o projeto na primeira linha do log, para que uma execução em produção com variáveis de dev seja percebida antes de gravar.

## Estrutura de arquivos

```
pyproject.toml, uv.lock        projeto e dependências (uv)
.gitignore, .gitattributes     .env*, .gcloud/, estado do Terraform; LF nos textos
.env.exemplo                   modelo de configuração local (o .env real não vai para o git)
scripts/ambiente.ps1           carrega um .env na sessão do PowerShell
fontes/{camara,senado,cgu,ibge}.yaml   manifesto da onda A
coletor/
  config.py          Config a partir de variáveis de ambiente
  manifesto.py       modelos pydantic do manifesto e carga dos YAML
  competencias.py    Competencia, fuso de Brasília, legislaturas
  nomes.py           normalização dos nomes de coluna
  hashes.py          SHA-256 de arquivos e de registros
  http.py            cliente httpx com retentativas
  cgu.py             descoberta da data do arquivo na página da CGU
  conversao.py       CSV/JSON → Parquet com colunas de controle
  adaptadores/
    __init__.py      registro: adaptador_para(recurso)
    base.py          Extracao, Preparado, ErroColeta, preencher(), extensao_de()
    arquivo.py       download de CSV/ZIP
    api_json.py      APIs JSON paginadas
  armazenamento.py   interface Armazenamento, caminhos e GcsArmazenamento
  warehouse.py       interface Warehouse, Particionamento e BigQueryWarehouse
  meta.py            RegistroColeta, RegistroExecucao, HistoricoColetas, RepositorioMeta
  coleta.py          fluxo coletar() e recarregar(), Dependencias
  agenda.py          tarefas com prazo vencido
  execucao.py        rodar() e ResumoColetas
  gcp.py             montagem das dependências reais
  cli.py             comandos fontes, executar, coletar, recarregar
tests/
  amostras.py        constantes e amostras fictícias das fontes
  fakes.py           FakeArmazenamento e FakeWarehouse
  conftest.py        fixtures
  test_*.py          um arquivo por tarefa
  integracao/test_gcp.py
infra/{versions,variables,main,armazenamento}.tf
README.md
```

---

### Tarefa 1: esqueleto do projeto e configuração

**Arquivos:**
- Criar: `pyproject.toml`, `.gitignore`, `.gitattributes`, `.env.exemplo`, `scripts/ambiente.ps1`, `coletor/__init__.py`, `coletor/config.py`, `tests/__init__.py`, `tests/test_config.py`
- Gerado: `uv.lock`

**Interfaces:**
- Consome: nada.
- Produz: `Config(projeto, bucket, regiao, ambiente, versao, origem)` com `.prefixo_gcs -> str` e `.dataset(nome: str) -> str`; `carregar_config(env: Mapping[str, str] | None = None) -> Config`; `ErroConfig(Exception)`.

- [ ] **Passo 1: criar o projeto e os pacotes vazios**

`pyproject.toml`:

```toml
[project]
name = "eleitorado"
version = "0.1.0"
description = "Ingestão de dados públicos no BigQuery"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
coletor = "coletor.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["coletor"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integracao: acessa GCP e fontes reais"]
addopts = "-m 'not integracao'"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

`coletor/__init__.py`:

```python
"""Coletor de dados públicos para o BigQuery."""
```

`tests/__init__.py`: arquivo vazio.

- [ ] **Passo 2: instalar as dependências**

Executar:

```bash
uv add google-cloud-bigquery google-cloud-storage httpx pyarrow pydantic pyyaml tzdata
uv add --dev pytest respx ruff
```

Esperado: `uv.lock` criado e `pyproject.toml` com as listas `dependencies` e `[dependency-groups] dev` preenchidas. O `tzdata` é obrigatório no Windows, porque `zoneinfo` não traz a base de fusos.

- [ ] **Passo 3: criar os arquivos de ambiente**

`.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/

# Configuração local e credenciais
.env*
!.env.exemplo
.gcloud/

# Terraform
infra/.terraform/
*.tfstate
*.tfstate.*

# dbt (planos seguintes)
dbt/target/
dbt/dbt_packages/
dbt/logs/
```

`.gitattributes`:

```gitattributes
* text=auto eol=lf
```

`.env.exemplo`:

```dotenv
# Copie para .env (desenvolvimento) e .env.prod (produção). Nenhum dos dois vai para o git.
ELEITORADO_PROJETO=eleitorado-0000
ELEITORADO_BUCKET=eleitorado-0000-dados
ELEITORADO_REGIAO=southamerica-east1
ELEITORADO_AMBIENTE=dev
# gcloud e credenciais deste projeto, isolados da configuração "prod" da máquina
CLOUDSDK_CONFIG=C:/git/eleitorado/.gcloud
GOOGLE_APPLICATION_CREDENTIALS=C:/git/eleitorado/.gcloud/application_default_credentials.json
```

`scripts/ambiente.ps1`:

```powershell
# Carrega as variáveis de um arquivo .env na sessão atual do PowerShell.
# Uso: . .\scripts\ambiente.ps1             (desenvolvimento: .env)
#      . .\scripts\ambiente.ps1 .env.prod   (produção)
param([string]$Arquivo = ".env")
$caminho = Join-Path (Split-Path $PSScriptRoot -Parent) $Arquivo
if (-not (Test-Path $caminho)) { throw "Arquivo não encontrado: $caminho" }
Get-Content $caminho | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}
Write-Host "Ambiente $env:ELEITORADO_AMBIENTE carregado (projeto $env:ELEITORADO_PROJETO)"
```

- [ ] **Passo 4: escrever o teste que falha**

`tests/test_config.py`:

```python
import pytest

from coletor.config import ErroConfig, carregar_config


def test_config_le_variaveis_e_aplica_padroes():
    config = carregar_config({"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b"})
    assert (config.regiao, config.ambiente, config.versao, config.origem) == (
        "southamerica-east1",
        "dev",
        "local",
        "manual",
    )
    assert config.dataset("raw_cgu") == "raw_cgu_dev"
    assert config.prefixo_gcs == "dev/"


def test_config_de_producao_nao_tem_sufixo():
    config = carregar_config(
        {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "prod"}
    )
    assert config.dataset("raw_cgu") == "raw_cgu"
    assert config.prefixo_gcs == ""


def test_config_sem_bucket_falha():
    with pytest.raises(ErroConfig, match="ELEITORADO_BUCKET"):
        carregar_config({"ELEITORADO_PROJETO": "p"})


def test_config_com_ambiente_invalido_falha():
    with pytest.raises(ErroConfig, match="dev ou prod"):
        carregar_config(
            {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "x"}
        )
```

- [ ] **Passo 5: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_config.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.config'`.

- [ ] **Passo 6: implementar**

`coletor/config.py`:

```python
"""Configuração do coletor, lida de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

AMBIENTES = ("dev", "prod")


class ErroConfig(Exception):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class Config:
    projeto: str
    bucket: str
    regiao: str
    ambiente: str
    versao: str
    origem: str

    @property
    def prefixo_gcs(self) -> str:
        return "dev/" if self.ambiente == "dev" else ""

    def dataset(self, nome: str) -> str:
        """Nome do dataset no ambiente: `raw_cgu` vira `raw_cgu_dev` em dev."""
        return f"{nome}_dev" if self.ambiente == "dev" else nome


def carregar_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    faltando = [nome for nome in ("ELEITORADO_PROJETO", "ELEITORADO_BUCKET") if not env.get(nome)]
    if faltando:
        raise ErroConfig(f"variáveis de ambiente ausentes: {', '.join(faltando)}")
    ambiente = env.get("ELEITORADO_AMBIENTE", "dev")
    if ambiente not in AMBIENTES:
        raise ErroConfig(f"ELEITORADO_AMBIENTE deve ser dev ou prod, recebido: {ambiente!r}")
    origem = env.get("ELEITORADO_ORIGEM", "manual")
    if origem not in ("manual", "agendada"):
        raise ErroConfig(f"ELEITORADO_ORIGEM deve ser manual ou agendada, recebido: {origem!r}")
    return Config(
        projeto=env["ELEITORADO_PROJETO"],
        bucket=env["ELEITORADO_BUCKET"],
        regiao=env.get("ELEITORADO_REGIAO", "southamerica-east1"),
        ambiente=ambiente,
        versao=env.get("ELEITORADO_VERSAO", "local"),
        origem=origem,
    )
```

- [ ] **Passo 7: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_config.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `4 passed`, `All checks passed!` e nenhum arquivo a reformatar.

- [ ] **Passo 8: commit**

```bash
git add pyproject.toml uv.lock .gitignore .gitattributes .env.exemplo scripts/ambiente.ps1 coletor/__init__.py coletor/config.py tests/__init__.py tests/test_config.py
git commit -m "feat(coletor): esqueleto do projeto e configuração por ambiente" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 2: manifesto de fontes

**Arquivos:**
- Criar: `coletor/manifesto.py`, `fontes/camara.yaml`, `fontes/senado.yaml`, `fontes/cgu.yaml`, `fontes/ibge.yaml`, `tests/amostras.py`, `tests/test_manifesto.py`

**Interfaces:**
- Consome: nada.
- Produz:
  - modelos `Recurso`, `Formato`, `RegraCompetencia`, `RegraCadencia`, `Iteracao` e `Orgao` (pydantic, `extra="forbid"`);
  - `RecursoCompleto(orgao: str, recurso: Recurso)` com `.id -> "orgao.recurso"`;
  - `Manifesto(recursos: dict[str, RecursoCompleto])` com `.obter(id) -> RecursoCompleto` e `.todos() -> list[RecursoCompleto]`;
  - `carregar_manifesto(diretorio: Path) -> Manifesto` e `ErroManifesto`.
- Produz para os testes (`tests/amostras.py`): `RAIZ`, `AGORA`, `CEAP_CSV`, `CNEP_CSV`, `PAGINA_CGU`, `CEAPS_JSON`, `senadores_json(versao)`, `pagina_deputados(ids, proxima)`, `zip_com(membros, data_hora)`, `json_bytes(dados)` e `recurso(**sobrescritas) -> Recurso`.

- [ ] **Passo 1: criar as amostras de teste**

As amostras usam documentos e nomes fictícios. Elas seguem o formato real verificado em 03/10/2026, sem copiar dados pessoais das fontes.

`tests/amostras.py`:

```python
"""Amostras reduzidas das fontes, com documentos e nomes fictícios."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coletor.manifesto import Recurso

RAIZ = Path(__file__).resolve().parents[1]

# 07:30 em Brasília (UTC-3) de 03/10/2026
AGORA = datetime(2026, 10, 3, 10, 30, tzinfo=UTC)

CEAP_CSV = (
    '"txNomeParlamentar";"cpf";"ideCadastro";"txtDescricao";"txtCNPJCPF";"vlrLiquido";"numAno"\n'
    '"DEPUTADO EXEMPLO";"00000000191";"1001";"LOCOMOÇÃO, ALIMENTAÇÃO E  HOSPEDAGEM";'
    '"11.222.333/0001-81";"3800";"2008"\n'
    '"LIDERANÇA DO PARTIDO";"";"";"TELEFONIA";"11.222.333/0001-81";"104.67";"2008"\n'
)

CNEP_CSV = (
    '"CADASTRO";"CÓDIGO DA SANÇÃO";"TIPO DE PESSOA";"CPF OU CNPJ DO SANCIONADO";'
    '"NOME DO SANCIONADO";"ABRAGÊNCIA DA SANÇÃO";"OBSERVAÇÕES"\n'
    '"CNEP";"1";"J";"11222333000181";"Empresa Exemplo Comércio Ltda";'
    '"Todas as Esferas em todos os Poderes";"linha 1\nlinha 2"\n'
    '"CNEP";"2";"F";"00000000191";"Pessoa Exemplo";"No órgão sancionador";""\n'
)

PAGINA_CGU = (
    "<html><script>var arquivos = [];\n"
    'arquivos.push({"ano" : "2026", "mes" : "10", "dia" : "02", "origem" :  "CEIS"});\n'
    "</script></html>"
)

CEAPS_JSON: list[dict[str, Any]] = [
    {
        "id": 2008080011403,
        "ano": 2008,
        "mes": 8,
        "codSenador": 3,
        "nomeSenador": "SENADOR EXEMPLO",
        "tipoDespesa": "Locomoção, hospedagem, alimentação, combustíveis e lubrificantes",
        "cpfCnpj": None,
        "fornecedor": None,
        "valorReembolsado": 386.6,
    },
    {
        "id": 2269008,
        "ano": 2008,
        "mes": 9,
        "codSenador": 3,
        "nomeSenador": "SENADOR EXEMPLO",
        "tipoDespesa": "Contratação de consultorias",
        "cpfCnpj": "11.222.333/0001-81",
        "fornecedor": "EMPRESA EXEMPLO",
        "valorReembolsado": 500,
    },
]


def senadores_json(versao: str) -> dict[str, Any]:
    return {
        "ListaParlamentarLegislatura": {
            "Metadados": {"Versao": versao},
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "3",
                            "NomeParlamentar": "A",
                        }
                    },
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "9",
                            "NomeParlamentar": "B",
                        }
                    },
                ]
            },
        }
    }


def pagina_deputados(ids: list[int], proxima: str | None) -> dict[str, Any]:
    links = [{"rel": "self", "href": "https://exemplo/self"}]
    if proxima:
        links.append({"rel": "next", "href": proxima})
    return {"dados": [{"id": i, "nome": f"Deputado {i}"} for i in ids], "links": links}


def zip_com(
    membros: dict[str, bytes], data_hora: tuple[int, ...] = (2026, 10, 2, 18, 0, 0)
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nome, conteudo in membros.items():
            info = zipfile.ZipInfo(nome, date_time=data_hora)
            arquivo.writestr(info, conteudo)
    return buffer.getvalue()


def json_bytes(dados: Any) -> bytes:
    return json.dumps(dados, ensure_ascii=False).encode("utf-8")


def recurso(**sobrescritas: Any) -> Recurso:
    """Recurso válido de teste; `sobrescritas` troca campos de primeiro nível."""
    base: dict[str, Any] = {
        "id": "cnep",
        "descricao": "teste",
        "fonte_oficial": "https://exemplo",
        "condicoes_uso": "teste",
        "adaptador": "arquivo",
        "url": "https://portaldatransparencia.gov.br/download-de-dados/cnep/{data}",
        "publicacao": "snapshot",
        "competencia": {
            "tipo": "data_arquivo",
            "pagina": "https://portaldatransparencia.gov.br/download-de-dados/cnep",
        },
        "cadencia": {"corrente": "diaria"},
        "formato": {"tipo": "csv", "compressao": "zip", "encoding": "cp1252"},
    }
    base.update(sobrescritas)
    return Recurso.model_validate(base)
```

- [ ] **Passo 2: escrever o teste que falha**

`tests/test_manifesto.py`:

```python
import pytest
from pydantic import ValidationError

from coletor.manifesto import ErroManifesto, carregar_manifesto
from tests.amostras import RAIZ, recurso


def test_manifesto_do_repositorio_tem_os_sete_recursos_da_onda_a():
    manifesto = carregar_manifesto(RAIZ / "fontes")
    assert sorted(manifesto.recursos) == [
        "camara.ceap",
        "camara.deputados",
        "cgu.ceis",
        "cgu.cnep",
        "ibge.municipios",
        "senado.ceaps",
        "senado.senadores",
    ]


def test_por_competencia_exige_ano_e_cadencia_anteriores():
    with pytest.raises(ValidationError, match="cadencia.anteriores"):
        recurso(
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2008},
            cadencia={"corrente": "diaria"},
        )


def test_data_arquivo_exige_pagina():
    with pytest.raises(ValidationError, match="pagina"):
        recurso(competencia={"tipo": "data_arquivo"})


def test_campo_desconhecido_no_manifesto_e_rejeitado(tmp_path):
    (tmp_path / "x.yaml").write_text(
        "orgao: x\nnome: X\nportal: https://x\nrecursos: []\ncampo_inventado: 1\n", encoding="utf-8"
    )
    with pytest.raises(ErroManifesto, match="x.yaml"):
        carregar_manifesto(tmp_path)


def test_recurso_duplicado_entre_arquivos_e_rejeitado(tmp_path):
    texto = (RAIZ / "fontes" / "ibge.yaml").read_text(encoding="utf-8")
    (tmp_path / "a.yaml").write_text(texto, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(texto, encoding="utf-8")
    with pytest.raises(ErroManifesto, match="duplicado"):
        carregar_manifesto(tmp_path)


def test_recurso_inexistente():
    manifesto = carregar_manifesto(RAIZ / "fontes")
    with pytest.raises(ErroManifesto, match="desconhecido"):
        manifesto.obter("cgu.nao_existe")
```

- [ ] **Passo 3: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_manifesto.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.manifesto'`.

- [ ] **Passo 4: implementar o modelo**

`coletor/manifesto.py`:

```python
"""Modelos e carga do manifesto de fontes (`fontes/*.yaml`)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

Cadencia = Literal["diaria", "semanal", "mensal"]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegraCompetencia(_Modelo):
    tipo: Literal["ano", "data_arquivo", "data_coleta"]
    inicio: int | None = None
    pagina: str | None = None


class RegraCadencia(_Modelo):
    corrente: Cadencia
    anteriores: Cadencia | None = None


class Formato(_Modelo):
    tipo: Literal["csv", "json"]
    compressao: Literal["zip"] | None = None
    arquivo: str | None = None
    encoding: str = "utf-8"
    delimitador: str = ";"
    linhas_a_pular: int = 0


class Iteracao(_Modelo):
    parametro: str
    valores: Literal["legislaturas"]
    inicio: int


class Recurso(_Modelo):
    id: str
    descricao: str
    fonte_oficial: str
    condicoes_uso: str
    adaptador: Literal["arquivo", "api_json"]
    url: str
    parametros: dict[str, str | int] = {}
    publicacao: Literal["snapshot", "por_competencia"]
    competencia: RegraCompetencia
    cadencia: RegraCadencia
    formato: Formato
    paginacao: Literal["links_next", "nenhuma"] = "nenhuma"
    iteracao: Iteracao | None = None
    registros: str | None = None
    acesso: Literal["publico"] = "publico"

    @model_validator(mode="after")
    def _coerente(self) -> Recurso:
        regra = self.competencia
        if self.publicacao == "por_competencia":
            if regra.tipo != "ano" or regra.inicio is None:
                raise ValueError("por_competencia exige competencia.tipo 'ano' com 'inicio'")
            if self.cadencia.anteriores is None:
                raise ValueError("por_competencia exige cadencia.anteriores")
        elif regra.tipo == "ano":
            raise ValueError("snapshot exige competencia.tipo 'data_arquivo' ou 'data_coleta'")
        if regra.tipo == "data_arquivo" and not regra.pagina:
            raise ValueError("competencia.tipo 'data_arquivo' exige 'pagina'")
        if self.adaptador == "arquivo" and self.formato.tipo != "csv":
            raise ValueError("adaptador 'arquivo' exige formato.tipo 'csv'")
        if self.adaptador == "api_json" and self.formato.tipo != "json":
            raise ValueError("adaptador 'api_json' exige formato.tipo 'json'")
        return self


class Orgao(_Modelo):
    orgao: str
    nome: str
    portal: str
    recursos: list[Recurso]


@dataclass(frozen=True)
class RecursoCompleto:
    orgao: str
    recurso: Recurso

    @property
    def id(self) -> str:
        return f"{self.orgao}.{self.recurso.id}"


class ErroManifesto(Exception):
    """Manifesto inválido ou recurso inexistente."""


@dataclass(frozen=True)
class Manifesto:
    recursos: dict[str, RecursoCompleto]

    def obter(self, recurso_id: str) -> RecursoCompleto:
        try:
            return self.recursos[recurso_id]
        except KeyError:
            disponiveis = ", ".join(sorted(self.recursos))
            raise ErroManifesto(
                f"recurso desconhecido: {recurso_id} (disponíveis: {disponiveis})"
            ) from None

    def todos(self) -> list[RecursoCompleto]:
        return [self.recursos[chave] for chave in sorted(self.recursos)]


def carregar_manifesto(diretorio: Path) -> Manifesto:
    arquivos = sorted(diretorio.glob("*.yaml"))
    if not arquivos:
        raise ErroManifesto(f"nenhum arquivo .yaml em {diretorio}")
    recursos: dict[str, RecursoCompleto] = {}
    for arquivo in arquivos:
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
        try:
            orgao = Orgao.model_validate(dados)
        except ValidationError as erro:
            raise ErroManifesto(f"{arquivo.name}: {erro}") from erro
        for recurso in orgao.recursos:
            completo = RecursoCompleto(orgao.orgao, recurso)
            if completo.id in recursos:
                raise ErroManifesto(f"recurso duplicado: {completo.id}")
            recursos[completo.id] = completo
    return Manifesto(recursos)
```

- [ ] **Passo 5: escrever o manifesto da onda A**

Endereços, encodings e caminhos de registros foram verificados contra as fontes em 03/10/2026.

`fontes/camara.yaml`:

```yaml
orgao: camara
nome: Câmara dos Deputados
portal: https://dadosabertos.camara.leg.br/
recursos:
  - id: deputados
    descricao: Deputados de cada legislatura, da 53ª à atual
    fonte_oficial: https://dadosabertos.camara.leg.br/swagger/api.html
    condicoes_uso: >-
      Serviço de Dados Abertos da Câmara dos Deputados: acesso livre, sem necessidade de
      autorização (https://www2.camara.leg.br/transparencia/dados-abertos/dados-abertos).
    adaptador: api_json
    url: https://dadosabertos.camara.leg.br/api/v2/deputados
    parametros: {itens: 100}
    publicacao: snapshot
    competencia: {tipo: data_coleta}
    cadencia: {corrente: semanal}
    formato: {tipo: json}
    paginacao: links_next
    iteracao: {parametro: idLegislatura, valores: legislaturas, inicio: 53}
    registros: dados
  - id: ceap
    descricao: Despesas da Cota para o Exercício da Atividade Parlamentar (CEAP)
    fonte_oficial: https://dadosabertos.camara.leg.br/
    condicoes_uso: >-
      Serviço de Dados Abertos da Câmara dos Deputados: acesso livre, sem necessidade de
      autorização (https://www2.camara.leg.br/transparencia/dados-abertos/dados-abertos).
    adaptador: arquivo
    url: https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
    publicacao: por_competencia
    competencia: {tipo: ano, inicio: 2008}
    cadencia: {corrente: diaria, anteriores: semanal}
    formato:
      tipo: csv
      compressao: zip
      arquivo: Ano-{ano}.csv
      encoding: utf-8-sig
      delimitador: ";"
```

`fontes/senado.yaml`:

```yaml
orgao: senado
nome: Senado Federal
portal: https://www12.senado.leg.br/dados-abertos
recursos:
  - id: senadores
    descricao: Senadores com mandato da 53ª legislatura à atual
    fonte_oficial: https://legis.senado.leg.br/dadosabertos/docs/
    condicoes_uso: >-
      Dados abertos do Senado Federal; condições de uso em
      https://www12.senado.leg.br/dados-abertos.
    adaptador: api_json
    url: https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/{legislatura}.json
    publicacao: snapshot
    competencia: {tipo: data_coleta}
    cadencia: {corrente: semanal}
    formato: {tipo: json}
    registros: ListaParlamentarLegislatura.Parlamentares.Parlamentar
  - id: ceaps
    descricao: Despesas da Cota para o Exercício da Atividade Parlamentar dos Senadores (CEAPS)
    fonte_oficial: https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html?configUrl=/adm-dadosabertos/swagger-config.json
    condicoes_uso: >-
      Dados abertos do Senado Federal; condições de uso em
      https://www12.senado.leg.br/dados-abertos.
    adaptador: api_json
    url: https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}
    publicacao: por_competencia
    competencia: {tipo: ano, inicio: 2008}
    cadencia: {corrente: diaria, anteriores: semanal}
    formato: {tipo: json}
```

`fontes/cgu.yaml`:

```yaml
orgao: cgu
nome: Controladoria-Geral da União (Portal da Transparência)
portal: https://portaldatransparencia.gov.br/
recursos:
  - id: ceis
    descricao: Cadastro de Empresas Inidôneas e Suspensas (CEIS)
    fonte_oficial: https://portaldatransparencia.gov.br/download-de-dados/ceis
    condicoes_uso: >-
      Dados abertos do Poder Executivo federal (Decreto nº 8.777/2016): livre utilização,
      limitada a creditar a autoria ou a fonte (Portal da Transparência/CGU).
    adaptador: arquivo
    url: https://portaldatransparencia.gov.br/download-de-dados/ceis/{data}
    publicacao: snapshot
    competencia:
      tipo: data_arquivo
      pagina: https://portaldatransparencia.gov.br/download-de-dados/ceis
    cadencia: {corrente: diaria}
    formato: {tipo: csv, compressao: zip, encoding: cp1252, delimitador: ";"}
  - id: cnep
    descricao: Cadastro Nacional de Empresas Punidas (CNEP)
    fonte_oficial: https://portaldatransparencia.gov.br/download-de-dados/cnep
    condicoes_uso: >-
      Dados abertos do Poder Executivo federal (Decreto nº 8.777/2016): livre utilização,
      limitada a creditar a autoria ou a fonte (Portal da Transparência/CGU).
    adaptador: arquivo
    url: https://portaldatransparencia.gov.br/download-de-dados/cnep/{data}
    publicacao: snapshot
    competencia:
      tipo: data_arquivo
      pagina: https://portaldatransparencia.gov.br/download-de-dados/cnep
    cadencia: {corrente: diaria}
    formato: {tipo: csv, compressao: zip, encoding: cp1252, delimitador: ";"}
```

`fontes/ibge.yaml`:

```yaml
orgao: ibge
nome: Instituto Brasileiro de Geografia e Estatística
portal: https://servicodados.ibge.gov.br/api/docs/
recursos:
  - id: municipios
    descricao: Municípios com a hierarquia territorial (API de Localidades)
    fonte_oficial: https://servicodados.ibge.gov.br/api/docs/localidades
    condicoes_uso: >-
      Dados abertos do Poder Executivo federal (Decreto nº 8.777/2016): livre utilização,
      limitada a creditar a autoria ou a fonte (IBGE).
    adaptador: api_json
    url: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
    publicacao: snapshot
    competencia: {tipo: data_coleta}
    cadencia: {corrente: mensal}
    formato: {tipo: json}
```

- [ ] **Passo 6: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_manifesto.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `6 passed` e o lint limpo.

- [ ] **Passo 7: commit**

```bash
git add coletor/manifesto.py fontes/ tests/amostras.py tests/test_manifesto.py
git commit -m "feat(coletor): manifesto de fontes da onda A" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 3: competências, nomes de coluna e hashes

**Arquivos:**
- Criar: `coletor/competencias.py`, `coletor/nomes.py`, `coletor/hashes.py`, `tests/test_utilitarios.py`

**Interfaces:**
- Consome: `tests.amostras.AGORA`.
- Produz:
  - `Competencia(rotulo: str, data: date)` com os construtores `.de_ano(int)`, `.de_dia(date)` e `.de_rotulo(str)`;
  - `FUSO_BRASILIA`;
  - `data_brasilia(instante) -> date`, `legislatura_atual(dia) -> int`, `legislaturas(inicio, dia) -> list[int]` e `anos(inicio, dia) -> list[int]`;
  - `normalizar_nome_coluna(nome) -> str` e `normalizar_cabecalho(nomes) -> tuple[list[str], list[list[str]]]`;
  - `sha256_arquivo(caminho) -> str`, `json_canonico(registro) -> str` e `sha256_registros(registros) -> str`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_utilitarios.py`:

```python
from datetime import date

import pytest

from coletor.competencias import Competencia, data_brasilia, legislatura_atual, legislaturas
from coletor.hashes import sha256_registros
from coletor.nomes import normalizar_cabecalho, normalizar_nome_coluna
from tests.amostras import AGORA


@pytest.mark.parametrize(
    ("dia", "esperada"),
    [
        (date(2026, 10, 3), 57),
        (date(2027, 1, 31), 57),
        (date(2027, 2, 1), 58),
        (date(2007, 2, 1), 53),
        (date(2007, 1, 31), 52),
    ],
)
def test_legislatura_atual_muda_em_1o_de_fevereiro(dia, esperada):
    assert legislatura_atual(dia) == esperada


def test_legislaturas_da_53a_ate_a_atual():
    assert legislaturas(53, date(2026, 10, 3)) == [53, 54, 55, 56, 57]


def test_competencia_a_partir_do_rotulo():
    assert Competencia.de_rotulo("2025") == Competencia("2025", date(2025, 1, 1))
    assert Competencia.de_rotulo("2026-10-02") == Competencia("2026-10-02", date(2026, 10, 2))


def test_data_em_brasilia():
    assert data_brasilia(AGORA) == date(2026, 10, 3)


@pytest.mark.parametrize(
    ("original", "normalizado"),
    [
        ("ABRAGÊNCIA DA SANÇÃO", "abragencia_da_sancao"),
        ("RAZÃO SOCIAL - CADASTRO RECEITA", "razao_social_cadastro_receita"),
        ("txNomeParlamentar", "txnomeparlamentar"),
        ("Nº", "no"),
        ("1º ano", "c_1o_ano"),
        ("", "coluna"),
    ],
)
def test_normalizar_nome_coluna(original, normalizado):
    assert normalizar_nome_coluna(original) == normalizado


def test_normalizar_cabecalho_desfaz_colisoes():
    nomes, pares = normalizar_cabecalho(["Valor", "VALOR", "valor_2"])
    assert nomes == ["valor", "valor_2", "valor_2_2"]
    assert pares[1] == ["VALOR", "valor_2"]


def test_hash_de_registros_ignora_ordem_de_registros_e_de_chaves():
    assert sha256_registros([{"a": 1, "b": 2}, {"c": 3}]) == sha256_registros(
        [{"c": 3}, {"b": 2, "a": 1}]
    )
    assert sha256_registros([{"a": 1}]) != sha256_registros([{"a": 2}])
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_utilitarios.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.competencias'`.

- [ ] **Passo 3: implementar**

`coletor/competencias.py`:

```python
"""Competências, legislaturas e datas no fuso de Brasília."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class Competencia:
    rotulo: str
    data: date

    @classmethod
    def de_ano(cls, ano: int) -> Competencia:
        return cls(str(ano), date(ano, 1, 1))

    @classmethod
    def de_dia(cls, dia: date) -> Competencia:
        return cls(dia.isoformat(), dia)

    @classmethod
    def de_rotulo(cls, rotulo: str) -> Competencia:
        if len(rotulo) == 4 and rotulo.isdigit():
            return cls.de_ano(int(rotulo))
        return cls.de_dia(date.fromisoformat(rotulo))


def data_brasilia(instante: datetime) -> date:
    return instante.astimezone(FUSO_BRASILIA).date()


def legislatura_atual(dia: date) -> int:
    """A 57ª legislatura vai de 01/02/2023 a 31/01/2027 e a numeração muda a cada 4 anos."""
    ano_inicio = dia.year if (dia.month, dia.day) >= (2, 1) else dia.year - 1
    return 57 + (ano_inicio - 2023) // 4


def legislaturas(inicio: int, dia: date) -> list[int]:
    return list(range(inicio, legislatura_atual(dia) + 1))


def anos(inicio: int, dia: date) -> list[int]:
    return list(range(inicio, dia.year + 1))
```

`coletor/nomes.py`:

```python
"""Normalização dos nomes de coluna gravados no raw."""

from __future__ import annotations

import re
import unicodedata

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar_nome_coluna(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    normalizado = _NAO_ALFANUMERICO.sub("_", sem_acento.lower()).strip("_")
    if not normalizado:
        return "coluna"
    if normalizado[0].isdigit():
        return f"c_{normalizado}"
    return normalizado


def normalizar_cabecalho(nomes: list[str]) -> tuple[list[str], list[list[str]]]:
    """Normaliza os nomes e desfaz colisões com sufixos `_2`, `_3`...

    Retorna os nomes normalizados e os pares `[original, normalizado]`.
    """
    vistos: set[str] = set()
    normalizados: list[str] = []
    for nome in nomes:
        base = normalizar_nome_coluna(nome)
        final, numero = base, 1
        while final in vistos:
            numero += 1
            final = f"{base}_{numero}"
        vistos.add(final)
        normalizados.append(final)
    return normalizados, [[o, n] for o, n in zip(nomes, normalizados, strict=True)]
```

`coletor/hashes.py`:

```python
"""Hashes SHA-256 de arquivos e de registros JSON."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_BLOCO = 1 << 20


def sha256_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(_BLOCO), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def json_canonico(registro: Any) -> str:
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_registros(registros: Iterable[Any]) -> str:
    """Hash independente da ordem dos registros e da ordem das chaves."""
    resumo = hashlib.sha256()
    for linha in sorted(json_canonico(registro) for registro in registros):
        resumo.update(linha.encode("utf-8"))
        resumo.update(b"\n")
    return resumo.hexdigest()
```

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_utilitarios.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `16 passed` e o lint limpo.

- [ ] **Passo 5: commit**

```bash
git add coletor/competencias.py coletor/nomes.py coletor/hashes.py tests/test_utilitarios.py
git commit -m "feat(coletor): competências, normalização de colunas e hashes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 4: cliente HTTP com retentativas

**Arquivos:**
- Criar: `coletor/http.py`, `tests/conftest.py`, `tests/test_http.py`

**Interfaces:**
- Consome: nada.
- Produz:
  - `ClienteHttp(tentativas=5, espera_base=2.0, espera_maxima=60.0, dormir=time.sleep, transporte=None)`, com os métodos `.baixar(url, destino) -> Download`, `.obter_json(url, params=None) -> RespostaJson`, `.obter_texto(url) -> str` e `.fechar()`;
  - `Download(url_final, status, last_modified, etag, bytes, sha256)`;
  - `RespostaJson(url_final, status, corpo: bytes, dados)`;
  - `ErroHttp(url, status: int | None, mensagem)` com `.status`;
  - a fixture `http`, um `ClienteHttp` que não dorme entre tentativas.

- [ ] **Passo 1: criar a fixture**

`tests/conftest.py`:

```python
from __future__ import annotations

import pytest

from coletor.http import ClienteHttp


@pytest.fixture
def http() -> ClienteHttp:
    cliente = ClienteHttp(dormir=lambda segundos: None)
    yield cliente
    cliente.fechar()
```

- [ ] **Passo 2: escrever o teste que falha**

`tests/test_http.py`:

```python
import hashlib

import httpx
import pytest

from coletor.http import ClienteHttp, ErroHttp


def test_baixar_grava_o_arquivo_e_calcula_o_hash(respx_mock, http, tmp_path):
    respx_mock.get("https://fonte/arquivo.zip").mock(
        return_value=httpx.Response(200, content=b"abc", headers={"Last-Modified": "ontem"})
    )
    download = http.baixar("https://fonte/arquivo.zip", tmp_path / "x")
    assert (tmp_path / "x").read_bytes() == b"abc"
    assert download.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert (download.bytes, download.last_modified) == (3, "ontem")


def test_baixar_segue_redirecionamento_e_guarda_a_url_final(respx_mock, http, tmp_path):
    respx_mock.get("https://fonte/ceis/20261002").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn/20261002_CEIS.zip"})
    )
    respx_mock.get("https://cdn/20261002_CEIS.zip").mock(
        return_value=httpx.Response(200, content=b"z")
    )
    download = http.baixar("https://fonte/ceis/20261002", tmp_path / "x")
    assert download.url_final == "https://cdn/20261002_CEIS.zip"


def test_repete_em_503_e_respeita_retry_after(respx_mock, tmp_path):
    esperas: list[float] = []
    cliente = ClienteHttp(dormir=esperas.append)
    rota = respx_mock.get("https://fonte/a").mock(
        side_effect=[
            httpx.Response(503, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    resposta = cliente.obter_json("https://fonte/a")
    assert resposta.dados == {"ok": True}
    assert rota.call_count == 2
    assert esperas == [7.0]


def test_404_nao_e_repetido(respx_mock, http):
    rota = respx_mock.get("https://fonte/a").mock(return_value=httpx.Response(404))
    with pytest.raises(ErroHttp) as erro:
        http.obter_json("https://fonte/a")
    assert erro.value.status == 404
    assert rota.call_count == 1


def test_falha_de_transporte_esgota_as_tentativas(respx_mock):
    cliente = ClienteHttp(tentativas=3, dormir=lambda s: None)
    rota = respx_mock.get("https://fonte/a").mock(side_effect=httpx.ConnectError("recusada"))
    with pytest.raises(ErroHttp) as erro:
        cliente.obter_texto("https://fonte/a")
    assert erro.value.status is None
    assert rota.call_count == 3


def test_obter_json_envia_accept_json(respx_mock, http):
    rota = respx_mock.get("https://fonte/a").mock(return_value=httpx.Response(200, json=[]))
    http.obter_json("https://fonte/a", {"itens": 100})
    pedido = rota.calls.last.request
    assert pedido.headers["accept"] == "application/json"
    assert pedido.url.params["itens"] == "100"
```

- [ ] **Passo 3: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_http.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.http'`.

- [ ] **Passo 4: implementar**

`coletor/http.py`:

```python
"""Cliente HTTP com retentativas e download em streaming."""

from __future__ import annotations

import hashlib
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypeVar

import httpx

STATUS_RETENTAVEIS = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "eleitorado-coletor/0.1"

T = TypeVar("T")


class ErroHttp(Exception):
    def __init__(self, url: str, status: int | None, mensagem: str) -> None:
        super().__init__(f"{mensagem} (status={status}, url={url})")
        self.url = url
        self.status = status


class _RespostaComErro(Exception):
    def __init__(self, resposta: httpx.Response) -> None:
        super().__init__(resposta.status_code)
        self.resposta = resposta


@dataclass(frozen=True)
class Download:
    url_final: str
    status: int
    last_modified: str | None
    etag: str | None
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RespostaJson:
    url_final: str
    status: int
    corpo: bytes
    dados: Any


class ClienteHttp:
    def __init__(
        self,
        tentativas: int = 5,
        espera_base: float = 2.0,
        espera_maxima: float = 60.0,
        dormir: Callable[[float], None] = time.sleep,
        transporte: httpx.BaseTransport | None = None,
    ) -> None:
        self._tentativas = tentativas
        self._espera_base = espera_base
        self._espera_maxima = espera_maxima
        self._dormir = dormir
        self._cliente = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transporte,
        )

    def fechar(self) -> None:
        self._cliente.close()

    def baixar(self, url: str, destino: Path) -> Download:
        def tentativa() -> Download:
            resumo = hashlib.sha256()
            total = 0
            with self._cliente.stream("GET", url) as resposta:
                self._verificar(resposta)
                with destino.open("wb") as arquivo:
                    for bloco in resposta.iter_bytes():
                        arquivo.write(bloco)
                        resumo.update(bloco)
                        total += len(bloco)
                return Download(
                    url_final=str(resposta.url),
                    status=resposta.status_code,
                    last_modified=resposta.headers.get("last-modified"),
                    etag=resposta.headers.get("etag"),
                    bytes=total,
                    sha256=resumo.hexdigest(),
                )

        return self._com_retentativas(url, tentativa)

    def obter_json(self, url: str, params: dict[str, Any] | None = None) -> RespostaJson:
        def tentativa() -> RespostaJson:
            resposta = self._cliente.get(url, params=params, headers={"Accept": "application/json"})
            self._verificar(resposta)
            return RespostaJson(
                str(resposta.url), resposta.status_code, resposta.content, resposta.json()
            )

        return self._com_retentativas(url, tentativa)

    def obter_texto(self, url: str) -> str:
        def tentativa() -> str:
            resposta = self._cliente.get(url)
            self._verificar(resposta)
            return resposta.text

        return self._com_retentativas(url, tentativa)

    @staticmethod
    def _verificar(resposta: httpx.Response) -> None:
        if resposta.status_code >= 400:
            raise _RespostaComErro(resposta)

    def _com_retentativas(self, url: str, tentativa: Callable[[], T]) -> T:
        ultimo: ErroHttp | None = None
        for numero in range(1, self._tentativas + 1):
            try:
                return tentativa()
            except _RespostaComErro as erro:
                status = erro.resposta.status_code
                ultimo = ErroHttp(str(erro.resposta.url), status, "resposta HTTP de erro")
                if status not in STATUS_RETENTAVEIS:
                    raise ultimo from None
                espera = self._espera(numero, erro.resposta.headers.get("retry-after"))
            except httpx.TransportError as erro:
                ultimo = ErroHttp(url, None, f"falha de transporte: {erro!r}")
                espera = self._espera(numero, None)
            if numero < self._tentativas:
                self._dormir(espera)
        assert ultimo is not None
        raise ultimo

    def _espera(self, numero: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self._espera_maxima)
            except ValueError:
                try:
                    alvo = parsedate_to_datetime(retry_after)
                    segundos = (alvo - datetime.now(alvo.tzinfo)).total_seconds()
                    return min(max(segundos, 0.0), self._espera_maxima)
                except (TypeError, ValueError):
                    pass
        base = min(self._espera_base * 2 ** (numero - 1), self._espera_maxima)
        return base * random.uniform(0.5, 1.0)
```

- [ ] **Passo 5: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_http.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `6 passed` e o lint limpo.

- [ ] **Passo 6: commit**

```bash
git add coletor/http.py tests/conftest.py tests/test_http.py
git commit -m "feat(coletor): cliente HTTP com retentativas e download em streaming" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 5: conversão para Parquet

**Arquivos:**
- Criar: `coletor/conversao.py`, `tests/test_conversao.py`

**Interfaces:**
- Consome: `Formato` (Tarefa 2), `normalizar_cabecalho` e `json_canonico` (Tarefa 3).
- Produz:
  - `Controle(coleta_id, competencia, competencia_data, arquivo_original, carregado_em)`;
  - `ResultadoConversao(linhas: int, colunas: list[list[str]])`;
  - `CAMPOS_CONTROLE`;
  - `ler_cabecalho(caminho, formato) -> list[str]`;
  - `csv_para_parquet(origem, destino, formato, controle, tamanho_bloco=16 << 20) -> ResultadoConversao`;
  - `registros_para_parquet(registros, destino, controle) -> ResultadoConversao`.

- [ ] **Passo 1: escrever o teste que falha**

O teste de BOM usa o caractere `\ufeff`, que é o BOM do UTF-8.

`tests/test_conversao.py`:

```python
from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.conversao import Controle, csv_para_parquet, registros_para_parquet
from coletor.manifesto import Formato
from tests.amostras import CEAP_CSV, CEAPS_JSON, CNEP_CSV

CONTROLE = Controle(
    "coleta-1",
    "2026-10-02",
    date(2026, 10, 2),
    "gs://b/original.zip",
    datetime(2026, 10, 3, tzinfo=UTC),
)


def test_csv_windows_1252_com_quebra_de_linha_em_campo(tmp_path):
    origem = tmp_path / "cnep.csv"
    origem.write_bytes(CNEP_CSV.encode("cp1252"))
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv", encoding="cp1252"), CONTROLE
    )
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 2
    assert tabela.column("nome_do_sancionado").to_pylist() == [
        "Empresa Exemplo Comércio Ltda",
        "Pessoa Exemplo",
    ]
    assert tabela.column("observacoes").to_pylist() == ["linha 1\nlinha 2", ""]
    assert ["ABRAGÊNCIA DA SANÇÃO", "abragencia_da_sancao"] in resultado.colunas
    assert tabela.column("_linha").to_pylist() == [1, 2]
    assert tabela.column("_competencia_data").to_pylist() == [date(2026, 10, 2)] * 2
    assert tabela.schema.field("_carregado_em").type == pa.timestamp("us", tz="UTC")


def test_csv_utf8_com_bom_nao_contamina_o_primeiro_nome(tmp_path):
    origem = tmp_path / "ceap.csv"
    origem.write_bytes(("\ufeff" + CEAP_CSV).encode("utf-8"))
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv", encoding="utf-8-sig"), CONTROLE
    )
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.colunas[0] == ["txNomeParlamentar", "txnomeparlamentar"]
    assert tabela.column("txtdescricao").to_pylist()[0] == "LOCOMOÇÃO, ALIMENTAÇÃO E  HOSPEDAGEM"
    assert tabela.column("cpf").to_pylist() == ["00000000191", ""]


def test_csv_com_linha_antes_do_cabecalho(tmp_path):
    origem = tmp_path / "ceaps.csv"
    origem.write_text(
        '"ULTIMA ATUALIZACAO";"06/08/2021"\n"ANO";"MES"\n"2008";"9"\n', encoding="cp1252"
    )
    formato = Formato(tipo="csv", encoding="cp1252", linhas_a_pular=1)
    resultado = csv_para_parquet(origem, tmp_path / "s.parquet", formato, CONTROLE)
    assert resultado.linhas == 1
    assert [normalizado for _, normalizado in resultado.colunas] == ["ano", "mes"]


def test_csv_so_com_cabecalho_gera_parquet_vazio(tmp_path):
    origem = tmp_path / "vazio.csv"
    origem.write_text('"A";"B"\n', encoding="utf-8")
    resultado = csv_para_parquet(origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE)
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 0
    assert tabela.num_rows == 0
    assert tabela.column_names[:2] == ["a", "b"]


def test_csv_com_linha_de_tamanho_errado_falha(tmp_path):
    origem = tmp_path / "torto.csv"
    origem.write_text('"A";"B"\n"1";"2";"3"\n', encoding="utf-8")
    with pytest.raises(pa.ArrowInvalid):
        csv_para_parquet(origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE)


def test_registros_viram_payload_json_e_colunas_sao_as_chaves(tmp_path):
    resultado = registros_para_parquet(CEAPS_JSON, tmp_path / "s.parquet", CONTROLE)
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 2
    assert tabela.column_names[0] == "payload"
    assert '"codSenador":3' in tabela.column("payload").to_pylist()[0]
    assert ["codSenador", "codSenador"] in resultado.colunas


def test_registros_vazios_geram_parquet_vazio(tmp_path):
    resultado = registros_para_parquet([], tmp_path / "s.parquet", CONTROLE)
    assert resultado.linhas == 0
    assert pq.read_table(tmp_path / "s.parquet").num_rows == 0


def test_csv_maior_que_um_bloco_numera_linhas_sem_saltos(tmp_path):
    origem = tmp_path / "grande.csv"
    linhas = ['"A";"B"'] + [f'"{i}";"texto {i}"' for i in range(5000)]
    origem.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE, tamanho_bloco=4096
    )
    arquivo = pq.ParquetFile(tmp_path / "s.parquet")
    tabela = arquivo.read()
    assert arquivo.metadata.num_row_groups > 1
    assert resultado.linhas == 5000
    assert tabela.column("_linha").to_pylist() == list(range(1, 5001))
    assert tabela.column("a").to_pylist()[-1] == "4999"
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_conversao.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.conversao'`.

- [ ] **Passo 3: implementar**

`coletor/conversao.py`:

```python
"""Conversão de CSV e de registros JSON para Parquet, com colunas de controle."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from coletor.hashes import json_canonico
from coletor.manifesto import Formato
from coletor.nomes import normalizar_cabecalho

CAMPOS_CONTROLE = [
    pa.field("_coleta_id", pa.string()),
    pa.field("_competencia", pa.string()),
    pa.field("_competencia_data", pa.date32()),
    pa.field("_linha", pa.int64()),
    pa.field("_arquivo_original", pa.string()),
    pa.field("_carregado_em", pa.timestamp("us", tz="UTC")),
]


@dataclass(frozen=True)
class Controle:
    coleta_id: str
    competencia: str
    competencia_data: date
    arquivo_original: str
    carregado_em: datetime


@dataclass(frozen=True)
class ResultadoConversao:
    linhas: int
    colunas: list[list[str]]


def _arrays_controle(controle: Controle, primeira_linha: int, quantidade: int) -> list[pa.Array]:
    return [
        pa.array([controle.coleta_id] * quantidade, pa.string()),
        pa.array([controle.competencia] * quantidade, pa.string()),
        pa.array([controle.competencia_data] * quantidade, pa.date32()),
        pa.array(range(primeira_linha, primeira_linha + quantidade), pa.int64()),
        pa.array([controle.arquivo_original] * quantidade, pa.string()),
        pa.array([controle.carregado_em] * quantidade, pa.timestamp("us", tz="UTC")),
    ]


def ler_cabecalho(caminho: Path, formato: Formato) -> list[str]:
    with caminho.open("r", encoding=formato.encoding, newline="") as arquivo:
        for _ in range(formato.linhas_a_pular):
            arquivo.readline()
        leitor = csv.reader(arquivo, delimiter=formato.delimitador)
        try:
            return next(leitor)
        except StopIteration:
            raise ValueError(f"arquivo sem cabeçalho: {caminho.name}") from None


def csv_para_parquet(
    origem: Path,
    destino: Path,
    formato: Formato,
    controle: Controle,
    tamanho_bloco: int = 16 << 20,
) -> ResultadoConversao:
    nomes, pares = normalizar_cabecalho(ler_cabecalho(origem, formato))
    esquema = pa.schema([pa.field(nome, pa.string()) for nome in nomes] + CAMPOS_CONTROLE)
    leitor = pacsv.open_csv(
        origem,
        read_options=pacsv.ReadOptions(
            encoding=formato.encoding,
            skip_rows=formato.linhas_a_pular + 1,
            column_names=nomes,
            block_size=tamanho_bloco,
        ),
        parse_options=pacsv.ParseOptions(delimiter=formato.delimitador, newlines_in_values=True),
        convert_options=pacsv.ConvertOptions(
            column_types={nome: pa.string() for nome in nomes}, strings_can_be_null=False
        ),
    )
    linhas = 0
    with pq.ParquetWriter(destino, esquema, compression="zstd") as escritor:
        for lote in leitor:
            quantidade = lote.num_rows
            colunas = list(lote.columns) + _arrays_controle(controle, linhas + 1, quantidade)
            escritor.write_batch(pa.RecordBatch.from_arrays(colunas, schema=esquema))
            linhas += quantidade
    return ResultadoConversao(linhas, pares)


def registros_para_parquet(
    registros: list[Any], destino: Path, controle: Controle
) -> ResultadoConversao:
    esquema = pa.schema([pa.field("payload", pa.string())] + CAMPOS_CONTROLE)
    quantidade = len(registros)
    payload = pa.array([json_canonico(registro) for registro in registros], pa.string())
    tabela = pa.Table.from_arrays(
        [payload, *_arrays_controle(controle, 1, quantidade)], schema=esquema
    )
    pq.write_table(tabela, destino, compression="zstd")
    chaves = sorted({chave for r in registros if isinstance(r, dict) for chave in r})
    return ResultadoConversao(quantidade, [[chave, chave] for chave in chaves])
```

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_conversao.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `8 passed` e o lint limpo.

- [ ] **Passo 5: commit**

```bash
git add coletor/conversao.py tests/test_conversao.py
git commit -m "feat(coletor): conversão de CSV e JSON para Parquet com colunas de controle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 6: adaptador `arquivo` e descoberta da data da CGU

**Arquivos:**
- Criar: `coletor/adaptadores/__init__.py` (por enquanto só com a docstring), `coletor/adaptadores/base.py`, `coletor/cgu.py`, `coletor/adaptadores/arquivo.py`, `tests/test_adaptador_arquivo.py`

**Interfaces:**
- Consome: `ClienteHttp`/`ErroHttp` (Tarefa 4), `Competencia`/`legislatura_atual` (Tarefa 3), `sha256_arquivo` (Tarefa 3) e `Recurso` (Tarefa 2).
- Produz:
  - `Extracao(competencia, arquivo_original: Path, extensao, url, http_status, bytes_arquivo, sha256_arquivo, last_modified=None, etag=None, parametros={})`;
  - `Preparado(sha256_conteudo, csv: Path | None = None, registros: list | None = None)`;
  - `ErroColeta`;
  - `preencher(modelo, competencia, dia) -> str`, para os marcadores `{ano}`, `{data}` e `{legislatura}`;
  - `extensao_de(url) -> str`;
  - `descobrir_data(html) -> date | None` e `datas_candidatas(descoberta, hoje) -> list[date]`;
  - o módulo `arquivo`, com `extrair(recurso, competencia, pasta, http, hoje) -> Extracao` e `preparar(recurso, competencia, original, pasta) -> Preparado`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_adaptador_arquivo.py`:

```python
from datetime import date

import httpx
import pytest

from coletor.adaptadores import arquivo
from coletor.adaptadores.base import ErroColeta, extensao_de, preencher
from coletor.cgu import datas_candidatas, descobrir_data
from coletor.competencias import Competencia
from coletor.hashes import sha256_arquivo
from tests.amostras import CEAP_CSV, CNEP_CSV, PAGINA_CGU, recurso, zip_com

HOJE = date(2026, 10, 3)
PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"


def test_descobre_a_data_na_pagina_da_cgu():
    assert descobrir_data(PAGINA_CGU) == date(2026, 10, 2)
    assert descobrir_data("<html>sem data</html>") is None


def test_datas_candidatas_comecam_pela_descoberta():
    assert datas_candidatas(date(2026, 10, 2), HOJE) == [
        date(2026, 10, 2),
        date(2026, 10, 1),
        date(2026, 9, 30),
    ]
    assert datas_candidatas(None, HOJE)[0] == date(2026, 10, 2)


def _mock_cgu(respx_mock, data: str, conteudo: bytes):
    respx_mock.get(f"{PAGINA}/{data}").mock(
        return_value=httpx.Response(
            302,
            headers={
                "Location": f"https://dadosabertos-download.cgu.gov.br/saida/cnep/{data}_CNEP.zip"
            },
        )
    )
    respx_mock.get(f"https://dadosabertos-download.cgu.gov.br/saida/cnep/{data}_CNEP.zip").mock(
        return_value=httpx.Response(200, content=conteudo)
    )


def test_arquivo_cgu_usa_a_data_anunciada(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    _mock_cgu(respx_mock, "20261002", zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")}))
    extracao = arquivo.extrair(recurso(), None, tmp_path, http, HOJE)
    assert extracao.competencia == Competencia.de_dia(date(2026, 10, 2))
    assert extracao.extensao == "zip"
    assert extracao.url.endswith("20261002_CNEP.zip")


def test_arquivo_cgu_sem_data_na_pagina_tenta_os_dias_anteriores(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx_mock.get(f"{PAGINA}/20261002").mock(return_value=httpx.Response(403))
    _mock_cgu(respx_mock, "20261001", zip_com({"20261001_CNEP.csv": b"x"}))
    extracao = arquivo.extrair(recurso(), None, tmp_path, http, HOJE)
    assert extracao.competencia.rotulo == "2026-10-01"


def test_arquivo_cgu_indisponivel_em_todas_as_datas(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(500))
    respx_mock.get(url__startswith=f"{PAGINA}/").mock(return_value=httpx.Response(403))
    with pytest.raises(ErroColeta, match="2026-10-02=403"):
        arquivo.extrair(recurso(), None, tmp_path, http, HOJE)


def test_hash_de_conteudo_ignora_metadados_do_zip(tmp_path):
    rec = recurso()
    competencia = Competencia.de_dia(date(2026, 10, 2))
    conteudo = CNEP_CSV.encode("cp1252")
    hashes = []
    for indice, data_hora in enumerate([(2026, 10, 2, 18, 0, 0), (2026, 10, 3, 6, 0, 0)]):
        pasta = tmp_path / str(indice)
        pasta.mkdir()
        original = pasta / "original.zip"
        original.write_bytes(zip_com({"20261002_CNEP.csv": conteudo}, data_hora))
        preparado = arquivo.preparar(rec, competencia, original, pasta)
        hashes.append((sha256_arquivo(original), preparado.sha256_conteudo))
        assert preparado.csv is not None and preparado.csv.read_bytes() == conteudo
    assert hashes[0][0] != hashes[1][0]
    assert hashes[0][1] == hashes[1][1]


def test_zip_com_membro_nomeado_por_competencia(tmp_path):
    rec = recurso(
        id="ceap",
        url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
        publicacao="por_competencia",
        competencia={"tipo": "ano", "inicio": 2008},
        cadencia={"corrente": "diaria", "anteriores": "semanal"},
        formato={"tipo": "csv", "compressao": "zip", "arquivo": "Ano-{ano}.csv"},
    )
    original = tmp_path / "original.zip"
    original.write_bytes(zip_com({"leiame.txt": b"x", "Ano-2008.csv": CEAP_CSV.encode()}))
    preparado = arquivo.preparar(rec, Competencia.de_ano(2008), original, tmp_path)
    assert preparado.csv is not None and preparado.csv.read_bytes() == CEAP_CSV.encode()
    with pytest.raises(ErroColeta, match="Ano-2009.csv"):
        arquivo.preparar(rec, Competencia.de_ano(2009), original, tmp_path)


def test_zip_com_varios_membros_sem_formato_arquivo_falha(tmp_path):
    original = tmp_path / "original.zip"
    original.write_bytes(zip_com({"a.csv": b"1", "b.csv": b"2"}))
    with pytest.raises(ErroColeta, match="2 arquivos"):
        arquivo.preparar(recurso(), Competencia.de_dia(HOJE), original, tmp_path)


def test_preencher_marcadores():
    competencia = Competencia.de_dia(date(2026, 10, 2))
    assert preencher("x/{data}/{ano}/{legislatura}", competencia, date(2026, 10, 3)) == (
        "x/20261002/2026/57"
    )
    with pytest.raises(ErroColeta, match="marcador"):
        preencher("x/{desconhecido}", competencia, date(2026, 10, 3))


def test_extensao_a_partir_da_url_final():
    assert extensao_de("https://x/cotas/Ano-2025.csv.zip") == "csv.zip"
    assert extensao_de("https://x/saida/ceis/20261002_CEIS.zip?a=1") == "zip"
    assert extensao_de("https://x/download-de-dados/ceis/20261002") == "bin"
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_adaptador_arquivo.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.adaptadores'`.

- [ ] **Passo 3: implementar**

`coletor/adaptadores/__init__.py`. Nesta tarefa ele tem só a docstring; o registro de adaptadores entra na Tarefa 7:

```python
"""Adaptadores de coleta, escolhidos pelo campo `adaptador` do manifesto."""
```

`coletor/adaptadores/base.py`:

```python
"""Tipos comuns aos adaptadores de coleta."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from coletor.competencias import Competencia, legislatura_atual


class ErroColeta(Exception):
    """Falha de coleta com mensagem destinada a `meta.coletas`."""


@dataclass(frozen=True)
class Extracao:
    """O que foi baixado da fonte, antes de qualquer transformação."""

    competencia: Competencia
    arquivo_original: Path
    extensao: str
    url: str
    http_status: int
    bytes_arquivo: int
    sha256_arquivo: str
    last_modified: str | None = None
    etag: str | None = None
    parametros: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Preparado:
    """Conteúdo pronto para conversão: um CSV ou uma lista de registros."""

    sha256_conteudo: str
    csv: Path | None = None
    registros: list[Any] | None = None


def preencher(modelo: str, competencia: Competencia | None, dia: date) -> str:
    """Substitui `{ano}`, `{data}` e `{legislatura}` em URLs e nomes de arquivo."""
    valores: dict[str, Any] = {"legislatura": legislatura_atual(dia)}
    if competencia is not None:
        valores["ano"] = competencia.data.year
        valores["data"] = competencia.data.strftime("%Y%m%d")
    try:
        return modelo.format_map(valores)
    except KeyError as erro:
        raise ErroColeta(f"marcador sem valor em {modelo!r}: {erro}") from None


def extensao_de(url: str) -> str:
    nome = PurePosixPath(urlparse(url).path).name
    return nome.split(".", 1)[1].lower() if "." in nome else "bin"
```

`coletor/cgu.py`:

```python
"""Descoberta da data do arquivo mais recente nas páginas de download da CGU."""

from __future__ import annotations

import re
from datetime import date, timedelta

_PADRAO = re.compile(
    r'arquivos\.push\(\s*\{\s*"ano"\s*:\s*"(\d{4})"\s*,\s*"mes"\s*:\s*"(\d{2})"'
    r'\s*,\s*"dia"\s*:\s*"(\d{2})"'
)


def descobrir_data(html: str) -> date | None:
    datas = [date(int(ano), int(mes), int(dia)) for ano, mes, dia in _PADRAO.findall(html)]
    return max(datas) if datas else None


def datas_candidatas(descoberta: date | None, hoje: date) -> list[date]:
    """Data anunciada na página primeiro; depois D-1, D-2 e D-3."""
    candidatas = [descoberta] if descoberta else []
    for dias in (1, 2, 3):
        dia = hoje - timedelta(days=dias)
        if dia not in candidatas:
            candidatas.append(dia)
    return candidatas
```

`coletor/adaptadores/arquivo.py`:

```python
"""Adaptador `arquivo`: download HTTP de CSV, com ou sem ZIP."""

from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

from coletor.adaptadores.base import ErroColeta, Extracao, Preparado, extensao_de, preencher
from coletor.cgu import datas_candidatas, descobrir_data
from coletor.competencias import Competencia
from coletor.hashes import sha256_arquivo
from coletor.http import ClienteHttp, ErroHttp
from coletor.manifesto import Recurso


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    if recurso.competencia.tipo == "data_arquivo":
        return _extrair_data_arquivo(recurso, pasta, http, hoje)
    if competencia is None:
        raise ErroColeta(f"{recurso.id}: competência obrigatória")
    return _baixar(recurso, competencia, pasta, http, hoje)


def _extrair_data_arquivo(recurso: Recurso, pasta: Path, http: ClienteHttp, hoje: date) -> Extracao:
    assert recurso.competencia.pagina is not None
    try:
        descoberta = descobrir_data(http.obter_texto(recurso.competencia.pagina))
    except ErroHttp:
        descoberta = None
    tentativas: list[str] = []
    for dia in datas_candidatas(descoberta, hoje):
        try:
            return _baixar(recurso, Competencia.de_dia(dia), pasta, http, hoje)
        except ErroHttp as erro:
            if erro.status not in (403, 404):
                raise
            tentativas.append(f"{dia.isoformat()}={erro.status}")
    raise ErroColeta(f"nenhum arquivo disponível ({', '.join(tentativas)})")


def _baixar(
    recurso: Recurso, competencia: Competencia, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    url = preencher(recurso.url, competencia, hoje)
    temporario = pasta / "download"
    download = http.baixar(url, temporario)
    extensao = extensao_de(download.url_final)
    original = pasta / f"original.{extensao}"
    temporario.replace(original)
    return Extracao(
        competencia=competencia,
        arquivo_original=original,
        extensao=extensao,
        url=download.url_final,
        http_status=download.status,
        bytes_arquivo=download.bytes,
        sha256_arquivo=download.sha256,
        last_modified=download.last_modified,
        etag=download.etag,
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    formato = recurso.formato
    if formato.compressao != "zip":
        return Preparado(sha256_conteudo=sha256_arquivo(original), csv=original)
    destino = pasta / "conteudo.csv"
    with zipfile.ZipFile(original) as compactado:
        membros = [membro for membro in compactado.infolist() if not membro.is_dir()]
        if formato.arquivo:
            nome = preencher(formato.arquivo, competencia, competencia.data)
            escolhido = next((m for m in membros if m.filename == nome), None)
            if escolhido is None:
                nomes = [m.filename for m in membros]
                raise ErroColeta(f"{nome} não está no ZIP (membros: {nomes})")
        elif len(membros) == 1:
            escolhido = membros[0]
        else:
            raise ErroColeta(f"ZIP com {len(membros)} arquivos: defina formato.arquivo")
        with compactado.open(escolhido) as origem, destino.open("wb") as saida:
            shutil.copyfileobj(origem, saida, 1 << 20)
    return Preparado(sha256_conteudo=sha256_arquivo(destino), csv=destino)
```

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_adaptador_arquivo.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `10 passed` e o lint limpo.

- [ ] **Passo 5: commit**

```bash
git add coletor/adaptadores/ coletor/cgu.py tests/test_adaptador_arquivo.py
git commit -m "feat(coletor): adaptador de arquivos e descoberta da data da CGU" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 7: adaptador `api_json` e registro de adaptadores

**Arquivos:**
- Criar: `coletor/adaptadores/api_json.py`, `tests/test_adaptador_api_json.py`
- Modificar: `coletor/adaptadores/__init__.py` (substituir o conteúdo inteiro)

**Interfaces:**
- Consome: `ClienteHttp` (Tarefa 4), `Extracao`/`Preparado`/`ErroColeta`/`preencher` (Tarefa 6), `legislaturas` (Tarefa 3), `sha256_registros` (Tarefa 3) e o módulo `arquivo` (Tarefa 6).
- Produz:
  - o módulo `api_json`, com `extrair(...)`, `preparar(...)`, `extrair_registros(dados, caminho) -> list`, `proximo_link(dados) -> str | None`, `chave_url(url)` e `LIMITE_PAGINAS`;
  - `adaptador_para(recurso: Recurso) -> ModuleType` e `ADAPTADORES`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_adaptador_api_json.py`:

```python
import gzip
import json
from datetime import date

import httpx
import pytest

from coletor.adaptadores import api_json
from coletor.adaptadores.base import ErroColeta
from coletor.competencias import Competencia
from tests.amostras import json_bytes, pagina_deputados, recurso, senadores_json

HOJE = date(2026, 10, 3)


def _recurso_deputados():
    return recurso(
        id="deputados",
        adaptador="api_json",
        url="https://dadosabertos.camara.leg.br/api/v2/deputados",
        parametros={"itens": 100},
        competencia={"tipo": "data_coleta"},
        cadencia={"corrente": "semanal"},
        formato={"tipo": "json"},
        paginacao="links_next",
        iteracao={"parametro": "idLegislatura", "valores": "legislaturas", "inicio": 56},
        registros="dados",
    )


def test_api_pagina_por_links_e_itera_legislaturas(respx_mock, http, tmp_path):
    base = "https://dadosabertos.camara.leg.br/api/v2/deputados"
    proxima = f"{base}?idLegislatura=56&pagina=2&itens=100"
    # rotas mais específicas primeiro: o padrão de params do respx casa por "contém"
    respx_mock.get(base, params={"idLegislatura": "56", "pagina": "2"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([3], None))
    )
    respx_mock.get(base, params={"idLegislatura": "56", "itens": "100"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([1, 2], proxima))
    )
    respx_mock.get(base, params={"idLegislatura": "57"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([4], None))
    )
    rec = _recurso_deputados()
    extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), tmp_path, http, HOJE)
    preparado = api_json.preparar(rec, extracao.competencia, extracao.arquivo_original, tmp_path)
    assert [r["id"] for r in preparado.registros] == [1, 2, 3, 4]
    assert extracao.parametros["iteracao"]["valores"] == [56, 57]
    with gzip.open(extracao.arquivo_original, "rt", encoding="utf-8") as paginas:
        assert len(paginas.readlines()) == 3


def test_api_com_metadado_volatil_tem_o_mesmo_hash_de_conteudo(respx_mock, http, tmp_path):
    rec = recurso(
        id="senadores",
        adaptador="api_json",
        url="https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/{legislatura}.json",
        competencia={"tipo": "data_coleta"},
        cadencia={"corrente": "semanal"},
        formato={"tipo": "json"},
        registros="ListaParlamentarLegislatura.Parlamentares.Parlamentar",
    )
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/57.json"
    hashes = []
    for indice, versao in enumerate(["03/10/2026 15:20:06", "04/10/2026 08:00:00"]):
        respx_mock.get(url).mock(
            return_value=httpx.Response(200, content=json_bytes(senadores_json(versao)))
        )
        pasta = tmp_path / str(indice)
        pasta.mkdir()
        extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), pasta, http, HOJE)
        preparado = api_json.preparar(rec, extracao.competencia, extracao.arquivo_original, pasta)
        assert len(preparado.registros) == 2
        hashes.append((extracao.sha256_arquivo, preparado.sha256_conteudo))
    assert hashes[0][0] != hashes[1][0]
    assert hashes[0][1] == hashes[1][1]


def test_registros_unicos_viram_lista_e_caminho_ausente_falha():
    assert api_json.extrair_registros({"a": {"b": {"x": 1}}}, "a.b") == [{"x": 1}]
    assert api_json.extrair_registros({"a": None}, "a") == []
    assert api_json.extrair_registros([{"id": 1}], None) == [{"id": 1}]  # IBGE e CEAPS
    with pytest.raises(ErroColeta, match="parou em 'c'"):
        api_json.extrair_registros({"a": {"b": []}}, "a.c")


def test_paginacao_em_laco_e_interrompida(respx_mock, http, tmp_path):
    def pagina_que_aponta_para_si_mesma(request: httpx.Request) -> httpx.Response:
        # mesma URL com os parâmetros em outra ordem
        proxima = str(request.url.copy_with(params=sorted(request.url.params.multi_items())))
        return httpx.Response(200, json=pagina_deputados([1], proxima))

    base = "https://dadosabertos.camara.leg.br/api/v2/deputados"
    respx_mock.get(url__startswith=base).mock(side_effect=pagina_que_aponta_para_si_mesma)
    rec = _recurso_deputados()
    extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), tmp_path, http, HOJE)
    with gzip.open(extracao.arquivo_original, "rt", encoding="utf-8") as paginas:
        linhas = [json.loads(linha) for linha in paginas]
    assert len(linhas) == 2  # uma página por legislatura; o link para si mesma não é seguido


def test_adaptador_e_escolhido_pelo_manifesto():
    from coletor.adaptadores import adaptador_para, arquivo

    assert adaptador_para(recurso()) is arquivo
    assert adaptador_para(_recurso_deputados()) is api_json
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_adaptador_api_json.py -v`
Esperado: erro de coleta com `ImportError: cannot import name 'api_json' from 'coletor.adaptadores'`.

- [ ] **Passo 3: implementar**

`coletor/adaptadores/api_json.py`:

```python
"""Adaptador `api_json`: APIs JSON com paginação por link e iteração por legislatura."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from coletor.adaptadores.base import ErroColeta, Extracao, Preparado, preencher
from coletor.competencias import Competencia, legislaturas
from coletor.hashes import sha256_registros
from coletor.http import ClienteHttp
from coletor.manifesto import Recurso

LIMITE_PAGINAS = 10_000


def chave_url(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Identifica uma URL sem depender da ordem dos parâmetros."""
    endereco = httpx.URL(url)
    return endereco.host, endereco.path, tuple(sorted(endereco.params.multi_items()))


def proximo_link(dados: Any) -> str | None:
    if isinstance(dados, dict):
        for link in dados.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "next" and link.get("href"):
                return str(link["href"])
    return None


def extrair_registros(dados: Any, caminho: str | None) -> list[Any]:
    atual = dados
    if caminho:
        for parte in caminho.split("."):
            if not isinstance(atual, dict) or parte not in atual:
                raise ErroColeta(f"caminho '{caminho}' não encontrado (parou em '{parte}')")
            atual = atual[parte]
    if atual is None:
        return []
    if isinstance(atual, dict):
        return [atual]
    if isinstance(atual, list):
        return atual
    raise ErroColeta(f"registros em '{caminho}' não são lista nem objeto")


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    if competencia is None:
        raise ErroColeta(f"{recurso.id}: competência obrigatória")
    url_base = preencher(recurso.url, competencia, hoje)
    valores: list[int | None] = [None]
    if recurso.iteracao is not None:
        valores = list(legislaturas(recurso.iteracao.inicio, hoje))
    original = pasta / "paginas.jsonl.gz"
    resumo = hashlib.sha256()
    total = 0
    status = 0
    paginas = 0
    with gzip.open(original, "wt", encoding="utf-8") as saida:
        for valor in valores:
            params: dict[str, Any] | None = dict(recurso.parametros)
            if recurso.iteracao is not None:
                params[recurso.iteracao.parametro] = valor
            url: str | None = url_base
            visitadas: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
            while url is not None:
                resposta = http.obter_json(url, params)
                paginas += 1
                if paginas > LIMITE_PAGINAS:
                    raise ErroColeta(f"mais de {LIMITE_PAGINAS} páginas: paginação em laço?")
                visitadas.add(chave_url(resposta.url_final))
                pagina = {
                    "url": resposta.url_final,
                    "status": resposta.status,
                    "corpo": resposta.corpo.decode("utf-8"),
                }
                saida.write(json.dumps(pagina, ensure_ascii=False) + "\n")
                resumo.update(resposta.corpo)
                total += len(resposta.corpo)
                status = resposta.status
                url, params = None, None
                if recurso.paginacao == "links_next":
                    seguinte = proximo_link(resposta.dados)
                    if seguinte is not None and chave_url(seguinte) not in visitadas:
                        url = seguinte
    parametros: dict[str, Any] = {"parametros": dict(recurso.parametros)}
    if recurso.iteracao is not None:
        parametros["iteracao"] = {"parametro": recurso.iteracao.parametro, "valores": valores}
    return Extracao(
        competencia=competencia,
        arquivo_original=original,
        extensao="jsonl.gz",
        url=url_base,
        http_status=status,
        bytes_arquivo=total,
        sha256_arquivo=resumo.hexdigest(),
        parametros=parametros,
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    registros: list[Any] = []
    with gzip.open(original, "rt", encoding="utf-8") as entrada:
        for linha in entrada:
            pagina = json.loads(linha)
            registros.extend(extrair_registros(json.loads(pagina["corpo"]), recurso.registros))
    return Preparado(sha256_conteudo=sha256_registros(registros), registros=registros)
```

Substituir `coletor/adaptadores/__init__.py` por:

```python
"""Adaptadores de coleta, escolhidos pelo campo `adaptador` do manifesto.

Cada módulo expõe `extrair(recurso, competencia, pasta, http, hoje) -> Extracao`
e `preparar(recurso, competencia, original, pasta) -> Preparado`.
"""

from __future__ import annotations

from types import ModuleType

from coletor.adaptadores import api_json, arquivo
from coletor.manifesto import Recurso

ADAPTADORES: dict[str, ModuleType] = {"arquivo": arquivo, "api_json": api_json}


def adaptador_para(recurso: Recurso) -> ModuleType:
    return ADAPTADORES[recurso.adaptador]
```

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest tests/test_adaptador_api_json.py tests/test_adaptador_arquivo.py -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `15 passed` e o lint limpo.

- [ ] **Passo 5: commit**

```bash
git add coletor/adaptadores/ tests/test_adaptador_api_json.py
git commit -m "feat(coletor): adaptador de APIs JSON com paginação e iteração por legislatura" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 8: armazenamento, BigQuery e tabelas de controle

**Arquivos:**
- Criar: `coletor/armazenamento.py`, `coletor/warehouse.py`, `coletor/meta.py`, `tests/fakes.py`, `tests/test_armazenamento.py`, `tests/test_meta.py`
- Modificar: `tests/conftest.py` (substituir o conteúdo inteiro)

**Interfaces:**
- Consome: `Config` (Tarefa 1), `Manifesto`/`RecursoCompleto` (Tarefa 2) e `Competencia`/`data_brasilia` (Tarefa 3).
- Produz:
  - Protocolo `Armazenamento` com `enviar(origem: Path, caminho: str) -> str` (devolve `gs://…`), `baixar(caminho, destino)` e `listar(prefixo) -> list[str]`;
  - `caminho_original(prefixo, orgao, recurso, competencia, instante, sha256_conteudo, extensao)`, `caminho_carga(prefixo, orgao, recurso, competencia, coleta_id)`, `caminho_de_uri(uri)` e `GcsArmazenamento(bucket, projeto, credenciais=None)`;
  - `Coluna(nome, tipo, modo="NULLABLE")` e `Particionamento(granularidade: "DAY" | "YEAR", expiracao_dias=None)` com `.decorador(dia) -> str`;
  - Protocolo `Warehouse` com `carregar_parquet(tabela, uri, particionamento, dia) -> int`, `garantir_tabela(tabela, colunas, particao_por=None)`, `anexar_linhas(tabela, linhas, colunas)`, `substituir_linhas(tabela, linhas, colunas)` e `consultar(sql) -> list[dict]`;
  - `BigQueryWarehouse(projeto, regiao, credenciais=None)`;
  - `RegistroColeta`, com `novo(...)`, `recurso_id`, `definir_competencia(c)`, `finalizar(status, instante)` e `para_linha()`;
  - `RegistroExecucao` e `Sucesso`;
  - `HistoricoColetas`, com `ultimo_sha(recurso_id, competencia)`, `ultima_data_sucesso(recurso_id, competencia=None)`, `colunas_referencia(recurso_id, competencia)` e `registrar(registro)`;
  - `RepositorioMeta(warehouse, config)`, com `preparar()`, `carregar_historico()`, `registrar_coleta(r)`, `registrar_execucao(r)`, `publicar_fontes(manifesto, instante)` e `buscar_arquivo_original(coleta_id)`;
  - `STATUS_SUCESSO = ("carregada", "sem_alteracao")`;
  - Para os testes: `FakeArmazenamento(raiz, bucket="bucket-teste")`, com `.objetos: dict[str, Path]`, e `FakeWarehouse(armazenamento)`, com `.particoes`, `.particionamentos`, `.linhas`, `.tabelas`, `.falha_na_carga` e `.resposta_consulta`;
  - Fixtures novas: `config`, `armazenamento` e `warehouse`.

- [ ] **Passo 1: criar os dublês e as fixtures**

`tests/fakes.py`:

```python
"""Dublês de GCS e BigQuery para testes sem nuvem."""

from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from coletor.armazenamento import caminho_de_uri
from coletor.warehouse import Coluna, Particionamento


class FakeArmazenamento:
    def __init__(self, raiz: Path, bucket: str = "bucket-teste") -> None:
        self.raiz = raiz
        self.bucket = bucket
        self.objetos: dict[str, Path] = {}

    def enviar(self, origem: Path, caminho: str) -> str:
        if caminho in self.objetos:
            return f"gs://{self.bucket}/{caminho}"
        destino = self.raiz / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        self.objetos[caminho] = destino
        return f"gs://{self.bucket}/{caminho}"

    def baixar(self, caminho: str, destino: Path) -> None:
        shutil.copyfile(self.objetos[caminho], destino)

    def listar(self, prefixo: str) -> list[str]:
        return sorted(caminho for caminho in self.objetos if caminho.startswith(prefixo))


class FakeWarehouse:
    def __init__(self, armazenamento: FakeArmazenamento) -> None:
        self.armazenamento = armazenamento
        self.particoes: dict[tuple[str, str], pa.Table] = {}
        self.particionamentos: dict[str, Particionamento] = {}
        self.linhas: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.tabelas: set[str] = set()
        self.falha_na_carga: Exception | None = None
        self.resposta_consulta: list[dict[str, Any]] = []

    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        if self.falha_na_carga is not None:
            raise self.falha_na_carga
        dados = pq.read_table(self.armazenamento.objetos[caminho_de_uri(uri)])
        self.particionamentos.setdefault(tabela, particionamento)
        self.particoes[(tabela, particionamento.decorador(dia))] = dados
        return dados.num_rows

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None:
        self.tabelas.add(tabela)

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self.linhas[tabela].extend(linhas)

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self.linhas[tabela] = list(linhas)

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        return list(self.resposta_consulta)
```

Substituir `tests/conftest.py` por:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from coletor.config import Config
from coletor.http import ClienteHttp
from tests.fakes import FakeArmazenamento, FakeWarehouse


@pytest.fixture
def config() -> Config:
    return Config(
        projeto="projeto-teste",
        bucket="bucket-teste",
        regiao="southamerica-east1",
        ambiente="dev",
        versao="teste",
        origem="manual",
    )


@pytest.fixture
def armazenamento(tmp_path: Path) -> FakeArmazenamento:
    return FakeArmazenamento(tmp_path / "gcs")


@pytest.fixture
def warehouse(armazenamento: FakeArmazenamento) -> FakeWarehouse:
    return FakeWarehouse(armazenamento)


@pytest.fixture
def http() -> ClienteHttp:
    cliente = ClienteHttp(dormir=lambda segundos: None)
    yield cliente
    cliente.fechar()
```

- [ ] **Passo 2: escrever os testes que falham**

`tests/test_armazenamento.py`:

```python
from datetime import UTC, date, datetime

import pytest

from coletor.armazenamento import caminho_carga, caminho_de_uri, caminho_original
from coletor.warehouse import Particionamento


def test_caminho_do_original_tem_data_hora_e_hash():
    instante = datetime(2026, 10, 3, 10, 30, tzinfo=UTC)
    caminho = caminho_original(
        "dev/", "cgu", "ceis", "2026-10-02", instante, "abcdef0123456789", "zip"
    )
    assert (
        caminho == "dev/originais/cgu/ceis/competencia=2026-10-02/20261003T103000_abcdef012345.zip"
    )


def test_caminho_de_carga_usa_o_id_da_coleta():
    assert caminho_carga("", "camara", "ceap", "2025", "id-1") == (
        "carga/camara/ceap/competencia=2025/id-1.parquet"
    )


def test_caminho_a_partir_da_uri():
    assert caminho_de_uri("gs://bucket/a/b.zip") == "a/b.zip"
    with pytest.raises(ValueError):
        caminho_de_uri("/a/b.zip")


def test_decorador_de_particao():
    assert Particionamento("DAY", 60).decorador(date(2026, 10, 2)) == "20261002"
    assert Particionamento("YEAR").decorador(date(2025, 1, 1)) == "2025"
```

`tests/test_meta.py`:

```python
import json
from datetime import UTC, date, datetime

import pytest

from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta, RepositorioMeta, Sucesso
from tests.amostras import recurso

HOJE = date(2026, 10, 3)


def _instante(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 11, 0, tzinfo=UTC)


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2024},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
        ),
    )


def _sucesso(dia: date, competencia: date | None = None, colunas=None, sha="h") -> Sucesso:
    return Sucesso(_instante(dia), sha, competencia, colunas)


def test_colunas_de_referencia_usam_a_mesma_competencia_ou_a_anterior_mais_proxima():
    historico = HistoricoColetas(
        {
            ("camara.ceap", "2024"): _sucesso(HOJE, date(2024, 1, 1), [["A", "a"]]),
            ("camara.ceap", "2025"): _sucesso(HOJE, date(2025, 1, 1), [["B", "b"]]),
        }
    )
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2025)) == [["B", "b"]]
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2026)) == [["B", "b"]]
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2023)) is None


def _registro(status: str, colunas=None) -> RegistroColeta:
    registro = RegistroColeta.novo(
        "exec", _ceap(), Competencia.de_ano(2026), _instante(HOJE), "teste"
    )
    registro.sha256_conteudo = "novo"
    registro.colunas = colunas
    return registro.finalizar(status, _instante(HOJE))


def test_registrar_sem_alteracao_mantem_as_colunas_da_ultima_carga():
    historico = HistoricoColetas()
    historico.registrar(_registro("carregada", [["A", "a"]]))
    historico.registrar(_registro("sem_alteracao"))
    historico.registrar(_registro("falha"))
    assert historico.ultimo_sha("camara.ceap", "2026") == "novo"
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2026)) == [["A", "a"]]


def test_linha_de_coleta_serializa_json_e_datas():
    registro = _registro("carregada", [["A", "a"]])
    registro.parametros = {"x": 1}
    linha = registro.para_linha()
    assert json.loads(linha["parametros"]) == {"x": 1}
    assert json.loads(linha["colunas"]) == [["A", "a"]]
    assert linha["competencia_data"] == "2026-01-01"
    assert linha["iniciada_em"] == "2026-10-03T11:00:00+00:00"


def test_historico_e_montado_a_partir_da_consulta(warehouse, config):
    warehouse.resposta_consulta = [
        {
            "orgao": "camara",
            "recurso": "ceap",
            "competencia": "2025",
            "competencia_data": date(2025, 1, 1),
            "finalizada_em": _instante(HOJE),
            "sha256_conteudo": "abc",
            "colunas": '[["A", "a"]]',
        }
    ]
    historico = RepositorioMeta(warehouse, config).carregar_historico()
    assert historico.ultimo_sha("camara.ceap", "2025") == "abc"
    assert historico.ultima_data_sucesso("camara.ceap") == HOJE


def test_buscar_arquivo_original_exige_uuid(warehouse, config):
    with pytest.raises(ValueError):
        RepositorioMeta(warehouse, config).buscar_arquivo_original("1' OR '1'='1")
```

- [ ] **Passo 3: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_armazenamento.py tests/test_meta.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.armazenamento'`, vindo de `tests/fakes.py` pelo `conftest.py`.

- [ ] **Passo 4: implementar o armazenamento**

`coletor/armazenamento.py`:

```python
"""Gravação de originais e arquivos de carga no Cloud Storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class Armazenamento(Protocol):
    def enviar(self, origem: Path, caminho: str) -> str:
        """Grava sem sobrescrever e devolve a URI `gs://`.

        Os caminhos incluem o hash do conteúdo ou o id da coleta: se o objeto já
        existe, ele tem o mesmo conteúdo e é reaproveitado.
        """
        ...

    def baixar(self, caminho: str, destino: Path) -> None: ...

    def listar(self, prefixo: str) -> list[str]: ...


def caminho_original(
    prefixo: str,
    orgao: str,
    recurso: str,
    competencia: str,
    instante: datetime,
    sha256_conteudo: str,
    extensao: str,
) -> str:
    return (
        f"{prefixo}originais/{orgao}/{recurso}/competencia={competencia}/"
        f"{instante:%Y%m%dT%H%M%S}_{sha256_conteudo[:12]}.{extensao}"
    )


def caminho_carga(prefixo: str, orgao: str, recurso: str, competencia: str, coleta_id: str) -> str:
    return f"{prefixo}carga/{orgao}/{recurso}/competencia={competencia}/{coleta_id}.parquet"


def caminho_de_uri(uri: str) -> str:
    """`gs://bucket/a/b.zip` vira `a/b.zip`."""
    if not uri.startswith("gs://"):
        raise ValueError(f"URI do GCS inválida: {uri}")
    return uri.removeprefix("gs://").split("/", 1)[1]


class GcsArmazenamento:
    def __init__(self, bucket: str, projeto: str, credenciais: Any = None) -> None:
        from google.cloud import storage

        self._cliente = storage.Client(project=projeto, credentials=credenciais)
        self._bucket = self._cliente.bucket(bucket)
        self._nome = bucket

    def enviar(self, origem: Path, caminho: str) -> str:
        from google.api_core.exceptions import PreconditionFailed

        try:
            self._bucket.blob(caminho).upload_from_filename(str(origem), if_generation_match=0)
        except PreconditionFailed:
            pass  # já existe com o mesmo conteúdo (caminho endereçado por conteúdo)
        return f"gs://{self._nome}/{caminho}"

    def baixar(self, caminho: str, destino: Path) -> None:
        self._bucket.blob(caminho).download_to_filename(str(destino))

    def listar(self, prefixo: str) -> list[str]:
        return sorted(blob.name for blob in self._cliente.list_blobs(self._bucket, prefix=prefixo))
```

- [ ] **Passo 5: implementar o acesso ao BigQuery**

`coletor/warehouse.py`:

```python
"""Cargas e consultas no BigQuery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str
    modo: str = "NULLABLE"


@dataclass(frozen=True)
class Particionamento:
    granularidade: Literal["DAY", "YEAR"]
    expiracao_dias: int | None = None

    def decorador(self, dia: date) -> str:
        return dia.strftime("%Y%m%d") if self.granularidade == "DAY" else dia.strftime("%Y")


class Warehouse(Protocol):
    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        """Substitui a partição de `dia` com o Parquet em `uri`; devolve as linhas carregadas."""
        ...

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None: ...

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def consultar(self, sql: str) -> list[dict[str, Any]]: ...


class BigQueryWarehouse:
    """`tabela` é sempre `dataset.tabela`; o projeto vem do construtor."""

    def __init__(self, projeto: str, regiao: str, credenciais: Any = None) -> None:
        from google.cloud import bigquery

        self._bq = bigquery
        self._projeto = projeto
        self._cliente = bigquery.Client(project=projeto, location=regiao, credentials=credenciais)

    def _id(self, tabela: str) -> str:
        return f"{self._projeto}.{tabela}"

    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        from google.api_core.exceptions import NotFound

        bigquery = self._bq
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        try:
            self._cliente.get_table(self._id(tabela))
        except NotFound:
            destino = self._id(tabela)
            expiracao = (
                particionamento.expiracao_dias * 86_400_000
                if particionamento.expiracao_dias
                else None
            )
            config.time_partitioning = bigquery.TimePartitioning(
                type_=particionamento.granularidade,
                field="_competencia_data",
                expiration_ms=expiracao,
            )
        else:
            destino = f"{self._id(tabela)}${particionamento.decorador(dia)}"
            config.schema_update_options = [
                bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
                bigquery.SchemaUpdateOption.ALLOW_FIELD_RELAXATION,
            ]
        job = self._cliente.load_table_from_uri(uri, destino, job_config=config)
        job.result()
        return int(job.output_rows or 0)

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None:
        bigquery = self._bq
        objeto = bigquery.Table(self._id(tabela), schema=self._esquema(colunas))
        if particao_por:
            objeto.time_partitioning = bigquery.TimePartitioning(type_="DAY", field=particao_por)
        self._cliente.create_table(objeto, exists_ok=True)

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._carregar_json(tabela, linhas, colunas, self._bq.WriteDisposition.WRITE_APPEND)

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._carregar_json(tabela, linhas, colunas, self._bq.WriteDisposition.WRITE_TRUNCATE)

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        return [dict(linha.items()) for linha in self._cliente.query(sql).result()]

    def _esquema(self, colunas: list[Coluna]) -> list[Any]:
        return [self._bq.SchemaField(c.nome, c.tipo, mode=c.modo) for c in colunas]

    def _carregar_json(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna], disposicao: str
    ) -> None:
        bigquery = self._bq
        config = bigquery.LoadJobConfig(
            schema=self._esquema(colunas),
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=disposicao,
        )
        self._cliente.load_table_from_json(linhas, self._id(tabela), job_config=config).result()
```

- [ ] **Passo 6: implementar as tabelas de controle**

`coletor/meta.py`:

```python
"""Tabelas de controle em `meta`: coletas, execuções e manifesto publicado."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from coletor.competencias import Competencia, data_brasilia
from coletor.config import Config
from coletor.manifesto import Manifesto, RecursoCompleto
from coletor.warehouse import Coluna, Warehouse

STATUS_SUCESSO = ("carregada", "sem_alteracao")

COLUNAS_COLETAS = [
    Coluna("coleta_id", "STRING", "REQUIRED"),
    Coluna("execucao_id", "STRING"),
    Coluna("orgao", "STRING", "REQUIRED"),
    Coluna("recurso", "STRING", "REQUIRED"),
    Coluna("competencia", "STRING"),
    Coluna("competencia_data", "DATE"),
    Coluna("destino", "STRING"),
    Coluna("url", "STRING"),
    Coluna("parametros", "STRING"),
    Coluna("iniciada_em", "TIMESTAMP", "REQUIRED"),
    Coluna("finalizada_em", "TIMESTAMP"),
    Coluna("status", "STRING", "REQUIRED"),
    Coluna("http_status", "INTEGER"),
    Coluna("http_last_modified", "STRING"),
    Coluna("http_etag", "STRING"),
    Coluna("bytes_arquivo", "INTEGER"),
    Coluna("linhas", "INTEGER"),
    Coluna("sha256_arquivo", "STRING"),
    Coluna("sha256_conteudo", "STRING"),
    Coluna("arquivo_original", "STRING"),
    Coluna("arquivo_carga", "STRING"),
    Coluna("colunas", "STRING"),
    Coluna("esquema_alterado", "BOOLEAN"),
    Coluna("erro", "STRING"),
    Coluna("versao_coletor", "STRING"),
]

COLUNAS_EXECUCOES = [
    Coluna("execucao_id", "STRING", "REQUIRED"),
    Coluna("origem", "STRING", "REQUIRED"),
    Coluna("iniciada_em", "TIMESTAMP", "REQUIRED"),
    Coluna("finalizada_em", "TIMESTAMP"),
    Coluna("status", "STRING", "REQUIRED"),
    Coluna("coletas_carregadas", "INTEGER"),
    Coluna("coletas_sem_alteracao", "INTEGER"),
    Coluna("coletas_nao_publicadas", "INTEGER"),
    Coluna("coletas_falha", "INTEGER"),
    Coluna("dbt_status", "STRING"),
    Coluna("dbt_testes_com_erro", "INTEGER"),
    Coluna("versao", "STRING"),
]

COLUNAS_FONTES = [
    Coluna("recurso_id", "STRING", "REQUIRED"),
    Coluna("orgao", "STRING", "REQUIRED"),
    Coluna("recurso", "STRING", "REQUIRED"),
    Coluna("descricao", "STRING"),
    Coluna("fonte_oficial", "STRING"),
    Coluna("condicoes_uso", "STRING"),
    Coluna("adaptador", "STRING"),
    Coluna("url", "STRING"),
    Coluna("publicacao", "STRING"),
    Coluna("competencia_tipo", "STRING"),
    Coluna("cadencia_corrente", "STRING"),
    Coluna("cadencia_anteriores", "STRING"),
    Coluna("publicado_em", "TIMESTAMP"),
]


def _serializar(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


@dataclass
class RegistroColeta:
    coleta_id: str
    execucao_id: str
    orgao: str
    recurso: str
    destino: str
    iniciada_em: datetime
    versao_coletor: str
    competencia: str | None = None
    competencia_data: date | None = None
    url: str | None = None
    parametros: dict[str, Any] = field(default_factory=dict)
    finalizada_em: datetime | None = None
    status: str = "falha"
    http_status: int | None = None
    http_last_modified: str | None = None
    http_etag: str | None = None
    bytes_arquivo: int | None = None
    linhas: int | None = None
    sha256_arquivo: str | None = None
    sha256_conteudo: str | None = None
    arquivo_original: str | None = None
    arquivo_carga: str | None = None
    colunas: list[list[str]] | None = None
    esquema_alterado: bool | None = None
    erro: str | None = None

    @classmethod
    def novo(
        cls,
        execucao_id: str,
        recurso: RecursoCompleto,
        competencia: Competencia | None,
        inicio: datetime,
        versao: str,
        destino: str = "raw",
    ) -> RegistroColeta:
        registro = cls(
            coleta_id=str(uuid.uuid4()),
            execucao_id=execucao_id,
            orgao=recurso.orgao,
            recurso=recurso.recurso.id,
            destino=destino,
            iniciada_em=inicio,
            versao_coletor=versao,
        )
        if competencia is not None:
            registro.definir_competencia(competencia)
        return registro

    @property
    def recurso_id(self) -> str:
        return f"{self.orgao}.{self.recurso}"

    def definir_competencia(self, competencia: Competencia) -> None:
        self.competencia = competencia.rotulo
        self.competencia_data = competencia.data

    def finalizar(self, status: str, instante: datetime) -> RegistroColeta:
        self.status = status
        self.finalizada_em = instante
        return self

    def para_linha(self) -> dict[str, Any]:
        linha = {chave: _serializar(valor) for chave, valor in asdict(self).items()}
        linha["parametros"] = json.dumps(self.parametros, ensure_ascii=False)
        linha["colunas"] = (
            None if self.colunas is None else json.dumps(self.colunas, ensure_ascii=False)
        )
        return linha


@dataclass
class RegistroExecucao:
    execucao_id: str
    origem: str
    iniciada_em: datetime
    finalizada_em: datetime
    status: str
    coletas_carregadas: int
    coletas_sem_alteracao: int
    coletas_nao_publicadas: int
    coletas_falha: int
    versao: str
    dbt_status: str | None = None
    dbt_testes_com_erro: int | None = None

    def para_linha(self) -> dict[str, Any]:
        return {chave: _serializar(valor) for chave, valor in asdict(self).items()}


@dataclass
class Sucesso:
    finalizada_em: datetime
    sha256_conteudo: str | None
    competencia_data: date | None
    colunas: list[list[str]] | None


class HistoricoColetas:
    """Última coleta bem-sucedida de cada (recurso, competência)."""

    def __init__(self, sucessos: dict[tuple[str, str], Sucesso] | None = None) -> None:
        self._sucessos = dict(sucessos or {})

    def ultimo_sha(self, recurso_id: str, competencia: str) -> str | None:
        sucesso = self._sucessos.get((recurso_id, competencia))
        return sucesso.sha256_conteudo if sucesso else None

    def ultima_data_sucesso(self, recurso_id: str, competencia: str | None = None) -> date | None:
        instantes = [
            sucesso.finalizada_em
            for (rid, comp), sucesso in self._sucessos.items()
            if rid == recurso_id and (competencia is None or comp == competencia)
        ]
        return data_brasilia(max(instantes)) if instantes else None

    def colunas_referencia(
        self, recurso_id: str, competencia: Competencia
    ) -> list[list[str]] | None:
        """Colunas da mesma competência; senão, da competência anterior mais próxima."""
        mesma = self._sucessos.get((recurso_id, competencia.rotulo))
        if mesma is not None and mesma.colunas is not None:
            return mesma.colunas
        anteriores = [
            sucesso
            for (rid, _), sucesso in self._sucessos.items()
            if rid == recurso_id
            and sucesso.colunas is not None
            and sucesso.competencia_data is not None
            and sucesso.competencia_data < competencia.data
        ]
        if not anteriores:
            return None
        return max(anteriores, key=lambda s: (s.competencia_data, s.finalizada_em)).colunas

    def registrar(self, registro: RegistroColeta) -> None:
        if registro.status not in STATUS_SUCESSO or registro.competencia is None:
            return
        chave = (registro.recurso_id, registro.competencia)
        anterior = self._sucessos.get(chave)
        colunas = registro.colunas if registro.status == "carregada" else None
        if colunas is None and anterior is not None:
            colunas = anterior.colunas
        assert registro.finalizada_em is not None
        self._sucessos[chave] = Sucesso(
            registro.finalizada_em, registro.sha256_conteudo, registro.competencia_data, colunas
        )


SQL_HISTORICO = """
WITH sucesso AS (
  SELECT orgao, recurso, competencia, competencia_data, finalizada_em, sha256_conteudo,
         ROW_NUMBER() OVER (
           PARTITION BY orgao, recurso, competencia ORDER BY finalizada_em DESC) AS ordem
  FROM `{tabela}`
  WHERE status IN ('carregada', 'sem_alteracao') AND destino = 'raw'
),
carga AS (
  SELECT orgao, recurso, competencia, colunas,
         ROW_NUMBER() OVER (
           PARTITION BY orgao, recurso, competencia ORDER BY finalizada_em DESC) AS ordem
  FROM `{tabela}`
  WHERE status = 'carregada' AND destino = 'raw'
)
SELECT s.orgao, s.recurso, s.competencia, s.competencia_data, s.finalizada_em,
       s.sha256_conteudo, c.colunas
FROM sucesso AS s
LEFT JOIN carga AS c
  ON c.orgao = s.orgao AND c.recurso = s.recurso AND c.competencia = s.competencia AND c.ordem = 1
WHERE s.ordem = 1
"""


class RepositorioMeta:
    def __init__(self, warehouse: Warehouse, config: Config) -> None:
        self._warehouse = warehouse
        self._config = config
        dataset = config.dataset("meta")
        self.tabela_coletas = f"{dataset}.coletas"
        self.tabela_execucoes = f"{dataset}.execucoes"
        self.tabela_fontes = f"{dataset}.fontes"

    def preparar(self) -> None:
        self._warehouse.garantir_tabela(self.tabela_coletas, COLUNAS_COLETAS, "iniciada_em")
        self._warehouse.garantir_tabela(self.tabela_execucoes, COLUNAS_EXECUCOES, "iniciada_em")
        self._warehouse.garantir_tabela(self.tabela_fontes, COLUNAS_FONTES)

    def carregar_historico(self) -> HistoricoColetas:
        sql = SQL_HISTORICO.format(tabela=f"{self._config.projeto}.{self.tabela_coletas}")
        sucessos: dict[tuple[str, str], Sucesso] = {}
        for linha in self._warehouse.consultar(sql):
            colunas = json.loads(linha["colunas"]) if linha.get("colunas") else None
            chave = (f"{linha['orgao']}.{linha['recurso']}", linha["competencia"])
            sucessos[chave] = Sucesso(
                linha["finalizada_em"], linha["sha256_conteudo"], linha["competencia_data"], colunas
            )
        return HistoricoColetas(sucessos)

    def registrar_coleta(self, registro: RegistroColeta) -> None:
        self._warehouse.anexar_linhas(self.tabela_coletas, [registro.para_linha()], COLUNAS_COLETAS)

    def registrar_execucao(self, registro: RegistroExecucao) -> None:
        self._warehouse.anexar_linhas(
            self.tabela_execucoes, [registro.para_linha()], COLUNAS_EXECUCOES
        )

    def publicar_fontes(self, manifesto: Manifesto, instante: datetime) -> None:
        linhas = [
            {
                "recurso_id": rc.id,
                "orgao": rc.orgao,
                "recurso": rc.recurso.id,
                "descricao": rc.recurso.descricao,
                "fonte_oficial": rc.recurso.fonte_oficial,
                "condicoes_uso": rc.recurso.condicoes_uso,
                "adaptador": rc.recurso.adaptador,
                "url": rc.recurso.url,
                "publicacao": rc.recurso.publicacao,
                "competencia_tipo": rc.recurso.competencia.tipo,
                "cadencia_corrente": rc.recurso.cadencia.corrente,
                "cadencia_anteriores": rc.recurso.cadencia.anteriores,
                "publicado_em": instante.isoformat(),
            }
            for rc in manifesto.todos()
        ]
        self._warehouse.substituir_linhas(self.tabela_fontes, linhas, COLUNAS_FONTES)

    def buscar_arquivo_original(self, coleta_id: str) -> str | None:
        coleta_id = str(uuid.UUID(coleta_id))  # valida o formato antes de montar o SQL
        sql = (
            f"SELECT arquivo_original FROM `{self._config.projeto}.{self.tabela_coletas}` "
            f"WHERE coleta_id = '{coleta_id}' LIMIT 1"
        )
        linhas = self._warehouse.consultar(sql)
        return linhas[0]["arquivo_original"] if linhas else None
```

- [ ] **Passo 7: rodar e confirmar que passa**

Executar: `uv run pytest -v && uv run ruff check . && uv run ruff format --check .`
Esperado: todos os testes até aqui passando (`64 passed`) e o lint limpo.

- [ ] **Passo 8: commit**

```bash
git add coletor/armazenamento.py coletor/warehouse.py coletor/meta.py tests/fakes.py tests/conftest.py tests/test_armazenamento.py tests/test_meta.py
git commit -m "feat(coletor): armazenamento no GCS, cargas no BigQuery e tabelas de controle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 9: fluxo de coleta, agenda e execução

**Arquivos:**
- Criar: `coletor/coleta.py`, `coletor/agenda.py`, `coletor/execucao.py`, `tests/test_agenda.py`, `tests/test_coleta.py`
- Modificar: `tests/conftest.py` (substituir o conteúdo inteiro)

**Interfaces:**
- Consome: `adaptador_para` (Tarefa 7), `Preparado` (Tarefa 6), caminhos e `Armazenamento` (Tarefa 8), `Warehouse`/`Particionamento` (Tarefa 8), `HistoricoColetas`/`RegistroColeta`/`RegistroExecucao`/`RepositorioMeta` (Tarefa 8), `csv_para_parquet`/`registros_para_parquet`/`Controle` (Tarefa 5), `ClienteHttp`/`ErroHttp` (Tarefa 4) e `Competencia`/`anos`/`data_brasilia` (Tarefa 3).
- Produz:
  - `Dependencias(config, http, armazenamento, warehouse, agora: Callable[[], datetime])` e `EXPIRACAO_SNAPSHOT_DIAS = 60`;
  - `particionamento(recurso, destino) -> Particionamento` e `tabela_destino(config, recurso, destino) -> str`;
  - `coletar(recurso, competencia, historico, deps, execucao_id, forcar=False) -> RegistroColeta`;
  - `recarregar(recurso, competencia, uri_original, historico, deps, execucao_id, destino) -> RegistroColeta`;
  - `Tarefa(recurso, competencia | None)`, `tarefa_snapshot(recurso, hoje)`, `tarefas_pendentes(recursos, historico, hoje)` e `INTERVALO_DIAS`;
  - `ResumoColetas`, com `contar(status)` e `.sucesso`;
  - `rodar(tarefas, historico, deps, repositorio, execucao_id, forcar=False) -> ResumoColetas` e `registro_execucao(execucao_id, origem, deps, inicio, resumo) -> RegistroExecucao`;
  - a fixture `deps`.

- [ ] **Passo 1: completar as fixtures**

Substituir `tests/conftest.py` por:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from coletor.coleta import Dependencias
from coletor.config import Config
from coletor.http import ClienteHttp
from tests.amostras import AGORA
from tests.fakes import FakeArmazenamento, FakeWarehouse


@pytest.fixture
def config() -> Config:
    return Config(
        projeto="projeto-teste",
        bucket="bucket-teste",
        regiao="southamerica-east1",
        ambiente="dev",
        versao="teste",
        origem="manual",
    )


@pytest.fixture
def armazenamento(tmp_path: Path) -> FakeArmazenamento:
    return FakeArmazenamento(tmp_path / "gcs")


@pytest.fixture
def warehouse(armazenamento: FakeArmazenamento) -> FakeWarehouse:
    return FakeWarehouse(armazenamento)


@pytest.fixture
def http() -> ClienteHttp:
    cliente = ClienteHttp(dormir=lambda segundos: None)
    yield cliente
    cliente.fechar()


@pytest.fixture
def deps(config, http, armazenamento, warehouse) -> Dependencias:
    return Dependencias(
        config=config,
        http=http,
        armazenamento=armazenamento,
        warehouse=warehouse,
        agora=lambda: AGORA,
    )
```

- [ ] **Passo 2: escrever os testes que falham**

`tests/test_agenda.py`:

```python
from datetime import UTC, date, datetime, timedelta

from coletor.agenda import tarefas_pendentes
from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, Sucesso
from tests.amostras import recurso

HOJE = date(2026, 10, 3)


def _instante(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 11, 0, tzinfo=UTC)


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2024},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
        ),
    )


def _sucesso(dia: date, competencia: date | None = None, colunas=None, sha="h") -> Sucesso:
    return Sucesso(_instante(dia), sha, competencia, colunas)


def test_sem_historico_tudo_esta_vencido():
    cnep = RecursoCompleto("cgu", recurso())
    tarefas = tarefas_pendentes([cnep, _ceap()], HistoricoColetas(), HOJE)
    assert [(t.recurso.id, t.competencia) for t in tarefas] == [
        ("cgu.cnep", None),
        ("camara.ceap", Competencia.de_ano(2024)),
        ("camara.ceap", Competencia.de_ano(2025)),
        ("camara.ceap", Competencia.de_ano(2026)),
    ]


def test_cadencias_do_ano_corrente_e_dos_anteriores():
    historico = HistoricoColetas(
        {
            ("camara.ceap", "2024"): _sucesso(HOJE - timedelta(days=7)),
            ("camara.ceap", "2025"): _sucesso(HOJE - timedelta(days=6)),
            ("camara.ceap", "2026"): _sucesso(HOJE),
        }
    )
    tarefas = tarefas_pendentes([_ceap()], historico, HOJE)
    assert [t.competencia.rotulo for t in tarefas] == ["2024"]


def test_snapshot_diario_coletado_ontem_esta_vencido():
    cnep = RecursoCompleto("cgu", recurso())
    ontem = HistoricoColetas({("cgu.cnep", "2026-10-01"): _sucesso(HOJE - timedelta(days=1))})
    hoje = HistoricoColetas({("cgu.cnep", "2026-10-02"): _sucesso(HOJE)})
    assert len(tarefas_pendentes([cnep], ontem, HOJE)) == 1
    assert tarefas_pendentes([cnep], hoje, HOJE) == []


def test_snapshot_por_data_de_coleta_recebe_a_competencia_de_hoje():
    deputados = RecursoCompleto(
        "camara",
        recurso(
            id="deputados",
            adaptador="api_json",
            url="https://x",
            competencia={"tipo": "data_coleta"},
            formato={"tipo": "json"},
        ),
    )
    [tarefa] = tarefas_pendentes([deputados], HistoricoColetas(), HOJE)
    assert tarefa.competencia == Competencia.de_dia(HOJE)
```

`tests/test_coleta.py`:

```python
from datetime import UTC, date, datetime

import httpx

from coletor.coleta import coletar, recarregar
from coletor.competencias import Competencia
from coletor.execucao import ResumoColetas
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas
from tests.amostras import CNEP_CSV, PAGINA_CGU, recurso, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
CNEP = RecursoCompleto("cgu", recurso())


def _mock_cnep(respx_mock, conteudo: bytes = CNEP_CSV.encode("cp1252")):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(200, content=zip_com({"20261002_CNEP.csv": conteudo}))
    )


def test_coleta_nova_arquiva_converte_e_carrega(respx_mock, deps, armazenamento, warehouse):
    _mock_cnep(respx_mock)
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "carregada", registro.erro
    assert registro.competencia == "2026-10-02"
    assert registro.linhas == 2
    assert registro.esquema_alterado is False
    assert registro.arquivo_original.startswith(
        "gs://bucket-teste/dev/originais/cgu/cnep/competencia=2026-10-02/20261003T103000_"
    )
    assert registro.arquivo_original.endswith(".bin")
    assert registro.arquivo_carga == (
        f"gs://bucket-teste/dev/carga/cgu/cnep/competencia=2026-10-02/{registro.coleta_id}.parquet"
    )
    tabela = warehouse.particoes[("raw_cgu_dev.cnep", "20261002")]
    assert tabela.column("_arquivo_original").to_pylist() == [registro.arquivo_original] * 2
    particionamento = warehouse.particionamentos["raw_cgu_dev.cnep"]
    assert (particionamento.granularidade, particionamento.expiracao_dias) == ("DAY", 60)


def test_mesmo_conteudo_da_ultima_coleta_nao_e_recarregado(respx_mock, deps, armazenamento):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(primeiro)
    objetos_antes = dict(armazenamento.objetos)
    segundo = coletar(CNEP, None, historico, deps, "exec-2")
    assert segundo.status == "sem_alteracao"
    assert segundo.sha256_conteudo == primeiro.sha256_conteudo
    assert armazenamento.objetos == objetos_antes


def test_forcar_recarrega_mesmo_sem_alteracao(respx_mock, deps):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    historico.registrar(coletar(CNEP, None, historico, deps, "exec-1"))
    deps.agora = lambda: datetime(2026, 10, 3, 10, 31, tzinfo=UTC)
    assert coletar(CNEP, None, historico, deps, "exec-2", forcar=True).status == "carregada"


def test_falha_na_carga_vira_registro_sem_carga_parcial(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    warehouse.falha_na_carga = RuntimeError("BigQuery fora do ar")
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "falha"
    assert registro.erro == "RuntimeError: BigQuery fora do ar"
    assert warehouse.particoes == {}


def test_mudanca_de_cabecalho_marca_esquema_alterado(respx_mock, deps):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(primeiro)
    novo_csv = CNEP_CSV.replace('"OBSERVAÇÕES"', '"OBSERVACAO NOVA"')
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": novo_csv.encode("cp1252")})
        )
    )
    deps.agora = lambda: datetime(2026, 10, 3, 10, 31, tzinfo=UTC)
    segundo = coletar(CNEP, None, historico, deps, "exec-2")
    assert segundo.status == "carregada"
    assert segundo.esquema_alterado is True


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2008},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
            formato={"tipo": "csv", "compressao": "zip", "arquivo": "Ano-{ano}.csv"},
        ),
    )


def test_ano_corrente_ainda_nao_publicado_no_primeiro_trimestre(respx_mock, deps):
    respx_mock.get("https://www.camara.leg.br/cotas/Ano-2027.csv.zip").mock(
        return_value=httpx.Response(404)
    )
    deps.agora = lambda: datetime(2027, 1, 2, 10, 30, tzinfo=UTC)
    registro = coletar(_ceap(), Competencia.de_ano(2027), HistoricoColetas(), deps, "exec-1")
    assert registro.status == "nao_publicada"
    deps.agora = lambda: datetime(2027, 5, 2, 10, 30, tzinfo=UTC)
    tardio = coletar(_ceap(), Competencia.de_ano(2027), HistoricoColetas(), deps, "exec-2")
    assert tardio.status == "falha"


def test_por_competencia_carrega_na_particao_anual(respx_mock, deps, warehouse):
    respx_mock.get("https://www.camara.leg.br/cotas/Ano-2025.csv.zip").mock(
        return_value=httpx.Response(200, content=zip_com({"Ano-2025.csv": b'"A";"B"\n"1";"2"\n'}))
    )
    registro = coletar(_ceap(), Competencia.de_ano(2025), HistoricoColetas(), deps, "exec-1")
    assert registro.status == "carregada", registro.erro
    assert ("raw_camara_dev.ceap", "2025") in warehouse.particoes
    particionamento = warehouse.particionamentos["raw_camara_dev.ceap"]
    assert (particionamento.granularidade, particionamento.expiracao_dias) == ("YEAR", None)


def test_recarga_para_replay_usa_o_original_e_nao_expira(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    original = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    registro = recarregar(
        CNEP,
        Competencia.de_dia(date(2026, 10, 2)),
        original.arquivo_original,
        HistoricoColetas(),
        deps,
        "exec-2",
        "replay",
    )
    assert registro.status == "recarregada", registro.erro
    assert registro.sha256_conteudo == original.sha256_conteudo
    assert ("replay_dev.cgu__cnep", "20261002") in warehouse.particoes
    assert warehouse.particionamentos["replay_dev.cgu__cnep"].expiracao_dias is None


def test_coleta_forcada_duas_vezes_no_mesmo_segundo_reaproveita_o_original(
    respx_mock, deps, armazenamento
):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1", forcar=True)
    segundo = coletar(CNEP, None, historico, deps, "exec-2", forcar=True)
    assert (primeiro.status, segundo.status) == ("carregada", "carregada")
    assert primeiro.arquivo_original == segundo.arquivo_original
    originais = [c for c in armazenamento.objetos if "/originais/" in c]
    assert len(originais) == 1


def test_html_de_erro_no_lugar_do_zip_vira_falha(respx_mock, deps, warehouse):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(200, text="<html>Serviço indisponível</html>")
    )
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "falha"
    assert registro.erro.startswith("BadZipFile")
    assert warehouse.particoes == {}


def test_json_invalido_na_api_vira_falha(respx_mock, deps):
    municipios = RecursoCompleto(
        "ibge",
        recurso(
            id="municipios",
            adaptador="api_json",
            url="https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
            competencia={"tipo": "data_coleta"},
            formato={"tipo": "json"},
        ),
    )
    respx_mock.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios").mock(
        return_value=httpx.Response(200, text="<html>erro</html>")
    )
    registro = coletar(
        municipios, Competencia.de_dia(date(2026, 10, 3)), HistoricoColetas(), deps, "e"
    )
    assert registro.status == "falha"
    assert "JSONDecodeError" in registro.erro


def test_execucao_interrompida_antes_da_carga_e_refeita_na_seguinte(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    warehouse.falha_na_carga = RuntimeError("processo interrompido")
    interrompida = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(interrompida)  # falha não conta como sucesso
    warehouse.falha_na_carga = None
    deps.agora = lambda: datetime(2026, 10, 3, 11, 0, tzinfo=UTC)
    refeita = coletar(CNEP, None, historico, deps, "exec-2")
    assert (interrompida.status, refeita.status) == ("falha", "carregada")
    assert ("raw_cgu_dev.cnep", "20261002") in warehouse.particoes


def test_resumo_conta_status_e_so_falha_derruba_o_sucesso():
    resumo = ResumoColetas()
    for status in ["carregada", "sem_alteracao", "nao_publicada"]:
        resumo.contar(status)
    assert resumo.sucesso
    resumo.contar("falha")
    assert (resumo.carregadas, resumo.sem_alteracao, resumo.nao_publicadas, resumo.falhas) == (
        1,
        1,
        1,
        1,
    )
    assert not resumo.sucesso
```

- [ ] **Passo 3: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_agenda.py tests/test_coleta.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.coleta'`, vindo do `conftest.py`.

- [ ] **Passo 4: implementar o fluxo de coleta**

`coletor/coleta.py`:

```python
"""Fluxo de uma coleta: extrair, deduplicar, arquivar, converter, carregar e registrar."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from coletor.adaptadores import adaptador_para
from coletor.adaptadores.base import Preparado
from coletor.armazenamento import Armazenamento, caminho_carga, caminho_de_uri, caminho_original
from coletor.competencias import Competencia, data_brasilia
from coletor.config import Config
from coletor.conversao import Controle, csv_para_parquet, registros_para_parquet
from coletor.hashes import sha256_arquivo
from coletor.http import ClienteHttp, ErroHttp
from coletor.manifesto import Recurso, RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta
from coletor.warehouse import Particionamento, Warehouse

EXPIRACAO_SNAPSHOT_DIAS = 60


@dataclass
class Dependencias:
    config: Config
    http: ClienteHttp
    armazenamento: Armazenamento
    warehouse: Warehouse
    agora: Callable[[], datetime]


def particionamento(recurso: Recurso, destino: str) -> Particionamento:
    if recurso.publicacao == "snapshot":
        return Particionamento("DAY", EXPIRACAO_SNAPSHOT_DIAS if destino == "raw" else None)
    return Particionamento("YEAR")


def tabela_destino(config: Config, recurso: RecursoCompleto, destino: str) -> str:
    if destino == "replay":
        return f"{config.dataset('replay')}.{recurso.orgao}__{recurso.recurso.id}"
    return f"{config.dataset('raw_' + recurso.orgao)}.{recurso.recurso.id}"


def nao_publicada(
    recurso: Recurso, competencia: Competencia | None, erro: ErroHttp, hoje: date
) -> bool:
    """HTTP 404 no ano corrente, no 1º trimestre: a fonte ainda não publicou o ano."""
    return (
        erro.status == 404
        and recurso.publicacao == "por_competencia"
        and competencia is not None
        and competencia.data.year == hoje.year
        and hoje.month <= 3
    )


def _descrever(erro: Exception) -> str:
    return f"{type(erro).__name__}: {erro}"


def _converter_e_carregar(
    recurso: RecursoCompleto,
    competencia: Competencia,
    uri_original: str,
    preparado: Preparado,
    registro: RegistroColeta,
    historico: HistoricoColetas,
    deps: Dependencias,
    pasta: Path,
    destino: str,
) -> None:
    config = deps.config
    controle = Controle(
        registro.coleta_id, competencia.rotulo, competencia.data, uri_original, deps.agora()
    )
    parquet = pasta / "carga.parquet"
    if preparado.csv is not None:
        resultado = csv_para_parquet(preparado.csv, parquet, recurso.recurso.formato, controle)
    else:
        resultado = registros_para_parquet(preparado.registros or [], parquet, controle)
    caminho = caminho_carga(
        config.prefixo_gcs,
        recurso.orgao,
        recurso.recurso.id,
        competencia.rotulo,
        registro.coleta_id,
    )
    registro.arquivo_carga = deps.armazenamento.enviar(parquet, caminho)
    registro.linhas = deps.warehouse.carregar_parquet(
        tabela_destino(config, recurso, destino),
        registro.arquivo_carga,
        particionamento(recurso.recurso, destino),
        competencia.data,
    )
    registro.colunas = resultado.colunas
    referencia = historico.colunas_referencia(recurso.id, competencia)
    registro.esquema_alterado = referencia is not None and [o for o, _ in referencia] != [
        o for o, _ in resultado.colunas
    ]


def coletar(
    recurso: RecursoCompleto,
    competencia: Competencia | None,
    historico: HistoricoColetas,
    deps: Dependencias,
    execucao_id: str,
    forcar: bool = False,
) -> RegistroColeta:
    inicio = deps.agora()
    hoje = data_brasilia(inicio)
    registro = RegistroColeta.novo(
        execucao_id, recurso, competencia, inicio, deps.config.versao, destino="raw"
    )
    adaptador = adaptador_para(recurso.recurso)
    with tempfile.TemporaryDirectory(prefix="coletor-") as temporario:
        pasta = Path(temporario)
        try:
            extracao = adaptador.extrair(recurso.recurso, competencia, pasta, deps.http, hoje)
            registro.definir_competencia(extracao.competencia)
            registro.url = extracao.url
            registro.parametros = extracao.parametros
            registro.http_status = extracao.http_status
            registro.http_last_modified = extracao.last_modified
            registro.http_etag = extracao.etag
            registro.bytes_arquivo = extracao.bytes_arquivo
            registro.sha256_arquivo = extracao.sha256_arquivo
            preparado = adaptador.preparar(
                recurso.recurso, extracao.competencia, extracao.arquivo_original, pasta
            )
            registro.sha256_conteudo = preparado.sha256_conteudo
            anterior = historico.ultimo_sha(recurso.id, extracao.competencia.rotulo)
            if not forcar and anterior == preparado.sha256_conteudo:
                return registro.finalizar("sem_alteracao", deps.agora())
            caminho = caminho_original(
                deps.config.prefixo_gcs,
                recurso.orgao,
                recurso.recurso.id,
                extracao.competencia.rotulo,
                inicio,
                preparado.sha256_conteudo,
                extracao.extensao,
            )
            registro.arquivo_original = deps.armazenamento.enviar(
                extracao.arquivo_original, caminho
            )
            _converter_e_carregar(
                recurso,
                extracao.competencia,
                registro.arquivo_original,
                preparado,
                registro,
                historico,
                deps,
                pasta,
                "raw",
            )
            return registro.finalizar("carregada", deps.agora())
        except ErroHttp as erro:
            registro.erro = _descrever(erro)
            status = (
                "nao_publicada"
                if nao_publicada(recurso.recurso, competencia, erro, hoje)
                else "falha"
            )
            return registro.finalizar(status, deps.agora())
        except Exception as erro:  # noqa: BLE001 - toda falha vira registro e as demais seguem
            registro.erro = _descrever(erro)
            return registro.finalizar("falha", deps.agora())


def recarregar(
    recurso: RecursoCompleto,
    competencia: Competencia,
    uri_original: str,
    historico: HistoricoColetas,
    deps: Dependencias,
    execucao_id: str,
    destino: str,
) -> RegistroColeta:
    inicio = deps.agora()
    registro = RegistroColeta.novo(
        execucao_id, recurso, competencia, inicio, deps.config.versao, destino=destino
    )
    registro.url = uri_original
    registro.parametros = {"recarga_de": uri_original}
    registro.arquivo_original = uri_original
    adaptador = adaptador_para(recurso.recurso)
    with tempfile.TemporaryDirectory(prefix="coletor-") as temporario:
        pasta = Path(temporario)
        try:
            extensao = uri_original.rsplit("/", 1)[-1].split(".", 1)[1]
            original = pasta / f"original.{extensao}"
            deps.armazenamento.baixar(caminho_de_uri(uri_original), original)
            registro.bytes_arquivo = original.stat().st_size
            registro.sha256_arquivo = sha256_arquivo(original)
            preparado = adaptador.preparar(recurso.recurso, competencia, original, pasta)
            registro.sha256_conteudo = preparado.sha256_conteudo
            _converter_e_carregar(
                recurso,
                competencia,
                uri_original,
                preparado,
                registro,
                historico,
                deps,
                pasta,
                destino,
            )
            return registro.finalizar("recarregada", deps.agora())
        except Exception as erro:  # noqa: BLE001
            registro.erro = _descrever(erro)
            return registro.finalizar("falha", deps.agora())
```

- [ ] **Passo 5: implementar a agenda e a execução**

`coletor/agenda.py`:

```python
"""Decide quais (recurso, competência) estão com a coleta vencida."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from coletor.competencias import Competencia, anos
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas

INTERVALO_DIAS = {"diaria": 1, "semanal": 7, "mensal": 30}


@dataclass(frozen=True)
class Tarefa:
    recurso: RecursoCompleto
    competencia: Competencia | None  # None: a competência é descoberta na coleta (CGU)


def _vencida(ultima: date | None, hoje: date, cadencia: str) -> bool:
    return ultima is None or (hoje - ultima).days >= INTERVALO_DIAS[cadencia]


def tarefa_snapshot(recurso: RecursoCompleto, hoje: date) -> Tarefa:
    if recurso.recurso.competencia.tipo == "data_arquivo":
        return Tarefa(recurso, None)
    return Tarefa(recurso, Competencia.de_dia(hoje))


def tarefas_pendentes(
    recursos: list[RecursoCompleto], historico: HistoricoColetas, hoje: date
) -> list[Tarefa]:
    tarefas: list[Tarefa] = []
    for rc in recursos:
        regra = rc.recurso
        if regra.publicacao == "snapshot":
            if _vencida(historico.ultima_data_sucesso(rc.id), hoje, regra.cadencia.corrente):
                tarefas.append(tarefa_snapshot(rc, hoje))
            continue
        assert regra.competencia.inicio is not None and regra.cadencia.anteriores is not None
        for ano in anos(regra.competencia.inicio, hoje):
            cadencia = regra.cadencia.corrente if ano == hoje.year else regra.cadencia.anteriores
            competencia = Competencia.de_ano(ano)
            if _vencida(historico.ultima_data_sucesso(rc.id, competencia.rotulo), hoje, cadencia):
                tarefas.append(Tarefa(rc, competencia))
    return tarefas
```

`coletor/execucao.py`:

```python
"""Execução de uma lista de tarefas, com registro em `meta`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from coletor.agenda import Tarefa
from coletor.coleta import Dependencias, coletar
from coletor.meta import HistoricoColetas, RegistroExecucao, RepositorioMeta

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
        repositorio.registrar_coleta(registro)
        historico.registrar(registro)
        resumo.contar(registro.status)
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
) -> RegistroExecucao:
    return RegistroExecucao(
        execucao_id=execucao_id,
        origem=origem,
        iniciada_em=inicio,
        finalizada_em=deps.agora(),
        status="sucesso" if resumo.sucesso else "falha",
        coletas_carregadas=resumo.carregadas,
        coletas_sem_alteracao=resumo.sem_alteracao,
        coletas_nao_publicadas=resumo.nao_publicadas,
        coletas_falha=resumo.falhas,
        versao=deps.config.versao,
    )
```

- [ ] **Passo 6: rodar e confirmar que passa**

Executar: `uv run pytest -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `81 passed` e o lint limpo.

- [ ] **Passo 7: commit**

```bash
git add coletor/coleta.py coletor/agenda.py coletor/execucao.py tests/conftest.py tests/test_agenda.py tests/test_coleta.py
git commit -m "feat(coletor): fluxo de coleta idempotente, agenda por cadência e execução" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 10: CLI e montagem das dependências reais

**Arquivos:**
- Criar: `coletor/cli.py`, `coletor/gcp.py`, `tests/test_cli.py`

**Interfaces:**
- Consome: tudo o que foi produzido nas tarefas 1 a 9.
- Produz:
  - `main(argv=None, fabrica=None, env=None) -> int`, com os comandos `fontes`, `executar [--recursos] [--forcar]`, `coletar <recurso> [--competencia | --de [--ate]] [--forcar]` e `recarregar <recurso> --competencia C [--coleta-id] [--destino raw|replay]`. Códigos de saída: 0 em sucesso, 1 quando houve falha de coleta, 2 em erro de uso ou de configuração;
  - `montar_dependencias(config) -> Dependencias` e `agora_utc()`;
  - `ErroUso`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_cli.py`:

```python
import httpx
import pytest

from coletor.cli import main
from tests.amostras import CEAP_CSV, CNEP_CSV, PAGINA_CGU, RAIZ, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
ENV = {"ELEITORADO_PROJETO": "projeto-teste", "ELEITORADO_BUCKET": "bucket-teste"}


def _rodar(argumentos: list[str], deps) -> int:
    return main(
        ["--fontes", str(RAIZ / "fontes"), *argumentos], fabrica=lambda config: deps, env=ENV
    )


def test_executar_coleta_o_recurso_pedido_e_registra_tudo(respx_mock, deps, warehouse):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")})
        )
    )
    assert _rodar(["executar", "--recursos", "cgu.cnep"], deps) == 0
    [coleta] = warehouse.linhas["meta_dev.coletas"]
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (coleta["recurso"], coleta["status"], coleta["linhas"]) == ("cnep", "carregada", 2)
    assert (execucao["status"], execucao["coletas_carregadas"], execucao["origem"]) == (
        "sucesso",
        1,
        "manual",
    )
    assert len(warehouse.linhas["meta_dev.fontes"]) == 7
    assert "meta_dev.coletas" in warehouse.tabelas


def test_executar_com_falha_sai_com_codigo_1(respx_mock, deps, warehouse):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))
    assert _rodar(["executar", "--recursos", "cgu.cnep"], deps) == 1
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["coletas_falha"]) == ("falha", 1)


def test_coletar_intervalo_de_anos(respx_mock, deps, warehouse):
    for ano in (2025, 2026):
        respx_mock.get(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip").mock(
            return_value=httpx.Response(200, content=zip_com({f"Ano-{ano}.csv": CEAP_CSV.encode()}))
        )
    assert _rodar(["coletar", "camara.ceap", "--de", "2025"], deps) == 0
    competencias = [linha["competencia"] for linha in warehouse.linhas["meta_dev.coletas"]]
    assert competencias == ["2025", "2026"]


def test_coletar_snapshot_com_competencia_e_erro_de_uso(deps, capsys):
    assert _rodar(["coletar", "cgu.cnep", "--competencia", "2025"], deps) == 2
    assert "snapshot" in capsys.readouterr().err


def test_recarregar_snapshot_antigo_no_raw_e_recusado(deps, capsys):
    assert _rodar(["recarregar", "cgu.cnep", "--competencia", "2026-07-01"], deps) == 2
    assert "--destino replay" in capsys.readouterr().err


def test_recarregar_para_replay_usa_o_ultimo_original(respx_mock, deps, warehouse):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")})
        )
    )
    assert _rodar(["executar", "--recursos", "cgu.cnep"], deps) == 0
    codigo = _rodar(
        ["recarregar", "cgu.cnep", "--competencia", "2026-10-02", "--destino", "replay"], deps
    )
    assert codigo == 0
    ultima = warehouse.linhas["meta_dev.coletas"][-1]
    assert (ultima["status"], ultima["destino"]) == ("recarregada", "replay")


def test_sem_configuracao_sai_com_codigo_2(capsys):
    codigo = main(["--fontes", str(RAIZ / "fontes"), "fontes"], fabrica=None, env={})
    assert codigo == 2
    assert "ELEITORADO_PROJETO" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argumentos", [["coletar", "camara.ceap"], ["coletar", "camara.ceap", "--ate", "2025"]]
)
def test_coletar_por_competencia_sem_anos_e_erro_de_uso(deps, argumentos):
    assert _rodar(argumentos, deps) == 2
```

- [ ] **Passo 2: rodar e confirmar a falha**

Executar: `uv run pytest tests/test_cli.py -v`
Esperado: erro de coleta com `ModuleNotFoundError: No module named 'coletor.cli'`.

- [ ] **Passo 3: implementar**

`coletor/gcp.py`:

```python
"""Montagem das dependências reais (GCP e HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime

from coletor.armazenamento import GcsArmazenamento
from coletor.coleta import Dependencias
from coletor.config import Config
from coletor.http import ClienteHttp
from coletor.warehouse import BigQueryWarehouse


def agora_utc() -> datetime:
    return datetime.now(UTC)


def montar_dependencias(config: Config) -> Dependencias:
    import google.auth

    credenciais, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=config.projeto,
    )
    return Dependencias(
        config=config,
        http=ClienteHttp(),
        armazenamento=GcsArmazenamento(config.bucket, config.projeto, credenciais),
        warehouse=BigQueryWarehouse(config.projeto, config.regiao, credenciais),
        agora=agora_utc,
    )
```

`coletor/cli.py`:

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
from coletor.execucao import registro_execucao, rodar
from coletor.manifesto import ErroManifesto, Manifesto, carregar_manifesto
from coletor.meta import HistoricoColetas, RepositorioMeta

log = logging.getLogger("coletor")

Fabrica = Callable[[Config], Dependencias]


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
) -> int:
    execucao_id = str(uuid.uuid4())
    resumo = rodar(tarefas, historico, deps, repo, execucao_id, forcar)
    repo.registrar_execucao(
        registro_execucao(execucao_id, deps.config.origem, deps, inicio, resumo)
    )
    log.info("resumo: %s", resumo)
    return 0 if resumo.sucesso else 1


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
        uri = repo.buscar_arquivo_original(args.coleta_id)
        if uri is None:
            raise ErroUso(f"coleta {args.coleta_id} não encontrada")
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
        repo.preparar()
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

- [ ] **Passo 4: rodar e confirmar que passa**

Executar: `uv run pytest -v && uv run ruff check . && uv run ruff format --check .`
Esperado: `90 passed` e o lint limpo.

- [ ] **Passo 5: conferir o executável**

Executar: `uv run coletor --help`
Esperado: a ajuda lista os comandos `fontes`, `executar`, `coletar` e `recarregar`.

- [ ] **Passo 6: commit**

```bash
git add coletor/cli.py coletor/gcp.py tests/test_cli.py
git commit -m "feat(coletor): CLI com executar, coletar, recarregar e fontes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 11: infraestrutura base no GCP, junto com o usuário

Esta tarefa exige ações do usuário: login no navegador, escolha do id do projeto e da conta de faturamento. **Agente: não execute os passos marcados como "Usuário"; peça ao usuário e espere a confirmação.**

**Arquivos:**
- Criar: `infra/versions.tf`, `infra/variables.tf`, `infra/main.tf`, `infra/armazenamento.tf`
- Gerado e versionado: `infra/.terraform.lock.hcl`
- Local, fora do git: `.env`, `.env.prod`, `.gcloud/`

**Interfaces:**
- Consome: `scripts/ambiente.ps1` e `.env.exemplo` (Tarefa 1).
- Produz:
  - no projeto GCP: o bucket `<projeto>-dados` e os datasets `meta`, `raw_camara`, `raw_senado`, `raw_cgu`, `raw_ibge` e `replay`, mais as versões `_dev`;
  - localmente: os arquivos `.env` (dev) e `.env.prod` (prod).

- [ ] **Passo 1 (Usuário): instalar o Terraform**

No PowerShell:

```powershell
winget install --id Hashicorp.Terraform -e
```

Reabra o terminal e confira com `terraform version`. Esperado: `Terraform v1.9` ou mais recente.

- [ ] **Passo 2 (Usuário): criar os arquivos de ambiente e escolher o id do projeto**

O id precisa ter de 6 a 30 caracteres (minúsculas, números e hífens) e ser único no GCP. Exemplo: `eleitorado-dados-2026`.

```powershell
Copy-Item .env.exemplo .env
notepad .env
```

No `.env`:
- `ELEITORADO_PROJETO` recebe o id escolhido;
- `ELEITORADO_BUCKET` recebe `<id>-dados`;
- `ELEITORADO_AMBIENTE` fica `dev`;
- `CLOUDSDK_CONFIG` e `GOOGLE_APPLICATION_CREDENTIALS` só mudam se o repositório não estiver em `C:/git/eleitorado`.

Depois:

```powershell
Copy-Item .env .env.prod
(Get-Content .env.prod) -replace '^ELEITORADO_AMBIENTE=.*', 'ELEITORADO_AMBIENTE=prod' | Set-Content .env.prod
. .\scripts\ambiente.ps1
```

Esperado: `Ambiente dev carregado (projeto <id>)`.

- [ ] **Passo 3 (Usuário): login isolado, criação do projeto e faturamento**

Use a conta que tem o crédito mensal de desenvolvedor. Como `CLOUDSDK_CONFIG` aponta para `.gcloud/`, a configuração `prod` da máquina não é tocada.

No `billing projects link`, troque `ID_LISTADO_NO_COMANDO_ANTERIOR` pelo ID (formato `XXXXXX-XXXXXX-XXXXXX`) da conta de faturamento com o crédito, mostrado por `gcloud billing accounts list`.

```powershell
gcloud auth login
gcloud projects create $env:ELEITORADO_PROJETO --name="eleitorado"
gcloud billing accounts list
gcloud billing projects link $env:ELEITORADO_PROJETO --billing-account=ID_LISTADO_NO_COMANDO_ANTERIOR
gcloud config set project $env:ELEITORADO_PROJETO
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com storage.googleapis.com bigquery.googleapis.com
gcloud auth application-default login
gcloud auth application-default set-quota-project $env:ELEITORADO_PROJETO
gcloud storage buckets create "gs://$($env:ELEITORADO_PROJETO)-tfstate" --location=southamerica-east1 --uniform-bucket-level-access --public-access-prevention
```

Esperado:
- `gcloud config list` mostra o projeto novo e a conta correta;
- `Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS` retorna `True`;
- o bucket `-tfstate` foi criado.

- [ ] **Passo 4: escrever o Terraform**

`infra/versions.tf`:

```hcl
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }

  backend "gcs" {}
}
```

`infra/variables.tf`:

```hcl
variable "projeto" {
  description = "ID do projeto GCP dedicado ao eleitorado"
  type        = string
}

variable "regiao" {
  description = "Região de todos os recursos"
  type        = string
  default     = "southamerica-east1"
}
```

`infra/main.tf`:

```hcl
provider "google" {
  project               = var.projeto
  region                = var.regiao
  billing_project       = var.projeto
  user_project_override = true
}

resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
```

`infra/armazenamento.tf`:

```hcl
resource "google_storage_bucket" "dados" {
  name                        = "${var.projeto}-dados"
  location                    = var.regiao
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Originais nunca são apagados; depois de 30 dias vão para a classe mais barata.
  lifecycle_rule {
    condition {
      age                   = 30
      matches_prefix        = ["originais/", "dev/originais/"]
      matches_storage_class = ["STANDARD"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  # O Parquet de carga é descartável: pode ser refeito a partir do original.
  lifecycle_rule {
    condition {
      age            = 7
      matches_prefix = ["carga/", "dev/carga/"]
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

locals {
  datasets = ["meta", "raw_camara", "raw_senado", "raw_cgu", "raw_ibge", "replay"]
}

resource "google_bigquery_dataset" "prod" {
  for_each    = toset(local.datasets)
  dataset_id  = each.value
  location    = var.regiao
  description = "Eleitorado: ${each.value}"
  depends_on  = [google_project_service.apis]
}

resource "google_bigquery_dataset" "dev" {
  for_each                    = toset(local.datasets)
  dataset_id                  = "${each.value}_dev"
  location                    = var.regiao
  description                 = "Eleitorado (desenvolvimento): ${each.value}"
  default_table_expiration_ms = 2592000000 # 30 dias: dados de teste não se acumulam
  depends_on                  = [google_project_service.apis]
}

output "bucket_dados" {
  value = google_storage_bucket.dados.name
}
```

- [ ] **Passo 5 (Usuário, com o agente acompanhando a saída): validar e aplicar**

No PowerShell, com o ambiente carregado:

```powershell
terraform -chdir=infra fmt -check
terraform -chdir=infra init "-backend-config=bucket=$($env:ELEITORADO_PROJETO)-tfstate" "-backend-config=prefix=infra"
terraform -chdir=infra validate
terraform -chdir=infra plan "-var=projeto=$env:ELEITORADO_PROJETO"
terraform -chdir=infra apply "-var=projeto=$env:ELEITORADO_PROJETO"
```

Esperado:
- o `fmt` não lista arquivos;
- o `validate` responde `Success!`;
- o `plan` mostra 18 recursos a criar: 5 APIs, 1 bucket e 12 datasets;
- o `apply` termina com `Apply complete!` e mostra `bucket_dados = "<id>-dados"`.

- [ ] **Passo 6: verificar**

```powershell
bq ls --project_id=$env:ELEITORADO_PROJETO
gcloud storage buckets describe "gs://$env:ELEITORADO_BUCKET" --format="value(location,storage_class)"
```

Esperado: 12 datasets (`meta`, `meta_dev`, `raw_camara`, …, `replay_dev`) e `SOUTHAMERICA-EAST1  STANDARD`.

- [ ] **Passo 7: commit**

```bash
git add infra/versions.tf infra/variables.tf infra/main.tf infra/armazenamento.tf infra/.terraform.lock.hcl
git commit -m "feat(infra): bucket e datasets do BigQuery em southamerica-east1" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 12: testes de integração no ambiente dev

**Arquivos:**
- Criar: `tests/integracao/__init__.py` (vazio) e `tests/integracao/test_gcp.py`

**Interfaces:**
- Consome: `montar_dependencias` (Tarefa 10), `coletar` (Tarefa 9), `RepositorioMeta` (Tarefa 8), `csv_para_parquet`/`Controle` (Tarefa 5), a infraestrutura da Tarefa 11 e o `.env` com `ELEITORADO_AMBIENTE=dev`.
- Produz: a confirmação, contra o GCP real, de que o BigQuery aceita a carga, os decoradores de partição e a evolução de esquema. É o item 5 do Foco de revisão.

- [ ] **Passo 1: escrever os testes**

`tests/integracao/test_gcp.py`:

```python
"""Testes contra o GCP e as fontes reais. Rodar com: uv run --env-file .env pytest -m integracao"""

import uuid
from datetime import UTC, datetime

import pytest

from coletor.coleta import coletar
from coletor.competencias import data_brasilia
from coletor.config import Config, carregar_config
from coletor.conversao import Controle, csv_para_parquet
from coletor.gcp import montar_dependencias
from coletor.manifesto import Formato, carregar_manifesto
from coletor.meta import RepositorioMeta
from coletor.warehouse import Particionamento
from tests.amostras import RAIZ

pytestmark = pytest.mark.integracao


@pytest.fixture
def config_dev() -> Config:
    config = carregar_config()
    assert config.ambiente == "dev", "os testes de integração só rodam com ELEITORADO_AMBIENTE=dev"
    return config


def test_coleta_real_do_cnep_e_idempotente(config_dev):
    deps = montar_dependencias(config_dev)
    try:
        repo = RepositorioMeta(deps.warehouse, config_dev)
        repo.preparar()
        cnep = carregar_manifesto(RAIZ / "fontes").obter("cgu.cnep")
        historico = repo.carregar_historico()
        primeira = coletar(cnep, None, historico, deps, "integracao", forcar=True)
        repo.registrar_coleta(primeira)
        assert primeira.status == "carregada", primeira.erro
        assert primeira.linhas > 1000
        tabela = f"{config_dev.projeto}.{config_dev.dataset('raw_cgu')}.cnep"
        [contagem] = deps.warehouse.consultar(
            f"SELECT COUNT(*) AS n FROM `{tabela}` WHERE _coleta_id = '{primeira.coleta_id}'"
        )
        assert contagem["n"] == primeira.linhas
        historico.registrar(primeira)
        segunda = coletar(cnep, None, historico, deps, "integracao")
        repo.registrar_coleta(segunda)
        assert segunda.status == "sem_alteracao"
    finally:
        deps.http.fechar()


def test_coluna_nova_e_coluna_ausente_entre_cargas(config_dev, tmp_path):
    from google.cloud import bigquery

    deps = montar_dependencias(config_dev)
    tabela = f"{config_dev.dataset('raw_cgu')}.teste_evolucao_{uuid.uuid4().hex[:8]}"
    dia = data_brasilia(datetime.now(UTC))
    try:
        for indice, cabecalho in enumerate(["A;B", "A;C"]):
            csv = tmp_path / f"{indice}.csv"
            csv.write_text(f"{cabecalho}\n1;2\n", encoding="utf-8")
            parquet = tmp_path / f"{indice}.parquet"
            controle = Controle(
                f"teste-{indice}", dia.isoformat(), dia, "gs://teste", datetime.now(UTC)
            )
            csv_para_parquet(csv, parquet, Formato(tipo="csv"), controle)
            uri = deps.armazenamento.enviar(parquet, f"dev/carga/teste/{uuid.uuid4()}.parquet")
            linhas = deps.warehouse.carregar_parquet(tabela, uri, Particionamento("DAY"), dia)
            assert linhas == 1
        resultado = deps.warehouse.consultar(f"SELECT a, b, c FROM `{config_dev.projeto}.{tabela}`")
        assert resultado == [{"a": "1", "b": None, "c": "2"}]
    finally:
        bigquery.Client(project=config_dev.projeto).delete_table(
            f"{config_dev.projeto}.{tabela}", not_found_ok=True
        )
        deps.http.fechar()
```

- [ ] **Passo 2: confirmar que os testes de integração ficam fora da suíte padrão**

Executar: `uv run pytest`
Esperado: `90 passed, 2 deselected`.

- [ ] **Passo 3: rodar contra o GCP em dev**

Executar: `uv run --env-file .env pytest -m integracao -v`
Esperado: `2 passed`. Se `test_coluna_nova_e_coluna_ausente_entre_cargas` falhar porque o BigQuery recusou a coluna ausente, há duas saídas:
- ajustar `BigQueryWarehouse.carregar_parquet` para incluir no Parquet as colunas já existentes, como nulas;
- ou registrar a limitação no README e tratar a ausência como falha de coleta.

Em qualquer dos casos, decida com o usuário antes de seguir.

- [ ] **Passo 4: conferir o que ficou no dev**

```bash
set -a; source .env; set +a
bq query --use_legacy_sql=false --format=pretty "SELECT recurso, status, linhas, esquema_alterado FROM \`${ELEITORADO_PROJETO}.meta_dev.coletas\` ORDER BY iniciada_em DESC LIMIT 5"
```

Esperado: duas linhas de `cnep`, uma `carregada` e uma `sem_alteracao`.

- [ ] **Passo 5: commit**

```bash
git add tests/integracao/
git commit -m "test(coletor): integração com GCS e BigQuery no ambiente dev" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarefa 13: carga histórica em produção, verificação e README

**Confirme com o usuário antes do Passo 1.** Esta tarefa grava em produção e baixa algumas centenas de MB das fontes.

**Arquivos:**
- Criar: `README.md`

**Interfaces:**
- Consome: a CLI (Tarefa 10), o `.env.prod` e a infraestrutura (Tarefa 11).
- Produz: o raw completo da onda A em produção e o `meta` preenchido. O Plano 2 parte desse estado.

- [ ] **Passo 1: rodar a carga completa em produção**

Use um terminal sem as variáveis de dev carregadas, porque variáveis já definidas na sessão podem prevalecer sobre o arquivo.

Executar: `uv run --env-file .env.prod coletor executar`

Esperado:
- a primeira linha do log mostra `ambiente=prod projeto=<id>`. Se mostrar `dev`, interrompa e abra um terminal novo;
- o log informa 43 tarefas pendentes: 19 anos da CEAP, 19 anos da CEAPS e 5 snapshots;
- cada linha termina com `status=carregada`;
- o resumo final traz `falhas=0`;
- o código de saída é 0;
- duração de alguns minutos, sendo uns 55 s só para a lista de deputados (cerca de 50 páginas).

- [ ] **Passo 2: conferir o controle de coletas**

```bash
set -a; source .env.prod; set +a
bq query --use_legacy_sql=false --format=pretty "SELECT CONCAT(orgao, '.', recurso) AS recurso, status, COUNT(*) AS coletas, SUM(linhas) AS linhas FROM \`${ELEITORADO_PROJETO}.meta.coletas\` GROUP BY 1, 2 ORDER BY 1, 2"
```

Esperado, sem nenhuma linha com `falha`:

| recurso | coletas | linhas |
|---|---|---|
| `camara.ceap` | 19 | — |
| `camara.deputados` | 1 | cerca de 4,8 mil |
| `senado.ceaps` | 19 | — |
| `senado.senadores` | 1 | 681 |
| `cgu.ceis` | 1 | cerca de 23,7 mil |
| `cgu.cnep` | 1 | cerca de 1,8 mil |
| `ibge.municipios` | 1 | 5.571 |

Valores observados em 03/10/2026.

- [ ] **Passo 3: conferir o raw da CEAP**

```bash
bq query --use_legacy_sql=false --format=pretty "SELECT _competencia, COUNT(*) AS linhas FROM \`${ELEITORADO_PROJETO}.raw_camara.ceap\` GROUP BY 1 ORDER BY 1"
```

Esperado: 19 linhas, de 2008 a 2026. A competência 2008 tem 445 linhas e a de 2025, cerca de 209 mil.

- [ ] **Passo 4: conferir a idempotência**

```bash
uv run --env-file .env.prod coletor executar
uv run --env-file .env.prod coletor coletar camara.ceap --competencia 2015
uv run --env-file .env.prod coletor fontes
```

Esperado:
- o primeiro comando informa `0 tarefa(s) pendente(s)` e sai com código 0;
- o segundo termina com `status=sem_alteracao`;
- o terceiro lista os 7 recursos com a data de hoje.

- [ ] **Passo 5: conferir os originais no GCS**

```bash
gcloud storage ls "gs://${ELEITORADO_BUCKET}/originais/camara/ceap/"
```

Esperado: 19 prefixos, de `competencia=2008/` a `competencia=2026/`.

- [ ] **Passo 6: escrever o README**

`README.md`:

````markdown
# eleitorado

Repositório de dados públicos dos portais de transparência no BigQuery, para monitorar o
governo e as ações públicas. Desenho em `docs/superpowers/specs/`; planos em
`docs/superpowers/plans/`.

## Coletor (onda A)

Fontes declaradas em `fontes/*.yaml`: deputados e CEAP (Câmara), senadores e CEAPS (Senado),
CEIS e CNEP (CGU), municípios (IBGE). Cada coleta guarda o original no GCS
(`originais/…`), carrega o raw no BigQuery (`raw_<órgão>`) e registra tudo em `meta.coletas`.

### Configuração local

1. `uv sync`
2. Copie `.env.exemplo` para `.env` (dev) e `.env.prod` (prod) e ajuste o projeto e o bucket.
   O gcloud deste projeto fica isolado em `.gcloud/` (variável `CLOUDSDK_CONFIG`) e não altera
   outras configurações da máquina.
3. No PowerShell, `. .\scripts\ambiente.ps1` carrega o `.env` para usar `gcloud`, `bq` e
   `terraform`.

### Comandos

```bash
uv run --env-file .env coletor fontes                      # recursos e última coleta
uv run --env-file .env coletor executar                    # coleta o que está vencido
uv run --env-file .env coletor coletar camara.ceap --de 2020
uv run --env-file .env coletor recarregar cgu.ceis --competencia 2026-10-02 --destino replay
```

Use `.env.prod` no lugar de `.env` para gravar em produção, num terminal sem as variáveis de dev
carregadas. A primeira linha do log mostra o ambiente e o projeto em uso.

### Testes

```bash
uv run pytest                                     # unitários
uv run --env-file .env pytest -m integracao       # contra o GCP, só em dev
```

### Infraestrutura

`infra/` (Terraform): bucket `<projeto>-dados` e datasets em `southamerica-east1`.

```powershell
terraform -chdir=infra init "-backend-config=bucket=$($env:ELEITORADO_PROJETO)-tfstate" "-backend-config=prefix=infra"
terraform -chdir=infra apply "-var=projeto=$env:ELEITORADO_PROJETO"
```

### Até a coleta agendada (Plano 2)

A CGU só publica o arquivo do dia do CEIS e do CNEP. Até o job diário existir, rode
`uv run --env-file .env.prod coletor executar` uma vez por dia para não perder dias do
histórico de sanções.
````

- [ ] **Passo 7: commit**

```bash
git add README.md
git commit -m "docs: README do coletor e da infraestrutura base" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Depois deste plano

- **Plano 2, operação na nuvem:**
  - comando `coletor pipeline` (coleta + `dbt build` + `meta.execucoes`, com esqueleto dbt);
  - Dockerfile e Artifact Registry;
  - Cloud Run Job e Cloud Scheduler às 07:30;
  - contas de serviço com permissão mínima;
  - Workload Identity Federation;
  - workflows `ci.yml`, `deploy.yml` e `vigia.yml`;
  - orçamento, cota diária do BigQuery e `maximum_bytes_billed`;
  - dataset `ci`.
- **Plano 3, modelagem dbt:**
  - datasets `staging`, `intermediate` e `marts`;
  - staging, intermediate (com os históricos SCD2) e marts;
  - alertas e `monitor_fontes`;
  - os testes da seção 7.7 da spec.
