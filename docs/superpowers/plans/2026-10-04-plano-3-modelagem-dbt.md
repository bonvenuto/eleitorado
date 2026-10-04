# Plano 3: modelagem dbt

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** transformar o raw já em produção em marts prontos para a web app. São quatro grupos:
- dimensões de UF, município e parlamentar;
- fatos da cota parlamentar (Câmara e Senado) e das sanções (CEIS e CNEP), com histórico;
- dois alertas de inconsistência;
- um monitor das fontes.

Tudo testado e rodando no `dbt build` diário do job `pipeline`.

**Arquitetura:** o dbt organiza o trabalho em três camadas:
- **staging (views):** tipa e normaliza cada recurso do raw, expondo todas as datas de referência dos snapshots;
- **intermediate:** unifica Câmara e Senado e guarda o histórico das sanções e dos parlamentares como eventos (`inclusao`, `alteracao`, `exclusao`) em modelos incrementais;
- **marts:** derivam o SCD2 (`valido_de`/`valido_ate`) dos eventos, mascaram CPF e aplicam as regras dos alertas.

O CI cria as relações vazias no dataset `ci` (`dbt run --empty`) e roda os testes unitários do dbt.

**Stack:** dbt-core 1.12 e dbt-bigquery 1.12 (já no `pyproject.toml`), BigQuery GoogleSQL, Terraform (provider google ≥ 6), GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-10-03-ingestao-onda-a-design.md](../specs/2026-10-03-ingestao-onda-a-design.md), seções 7.1 a 7.7. A seção 7.1 já foi coberta em parte pelo Plano 2.

**Ponto de partida:** `main` em `8fccf30`, com coletor e operação em produção e o raw carregado. Este plano roda em `feat/plano-3-modelagem-dbt`.

**Protótipo:** todo o código abaixo foi construído e testado contra os dados reais de produção no target `dev`, antes da escrita do plano:
- `dbt build` completo: 19 modelos, 52 testes de dados e 4 testes unitários passando;
- os testes unitários `despesa_documentos_especiais_e_uf` e `monitor_sem_alteracao_conta_como_sucesso`, os `relationships` de UF, o `accepted_values` de `tipo_pessoa`, o `_coleta_id` de `dim_uf` e o `sem_cpf_completo` do fato da cota, depois da última mudança, foram escritos quando a cota diária do BigQuery já tinha esgotado; eles rodam pela primeira vez na execução deste plano;
- prova de mutação nos testes unitários do alerta e do incremental: ambos falham quando a regra é removida.

Os números citados nos passos (5.571 municípios, 27 UFs, cerca de 5,6 milhões de despesas e de 25,6 mil sanções) são os de 2026-10-04.

## Restrições globais

- **Região e projeto:** `southamerica-east1`, projeto `dados-publicos-prd`. Raw e meta são sempre os de produção, inclusive em dev (seção 5.3 da spec).
- **Schemas:**
  - `prod`: `staging`, `intermediate` e `marts`;
  - `dev`: `dev_<ELEITORADO_USUARIO_DBT>_<schema>`;
  - `ci`: tudo no dataset `ci`.
- **LGPD:** CPF completo só em raw, staging e intermediate. Nos marts, todo CPF sai como `***.456.789-**`, inclusive dentro de texto livre, como a razão social de MEI. O teste `sem_cpf_completo` roda em todos os marts.
- **Custo:**
  - `maximum_bytes_billed` de 10 GiB por consulta (já no profile);
  - cota de 30 GiB por dia no projeto;
  - o `dbt build` completo processa cerca de 7,7 GiB.

  Em dev, prefira `--select` com o modelo da tarefa a reconstruir tudo. Reconstruções repetidas esgotam a cota do dia, e a consulta seguinte falha com `Custom quota exceeded`.
- **Comandos dbt locais:** sempre `uv run --env-file .env dbt <comando> --project-dir dbt --profiles-dir dbt --target dev ...`. Abaixo isso é abreviado como `DBT <comando> ...`.
- **Antes de cada commit:** `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest` passando.
- **Commits:** mensagens em português, terminadas com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Escritas em produção:** `terraform apply`, merge e execução do job só com o ok explícito do usuário, a cada vez.

## Foco de revisão

1. **CPF dentro de texto livre.** A razão social de MEI traz o CPF ("FULANO 12345678909"): são 9.859 despesas e 110 sanções. Esses CPFs têm de sair mascarados nos marts. Cobertura:
   - `mascarar_cpfs_em_texto` (Tarefa 1, teste `documentos_macros`);
   - `sem_cpf_completo` em todos os marts (Tarefa 5).
2. **Pseudodocumentos tratados como inválidos.** A Câmara usa `000000000000NN` para serviços internos e fornecedores estrangeiros (833 mil linhas), e o Senado publica CPFs já mascarados. Nenhum dos dois pode virar alerta de documento inválido nem raiz de CNPJ `00000000`. O CNPJ real `00000000000191`, do Banco do Brasil, continua CNPJ. Teste unitário `despesa_documentos_especiais_e_uf` (Tarefa 4).
3. **Reprocessar ou pular dias no histórico.** Rodar o incremental de novo não gera eventos duplicados. Uma chave excluída que reaparece volta como `inclusao`. Testes `eventos_de_snapshots_carga_inicial` e `eventos_de_snapshots_incremental` (Tarefa 3), mais a nova execução sem eventos na verificação da Tarefa 3.
4. **Sanção vencida, filial e exclusão no alerta.** Despesa fora da vigência não gera alerta. Filial gera com `cnpj_raiz`. Versão de exclusão não conta. Teste `alerta_sancionado_por_documento_raiz_e_vigencia` (Tarefa 6).
5. **Fonte sem dado novo não é fonte atrasada.** `sem_alteracao` conta como sucesso, e uma falha posterior não apaga o último sucesso. Teste `monitor_sem_alteracao_conta_como_sucesso` (Tarefa 7).

## Decisões de implementação que refinam a spec

- **Histórico guardado como eventos (`int_*__eventos`), com o SCD2 derivado no mart.** A spec fala em `int_cgu__sancoes_historico` com `valido_de`/`valido_ate`. Com eventos, o incremental só insere linhas (merge por `evento_id`) e nunca precisa reabrir uma versão para fechar o `valido_ate`. `fct_sancao_historico` calcula `valido_ate` com `LEAD`. O resultado para quem consome é o mesmo SCD2 da spec.
- **O staging de snapshots expõe todas as datas de referência**, não só a mais recente. O histórico e o replay precisam de todas. Quem quer o cadastro atual filtra a data mais recente: `fct_sancao`, `dim_parlamentar` e o join de UF do Senado.
- **Tipos de documento em maiúsculas, com dois tipos extras:** `CPF`, `CNPJ`, `INVALIDO`, `CPF_MASCARADO` (Senado) e `CODIGO_CAMARA` (`000000000000NN`). Com os dois extras, o alerta de documento inválido cai de 842 mil para 73 linhas.
- **`mascarar_cpfs_em_texto` em nomes e textos livres dos marts.** A spec diz que "nomes seguem como publicados", mas isso contradiz a regra de não ter CPF completo nos marts quando o nome traz o CPF. A LGPD prevalece. O teste `sem_cpf_completo` exclui só as colunas `*_id` e as listadas explicitamente, como número de nota e número de processo, que têm 11 dígitos sem ser CPF.
- **Macros de documento testadas por um teste singular** (`documentos_macros`), e não por dbt unit tests. Os unit tests do dbt testam modelos, não macros.
- **UF `NA` da Câmara vira nula.** As lideranças vêm com `NA`, que não é uma UF.
- **Sem `dbt_utils`.** Nenhum modelo precisa dele, e o pacote exigiria `dbt deps` no CI e na imagem.
- **Reconciliação contra o staging.** O staging da cota é uma view sem filtro sobre o raw, então reconciliar contra ele é reconciliar contra o raw.
- **A conta `ci-github` passa a ler os datasets `raw_*`.** O `dbt run --empty` cria as views do staging no dataset `ci`, e o BigQuery valida a consulta da view. Os dados lidos são zero linhas. O raw tem CPFs, mas só os que as próprias fontes já publicam.
- **Testes de atraso (aviso e erro) no `dbt build` de produção.** Um recurso acima do limite de erro faz o `dbt build` falhar. A execução termina como `falha`, e o vigia avisa por e-mail.

## Estrutura de arquivos

```
dbt/dbt_project.yml                      camadas, schemas e materializações
dbt/macros/generate_schema_name.sql      ci: tudo no dataset ci
dbt/macros/conversoes.sql                texto, numero_br, data_br
dbt/macros/documentos.sql                normalizar, tipo, validar, mascarar, cnpj_raiz
dbt/macros/fonte_snapshot.sql            raw ou replay (var fonte_historico)
dbt/macros/eventos_de_snapshots.sql      eventos inclusão/alteração/exclusão
dbt/models/staging/fontes.yml            sources raw_*, meta e replay
dbt/models/staging/stg_*.sql             6 modelos (views)
dbt/models/intermediate/historico.yml    testes dos eventos
dbt/models/intermediate/cota.yml         testes da cota unificada
dbt/models/intermediate/int_*.sql        4 modelos
dbt/models/marts/marts.yml               dimensões e fatos
dbt/models/marts/alertas.yml             alertas
dbt/models/marts/monitor_fontes.yml      monitor
dbt/models/marts/*.sql                   9 modelos
dbt/tests/generic/sem_cpf_completo.sql   teste genérico de LGPD
dbt/tests/*.sql                          macros, reconciliação, atraso
tests/test_dbt_projeto.py                + schema do target ci
infra/armazenamento.tf                   + datasets staging/intermediate/marts
infra/execucao.tf                        + pipeline edita os datasets do dbt
infra/github.tf                          + ci-github lê os raw_*
.github/workflows/ci.yml                 + job dbt-unitarios
.gitignore, .env.exemplo, README.md
```

---

### Tarefa 1: fundação do projeto dbt e macros de documento

**Arquivos:**
- Modificar: `dbt/dbt_project.yml`, `dbt/macros/generate_schema_name.sql`, `tests/test_dbt_projeto.py`, `.gitignore`, `.env.exemplo`
- Criar: `dbt/macros/conversoes.sql`, `dbt/macros/documentos.sql`, `dbt/tests/documentos_macros.sql`

**Interfaces:**
- Produz:
  - macros `texto(coluna)`, `numero_br(coluna)` e `data_br(coluna)`;
  - `normalizar_documento(coluna)`, que devolve STRING ou nulo;
  - `tipo_documento(doc)`: `'CPF'`, `'CNPJ'`, `'INVALIDO'` ou nulo;
  - `documento_valido(doc)`: BOOL ou nulo;
  - `mascarar_cpf(doc)`, `documento_publico(doc)`, `cnpj_raiz(doc)` e `mascarar_cpfs_em_texto(coluna)`.

  Todas as macros recebem expressões SQL como texto.

- [ ] **Passo 1: teste do schema do target `ci` (falha primeiro)**

Em `tests/test_dbt_projeto.py`, filtre os dois modelos de teste em `_schemas`, porque o projeto real passa a ter modelos, e acrescente o teste do `ci`:

```python
    linhas = [json.loads(linha) for linha in saida.stdout.splitlines() if linha.startswith("{")]
    return {
        linha["name"]: linha["schema"]
        for linha in linhas
        if linha["name"] in ("com_schema", "sem_schema")
    }
```

```python
def test_schemas_em_ci_ficam_todos_no_dataset_do_ci(projeto):
    assert _schemas(projeto, "ci") == {"com_schema": "ci", "sem_schema": "ci"}
```

Rode: `uv run pytest tests/test_dbt_projeto.py -v`
Esperado: FAIL em `test_schemas_em_ci_ficam_todos_no_dataset_do_ci`, porque hoje o `com_schema` resolve para `ci_staging`.

- [ ] **Passo 2: macro de schema e camadas do projeto**

`dbt/macros/generate_schema_name.sql`:

```sql
{#- prod: o schema configurado (staging, intermediate, marts);
    dev: <dataset do target>_<schema>;
    ci: tudo no dataset do target, porque a conta do CI só grava no dataset ci -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none or target.name == 'ci' -%}
        {{ target.schema }}
    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

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

models:
  eleitorado:
    staging:
      +schema: staging
      +materialized: view
    intermediate:
      +schema: intermediate
      +materialized: table
    marts:
      +schema: marts
      +materialized: table

flags:
  send_anonymous_usage_stats: false
```

Rode: `uv run pytest tests/test_dbt_projeto.py -v`
Esperado: 3 passed.

- [ ] **Passo 3: `.gitignore` e `.env.exemplo`**

No `.gitignore`, troque o comentário `# dbt (planos seguintes)` por `# dbt` e acrescente `dbt/.user.yml` ao bloco. No `.env.exemplo`, acrescente:

```
# sufixo dos datasets de desenvolvimento do dbt (dev_<usuario>_staging, ...)
ELEITORADO_USUARIO_DBT=seu_usuario
```

Copie a linha para o seu `.env` com o seu usuário.

- [ ] **Passo 4: teste das macros de documento (falha primeiro)**

`dbt/tests/documentos_macros.sql`:

```sql
-- Casos conhecidos das macros de documento (CPF, CNPJ numérico e alfanumérico).
with casos as (
    select * from unnest([
        struct('111.444.777-35' as entrada, 'CPF' as tipo, true as valido),
        struct('11144477734', 'CPF', false),
        struct('00000000000', 'CPF', false),
        struct('11.222.333/0001-81', 'CNPJ', true),
        struct('11222333000180', 'CNPJ', false),
        struct('12.ABC.345/01DE-35', 'CNPJ', true),
        struct('12abc34501de35', 'CNPJ', true),
        struct('1234567890123', 'INVALIDO', false),
        -- pontuação fora do lugar não importa: só os caracteres contam
        struct('071.414.740/0010-0', 'CNPJ', true),
        struct(cast(null as string), cast(null as string), cast(null as bool))
    ])
),

calculados as (
    select
        entrada, tipo, valido,
        {{ normalizar_documento('entrada') }} as documento
    from casos
)

select *
from (
    select
        *,
        {{ tipo_documento('documento') }} as tipo_obtido,
        {{ documento_valido('documento') }} as valido_obtido,
        {{ documento_publico('documento') }} as publico_obtido,
        {{ mascarar_cpfs_em_texto("concat('JOSE DA SILVA ', coalesce(entrada, ''))") }} as texto_obtido
    from calculados
)
where tipo_obtido is distinct from tipo
    or valido_obtido is distinct from valido
    or (tipo = 'CPF' and publico_obtido != concat('***.', substr(documento, 4, 3), '.', substr(documento, 7, 3), '-**'))
    or (tipo = 'CPF' and texto_obtido != concat('JOSE DA SILVA ', publico_obtido))
    or (tipo = 'CNPJ' and texto_obtido != concat('JOSE DA SILVA ', entrada))
```

Rode: `DBT test --select documentos_macros`
Esperado: erro de compilação, `'normalizar_documento' is undefined`.

- [ ] **Passo 5: macros**

`dbt/macros/conversoes.sql`:

```sql
{#- Texto do raw para tipos. Cada fonte tem seu formato (seção 7.3 da spec). -#}

{% macro texto(coluna) -%}
nullif(trim({{ coluna }}), '')
{%- endmacro %}

{#- CGU: vírgula decimal e ponto de milhar ("1.234,56") -#}
{% macro numero_br(coluna) -%}
safe_cast(replace(replace({{ texto(coluna) }}, '.', ''), ',', '.') as numeric)
{%- endmacro %}

{#- CGU: "dd/mm/aaaa" -#}
{% macro data_br(coluna) -%}
safe.parse_date('%d/%m/%Y', {{ texto(coluna) }})
{%- endmacro %}
```

`dbt/macros/documentos.sql`:

```sql
{#- Documentos (CPF e CNPJ). Desde 31/07/2026 o CNPJ pode ser alfanumérico: 12 posições com
    dígitos ou letras maiúsculas e 2 dígitos verificadores, calculados por módulo 11 com cada
    caractere valendo seu código ASCII menos 48. -#}

{% macro normalizar_documento(coluna) -%}
nullif(upper(regexp_replace(coalesce({{ coluna }}, ''), r'[^0-9A-Za-z]', '')), '')
{%- endmacro %}

{% macro tipo_documento(doc) -%}
case
    when {{ doc }} is null then null
    when regexp_contains({{ doc }}, r'^[0-9]{11}$') then 'CPF'
    when regexp_contains({{ doc }}, r'^[0-9A-Z]{12}[0-9]{2}$') then 'CNPJ'
    else 'INVALIDO'
end
{%- endmacro %}

{#- dígito verificador por módulo 11: resto < 2 vale 0, senão 11 - resto -#}
{% macro _dv_mod11(doc, pesos) -%}
(
    select if(mod(sum((ascii(substr({{ doc }}, posicao + 1, 1)) - 48) * peso), 11) < 2, 0,
              11 - mod(sum((ascii(substr({{ doc }}, posicao + 1, 1)) - 48) * peso), 11))
    from unnest({{ pesos }}) as peso with offset as posicao
)
{%- endmacro %}

{% macro documento_valido(doc) -%}
case {{ tipo_documento(doc) }}
    when 'CPF' then
        {{ doc }} != repeat(substr({{ doc }}, 1, 1), 11)
        and {{ _dv_mod11(doc, '[10, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 10, 1) as int64)
        and {{ _dv_mod11(doc, '[11, 10, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 11, 1) as int64)
    when 'CNPJ' then
        {{ _dv_mod11(doc, '[5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 13, 1) as int64)
        and {{ _dv_mod11(doc, '[6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 14, 1) as int64)
    when 'INVALIDO' then false
end
{%- endmacro %}

{% macro mascarar_cpf(doc) -%}
concat('***.', substr({{ doc }}, 4, 3), '.', substr({{ doc }}, 7, 3), '-**')
{%- endmacro %}

{#- documento que pode ir para os marts: CPF sempre mascarado -#}
{% macro documento_publico(doc) -%}
if({{ tipo_documento(doc) }} = 'CPF', {{ mascarar_cpf(doc) }}, {{ doc }})
{%- endmacro %}

{% macro cnpj_raiz(doc) -%}
if({{ tipo_documento(doc) }} = 'CNPJ', substr({{ doc }}, 1, 8), null)
{%- endmacro %}

{#- CPF dentro de texto livre (razão social de MEI traz "NOME 12345678909"): mascara qualquer
    sequência de 11 dígitos isolada, com ou sem pontuação, válida ou não. Aplicada duas vezes
    porque o RE2 não sobrepõe ocorrências que dividem o separador. -#}
{% macro mascarar_cpfs_em_texto(coluna) -%}
regexp_replace(
    regexp_replace(
        {{ coluna }},
        r'(^|[^0-9])[0-9]{3}\.?([0-9]{3})\.?([0-9]{3})-?[0-9]{2}([^0-9]|$)', r'\1***.\2.\3-**\4'
    ),
    r'(^|[^0-9])[0-9]{3}\.?([0-9]{3})\.?([0-9]{3})-?[0-9]{2}([^0-9]|$)', r'\1***.\2.\3-**\4'
)
{%- endmacro %}
```

Rode: `DBT test --select documentos_macros`
Esperado: `PASS=1`. O CNPJ `12.ABC.345/01DE-35` é o exemplo oficial da Receita para o CNPJ alfanumérico.

- [ ] **Passo 6: commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
git add .gitignore .env.exemplo dbt/dbt_project.yml dbt/macros tests/test_dbt_projeto.py dbt/tests/documentos_macros.sql
git commit -m "feat(dbt): camadas, schema do ci e macros de documento"
```

---

### Tarefa 2: sources e staging

**Arquivos:**
- Criar: `dbt/macros/fonte_snapshot.sql`, `dbt/models/staging/fontes.yml` e seis modelos `stg_*.sql`
- Remover: `dbt/models/.gitkeep`

**Interfaces:**
- Consome: as macros da Tarefa 1.
- Produz, com uma linha por registro publicado e todas as datas de referência nos snapshots:
  - `stg_camara__ceap`: colunas tipadas, mais `hash_linha`, `_competencia`, `_linha` e `cpf_parlamentar`;
  - `stg_camara__deputados`: `id_deputado`, `legislatura` e `data_referencia`;
  - `stg_senado__senadores`: `id_senador`, `uf_sigla`, `legislaturas` e `data_referencia`;
  - `stg_senado__ceaps`: `fornecedor_documento` e `fornecedor_documento_mascarado`;
  - `stg_cgu__sancoes`: `sancao_id`, `cadastro`, `documento`, `data_referencia` e `hash_atributos`;
  - `stg_ibge__municipios`: só o snapshot mais recente, porque o IBGE não tem histórico.
- Macro `fonte_snapshot(orgao, recurso)`.

- [ ] **Passo 1: sources**

`dbt/models/staging/fontes.yml`:

```yaml
version: 2

# O raw e o meta são sempre os de produção, também em dev (seção 5.3 da spec).
sources:
  - name: raw_camara
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: raw_camara
    tables:
      - name: ceap
      - name: deputados
  - name: raw_senado
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: raw_senado
    tables:
      - name: ceaps
      - name: senadores
  - name: raw_cgu
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: raw_cgu
    tables:
      - name: ceis
      - name: cnep
  - name: raw_ibge
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: raw_ibge
    tables:
      - name: municipios
  # snapshots recarregados dos originais para reconstruir os históricos (seção 7.4)
  - name: replay
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: replay
    tables:
      - name: cgu__ceis
      - name: cgu__cnep
      - name: camara__deputados
      - name: senado__senadores
  - name: meta
    database: "{{ env_var('ELEITORADO_PROJETO') }}"
    schema: meta
    tables:
      - name: coletas
      - name: fontes
```

`dbt/macros/fonte_snapshot.sql`:

```sql
{#- Snapshot de onde partem os históricos: o raw (padrão) ou, numa reconstrução completa
    (`--full-refresh --vars '{fonte_historico: replay}'`), o dataset `replay`, carregado antes
    com `coletor recarregar --destino replay` a partir dos originais (seção 7.4 da spec). -#}
{% macro fonte_snapshot(orgao, recurso) -%}
{%- set fonte = var('fonte_historico', 'raw') -%}
{%- if fonte == 'replay' -%}
{{ source('replay', orgao ~ '__' ~ recurso) }}
{%- elif fonte == 'raw' -%}
{{ source('raw_' ~ orgao, recurso) }}
{%- else -%}
{{ exceptions.raise_compiler_error("fonte_historico deve ser raw ou replay, não " ~ fonte) }}
{%- endif -%}
{%- endmacro %}
```

- [ ] **Passo 2: o replay troca a origem, e um valor errado é recusado (falha primeiro)**

Rode:
```bash
DBT compile --select stg_cgu__sancoes --vars "{fonte_historico: replay}"
```
Esperado: erro, porque o modelo ainda não existe (`does not match any enabled nodes`).

- [ ] **Passo 3: modelos de staging**

`dbt/models/staging/stg_camara__ceap.sql`:

```sql
-- CEAP da Câmara: uma linha por linha publicada. Decimal com ponto e datas ISO.
with origem as (
    select * from {{ source('raw_camara', 'ceap') }}
)

select
    _coleta_id,
    _competencia,
    _linha,
    {{ texto('txnomeparlamentar') }} as nome_beneficiario,
    {{ texto('cpf') }} as cpf_parlamentar,
    {{ texto('idecadastro') }} as id_deputado,
    {{ texto('sguf') }} as uf_sigla,
    {{ texto('sgpartido') }} as partido_sigla,
    {{ texto('txtdescricao') }} as categoria,
    {{ texto('txtdescricaoespecificacao') }} as subcategoria,
    {{ texto('txtfornecedor') }} as fornecedor_nome,
    {{ normalizar_documento('txtcnpjcpf') }} as fornecedor_documento,
    {{ texto('txtnumero') }} as numero_documento,
    safe_cast(substr({{ texto('datemissao') }}, 1, 10) as date) as data_emissao,
    safe_cast({{ texto('vlrdocumento') }} as numeric) as valor_documento,
    safe_cast({{ texto('vlrglosa') }} as numeric) as valor_glosa,
    safe_cast({{ texto('vlrliquido') }} as numeric) as valor_reembolsado,
    safe_cast({{ texto('nummes') }} as int64) as mes,
    safe_cast({{ texto('numano') }} as int64) as ano,
    {{ texto('txtpassageiro') }} as passageiro,
    {{ texto('txttrecho') }} as trecho,
    {{ texto('idedocumento') }} as id_documento_origem,
    {{ texto('urldocumento') }} as url_documento,
    -- conteúdo publicado da linha, sem as colunas de controle
    to_hex(md5(to_json_string((
        select as struct origem.* except (
            _coleta_id, _competencia, _competencia_data, _linha, _arquivo_original, _carregado_em
        )
    )))) as hash_linha
from origem
```

`dbt/models/staging/stg_camara__deputados.sql`:

```sql
-- Deputados por legislatura, em todas as datas de referência do raw (ou do replay).
with origem as (
    select * from {{ fonte_snapshot('camara', 'deputados') }}
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_value(payload, '$.id') as id_deputado,
    json_value(payload, '$.nome') as nome,
    json_value(payload, '$.siglaPartido') as partido_sigla,
    json_value(payload, '$.siglaUf') as uf_sigla,
    safe_cast(json_value(payload, '$.idLegislatura') as int64) as legislatura,
    json_value(payload, '$.urlFoto') as url_foto
from origem
```

`dbt/models/staging/stg_senado__senadores.sql`:

```sql
-- Senadores com mandato da 53ª legislatura em diante, em todas as datas de referência.
-- `Mandatos.Mandato` vem como lista ou, quando há um só mandato, como objeto.
with origem as (
    select * from {{ fonte_snapshot('senado', 'senadores') }}
),

com_mandatos as (
    select
        *,
        if(
            starts_with(trim(json_query(payload, '$.Mandatos.Mandato')), '['),
            json_query_array(payload, '$.Mandatos.Mandato'),
            [json_query(payload, '$.Mandatos.Mandato')]
        ) as mandatos
    from origem
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_value(payload, '$.IdentificacaoParlamentar.CodigoParlamentar') as id_senador,
    json_value(payload, '$.IdentificacaoParlamentar.NomeParlamentar') as nome,
    json_value(payload, '$.IdentificacaoParlamentar.NomeCompletoParlamentar') as nome_completo,
    json_value(payload, '$.IdentificacaoParlamentar.SexoParlamentar') as sexo,
    json_value(payload, '$.IdentificacaoParlamentar.SiglaPartidoParlamentar') as partido_sigla,
    json_value(payload, '$.IdentificacaoParlamentar.UrlFotoParlamentar') as url_foto,
    -- UF do mandato mais recente
    (
        select json_value(mandato, '$.UfParlamentar')
        from unnest(mandatos) as mandato
        order by coalesce(
            safe_cast(json_value(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as int64),
            safe_cast(json_value(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as int64)
        ) desc
        limit 1
    ) as uf_sigla,
    array(
        select distinct legislatura
        from unnest(mandatos) as mandato,
            unnest([
                safe_cast(json_value(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as int64),
                safe_cast(json_value(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as int64)
            ]) as legislatura
        where legislatura is not null
        order by legislatura
    ) as legislaturas
from com_mandatos
```

`dbt/models/staging/stg_senado__ceaps.sql`:

```sql
-- CEAPS do Senado: um registro por despesa (`id` único). Números e datas ISO no JSON.
with origem as (
    select * from {{ source('raw_senado', 'ceaps') }}
)

select
    _coleta_id,
    _competencia,
    json_value(payload, '$.id') as id_despesa,
    json_value(payload, '$.codSenador') as id_senador,
    json_value(payload, '$.nomeSenador') as nome_senador,
    safe_cast(json_value(payload, '$.ano') as int64) as ano,
    safe_cast(json_value(payload, '$.mes') as int64) as mes,
    json_value(payload, '$.tipoDespesa') as categoria,
    json_value(payload, '$.tipoDocumento') as tipo_documento_fiscal,
    -- CPF de pessoa física às vezes já vem mascarado pelo Senado (`240.***.***-04`)
    if(
        contains_substr(json_value(payload, '$.cpfCnpj'), '*'),
        null,
        {{ normalizar_documento("json_value(payload, '$.cpfCnpj')") }}
    ) as fornecedor_documento,
    if(
        contains_substr(json_value(payload, '$.cpfCnpj'), '*'),
        trim(json_value(payload, '$.cpfCnpj')),
        null
    ) as fornecedor_documento_mascarado,
    json_value(payload, '$.fornecedor') as fornecedor_nome,
    json_value(payload, '$.documento') as numero_documento,
    safe_cast(json_value(payload, '$.data') as date) as data_emissao,
    json_value(payload, '$.detalhamento') as detalhamento,
    safe_cast(json_value(payload, '$.valorReembolsado') as numeric) as valor_reembolsado
from origem
```

`dbt/models/staging/stg_cgu__sancoes.sql`:

```sql
-- CEIS e CNEP num só formato, com todas as datas de referência do raw (60 dias) ou do replay.
-- Vírgula decimal e datas dd/mm/aaaa. O CPF de pessoa física vem completo.
{% set cadastros = ['ceis', 'cnep'] %}

with unidas as (
    {% for cadastro in cadastros %}
    select
        _coleta_id,
        _competencia_data as data_referencia,
        '{{ cadastro | upper }}' as cadastro,
        concat('{{ cadastro }}:', {{ texto('codigo_da_sancao') }}) as sancao_id,
        {{ texto('tipo_de_pessoa') }} as tipo_pessoa,
        {{ normalizar_documento('cpf_ou_cnpj_do_sancionado') }} as documento,
        {{ texto('nome_do_sancionado') }} as nome_sancionado,
        {{ texto('razao_social_cadastro_receita') }} as razao_social_receita,
        {{ texto('categoria_da_sancao') }} as categoria,
        {% if cadastro == 'cnep' %}{{ numero_br('valor_da_multa') }}{% else %}cast(null as numeric){% endif %} as valor_multa,
        {{ data_br('data_inicio_sancao') }} as data_inicio,
        {{ data_br('data_final_sancao') }} as data_fim,
        {{ data_br('data_publicacao') }} as data_publicacao,
        {{ data_br('data_do_transito_em_julgado') }} as data_transito_julgado,
        {{ texto('abragencia_da_sancao') }} as abrangencia,
        {{ texto('orgao_sancionador') }} as orgao_sancionador,
        {{ texto('uf_orgao_sancionador') }} as uf_orgao_sancionador,
        {{ texto('esfera_orgao_sancionador') }} as esfera_orgao_sancionador,
        {{ texto('fundamentacao_legal') }} as fundamentacao_legal,
        {{ texto('numero_do_processo') }} as numero_processo
    from {{ fonte_snapshot('cgu', cadastro) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    *,
    -- muda quando qualquer atributo da sanção muda (base do histórico)
    to_hex(md5(to_json_string(struct(
        tipo_pessoa, documento, nome_sancionado, razao_social_receita, categoria, valor_multa,
        data_inicio, data_fim, data_publicacao, data_transito_julgado, abrangencia,
        orgao_sancionador, uf_orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal,
        numero_processo
    )))) as hash_atributos
from unidas
```

`dbt/models/staging/stg_ibge__municipios.sql`:

```sql
-- Municípios do snapshot mais recente. A UF vem da região imediata, que todos têm;
-- micro e mesorregião podem faltar em municípios novos.
with origem as (
    select * from {{ source('raw_ibge', 'municipios') }}
    where _competencia_data = (
        select max(_competencia_data) from {{ source('raw_ibge', 'municipios') }}
    )
)

select
    _coleta_id,
    json_value(payload, '$.id') as municipio_id,
    json_value(payload, '$.nome') as municipio_nome,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".UF.id') as uf_id,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".UF.sigla') as uf_sigla,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".UF.nome') as uf_nome,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".UF.regiao.sigla') as regiao_sigla,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".UF.regiao.nome') as regiao_nome,
    json_value(payload, '$.microrregiao.nome') as microrregiao,
    json_value(payload, '$.microrregiao.mesorregiao.nome') as mesorregiao,
    json_value(payload, '$."regiao-imediata".nome') as regiao_imediata,
    json_value(payload, '$."regiao-imediata"."regiao-intermediaria".nome') as regiao_intermediaria
from origem
```

Apague `dbt/models/.gitkeep`.

- [ ] **Passo 4: conferir a troca de origem**

Rode:
```bash
DBT compile --select stg_cgu__sancoes --vars "{fonte_historico: replay}" | grep -c "replay"
DBT compile --select stg_cgu__sancoes | grep -c "raw_cgu"
DBT compile --select stg_cgu__sancoes --vars "{fonte_historico: outro}"
```
Esperado:
- a primeira contagem é ≥ 2, com `replay`.`cgu__ceis` e `replay`.`cgu__cnep`;
- a segunda é ≥ 2;
- a terceira falha com `fonte_historico deve ser raw ou replay, não outro`.

- [ ] **Passo 5: construir e conferir no BigQuery**

Rode: `DBT build --select staging`
Esperado: `PASS=6`. As views não processam bytes.

Confira as contagens:
```bash
bq query --use_legacy_sql=false "select count(*) municipios, count(distinct uf_sigla) ufs from dev_${ELEITORADO_USUARIO_DBT}_staging.stg_ibge__municipios"
```
Esperado: 5.571 municípios e 27 UFs.

- [ ] **Passo 6: commit**

```bash
git add dbt/macros/fonte_snapshot.sql dbt/models
git commit -m "feat(dbt): sources e staging de Câmara, Senado, CGU e IBGE"
```

---

### Tarefa 3: histórico por eventos

**Arquivos:**
- Criar: `dbt/macros/eventos_de_snapshots.sql`, `dbt/models/intermediate/historico.yml`, `int_cgu__sancoes_eventos.sql`, `int_parlamentares__snapshots.sql` e `int_parlamentares__eventos.sql`

**Interfaces:**
- Consome: `stg_cgu__sancoes`, `stg_camara__deputados` e `stg_senado__senadores` (Tarefa 2).
- Produz:
  - macro `eventos_de_snapshots(origem, chave, atributos)`. A origem tem uma linha por (chave, `data_referencia`), com os atributos, `hash_atributos` e `_coleta_id`;
  - `int_cgu__sancoes_eventos` e `int_parlamentares__eventos`, com as colunas `evento_id`, a chave, `data_evento`, `evento` (`inclusao`, `alteracao` ou `exclusao`), `hash_atributos`, `_coleta_id` e os atributos;
  - `int_parlamentares__snapshots`, com uma linha por parlamentar e data, nas colunas `parlamentar_id`, `casa`, `id_origem`, `data_referencia`, `nome`, `uf_sigla`, `partido_sigla`, `url_foto`, `legislaturas` e `hash_atributos`.

- [ ] **Passo 1: testes (unitários e de chave)**

`dbt/models/intermediate/historico.yml`:

```yaml
version: 2

models:
  - name: int_cgu__sancoes_eventos
    columns:
      - name: evento_id
        data_tests: [unique, not_null]
  - name: int_parlamentares__eventos
    columns:
      - name: evento_id
        data_tests: [unique, not_null]

unit_tests:
  - name: eventos_de_snapshots_carga_inicial
    description: >
      Sem histórico: inclusão na primeira aparição, alteração quando o hash muda, exclusão
      quando some (com os últimos atributos) e nova inclusão quando reaparece.
    model: int_cgu__sancoes_eventos
    overrides:
      macros: {is_incremental: false}
    given:
      - input: ref('stg_cgu__sancoes')
        rows:
          - {sancao_id: 'ceis:A', data_referencia: '2026-10-01', hash_atributos: h1, nome_sancionado: A1, _coleta_id: c1}
          - {sancao_id: 'ceis:B', data_referencia: '2026-10-01', hash_atributos: h1, nome_sancionado: B1, _coleta_id: c1}
          - {sancao_id: 'ceis:A', data_referencia: '2026-10-02', hash_atributos: h2, nome_sancionado: A2, _coleta_id: c2}
          - {sancao_id: 'ceis:A', data_referencia: '2026-10-03', hash_atributos: h2, nome_sancionado: A2, _coleta_id: c3}
          - {sancao_id: 'ceis:B', data_referencia: '2026-10-03', hash_atributos: h1, nome_sancionado: B1, _coleta_id: c3}
    expect:
      rows:
        - {sancao_id: 'ceis:A', data_evento: '2026-10-01', evento: inclusao, nome_sancionado: A1}
        - {sancao_id: 'ceis:B', data_evento: '2026-10-01', evento: inclusao, nome_sancionado: B1}
        - {sancao_id: 'ceis:A', data_evento: '2026-10-02', evento: alteracao, nome_sancionado: A2}
        - {sancao_id: 'ceis:B', data_evento: '2026-10-02', evento: exclusao, nome_sancionado: B1}
        - {sancao_id: 'ceis:B', data_evento: '2026-10-03', evento: inclusao, nome_sancionado: B1}

  - name: eventos_de_snapshots_incremental
    description: >
      Com histórico: só datas novas são lidas; o estado vigente vale como snapshot anterior.
      Sem mudança não gera evento; chave cuja última versão é exclusão volta como inclusão.
    model: int_cgu__sancoes_eventos
    overrides:
      macros: {is_incremental: true}
    given:
      - input: this
        rows:
          - {sancao_id: 'ceis:A', data_evento: '2026-10-01', evento: inclusao, hash_atributos: h1, _coleta_id: c1}
          - {sancao_id: 'ceis:B', data_evento: '2026-10-01', evento: inclusao, hash_atributos: h1, _coleta_id: c1}
          - {sancao_id: 'ceis:C', data_evento: '2026-09-30', evento: inclusao, hash_atributos: h1, _coleta_id: c0}
          - {sancao_id: 'ceis:C', data_evento: '2026-10-01', evento: exclusao, hash_atributos: h1, _coleta_id: c0}
      - input: ref('stg_cgu__sancoes')
        rows:
          - {sancao_id: 'ceis:A', data_referencia: '2026-10-01', hash_atributos: h1, _coleta_id: c1}
          - {sancao_id: 'ceis:B', data_referencia: '2026-10-01', hash_atributos: h1, _coleta_id: c1}
          - {sancao_id: 'ceis:A', data_referencia: '2026-10-02', hash_atributos: h1, _coleta_id: c2}
          - {sancao_id: 'ceis:C', data_referencia: '2026-10-02', hash_atributos: h1, _coleta_id: c2}
    expect:
      rows:
        - {sancao_id: 'ceis:B', data_evento: '2026-10-02', evento: exclusao, _coleta_id: c1}
        - {sancao_id: 'ceis:C', data_evento: '2026-10-02', evento: inclusao, _coleta_id: c2}
```

Rode: `DBT test --select int_cgu__sancoes_eventos`
Esperado: erro, porque o modelo não existe.

- [ ] **Passo 2: macro e modelos**

`dbt/macros/eventos_de_snapshots.sql`:

```sql
{#-
    Histórico por eventos a partir de snapshots completos (seção 7.4 da spec).

    Compara cada data de referência nova com a anterior e com o estado vigente já gravado
    em {{ this }}, e emite um evento por mudança:
      inclusao   - a chave aparece (ou reaparece depois de uma exclusão)
      alteracao  - a chave continua, mas o hash dos atributos mudou
      exclusao   - a chave deixou de aparecer; o evento guarda os últimos atributos

    O tempo do histórico é a data de referência da publicação, nunca o horário da execução.
    Uma data já processada e sem mudanças volta a ser comparada na próxima execução sem gerar
    eventos, então reprocessar é seguro.

    origem: relação com uma linha por (chave, data_referencia), as colunas de `atributos`,
            `hash_atributos` e `_coleta_id`.
-#}
{% macro eventos_de_snapshots(origem, chave, atributos) -%}

with novos as (
    select * from {{ origem }}
    {% if is_incremental() %}
    where data_referencia > (select coalesce(max(data_evento), date '1900-01-01') from {{ this }})
    {% endif %}
),

presencas as (
    select
        {{ chave }},
        data_referencia,
        struct(
            hash_atributos, _coleta_id,
            {% for atributo in atributos %}{{ atributo }}{% if not loop.last %}, {% endif %}{% endfor %}
        ) as estado
    from novos
    {% if is_incremental() %}
    union all
    -- estado vigente já gravado, como se fosse um snapshot anterior a todas as datas novas;
    -- uma chave cuja última versão é exclusão conta como ausente
    select
        {{ chave }},
        date '0001-01-01' as data_referencia,
        struct(
            hash_atributos, _coleta_id,
            {% for atributo in atributos %}{{ atributo }}{% if not loop.last %}, {% endif %}{% endfor %}
        ) as estado
    from {{ this }}
    where true
    qualify row_number() over (partition by {{ chave }} order by data_evento desc) = 1
        and evento != 'exclusao'
    {% endif %}
),

datas as (
    select distinct data_referencia from presencas
),

chaves as (
    select distinct {{ chave }} from presencas
),

grade as (
    select c.{{ chave }}, d.data_referencia, p.estado
    from chaves as c
    cross join datas as d
    left join presencas as p
        on p.{{ chave }} = c.{{ chave }} and p.data_referencia = d.data_referencia
),

comparada as (
    select
        {{ chave }},
        data_referencia,
        estado is not null as presente,
        coalesce(lag(estado is not null) over janela, false) as presente_antes,
        estado.hash_atributos as hash_agora,
        lag(estado.hash_atributos) over janela as hash_antes,
        -- o próprio estado quando presente; o último estado conhecido quando ausente
        last_value(estado ignore nulls) over (
            janela rows between unbounded preceding and current row
        ) as ultimo_estado
    from grade
    window janela as (partition by {{ chave }} order by data_referencia)
),

eventos as (
    select
        *,
        case
            when presente and not presente_antes then 'inclusao'
            when presente and hash_agora != hash_antes then 'alteracao'
            when not presente and presente_antes then 'exclusao'
        end as evento
    from comparada
    where data_referencia > date '0001-01-01'
)

select
    to_hex(md5(concat({{ chave }}, '|', cast(data_referencia as string), '|', evento))) as evento_id,
    {{ chave }},
    data_referencia as data_evento,
    evento,
    ultimo_estado.hash_atributos,
    ultimo_estado._coleta_id,
    {% for atributo in atributos %}
    ultimo_estado.{{ atributo }}{% if not loop.last %},{% endif %}
    {% endfor %}
from eventos
where evento is not null

{%- endmacro %}
```

`dbt/models/intermediate/int_cgu__sancoes_eventos.sql`:

```sql
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='evento_id',
        partition_by={'field': 'data_evento', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['sancao_id'],
    )
}}

-- Eventos de inclusão, alteração e exclusão das sanções do CEIS e do CNEP.
-- Permanente: o raw guarda só 60 dias de snapshots (seção 6.3 da spec).
{{ eventos_de_snapshots(
    origem=ref('stg_cgu__sancoes'),
    chave='sancao_id',
    atributos=[
        'cadastro', 'tipo_pessoa', 'documento', 'nome_sancionado', 'razao_social_receita',
        'categoria', 'valor_multa', 'data_inicio', 'data_fim', 'data_publicacao',
        'data_transito_julgado', 'abrangencia', 'orgao_sancionador', 'uf_orgao_sancionador',
        'esfera_orgao_sancionador', 'fundamentacao_legal', 'numero_processo',
    ],
) }}
```

`dbt/models/intermediate/int_parlamentares__snapshots.sql`:

```sql
{{ config(materialized='view') }}

-- Câmara e Senado num só cadastro, uma linha por parlamentar na data de referência.
-- Na Câmara, nome, UF e partido vêm da legislatura mais recente do deputado.
with deputados as (
    select
        concat('camara:', id_deputado) as parlamentar_id,
        'camara' as casa,
        id_deputado as id_origem,
        data_referencia,
        _coleta_id,
        array_agg(
            struct(nome, uf_sigla, partido_sigla, url_foto)
            order by legislatura desc limit 1
        )[offset(0)] as recente,
        array_agg(distinct legislatura order by legislatura) as legislaturas
    from {{ ref('stg_camara__deputados') }}
    group by 1, 2, 3, 4, 5
),

unidos as (
    select
        parlamentar_id, casa, id_origem, data_referencia, _coleta_id,
        recente.nome, recente.uf_sigla, recente.partido_sigla, recente.url_foto, legislaturas
    from deputados
    union all
    select
        concat('senado:', id_senador), 'senado', id_senador, data_referencia, _coleta_id,
        nome, uf_sigla, partido_sigla, url_foto, legislaturas
    from {{ ref('stg_senado__senadores') }}
)

select
    *,
    to_hex(md5(to_json_string(struct(casa, nome, uf_sigla, partido_sigla)))) as hash_atributos
from unidos
```

`dbt/models/intermediate/int_parlamentares__eventos.sql`:

```sql
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='evento_id',
        cluster_by=['parlamentar_id'],
    )
}}

-- Eventos do cadastro de parlamentares (mudança de partido, de UF, entrada e saída).
{{ eventos_de_snapshots(
    origem=ref('int_parlamentares__snapshots'),
    chave='parlamentar_id',
    atributos=['casa', 'nome', 'uf_sigla', 'partido_sigla'],
) }}
```

- [ ] **Passo 3: testes passando, depois idempotência contra os dados reais**

Rode: `DBT build --select int_cgu__sancoes_eventos int_parlamentares__snapshots int_parlamentares__eventos`
Esperado:
- 3 modelos OK;
- os 2 testes unitários e os 4 testes de chave passando;
- `int_cgu__sancoes_eventos` com cerca de 25 mil eventos, quase todos `inclusao`, porque o raw tem poucas datas de referência.

Rode o mesmo comando de novo.
Esperado: os dois incrementais com `MERGE (0.0 rows ...)`.

- [ ] **Passo 4: commit**

```bash
git add dbt/macros/eventos_de_snapshots.sql dbt/models/intermediate
git commit -m "feat(dbt): histórico por eventos de sanções e parlamentares"
```

---

### Tarefa 4: cota parlamentar unificada

**Arquivos:**
- Criar: `dbt/models/intermediate/cota.yml` e `dbt/models/intermediate/int_cota__despesas.sql`

**Interfaces:**
- Consome: `stg_camara__ceap`, `stg_senado__ceaps` e `stg_senado__senadores`.
- Produz `int_cota__despesas`, com as colunas de `fct_despesa_cota_parlamentar` (seção 7.5 da spec).
  - O `fornecedor_documento` vem completo, inclusive o CPF.
  - Também traz `fornecedor_tipo_documento`, com os valores `CPF`, `CNPJ`, `INVALIDO`, `CPF_MASCARADO` e `CODIGO_CAMARA`.
  - `fornecedor_documento_valido` só tem valor para CPF, CNPJ e INVALIDO.
  - `fornecedor_cnpj_raiz` só tem valor para CNPJ.
  - `despesa_id` é `camara:<hash_linha>-<n>` ou `senado:<id>`.

- [ ] **Passo 1: testes**

`dbt/models/intermediate/cota.yml`:

```yaml
version: 2

models:
  - name: int_cota__despesas
    columns:
      - name: despesa_id
        data_tests: [unique, not_null]

unit_tests:
  - name: despesa_camara_linhas_identicas
    description: >
      A CEAP não tem chave: linhas idênticas recebem ids distintos e estáveis (ordem por
      competência e linha); sem deputado, a despesa é da liderança.
    model: int_cota__despesas
    given:
      - input: ref('stg_camara__ceap')
        rows:
          - {hash_linha: x, id_deputado: '1', _competencia: '2026', _linha: 7}
          - {hash_linha: x, id_deputado: '1', _competencia: '2026', _linha: 3}
          - {hash_linha: y, _competencia: '2026', _linha: 1}
      - input: ref('stg_senado__ceaps')
        rows: []
      - input: ref('stg_senado__senadores')
        rows: []
    expect:
      rows:
        - {despesa_id: 'camara:x-1', parlamentar_id: 'camara:1', tipo_beneficiario: parlamentar}
        - {despesa_id: 'camara:x-2', parlamentar_id: 'camara:1', tipo_beneficiario: parlamentar}
        - {despesa_id: 'camara:y-1', parlamentar_id: null, tipo_beneficiario: lideranca}

  - name: despesa_documentos_especiais_e_uf
    description: >
      Códigos internos da Câmara (`000000000000NN`) e CPFs que o Senado já publica mascarados
      não são documentos inválidos nem viram raiz de CNPJ; o CNPJ real do Banco do Brasil
      (`00000000000191`) continua CNPJ. A UF `NA` das lideranças vira nula, e a UF do Senado
      vem do snapshot mais recente do cadastro.
    model: int_cota__despesas
    given:
      - input: ref('stg_camara__ceap')
        rows:
          - {hash_linha: a, fornecedor_documento: '00000000000007', uf_sigla: NA, _competencia: '2026', _linha: 1}
          - {hash_linha: b, fornecedor_documento: '00000000000191', uf_sigla: DF, id_deputado: '1', _competencia: '2026', _linha: 2}
      - input: ref('stg_senado__ceaps')
        rows:
          - {id_despesa: '9', id_senador: '5', fornecedor_documento_mascarado: '240.***.***-04'}
          - {id_despesa: '10', id_senador: '5', fornecedor_documento: '123'}
      - input: ref('stg_senado__senadores')
        rows:
          - {id_senador: '5', uf_sigla: RJ, data_referencia: '2026-09-01'}
          - {id_senador: '5', uf_sigla: SP, data_referencia: '2026-10-01'}
    expect:
      rows:
        - {despesa_id: 'camara:a-1', fornecedor_documento: '00000000000007', fornecedor_tipo_documento: CODIGO_CAMARA, fornecedor_documento_valido: null, fornecedor_cnpj_raiz: null, uf_sigla: null}
        - {despesa_id: 'camara:b-1', fornecedor_documento: '00000000000191', fornecedor_tipo_documento: CNPJ, fornecedor_documento_valido: true, fornecedor_cnpj_raiz: '00000000', uf_sigla: DF}
        - {despesa_id: 'senado:9', fornecedor_documento: '240.***.***-04', fornecedor_tipo_documento: CPF_MASCARADO, fornecedor_documento_valido: null, fornecedor_cnpj_raiz: null, uf_sigla: SP}
        - {despesa_id: 'senado:10', fornecedor_documento: '123', fornecedor_tipo_documento: INVALIDO, fornecedor_documento_valido: false, fornecedor_cnpj_raiz: null, uf_sigla: SP}
```

Rode: `DBT test --select int_cota__despesas`
Esperado: erro, porque o modelo não existe.

- [ ] **Passo 2: modelo**

`dbt/models/intermediate/int_cota__despesas.sql`:

```sql
{{
    config(
        partition_by={'field': 'data_competencia', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['casa', 'fornecedor_cnpj_raiz'],
    )
}}

-- CEAP e CEAPS no mesmo grão: uma linha de despesa como publicada.
-- Documento do fornecedor completo (CPF inclusive): esta camada não é exposta à web app.
with camara as (
    select
        -- a CEAP não tem chave natural: hash do conteúdo + ocorrência entre linhas idênticas
        concat(
            'camara:', hash_linha, '-',
            cast(row_number() over (partition by hash_linha order by _competencia, _linha) as string)
        ) as despesa_id,
        'camara' as casa,
        if(id_deputado is null, null, concat('camara:', id_deputado)) as parlamentar_id,
        if(id_deputado is null, 'lideranca', 'parlamentar') as tipo_beneficiario,
        nome_beneficiario,
        nullif(uf_sigla, 'NA') as uf_sigla,  -- lideranças vêm com `NA`
        partido_sigla,
        ano,
        mes,
        data_emissao,
        categoria,
        subcategoria,
        fornecedor_nome,
        fornecedor_documento,
        cast(null as string) as fornecedor_documento_mascarado,
        valor_documento,
        valor_glosa,
        valor_reembolsado,
        numero_documento,
        url_documento,
        id_documento_origem,
        passageiro as camara_passageiro,
        trecho as camara_trecho,
        cast(null as string) as senado_detalhamento,
        _coleta_id
    from {{ ref('stg_camara__ceap') }}
),

senado as (
    select
        concat('senado:', c.id_despesa) as despesa_id,
        'senado' as casa,
        concat('senado:', c.id_senador) as parlamentar_id,
        'parlamentar' as tipo_beneficiario,
        c.nome_senador as nome_beneficiario,
        s.uf_sigla,
        cast(null as string) as partido_sigla,
        c.ano,
        c.mes,
        c.data_emissao,
        c.categoria,
        c.tipo_documento_fiscal as subcategoria,
        c.fornecedor_nome,
        c.fornecedor_documento,
        c.fornecedor_documento_mascarado,
        cast(null as numeric) as valor_documento,
        cast(null as numeric) as valor_glosa,
        c.valor_reembolsado,
        c.numero_documento,
        cast(null as string) as url_documento,
        c.id_despesa as id_documento_origem,
        cast(null as string) as camara_passageiro,
        cast(null as string) as camara_trecho,
        c.detalhamento as senado_detalhamento,
        c._coleta_id
    from {{ ref('stg_senado__ceaps') }} as c
    left join (
        select id_senador, uf_sigla
        from {{ ref('stg_senado__senadores') }}
        where true
        qualify data_referencia = max(data_referencia) over ()
    ) as s
        on s.id_senador = c.id_senador
),

unidas as (
    select * from camara
    union all
    select * from senado
),

-- CPF e CNPJ seguem a validação; o resto não é documento de fornecedor:
-- CPF_MASCARADO (o Senado publica `240.***.***-04`) e CODIGO_CAMARA (`000000000000NN`, que
-- a Câmara usa para serviços internos, como telefonia e Correios, e fornecedores estrangeiros)
classificadas as (
    select
        *,
        case
            when fornecedor_documento_mascarado is not null then 'CPF_MASCARADO'
            when casa = 'camara' and regexp_contains(fornecedor_documento, r'^0{12}[0-9]{2}$')
                then 'CODIGO_CAMARA'
            else {{ tipo_documento('fornecedor_documento') }}
        end as fornecedor_tipo_documento
    from unidas
)

select
    * except (fornecedor_documento, fornecedor_documento_mascarado, fornecedor_tipo_documento),
    safe.date(ano, mes, 1) as data_competencia,
    coalesce(fornecedor_documento_mascarado, fornecedor_documento) as fornecedor_documento,
    fornecedor_tipo_documento,
    case fornecedor_tipo_documento
        when 'CPF' then {{ documento_valido('fornecedor_documento') }}
        when 'CNPJ' then {{ documento_valido('fornecedor_documento') }}
        when 'INVALIDO' then false
    end as fornecedor_documento_valido,
    if(fornecedor_tipo_documento = 'CNPJ', substr(fornecedor_documento, 1, 8), null)
        as fornecedor_cnpj_raiz
from classificadas
```

- [ ] **Passo 3: testes passando e distribuição real**

Rode: `DBT build --select int_cota__despesas`
Esperado:
- o modelo com cerca de 5,6 milhões de linhas e cerca de 1,8 GiB processados;
- os 2 testes unitários passando;
- `unique` e `not_null` de `despesa_id` passando.

```bash
bq query --use_legacy_sql=false "select casa, fornecedor_tipo_documento, fornecedor_documento_valido, count(*) n from dev_${ELEITORADO_USUARIO_DBT}_intermediate.int_cota__despesas group by 1, 2, 3 order by 1, n desc"
```
Esperado:
- a maior parte é CNPJ válido;
- `CODIGO_CAMARA` tem cerca de 833 mil linhas, todas da Câmara;
- `CPF_MASCARADO` tem cerca de 8,9 mil, todas do Senado;
- os inválidos somam menos de 100.

- [ ] **Passo 4: commit**

```bash
git add dbt/models/intermediate/cota.yml dbt/models/intermediate/int_cota__despesas.sql
git commit -m "feat(dbt): cota parlamentar unificada com classificação de documentos"
```

---

### Tarefa 5: dimensões, fatos e o teste de LGPD

**Arquivos:**
- Criar: `dbt/tests/generic/sem_cpf_completo.sql`, `dbt/tests/cota_reconciliacao.sql`, `dbt/models/marts/marts.yml`, `dim_uf.sql`, `dim_municipio.sql`, `dim_parlamentar.sql`, `fct_despesa_cota_parlamentar.sql`, `fct_sancao.sql` e `fct_sancao_historico.sql`
- Remover: `dbt/tests/.gitkeep`

**Interfaces:**
- Consome: Tarefas 2, 3 e 4.
- Produz:
  - os marts da seção 7.5 da spec, com documentos de pessoa física mascarados;
  - o teste genérico `sem_cpf_completo(model, excluir=[])`.

- [ ] **Passo 1: o teste de LGPD acusa CPF (falha primeiro)**

`dbt/tests/generic/sem_cpf_completo.sql`:

```sql
{#-
    LGPD (seção 7.6 da spec): nenhuma coluna de texto do modelo pode ter um CPF sem máscara,
    formatado ou não. Percorre todas as colunas STRING, menos as chaves (`*_id`, hashes
    hexadecimais) e as listadas em `excluir` (números de nota, URLs). Falha com cada valor
    encontrado, para dar para corrigir na origem.
-#}
{% test sem_cpf_completo(model, excluir=[]) %}
{%- set colunas = [] -%}
{%- for coluna in adapter.get_columns_in_relation(model) -%}
    {%- if coluna.dtype == 'STRING' and not coluna.name.endswith('_id')
        and coluna.name not in excluir -%}
        {%- do colunas.append(coluna.name) -%}
    {%- endif -%}
{%- endfor -%}

{%- for coluna in colunas %}
select '{{ coluna }}' as coluna, {{ coluna }} as valor
from {{ model }}
where regexp_contains({{ coluna }}, r'(^|[^0-9])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9]|$)')
{% if not loop.last %}union all{% endif %}
{%- else %}
select cast(null as string) as coluna, cast(null as string) as valor
from (select 1) where false
{%- endfor %}
{% endtest %}
```

`dbt/models/marts/marts.yml`:

```yaml
version: 2

# Todos os marts passam pelo `sem_cpf_completo` (seção 7.6 da spec).
models:
  - name: dim_uf
    data_tests: [sem_cpf_completo]
    columns:
      - name: uf_sigla
        data_tests: [unique, not_null]

  - name: dim_municipio
    data_tests: [sem_cpf_completo]
    columns:
      - name: municipio_id
        data_tests: [unique, not_null]
      - name: uf_sigla
        data_tests:
          - not_null
          - relationships:
              arguments: {to: ref('dim_uf'), field: uf_sigla}

  - name: dim_parlamentar
    data_tests:
      - sem_cpf_completo:
          arguments: {excluir: [url_foto]}
    columns:
      - name: parlamentar_id
        data_tests: [unique, not_null]
      - name: casa
        data_tests:
          - accepted_values:
              arguments: {values: [camara, senado]}
      - name: uf_sigla
        data_tests:
          - relationships:
              arguments: {to: ref('dim_uf'), field: uf_sigla}

  - name: fct_despesa_cota_parlamentar
    data_tests:
      - sem_cpf_completo:
          arguments: {excluir: [numero_documento, url_documento]}
    columns:
      - name: despesa_id
        data_tests: [unique, not_null]
      - name: casa
        data_tests:
          - not_null
          - accepted_values:
              arguments: {values: [camara, senado]}
      - name: parlamentar_id
        data_tests:
          - relationships:
              arguments: {to: ref('dim_parlamentar'), field: parlamentar_id}
              config: {severity: warn}
      - name: uf_sigla
        data_tests:
          - relationships:
              arguments: {to: ref('dim_uf'), field: uf_sigla}
      - name: tipo_beneficiario
        data_tests:
          - accepted_values:
              arguments: {values: [parlamentar, lideranca]}
      - name: fornecedor_tipo_documento
        data_tests:
          - accepted_values:
              arguments: {values: [CPF, CNPJ, CPF_MASCARADO, CODIGO_CAMARA, INVALIDO]}

  - name: fct_sancao
    data_tests:
      - sem_cpf_completo:
          arguments: {excluir: [numero_processo]}
    columns:
      - name: sancao_id
        data_tests: [unique, not_null]
      - name: cadastro
        data_tests:
          - accepted_values:
              arguments: {values: [CEIS, CNEP]}
      - name: tipo_pessoa
        data_tests:
          - accepted_values:
              arguments: {values: [F, J]}

  - name: fct_sancao_historico
    data_tests:
      - sem_cpf_completo:
          arguments: {excluir: [numero_processo]}
    columns:
      - name: evento_id
        data_tests: [unique, not_null]
      - name: evento
        data_tests:
          - accepted_values:
              arguments: {values: [inclusao, alteracao, exclusao]}
```

`dbt/tests/cota_reconciliacao.sql`:

```sql
-- O fato da cota tem as mesmas linhas e o mesmo valor reembolsado que o staging, por casa e ano.
with origem as (
    select 'camara' as casa, ano, count(*) as linhas, sum(valor_reembolsado) as valor
    from {{ ref('stg_camara__ceap') }}
    group by 1, 2
    union all
    select 'senado', ano, count(*), sum(valor_reembolsado)
    from {{ ref('stg_senado__ceaps') }}
    group by 1, 2
),

fato as (
    select casa, ano, count(*) as linhas, sum(valor_reembolsado) as valor
    from {{ ref('fct_despesa_cota_parlamentar') }}
    group by 1, 2
)

select *
from origem as o
full join fato as f using (casa, ano)
where o.linhas is distinct from f.linhas
    or abs(coalesce(o.valor, 0) - coalesce(f.valor, 0)) > 0.01
```

Para ver o teste de LGPD falhar, crie primeiro `fct_sancao.sql` **sem** a máscara, com `documento as sancionado_documento` e `nome_sancionado as sancionado_nome`. Depois rode `DBT build --select fct_sancao`.
Esperado: `FAIL` em `sem_cpf_completo_fct_sancao_`, com milhares de linhas: os CPFs dos sancionados pessoa física, mais os nomes de MEI.

- [ ] **Passo 2: modelos**

`dbt/models/marts/dim_uf.sql`:

```sql
-- Uma linha por UF, a partir dos municípios do snapshot mais recente do IBGE.
select
    uf_id,
    uf_sigla,
    uf_nome,
    regiao_sigla,
    regiao_nome,
    any_value(_coleta_id) as _coleta_id
from {{ ref('stg_ibge__municipios') }}
group by uf_id, uf_sigla, uf_nome, regiao_sigla, regiao_nome
```

`dbt/models/marts/dim_municipio.sql`:

```sql
select
    municipio_id,
    municipio_nome,
    uf_sigla,
    microrregiao,
    mesorregiao,
    regiao_imediata,
    regiao_intermediaria,
    _coleta_id
from {{ ref('stg_ibge__municipios') }}
```

`dbt/models/marts/dim_parlamentar.sql`:

```sql
-- Câmara e Senado num só cadastro (`camara:<id>`, `senado:<CodigoParlamentar>`).
-- O CPF do deputado não entra nos marts (seção 7.6 da spec).
select
    parlamentar_id,
    casa,
    id_origem,
    nome,
    uf_sigla,
    partido_sigla,
    legislaturas,
    url_foto,
    _coleta_id
from {{ ref('int_parlamentares__snapshots') }}
where true
qualify data_referencia = max(data_referencia) over (partition by casa)
```

`dbt/models/marts/fct_despesa_cota_parlamentar.sql`:

```sql
{{
    config(
        partition_by={'field': 'data_competencia', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['casa', 'fornecedor_cnpj_raiz', 'parlamentar_id'],
    )
}}

-- Uma linha de despesa publicada da CEAP (Câmara) ou da CEAPS (Senado).
-- CPF de fornecedor pessoa física sai mascarado.
select
    despesa_id,
    casa,
    parlamentar_id,
    tipo_beneficiario,
    nome_beneficiario,
    uf_sigla,
    partido_sigla,
    ano,
    mes,
    data_competencia,
    data_emissao,
    categoria,
    subcategoria,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    {{ documento_publico('fornecedor_documento') }} as fornecedor_documento,
    fornecedor_tipo_documento,
    fornecedor_documento_valido,
    fornecedor_cnpj_raiz,
    valor_documento,
    valor_glosa,
    valor_reembolsado,
    numero_documento,
    url_documento,
    id_documento_origem,
    {{ mascarar_cpfs_em_texto('camara_passageiro') }} as camara_passageiro,
    camara_trecho,
    {{ mascarar_cpfs_em_texto('senado_detalhamento') }} as senado_detalhamento,
    _coleta_id
from {{ ref('int_cota__despesas') }}
```

`dbt/models/marts/fct_sancao.sql`, na versão final, com máscara:

```sql
-- Sanções presentes no arquivo mais recente de cada cadastro (CEIS e CNEP).
with sancoes as (
    select *
    from {{ ref('stg_cgu__sancoes') }}
    where true
    qualify data_referencia = max(data_referencia) over (partition by cadastro)
)

select
    sancao_id,
    cadastro,
    data_referencia,
    tipo_pessoa,
    {{ documento_publico('documento') }} as sancionado_documento,
    {{ cnpj_raiz('documento') }} as sancionado_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('nome_sancionado') }} as sancionado_nome,
    {{ mascarar_cpfs_em_texto('razao_social_receita') }} as razao_social_receita,
    categoria,
    valor_multa,
    abrangencia,
    fundamentacao_legal,
    numero_processo,
    data_inicio,
    data_fim,
    data_publicacao,
    data_transito_julgado,
    orgao_sancionador,
    uf_orgao_sancionador,
    esfera_orgao_sancionador,
    _coleta_id
from sancoes
```

`dbt/models/marts/fct_sancao_historico.sql`:

```sql
-- Histórico SCD2 das sanções: cada evento abre uma versão que vale até o próximo evento.
select
    evento_id,
    sancao_id,
    cadastro,
    evento,
    data_evento as valido_de,
    lead(data_evento) over (partition by sancao_id order by data_evento) as valido_ate,
    tipo_pessoa,
    {{ documento_publico('documento') }} as sancionado_documento,
    {{ cnpj_raiz('documento') }} as sancionado_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('nome_sancionado') }} as sancionado_nome,
    {{ mascarar_cpfs_em_texto('razao_social_receita') }} as razao_social_receita,
    categoria,
    valor_multa,
    abrangencia,
    fundamentacao_legal,
    numero_processo,
    data_inicio,
    data_fim,
    data_publicacao,
    data_transito_julgado,
    orgao_sancionador,
    uf_orgao_sancionador,
    esfera_orgao_sancionador,
    _coleta_id
from {{ ref('int_cgu__sancoes_eventos') }}
```

Apague `dbt/tests/.gitkeep`.

- [ ] **Passo 3: testes passando**

Rode: `DBT build --select dim_uf dim_municipio dim_parlamentar fct_despesa_cota_parlamentar fct_sancao fct_sancao_historico cota_reconciliacao`
Esperado:
- 6 modelos OK: `dim_uf` com 27 linhas, `dim_municipio` com 5.571, `dim_parlamentar` com cerca de 2,5 mil, o fato da cota com cerca de 5,6 milhões e as sanções com cerca de 25,6 mil;
- todos os testes passando, incluindo os 6 `sem_cpf_completo` e a `cota_reconciliacao`.

- [ ] **Passo 4: commit**

```bash
git add dbt/tests dbt/models/marts
git commit -m "feat(dbt): dimensões, fatos da cota e das sanções, teste de LGPD"
```

---

### Tarefa 6: alertas

**Arquivos:**
- Criar: `dbt/models/marts/alertas.yml`, `alerta_cota_fornecedor_sancionado.sql` e `alerta_cota_documento_invalido.sql`

**Interfaces:**
- Consome: `int_cota__despesas` e `int_cgu__sancoes_eventos`.
- Produz:
  - `alerta_cota_fornecedor_sancionado`: uma linha por (despesa, sanção), com `tipo_correspondencia` (`cpf`, `cnpj` ou `cnpj_raiz`);
  - `alerta_cota_documento_invalido`: uma linha por despesa, com `motivo` (`tamanho` ou `digito_verificador`).

- [ ] **Passo 1: testes**

`dbt/models/marts/alertas.yml`:

```yaml
version: 2

# Todos os marts passam pelo `sem_cpf_completo` (seção 7.6 da spec).
models:
  - name: alerta_cota_fornecedor_sancionado
    data_tests: [sem_cpf_completo]
    columns:
      - name: alerta_id
        data_tests: [unique, not_null]
      - name: despesa_id
        data_tests:
          - relationships:
              arguments: {to: ref('fct_despesa_cota_parlamentar'), field: despesa_id}
      - name: tipo_correspondencia
        data_tests:
          - accepted_values:
              arguments: {values: [cpf, cnpj, cnpj_raiz]}

  - name: alerta_cota_documento_invalido
    data_tests: [sem_cpf_completo]
    columns:
      - name: alerta_id
        data_tests: [unique, not_null]
      - name: motivo
        data_tests:
          - accepted_values:
              arguments: {values: [tamanho, digito_verificador]}

unit_tests:
  - name: alerta_sancionado_por_documento_raiz_e_vigencia
    description: >
      CNPJ completo e raiz (filial) dentro da vigência geram alerta; fora da vigência e
      versões de exclusão não; CPF com sanção sem data de fim gera.
    model: alerta_cota_fornecedor_sancionado
    given:
      - input: ref('int_cota__despesas')
        rows:
          - {despesa_id: d1, fornecedor_documento: '11222333000181', fornecedor_tipo_documento: CNPJ, fornecedor_documento_valido: true, fornecedor_cnpj_raiz: '11222333', data_emissao: '2024-05-10'}
          - {despesa_id: d2, fornecedor_documento: '11222333000262', fornecedor_tipo_documento: CNPJ, fornecedor_documento_valido: true, fornecedor_cnpj_raiz: '11222333', data_emissao: '2024-05-10'}
          - {despesa_id: d3, fornecedor_documento: '11222333000181', fornecedor_tipo_documento: CNPJ, fornecedor_documento_valido: true, fornecedor_cnpj_raiz: '11222333', data_emissao: '2025-01-05'}
          - {despesa_id: d4, fornecedor_documento: '11144477735', fornecedor_tipo_documento: CPF, fornecedor_documento_valido: true, data_emissao: '2024-06-01'}
          - {despesa_id: d5, fornecedor_documento: '11444777000161', fornecedor_tipo_documento: CNPJ, fornecedor_documento_valido: true, fornecedor_cnpj_raiz: '11444777', data_emissao: '2024-06-01'}
      - input: ref('int_cgu__sancoes_eventos')
        rows:
          - {sancao_id: 'ceis:1', evento: inclusao, documento: '11222333000181', data_inicio: '2024-01-01', data_fim: '2024-12-31', _coleta_id: c1}
          - {sancao_id: 'ceis:2', evento: inclusao, documento: '11144477735', data_inicio: '2024-01-01', _coleta_id: c1}
          - {sancao_id: 'ceis:3', evento: exclusao, documento: '11444777000161', data_inicio: '2024-01-01', _coleta_id: c1}
    expect:
      rows:
        - {despesa_id: d1, sancao_id: 'ceis:1', tipo_correspondencia: cnpj, fornecedor_documento: '11222333000181'}
        - {despesa_id: d2, sancao_id: 'ceis:1', tipo_correspondencia: cnpj_raiz, fornecedor_documento: '11222333000262'}
        - {despesa_id: d4, sancao_id: 'ceis:2', tipo_correspondencia: cpf, fornecedor_documento: '***.444.777-**'}
```

Rode: `DBT test --select alerta_cota_fornecedor_sancionado`
Esperado: erro, porque o modelo não existe.

- [ ] **Passo 2: modelos**

`dbt/models/marts/alerta_cota_fornecedor_sancionado.sql`:

```sql
-- Despesa de cota cujo fornecedor tinha sanção (CEIS ou CNEP) na data da despesa.
-- É um indício para investigar, não a constatação de irregularidade: a cota reembolsa gastos
-- do parlamentar (não é contratação pública) e a abrangência da sanção varia.
-- Cobertura: só sanções vistas desde a primeira coleta (a CGU publica apenas o arquivo do dia).
with despesas as (
    select *
    from {{ ref('int_cota__despesas') }}
    where fornecedor_documento_valido and data_emissao is not null
),

-- qualquer versão já vista de cada sanção (exclusões não são versões)
sancoes as (
    select distinct
        sancao_id, cadastro, tipo_pessoa, documento,
        {{ tipo_documento('documento') }} as tipo_documento,
        {{ cnpj_raiz('documento') }} as cnpj_raiz,
        nome_sancionado, categoria, abrangencia, orgao_sancionador, data_inicio, data_fim, _coleta_id
    from {{ ref('int_cgu__sancoes_eventos') }}
    where evento != 'exclusao' and data_inicio is not null
),

cruzadas as (
    select
        d.despesa_id,
        s.sancao_id,
        case
            when d.fornecedor_tipo_documento = 'CPF' then 'cpf'
            when d.fornecedor_documento = s.documento then 'cnpj'
            else 'cnpj_raiz'
        end as tipo_correspondencia,
        d.casa,
        d.parlamentar_id,
        d.nome_beneficiario,
        d.data_emissao,
        d.categoria as categoria_despesa,
        d.valor_reembolsado,
        {{ mascarar_cpfs_em_texto('d.fornecedor_nome') }} as fornecedor_nome,
        {{ documento_publico('d.fornecedor_documento') }} as fornecedor_documento,
        s.cadastro,
        s.categoria as categoria_sancao,
        s.abrangencia,
        s.orgao_sancionador,
        s.data_inicio as sancao_data_inicio,
        s.data_fim as sancao_data_fim,
        d._coleta_id as despesa_coleta_id,
        s._coleta_id as sancao_coleta_id
    from despesas as d
    join sancoes as s
        on (
            (d.fornecedor_tipo_documento = 'CPF' and s.tipo_documento = 'CPF'
                and d.fornecedor_documento = s.documento)
            or (d.fornecedor_tipo_documento = 'CNPJ' and s.tipo_documento = 'CNPJ'
                and d.fornecedor_cnpj_raiz = s.cnpj_raiz)
        )
        and d.data_emissao between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    to_hex(md5(concat('cota_fornecedor_sancionado|', despesa_id, '|', sancao_id))) as alerta_id,
    *,
    'Despesa de cota com fornecedor que tinha sanção vigente no CEIS/CNEP na data de emissão '
    || '(correspondência por CPF, CNPJ ou raiz do CNPJ)' as regra
from cruzadas
-- uma linha por (despesa, sanção), preferindo o CNPJ completo à raiz
qualify row_number() over (
    partition by despesa_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_coleta_id
) = 1
```

`dbt/models/marts/alerta_cota_documento_invalido.sql`:

```sql
-- Despesa de cota com CPF ou CNPJ de fornecedor preenchido e inválido.
-- Ficam de fora documentos vazios, CPFs que o Senado já publica mascarados e os códigos
-- internos da Câmara (`000000000000NN`).
select
    to_hex(md5(concat('cota_documento_invalido|', despesa_id))) as alerta_id,
    despesa_id,
    casa,
    parlamentar_id,
    nome_beneficiario,
    data_emissao,
    categoria,
    valor_reembolsado,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    {{ documento_publico('fornecedor_documento') }} as documento_publicado,
    if(fornecedor_tipo_documento = 'INVALIDO', 'tamanho', 'digito_verificador') as motivo,
    'Documento de fornecedor com tamanho ou dígito verificador inválido' as regra,
    _coleta_id
from {{ ref('int_cota__despesas') }}
where fornecedor_tipo_documento in ('CPF', 'CNPJ', 'INVALIDO')
    and not fornecedor_documento_valido
```

- [ ] **Passo 3: testes passando, prova de mutação e números reais**

Rode: `DBT build --select alerta_cota_fornecedor_sancionado alerta_cota_documento_invalido`
Esperado:
- 2 modelos OK: cerca de 390 alertas de fornecedor sancionado e menos de 100 de documento inválido;
- o teste unitário e os testes de dados passando.

Prova de mutação: apague temporariamente a linha `and d.data_emissao between ...` e rode `DBT test --select "alerta_cota_fornecedor_sancionado,test_type:unit"`.
Esperado: `FAIL 1`. Restaure a linha.

- [ ] **Passo 4: commit**

```bash
git add dbt/models/marts/alertas.yml dbt/models/marts/alerta_*.sql
git commit -m "feat(dbt): alertas de fornecedor sancionado e de documento inválido"
```

---

### Tarefa 7: monitor das fontes e testes de atraso

**Arquivos:**
- Criar: `dbt/models/marts/monitor_fontes.yml`, `monitor_fontes.sql`, `dbt/tests/fontes_em_atraso_aviso.sql` e `dbt/tests/fontes_em_atraso_erro.sql`

**Interfaces:**
- Consome: `source('meta', 'coletas')` e `source('meta', 'fontes')`.
- Produz `monitor_fontes` (view) com as colunas `recurso_id`, `cadencia_corrente`, `ultima_coleta`, `ultimo_sucesso`, `status_ultima_coleta`, `linhas_ultima_carga`, `mudancas_esquema_30d`, `atraso_horas`, `limite_aviso_horas` e `limite_erro_horas`.

- [ ] **Passo 1: testes**

`dbt/models/marts/monitor_fontes.yml`:

```yaml
version: 2

models:
  - name: monitor_fontes
    columns:
      - name: recurso_id
        data_tests: [unique, not_null]

unit_tests:
  - name: monitor_sem_alteracao_conta_como_sucesso
    description: >
      `sem_alteracao` é sucesso (o raw não recebe carga, mas a fonte foi conferida); uma falha
      depois não apaga o último sucesso; recargas no replay não contam; recurso sem coleta
      aparece com último sucesso nulo.
    model: monitor_fontes
    given:
      - input: source('meta', 'coletas')
        rows:
          - {orgao: cgu, recurso: ceis, destino: raw, status: sem_alteracao, iniciada_em: '2026-10-03 10:00:00', finalizada_em: '2026-10-03 10:01:00'}
          - {orgao: cgu, recurso: ceis, destino: raw, status: falha, iniciada_em: '2026-10-04 10:00:00', finalizada_em: '2026-10-04 10:01:00'}
          - {orgao: cgu, recurso: ceis, destino: replay, status: recarregada, iniciada_em: '2026-10-04 11:00:00', finalizada_em: '2026-10-04 11:01:00'}
      - input: source('meta', 'fontes')
        rows:
          - {recurso_id: cgu.ceis, cadencia_corrente: diaria}
          - {recurso_id: cgu.cnep, cadencia_corrente: semanal}
    expect:
      rows:
        - {recurso_id: cgu.ceis, ultima_coleta: '2026-10-04 10:00:00', ultimo_sucesso: '2026-10-03 10:01:00', status_ultima_coleta: falha, limite_aviso_horas: 30, limite_erro_horas: 54}
        - {recurso_id: cgu.cnep, ultima_coleta: null, ultimo_sucesso: null, status_ultima_coleta: null, limite_aviso_horas: 192, limite_erro_horas: 240}
```

`dbt/tests/fontes_em_atraso_aviso.sql`:

```sql
{{ config(severity='warn') }}

-- Recurso sem coleta bem-sucedida dentro do limite de aviso da sua cadência.
select recurso_id, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_aviso_horas
from {{ ref('monitor_fontes') }}
where ultimo_sucesso is null or atraso_horas > limite_aviso_horas
```

`dbt/tests/fontes_em_atraso_erro.sql`:

```sql
-- Recurso sem coleta bem-sucedida dentro do limite de erro da sua cadência: o vigia avisa.
select recurso_id, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_erro_horas
from {{ ref('monitor_fontes') }}
where ultimo_sucesso is null or atraso_horas > limite_erro_horas
```

Rode: `DBT test --select monitor_fontes`
Esperado: erro, porque o modelo não existe.

- [ ] **Passo 2: modelo**

`dbt/models/marts/monitor_fontes.sql`:

```sql
{{ config(materialized='view') }}

-- Situação de cada recurso: última coleta, último sucesso e atraso em relação à cadência.
-- Base dos testes de atraso (seção 7.7 da spec), que substituem o `dbt source freshness`.
with coletas as (
    select
        concat(orgao, '.', recurso) as recurso_id,
        iniciada_em,
        finalizada_em,
        status,
        linhas,
        esquema_alterado
    from {{ source('meta', 'coletas') }}
    where destino = 'raw'
),

resumo as (
    select
        recurso_id,
        max(iniciada_em) as ultima_coleta,
        max(if(status in ('carregada', 'sem_alteracao'), finalizada_em, null)) as ultimo_sucesso,
        array_agg(status order by iniciada_em desc limit 1)[offset(0)] as status_ultima_coleta,
        array_agg(if(status = 'carregada', linhas, null) ignore nulls
            order by iniciada_em desc limit 1)[safe_offset(0)] as linhas_ultima_carga,
        countif(esquema_alterado and iniciada_em >= timestamp_sub(current_timestamp(), interval 30 day))
            as mudancas_esquema_30d
    from coletas
    group by recurso_id
)

select
    f.recurso_id,
    f.cadencia_corrente,
    r.ultima_coleta,
    r.ultimo_sucesso,
    r.status_ultima_coleta,
    r.linhas_ultima_carga,
    coalesce(r.mudancas_esquema_30d, 0) as mudancas_esquema_30d,
    timestamp_diff(current_timestamp(), r.ultimo_sucesso, hour) as atraso_horas,
    case f.cadencia_corrente when 'diaria' then 30 when 'semanal' then 192 else 840 end
        as limite_aviso_horas,
    case f.cadencia_corrente when 'diaria' then 54 when 'semanal' then 240 else 960 end
        as limite_erro_horas
from {{ source('meta', 'fontes') }} as f
left join resumo as r
    on r.recurso_id = f.recurso_id
```

- [ ] **Passo 3: testes passando e o projeto inteiro**

Rode: `DBT build --select monitor_fontes fontes_em_atraso_aviso fontes_em_atraso_erro`
Esperado:
- a view criada;
- o teste unitário, `unique` e `not_null` e os dois testes de atraso passando, porque a coleta de hoje está em dia;
- 7 recursos no monitor.

Rode o projeto inteiro uma vez: `DBT build`
Esperado:
- 19 modelos OK;
- 52 testes de dados e 6 unitários passando (`PASS=77`);
- cerca de 7,7 GiB processados.

- [ ] **Passo 4: commit**

```bash
git add dbt/models/marts/monitor_fontes.* dbt/tests/fontes_em_atraso_*.sql
git commit -m "feat(dbt): monitor das fontes e testes de atraso por cadência"
```

---

### Tarefa 8: infraestrutura, CI e documentação

**Arquivos:**
- Modificar: `infra/armazenamento.tf`, `infra/execucao.tf`, `infra/github.tf`, `.github/workflows/ci.yml` e `README.md`

**Interfaces:**
- Produz:
  - os datasets `staging`, `intermediate` e `marts` em produção, editáveis pela conta `pipeline`;
  - leitura dos `raw_*` pela conta `ci-github`;
  - o job `dbt-unitarios` no CI.

- [ ] **Passo 1: Terraform**

Em `infra/armazenamento.tf`, depois do recurso `google_bigquery_dataset.ci`:

```hcl
# Camadas do dbt em produção (em dev, o dbt cria dev_<usuario>_* com a conta de quem roda)
locals {
  datasets_dbt = ["staging", "intermediate", "marts"]
}

resource "google_bigquery_dataset" "dbt" {
  for_each    = toset(local.datasets_dbt)
  dataset_id  = each.value
  location    = var.regiao
  description = "Eleitorado (dbt): ${each.value}"
  depends_on  = [google_project_service.apis]
}
```

Em `infra/execucao.tf`, depois de `pipeline_editor`:

```hcl
resource "google_bigquery_dataset_iam_member" "pipeline_edita_dbt" {
  for_each   = toset(local.datasets_dbt)
  dataset_id = google_bigquery_dataset.dbt[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}
```

Em `infra/github.tf`, no fim:

```hcl
# ci: lê o raw para criar as views vazias do staging (dbt run --empty) antes dos testes unitários
resource "google_bigquery_dataset_iam_member" "ci_le_raw" {
  for_each   = toset(["raw_camara", "raw_senado", "raw_cgu", "raw_ibge"])
  dataset_id = google_bigquery_dataset.prod[each.key].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.ci.email}"
}
```

Rode:
```bash
cd infra && terraform fmt -check && terraform validate && terraform plan -out plano3.tfplan
```
Esperado: `Plan: 10 to add, 0 to change, 0 to destroy`, com 3 datasets, 3 permissões do pipeline e 4 permissões do ci.

**Pare e peça o ok do usuário.** Depois rode `terraform apply plano3.tfplan` e apague `plano3.tfplan`.

- [ ] **Passo 2: job `dbt-unitarios` no CI**

Em `.github/workflows/ci.yml`, acrescente o job:

```yaml
  dbt-unitarios:
    runs-on: ubuntu-latest
    # um de cada vez: todas as execuções usam o mesmo dataset ci
    concurrency:
      group: dbt-ci
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_SA_CI }}
      - name: relações vazias no dataset ci
        run: uv run dbt run --empty --project-dir dbt --profiles-dir dbt --target ci
        env:
          ELEITORADO_PROJETO: ${{ vars.GCP_PROJETO }}
      - name: testes unitários do dbt
        run: uv run dbt test --select "test_type:unit" --project-dir dbt --profiles-dir dbt --target ci
        env:
          ELEITORADO_PROJETO: ${{ vars.GCP_PROJETO }}
```

Confira localmente o mesmo caminho com a sua conta:
```bash
uv run --env-file .env dbt run --empty --project-dir dbt --profiles-dir dbt --target ci
uv run --env-file .env dbt test --select "test_type:unit" --project-dir dbt --profiles-dir dbt --target ci
```
Esperado: 19 modelos OK no dataset `ci`, com 0 bytes processados ou perto disso, e `PASS=6`.

- [ ] **Passo 3: README**

Acrescente ao `README.md`, antes de `## Operação`:

```markdown
## Modelagem (dbt)

- Camadas: `staging` (views sobre o raw), `intermediate` (cota unificada e históricos por eventos)
  e `marts` (dimensões, fatos, alertas e `monitor_fontes`). Em dev, os datasets são
  `dev_<ELEITORADO_USUARIO_DBT>_<camada>`; raw e meta são sempre os de produção.
- Rodar um modelo: `uv run --env-file .env dbt build --project-dir dbt --profiles-dir dbt --target dev --select <modelo>`.
  O projeto inteiro processa cerca de 7,7 GiB; a cota é de 30 GiB por dia.
- LGPD: CPF completo só até `intermediate`. Nos marts, todo CPF sai mascarado (`***.456.789-**`),
  inclusive dentro de nomes; o teste `sem_cpf_completo` roda em todos os marts.
- Reconstruir os históricos a partir dos originais: recarregue cada data no replay
  (`coletor recarregar <recurso> --competencia <data> --destino replay`) e rode
  `dbt build --full-refresh --vars "{fonte_historico: replay}" --select int_cgu__sancoes_eventos+ int_parlamentares__eventos+`.
- Alertas são indícios para investigar, não constatações: a cota reembolsa gastos do parlamentar
  (não é contratação pública) e só aparecem sanções vistas desde a primeira coleta.
```

- [ ] **Passo 4: commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
git add infra .github/workflows/ci.yml README.md
git commit -m "feat(infra): datasets do dbt em produção e testes unitários do dbt no CI"
```

---

### Tarefa 9: produção

- [ ] **Passo 1: PR**

```bash
git push -u origin feat/plano-3-modelagem-dbt
gh pr create --base main --title "Plano 3: modelagem dbt" --body "$(cat <<'CORPO'
Plano 3 (docs/superpowers/plans/2026-10-04-plano-3-modelagem-dbt.md): staging, histórico por
eventos de sanções e parlamentares, cota unificada, dimensões, fatos, alertas de fornecedor
sancionado e de documento inválido, monitor das fontes e testes (LGPD, reconciliação, atraso,
unitários). Infra: datasets do dbt em produção e testes unitários do dbt no CI.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
CORPO
)"
```
Esperado: os jobs `testes`, `imagem` e `dbt-unitarios` do CI verdes.

- [ ] **Passo 2: merge e deploy (só com o ok do usuário)**

Depois do merge, o `deploy.yml` publica a imagem e atualiza o job. Confira:
```bash
gh run list --workflow deploy.yml --limit 1
```
Esperado: `completed success`.

- [ ] **Passo 3: primeira execução em produção (só com o ok do usuário)**

```bash
gcloud run jobs execute pipeline --region southamerica-east1 --wait
bq query --use_legacy_sql=false "select status, dbt_status, dbt_testes_com_erro from meta.execucoes order by iniciada_em desc limit 1"
bq query --use_legacy_sql=false "select table_id, row_count from marts.__TABLES__ order by table_id"
```
Esperado:
- a execução com `sucesso`, `dbt_status` igual a `sucesso` e 0 testes com erro;
- os 8 marts em tabela no dataset `marts`, com as contagens da Tarefa 7. O `monitor_fontes` é view e não aparece em `__TABLES__`.

## Depois deste plano

- A web app lê os marts com uma conta própria, com `dataViewer` só em `marts`.
- O histórico das sanções ganha profundidade a cada dia de coleta. Para recuperar o passado, use o replay a partir dos originais arquivados.
- Pendências menores herdadas dos planos 1 e 2 seguem no backlog. Entre elas: 403 em vez de 412 no GCS, `repository_id` no WIF, actions fixadas por SHA, container sem root, e falha antes de `_rodar_tarefas` sem registro em `meta.execucoes`.
