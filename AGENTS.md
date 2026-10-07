# Instruções para agentes de código

Este arquivo vale para qualquer agente que trabalhe neste repositório (Codex, Claude Code,
Gemini). O que fazer a seguir está em [docs/roteiro.md](docs/roteiro.md); o desenho de cada parte,
em `docs/superpowers/specs/`; os planos já executados, em `docs/superpowers/plans/`; os dados
publicados, em [docs/modelos-de-dados.md](docs/modelos-de-dados.md).

## O projeto

Coleta dados públicos oficiais (Câmara, Senado, CGU/Portal da Transparência, PNCP, IBGE, Receita
Federal), modela com dbt sobre DuckDB e publica marts em Parquet no Cloudflare R2, para monitorar o
governo e achar inconsistências. O repositório é **público**.

- `coletor/`: CLI `coletor` (Python 3.12, uv). Fontes declaradas em `fontes/*.yaml`; adaptadores em
  `coletor/adaptadores/` (`arquivo`, `api_json`, `api_detalhe`, `webdav_zip`). Cada coleta arquiva
  o original no bucket privado do GCS, grava o raw em Parquet no lago local
  (`dados/raw/<órgão>/<recurso>/<partição>/`) e registra em `dados/meta/`.
- `dbt/`: staging (views), intermediate (tabelas, privadas) e marts (Parquet externo, públicos).
  Targets: `prod`, `dev`, `ci` (lago vazio de `dbt/tests/lago_vazio`) e `agente`.
- `agente/`: agente investigador L1 (controlador Python + sessões `claude -p` com servidor MCP
  próprio). Recomenda; não decide nem age. Relatórios só para uso interno.
- `.github/workflows/`: `pipeline.yml` (diário: coleta do grupo `diario`, dbt build, publica),
  `receita.yml` (segundas: base do CNPJ da Receita, grupo `receita`, não publica), `ci.yml`.
- `infra/`: Terraform (bucket, conta de serviço `pipeline` com WIF, orçamento).

## Regras que não se negociam

- **Nunca commitar nem dar push na `main`.** Ela é protegida: só entra por PR com o check `testes`
  verde. Trabalhe num branch (`feat/...`, `fix/...`, `docs/...`).
- **Não fazer sem o ok explícito do usuário, a cada vez:** merge de PR, disparar workflow
  (`gh workflow run`), `terraform apply`, apagar objetos no bucket ou branches remotos, mudar
  secrets, settings ou rulesets do GitHub. O usuário roda o `terraform apply`.
- **Segredos:** nunca no git (`.env*`, `.gcloud/`, chaves). Nunca peça nem receba valores de
  secrets; o usuário os define com `gh secret set`. Não altere a configuração `prod` do gcloud da
  máquina nem as credenciais globais: este projeto usa `CLOUDSDK_CONFIG=.gcloud`.
- **LGPD:**
  - CPF completo nunca vai para um mart público (só a máscara `***.456.789-**`). Todo mart novo
    leva o teste `sem_cpf_completo`; marts com dados cadastrais também `sem_dados_pessoais`
    (endereço, contato, sócio pessoa física).
  - Sócios, endereços, contatos e CPF completo ficam só no lago privado (`raw`, `staging`,
    `intermediate`).
  - Nunca vão para o git: `dados/`, `dados-*/`, `investigacoes/`, `avaliacao/`,
    `.claude/settings.local.json`.
- **Hosts:** o coletor só acessa `.gov.br` e `.leg.br` (`SUFIXOS_OFICIAIS` em `coletor/http.py`).
  Fonte nova fora disso precisa de decisão do usuário.
- **Ações do GitHub fixadas por SHA**, com a versão em comentário (`# v4.4.0`).

## Como trabalhamos

1. **Spec** em `docs/superpowers/specs/AAAA-MM-DD-<tema>-design.md`, aprovada pelo usuário.
2. **Protótipo** com dados reais antes do plano (medir volumes, tempos e quantos casos cada regra
   gera; ajustar a spec).
3. **Plano** em `docs/superpowers/plans/`, com tarefas pequenas, testes primeiro e uma **prova de
   mutação** por tarefa (estragar a regra de propósito e ver o teste falhar).
4. **PR** com CI verde; o usuário faz o merge.

Antes de declarar algo pronto, rode e leia a saída de:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

E o dbt inteiro sobre o lago vazio, como o CI (PowerShell):

```powershell
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"; $env:ELEITORADO_PUBLICO = "$env:TEMP\publico-ci"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO\marts" | Out-Null
uv run dbt build --project-dir dbt --profiles-dir dbt --target ci
```

## Convenções

- Código, comentários, docs, commits e PRs em **português**. Linhas de até 100 colunas (`ruff`).
- Commits no estilo `feat(coletor): ...`, `fix(dbt): ...`, `docs: ...`, `ci: ...`.
- Fonte nova: recurso em `fontes/<órgão>.yaml` (validado por `coletor/manifesto.py`), fonte no
  `dbt/models/staging/fontes.yml`, esquema em `dbt/tests/lago_vazio/esquemas.json` (gere com
  `uv run python scripts/lago_vazio.py --de-lago <lago real>`) e documentação em
  `docs/modelos-de-dados.md`.
- Alerta novo: `marts/alerta_<tema>.sql` com `alerta_id` estável (MD5 da regra e das chaves),
  coluna `regra`, exclusão dos registros marcados com problema de qualidade (`valor_suspeito`,
  `data_emissao_valida = false`), testes `unique`/`not_null` no `alerta_id`, `sem_cpf_completo` e
  um teste unitário do dbt com as bordas da regra.
- Documento (CPF/CNPJ): use as macros de `dbt/macros/documentos.sql` (CNPJ pode ser alfanumérico
  desde 07/2026; compare empresas pela raiz de 8 posições).
- Testes do coletor sem rede: `respx` para HTTP, dublês em `tests/fakes.py`, amostras em
  `tests/amostras.py`. Testes que acessam GCP e fontes reais levam `@pytest.mark.integracao`.

## Operação: o que já se sabe

- **Pipeline diário** (`pipeline.yml`, 10:30 UTC, mas o GitHub costuma atrasar; limite de 120 min):
  saída **3** = só coletas falharam e o dbt passou, então os marts são publicados mesmo assim (o
  job fica vermelho de propósito).
- **Lago no cache do Actions** sempre cifrado com GPG (secret `LAGO_CHAVE`): workflows de PR,
  inclusive de forks, conseguem ler caches da `main`.
- **Estado:** o lago local espelha `raw/`, `meta/` e `estado/` do bucket
  (`coletor estado restaurar|salvar`); o `.duckdb` é descartável. Os históricos por eventos
  (sanções, parlamentares) são o único estado que não se recalcula do raw.
- **CI:** às vezes um PR não dispara o check `testes`; feche e reabra o PR.
- **Fonte com defeito conhecido:** o ZIP de licitações da CGU de 2018-12 vem truncado na própria
  fonte e falha todo dia (ver o roteiro).
- **Receita:** a base mensal tem 7,6 GB; o adaptador `webdav_zip` recorta em fluxo só as raízes de
  CNPJ que aparecem nos dados (`<lago>/rfb_raizes_interesse.parquet`, gerado pelo dbt).
- **Windows:** o desenvolvimento local é em Windows (PowerShell e Git Bash). Use caminhos com `/`
  ou caminhos Windows; caminhos `/c/...` quebram em subprocessos Python.
