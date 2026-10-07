# Onda C2: dados eleitorais do TSE

Data: 2026-10-06
Status: desenho e ajustes pós-protótipo aprovados em 2026-10-07; plano 10 aprovado; implementação autorizada em 2026-10-07.

## 1. Objetivo e decisões

Trazer candidaturas, bens declarados, receitas e despesas de campanha para cruzar com cota,
emendas, contratos e cadastro da Receita. Os resultados descrevem relações e indícios;
não demonstram favorecimento nem irregularidade por si sós.

Decisões expressas do usuário:

- Todos os cargos nas eleições de **2018, 2020, 2022 e 2024**.
- Autorizar o coletor a acessar **tse.jus.br e seus subdomínios**, incluindo redirecionamentos;
  a implementação dessa permissão entra na entrega aprovada. Outros `.jus.br` continuam
  fora da autorização. Não houve alteração de hosts nesta etapa.
- 2026 fica fora deste recorte.

Propõe-se cobrir todas as UFs e incluir candidaturas não eleitas; ligação com parlamentar
é opcional e terá cobertura medida.

Alternativas consideradas: federal 2018/2022 entrega menor e ligação direta à cota/emendas,
mas perde trajetórias municipais/estaduais; todos os cargos 2018–2024, opção escolhida,
amplia essas trajetórias e exige medir maior volume; incluir 2026 acrescentaria acompanhamento
provisório e maior frequência de retificações, ficando para outra entrega.

## 2. Fontes e limites verificados

O catálogo oficial de [candidatos de 2022](https://dadosabertos.tse.jus.br/dataset/candidatos-2022)
lista candidaturas e bens. O de [contas de 2022](https://dadosabertos.tse.jus.br/dataset/dadosabertos-tse-jus-br-dataset-prestacao-de-contas-eleitorais-2022)
lista contas de candidatos, de partidos, CNPJ de campanha e extratos, com arquivos no
`cdn.tse.jus.br` e data de geração por arquivo. O protótipo posterior leu os arquivos dos
quatro anos; medições e limites estão na seção 8.

O TSE informa que [doações empresariais estão vedadas desde as eleições de 2016](https://www.tse.jus.br/comunicacao/noticias/2016/Agosto/doacoes-de-pessoas-juridicas-estao-proibidas-nas-eleicoes-2016).
Por isso, o cruzamento empresarial principal parte de **fornecedores da campanha**. CNPJ de
partido ou campanha em receita não será classificado automaticamente como empresa doadora.
Contas próprias de órgãos partidários e extratos bancários ficam fora; repasses recebidos
pelas candidaturas permanecem nas receitas com sua natureza identificada.

## 3. Coleta, versões e publicação

Usar arquivos oficiais por eleição, com originais no GCS privado e raw imutável por
recurso/ano/versão, restrito à C2. Um manifesto privado seleciona explicitamente as versões
vigentes; staging lê essa seleção uma vez por execução, nunca todas as versões por glob.
Preparar e validar o conjunto candidato antes de promover o manifesto privado. Arquivos
rejeitados ficam sem referência vigente; um download repetido não torna válida uma coleta
rejeitada. IDs dos fatos não dependem da coleta. Registrar hash físico e diferença semântica:
DT_GERACAO pode mudar sem mudança de negócio. O gravador atual substitui partições e não
satisfaz esse contrato; a implementação precisa de gravação própria para versões da C2.

O ZIP de contas contém vários CSVs: baixar e arquivar uma vez por ano/versão e processar
os membros necessários desse mesmo ZIP. O adaptador atual aceita somente um membro;
a implementação deve atender à conversão de múltiplas famílias sem repetir o download.
O manifesto precisa representar exatamente os quatro anos aprovados, sem tentar anos ímpares
ou 2026. Essa seleção de fontes não substitui o filtro da data real das eleições nos registros.

- Registrar recurso, eleição, URL final, arquivo, hash, coleta, geração da fonte, layout e contagens.
- Selecionar uma versão válida por recurso/partição; não somar snapshots, prestações parciais,
  finais ou retificadoras. Usar a exportação selecionada, sem escolher por maior valor ou
  última linha. Multiplicidade de itens dentro da mesma prestação é preservada. Coexistência
  futura de prestações com vigência ambígua fica segregada no privado até regra demonstrada.
- Truncamento, esquema inesperado e conflito de metadados não promovem o conjunto candidato.
  Ausência de recurso, relação ainda não resolvida e vazio válido são estados distintos.
- O conjunto é um vetor explícito das versões por recurso/ano, não uma geração sincronizada
  do TSE. Datas de geração diferentes são permitidas após validar cobertura e relações.
  Exceções não resolvidas ficam no privado, sem entrar automaticamente nos joins públicos.
- Manter o conjunto vigente quando a nova preparação falhar, com cobertura/atraso visíveis.
  Preservar originais e raw das versões observadas; crescimento deve ser acompanhado.
- Proposta de cadência: rechecagem mensal dos quatro anos históricos, aceitando até cerca de
  um mês para incorporar revisão. Sem limpeza automática de versões nesta entrega.

### Decisão de publicação após revisão técnica

O publicador legado sobrescreve caminhos antes do manifesto e pode misturar edições em falha.
O usuário escolheu **prefixos imutáveis somente na C2, com manifesto atualizado ao final**.
Enviar todos os arquivos da edição, validar o envio e só então trocar o manifesto que os aponta.
Consumidores seguem o manifesto C2; caminhos fixos antigos não oferecem essa garantia.
Edições anteriores ficam preservadas; a limpeza legada deve respeitar os prefixos C2.
A publicação da mesma edição pode ser repetida sem nova coleta e sem duplicar fatos.

A garantia cobre somente os arquivos apontados pelo manifesto C2. Não torna atômicos os marts
legados de Câmara, emendas ou Receita. Registrar as versões dessas entradas usadas nos
cruzamentos. Migrar a publicação dos demais marts está fora desta entrega.

## 4. Identidade e contratos de dados

Separar candidatura, pessoa e parlamentar. `parlamentar_id` continua sendo `camara:<id>` ou
`senado:<id>`; não fundir identificadores de casas distintas nem usar CPF/hash de CPF público.

| Entidade | Grão e contrato proposto |
|---|---|
| Candidatura | Chave `(CD_ELEICAO, SQ_CANDIDATO)`; distingue eleições suplementares. |
| Pessoa privada | Agrupa candidaturas apenas com documento completo válido e vínculo inequívoco ou evidência oficial revisada; máscara/nome isolados não bastam. |
| Vínculo parlamentar | Candidatura, parlamentar_id, método, evidência, versão da regra e estado confirmado/ambíguo/ausente; evidência sensível privada. |
| Receita | Registro nativo da prestação vigente, natureza, data, valor e origem; doador direto e originário, se existentes, têm papéis distintos. |
| Despesa | Registro nativo e candidatura; contratação e pagamento são fatos separados, ligados pela chave da fonte quando disponível. |
| Bem | Item da declaração daquela candidatura/versão; não assumir identidade do mesmo bem entre eleições. |

CPF exato só produz ligação automática se válido e associado inequivocamente à mesma pessoa
nas fontes comparadas; várias candidaturas ou casas dessa pessoa são relações legítimas.
Documentos ausentes,
divergentes ou mascarados preservam a lacuna. Nome civil/urna pode apoiar investigação privada,
mas não autoriza vínculo público automático. A cobertura dos senadores pode ser menor.
Uma pessoa pode ter várias candidaturas e identificadores parlamentares sem duplicar fatos.
Emendas só ligam ao autor individual; não inferir autoria para bancada/comissão. Hoje a ligação
de `dim_autor_emenda` usa nome único, não CPF: preservar essa evidência mais fraca. Até reforçá-la,
o cruzamento de emenda permanece contextual/privado, sem alegar cadeia de identidade forte.

Valores usam decimal e datas conservam a semântica original. Sentinelas viram ausência marcada,
nunca zero implícito. Chaves estáveis usam identificadores oficiais com namespace; se inexistentes,
o protótipo deve demonstrar a chave e o tratamento de linhas idênticas antes do plano.
CNPJ conserva zeros e suporta alfanumérico pelas macros existentes; raiz liga empresas,
CNPJ completo identifica estabelecimento. Campanhas e partidos têm classificação própria.
Incluir fornecedores empresariais do TSE nas raízes de interesse da Receita; ausência de cadastro
até a coleta mensal seguinte é cobertura pendente, não empresa inexistente ou irregular.

## 5. Camadas públicas e privacidade

Proposta de marts, com nomes finais a confirmar no desenho ajustado pelo protótipo:

- `dim_candidatura`: chave, eleição, cargo, localidade, nome público, partido e situação eleitoral,
  sem contato, endereço ou CPF; vínculo parlamentar somente quando confirmado.
- `fct_receita_campanha_resumo`: candidatura × natureza/origem dos recursos, valores e contagens;
  doadores PF ficam somente no privado, sem nomes, máscaras ou identificadores individuais.
- `fct_despesa_campanha_pj`: fatos de contratação/pagamento com tipo explícito, fornecedor CNPJ,
  data e valor; totais nunca somam os dois tipos como se fossem gasto único. PF só no privado.
- `fct_patrimonio_declarado`: candidatura × tipo de bem, quantidade e valor declarado;
  descrições livres, localização de imóveis, contas e identificadores patrimoniais só no privado.

Agregados de receitas não incluem combinações que individualizem doadores; o protótipo deve
avaliar células pequenas antes de fixar as dimensões públicas. Não publicar dados bancários,
documentos de terceiros ou atributos pessoais sem necessidade para o objetivo.
Todos os marts levam `sem_cpf_completo`; cadastrais também `sem_dados_pessoais`.
Testar vazamento em texto, além de nomes de colunas. Somente colunas explicitamente permitidas
saem para os marts, evitando vazamento quando a fonte acrescentar campos.

## 6. Cruzamentos e semântica temporal

- Fornecedor de campanha que recebe cota ou pagamento de emenda: mesma raiz empresarial,
  vínculo confirmado ao parlamentar e fato público posterior à data do fato de campanha.
  Emenda só gera alerta público com autoria suficientemente comprovada em toda a cadeia.
  Guardar as duas datas, os fatos e método do vínculo; agregação não multiplica valores.
- Contratos federais da empresa são contexto separado: não atribuir contrato ao parlamentar
  sem uma relação de autoria documentada que os dados atuais não oferecem.
- Empresa irregular/recém-aberta em despesa de campanha: reaproveitar as exclusões e lógica
  temporal C1, distinguindo contratação e pagamento. Situação atual não prova situação antiga;
  exigir data de início da situação compatível e declarar cobertura limitada do cadastro.
  Data de abertura usa o menor início de atividade dos estabelecimentos, como na C1.
  Os 180 dias e limites monetários C1 são referências, não limites já validados para campanhas.
- Sócio PF relacionado a doador/parlamentar: investigação privada com método e incerteza;
  cadastro societário atual não demonstra vínculo durante eleição passada.
- Evolução patrimonial: comparação descritiva dos totais declarados entre candidaturas da
  mesma pessoa confirmada. Ausência não é patrimônio zero; variação não equivale a renda,
  enriquecimento ilícito ou valorização de mercado. Sem alerta acusatório automático.

Alertas públicos terão `alerta_id` estável pela regra e chaves, evidência dos fatos e exclusão
de valores/datas suspeitos. Janela máxima posterior e limites de materialidade serão propostos
com a distribuição real; até isso, os cruzamentos são consultas exploratórias privadas.

## 7. Critérios para plano e implementação

O protótipo mediu arquivos, bytes, linhas, tempos, chaves, CPF, relações e cruzamentos da seção 8.
As medições não demonstram o comportamento futuro do coletor/publicador, ainda não implementado.
O plano deve incluir testes com prova de mutação para, no mínimo:

- mesma entrada sem duplicar fatos; retificação menor sem somar versões;
- promoção privada e publicação C2 que conservam a seleção anterior em falha;
- namespace de eleição/candidatura, suplementares e troca de cargo/casa;
- CPF ausente, nome divergente, documento inválido e evidência de vínculo;
- itens preservados; pagamentos sem multiplicação; duplicata de parcela auditada;
- datas/valores inválidos e cobertura cadastral ausente sem inferir irregularidade;
- CPF em texto, descrições de bens e doadores PF sem vazamento nos marts;
- supressão de células, totais e diferenças entre edições, lago vazio e reconciliações reais.

Ajustes pós-protótipo aprovados em 2026-10-07: cadência mensal, política das 79 repetições
idênticas de pagamentos e regra de supressão das receitas PF, explicitadas abaixo.
Escrever o plano com esses contratos. Regras cadastrais C1 só recebem limites/volumes após
validação com cadastro utilizável, em momento coordenado com o usuário e com a outra coleta.

## 8. Protótipo com dados reais

Execução privada, sem coletor de produção, publicação ou gravação nos buckets. Após separar
os trabalhos, artefatos ficaram em C:/git/eleitorado-c2/avaliacao/c2/, ignorado pelo Git.
Downloads oficiais com host de cada redirecionamento validado, SHA-256 por ZIP e leitura dos
membros selecionados até EOF/CRC. CSV Latin-1, ponto e vírgula, campos inicialmente em texto.

BR contém a eleição presidencial; BRASIL é consolidado. Usar BRASIL por família, sem somar
as UFs. Foram processadas seis famílias por ano: candidaturas, bens, receitas, contratações,
pagamentos e doador originário. Estes quatro últimos são membros do mesmo ZIP de contas.

### Volumes observados por arquivo

Linhas brutas, antes do recorte temporal e das políticas finais de qualidade. Não representam
prestações vigentes consolidadas nem casos de irregularidade.

| Arquivo | Candidaturas | Bens | Receitas | Contratações | Pagamentos | Doador originário |
|---|---:|---:|---:|---:|---:|---:|
| 2018 | 29.287 | 93.527 | 329.683 | 1.724.053 | 1.653.375 | 151.448 |
| 2020 | 558.804 | 1.015.279 | 2.339.070 | 4.107.514 | 3.086.903 | 662.575 |
| 2022 | 29.322 | 92.559 | 674.944 | 2.209.835 | 2.411.963 | 199.241 |
| 2024 | 463.875 | 911.163 | 2.041.006 | 4.452.136 | 3.719.558 | 534.335 |

Os 12 ZIPs somam 3.661.108.849 bytes; os 24 Parquet,
1.648.462.464 bytes e 33.491.455 linhas. Downloads somados: 111,095 s nesta máquina;
não é estimativa para o Actions. Tempos por arquivo medem conversão/contagem inicial, antes
dos perfis. Interrupção e migração impedem afirmar um tempo total contínuo. Amostra de memória:
pico acumulado do processo de conversão de 572 MB até a amostra, não pico de toda execução.
DuckDB limitado a 768 MB no processamento, com spill privado.

### Recorte real e identidade

Ano do ZIP não determina a data da eleição: há suplementares de 2025/2026 nos arquivos
2022/2024 e de 2021/2023 no de 2020. Filtrar o ano de DT_ELEICAO pelos anos aprovados.
A união filtrada tem 1.080.418 linhas e chaves distintas (CD_ELEICAO, SQ_CANDIDATO),
sem repetição entre arquivos, conflito nos atributos testados ou múltiplos turnos na mesma chave.
Conservar turno como atributo; ele já é distinguido pelo CD_ELEICAO observado. Excluídas 870 linhas.

| Ano real da eleição | Candidaturas observadas no recorte |
|---|---:|
| 2018 | 29.213 |
| 2020 | 557.984 |
| 2022 | 29.500 |
| 2024 | 463.721 |

Os ZIPs nomeados 2024 têm CPF candidato indisponível (-4) em cadastro, receitas e contratações.
Isso não significa ausência global em 2024: o ZIP 2020 contém 123 candidaturas de eleição
ocorrida em 2024 com CPF válido. Não preencher lacunas por nome. A cobertura longitudinal
entre todas as origens de suplementares ainda precisa ser consolidada na implementação.

Para cruzar com a Câmara, foi usado CPF exato inequívoco da CEAP privada: 876 pares válidos
CPF/parlamentar na fonte local. Não equivale à cobertura do detalhe de deputados e não cobre
igualmente todos os anos/casas. A origem e o método do vínculo acompanham cada resultado.

### Granularidade, parcelas e relações

- SQ_DESPESA/SQ_RECEITA não identificam o item. Em 2022, as chaves testadas têm 381.542 e
  9.813 linhas excedentes, variando descrição/valor dentro da mesma prestação. Tipo/data de
  prestação não resolvem essa multiplicidade. Preservar conteúdo e ocorrência para a chave
  estável da linha, separada da chave oficial do fato; nunca selecionar última linha por isso.
  Excluir metadados de coleta/geração da identidade estável. Identificadores derivados de
  atributos sensíveis permanecem privados; não publicar hash de CPF ou doador.
- Pagamentos não trazem candidatura/fornecedor. Enriquecer por mapa único de metadados da
  contratação, com chave/prestação/data testadas, sem juntar parcelas diretamente aos itens.
  As relações principais bens/receitas/contratações→candidatura e pagamentos→contratação
  não tiveram ausência pelas chaves testadas nos quatro arquivos.
- Pagamentos 2024 têm 79 linhas excedentes formalmente idênticas em 56 grupos, com efeito
  bruto de R$ 452.661,12. Proposta: colapsar somente repetição idêntica da mesma parcela
  oficial na camada tratada, com contagem/valor auditáveis; preservar raw. Conteúdo divergente
  na chave não pode ser descartado automaticamente. Volumes abaixo ainda incluem essas linhas.
- A chave testada de doador originário não resolveu a relação com receitas: 21.446, 423.961,
  22.033 e 366.777 linhas sem correspondência, respectivamente 2018/2020/2022/2024.
  Isso não demonstra defeito da fonte. Preservar no privado, sem enriquecimento automático
  enquanto a semântica não estiver demonstrada; resumo público usa receitas principais.

### Cruzamentos exploratórios

Contagem de linhas de campanha com algum fato local posterior, sem somar valores após joins.
CNPJ válido e flags oficiais excluem campanhas/partidos identificados, mas não comprovam cadastro
empresarial. Datas/valores inválidos ficam fora. Os resultados são por arquivo observado;
janela de alerta e materialidade ainda precisam de validação. Zero de vínculo indica cobertura,
não ausência de relação. Raízes ausentes de anos diferentes não podem ser somadas.

| Arquivo | Contratações com cota posterior | Pagamentos com cota posterior |
|---|---:|---:|
| 2018 | 29.048 | 13.426 |
| 2020 | 3.769 | 1.026 |
| 2022 | 31.033 | 13.167 |
| 2024 | 0 | 0 |

Emendas ficam contextuais/privadas pela autoria ligada por nome; contratos não são atribuídos
a parlamentar. Em 2022, 62.553 raízes contratadas estavam ausentes da união de 250.822 raízes
das cinco fontes locais comparadas. Isso mede expansão de cobertura, não empresas inexistentes.
Alertas de situação/abertura não foram medidos com Receita utilizável. Nenhuma nova leitura
em dados-receita ocorreu após o pedido de isolamento do usuário.

Na comparação entre arquivos nomeados 2018/2022, após filtrar a data real aos anos aprovados,
há 4.161 pares com CPF válido, declaração única e nome coerente: 2.667 totais maiores,
111 iguais e 1.383 menores. Outros 97 pares têm nome divergente e ficam pendentes. Essa
comparação não unifica todas as origens de suplementares e não demonstra enriquecimento ilícito.

### Receitas PF e privacidade

A distribuição exploratória mostrou muitas células com um ou dois documentos distintos:
por exemplo, no arquivo 2024, 265.927 células com um e 41.536 com dois, nas dimensões testadas.
Contagem de documento não comprova por si só identidade válida; não certifica anonimato.
Proposta para a primeira publicação: suprimir montante e contagem de células PF com menos de
cinco doadores de identidade verificável ou com identidade insuficiente. Não publicar totais
complementares que reconstruam os valores suprimidos por subtração. Validar também diferenças
entre edições imutáveis: uma correção isolada pode revelar valor mesmo em célula com cinco
ou mais doadores. O mínimo de cinco sozinho não libera a publicação. Controles e perdas de
cobertura devem ser reconciliados antes da publicação; até lá, agregados PF ficam privados.
O mínimo de cinco é regra de produto proposta, não garantia jurídica ou de anonimato.

Evidências privadas: metricas.json, reconciliacoes.json, uniao_candidaturas.json,
diagnostico_chaves.json, duplicados_pagamento_2024.json, evidencias_download.json e
cruzamentos.json, com scripts reproduzíveis em avaliacao/c2/. Nada disso entra no Git.

## 9. Verificação desta etapa

Nenhum código de produção foi alterado. Na worktree baseada na main:

- uv run ruff check . e uv run ruff format --check .: passaram; 94 arquivos formatados.
- Primeira suíte pytest: 296 passaram e 1 falhou com WinError 5 em os.replace do estado
  temporário do agente. Repetição isolada: 1 passou. Repetição completa final: 297 passaram,
  2 testes de integração desmarcados. Não foi necessário alterar código para esses resultados.
- Primeiro dbt build no lago recém-criado: PASS=169, ERROR=1, SKIP=33; teste incremental
  referenciava this antes de existir a relação. O CI roda dbt run antes dos testes.
  Após essa preparação, dbt build completo: PASS=203, WARN=0, ERROR=0, SKIP=0.
- Na pasta original, uma primeira verificação paralela pytest/dbt teve três erros de cópia
  do banco aberto no Windows; repetição sequencial passou. Não repetir essa concorrência.
- Sem commit, push, publicação, workflow manual, mudança de secrets ou operação no bucket.

Reverificação em 2026-10-07, durante o plano (somente documentação alterada):

- Ruff: check e format --check passaram, 94 arquivos.
- Pytest: 296 passaram e um falhou com WinError 5 em os.replace, agora no teste de
  achado validado no fim do orçamento. Isolado passou; repetição completa passou com
  297 testes e dois de integração desmarcados, em 79,81 s.
- Lago vazio gerado novamente, dbt run: PASS=62; dbt build: PASS=203, WARN=0,
  ERROR=0, SKIP=0. Execuções sequenciais, sem concorrência com pytest.
