# Plano 7: onda B2 (contratos do PNCP)

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** coletar os contratos do PNCP de todas as esferas para o raw (lago privado) e unificar os do Executivo federal com os contratos do Portal da Transparência no `fct_contrato_federal`.

**Arquitetura:**
- **Adaptador:** o `api_json` ganha a paginação por número de página (`pagina` até `totalPaginas`) e parâmetros com marcadores.
- **Competência por dia:** cada dia tem cerca de 6 mil contratos. Um mês inteiro (175 mil) não cabe na memória do runner, porque o coletor monta todos os registros antes de converter.
- **Atualizações:** um recurso diário traz as retificações (`/contratos/atualizacao`) dos últimos 7 dias.
- **dbt:** fica com a versão mais recente de cada `numeroControlePNCP`, filtra o Executivo federal e pareia com o Portal por UG, número sem zeros e ano.

**Spec:** [docs/superpowers/specs/2026-10-05-onda-b-emendas-contratos-design.md](../specs/2026-10-05-onda-b-emendas-contratos-design.md), seções 3.2, 4.2, 5.1, 5.4, 6 e 7. As seções "Decisões" abaixo refinam a 4.2.

**Ponto de partida:** `main` com a onda B1 (Plano 6) e a correção de fontes sem dados. Branch `feat/onda-b2`.

## Restrições globais

As do Plano 6 valem integralmente: commits, verificações antes de cada commit, LGPD, itens proibidos ao executor e o fluxo do dbt sobre o lago vazio. O fluxo:

```powershell
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"; $env:ELEITORADO_PUBLICO = "$env:TEMP/eleitorado-publico-b2"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO/marts" | Out-Null
uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
Remove-Item Env:ELEITORADO_LAGO, Env:ELEITORADO_PUBLICO
```

**Ritmo do PNCP:** a API responde `HTTP 429` depois de 5 a 7 requisições rápidas. Use 2 s de pausa entre páginas. Nos testes manuais, não dispare mais de uma coleta por vez.

## Foco de revisão

1. **Dia sem nenhum contrato.** O PNCP responde `204 No Content`, com corpo vazio. Deve virar uma carga com 0 linhas, não uma falha de JSON. Teste `test_pagina_total_com_resposta_vazia` (Tarefa 1).
2. **Contrato retificado.** Vale a versão com o `dataAtualizacaoGlobal` mais recente, venha ela da coleta por dia ou das atualizações. Teste unitário `pncp_fica_com_a_versao_mais_recente` (Tarefa 3).
3. **Pareamento Portal × PNCP:**
   - `000112026` na UG `110096` corresponde a `00011` de 2026 na unidade `110096`;
   - empenhos (`2026NE000397`) ficam só no PNCP;
   - órgão municipal não entra.

   Teste unitário `contrato_federal_pareia_as_duas_fontes` (Tarefa 3).
4. **Carga histórica longa.** Com no máximo 40 dias por execução, os mais recentes primeiro, a execução não passa do tempo limite e a carga é retomável. Teste `test_dias_mais_recentes_primeiro_com_limite` (Tarefa 1).
5. **CPF do fornecedor pessoa física no PNCP** (`niFornecedor` com 11 dígitos). Mascarado no mart; o teste `sem_cpf_completo` cobre (Tarefa 3).

## Decisões de implementação que refinam a spec

- **Competência por dia, não por mês.** A spec previa meses, mas um mês tem cerca de 175 mil registros JSON e passaria de 4 GB de memória no `preparar`. Um dia tem cerca de 6 mil registros e 17 páginas. Entra o tipo de competência `dia` para `por_competencia`, com a partição `DAY` no lago e sem expiração.
- **Cadência `anual`** (365 dias). Os dias dos últimos 30 dias usam `cadencia.corrente` (semanal); os anteriores, `anual`. As retificações de contratos antigos chegam pelo `pncp.contratos_atualizacao` (diário, janela de 7 dias).
- **`limite_por_execucao: 40` dias.** Cerca de 30 minutos por execução, já que cada dia leva uns 45 s. A carga histórica, de 2021-01-01 até hoje, termina em cerca de 50 dias.
- **Marcadores novos:** `{ontem}` e `{semana_passada}` (`AAAAMMDD`, a partir da data de hoje), também nos `parametros`.
- **`ClienteHttp.obter_json`** aceita corpo vazio (`204`) e devolve `dados=None`. **`ClienteHttp.pausar(segundos)`** usa o `dormir` injetado.
- **Um intermediate unificado, `int_contratos_federais`,** com o documento completo. Tanto o `fct_contrato_federal` (com a máscara) quanto o `alerta_contrato_fornecedor_sancionado` passam a ler dele. O mart ganha as colunas `fonte` (`cgu`, `pncp` ou `ambas`), `id_cgu`, `id_pncp` e `tipo_contrato`.
- **Esferas no raw, federal no mart:** o raw guarda todas as esferas, como decidido na conversa. O `stg_pncp__contratos` também tem todas; só o `int_contratos_federais` filtra `esferaId = 'F'` e `poderId = 'E'`.

## Estrutura de arquivos

```
coletor/http.py                 obter_json aceita 204; pausar()
coletor/manifesto.py            competencia.tipo "dia"; cadência "anual"; paginacao "pagina_total";
                                pagina_parametro, total_paginas_campo, pausa_pagina_segundos
coletor/adaptadores/base.py     marcadores {ontem} e {semana_passada}
coletor/adaptadores/api_json.py paginação pagina_total; parâmetros com marcadores
coletor/agenda.py               tarefas diárias; INTERVALO_DIAS["anual"] = 365
coletor/coleta.py               particionamento DAY para por_competencia "dia"
fontes/pncp.yaml                NOVO: pncp.contratos e pncp.contratos_atualizacao
dbt/models/staging/fontes.yml   + source raw_pncp
dbt/models/staging/stg_pncp__contratos.sql        NOVO
dbt/models/intermediate/int_pncp__contratos.sql   NOVO (versão vigente)
dbt/models/intermediate/int_contratos_federais.sql NOVO (Portal + PNCP federal pareados)
dbt/models/intermediate/contratos.yml             NOVO (testes)
dbt/models/marts/fct_contrato_federal.sql         passa a ler int_contratos_federais
dbt/models/marts/alerta_contrato_fornecedor_sancionado.sql  idem
dbt/models/marts/alertas_onda_b.yml               teste unitário com a entrada nova
dbt/tests/contratos_pareamento.sql                NOVO (aviso: taxa de pareamento)
dbt/tests/lago_vazio/esquemas.json                + raw/pncp/*
```

---

### Tarefa 1: competência diária, cadência anual e paginação por página

**Arquivos:** `coletor/http.py`, `coletor/manifesto.py`, `coletor/adaptadores/base.py`, `coletor/adaptadores/api_json.py`, `coletor/agenda.py`, `coletor/coleta.py`, mais os testes correspondentes (`tests/test_http.py`, `tests/test_agenda.py`, `tests/test_adaptador_api_json.py`, `tests/test_utilitarios.py` e `tests/test_manifesto.py`).

- [ ] **Passo 1: testes (falham primeiro).**

Em `tests/test_agenda.py` (use os auxiliares que já existem, como `_mensal` do Plano 6, como modelo):

```python
def _diario(limite=None):
    regra = {"tipo": "dia", "inicio": 2026}
    r = recurso(
        id="contratos",
        publicacao="por_competencia",
        competencia=regra,
        cadencia={"corrente": "semanal", "anteriores": "anual"},
    ).model_copy(update={"limite_por_execucao": limite})
    return RecursoCompleto("pncp", r)


def test_dias_ate_ontem():
    tarefas = tarefas_pendentes([_diario()], HistoricoColetas(), date(2026, 1, 4))
    assert [t.competencia.rotulo for t in tarefas] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_dias_mais_recentes_primeiro_com_limite():
    tarefas = tarefas_pendentes([_diario(limite=2)], HistoricoColetas(), date(2026, 3, 1))
    assert [t.competencia.rotulo for t in tarefas] == ["2026-02-28", "2026-02-27"]
```

Em `tests/test_utilitarios.py`:

```python
def test_marcadores_ontem_e_semana_passada():
    from coletor.adaptadores.base import preencher

    assert preencher("{ontem}-{semana_passada}", None, date(2026, 10, 5)) == "20261004-20260928"
```

Em `tests/test_http.py`, seguindo o padrão `respx` do arquivo:

```python
def test_obter_json_com_204_devolve_dados_vazios(respx_mock, http):
    respx_mock.get("https://api.exemplo/x").mock(return_value=httpx.Response(204))
    resposta = http.obter_json("https://api.exemplo/x")
    assert (resposta.status, resposta.dados) == (204, None)
```

(use a fixture/cliente HTTP que o arquivo já usa; ajuste só a construção).

Em `tests/test_adaptador_api_json.py`:

```python
def _pncp(**sobrescritas):
    return recurso(
        adaptador="api_json",
        url="https://pncp.exemplo/api/contratos",
        parametros={"dataInicial": "{data}", "dataFinal": "{data}", "tamanhoPagina": 500},
        publicacao="por_competencia",
        competencia={"tipo": "dia", "inicio": 2021},
        cadencia={"corrente": "semanal", "anteriores": "anual"},
        formato={"tipo": "json"},
        paginacao="pagina_total",
        registros="data",
        **sobrescritas,
    )


def test_pagina_total_percorre_todas_as_paginas(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://pncp.exemplo/api/contratos")
    rota.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1}], "totalPaginas": 2}),
        httpx.Response(200, json={"data": [{"id": 2}], "totalPaginas": 2}),
    ]
    regra = _pncp()
    competencia = Competencia.de_dia(date(2026, 6, 1))
    extracao = api_json.extrair(regra, competencia, tmp_path, http, date(2026, 6, 2))
    preparado = api_json.preparar(regra, competencia, extracao.arquivo_original, tmp_path)
    assert [r["id"] for r in preparado.registros] == [1, 2]
    pedidas = [dict(chamada.request.url.params) for chamada in rota.calls]
    assert pedidas == [
        {"dataInicial": "20260601", "dataFinal": "20260601", "tamanhoPagina": "500", "pagina": "1"},
        {"dataInicial": "20260601", "dataFinal": "20260601", "tamanhoPagina": "500", "pagina": "2"},
    ]


def test_pagina_total_com_resposta_vazia(respx_mock, http, tmp_path):
    respx_mock.get("https://pncp.exemplo/api/contratos").mock(return_value=httpx.Response(204))
    regra = _pncp()
    competencia = Competencia.de_dia(date(2026, 6, 1))
    extracao = api_json.extrair(regra, competencia, tmp_path, http, date(2026, 6, 2))
    preparado = api_json.preparar(regra, competencia, extracao.arquivo_original, tmp_path)
    assert preparado.registros == []
```

Ajuste os imports (`api_json`, `Competencia`, `date`, `httpx`) e a construção do recurso, se `recurso()` não aceitar algum campo como dicionário.

Em `tests/test_manifesto.py`:

```python
def test_competencia_dia_e_cadencia_anual():
    from coletor.manifesto import RegraCadencia, RegraCompetencia

    assert RegraCompetencia(tipo="dia", inicio=2021).tipo == "dia"
    assert RegraCadencia(corrente="semanal", anteriores="anual").anteriores == "anual"
```

Rode `uv run pytest -q`. Esperado: os testes novos falham.

- [ ] **Passo 2: implementação.**

`coletor/http.py`. Em `obter_json`, troque o `return RespostaJson(...)` por:

```python
            dados = resposta.json() if resposta.content else None  # 204 No Content: sem registros
            return RespostaJson(str(resposta.url), resposta.status_code, resposta.content, dados)
```

E acrescente o método:

```python
    def pausar(self, segundos: float) -> None:
        """Pausa entre requisições (usa o `dormir` injetado, instantâneo nos testes)."""
        if segundos > 0:
            self._dormir(segundos)
```

`coletor/manifesto.py`:
- `Cadencia = Literal["diaria", "semanal", "mensal", "anual"]`.
- `RegraCompetencia.tipo: Literal["ano", "mes", "dia", "data_arquivo", "data_coleta"]`.
- Em `Recurso._coerente`, as tuplas `("ano", "mes")` passam a ser `("ano", "mes", "dia")`, tanto na exigência de `por_competencia` quanto na proibição do `snapshot`. Atualize as mensagens: "competencia.tipo 'ano', 'mes' ou 'dia'".
- Em `Recurso`:
  - `paginacao: Literal["links_next", "nenhuma", "pagina_total"] = "nenhuma"`;
  - `pagina_parametro: str = "pagina"`;
  - `total_paginas_campo: str = "totalPaginas"`;
  - `pausa_pagina_segundos: float = 0`.

`coletor/adaptadores/base.py`. Em `preencher`, logo depois de `valores: dict[str, Any] = {...}`:

```python
    valores["ontem"] = (dia - timedelta(days=1)).strftime("%Y%m%d")
    valores["semana_passada"] = (dia - timedelta(days=7)).strftime("%Y%m%d")
```

Importe `timedelta` e atualize a docstring com os marcadores novos.

`coletor/adaptadores/api_json.py`. Em `extrair`:
- a montagem dos parâmetros vira `parametros_base = {chave: preencher(valor, competencia, hoje) if isinstance(valor, str) else valor for chave, valor in recurso.parametros.items()}`, e `params: dict[str, Any] | None = dict(parametros_base)` dentro do laço de `valores`;
- quando `recurso.paginacao == "pagina_total"`, antes do `while`, faça `params[recurso.pagina_parametro] = 1`;
- no fim do corpo do `while`, troque o bloco a partir de `url, params = None, None` por:

```python
                atual = params
                url, params = None, None
                if recurso.paginacao == "links_next":
                    seguinte = proximo_link(resposta.dados)
                    if seguinte is not None and chave_url(seguinte) not in visitadas:
                        url = seguinte
                elif recurso.paginacao == "pagina_total" and isinstance(resposta.dados, dict):
                    numero = int(atual[recurso.pagina_parametro])
                    total_paginas = int(resposta.dados.get(recurso.total_paginas_campo) or 0)
                    if numero < total_paginas:
                        http.pausar(recurso.pausa_pagina_segundos)
                        url, params = url_base, {**atual, recurso.pagina_parametro: numero + 1}
```

- no registro de cada página, troque `"corpo": resposta.corpo.decode("utf-8")` por `"corpo": resposta.corpo.decode("utf-8") or "null"`.
- `parametros` (o dicionário devolvido na `Extracao`) passa a usar `parametros_base`.

Em `preparar`, use `json.loads(pagina["corpo"] or "null")`; `extrair_registros` já devolve `[]` para `None`.

`coletor/agenda.py`:
- `INTERVALO_DIAS = {"diaria": 1, "semanal": 7, "mensal": 30, "anual": 365}`.
- Em `tarefas_pendentes`, ao lado do ramo `mes`, acrescente o ramo `dia` (usando a mesma lista `do_recurso` e o limite da Tarefa 3A do Plano 6):

```python
        if regra.competencia.tipo == "dia":
            ontem = hoje - timedelta(days=1)
            recentes = hoje - timedelta(days=30)
            dia = date(regra.competencia.inicio, 1, 1)
            while dia <= ontem:
                cadencia = regra.cadencia.corrente if dia >= recentes else regra.cadencia.anteriores
                competencia = Competencia.de_dia(dia)
                if _vencida(historico.ultima_data_sucesso(rc.id, competencia.rotulo), hoje, cadencia):
                    do_recurso.append(Tarefa(rc, competencia))
                dia += timedelta(days=1)
```

Adapte à estrutura atual da função, mantendo o limite e o `tarefas.extend(do_recurso)` no fim. Importe `timedelta`.

`coletor/coleta.py`. Em `particionamento`:

```python
    if recurso.competencia.tipo == "dia":
        return Particionamento("DAY")  # por competência diária: sem expiração
    return Particionamento("MONTH" if recurso.competencia.tipo == "mes" else "YEAR")
```

- [ ] **Passo 3:** pytest verde, ruff e o fluxo do lago vazio verdes. Commit: `feat(coletor): competência diária, cadência anual e paginação por número de página`.

---

### Tarefa 2: recursos do PNCP, coleta real em dev e esquemas

**Arquivos:** `fontes/pncp.yaml` (novo), `tests/test_manifesto.py` e `tests/test_cli.py` (contagem de recursos), `dbt/tests/lago_vazio/esquemas.json` e `dbt/models/staging/fontes.yml`.

- [ ] **Passo 1: manifesto.** `fontes/pncp.yaml`:

```yaml
orgao: pncp
nome: Portal Nacional de Contratações Públicas (PNCP)
portal: https://pncp.gov.br/
recursos:
  - id: contratos
    descricao: Contratos publicados no PNCP por dia (todas as esferas)
    fonte_oficial: https://pncp.gov.br/api/consulta/swagger-ui/index.html
    condicoes_uso: >-
      Dados abertos do PNCP (Lei nº 14.133/2021, art. 174): consulta pública, livre utilização
      com citação da fonte.
    adaptador: api_json
    url: https://pncp.gov.br/api/consulta/v1/contratos
    parametros: {dataInicial: "{data}", dataFinal: "{data}", tamanhoPagina: 500}
    publicacao: por_competencia
    competencia: {tipo: dia, inicio: 2021}
    cadencia: {corrente: semanal, anteriores: anual}
    formato: {tipo: json}
    paginacao: pagina_total
    registros: data
    pausa_pagina_segundos: 2
    limite_por_execucao: 40
  - id: contratos_atualizacao
    descricao: Contratos do PNCP atualizados nos últimos 7 dias (retificações)
    fonte_oficial: https://pncp.gov.br/api/consulta/swagger-ui/index.html
    condicoes_uso: >-
      Dados abertos do PNCP (Lei nº 14.133/2021, art. 174): consulta pública, livre utilização
      com citação da fonte.
    adaptador: api_json
    url: https://pncp.gov.br/api/consulta/v1/contratos/atualizacao
    parametros: {dataInicial: "{semana_passada}", dataFinal: "{ontem}", tamanhoPagina: 500}
    publicacao: snapshot
    competencia: {tipo: data_coleta}
    cadencia: {corrente: diaria}
    formato: {tipo: json}
    paginacao: pagina_total
    registros: data
    pausa_pagina_segundos: 2
```

Atualize as contagens de recursos nos testes, de 14 para 16. Rode o pytest.

- [ ] **Passo 2: coleta real em dev, no lago `dados-b1` do Plano 6.** Com o `.env` carregado:

```powershell
$env:ELEITORADO_AMBIENTE = "dev"; $env:ELEITORADO_PREFIXO = ""; $env:ELEITORADO_LAGO = "dados-b1"
uv run coletor coletar pncp.contratos --competencia 2026-06-01
uv run coletor coletar pncp.contratos --competencia 2026-06-02
uv run coletor coletar pncp.contratos_atualizacao
```

A CLI `coletar` precisa aceitar `--competencia AAAA-MM-DD` para recursos `dia`. Se ela recusar, estenda a validação de `_coletar` em `coletor/cli.py`: o comprimento do rótulo esperado passa a ser 4 (ano), 7 (mês) ou 10 (dia), conforme `rc.recurso.competencia.tipo`. Inclua um teste em `tests/test_cli.py` para `--competencia 2026-06-01` num recurso diário (use a fixture `deps` e um mock `respx` da URL do PNCP que devolva `{"data": [], "totalPaginas": 0}`).

Esperado: três coletas `carregada`. As de um dia têm milhares de linhas cada; a de atualização deve ter muito mais. Relate as linhas `status=`, os tempos e se apareceu algum `429` (nos logs do httpx).

**Atenção:** se `contratos_atualizacao` tiver mais de 150 mil registros e o processo ficar lento ou estourar memória, pare e relate. Nesse caso a janela de 7 dias será reduzida.

- [ ] **Passo 3: sources e esquemas.** Em `dbt/models/staging/fontes.yml`, acrescente depois de `raw_ibge`:

```yaml
  - name: raw_pncp
    meta:
      external_location: "read_parquet('{{ env_var('ELEITORADO_LAGO', 'dados') }}/raw/pncp/{name}/*/*.parquet', union_by_name = true)"
    tables:
      - name: contratos
      - name: contratos_atualizacao
```

Rode `uv run python scripts/lago_vazio.py --de-lago dados-b1`.
Esperado: `esquemas.json` ganha `raw/pncp/contratos` e `raw/pncp/contratos_atualizacao`, só com acréscimos.

- [ ] **Passo 4:** pytest, ruff e o fluxo do lago vazio verdes. Commit: `feat(fontes): contratos do PNCP (por dia e atualizações)`.

---

### Tarefa 3: staging, versão vigente e unificação dos contratos federais

**Arquivos:**
- `dbt/models/staging/stg_pncp__contratos.sql`;
- `dbt/models/intermediate/int_pncp__contratos.sql`, `int_contratos_federais.sql` e `contratos.yml`;
- `dbt/models/marts/fct_contrato_federal.sql` e `alerta_contrato_fornecedor_sancionado.sql`;
- `dbt/models/marts/alertas_onda_b.yml` e `compras.yml`;
- `dbt/tests/contratos_pareamento.sql`.

- [ ] **Passo 1: testes (falham primeiro).** `dbt/models/intermediate/contratos.yml`:

```yaml
version: 2

models:
  - name: int_pncp__contratos
    columns:
      - name: contrato_pncp_id
        data_tests: [unique, not_null]
  - name: int_contratos_federais
    columns:
      - name: contrato_id
        data_tests: [unique, not_null]
      - name: fonte
        data_tests:
          - accepted_values:
              arguments: {values: [cgu, pncp, ambas]}

unit_tests:
  - name: pncp_fica_com_a_versao_mais_recente
    model: int_pncp__contratos
    given:
      - input: ref('stg_pncp__contratos')
        rows:
          - {contrato_pncp_id: 'X-2-1/2026', data_atualizacao: '2026-06-01 10:00:00', valor_global: 100, origem: publicacao}
          - {contrato_pncp_id: 'X-2-1/2026', data_atualizacao: '2026-06-10 10:00:00', valor_global: 150, origem: atualizacao}
          - {contrato_pncp_id: 'Y-2-1/2026', data_atualizacao: '2026-06-01 10:00:00', valor_global: 70, origem: publicacao}
    expect:
      rows:
        - {contrato_pncp_id: 'X-2-1/2026', valor_global: 150}
        - {contrato_pncp_id: 'Y-2-1/2026', valor_global: 70}

  - name: contrato_federal_pareia_as_duas_fontes
    description: >
      Portal 000112026 na UG 110096 pareia com o PNCP número 00011 de 2026 na unidade 110096
      (vale o PNCP); empenho do PNCP sem par fica só no PNCP; contrato do Portal sem par fica;
      órgão municipal do PNCP não entra.
    model: int_contratos_federais
    given:
      - input: ref('int_cgu__contratos')
        rows:
          - {contrato_id: 'cgu:110096:000112026', ug_codigo: '110096', contrato_numero: '000112026', data_assinatura: '2026-05-29'}
          - {contrato_id: 'cgu:170175:000032026', ug_codigo: '170175', contrato_numero: '000032026', data_assinatura: '2026-06-09'}
      - input: ref('int_pncp__contratos')
        rows:
          - {contrato_pncp_id: 'A-2-1/2026', esfera: F, poder: E, unidade_codigo: '110096', numero_contrato: '00011', ano_contrato: 2026, tipo_contrato: 'Contrato (termo inicial)'}
          - {contrato_pncp_id: 'B-2-2/2026', esfera: F, poder: E, unidade_codigo: '154051', numero_contrato: '2026NE000397', ano_contrato: 2026, tipo_contrato: Empenho}
          - {contrato_pncp_id: 'C-2-3/2026', esfera: M, poder: E, unidade_codigo: '000000002', numero_contrato: '219', ano_contrato: 2026, tipo_contrato: 'Contrato (termo inicial)'}
    expect:
      rows:
        - {contrato_id: 'pncp:A-2-1/2026', fonte: ambas, id_cgu: 'cgu:110096:000112026', id_pncp: 'A-2-1/2026'}
        - {contrato_id: 'pncp:B-2-2/2026', fonte: pncp, id_cgu: null, id_pncp: 'B-2-2/2026'}
        - {contrato_id: 'cgu:170175:000032026', fonte: cgu, id_cgu: 'cgu:170175:000032026', id_pncp: null}
```

Em `dbt/models/marts/alertas_onda_b.yml`, no teste unitário `contrato_com_fornecedor_sancionado_na_assinatura`, troque `input: ref('int_cgu__contratos')` por `input: ref('int_contratos_federais')`. Mantenha as mesmas linhas, cujas colunas existem no modelo novo.

Rode o fluxo do lago vazio e confirme a falha (modelos inexistentes).

- [ ] **Passo 2: modelos.**

`dbt/models/staging/stg_pncp__contratos.sql`:

```sql
-- Contratos do PNCP (todas as esferas): os publicados por dia e as atualizações recentes.
-- Uma linha por versão coletada; a vigente é escolhida em int_pncp__contratos.
with origem as (
    select _coleta_id, payload, 'publicacao' as origem from {{ source('raw_pncp', 'contratos') }}
    union all
    select _coleta_id, payload, 'atualizacao' as origem from {{ source('raw_pncp', 'contratos_atualizacao') }}
)

select
    _coleta_id,
    origem,
    json_extract_string(payload, '$.numeroControlePNCP') as contrato_pncp_id,
    json_extract_string(payload, '$.numeroControlePncpCompra') as compra_pncp_id,
    json_extract_string(payload, '$.orgaoEntidade.cnpj') as orgao_cnpj,
    json_extract_string(payload, '$.orgaoEntidade.razaoSocial') as orgao_nome,
    json_extract_string(payload, '$.orgaoEntidade.esferaId') as esfera,
    json_extract_string(payload, '$.orgaoEntidade.poderId') as poder,
    json_extract_string(payload, '$.unidadeOrgao.codigoUnidade') as unidade_codigo,
    json_extract_string(payload, '$.unidadeOrgao.nomeUnidade') as unidade_nome,
    json_extract_string(payload, '$.unidadeOrgao.ufSigla') as uf_sigla,
    json_extract_string(payload, '$.unidadeOrgao.codigoIbge') as municipio_id,
    try_cast(json_extract_string(payload, '$.anoContrato') as integer) as ano_contrato,
    json_extract_string(payload, '$.numeroContratoEmpenho') as numero_contrato,
    json_extract_string(payload, '$.processo') as processo,
    json_extract_string(payload, '$.tipoContrato.nome') as tipo_contrato,
    json_extract_string(payload, '$.categoriaProcesso.nome') as categoria_processo,
    json_extract_string(payload, '$.objetoContrato') as objeto,
    {{ documento_fonte("json_extract_string(payload, '$.niFornecedor')") }} as fornecedor_documento,
    {{ tipo_documento_fonte("json_extract_string(payload, '$.niFornecedor')") }} as fornecedor_tipo_documento,
    json_extract_string(payload, '$.nomeRazaoSocialFornecedor') as fornecedor_nome,
    {{ numero("json_extract_string(payload, '$.valorInicial')") }} as valor_inicial,
    {{ numero("json_extract_string(payload, '$.valorGlobal')") }} as valor_global,
    {{ numero("json_extract_string(payload, '$.valorAcumulado')") }} as valor_acumulado,
    try_cast(json_extract_string(payload, '$.dataAssinatura') as date) as data_assinatura,
    try_cast(json_extract_string(payload, '$.dataVigenciaInicio') as date) as data_inicio_vigencia,
    try_cast(json_extract_string(payload, '$.dataVigenciaFim') as date) as data_fim_vigencia,
    try_cast(json_extract_string(payload, '$.dataPublicacaoPncp') as timestamp) as data_publicacao,
    try_cast(json_extract_string(payload, '$.dataAtualizacaoGlobal') as timestamp) as data_atualizacao,
    try_cast(json_extract_string(payload, '$.numeroRetificacao') as integer) as numero_retificacao,
    json_extract_string(payload, '$.emendaParlamentar') as emenda_parlamentar
from origem
```

`dbt/models/intermediate/int_pncp__contratos.sql`:

```sql
-- Versão vigente de cada contrato do PNCP (a de atualização mais recente), com o documento
-- completo do fornecedor.
select
    *,
    case fornecedor_tipo_documento
        when 'CPF' then {{ documento_valido('fornecedor_documento') }}
        when 'CNPJ' then {{ documento_valido('fornecedor_documento') }}
        when 'INVALIDO' then false
    end as fornecedor_documento_valido,
    if(fornecedor_tipo_documento = 'CNPJ', substr(fornecedor_documento, 1, 8), null) as fornecedor_cnpj_raiz
from {{ ref('stg_pncp__contratos') }}
where contrato_pncp_id is not null
qualify row_number() over (
    partition by contrato_pncp_id
    order by data_atualizacao desc nulls last, numero_retificacao desc nulls last, origem
) = 1
```

`dbt/models/intermediate/int_contratos_federais.sql`:

```sql
-- Contratos do Poder Executivo federal das duas fontes, com o documento completo (para os alertas).
-- Par Portal x PNCP: UG/unidade + número do contrato sem zeros à esquerda + ano. Havendo par, vale
-- o PNCP (chave nacional e retificações). Empenhos do PNCP não existem no Portal e ficam só no PNCP.
with cgu as (
    select
        *,
        -- NNNNNAAAA: número + ano; fora desse formato não há par (concat ignoraria nulos)
        case when regexp_matches(contrato_numero, '^[0-9]{5,}$') then concat(
            ug_codigo, '|',
            ltrim(left(contrato_numero, length(contrato_numero) - 4), '0'), '|',
            right(contrato_numero, 4)
        ) end as par
    from {{ ref('int_cgu__contratos') }}
),

pncp as (
    select
        *,
        -- só números puramente numéricos têm par (empenhos como 2026NE000397 ficam sem)
        case when regexp_matches(numero_contrato, '^[0-9]+$') and ano_contrato is not null then concat(
            unidade_codigo, '|', ltrim(numero_contrato, '0'), '|', cast(ano_contrato as varchar)
        ) end as par
    from {{ ref('int_pncp__contratos') }}
    where esfera = 'F' and poder = 'E'
),

unidas as (
    select
        coalesce('pncp:' || p.contrato_pncp_id, c.contrato_id) as contrato_id,
        c.contrato_id as id_cgu,
        p.contrato_pncp_id as id_pncp,
        case
            when p.contrato_pncp_id is not null and c.contrato_id is not null then 'ambas'
            when p.contrato_pncp_id is not null then 'pncp'
            else 'cgu'
        end as fonte,
        coalesce(p.numero_contrato, c.contrato_numero) as contrato_numero,
        coalesce(p.unidade_codigo, c.ug_codigo) as ug_codigo,
        coalesce(p.unidade_nome, c.ug_nome) as ug_nome,
        coalesce(p.orgao_nome, c.orgao_nome) as orgao_nome,
        c.orgao_superior_nome,
        coalesce(p.objeto, c.objeto) as objeto,
        p.tipo_contrato,
        c.modalidade,
        coalesce(p.data_assinatura, c.data_assinatura) as data_assinatura,
        coalesce(p.data_inicio_vigencia, c.data_inicio_vigencia) as data_inicio_vigencia,
        coalesce(p.data_fim_vigencia, c.data_fim_vigencia) as data_fim_vigencia,
        coalesce(p.fornecedor_documento, c.fornecedor_documento) as fornecedor_documento,
        coalesce(p.fornecedor_tipo_documento, c.fornecedor_tipo_documento) as fornecedor_tipo_documento,
        coalesce(p.fornecedor_documento_valido, c.fornecedor_documento_valido) as fornecedor_documento_valido,
        coalesce(p.fornecedor_cnpj_raiz, c.fornecedor_cnpj_raiz) as fornecedor_cnpj_raiz,
        coalesce(p.fornecedor_nome, c.fornecedor_nome) as fornecedor_nome,
        coalesce(p.valor_inicial, c.valor_inicial) as valor_inicial,
        coalesce(p.valor_global, c.valor_final) as valor_final,
        p.compra_pncp_id,
        c.licitacao_numero,
        p.emenda_parlamentar,
        coalesce(p._coleta_id, c._coleta_id) as _coleta_id
    from pncp as p
    full join cgu as c
        on c.par = p.par
)

select *
from unidas
qualify row_number() over (partition by contrato_id order by id_cgu nulls last) = 1
```

Substitua `dbt/models/marts/fct_contrato_federal.sql` por:

```sql
-- Contratos do Poder Executivo federal (Portal da Transparência, 2013 em diante, e PNCP, 2021 em
-- diante, pareados). CPF mascarado.
select
    contrato_id,
    id_cgu,
    id_pncp,
    fonte,
    contrato_numero,
    ug_codigo,
    {{ mascarar_cpfs_em_texto('ug_nome') }} as ug_nome,
    orgao_nome,
    orgao_superior_nome,
    {{ mascarar_cpfs_em_texto('objeto') }} as objeto,
    tipo_contrato,
    modalidade,
    data_assinatura,
    data_inicio_vigencia,
    data_fim_vigencia,
    {{ documento_publico('fornecedor_documento') }} as fornecedor_documento,
    fornecedor_tipo_documento,
    fornecedor_documento_valido,
    fornecedor_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    valor_inicial,
    valor_final,
    compra_pncp_id,
    licitacao_numero,
    emenda_parlamentar,
    _coleta_id
from {{ ref('int_contratos_federais') }}
```

Em `dbt/models/marts/compras.yml`, em `fct_contrato_federal`, o `excluir` do `sem_cpf_completo` passa a ser `[contrato_numero, licitacao_numero, compra_pncp_id, id_pncp, id_cgu, emenda_parlamentar]`.

Em `dbt/models/marts/alerta_contrato_fornecedor_sancionado.sql`, troque `from {{ ref('int_cgu__contratos') }}` por `from {{ ref('int_contratos_federais') }}`. As colunas usadas existem com o mesmo nome no modelo novo; `ug_nome` e `orgao_nome` também.

`dbt/tests/contratos_pareamento.sql`:

```sql
{{ config(severity='warn') }}

-- Aviso quando, nos anos em que as duas fontes se sobrepõem, menos da metade dos contratos
-- federais do PNCP (sem contar empenhos) encontra par no Portal: a regra de pareamento pode ter
-- enfraquecido.
with pncp as (
    select fonte
    from {{ ref('int_contratos_federais') }}
    where id_pncp is not null
        and tipo_contrato ilike 'contrato%'
        and year(data_assinatura) between 2022 and year(current_date) - 1
)

select count(*) as contratos, count_if(fonte = 'ambas') as pareados
from pncp
having count(*) > 0 and count_if(fonte = 'ambas') < 0.5 * count(*)
```

- [ ] **Passo 3: validação.** Rode o fluxo do lago vazio.
Esperado: `ERROR=0`, com os testes unitários novos e o do alerta de contrato passando.

Prova de mutação: em `int_contratos_federais`, do lado do PNCP, troque `ltrim(numero_contrato, '0')` por `numero_contrato` (sem tirar os zeros) e rode `--select "int_contratos_federais,test_type:unit"`. Esperado: FAIL. Restaure.

No lago real (`dados-b1`), rode `dbt build ... --select +fct_contrato_federal +alerta_contrato_fornecedor_sancionado contratos_pareamento --exclude-resource-type unit_test`.
Esperado: `ERROR=0`. Relate:
- quantas linhas tem `int_pncp__contratos` por `esfera`;
- quantas `int_contratos_federais` tem por `fonte`;
- quantas das linhas `pncp` são empenhos e quantas são contratos;
- a contagem de `alerta_contrato_fornecedor_sancionado`;
- o resultado do `contratos_pareamento`.

Como o lago só tem 2 dias do PNCP, o pareamento ficará baixo: o aviso é esperado e não bloqueia.

- [ ] **Passo 4:** pytest, ruff e o fluxo do lago vazio verdes. Commit: `feat(dbt): contratos do PNCP unificados aos do Portal no fct_contrato_federal`.

---

### Tarefa 4: documentação e integração (com o usuário)

- [ ] **Passo 1:** em "Coletor (onda A)" no README, acrescente: "Onda B2: contratos do PNCP (todas as esferas no lago privado; o Executivo federal é unificado aos contratos do Portal no `fct_contrato_federal`)."
- [ ] **Passo 2:** rode o build completo no lago real, como no Plano 6 (Tarefa 8, passo 2). Esperado: `ERROR=0`. Relate a linha `Done.`.
- [ ] **Passo 3:** commit `docs: onda B2 no README`.
- [ ] **Passo 4 (Claude, com o ok do usuário):** push, PR, CI, merge e disparo do `pipeline.yml`. A carga histórica do PNCP avança 40 dias por execução, por cerca de 50 execuções. Confira:
  - os tempos do passo "coleta e dbt", que deve ficar abaixo de 60 minutos;
  - possíveis `adiada` por `429`;
  - o tamanho do cache (estimativa de cerca de 5 GB ao fim da carga).

## Depois deste plano

- **Virada (Plano 5),** promovendo `paralelo/` para a raiz.
- **Ligação entre emendas e contratos** pelo campo `emendaParlamentar` do PNCP.
- **Identificação de quem foi deputado e senador** (melhora a ligação dos autores de emenda).
