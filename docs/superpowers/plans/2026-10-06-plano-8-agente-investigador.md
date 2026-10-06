# Plano 8: agente investigador L1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** um agente L1 que investiga os dados do eleitorado num laço Sense-Think-Act, valida cada
achado com um validador independente (e pesquisa na web) e gera relatórios HTML autocontidos, sem
autonomia de decisão.

**Architecture:** pacote `agente/` com um controlador Python (máquina de estados persistida) que
abre uma sessão `claude -p` por fase. Os agentes (`.claude/agents/investigador.md` e
`validador.md`) não têm shell nem acesso a arquivos: só as ferramentas de um servidor MCP próprio
(consultas SELECT num DuckDB só de leitura e com diretórios restritos, caderno de casos, registro
de hipóteses, achados e vereditos), `WebSearch` e `WebFetch`, com um hook que bloqueia CPF nas
buscas. O `preparar` copia o lago de produção para `dados-agente/` e roda o dbt no target
`agente`.

**Tech Stack:** Python 3.12, uv, DuckDB 1.5.6, pyarrow, pydantic 2, MCP Python SDK 2.3
(`MCPServer`), Jinja2, Vega 6.4.0 / Vega-Lite 6.4.3 / vega-embed 7.3.0 (embutidos), Claude Code
2.1.273 (`claude -p`), dbt-duckdb, PowerShell 5.1 (Agendador de Tarefas).

**Spec:** `docs/superpowers/specs/2026-10-06-agente-investigador-design.md` (a seção 11 prevalece:
revisões depois do protótipo).

## Como este plano é executado

Todo o código foi escrito e validado num protótipo, no branch local **`proto/agente`** (a partir
de `c217ccb`), inclusive sessões reais `claude -p` com o servidor MCP, o hook e o executor, o
`preparar` real contra o lago de produção e a avaliação real com casos plantados. O conteúdo de cada arquivo é o do
**último commit** desse branch; o plano não o repete.

Cada tarefa:

1. traz os arquivos da tarefa com `git checkout proto/agente -- <arquivos>`;
2. roda os testes da tarefa e confere a contagem esperada;
3. faz a **prova de mutação** indicada (estraga de propósito uma trava, vê o teste falhar,
   restaura com `git checkout -- <arquivo>` e vê passar de novo), para provar que os testes
   protegem o que dizem proteger;
4. roda `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest -q`;
5. faz o commit com a mensagem indicada.

Os arquivos de cada tarefa só importam módulos de tarefas anteriores, então cada commit fica
verde sozinho.

## Global Constraints

- Branch de trabalho: `feat/agente-investigador`, criado a partir da `main` atual. Nunca commitar
  em `main` (protegida: só por PR com o check `testes`).
- Nada de `dados-agente/`, `investigacoes/`, `avaliacao/`, `.env*` ou `.claude/settings*` no git
  (o `.gitignore` da tarefa 1 e da tarefa 8 cobre).
- O agente nunca tem `Bash`, `Read`, `Write` ou `Edit`: só `mcp__agente__*`, `WebSearch` e `WebFetch`.
- O banco do agente é aberto com `read_only=True`, `allowed_directories` (lago e marts) e
  `enable_external_access = false`, nessa ordem; só instruções do tipo `SELECT` passam.
- CPF nunca sai da máquina numa busca (hook) e nunca aparece completo no HTML (máscara).
- Linhas de até 100 colunas (`ruff`), código e textos em português.
- Toda mensagem de commit termina com:
  ```
  Co-Authored-By: Gemini <noreply@google.com>
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```

## Review Focus

1. **Agente tentando ler fora do lago** (`read_text`, `read_parquet('../..')`, `getenv`,
   `ATTACH`, `COPY` para dentro do lago): tudo recusado com mensagem que chega ao agente
   (`test_consulta.py`, `test_servidor.py::test_erro_da_ferramenta_chega_ao_agente`).
2. **Sessão que cai no meio** (limite de uso da assinatura, máquina desligada, achado registrado e
   ainda sem veredito): retoma sem refazer o que já foi feito
   (`test_controlador.py::test_limite_de_uso_pausa_e_retoma_sem_refazer`,
   `::test_retoma_investigacao_com_achado_registrado_e_sem_veredito`).
3. **Investigador tentando se autoconfirmar:** só o veredito do validador muda a situação; o
   validador não tem `achado_registrar`; o investigador não tem `veredito_registrar`
   (`test_servidor.py::test_ferramentas_por_papel`, `test_controlador.py`).
4. **Conteúdo hostil nos dados ou na web** (`<script>`, apóstrofo em nome, CPF em texto livre):
   escapado e mascarado no HTML (`test_relatorio.py::test_conteudo_externo_e_escapado`,
   `::test_html_autocontido_mascarado_e_com_links`).
5. **Marts particionados sem colunas de partição** no banco do agente (`casa`, `ano`): corrigidos
   pelo `preparar` (`test_preparar.py::test_corrigir_particoes_devolve_as_colunas_de_particao`).

## Rulings do protótipo (em relação à spec)

Registrados na seção 11 da spec: ferramentas por MCP em vez de CLI por Bash (o `dontAsk` libera
comandos de leitura sozinho); `ErroFerramenta(ToolError)`; veredito por ferramenta; valores só nos
fatos; reabertura de casos pelas consultas-chave; views particionadas; disco de ~4 GB; dia e hora
do agendamento em `agendar.ps1`; armadilha de homônimo de empresa; relatório recusado vira
`parcial`; orçamento com reserva por hipótese, validação mínima e resumo garantido (padrões de
120 e 80 ciclos, medidos na avaliação real).

---

### Tarefa 1: Consulta travada, diário e configuração

**Files:**
- Create: `agente/__init__.py`, `agente/config.py`, `agente/config.toml`, `agente/diario.py`,
  `agente/consulta.py`, `agente/estaticos/vega.min.js`, `agente/estaticos/vega-lite.min.js`,
  `agente/estaticos/vega-embed.min.js`, `tests/agente/__init__.py`, `tests/agente/conftest.py`,
  `tests/agente/test_config.py`, `tests/agente/test_consulta.py`
- Modify: `.gitignore` (acrescenta `dados-agente/`, `investigacoes/`, `avaliacao/`)

**Interfaces:**
- Produces: `ConfigAgente` (`raiz, lago, investigacoes, prefixo_gcs, modelo, tempo_consulta_s,
  linhas_exibidas, linhas_salvas, livre, tema`; propriedades `banco`, `publico`, `caderno`;
  `diretorios_permitidos()`, `orcamento(tema)`), `carregar(arquivo=ARQUIVO, raiz=RAIZ)`,
  `Orcamento(ciclos, minutos, hipoteses, rodadas_validacao)`; `Diario(pasta)` com `proximo_id()`,
  `caminho_resultado(id)`, `registrar(RegistroConsulta)`, `consultas() -> dict[str,
  RegistroConsulta]`; `validar_sql(sql) -> str`, `abrir(banco, diretorios, memoria="4GB")`,
  `executar(conexao, sql, diario, papel, tempo_maximo_s, linhas_exibidas, linhas_salvas) ->
  ResultadoConsulta(id, linhas, truncada, texto)`, `ErroConsulta`.

- [ ] **Passo 1:** `git checkout main; git pull; git checkout -b feat/agente-investigador`.
- [ ] **Passo 2:** `git checkout proto/agente -- agente/__init__.py agente/config.py agente/config.toml agente/diario.py agente/consulta.py agente/estaticos tests/agente/__init__.py tests/agente/conftest.py tests/agente/test_config.py tests/agente/test_consulta.py`.
  No `.gitignore`, acrescente ao fim:
  ```
  # agente investigador: lago local de produção e investigações (dados pessoais; nunca no git)
  dados-agente/
  investigacoes/
  avaliacao/
  ```
- [ ] **Passo 3:** `uv run pytest -q tests/agente`. Esperado: **21 passed**.
- [ ] **Passo 4 (mutação):** em `agente/consulta.py`, apague a linha
  `conexao.execute("set enable_external_access = false")`. Rode
  `uv run pytest -q tests/agente/test_consulta.py`: `test_arquivo_fora_do_lago_e_bloqueado` **deve
  falhar**. Restaure com `git checkout -- agente/consulta.py` e confirme 21 passed.
- [ ] **Passo 5:** ruff e pytest completos verdes. Commit:
  `feat(agente): consulta só de leitura com diretórios restritos, diário e configuração`.

### Tarefa 2: Modelos, estado, caderno de casos e hook anti-CPF

**Files:**
- Create: `agente/modelos.py`, `agente/estado.py`, `agente/caderno.py`, `agente/hook_web.py`,
  `tests/agente/test_modelos.py`, `tests/agente/test_caderno.py`, `tests/agente/test_hook_web.py`
- Modify: `pyproject.toml`, `uv.lock` (dependências `mcp>=2.3.0` e `jinja2>=3.1.6`)

**Interfaces:**
- Produces (modelos): `NovaHipotese(texto, lente, prioridade, entidades)`,
  `Hipotese(NovaHipotese) + id, situacao, rodadas, motivo, origem, caso_id`,
  `Afirmacao(texto, consultas)`, `FonteWeb(url, titulo, acessado_em, trecho)`,
  `Grafico(tipo, titulo, consulta, x, y, cor, destaque, origem, destino, peso)`,
  `Achado(hipotese_id, tipo, padrao, titulo, entidades, fatos, indicios, hipoteses, fontes_web,
  graficos, recomendacoes)` com `consultas_citadas()` e a regra de valores (`tem_valor`),
  `Alternativa`, `Veredito(decisao, justificativa, alternativas, pendencias,
  corroboracao_independente, fontes_web)`, `Correlacionado`, `Resumo(texto, destaques)`,
  `RegistroAchado(id, achado, vereditos, situacao, confianca, correlacionados)`, `Uso`,
  `Transicao`, `Estado(...)` com `hipotese(id)` e `achado(id)`.
- Produces (estado): `salvar(pasta, estado)`, `carregar(pasta)`, `existe(pasta)`.
- Produces (caderno): `Caso`, `ConsultaChave(sql, linhas, soma)`, `EntradaHistorico`,
  `caso_id(padrao, entidades)`, `mudou(anterior, linhas, soma)`, `Caderno(pasta)` com `obter`,
  `salvar`, `listar(situacao)`, `buscar(termo)`, `registrar(registro, investigacao, dia,
  relatorio, consultas_chave, agora)`, `aprendizados()`, `aprender(texto, investigacao, dia)`.
- Produces (hook): `motivo_bloqueio(evento) -> str | None`, `main(entrada, erro) -> int`,
  executável por `python -m agente.hook_web`.

- [ ] **Passo 1:** `git checkout proto/agente -- agente/modelos.py agente/estado.py agente/caderno.py agente/hook_web.py tests/agente/test_modelos.py tests/agente/test_caderno.py tests/agente/test_hook_web.py`
  e `uv add "mcp>=2.3.0" "jinja2>=3.1.6"`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente`. Esperado: **45 passed**.
- [ ] **Passo 3 (mutação):** em `agente/hook_web.py`, troque `[.\s]?` por `\.?` nas duas primeiras
  ocorrências do `PADRAO_CPF`. `test_bloqueia_onze_digitos[123 456 789 09]` **deve falhar**.
  Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(agente): modelos de hipóteses, achados e vereditos, caderno de casos e hook anti-CPF`.

### Tarefa 3: Servidor MCP com ferramentas por papel, fase e alvo

**Files:**
- Create: `agente/servidor.py`, `tests/agente/test_servidor.py`

**Interfaces:**
- Consumes: Tarefas 1 e 2.
- Produces: `FERRAMENTAS_POR_PAPEL` (investigador: `consultar, caderno_buscar,
  caderno_aprender, hipoteses_registrar, hipotese_descartar, achado_registrar,
  correlacionados_registrar, resumo_registrar`; validador: `consultar, caderno_buscar,
  veredito_registrar`), `Sessao(pasta, papel, fase, alvo, config)` e
  `Sessao.do_ambiente(env, config)` (`AGENTE_INVESTIGACAO`, `AGENTE_PAPEL`, `AGENTE_FASE`,
  `AGENTE_ALVO`), `Ferramentas(sessao, abrir_conexao=None, hoje=date.today)`,
  `ErroFerramenta(ToolError)`, `criar_servidor(ferramentas)`, `main()` (lê `AGENTE_CONFIG` quando
  definido).

- [ ] **Passo 1:** `git checkout proto/agente -- agente/servidor.py tests/agente/test_servidor.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente`. Esperado: **55 passed**.
- [ ] **Passo 3 (mutação):** em `FERRAMENTAS_POR_PAPEL["validador"]`, acrescente
  `"achado_registrar"`. `test_ferramentas_por_papel` **deve falhar**. Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(agente): servidor MCP com ferramentas por papel, fase e alvo`.

### Tarefa 4: Executor das sessões e rastro Sense-Think-Act

**Files:**
- Create: `agente/executor.py`, `agente/permissoes.json`, `tests/agente/test_executor.py`

**Interfaces:**
- Produces: `Limites(ciclos, segundos, repeticoes=3)`, `PedidoSessao(agente, fase, alvo, prompt,
  pasta)`, `ResultadoSessao(parada, ciclos, segundos, texto_final, detalhe)` com `parada` em
  `concluida | orcamento_ciclos | orcamento_tempo | repeticao | limite_uso | erro`, protocolo
  `Executor.rodar(pedido, limites)`, `Monitor(pedido, limites, agora)` (grava
  `investigacoes/<id>/ciclos.jsonl` com etapas `think`, `act`, `sense`),
  `ExecutorClaude(raiz, modelo=None, comando=None, arquivo_config=None)` com
  `configuracao_mcp(pedido)`, `comando_sessao(pedido, arquivo_mcp)` e `rodar`;
  `encerrar_processo(processo)` (no Windows, `taskkill /T /F`).
- `agente/permissoes.json`: `permissions.allow` com as 9 ferramentas `mcp__agente__*`,
  `WebSearch` e `WebFetch`, `defaultMode: dontAsk`; hook `PreToolUse` com matcher
  `WebSearch|WebFetch` e comando `uv run python -m agente.hook_web`.

- [ ] **Passo 1:** `git checkout proto/agente -- agente/executor.py agente/permissoes.json tests/agente/test_executor.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente`. Esperado: **65 passed**.
- [ ] **Passo 3 (mutação):** em `Monitor.evento`, troque `>= self.limites.repeticoes` por
  `> self.limites.repeticoes`. `test_repeticao_da_mesma_acao` **deve falhar**. Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(agente): executor das sessões claude -p com rastro Sense-Think-Act e limites`.

### Tarefa 5: Relatório HTML, gráficos e índice

**Files:**
- Create: `agente/graficos.py`, `agente/relatorio.py`, `agente/html/estilo.css`,
  `agente/html/relatorio.html.j2`, `agente/html/indice.html.j2`, `tests/agente/test_relatorio.py`

**Interfaces:**
- Produces (graficos): `mascarar(texto)`, `linhas(tabela, limite=5000)`,
  `especificacao(grafico, tabela) -> dict` (Vega-Lite: barras, linha, dispersão, distribuição),
  `rede_svg(grafico, tabela) -> str`.
- Produces (relatorio): `ErroRelatorio`, `confianca(veredito)` (`alta` com corroboração
  independente, senão `média`), `resumo_ciclos(arquivo)`, `montar(estado, pasta, gerado_em)`,
  `validar(relatorio)`, `renderizar(relatorio, pasta)`, `gerar(estado, pasta, gerado_em) ->
  Path` (grava `relatorio.json` e `relatorio.html`), `gerar_indice(investigacoes) -> Path`.

- [ ] **Passo 1:** `git checkout proto/agente -- agente/graficos.py agente/relatorio.py agente/html tests/agente/test_relatorio.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente`. Esperado: **75 passed**.
- [ ] **Passo 3 (mutação):** em `relatorio._finalizar`, troque `return graficos.mascarar(valor)` por
  `return valor`. `test_html_autocontido_mascarado_e_com_links` **deve falhar**. Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(agente): relatório HTML autocontido com gráficos Vega-Lite, rede em SVG e índice`.

### Tarefa 6: Preparar (lago de produção local e contexto)

**Files:**
- Create: `agente/preparar.py`, `tests/agente/test_preparar.py`
- Modify: `dbt/profiles.yml` (target `agente`), `tests/test_dbt_projeto.py` (4 targets)

**Interfaces:**
- Produces: `ErroPreparo`, `Preparo(versao_dados, dbt_rodou, revisar)`, `ler_env(arquivo)`,
  `ambiente(config, base)` (credenciais do `.env`, `ELEITORADO_AMBIENTE=prod`,
  `ELEITORADO_PREFIXO=config.prefixo_gcs`, `ELEITORADO_LAGO`, `ELEITORADO_PUBLICO`),
  `impressao_lago(lago)`, `corrigir_particoes(banco) -> list[str]`,
  `gerar_contexto(config, segundos_contagem=10) -> str`, `medir(conexao, sql, diario)`,
  `revisar_caderno(config, caderno) -> list[Caso]`, `_somar(tabela)`,
  `preparar(config, base, rodar=..., agora=...) -> Preparo` (roda
  `uv run coletor --target agente estado restaurar`; `dbt build --target agente` só quando a
  impressão do lago mudou; grava `investigacoes/contexto.md`).

- [ ] **Passo 1:** `git checkout proto/agente -- agente/preparar.py tests/agente/test_preparar.py dbt/profiles.yml tests/test_dbt_projeto.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente tests/test_dbt_projeto.py`. Esperado: tudo
  verde, com **85 passed** em `tests/agente`.
- [ ] **Passo 3 (mutação):** em `preparar`, troque a condição do dbt por `if False:`.
  `test_preparar_roda_restaurar_e_dbt_so_quando_muda` **deve falhar**. Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes; o fluxo do dbt sobre o lago vazio do CI
  (README, seção Testes) continua `ERROR=0`. Commit:
  `feat(agente): preparar com o lago de produção local, dbt no target agente e contexto`.

### Tarefa 7: Controlador e prompts por fase

**Files:**
- Create: `agente/controlador.py`, `agente/prompts.py`, `tests/agente/test_controlador.py`

**Interfaces:**
- Consumes: todas as anteriores.
- Produces: `ErroTrava`, `Dependencias(config, executor, preparar, agora)`,
  `identificador(agora, tema)`, `trava(investigacoes, agora)` (contexto; trava órfã depois de
  6 h), `Controlador(deps)` com `nova(tema) -> Path`, `pendente() -> Path | None`,
  `executar(pasta) -> Estado`. Constantes `CICLOS_POR_SESSAO = 25`, `RESERVA_HIPOTESE = 20`,
  `MINIMO_VALIDACAO = 12`, `CICLOS_RELATAR = 6`, `MINUTOS_POR_SESSAO = 20`,
  `ERROS_SEGUIDOS_PARA_PAUSAR = 2`. Prompts: `explorar`, `investigar`, `validar`,
  `correlacionar`, `relatar`.

- [ ] **Passo 1:** `git checkout proto/agente -- agente/controlador.py agente/prompts.py tests/agente/test_controlador.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente`. Esperado: **97 passed**.
- [ ] **Passo 3 (mutação):** em `Controlador._validar`, troque `if decisao == "confirmado":` por
  `if decisao in ("confirmado", "inconclusivo"):`.
  `test_inconclusivo_sem_rodadas_fica_inconclusivo` **deve falhar**. Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(agente): controlador com máquina de estados, orçamentos, retomada e prompts por fase`.

### Tarefa 8: Agentes, CLI, avaliação, agendamento e documentação

**Files:**
- Create: `.claude/agents/investigador.md`, `.claude/agents/validador.md`, `agente/cli.py`,
  `agente/avaliacao.py`, `agente/executar.ps1`, `agente/agendar.ps1`,
  `tests/agente/test_cli_avaliacao.py`
- Modify: `pyproject.toml` (`agente = "agente.cli:main"` em `[project.scripts]`;
  `packages = ["coletor", "agente"]`), `.gitignore` (bloco do `.claude`), `README.md` (seção
  "Agente investigador (L1)")

**Interfaces:**
- Produces: `uv run agente preparar | investigar [--tema T] [--retomar ID] | relatorio ID | indice
  | caderno [--situacao S] | avaliar`; saídas `0` (concluída ou parcial), `3` (pausada),
  `4` (trava), `5` (preparo); `investigacoes/ultima.json` para a notificação.
  `avaliacao.criar_lago(lago)`, `verificar(estado) -> dict[str, bool]`,
  `preparar_avaliacao(raiz, modelo) -> Path`.

- [ ] **Passo 1:** `git checkout proto/agente -- .claude/agents/investigador.md .claude/agents/validador.md agente/cli.py agente/avaliacao.py agente/executar.ps1 agente/agendar.ps1 tests/agente/test_cli_avaliacao.py README.md pyproject.toml .gitignore`
  e `uv sync`.
- [ ] **Passo 2:** `git status --short` não pode listar nada de `.claude/` além de `agents/`
  (`git check-ignore .claude/settings.local.json` deve responder o caminho).
- [ ] **Passo 3:** `uv run pytest -q`. Esperado: **102 passed** em `tests/agente` e a suíte
  inteira verde. `uv run agente --help` lista os 6 comandos.
- [ ] **Passo 4 (mutação):** em `avaliacao.verificar`, no primeiro critério, troque `"11222333"`
  por `"00000000"`. `test_verificar` **deve falhar**. Restaure e confirme.
- [ ] **Passo 5:** ruff e pytest completos verdes. Commit:
  `feat(agente): agentes investigador e validador, CLI, avaliação com casos plantados e agendamento`.

### Tarefa 9 (Claude, com o ok do usuário): integração e primeira execução

- [ ] **Passo 1:** push, PR, CI verde, merge.
- [ ] **Passo 2:** `uv run agente preparar` na máquina do usuário (sincroniza ~4 GB).
- [ ] **Passo 3:** `uv run agente avaliar`: os três critérios `ok`.
- [ ] **Passo 4:** primeira investigação livre (`uv run agente investigar`); o usuário revisa o
  relatório e o caderno.
- [ ] **Passo 5:** o usuário roda `.\agente\agendar.ps1` (registra a tarefa semanal).
