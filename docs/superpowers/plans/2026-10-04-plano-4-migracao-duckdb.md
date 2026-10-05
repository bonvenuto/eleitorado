# Plano 4: migração para DuckDB e paralelo

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** tirar o pipeline do BigQuery e do Cloud Run e rodá-lo no GitHub Actions com DuckDB. O raw e o `meta` passam a ser Parquet num lago local, espelhado no bucket privado. Os marts e a linhagem são publicados no Cloudflare R2. Durante uma semana, o pipeline novo roda em paralelo com o atual e é reconciliado com o BigQuery todos os dias.

**Arquitetura:** o coletor mantém a lógica de coleta. A interface `Warehouse` ganha uma implementação sobre Parquet local (`LagoWarehouse`), e entram três módulos:
- `estado.py`: sincroniza o lago com o GCS e restaura os históricos;
- `publicacao.py`: envia marts e linhagem ao R2;
- `reconciliacao.py`: compara os marts do DuckDB com os do BigQuery.

O projeto dbt passa a usar o adaptador DuckDB. As fontes são Parquet externos, os marts são materializados como Parquet (`external`) e o CI roda o dbt sobre um "lago vazio" gerado a partir de esquemas em texto. Um workflow `pipeline.yml` diário substitui o Cloud Run Job e o vigia.

**Stack:** Python 3.12, uv, DuckDB 1.5, dbt-core 1.12 + dbt-duckdb 1.11, google-cloud-storage, boto3 (R2 pela API do S3), Terraform, GitHub Actions (`actions/cache`, `google-github-actions/auth@v2`).

**Spec:** [docs/superpowers/specs/2026-10-04-migracao-duckdb-design.md](../specs/2026-10-04-migracao-duckdb-design.md), seções 4 a 7, 8.1 e 8.2. A virada e a limpeza (seção 8.3) são o Plano 5.

**Ponto de partida:** `main` em `2acac63` (Plano 3 em produção no BigQuery). Este plano roda em `feat/migracao-duckdb`, que já tem a spec.

**Código-fonte: branch local `proto/duckdb` (commit `75b7cfc`).** O código de todas as tarefas foi escrito e validado num protótipo, e cada tarefa traz os arquivos de lá com `git checkout proto/duckdb -- <arquivo>`. Essa branch existe só neste repositório local, não está no GitHub, e não deve ser apagada até o fim deste plano. Validação do protótipo:
- **Dados reais:** o lago foi montado a partir de uma exportação do BigQuery (`bq extract`) e rodou o `dbt build` completo, com 19 modelos, 52 testes de dados e 9 unitários passando.
- **Reconciliação:** `coletor reconciliar` contra o BigQuery de produção, sem nenhuma divergência.
- **Pipeline e reconstrução:** `coletor pipeline` rodou de ponta a ponta sobre o lago. `coletor reconstruir` leu os originais reais do bucket e refez os 25.562 eventos de sanções e os 2.495 de parlamentares.
- **Lago vazio:** o fluxo do CI passou, com `dbt run` em 21 modelos e `dbt test` em 61 testes.
- **pytest:** 136 testes passando.

## Restrições globais

- **Dados no Brasil:** o bucket privado é o atual (`dados-publicos-prd-dados`, `southamerica-east1`). O que é público vai para o R2 (`eleitorado-publico`), só marts e linhagem.
- **LGPD:**
  - CPF completo só no lago privado (raw, intermediate);
  - nos marts, todo CPF sai mascarado, e o teste `sem_cpf_completo` continua em todos eles;
  - `coletor publicar` só aceita arquivos sob `marts/` e `linhagem/`.
- **Paralelo:**
  - o pipeline novo grava tudo sob o prefixo `paralelo/` (`ELEITORADO_PREFIXO=paralelo/`) e **só lê** os `originais/` da raiz;
  - o Cloud Run Job atual não é tocado: continua na imagem `2acac63`, e o `deploy.yml` sai neste plano.
- **Credenciais:**
  - GCP por WIF, com a conta `pipeline` e só a partir de `refs/heads/main`;
  - R2 por token restrito ao bucket público, nos secrets do GitHub;
  - nenhum segredo no git, e o executor nunca pede nem recebe valores de segredos: quem os grava é o usuário, com `gh secret set`.
- **Comandos locais:** `uv run --env-file .env ...`. O `.env` local é de dev: tudo no bucket fica sob `dev/`.
- **Antes de cada commit:** `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest` passando.
- **Commits:** mensagens em português, terminadas com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (e `Co-Authored-By: Gemini <noreply@google.com>` quando for o caso).
- **Ações que exigem o ok do usuário, a cada vez:** `terraform apply`, push, criação e merge de PR e disparo do workflow em produção.

## Foco de revisão

1. **Lago local vazio ou incompleto depois de uma restauração que falhou.** O `estado salvar` não pode apagar o bucket. Ele monta o plano inteiro antes de alterar qualquer coisa e recusa remover mais de 50% dos objetos de uma pasta. Teste `test_salvar_recusa_apagar_quase_tudo` (Tarefa 3).
2. **Arquivo fora de `marts/` e `linhagem/` no diretório público** (por exemplo, um Parquet do raw com CPF). Nada é publicado. Teste `test_arquivo_fora_dos_caminhos_permitidos_impede_a_publicacao` (Tarefa 4).
3. **Cache do Actions com uma versão antiga de um arquivo que mudou no bucket.** O `estado restaurar` compara tamanho e MD5 e baixa a versão do bucket. Teste `test_restaurar_baixa_so_o_que_falta_ou_mudou` (Tarefa 3).
4. **Original corrompido na reconstrução.** O dbt não roda, e os históricos atuais ficam intactos. Teste `test_reconstruir_com_original_ilegivel_nao_roda_o_dbt` (Tarefa 5).
5. **Snapshot carregado já vencido (mais de 60 dias).** A carga devolve as linhas antes da expiração apagar a partição. Teste `test_snapshot_expira_depois_do_prazo_e_competencia_nao` (Tarefa 2).

Sem teste automatizado, para o revisor conferir no `pipeline.yml` (Tarefa 6): se o `dbt build` falhar, o estado é salvo mesmo assim (`always()`), mas nada é publicado.

## Decisões de implementação que refinam a spec

- **O `.duckdb` não vai para o cache.** A spec previa guardar o arquivo de trabalho no cache. Como os históricos são restaurados de `estado/historicos/*.parquet` a cada execução e o resto é recalculado, o banco é recriado do zero a cada vez. O cache guarda só `dados/raw`, `dados/meta` e `dados/estado`.
- **Exclusão reversível do bucket (30 dias) no lugar da cópia diária dos históricos e do sufixo `.substituido-<data>`.** Toda versão sobrescrita ou apagada fica recuperável por 30 dias, sem código a mais. Configurado no Terraform (`soft_delete_policy`).
- **A expiração dos snapshots (60 dias) fica no código (`LagoWarehouse`), não numa regra de ciclo de vida.** O lago local e o bucket precisam ter os mesmos arquivos. O `estado salvar` apaga do bucket o que expirou no lago.
- **`stg_meta__coletas` e `stg_meta__fontes`.** O `monitor_fontes` passa a ler deles com `ref`, porque os testes unitários do dbt não aceitam um source externo (Parquet) como entrada.
- **Alerta de fornecedor sancionado com chave de correspondência** (`cpf:<doc>` ou `cnpj:<raiz>`) em vez de join com `OR`. No DuckDB, o `OR` virava um laço aninhado de minutos; com a chave, leva 3 s. É o achado I4 da revisão do Plano 3.
- **CI sem credenciais.** O dbt roda sobre `dbt/tests/lago_vazio`, Parquets sem linhas gerados de `esquemas.json`, e o job `dbt-unitarios` com a conta `ci-github` sai. No CI, `dbt run` e depois `dbt test`, porque o teste unitário do incremental precisa da tabela já criada.
- **O `vigia.yml` sai neste plano.** O comando `coletor vigia` deixa de existir. Durante o paralelo, se o Cloud Run antigo falhar, os marts do BigQuery ficam desatualizados e a reconciliação diária do workflow novo falha, o que gera e-mail.
- **`recarregar` sai da CLI**, e o `reconstruir` faz o papel dele. A função `recarregar` continua em `coleta.py`, usada pelo `reconstruir`.
- **Ids das despesas da Câmara mudam**, porque o hash da linha é calculado de outro jeito no DuckDB. Ainda não há consumidores. A reconciliação compara campos naturais, não ids.

## Estrutura de arquivos

```
pyproject.toml, uv.lock                 - dbt-bigquery, google-cloud-bigquery; + duckdb, dbt-duckdb, boto3;
                                         grupo opcional `migracao` (google-cloud-bigquery, até o Plano 5)
.gitignore, .env.exemplo                + dados/, *.duckdb, Parquets do lago vazio; ELEITORADO_LAGO/PUBLICO
coletor/config.py                       + lago, publico, prefixo (ELEITORADO_PREFIXO); - dataset()
coletor/lago.py                         NOVO: LagoWarehouse (raw e meta em Parquet; consultas no DuckDB)
coletor/warehouse.py                    REMOVIDO (BigQueryWarehouse)
coletor/armazenamento.py                + Objeto, listar_objetos, substituir, apagar; - caminho_carga
coletor/estado.py                       NOVO: restaurar, salvar, carregar/exportar históricos
coletor/publicacao.py                   NOVO: publicar no R2 (lista permitida, manifesto por último)
coletor/reconciliacao.py                NOVO (temporário): marts DuckDB x BigQuery
coletor/meta.py, coleta.py, gcp.py      tabelas como caminhos do lago; carga direto no lago
coletor/dbt.py                          + publico, argumentos, gerar_linhagem, banco_do_target
coletor/cli.py                          + estado, publicar, reconstruir, reconciliar; - vigia, recarregar
dbt/**                                  adaptador DuckDB (profiles, macros, sources externos, marts external)
dbt/tests/lago_vazio/esquemas.json      NOVO: esquema de cada fonte (sem dados)
scripts/lago_vazio.py                   NOVO: gera o lago vazio (e atualiza os esquemas a partir de um lago)
tests/**                                fakes e testes adaptados; + test_lago, test_estado, test_publicacao,
                                         test_reconciliacao, test_reconstruir
.github/workflows/ci.yml                dbt sobre o lago vazio; - jobs imagem e dbt-unitarios
.github/workflows/pipeline.yml          NOVO: pipeline diário
.github/workflows/deploy.yml, vigia.yml REMOVIDOS
infra/armazenamento.tf, execucao.tf, github.tf   soft delete, prefixos de estado, WIF da conta pipeline
README.md                               operação nova e configuração do R2
```

Em todas as tarefas, "traga do protótipo" significa:

```bash
git checkout proto/duckdb -- <arquivo> [<arquivo> ...]
```

Para conferir que um arquivo ficou igual ao do protótipo: `git diff --exit-code proto/duckdb -- <arquivo>`, que deve sair sem diferença.

---

### Tarefa 1: dependências e projeto dbt em DuckDB

**Arquivos:**
- Do protótipo: `pyproject.toml`, `uv.lock`, `.gitignore`, todo o diretório `dbt/` (exceto `dbt/.user.yml`), `scripts/lago_vazio.py` e `tests/test_dbt_projeto.py`.

**Interfaces:**
- Produz:
  - `dbt/profiles.yml` com os targets `dev`, `prod` e `ci`, todos `type: duckdb`. O `path` é `${ELEITORADO_LAGO:-dados}/{dev,eleitorado,ci}.duckdb`, e o `external_root` é `${ELEITORADO_PUBLICO:-dados/publico}/marts`;
  - sources externos lendo `${ELEITORADO_LAGO}/raw/<órgão>/<recurso>/*/*.parquet` e `.../meta/{coletas,fontes}/*/*.parquet`;
  - os marts em Parquet: `<publico>/marts/<mart>.parquet`, e o fato da cota particionado por `casa`/`ano`;
  - `scripts/lago_vazio.py`, que gera os Parquets de `dbt/tests/lago_vazio/<tabela>/vazio/vazio.parquet` a partir de `esquemas.json`.

- [ ] **Passo 1: teste dos schemas no DuckDB (falha primeiro)**

Traga do protótipo `tests/test_dbt_projeto.py`. Rode: `uv run pytest tests/test_dbt_projeto.py -q`
Esperado: FAIL. Com o projeto ainda em BigQuery, os schemas de dev saem com o prefixo `dev_local_`, e o tipo dos targets é `bigquery`.

- [ ] **Passo 2: dependências e projeto dbt**

```bash
git checkout proto/duckdb -- pyproject.toml uv.lock .gitignore dbt scripts/lago_vazio.py
uv sync
```

Rode: `uv run pytest tests/test_dbt_projeto.py -q`
Esperado: `4 passed`.

- [ ] **Passo 3: o dbt inteiro sobre o lago vazio (o mesmo fluxo do CI)**

PowerShell:

```powershell
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"; $env:ELEITORADO_PUBLICO = "$env:TEMP/eleitorado-publico"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO/marts" | Out-Null
uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
Remove-Item Env:ELEITORADO_LAGO, Env:ELEITORADO_PUBLICO
```

Esperado: `dbt run` com `Done. PASS=21 ... ERROR=0` e `dbt test` com `Done. PASS=61 ... ERROR=0`. São 52 testes de dados, todos sobre tabelas vazias, e os 9 unitários.

Confira que nenhum Parquet nem `.duckdb` aparece para commit: `git status --short dbt` deve listar só arquivos `.sql`, `.yml` e o `esquemas.json`.

- [ ] **Passo 4: suíte e commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
git add pyproject.toml uv.lock .gitignore dbt scripts/lago_vazio.py tests/test_dbt_projeto.py
git commit -m "feat(dbt): projeto em DuckDB, fontes em Parquet e lago vazio do CI"
```

Esperado no pytest: todos passando. Os testes do coletor ainda usam o `warehouse.py` antigo com dublês, sem BigQuery de verdade.

---

### Tarefa 2: lago em Parquet (`LagoWarehouse`)

**Arquivos:** do protótipo, `coletor/lago.py` e `tests/test_lago.py`.

**Interfaces:**
- Produz `coletor.lago` com:
  - `Coluna(nome, tipo, modo)`;
  - `Particionamento(granularidade: "DAY"|"YEAR", expiracao_dias)` e `.decorador(dia)`;
  - `Carga(linhas: int, caminho: str)`;
  - o protocolo `Warehouse`;
  - `LagoWarehouse(raiz: Path, hoje: date | None = None)`.
- Métodos do `LagoWarehouse`:
  - `carregar_parquet(tabela, origem: Path, particionamento, dia, coleta_id) -> Carga` substitui a partição e expira os snapshots vencidos;
  - `garantir_tabela(tabela, colunas)`;
  - `anexar_linhas(tabela, linhas, colunas)` grava um arquivo por chamada em `<tabela>/<AAAA-MM-DD>/<uuid>.parquet`;
  - `substituir_linhas(tabela, linhas, colunas)` grava `<tabela>/atual/dados.parquet`;
  - `consultar(sql) -> list[dict]`: cada tabela registrada vira uma view com o último segmento do nome (`meta/coletas` vira `coletas`).

- [ ] **Passo 1:** traga `tests/test_lago.py`. Rode `uv run pytest tests/test_lago.py -q`.
Esperado: erro de importação, `No module named 'coletor.lago'`.
- [ ] **Passo 2:** traga `coletor/lago.py`. Rode de novo.
Esperado: `7 passed`. Entre eles está `test_snapshot_expira_depois_do_prazo_e_competencia_nao` (Foco de revisão 5).
- [ ] **Passo 3:** commit: `feat(coletor): lago local em Parquet com consultas no DuckDB`.

---

### Tarefa 3: estado espelhado no bucket

**Arquivos:**
- Do protótipo: `coletor/estado.py` e `tests/test_estado.py`.
- Modificar:
  - `coletor/armazenamento.py`: acrescenta `Objeto` e os três métodos novos e mantém `caminho_carga`, que ainda é usado por `coleta.py`. A versão final entra na Tarefa 5;
  - `tests/fakes.py`: só a classe `FakeArmazenamento`. A versão final também entra na Tarefa 5.

**Interfaces:**
- Consome `Armazenamento` (GCS).
- Produz em `coletor.armazenamento`:
  - `Objeto(tamanho: int, md5: str)`;
  - os métodos `listar_objetos(prefixo) -> dict[str, Objeto]`, `substituir(origem, caminho)` e `apagar(caminho)` no protocolo e no `GcsArmazenamento`.
- Produz em `coletor.estado`:
  - `HISTORICOS`, `Resumo`, `ErroSincronia` e `md5_arquivo(caminho) -> str`;
  - `restaurar(armazenamento, prefixo, lago, banco) -> Resumo`;
  - `salvar(armazenamento, prefixo, lago, banco) -> Resumo`;
  - `carregar_historicos(pasta, banco) -> list[str]`;
  - `exportar_historicos(banco, pasta) -> list[str]`.

- [ ] **Passo 1:** traga `tests/test_estado.py`. Rode `uv run pytest tests/test_estado.py -q`.
Esperado: erro de importação, `cannot import name 'estado'`.
- [ ] **Passo 2:** traga `coletor/estado.py`. Em `coletor/armazenamento.py`, acrescente `import base64` e `from dataclasses import dataclass` aos imports e, antes de `class Armazenamento(Protocol):`, a classe:

```python
@dataclass(frozen=True)
class Objeto:
    tamanho: int
    md5: str  # hexadecimal
```

No protocolo `Armazenamento`, depois de `listar`:

```python
    def listar_objetos(self, prefixo: str) -> dict[str, Objeto]:
        """Objetos sob `prefixo`, pelo caminho completo."""
        ...

    def substituir(self, origem: Path, caminho: str) -> None:
        """Grava sobrescrevendo (só para o estado espelhado: raw/, meta/, estado/)."""
        ...

    def apagar(self, caminho: str) -> None: ...
```

No fim de `GcsArmazenamento`:

```python
    def listar_objetos(self, prefixo: str) -> dict[str, Objeto]:
        return {
            blob.name: Objeto(int(blob.size), base64.b64decode(blob.md5_hash).hex())
            for blob in self._cliente.list_blobs(self._bucket, prefix=prefixo)
        }

    def substituir(self, origem: Path, caminho: str) -> None:
        self._bucket.blob(caminho).upload_from_filename(str(origem))

    def apagar(self, caminho: str) -> None:
        self._bucket.blob(caminho).delete()
```

Em `tests/fakes.py`, acrescente ao `FakeArmazenamento`, depois do método `listar`, os três métodos abaixo e os imports correspondentes no topo do arquivo:

```python
from coletor.armazenamento import Objeto
from coletor.estado import md5_arquivo
```

```python
    def listar_objetos(self, prefixo: str) -> dict[str, Objeto]:
        return {
            caminho: Objeto(arquivo.stat().st_size, md5_arquivo(arquivo))
            for caminho, arquivo in self.objetos.items()
            if caminho.startswith(prefixo)
        }

    def substituir(self, origem: Path, caminho: str) -> None:
        destino = self.raiz / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        self.objetos[caminho] = destino

    def apagar(self, caminho: str) -> None:
        self.objetos.pop(caminho).unlink()
```

Rode `uv run pytest tests/test_estado.py -q`.
Esperado: `6 passed`, incluindo `test_salvar_recusa_apagar_quase_tudo` e `test_restaurar_baixa_so_o_que_falta_ou_mudou` (Foco de revisão 1 e 3).

- [ ] **Passo 3:** `uv run pytest -q` (tudo verde) e commit de `coletor/armazenamento.py`, `coletor/estado.py`, `tests/test_estado.py` e `tests/fakes.py`: `feat(coletor): estado do lago espelhado no bucket privado`.

---

### Tarefa 4: publicação no R2 e reconciliação

**Arquivos:** do protótipo, `coletor/publicacao.py`, `coletor/reconciliacao.py`, `tests/test_publicacao.py` e `tests/test_reconciliacao.py`.

**Interfaces:**
- Produz em `coletor.publicacao`:
  - `PERMITIDOS = ("marts/", "linhagem/")`, `ErroPublicacao` e o protocolo `Publicador` (`listar`, `enviar(origem, chave, tipo)`, `apagar`);
  - `publicar(publicador, publico, gerado_em, versao) -> ResumoPublicacao`;
  - `R2Publicador(conta, chave_id, segredo, bucket)`.
- Produz em `coletor.reconciliacao`:
  - `COMPARACOES` e `Divergencia(nome, so_no_bigquery, so_no_duckdb)`;
  - `reconciliar(consultar_bigquery, consultar_duckdb) -> list[Divergencia]`;
  - `consulta_duckdb(publico)` e `consulta_bigquery(projeto, credenciais)`.

- [ ] **Passo 1:** traga os dois testes. Rode `uv run pytest tests/test_publicacao.py tests/test_reconciliacao.py -q`.
Esperado: erros de importação.
- [ ] **Passo 2:** traga os dois módulos. Rode de novo.
Esperado: `8 passed`, incluindo `test_arquivo_fora_dos_caminhos_permitidos_impede_a_publicacao` (Foco de revisão 2).
- [ ] **Passo 3:** commit: `feat(coletor): publicação no R2 e reconciliação com o BigQuery`.

---

### Tarefa 5: coletor no lago, CLI nova e reconstrução

**Arquivos:**
- Do protótipo:
  - `coletor/config.py`, `coletor/armazenamento.py`, `coletor/meta.py`, `coletor/coleta.py`, `coletor/gcp.py`, `coletor/dbt.py`, `coletor/cli.py` e `.env.exemplo`;
  - `tests/fakes.py`, `tests/test_config.py`, `tests/test_cli.py`, `tests/test_coleta.py`, `tests/test_meta.py`, `tests/test_pipeline.py`, `tests/test_armazenamento.py`, `tests/test_dbt.py`, `tests/test_reconstruir.py` e `tests/integracao/test_gcp.py`.
- Remover: `coletor/warehouse.py`.

**Interfaces:**
- Consome as Tarefas 2 a 4.
- Produz:
  - `Config.lago: Path` (`ELEITORADO_LAGO`, padrão `dados`), `Config.publico: Path` (`ELEITORADO_PUBLICO`, padrão `dados/publico`) e `Config.prefixo: str` (`ELEITORADO_PREFIXO`, padrão vazio, que precisa terminar com `/`). `Config.prefixo_gcs` passa a ser `prefixo + ("dev/" se ambiente == "dev")`, e `Config.dataset()` sai;
  - `armazenamento`: sai `caminho_carga`, já que a carga não passa mais pelo GCS;
  - `RepositorioMeta(warehouse)`, com as tabelas `meta/coletas`, `meta/execucoes` e `meta/fontes`. O `SQL_HISTORICO` passa a ler `coletas`. Saem `execucao_agendada_com_sucesso` e `buscar_coleta`;
  - `coleta.tabela_destino(recurso, destino)`, que devolve `raw/<órgão>/<recurso>` ou `replay/raw/<órgão>/<recurso>`. O `arquivo_carga` passa a ser o caminho no lago;
  - `dbt.rodar_dbt(diretorio, target, publico, argumentos=(), executar=...)`, que cria `<publico>/marts` e usa `--exclude-resource-type unit_test`;
  - `dbt.gerar_linhagem(diretorio, target, publico)` e `dbt.banco_do_target(lago, target)`;
  - na CLI:
    - `--dbt-dir` e `--target` passam a ser opções globais, antes do subcomando;
    - os subcomandos são `fontes`, `executar`, `coletar`, `pipeline`, `estado restaurar|salvar`, `publicar`, `reconstruir [--origem-prefixo P]` e `reconciliar`;
    - `publicar` lê `R2_CONTA`, `R2_CHAVE_ID`, `R2_SEGREDO` e `R2_BUCKET`.

- [ ] **Passo 1: testes primeiro.** Traga todos os arquivos de `tests/` listados acima. Rode `uv run pytest -q`.
Esperado: falhas de importação e de assinatura, porque `tests/fakes.py` importa `coletor.lago.Carga` e os testes usam a CLI nova.
- [ ] **Passo 2: implementação.**

```bash
git checkout proto/duckdb -- coletor/config.py coletor/armazenamento.py coletor/meta.py coletor/coleta.py coletor/gcp.py coletor/dbt.py coletor/cli.py .env.exemplo
git rm coletor/warehouse.py
```

Rode `uv run pytest -q`.
Esperado: `136 passed, 2 deselected`. Os dois de integração ficam de fora por padrão.

- [ ] **Passo 3: conferência com o protótipo.** Rode `git diff --exit-code proto/duckdb -- coletor tests .env.exemplo`.
Esperado: sem diferença.
- [ ] **Passo 4: integração com o GCS (dev).** Rode `uv run --env-file .env pytest -m integracao -q`.
Esperado: `2 passed`. O CNEP é coletado de verdade num lago temporário, e o estado vai a `dev/teste-estado-<pid>/` e volta. O teste apaga o que criou.
- [ ] **Passo 5:** commit: `feat(coletor): coleta no lago, CLI de estado, publicação e reconstrução`.

---

### Tarefa 6: workflows, Terraform e documentação

**Arquivos:**
- Do protótipo: `.github/workflows/ci.yml`, `.github/workflows/pipeline.yml`, `infra/armazenamento.tf`, `infra/execucao.tf`, `infra/github.tf` e `README.md`.
- Remover: `.github/workflows/deploy.yml` e `.github/workflows/vigia.yml`.

- [ ] **Passo 1: trazer e remover.**

```bash
git checkout proto/duckdb -- .github/workflows/ci.yml .github/workflows/pipeline.yml infra/armazenamento.tf infra/execucao.tf infra/github.tf README.md
git rm .github/workflows/deploy.yml .github/workflows/vigia.yml
```

- [ ] **Passo 2: revisar o `pipeline.yml`** contra a spec, seção 3. A ordem dos passos deve ser:
  1. cache;
  2. `estado restaurar`;
  3. `pipeline`;
  4. `reconstruir`, só com o input marcado;
  5. `estado salvar` e gravação do cache, com `always()` e restauração bem-sucedida;
  6. `publicar`;
  7. `reconciliar`.

  O `concurrency` é `pipeline`, sem cancelar a execução em andamento, e o `ELEITORADO_PREFIXO` é `paralelo/`.

- [ ] **Passo 3: Terraform (plano).** No PowerShell, com `. .\scripts\ambiente.ps1` carregado:

```powershell
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
terraform -chdir=infra plan "-var=projeto=$env:ELEITORADO_PROJETO" "-var=conta_faturamento=01A56D-15D9DD-C83237" -out plano4.tfplan
```

Esperado: `Plan: 2 to add, 1 to change, 0 to destroy.`
- adicionados: `google_service_account_iam_member.pipeline_wif` e `google_storage_bucket_iam_member.pipeline_espelha_estado`;
- alterado: `google_storage_bucket.dados`, com a exclusão reversível de 7 para 30 dias e `paralelo/originais/` no arquivamento;
- nas saídas, o novo `sa_pipeline`.

Se o plano for diferente, **pare e relate**. Se aparecer "Error acquiring the state lock" por causa de um plano interrompido, mostre o ID e peça ao usuário para liberar com `terraform force-unlock`.

**Pare e peça o ok do usuário.** Com o ok: `terraform -chdir=infra apply plano4.tfplan`, depois apague `infra/plano4.tfplan`.

- [ ] **Passo 4:** suíte (`ruff` e `pytest`) e commit: `feat(infra): pipeline no GitHub Actions, estado espelhado e publicação no R2`.

---

### Tarefa 7: configuração do R2 e do GitHub (usuário) e primeira carga

Esta tarefa é feita com o usuário. O executor só roda os comandos que não envolvem segredos.

- [ ] **Passo 1: R2 (usuário, painel da Cloudflare).** Siga a seção "Cloudflare R2 (configuração única)" do README:
  1. crie o bucket `eleitorado-publico`;
  2. ative o acesso público por `r2.dev` e anote a URL pública;
  3. crie um token com "Object Read & Write" só nesse bucket.
- [ ] **Passo 2: segredos e variáveis do GitHub.** O usuário roda, no próprio terminal, `gh secret set R2_CONTA`, `gh secret set R2_CHAVE_ID` e `gh secret set R2_SEGREDO` (cada um pede o valor sem ecoar). O executor roda:

```bash
gh variable set R2_BUCKET --body eleitorado-publico
gh variable set GCP_SA_PIPELINE --body "$(terraform -chdir=infra output -raw sa_pipeline)"
gh variable list
```

Esperado: `GCP_PROJETO`, `GCP_WIF_PROVIDER`, `GCP_SA_PIPELINE` e `R2_BUCKET` listadas. `gh secret list` deve mostrar os três `R2_*`.

- [ ] **Passo 3: PR, CI e merge (com o ok do usuário).**

```bash
git push -u origin feat/migracao-duckdb
gh pr create --base main --title "Plano 4: migração para DuckDB (paralelo)" --body-file <resumo>
gh pr checks --watch
```

Esperado: o job `testes` verde, com ruff, pytest e o dbt sobre o lago vazio. Depois do merge, o `deploy.yml` não existe mais e o Cloud Run segue na imagem `2acac63`.

- [ ] **Passo 4: primeira carga (com o ok do usuário).**

```bash
gh workflow run pipeline.yml -f reconstruir=true
gh run watch --exit-status $(gh run list --workflow pipeline.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

Esperado:
- todos os passos verdes, incluindo `reconciliar` com "reconciliação sem divergências";
- a primeira execução coleta todas as competências de novo a partir das fontes, porque o `paralelo/meta` está vazio. Leva de 20 a 40 minutos;
- no GCS existem `paralelo/raw/`, `paralelo/meta/` e `paralelo/estado/historicos/`;
- no R2, `curl -s <URL r2.dev>/manifesto.json` devolve o manifesto com os 9 marts e `linhagem/index.html`.

Se a reconciliação divergir porque o Cloud Run e o Actions coletaram arquivos de dias diferentes, anote e rode de novo no dia seguinte. A tolerância não muda (spec, seção 8.2).

- [ ] **Passo 5: acompanhamento.** O workflow roda sozinho todo dia às 07:30. O critério de virada (spec, seção 8.3) é de 7 execuções seguidas sem divergência, com pelo menos uma coleta semanal de deputados e senadores. Cumprido o critério, vem o Plano 5 (virada e limpeza).

## Depois deste plano

- **Plano 5:** virada para o prefixo vazio e reconstrução na raiz; remoção do Cloud Run, Scheduler, Artifact Registry, BigQuery, contas `deployer` e `ci-github`, `Dockerfile`, `coletor reconciliar` e grupo `migracao`; limpeza de `paralelo/`.
- **Domínio próprio na Cloudflare:** pré-requisito da web app, que terá a sua própria spec.
- A branch local `proto/duckdb` e a worktree do protótipo podem ser apagadas depois do merge deste plano.
