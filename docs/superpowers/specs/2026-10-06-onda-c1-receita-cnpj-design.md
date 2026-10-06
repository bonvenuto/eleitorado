# Onda C1: cadastro de empresas da Receita Federal (CNPJ): design

Data: 2026-10-06
Status: em revisão

## 1. Objetivo

Trazer o cadastro das empresas que aparecem nos dados do eleitorado (fornecedores da cota,
favorecidos de emendas, contratados, licitantes e sancionadas) a partir da base aberta do CNPJ da
Receita Federal: situação cadastral, data de abertura, CNAE, porte, Simples/MEI e sócios. Com isso,
quatro alertas novos e mais matéria-prima para o agente investigador.

O TSE (candidaturas, bens, doações e gastos de campanha) é a onda C2, com sondagem e desenho
próprios.

### Decisões do usuário

| Tema | Decisão |
|---|---|
| Recorte | só as empresas (raízes de CNPJ) que aparecem nos nossos dados (~251 mil hoje), não os ~68 milhões |
| Sócios | lago privado (agente e alertas); os marts públicos trazem o cadastro da empresa e os fatos dos alertas, nunca a lista de sócios pessoa física |
| Alertas | empresa irregular recebendo; empresa recém-aberta; sócios em comum na licitação; parlamentar sócio do fornecedor |
| Abordagem | recorte em fluxo num workflow mensal próprio (abordagem A) |
| Originais | exceção à regra do projeto: não arquivar os 7,6 GB mensais; guardar o recorte e um manifesto com o hash de cada arquivo-fonte |

### Fora do escopo

- TSE (onda C2).
- Licitações do PNCP (o alerta de sócios em comum usa as licitações do Portal, até 04/2024).
- Correspondência de parentes (sobrenome) entre sócios e parlamentares.
- API de consulta individual de CNPJ (restrita ou paga) e APIs de terceiros.

## 2. A fonte

- **Onde:** compartilhamento público do Nextcloud da Receita (Serpro), com WebDAV:
  `https://arquivos.receitafederal.gov.br/public.php/webdav/` com o token público do compartilhamento
  (`YggdBLfdninEJX9`) como usuário e senha vazia. Uma pasta por competência (`AAAA-MM/`); a Receita
  mantém só os últimos ~5 meses. Em 2026-10-06 a mais recente é `2026-09/`.
- **Arquivos por competência** (ZIP com um CSV cada; 7,6 GB no total em 2026-09):

| Grupo | Arquivos | Tamanho |
|---|---|---:|
| Estabelecimentos | `Estabelecimentos0.zip` a `9` | 5,4 GB |
| Empresas | `Empresas0.zip` a `9` | 1,4 GB |
| Sócios | `Socios0.zip` a `9` | 0,7 GB |
| Simples/MEI | `Simples.zip` | 0,3 GB |
| Apoio | `Cnaes`, `Municipios`, `Naturezas`, `Qualificacoes`, `Motivos`, `Paises` | < 1 MB |

- **Formato:** CSV sem cabeçalho, separador `;`, campos entre aspas, codificação Latin-1, datas
  `AAAAMMDD` (`00000000` = sem data), valores com vírgula decimal. Layout (ordem das colunas):
  - **Empresas (7):** cnpj_basico, razao_social, natureza_juridica, qualificacao_responsavel,
    capital_social, porte_empresa, ente_federativo_responsavel.
  - **Estabelecimentos (30):** cnpj_basico, cnpj_ordem, cnpj_dv, identificador_matriz_filial,
    nome_fantasia, situacao_cadastral, data_situacao_cadastral, motivo_situacao_cadastral,
    nome_cidade_exterior, pais, data_inicio_atividade, cnae_fiscal_principal,
    cnae_fiscal_secundaria, tipo_logradouro, logradouro, numero, complemento, bairro, cep, uf,
    municipio, ddd_1, telefone_1, ddd_2, telefone_2, ddd_fax, fax, correio_eletronico,
    situacao_especial, data_situacao_especial.
  - **Sócios (11):** cnpj_basico, identificador_socio, nome_socio_razao_social, cnpj_cpf_socio,
    qualificacao_socio, data_entrada_sociedade, pais, representante_legal, nome_representante,
    qualificacao_representante_legal, faixa_etaria.
  - **Simples (7):** cnpj_basico, opcao_pelo_simples, data_opcao_simples, data_exclusao_simples,
    opcao_mei, data_opcao_mei, data_exclusao_mei.
  - **Apoio (2):** codigo, descricao.
- **Códigos:** situação cadastral 01 nula, 02 ativa, 03 suspensa, 04 inapta, 08 baixada; porte 00
  não informado, 01 microempresa, 03 empresa de pequeno porte, 05 demais; identificador do sócio
  1 pessoa jurídica, 2 pessoa física, 3 estrangeiro. O CPF de sócio pessoa física (e do
  representante legal) vem mascarado pela Receita: `***456789**` (6 dígitos do meio).
- **Município:** a Receita usa código próprio (tabela `Municipios`), não o do IBGE.
- **Detalhe de deputados** (para o alerta 4): `https://dadosabertos.camara.leg.br/api/v2/deputados/{id}`
  traz `cpf` e `nomeCivil`, que a lista de deputados que já coletamos não tem.

## 3. Coleta

### 3.1 Conjunto de interesse

Modelo novo `int_rfb__raizes_interesse` (dbt, tabela): raízes distintas de CNPJ (8 posições) que
aparecem em fornecedores da cota, favorecidos e documentos de emendas, contratos federais (Portal e
PNCP), **todos** os participantes de licitação (não só os vencedores) e sancionadas, com a origem
de cada raiz.

### 3.2 Workflow `receita.yml`

- Toda segunda às 06:00 UTC e por `workflow_dispatch`; limite de 3 horas; o mesmo grupo de
  concorrência do `pipeline.yml` (os dois nunca escrevem no lago ao mesmo tempo), as mesmas
  credenciais (WIF da conta `pipeline`) e o mesmo cache cifrado do lago.
- Passos: restaurar o lago; `dbt run --select +int_rfb__raizes_interesse` (só o necessário para o
  conjunto); exportar as raízes para um Parquet local; `coletor coletar rfb.<recurso>` para os
  recursos vencidos; salvar o estado.
- A competência é a pasta mais recente do WebDAV. Recurso já coletado naquela competência não é
  coletado de novo, então na prática a coleta acontece uma vez por mês.

### 3.3 Recurso e adaptador

- Manifesto novo `fontes/rfb.yaml`, com um recurso por grupo (`empresas`, `estabelecimentos`,
  `socios`, `simples`) e um por tabela de apoio, competência mensal (`AAAA-MM` = pasta da Receita).
- Adaptador novo `webdav_zip`: lista a pasta da competência, baixa cada ZIP do grupo em streaming
  calculando o SHA-256, e passa o CSV do ZIP pelo DuckDB com um semi-join contra as raízes de
  interesse (`cnpj_basico in (select raiz from raizes)`), gravando só o recorte em Parquet. O ZIP é
  apagado em seguida: o disco nunca guarda mais que um arquivo.
- Cada ZIP do grupo é uma coleta própria (retomada por arquivo). As tabelas de apoio vão inteiras.
- O número de colunas do CSV é conferido contra o layout; diferente, a coleta falha com erro claro
  e não grava nada parcial.
- Os metadados de coleta registram, por arquivo-fonte: nome, tamanho, SHA-256, linhas lidas e
  linhas mantidas.

### 3.4 Detalhe de deputados

Recurso novo `camara.deputados_detalhe`: para cada deputado já coletado (da 53ª legislatura em
diante, ~2.500), o detalhe da API da Câmara. Snapshot mensal, com pausa entre chamadas. Fica no
lago privado (tem CPF completo).

### 3.5 Lago privado

```
raw/rfb/{empresas,estabelecimentos,socios,simples}/<AAAA-MM>/<coleta_id>.parquet   recorte do mês
raw/rfb/{cnaes,municipios,naturezas,qualificacoes,motivos,paises}/<AAAA-MM>/...    inteiras
raw/camara/deputados_detalhe/<data>/...
```

O histórico mês a mês fica (poucos MB por mês): permite acompanhar mudanças de situação e de
sócios daqui em diante.

## 4. Modelagem

### 4.1 Staging e intermediate (privados)

- `stg_rfb__empresas`, `stg_rfb__estabelecimentos`, `stg_rfb__socios`, `stg_rfb__simples` e as
  tabelas de apoio: tipos convertidos (datas, capital social), CNPJ completo do estabelecimento
  (`cnpj_basico || cnpj_ordem || cnpj_dv`), descrições dos códigos.
- `stg_camara__deputados_detalhe`: id, nome civil, CPF.
- **Municípios:** correspondência do código da Receita com o código IBGE por nome normalizado + UF
  contra `dim_municipio`.
- `int_rfb__empresas`: a empresa na competência mais recente, com a matriz, o Simples/MEI e as
  contagens de estabelecimentos e sócios.
- `int_rfb__estabelecimentos`: estabelecimentos vigentes, com endereço e contato.
- `int_rfb__socios`: sócios vigentes (nome, documento como publicado, qualificação, data de
  entrada, faixa etária).

### 4.2 Situação na data do fato

A Receita informa desde quando vale a situação atual (`data_situacao_cadastral`). Um fato posterior
a essa data, com situação irregular, ocorreu com a empresa já irregular. Reativações anteriores não
aparecem na base do mês; o histórico mensal do lago passa a registrá-las daqui em diante.

### 4.3 Marts públicos (novos)

- `dim_empresa` (uma linha por raiz): razão social (CPFs no texto mascarados), natureza jurídica,
  porte, capital social, data de abertura (início de atividade da matriz), situação cadastral da
  matriz com data e motivo, CNAE principal com descrição, município IBGE e UF da matriz, Simples e
  MEI com datas, quantidade de estabelecimentos e de sócios, competência da Receita.
- `dim_estabelecimento` (uma linha por CNPJ completo): matriz ou filial, nome fantasia, situação
  com data e motivo, início de atividade, CNAE principal, município IBGE e UF.
- **Não vão para os marts:** endereço (logradouro, número, complemento, bairro, CEP), e-mail,
  telefones e sócios. No MEI, endereço e contato são de uma pessoa física.
- Os marts existentes já têm `*_cnpj_raiz`: o cruzamento é por essa coluna, sem duplicar dados da
  empresa nos fatos.

## 5. Alertas

Todos excluem registros marcados com problema de qualidade (`valor_suspeito`,
`data_emissao_valida = false`), têm `alerta_id` estável (MD5 da regra e das chaves) e uma coluna
`regra`. São indícios para investigar.

### 5.1 `alerta_pagamento_empresa_irregular`

Fatos: despesa de cota (`data_emissao`), pagamento de emenda (`data_documento`, fase
`Pagamento`) e contrato (`data_assinatura`). Situação do **estabelecimento exato** (CNPJ de 14
posições) ou, sem ele, da matriz. Dispara quando a situação é baixada, inapta, suspensa ou nula e
`data_situacao_cadastral <= data do fato`. Colunas: origem, identificador do fato, data, valor,
CNPJ, razão social, situação, data e motivo da situação, dias entre a irregularidade e o fato.

### 5.2 `alerta_empresa_recem_aberta`

Dispara quando a empresa (início de atividade da matriz) foi aberta até 180 dias antes do fato,
com valor de pelo menos R$ 50 mil (contrato ou pagamento de emenda) ou R$ 10 mil (despesa de
cota). Um fato **anterior** à abertura sai como tipo próprio (`fato_antes_da_abertura`). Colunas:
origem, fato, data, valor, CNPJ, razão social, data de abertura, dias desde a abertura, tipo.

### 5.3 `alerta_licitacao_socios_em_comum`

Dois participantes de raízes diferentes na mesma licitação do Portal com um sócio em comum: sócio
empresa pelo CNPJ; sócio pessoa física pelo nome **e** pelos 6 dígitos visíveis do CPF. O sócio
precisa ter entrado nas duas empresas antes da data da licitação. Publica o par de participantes,
quem venceu, o tipo e a qualificação do sócio e, quando o sócio é empresa, o CNPJ dele; nunca o
nome nem o CPF de sócio pessoa física.

### 5.4 `alerta_parlamentar_socio_fornecedor`

- Deputado: sócio pessoa física com o mesmo nome civil (normalizado) e os mesmos 6 dígitos do
  meio do CPF (`correspondencia = 'nome e cpf'`).
- Senador: só pelo nome completo (`correspondencia = 'só nome'`), mais fraca, sujeita a homônimo.
- Grão parlamentar × empresa: qualificação e data de entrada como sócio; total recebido da cota do
  próprio parlamentar; total recebido de emendas de autoria dele; total em contratos federais. O
  CPF não aparece.

## 6. Agente investigador

- O `preparar` passa a incluir as tabelas novas no contexto (automático); `docs/modelos-de-dados.md`
  documenta os marts e alertas novos.
- `investigador.md`: códigos de situação, porte e MEI; sócios só em `intermediate.int_rfb__socios`
  (CPF de pessoa física mascarado pela Receita); lentes novas (capital social baixo para o valor do
  contrato, fornecedoras no mesmo endereço, sócio em comum com empresa sancionada, alertas da C1).
- Avaliação: caso plantado novo (empresa baixada recebendo pagamento de emenda), que deve ser
  confirmado.

## 7. Testes

- **Coletor:** recorte em fluxo com um ZIP pequeno (mantém só as raízes de interesse, lê
  Latin-1, calcula o SHA-256); recusa quando o número de colunas muda; listagem do WebDAV com
  respostas simuladas; competência já coletada não é coletada de novo; detalhe de deputados.
- **dbt:** um teste unitário por alerta, com as bordas: fato no mesmo dia da baixa; sócio que
  entrou depois da licitação; senador só por nome; fato antes da abertura; registro com
  `valor_suspeito` excluído.
- **LGPD:** `sem_cpf_completo` em `dim_empresa`, `dim_estabelecimento` e nos alertas novos; um
  teste que falha se um mart público tiver coluna de endereço, contato ou sócio pessoa física.
- **Protótipo antes do plano:** coleta real de uma competência inteira (medir download e filtro
  no runner), coleta do detalhe dos deputados e os quatro alertas sobre os dados reais, para medir
  quantos casos cada um gera e ajustar os limites antes de publicar.

## 8. Operação

- Se a coleta mensal medir mais de 90 minutos, os grupos se dividem em semanas (Estabelecimentos
  numa execução, o resto na outra), com o mecanismo de limite por execução que já existe.
- O token do compartilhamento fica no manifesto; se a Receita trocar o link, a coleta falha com
  mensagem clara (o histórico do lago não é afetado).
- Recursos: o lago cresce poucos MB por mês; o runner baixa 7,6 GB por mês (sem custo).

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Receita muda o layout ou o link | conferência de colunas e erro claro; histórico intacto |
| Download lento ou instável no runner | medição no protótipo; divisão em semanas; retomada por arquivo |
| Exposição de pessoas físicas | sócios, endereço e contato só no privado; CPF da razão social do MEI mascarado; testes LGPD |
| Homônimos | exigir os 6 dígitos do CPF quando há; marcar `só nome` quando não há |
| Sócio atual não é o sócio da época | data de entrada contra a data do fato; histórico mensal daqui em diante |
| Empresa nova fica um mês sem cadastro | aceito: entra no recorte do mês seguinte |
