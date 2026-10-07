# Plano 10: implementação da onda C2, dados eleitorais do TSE

> **Para agentes executores:** SUB-SKILL OBRIGATÓRIA: usar
> `superpowers:subagent-driven-development` ou `superpowers:executing-plans`, tarefa por tarefa.
> Os passos usam caixas de seleção. Implementação autorizada pelo usuário em 2026-10-07.

**Objetivo:** coletar e versionar o recorte eleitoral aprovado, produzir dados privados confiáveis
e publicar somente os marts C2 permitidos, com seleção e edições recuperáveis.

**Arquitetura:** três downloads por ano — candidaturas, bens e contas — alimentam seis famílias
privadas imutáveis. Uma seleção validada é fixada para cada execução dbt; a saída candidata
fica no lago privado. A publicação C2 envia uma edição imutável e troca seu manifesto ao final.

**Tecnologias:** Python 3.12, uv, httpx, pyarrow, Pydantic, DuckDB e dbt-duckdb nas versões do lock.
**Spec:** [desenho aprovado](../specs/2026-10-06-onda-c2-tse-design.md), inclusive seções 7–9.

## Restrições globais e preparação

- Todos os cargos; anos aprovados **2018, 2020, 2022 e 2024**, filtrados também por `DT_ELEICAO`.
- Autorizar somente `tse.jus.br` e seus subdomínios; outros `.jus.br` continuam proibidos.
- Rechecagem mensal, usando o intervalo existente de 30 dias; sem limpeza automática de versões.
- Grão de candidatura: `(CD_ELEICAO, SQ_CANDIDATO)`; turno é atributo, não novo componente da chave.
- Não somar snapshots/prestações nem deduplicar itens por `SQ_RECEITA` ou `SQ_DESPESA`.
- Colapsar somente pagamentos idênticos da mesma parcela oficial; preservar raw e auditar efeito.
- PF e origens incertas ficam privados. Mínimo cinco não libera publicação sem validar células,
  totais complementares e diferenças entre edições. Primeira entrega mantém o bloqueio PF.
- Sem CPF completo/hash de CPF, descrições de bens, dados bancários, contatos ou doadores PF públicos.
- Cruzamentos exploratórios privados; sem alertas públicos, janela ou materialidade inventadas.
- Preservar alterações alheias. Não tocar o checkout original, `dados-receita` ou `fontes/rfb.yaml`.
- Não executar merge, workflow manual, exclusão remota, secrets/settings ou infraestrutura.

Antes da tarefa 1, após revisão deste plano: usar `superpowers:using-git-worktrees`; executar
`git fetch origin main` e criar `feat/onda-c2-tse-implementacao` em `C:/git/eleitorado-c2-impl`, baseada em
`origin/main`, sem mudar o checkout original. Levar somente spec/plano aprovados; ler `AGENTS.md`
da nova base. A base desta análise precede as correções Receita #35/#36: conferir interfaces
após atualizar, registrar SHA e adaptar integrações sem copiar arquivos do trabalho concorrente.
Verificar branch/diretório antes; nunca apagar ou reutilizar trabalho desconhecido.
Se houver mudanças de contrato material, interromper a tarefa afetada para revisão do desenho.

## Arquivos e limites de responsabilidade

- `coletor/adaptadores/tse_zip.py`: download/preparo multifamília, sem promoção de seleção.
- `coletor/tse/modelos.py`, `versoes.py`, `selecao.py`, `estado.py`, `execucao.py`, `publicacao.py`:
  contratos, gravação imutável, seleção, sincronização, execução fixada e publicação C2.
- `dbt/macros/tse.sql` e `dbt/models/{staging,intermediate,marts}/tse/`: leitura fixada,
  transformação privada e projeções permitidas; nenhum privado depende de materialização em marts.
- `tests/test_tse_*.py`, amostras sintéticas e testes unitários dbt: regressões sem rede/credenciais.
- Toda mudança em arquivo compartilhado é integrada pelo coordenador, preservando outros hunks.

## Foco da revisão

1. Redirecionamento intermediário para host proibido: recusar antes da requisição (T1).
2. ZIP com BR/BRASIL/UF, cabeçalho repetido e CRC inválido: escolher BRASIL e falhar fechado (T3).
3. Seleção ausente/corrompida com raw rejeitado disponível: não esconder com glob ou vazio (T5–T7).
4. Seletor de mesmo tamanho após rollback e dbt falho no agente: refazer preparo sem marcar sucesso (T15).
5. Publicador legado ou espelhamento apagando C2: proteger prefixos, hashes e ponteiros (T6/T13).

Cada tarefa tem responsável, dependências e ciclo vermelho/verde/mutação. Os nomes de testes
abaixo são novos, salvo os arquivos existentes indicados. Resultados são **esperados**, não executados.
Restaurar somente o hunk da mutação; nunca usar reset/checkout amplo sobre trabalho compartilhado.

### Tarefa 1: acesso HTTP restrito ao TSE

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** preparação.
**Arquivos:** modificar `coletor/http.py`, `tests/test_http.py`.
**Interface:** manter `host_permitido(host: str, sufixos: tuple[str, ...]) -> bool`;
acrescentar `.tse.jus.br` a `SUFIXOS_OFICIAIS`, mantendo o hook de cada request/redirect.
- [ ] Criar `test_tse_e_subdominio_permitidos`: `assert host_permitido('tse.jus.br', s)`;
  parametrizar `cdn.tse.jus.br`, `outro.jus.br`, `evil-tse.jus.br`, `tse.jus.br.evil.gov`.
- [ ] Rodar `uv run pytest -q tests/test_http.py -k tse`; esperado vermelho no host permitido.
- [ ] Implementar a allowlist; testar cadeia permitida→proibida→permitida com `respx`:
  `assert requisicoes_ao_host_proibido == 0`, inclusive em download com retomada.
- [ ] Repetir os testes: todos verdes. Mutação: substituir `.tse.jus.br` por `.jus.br`;
  o caso `outro.jus.br` deve falhar; restaurar e confirmar verde.
- [ ] Commit: `feat(coletor): permite somente o domínio do TSE e seus subdomínios`.

### Tarefa 2: competências eleitorais explícitas e contrato de famílias

**Responsável:** desenvolvedor. **Dependências:** T1.
**Arquivos:** modificar `coletor/manifesto.py`, `coletor/agenda.py`; criar
`tests/amostras_tse.py`, `tests/test_tse_manifesto.py`; ampliar `tests/test_agenda.py`.
**Interfaces:** `RegraCompetencia.anos: list[int] | None`; `Recurso.familias: dict[str, str] | None`;
novo adaptador literal `tse_zip`. `anos` exige tipo ano, valores únicos e não vazios; famílias só TSE.
- [ ] Criar `test_anos_eleitorais_exatos`: `assert competencias == ['2018','2020','2022','2024']`;
  `test_rechecagem_mensal`: em 29 dias nenhuma tarefa; em 30 dias quatro tarefas por recurso.
- [ ] Rodar `uv run pytest -q tests/test_tse_manifesto.py tests/test_agenda.py`; esperado vermelho.
- [ ] Implementar sem alterar séries existentes. Criar `recurso_tse(id: str) -> Recurso` e
  `zip_tse(membros: dict[str, bytes]) -> bytes` nas amostras; ainda não ativar fontes em produção.
- [ ] Repetir: verde. Mutação: ignorar `anos` e usar `anos(inicio, hoje)`;
  `test_anos_eleitorais_exatos` deve acusar anos ímpares/2026; restaurar.
- [ ] Commit: `feat(coletor): representa anos eleitorais e famílias de arquivos explicitamente`.

### Tarefa 3: um ZIP, várias famílias e validação completa

**Responsável:** desenvolvedor. **Dependências:** T2.
**Arquivos:** criar `coletor/adaptadores/tse_zip.py`, `coletor/tse/__init__.py`,
`coletor/tse/modelos.py`, `tests/test_tse_zip.py`; modificar `coletor/adaptadores/__init__.py`.
**Interfaces:** `FamiliaTse(familia: str, membro: str, csv: Path, layout_id: str)`;
`extrair(recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp,
hoje: date) -> Extracao`; `preparar_familias(recurso: Recurso, competencia: Competencia,
original: Path, pasta: Path, limite_membro_bytes: int = LIMITE_DESCOMPACTADO)
-> tuple[FamiliaTse, ...]`; reutilizar teto existente de 10 GiB por membro, não por ZIP.
- [ ] Criar `test_contas_um_download_quatro_familias`: `assert downloads == 1` e quatro famílias;
  `test_consolidado_sem_ufs`: `assert membros == ['..._BRASIL.csv']` para cada família.
- [ ] Rodar `uv run pytest -q tests/test_tse_zip.py`; esperado vermelho por módulo ausente.
- [ ] Implementar leitura Latin-1/`;`, nomes exatos e header por layout/ano; ler até EOF/CRC.
  Rejeitar membro ausente/ambíguo, header inesperado/repetido, truncamento e tamanho acima do teto.
  Definir no adaptador layouts dos quatro anos com campos essenciais por família; fixture por ano
  falha se faltar campo essencial, sem NULL silencioso. Opcional NULL só com regra explícita testada.
  Injetar limite de 32 bytes no teste; membro de 33 deve falhar. Processar download/CSV em fluxo;
  medir soma descompactada/disco na validação operacional, sem carregar ZIP inteiro em memória.
- [ ] Repetir: verde. Mutação: aceitar BR+UF ou omitir leitura até EOF;
  `test_consolidado_sem_ufs`/`test_crc_invalido_nao_prepara` devem falhar; restaurar.
- [ ] Commit: `feat(coletor): prepara famílias TSE de um único ZIP validado`.

### Tarefa 4: raw privado imutável e idempotência física

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T3.
**Arquivos:** criar `coletor/tse/versoes.py`, `coletor/tse/coleta.py`, `tests/test_tse_versoes.py`;
modificar `coletor/tse/modelos.py`, `coletor/coleta.py` somente no despacho TSE.
**Interfaces:** `VersaoTse(recurso_id: str, ano: int, versao_id: str, sha256_zip: str,
familias: dict[str, str], hashes: dict[str, str], layouts: dict[str, str],
sha256_semantico: str)`; `gravar_versao(lago: Path, recurso: RecursoCompleto, extracao: Extracao,
familias: tuple[FamiliaTse, ...], controle: Controle) -> VersaoTse`; formato vem de
`recurso.recurso.formato`. `coletar_tse(recurso: RecursoCompleto, competencia: Competencia,
historico: HistoricoColetas, deps: Dependencias, execucao_id: str,
forcar: bool = False) -> RegistroColeta`, integrado pelo despacho existente.
- [ ] Criar `test_duas_versoes_preservadas`: dois hashes deixam dois arquivos e raw antigo intacto;
  `test_mesmo_hash_nao_regrava`: `assert gravacoes == 1`; colisão de caminho/hash deve falhar.
- [ ] Rodar `uv run pytest -q tests/test_tse_versoes.py`; esperado vermelho.
- [ ] Gravar em `raw/tse/<familia>/<ano>/<sha256_zip>/dados.parquet`, usando conversor existente;
  descritor imutável em `estado/tse/versoes/<versao_id>.json`, com URL/hash/geração/layout/contagens.
  Arquivar ZIP via `Armazenamento.enviar` uma vez; registrar famílias em `RegistroColeta.parametros`.
  IDs de versão/seleção são hex SHA-256 (seguros em Windows); distinguir hash físico e semântico.
  Mudança só de geração preserva IDs de negócio, mas conserva nova versão física e sua origem.
- [ ] Repetir: verde. Mutação: chamar `LagoWarehouse.carregar_parquet` no TSE;
  `test_duas_versoes_preservadas` deve falhar. Restaurar; rejeição anterior não vira sucesso por hash igual.
- [ ] Commit: `feat(coletor): preserva versões privadas imutáveis do TSE`.

### Tarefa 5: vetor privado validado e promoção sem parcial

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T4.
**Arquivos:** criar `coletor/tse/selecao.py`, `tests/test_tse_selecao.py`; ampliar `modelos.py`.
**Interfaces:** `SelecaoTse(selecao_id: str, versoes: dict[str, str])`, chaves `tse.<recurso>:<ano>`;
`validar_selecao(lago: Path, selecao: SelecaoTse) -> tuple[str, ...]` retorna impedimentos;
`ReciboValidacaoTse(selecao_digest: str, execucao_id: str, entradas_digest: str,
saida_digest: str, resultado: ResultadoDbt)`; `promover_selecao(lago: Path,
selecao: SelecaoTse, recibo: ReciboValidacaoTse) -> None` exige recibo verde da mesma seleção.
- [ ] Criar `test_falha_conserva_vigente`: `assert vigente == anterior` após schema/CRC/arquivo faltante;
  `test_retificacao_menor`: total 100→80 resulta 80 e duas versões privadas, nunca 180.
- [ ] Rodar `uv run pytest -q tests/test_tse_selecao.py`; esperado vermelho.
- [ ] Exigir vetor de três recursos×quatro anos; permitir gerações diferentes explicitadas.
  Guardar seleção em `estado/tse/selecoes/<id>.json`; trocar `estado/tse/vigente.json` por replace local
  somente após hashes, layouts, cobertura e dbt. Recalcular digests das entradas/saída e vincular
  ao recibo; sucesso de outra seleção deve ser rejeitado. Após primeira promoção gravar marcador
  durável `estado/tse/inicializado.json`, independente do seletor. Relações incertas ficam privadas.
- [ ] Repetir: verde. Mutação: promover antes do resultado dbt ou tratar raw rejeitado como vigente;
  `test_falha_conserva_vigente`/`test_hash_rejeitado_nao_promove` devem falhar; restaurar.
- [ ] Commit: `feat(coletor): promove seleção TSE somente depois da validação`.

### Tarefa 6: sincronização privada preserva versões e restaura com segurança

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T5.
**Arquivos:** criar `coletor/tse/estado.py`, `tests/test_tse_estado.py`; modificar `coletor/estado.py`.
**Interfaces:** `salvar_tse(armazenamento: Armazenamento, prefixo: str, lago: Path) -> Resumo`;
`restaurar_tse(armazenamento: Armazenamento, prefixo: str, lago: Path) -> Resumo`.
- [ ] Criar `test_espelho_legado_preserva_tse`: `assert apagados_tse == []` com lago local incompleto;
  `test_restauro_parcial_conserva_seletor`: hash/dependência inválidos mantêm ponteiro local anterior.
- [ ] Rodar `uv run pytest -q tests/test_tse_estado.py tests/test_estado.py`; esperado vermelho nos novos.
- [ ] Excluir `raw/tse/` e `estado/tse/` do overwrite/delete genérico; enviar imutáveis e seleção antes
  do seletor e marcador durável; proteger ambos. Restaurar em área temporária, verificar hashes,
  dependências e coerência marcador/seletor, então promover localmente; falha parcial preserva
  estado anterior. Marcador remoto de inicialização sem seletor íntegro causa erro fechado.
  Preparadas/publicações privadas não são seleções vigentes; nunca apagar versões remotas.
- [ ] Repetir: verde. Mutação: retirar a proteção de prefixo ou baixar o seletor direto no vigente;
  os dois testes acima devem falhar; restaurar.
- [ ] Commit: `fix(estado): protege versões TSE e restaura seletores com validação`.

### Tarefa 7: execução dbt fixada e lago vazio explícito

**Responsável:** desenvolvedor. **Dependências:** T5–T6.
**Arquivos:** criar `coletor/tse/execucao.py`, `dbt/macros/tse.sql`, `tests/test_tse_execucao.py`;
modificar `coletor/esquemas.py`, `scripts/lago_vazio.py`, `dbt/tests/lago_vazio/esquemas.json`.
**Interfaces:** `ExecucaoTse(selecao_id: str | None, vars_dbt: dict, saida: Path, publicavel: bool)`;
`preparar_execucao_tse(lago: Path, execucao_id: str, target: str,
selecao: SelecaoTse | None = None) -> ExecucaoTse`;
macro `fonte_tse(familia)` usa exclusivamente `var('tse_fontes')`, lista de arquivos selecionados.
- [ ] Criar `test_selecao_lida_uma_vez`: trocar vigente após preparo não altera `vars_dbt`;
  `test_seletor_corrompido_nao_vira_vazio`: `assert erro`, mesmo com Parquet rejeitado existente.
  Testar lago novo/primeiro bootstrap parcial sem marcador: não publica; marcador sem seletor:
  erro; somente raw rejeitado: não publica. Seleção candidata explícita não lê/troca vigente.
- [ ] Rodar `uv run pytest -q tests/test_tse_execucao.py tests/test_esquemas.py`; esperado vermelho.
- [ ] Passar JSON fixado em `rodar_dbt(..., argumentos=['--vars', json])`; saída candidata em
  `<lago>/estado/tse/publicacoes/preparadas/<execucao>/marts`, fora do público legado.
  Seleção explícita prepara candidato antes da promoção; `None` lê vigente exatamente uma vez.
  `garantir_fontes` não cria glob TSE: CI tem seleção vazia tipada explícita; primeiro bootstrap
  produtivo é ausência do marcador durável, sem publicar C2; marcador sem seletor é erro.
  Vars `tse_fontes`/`tse_saida` têm defaults CI tipados e privados. Macro `tse_saida_mart(nome)`
  resolve location de cada mart C2 na saída própria, sem mudar `ELEITORADO_PUBLICO` global.
- [ ] Repetir: verde. Mutação: macro ler `raw/tse/**/*.parquet` ou fallback vazio em corrupção;
  os dois testes acima devem falhar; restaurar.
- [ ] Commit: `feat(dbt): fixa seleção TSE por execução sem glob de versões`.

### Tarefa 8: staging tipado, candidaturas e recorte pela eleição real

**Responsável:** desenvolvedor. **Dependências:** T7.
**Arquivos:** criar seis `dbt/models/staging/tse/stg_tse__{candidaturas,bens,receitas,
contratadas,pagamentos,doador_originario}.sql`, `dbt/models/staging/tse/tse.yml`;
criar `dbt/models/intermediate/tse/int_tse__candidaturas.sql`, `tse_candidaturas.yml`.
**Interfaces:** `candidatura_id='tse:'||cd_eleicao||':'||sq_candidato`; IDs fonte `varchar`,
`data_eleicao/date`, valores `decimal(38,2)`, CPF/CNPJ privados com estado de ausência/validade;
proveniência `ano_arquivo`, `versao_id`, `layout_id` vem da seleção, não da identidade.
- [ ] Criar unitários `recorte_data_real` (arquivo2022/eleição2026 excluído; arquivo2020/eleição2024
  incluído), `eleicoes_distintas` (mesmo SQ em duas eleições produz duas chaves) e `sentinela_menos4`
  (CPF -4 vira NULL com motivo de ausência, nunca documento normalizado válido).
- [ ] Rodar dbt direcionado conforme bloco de verificação; esperado FAIL antes das regras.
- [ ] Usar macros `documento_fonte`, `documento_valido`, `numero_br`, `data_br`; tratar -4 antes de
  normalizar e manter null marcado. Unificar arquivos por chave oficial; conflito fica privado.
- [ ] Repetir: verde. Mutação: filtrar `ano_arquivo` ou remover `cd_eleicao` da chave;
  `recorte_data_real`/`eleicoes_distintas` devem falhar; restaurar.
- [ ] Commit: `feat(dbt): tipa fontes TSE e aplica o recorte da eleição real`.

### Tarefa 9: itens de contas e chave sem metadados de geração

**Responsável:** desenvolvedor. **Dependências:** T8.
**Arquivos:** criar `dbt/models/intermediate/tse/int_tse__receitas.sql`,
`int_tse__contratadas.sql`, `tse_itens.yml`; ampliar `dbt/macros/tse.sql`.
**Interfaces:** `tse_linha_id(familia, chaves, campos_negocio)` produz hash privado+ocorrência;
`int_tse__contratadas` fornece chave oficial/prestação, candidatura, fornecedor, data e valor.
- [ ] Criar unitários `itens_preservados` (mesmo SQ, valores10/20→duas linhas,total30),
  `geracao_nao_muda_id` (só DT/HH_GERACAO/coleta mudam→mesmos IDs), `prestacao_ambigua_privada`
  (duas prestações sem regra oficial de vigência→zero fatos elegíveis; ambas privadas).
- [ ] Rodar dbt direcionado; esperado FAIL antes das regras.
- [ ] Separar chave do fato e item; preservar multiplicidade por conteúdo de negócio+ocorrência,
  sem ordem de coleta. Selecionar exportação aprovada; prestações ambíguas não entram nos fatos
  elegíveis. Doador originário permanece separado e privado; não impor join ainda não demonstrado.
- [ ] Repetir: verde. Mutação: `row_number()=1` por SQ ou incluir geração no hash;
  `itens_preservados`/`geracao_nao_muda_id` devem falhar; restaurar.
- [ ] Commit: `feat(dbt): preserva itens de contas sem somar versões de prestação`.

### Tarefa 10: parcelas, mapa único e auditoria de repetição idêntica

**Responsável:** desenvolvedor. **Dependências:** T9.
**Arquivos:** criar `dbt/models/intermediate/tse/int_tse__mapa_despesas.sql`,
`int_tse__pagamentos.sql`, `int_tse__auditoria_pagamentos.sql`, `tse_pagamentos.yml`.
**Interfaces:** mapa único por `(cd_eleicao,sq_prestador_contas,sq_despesa,tipo_prestacao,
data_prestacao)`; parcela acrescenta `sq_parcelamento_despesa`; auditoria contém repetições,
valor bruto/retido/removido `decimal(38,2)` e versão da política, sempre privada.
- [ ] Criar `pagamento_sem_fanout`: dois itens contratados e parcela30→uma parcela,total30;
  `identicos_auditados`: três parcelas idênticas100→retido100/removido200/excedentes2;
  `parcela_divergente_privada`: mesma chave com valores100/90 não escolhe uma silenciosamente;
  `campo_original_divergente`: mesma parcela/valor com descrição ou DT_GERACAO diferente não colapsa.
- [ ] Rodar dbt direcionado; esperado FAIL antes do mapa/deduplicação.
- [ ] Projetar metadados distintos antes do join; rejeitar conflitos de candidatura/fornecedor.
  Colapsar só linhas idênticas em TODAS as colunas originais da fonte, mesma parcela oficial e
  mesma versão selecionada. Excluir da igualdade apenas metadados adicionados pelo coletor.
  Qualquer diferença original fica pendente/privada/auditada; o hash estável que exclui geração
  não define essa igualdade. Guardar bruto/retido/removido e motivo da pendência.
- [ ] Repetir: verde. Mutação: join bruto aos itens ou deduplicar qualquer parcela pelo ID;
  `pagamento_sem_fanout`/`parcela_divergente_privada` devem falhar; restaurar.
- [ ] Commit: `feat(dbt): reconcilia parcelas sem multiplicação e audita repetições`.

### Tarefa 11: identidade privada, patrimônio e cobertura entre origens

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T8–T10.
**Arquivos:** criar `dbt/models/intermediate/tse/int_tse__vinculos_parlamentares.sql`,
`int_tse__patrimonio.sql`, `int_tse__evolucao_patrimonial.sql`, `tse_identidade.yml`.
**Interfaces:** vínculo `(candidatura_id,parlamentar_id,metodo,evidencia_id,regra_versao,estado)`;
`estado` confirmado/ambíguo/ausente; evidência sensível e agrupamento de pessoa só privados.
- [ ] Criar `cpf_inequivoco`, `homonimos_nao_unem`, `cpf_ausente_menos4`, `nome_divergente_pendente`,
  `troca_casa_nao_duplica_fato` (dois vínculos oficiais não duplicam receita/despesa),
  `sem_declaracao_nao_zero` (ausência não gera evolução) e `suplementar_outra_origem`.
  Mesmo nome/CPF ausente produz zero vínculos confirmados; CPF válido+nome divergente fica pendente.
- [ ] Rodar dbt direcionado; esperado FAIL antes dos vínculos/cobertura.
- [ ] Consumir detalhes Câmara/CEAP privados com método/origem explícitos; somente documento válido
  inequívoco ou evidência oficial revisada confirma. Nome divergente fica pendente; nome sozinho
  nunca confirma. Consolidar origens pela eleição real antes de comparar declarações efetivas.
- [ ] Repetir: verde. Mutação: fallback por nome ou `coalesce(patrimonio,0)`;
  `homonimos_nao_unem`/`sem_declaracao_nao_zero` devem falhar; restaurar.
- [ ] Commit: `feat(dbt): registra identidade TSE e patrimônio com cobertura explícita`.

### Tarefa 12: projeções públicas permitidas e PF bloqueado por padrão

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T10–T11.
**Arquivos:** criar `dbt/models/intermediate/tse/int_tse__fornecedores_elegiveis.sql`,
`int_tse__receitas_publicaveis.sql`, `tse_privacidade.yml`; criar
`dbt/models/marts/tse/{dim_candidatura,fct_receita_campanha_resumo,
fct_despesa_campanha_pj,fct_patrimonio_declarado}.sql` e `tse.yml`.
**Interfaces:** quatro marts da spec; `tipo_fato` contratação/pagamento obrigatório. Fornecedor
exige classificação PJ e `documento_valido`, não só `cnpj_raiz`; campanha/partido têm estados próprios.
- [ ] Criar `fornecedor_invalido_ou_campanha_excluido`, `pf_nao_publicado`,
  `totais_nao_reconstroem_pf`, `novo_campo_sensivel_nao_vaza`, `cpf_em_texto_nao_vaza`.
  Grupos PF com 4/5/6 identidades e correção isolada entre edições continuam todos privados.
  `saida_c2_isolada` inspeciona SQL compilado e arquivos: nenhum C2 no público legado.
- [ ] Rodar dbt direcionado; esperado FAIL antes das projeções/negação PF.
- [ ] Usar allowlist de colunas; chaves públicas derivam somente de campos públicos e ocorrência,
  nunca do hash privado de CPF/doador/texto sensível. PF/incerto, descrições de bens e bancários
  ficam em intermediate; nenhum total público inclui contribuição PF suprimida.
  Cada mart usa `tse_saida_mart(nome)`/var `tse_saida`, inclusive monitor futuro; aplicar testes
  `sem_cpf_completo` e, quando cadastral, `sem_dados_pessoais`. Não materializar privados em marts.
- [ ] Repetir: verde. Mutação: remover `documento_valido`, usar `select *` ou incluir PF no total;
  os testes correspondentes e `sem_cpf_completo`/`sem_dados_pessoais` devem falhar; restaurar.
- [ ] Commit: `feat(dbt): publica projeções C2 permitidas com receitas PF privadas`.

### Tarefa 13: publicação C2 imutável sem interferência legada

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T6–T7/T12.
**Arquivos:** criar `coletor/tse/publicacao.py`, `tests/test_tse_publicacao.py`;
modificar `coletor/publicacao.py`, `tests/test_publicacao.py` e seu dublê de publicador.
**Interfaces:** `publicar_tse(publicador: Publicador, preparada: Path, selecao: SelecaoTse,
gerado_em: datetime, versao: str, recibo: ReciboValidacaoTse) -> ResumoPublicacao`;
exige digests da seleção/entradas/saída iguais ao recibo verde; edição SHA-256 do conteúdo,
seleção, versões de regras e entradas; manifesto `marts/c2/manifesto.json`.
- [ ] Criar `test_falha_upload_conserva_manifesto`, `test_repetir_edicao_idempotente`,
  `test_legado_nao_envia_nem_apaga_c2`: `assert removidos_c2 == []`, inclusive o manifesto.
- [ ] Rodar `uv run pytest -q tests/test_tse_publicacao.py tests/test_publicacao.py`; esperado vermelho.
- [ ] Enviar allowlist validada a `marts/c2/edicoes/<id>/`; verificar bytes/hash remotos antes do
  manifesto (ampliar protocolo/dublê com `conferir(chave: str, sha256: str, bytes: int) -> bool`).
  Conferência lê por GET, em fluxo, os bytes armazenados e calcula SHA-256/tamanho; ETag multipart
  ou hash autodeclarado não bastam. Mesmo ETag/metadado com bytes errados deve reprovar.
  Proteger todo `marts/c2/` do envio/limpeza legados; edição anterior nunca é apagada.
- [ ] Repetir: verde. Mutação: manifesto antes dos arquivos, omitir conferência ou proteção legada;
  cada teste correspondente deve falhar; restaurar. Rollback reponta edição já verificada.
- [ ] Commit: `feat(publicacao): publica edições C2 imutáveis com manifesto ao final`.

### Tarefa 14: fontes e orquestração da seleção candidata

**Responsável:** desenvolvedor; integração coordenador. **Dependências:** T1–T13.
**Arquivos:** criar `fontes/tse.yaml`, `coletor/tse/pipeline.py`, `tests/test_tse_pipeline.py`;
modificar `coletor/cli.py`, `coletor/dbt.py`, `tests/test_dbt.py`.
**Interface:** `preparar_e_promover_tse(lago: Path, selecao: SelecaoTse, execucao_id: str,
target: str, rodar: Callable[..., ResultadoDbt]) -> ReciboValidacaoTse`: valida dependências,
prepara candidato explícito (T7), executa build privado, emite recibo e promove somente no sucesso.
`gerar_linhagem(diretorio: Path, target: str, publico: Path,
executar: Executor = _executar_subprocesso, argumentos: Sequence[str] = ()) -> bool`
propaga as mesmas vars fixadas.
- [ ] Criar `test_pipeline_tse_falha_preserva_edicao` (dbt falho não muda seleção/manifesto),
  `test_recibo_outra_selecao_rejeitado` e `test_fonte_tse_tres_zips_quatro_anos` (12 tarefas,
  seis famílias/ano, cadência30dias); `test_linhagem_mesmas_vars` exige seleção e saída idênticas.
- [ ] Rodar `uv run pytest -q tests/test_tse_pipeline.py tests/test_dbt.py`; esperado vermelho.
- [ ] Declarar os templates abaixo, grupo diário/cadência mensal, e ligar despacho TSE sem envio
  legado dos marts C2. Coleta falha mantém seleção anterior; candidato incompleto não publica.
  Build, docs/linhagem e publicação recebem a mesma seleção/saída; falha não cria recibo verde.
- [ ] Repetir: verde. Mutação: promover antes do build ou omitir vars da linhagem;
  testes de preservação e `test_linhagem_mesmas_vars` devem falhar; restaurar.
- [ ] Commit: `feat(tse): integra fontes e valida candidato antes da promoção`.

Templates públicos, com `{ano}` limitado aos quatro anos aprovados; base
`https://cdn.tse.jus.br/estatistica/sead/odsele`:

| Recurso | Caminho relativo à base | Membro consolidado |
|---|---|---|
| candidaturas | `/consulta_cand/consulta_cand_{ano}.zip` | `consulta_cand_{ano}_BRASIL.csv` |
| bens | `/bem_candidato/bem_candidato_{ano}.zip` | `bem_candidato_{ano}_BRASIL.csv` |
| contas | `/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip` | quatro abaixo |

Contas: `receitas_candidatos_{ano}_BRASIL.csv`,
`despesas_contratadas_candidatos_{ano}_BRASIL.csv`,
`despesas_pagas_candidatos_{ano}_BRASIL.csv`,
`receitas_candidatos_doador_originario_{ano}_BRASIL.csv`.
T3 registra headers/layouts essenciais das 24 combinações, lendo apenas cabeçalhos públicos
dos ZIPs oficiais. Metadados do protótipo podem apoiar essa conferência, sem serem dependência
de execução. Fixtures sintéticas registram o contrato sem incorporar linhas privadas.

### Tarefa 15: preparo do agente vinculado ao digest e à validação

**Responsável:** desenvolvedor; revisão arquiteto. **Dependências:** T7/T14.
**Arquivos:** modificar `agente/preparar.py`, `tests/agente/test_preparar.py`.
**Interfaces:** manter assinaturas públicas de `impressao_lago`/`preparar`; incorporar digest do
conteúdo da seleção C2 e de suas dependências na impressão, mantendo o escopo de correção C2.
- [ ] Criar `test_rollback_mesmo_tamanho_refaz_dbt` (mesmos caminhos/tamanhos, digest distinto:
  dbt roda novamente), `test_dbt_falho_nao_marca_preparo_c2` (marca anterior intacta, `ErroPreparo`,
  nenhuma sessão C2), `test_seletor_restaurado_invalido_bloqueia_c2`.
- [ ] Rodar `uv run pytest -q tests/agente/test_preparar.py`; esperado vermelho nos novos casos.
- [ ] Consumir T7/T14 e validar seleção restaurada antes do preparo; transmitir vars à construção
  e linhagem. Não confiar no comportamento legado que marca/segue após dbt falho; impedir
  investigação C2 sobre saída candidata inválida sem refatorar genericamente o agente.
- [ ] Repetir: verde. Mutação: fingerprint só tamanho ou gravar marca após falha C2;
  os dois primeiros testes devem falhar; restaurar.
- [ ] Commit: `fix(agente): valida seleção TSE e invalida preparo pelo conteúdo`.

### Tarefa 16: cruzamentos privados, raízes, monitor e documentação

**Responsável:** desenvolvedor; integração coordenador e revisão arquiteto. **Dependências:** T11–T15.
**Arquivos:** criar `dbt/models/intermediate/tse/int_tse__cruzamentos.sql`, `tse_cruzamentos.yml`,
`dbt/models/marts/tse/monitor_tse.sql`; modificar o modelo de raízes Receita da base atualizada
(atualmente `dbt/models/intermediate/int_rfb__raizes_interesse.sql`),
`docs/modelos-de-dados.md`, `docs/roteiro.md`; sem alterar `fontes/rfb.yaml`.
**Interfaces:** cruzamento privado com `candidatura_id`, raiz, origem, versões de entradas, datas,
estado de qualidade/cobertura; raízes com origem `tse_contratacao`/`tse_pagamento`.
Monitor usa `tse_saida_mart('monitor_tse')`; contém seleção/edição, atraso, cobertura e auditoria.
- [ ] Criar `data_anterior_nao_cruza` (anterioridade excluída, posterioridade válida incluída),
  `fato_invalido_nao_cruza` (`valor_suspeito` ou data inválida exclui), `emenda_so_pagamento`,
  `receita_ausente_cobertura_pendente` (ausência não vira irregularidade), `autoria_contextual`
  (nome não confirma autor), `raiz_tse_sem_ativar_alertas_c1` e `monitor_saida_isolada`.
- [ ] Rodar dbt direcionado; esperado FAIL antes das regras.
- [ ] Cruzar por raiz/identidade confirmada/datas válidas, sem janela ou limiar públicos.
  Cota usa `data_emissao_valida`/`valor_suspeito`; emendas só fase Pagamento, autoria por nome
  apenas contextual; contratos não recebem autoria inferida. Registrar snapshots C1 usados,
  sem alegar atomicidade legada. Adicionar raízes elegíveis sem inserir TSE em `rfb_fatos()`
  dos alertas C1; cadastro Receita indisponível permanece gate privado/cobertura pendente.
- [ ] Repetir: verde. Mutação: remover filtro temporal/qualidade ou materializar monitor no público
  legado; testes correspondentes devem falhar; restaurar. Documentar cobertura e gates pendentes.
- [ ] Commit: `feat(tse): integra raízes e monitor com cruzamentos privados e cobertura`.

## Verificação final e reconciliações propostas

Os comandos abaixo serão executados na implementação, sempre **sequencialmente**, com bancos e
saídas próprios da worktree. Nunca rodar pytest/dbt concorrentes no Windows.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
$env:ELEITORADO_LAGO = 'dbt/tests/lago_vazio'
$env:ELEITORADO_PUBLICO = "$env:TEMP\eleitorado-c2-ci"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO\marts" | Out-Null
uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
uv run dbt build --project-dir dbt --profiles-dir dbt --target ci
Remove-Item Env:ELEITORADO_LAGO, Env:ELEITORADO_PUBLICO
```

Para cada tarefa dbt: gerar lago vazio e rodar `dbt build ... --target ci --select <modelos da tarefa>`
com as mesmas variáveis; preparar `dbt run` antes de unitários que dependem de `this` incremental.
Os comandos diretos CI usam defaults seguros T7: seleção vazia tipada não publicável e saída C2
privada; testes de dados reais usam `--vars` do ExecucaoTse, inclusive docs/linhagem.
Esperado: zero FAIL/ERROR; final também WARN=0/SKIP=0. Não fixar número futuro de testes.
Em dados reais privados já disponíveis: reconciliar cada recurso/ano/versão e diferenças de
pagamentos; 2024 bruto menos R$452.661,12 e 79 excedentes somente se a entrada tiver o mesmo hash
medido. Confirmar nenhuma perda de itens; não somar contratação com pagamento nem snapshots.
Reconciliação da união de candidaturas pelo recorte deve explicar as 870 exclusões observadas,
não usar os números como constante para versões futuras. Provas de mutação permanecem propostas.

## Implantação proposta, estado e rollback

1. **Preparar:** branch/base revisados, CI verde e revisão independente. Coordenar carga inicial
   com o usuário/operador da Receita; sem usar seu lago/credenciais nem disparar workflow manual.
2. **Carregar privado:** baixar uma vez os três ZIPs de cada ano, validar CRC/layout e persistir
   versões/originais. Limitar lote a um ano por execução inicialmente; duração Actions não medida.
   Até completar vetor válido, monitorar bootstrap e manter C2 não publicada.
   Antes de habilitar rotina, medir execução contínua do produto em lago separado, sequencial:
   tempo total, pico de memória, bytes, disco e spill contra orçamento Actions de 120 minutos.
   O protótipo não validou esse limite; se excedido, não habilitar rotina e revisar operação.
   Não disparar workflow manual sem novo ok explícito nem paralelizar carga contra coleta Receita.
3. **Validar candidato:** fixar vetor, construir em saída privada e reconciliar itens/parcelas,
   identidade, recorte e privacidade. Falha conserva seleção/edição anterior; publicar motivo/atraso.
4. **Promover privado:** trocar seletor validado; sincronizar imutáveis antes do ponteiro.
   Agente valida restauração e digest; falha não avança sua marca nem inicia investigação C2.
5. **Publicar C2:** proteção legada instalada antes da primeira edição; upload imutável,
   conferência remota, manifesto ao final. Leitor deve seguir esse manifesto, sem globs/fixos.
6. **Observar:** monitor de tentativas/sucessos, seleção/edição, gerações por recurso, atraso mensal,
   bytes/tempo/spill, crescimento de versões, vínculos ausentes/ambíguos, parcelas removidas e PF
   retido. Conferir hashes e contagens de todos os arquivos apontados, não só HTTP200 do manifesto.
7. **Rollback:** validar seleção/edição anterior existente e repontar seus manifestos; não apagar
   edição ruim, raw ou histórico. Se o objeto anterior falhar conferência, interromper troca.
   Digest força reconstrução do agente mesmo com seletor do mesmo tamanho. Registrar o motivo.

PF público permanece bloqueado: a liberação futura exige política demonstrada/testada para
menos de cinco identidades verificáveis, identidade insuficiente, totais complementares e
correção isolada entre edições com cinco ou mais. Esta entrega não cria algoritmo genérico de
anonimização. Doador originário, prestação ambígua e cadastro Receita sem cobertura permanecem
privados. Alertas/limiares públicos e retenção com exclusão remota exigem decisão posterior.

## Auto-revisão e estado desta entrega

Auto-revisão `writing-plans`: cobertura da spec mapeada em T1–T16; assinaturas e caminhos conferidos;
verificados ciclo candidato/recibo/promoção, bootstrap durável, igualdade original da parcela,
isolamento por var própria e conferência remota dos bytes. Cada uma das 16 tarefas tem mutação.
Cinco riscos de revisão têm testes/mutações; nenhum requisito depende de copiar o protótipo privado.
Interfaces novas estão explicitadas; módulos legados só recebem integração/proteção C2.
Lacunas deliberadas acima bloqueiam a respectiva publicação, sem bloquear a implementação do núcleo.

Executado nesta etapa pelo coordenador: ruff check/format (94 arquivos), pytest final
297 passed/2 deselected após falha Windows transitória e repetição isolada; dbt run 62 e build
203, WARN=0/ERROR=0/SKIP=0. São baseline anterior à implementação. Nenhuma prova de mutação,
novo teste, download ou implantação deste plano foi executado. Revisar este plano antes de iniciar.
