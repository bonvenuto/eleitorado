import type { ReactNode } from 'react'
import { AVISO_ALERTA, AVISO_HOMONIMO, AVISO_RAIZ } from '../componentes/Alertas'
import { AvisoErro, Carregando } from '../componentes/Estados'
import { Secao, Subtitulo, Tabela } from '../componentes/Secao'
import { PADRAO_DADOS_URL } from '../caminhos'
import { carregarResumo } from '../dados'
import { TRACO, formatarInstante, formatarInteiro, formatarPercentual } from '../formato'
import type { Fonte, Resumo } from '../tipos'
import { useDados } from '../useDados'
import { useTitulo } from '../useTitulo'

const MODELOS = 'https://github.com/bonvenuto/eleitorado/blob/main/docs/modelos-de-dados.md'
const MANIFESTO = `${new URL(PADRAO_DADOS_URL).origin}/manifesto.json`

const SITUACAO: Record<Fonte['situacao'], string> = {
  ok: 'Em dia',
  aviso: 'Atrasada',
  erro: 'Com erro',
}

function Texto({ children }: { children: ReactNode }) {
  return <p className="max-w-3xl">{children}</p>
}

function Situacao({ fonte }: { fonte: Fonte }) {
  return (
    <span className="flex items-center gap-2">
      {SITUACAO[fonte.situacao]}
      {fonte.situacao !== 'ok' && (
        <span aria-hidden="true" className="selo-alerta">
          !
        </span>
      )}
    </span>
  )
}

function Fontes({ resumo }: { resumo: Resumo }) {
  return (
    <>
      <Tabela
        titulo="Situação das fontes"
        colunas={['Fonte', 'Cadência', 'Último sucesso', 'Situação']}
        linhas={resumo.fontes.map((f) => ({
          chave: f.recurso_id,
          celulas: [
            f.recurso_id,
            f.cadencia ?? TRACO,
            f.ultimo_sucesso ? formatarInstante(f.ultimo_sucesso) : 'nunca',
            <Situacao fonte={f} />,
          ],
        }))}
      />
      <Subtitulo>Fontes que encolheram</Subtitulo>
      <Texto>
        Quando uma coleta traz bem menos linhas que a anterior, a fonte pode ter perdido dados
        na origem. Os números do site dependem dessas fontes.
      </Texto>
      {resumo.fontes_reduzidas.length === 0 ? (
        <p className="text-ash">Nenhuma fonte encolheu na última coleta.</p>
      ) : (
        <Tabela
          titulo="Fontes que encolheram"
          colunas={['Fonte', 'Competência', 'Coletada em', 'Linhas antes', 'Linhas depois', 'Variação']}
          direita={[3, 4, 5]}
          linhas={resumo.fontes_reduzidas.map((f, i) => ({
            chave: `${i}`,
            celulas: [
              f.recurso_id,
              f.competencia ?? TRACO,
              formatarInstante(f.coletada_em),
              formatarInteiro(f.linhas_antes),
              formatarInteiro(f.linhas_depois),
              formatarPercentual(f.variacao_pct),
            ],
          }))}
        />
      )}
    </>
  )
}

export function Sobre() {
  useTitulo('Sobre')
  const resumo = useDados('resumo', carregarResumo)
  return (
    <>
      <h1 className="text-heading-sm font-medium sm:text-heading-lg">Sobre o Eleitorado</h1>

      <Secao titulo="De onde vêm os dados">
        <Texto>
          Tudo vem de fontes públicas oficiais: a Câmara dos Deputados e o Senado Federal (cota
          parlamentar e dados dos parlamentares); a Controladoria-Geral da União, pelo Portal da
          Transparência (emendas, contratos, licitações e as sanções do CEIS e do CNEP); o Portal
          Nacional de Contratações Públicas (PNCP); o IBGE; e a Receita Federal (cadastro de
          empresas).
        </Texto>
        <Texto>
          Os dados são coletados e atualizados todos os dias. A base de empresas da Receita é
          mensal.
        </Texto>
      </Secao>

      <Secao titulo="Como ler um alerta">
        <Texto>
          Um alerta é uma regra automática que aponta onde vale olhar com mais atenção: por
          exemplo, um pagamento a uma empresa que estava punida na data do pagamento. Cada
          alerta traz a regra que o gerou, uma explicação, os cuidados de leitura e o link para
          a fonte oficial.
        </Texto>
        <p className="max-w-3xl rounded-cartao bg-graphite p-7">{AVISO_ALERTA}</p>
        <Texto>
          Alguns alertas têm correspondência fraca e aparecem separados, com um aviso. Isso
          acontece em dois casos: “{AVISO_HOMONIMO}” e “{AVISO_RAIZ}”
        </Texto>
      </Secao>

      <Secao titulo="Limitações conhecidas">
        <ul className="flex max-w-3xl list-disc flex-col gap-2 pl-5">
          <li>Cada fonte tem a sua data; a página inicial mostra até quando vai cada uma.</li>
          <li>
            Senadores são ligados a empresas só pelo nome, então pode haver homônimos.
            Deputados também são comparados por parte do CPF.
          </li>
          <li>Uma sanção pode valer só para o órgão que a aplicou.</li>
          <li>
            A Receita informa só a situação atual da empresa e desde quando ela vale;
            reativações anteriores não aparecem.
          </li>
          <li>
            O site mostra totais e listas dos maiores valores; para cada despesa, siga o link da
            fonte oficial.
          </li>
        </ul>
      </Secao>

      <Secao titulo="Privacidade e LGPD">
        <Texto>
          CPF aparece só mascarado (***.456.789-**). Sócios de empresas aparecem só como
          contagem: nomes e documentos de sócios não são publicados.
        </Texto>
        <p className="max-w-3xl">O site não usa cookies, analytics nem fontes externas.</p>
      </Secao>

      <Secao titulo="Baixar os dados">
        <Texto>
          Os dados que alimentam o site estão publicados em arquivos abertos. A descrição de cada
          tabela está nos <a href={MODELOS}>Modelos de dados</a>; a lista de arquivos, no{' '}
          <a href={MANIFESTO}>Manifesto dos dados publicados</a>.
        </Texto>
      </Secao>

      <Secao titulo="Situação das fontes">
        {resumo.estado === 'carregando' && <Carregando />}
        {resumo.estado === 'erro' && (
          <AvisoErro erro={resumo.erro} tentarDeNovo={resumo.tentarDeNovo} />
        )}
        {resumo.estado === 'ok' && <Fontes resumo={resumo.dados} />}
      </Secao>
    </>
  )
}
