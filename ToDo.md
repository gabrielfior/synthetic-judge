[Resumo - Projeto Justiça]
Idéia é criar um juiz sintético, uma LLM que imita um juiz verdadeiro (como exemplo, Alexandre de Moraes do STF) e é capaz de gerar sentenças semelhantes às do juiz real.
Para isso, devemos extrair dados do Jusbrasil (tenho uma assinatura ativa - https://ia.jusbrasil.com.br/configuracoes).

[GTM]
- Advogados usarão a plataforma para fazer upload de peças
- Essas peças serão submetidas para apreciação do juiz virtual
- O Juiz virtual gera um documento final (a definir - provavelmente uma sentença sintética)
- A sentença sintética é comparada com a sentença real em variadas métricas (rubrics) e uma nota é gerada
- Iremos realizar fine-tuning no futuro (não agora) para otimizar a nota

[Objetivo inicial]
- Download de 10 casos recentes do juiz via Jusbrasil
- Gerar um script Python com uma LLM sendo chamada e gerando uma sentença ou output simples

---

## [Descobertas — investigação de fontes de dados, 2026-08-28]

### Jusbrasil: descartado como fonte primária
- **API Jusbrasil Soluções** (`api.jusbrasil.com.br/docs`): comercial, a partir de
  **R$ 1.000/mês**, contratação só via time de vendas. Pior: a própria página declara
  que **não inclui jurisprudência nem íntegra de decisões** — só capa processual,
  partes, movimentações e petições iniciais na distribuição. Ou seja, não entrega
  o output que precisamos (a sentença).
- **A assinatura do Jus IA (`ia.jusbrasil.com.br`) não dá acesso à API.** São produtos
  distintos.
- **Scraping**: `robots.txt` = `User-agent: * / Disallow: /` (bloqueio total), mais
  Cloudflare com `cf-mitigated: challenge` — curl simples devolve 403. Playwright
  logado passaria, mas viola ToS e é frágil. Risco alto, benefício baixo.

### DataJud (CNJ): útil, mas só metadados
- Grátis, sem cadastro, chave pública documentada. Elasticsearch puro.
- `POST https://api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search`
  com header `Authorization: APIKey <chave>`. Testado e funcionando.
- Aliases: `api_publica_tjsp`, `api_publica_trf1..6`, `api_publica_trt1..24`,
  `api_publica_stj`, `api_publica_tse`, `api_publica_tst`, `api_publica_tre-xx`.
- **Não tem endpoint para o STF.**
- Campos: `numeroProcesso`, `classe`, `assuntos`, `orgaoJulgador`, `movimentos`,
  `dataAjuizamento`, `grau`, `tribunal`.
  **Não tem nome de juiz e não tem texto de decisão.** Serve para amostragem e
  filtro de casos, não para treinar/avaliar o juiz sintético.

### STF: a fonte que funciona (escolhida para o MVP)
- Endpoint interno da SPA de jurisprudência, Elasticsearch:
  `POST https://jurisprudencia.stf.jus.br/api/search/search`
- **Proteção: AWS WAF** (cookie `aws-waf-token`). Consequências práticas:
  - `curl` direto → HTTP 202 com corpo vazio.
  - `fetch()` com payload próprio de dentro da página → **403**. O WAF rejeita
    payloads que não sejam os que a SPA monta.
  - **Só funciona navegando pela SPA com Playwright**, que resolve o desafio JS
    sozinho. Requer User-Agent explícito (o UA default do Playwright é bloqueado).
  - A SPA só dispara a busca se houver `queryString` na URL; `ministro_facet`
    sozinho não dispara.
- Bases: `acordaos`, `decisoes` (monocráticas), `sumulas`, `informativos`.
- Campos relevantes: `relator_processo_nome`, `relator_acordao_nome`,
  `ministro_facet`, `julgamento_data`, `orgao_julgador`, `ementa_texto`,
  **`decisao_texto` (inteiro teor, ~9k–24k chars)**, `inteiro_teor_url` (PDF),
  `partes_lista_texto`, `documental_legislacao_citada_texto`,
  `documental_jurisprudencia_citada_texto`, `documental_tese_texto`.
- Volume: ~41k decisões monocráticas de Alexandre de Moraes.
- **Objetivo inicial atingido**: `spikes/stf_fetch_decisoes.py` baixa as 10 decisões
  mais recentes dele (as capturadas são de 2026-08-27) → `data/stf_decisoes.json`.

---

## [Próximos passos]

### 1. Fechar o gap da peça de entrada (BLOQUEADOR do GTM)
O GTM é "advogado sobe uma peça → juiz sintético devolve a sentença". Hoje temos a
**saída** (decisão) mas não a **entrada** (a peça que a originou). Sem o par
(peça → decisão) não dá para avaliar nada.
- [ ] Investigar se o STF expõe as peças: `portal.stf.jus.br/processos/detalhe.asp?incidente=<seq>`
      (o `externo_seq_objeto_incidente` vem no resultado da busca). `abaPecas.asp` deu 404 —
      achar a aba correta e ver se o PDF da petição é público.
- [ ] Fallback: extrair o **relatório** de dentro da própria `decisao_texto`. Toda decisão
      começa resumindo o que a parte pediu. Isso dá um proxy de "peça" sem precisar do PDF.
      Mais barato e provavelmente suficiente para o MVP.
- [ ] Decidir entre os dois antes de escrever qualquer prompt.

### 2. Revisar a escolha do juiz-alvo
Alexandre de Moraes escreve **decisões monocráticas e acórdãos constitucionais**, não
sentenças. Se o cliente é o advogado que sobe uma petição inicial, o alvo natural é um
**juiz de 1ª instância** (TJSP, p.ex.), onde existe petição inicial → sentença de verdade.
- [ ] Confirmar qual dos dois é o alvo. Muda a fonte de dados inteira.
- [ ] Se for 1ª instância: DataJud dá os metadados, mas o texto da sentença tem que vir
      do e-SAJ/PJe do tribunal. Fazer um spike no TJSP antes de assumir que é viável.

### 3. Pipeline mínimo (depois de 1 e 2)
- [ ] `data/`: armazenar os pares (entrada, decisão real) em JSON.
- [ ] `judge.py`: prompt + chamada Claude gerando a decisão sintética.
- [ ] `eval.py`: rubrics comparando sintética vs. real (dispositivo bate? legislação
      citada bate? jurisprudência citada bate? estrutura?). Começar com métricas
      objetivas antes de LLM-as-judge.

### Riscos
- **Crawling é o risco #1, confirmado.** Tanto Jusbrasil quanto STF são protegidos por WAF.
  A diferença: o STF é público e sem login, então usar Playwright ali é legítimo —
  no Jusbrasil seria violação de ToS de uma conta paga.
- Playwright contra o STF é frágil: qualquer mudança na SPA quebra o coletor.
  Baixar e versionar o corpus cedo, não depender de fetch ao vivo.

---

## [1ª instância — resolvido, 2026-08-28]

Decisão: **TJSP via e-SAJ / CJPG** ("Consulta de Julgados de Primeiro Grau").
`spikes/tjsp_fetch_sentencas.py` → `data/tjsp_sentencas.json` (10 sentenças, split ok).

### Por que essa fonte ganhou
- Pública, **sem login, sem WAF, sem JS** — `requests` puro resolve. Nada de Playwright.
- Traz o **inteiro teor** da sentença + nome do magistrado + classe/assunto/vara/comarca.
- **Resolve o gap da peça de entrada**: a sentença contém o RELATÓRIO, que resume a
  petição inicial (pedido, causa de pedir, valores, defesa). É o par
  (entrada → decisão) que o GTM precisa, sem depender de PDF de petição.

### Spec
- `GET https://esaj.tjsp.jus.br/cjpg/pesquisar.do` (sessão via cookie de `GET /cjpg/`)
- Params: `dadosConsulta.pesquisaLivre`, `dadosConsulta.dtInicio` / `.dtFim` (dd/mm/aaaa),
  `dadosConsulta.ordenacao=DESC`, `tipoNumero=UNIFICADO`,
  `classeTreeSelection.values`, `assuntoTreeSelection.values`, `varasTreeSelection.values`,
  `cdAgente`, `nmAgente`.
- Paginação: `GET /cjpg/trocarDePagina.do?pagina=N`, 10 por página, mesma sessão.
- Resposta: HTML **UTF-8** (não latin-1). Blocos em `<tr class="fundocinza1">`.
  O texto vem duplicado (preview + íntegra) — pegar da ÚLTIMA ocorrência do marcador
  `SENTENÇA|DECISÃO|DESPACHO`.
- **Filtro por juiz**: `nmAgente` NÃO filtra sozinho (o e-SAJ exige `cdAgente`, que só sai
  de um popup `jsp/search/searchAgente.jsp`, que devolve 500 sem os params certos).
  Contorno validado: o nome do juiz aparece no corpo ("Juiz(a) de Direito: Dr(a). X"),
  então **busca livre com o nome entre aspas** dá 100% de precisão.

### Mesmo endpoint em outros tribunais (checado)
- `esaj.tjms.jus.br/cjpg/` — 200, tem campo Magistrado
- `esaj.tjce.jus.br/cjpg/` — 200, tem campo Magistrado
- TJAM 404, TJRN 403, TJBA/TJSC/TJAL/TJPE não responderam.

### Fallback nacional: DJEN (CNJ)
`GET https://comunicaapi.pje.jus.br/api/v1/comunicacao` — REST, JSON, **sem auth**.
Params: `siglaTribunal`, `dataDisponibilizacaoInicio/Fim`, `numeroProcesso`, `itensPorPagina`.
Campos: `texto` (HTML da publicação), `nomeOrgao`, `numero_processo`, `nomeClasse`,
`tipoDocumento`, `destinatarioadvogados`.
Cobre o país todo, mas **não tem nome de magistrado** e o `texto` é a publicação
(intimação/despacho), nem sempre a sentença inteira. Usar só se precisar sair do e-SAJ.

---

## [Próximos passos — atualizados]

- [ ] Escolher o juiz-alvo definitivo. Critério: volume de sentenças no período e
      concentração em poucos assuntos (dá rubrics mais limpas). Rodar o coletor sobre
      alguns candidatos da mesma vara e comparar.
- [ ] Subir para ~50-100 sentenças de um juiz só, filtrando por `classeTreeSelection`
      para manter o corpus homogêneo (ex.: só Procedimento Comum Cível).
- [ ] `judge.py`: prompt recebe `relatorio` → gera `fundamentacao` + `dispositivo`.
- [ ] `eval.py`: começar com métricas objetivas antes de LLM-as-judge —
      resultado bate (procedente / improcedente / parcial)? valor da condenação bate?
      artigos de lei citados batem? honorários no mesmo percentual?
- [ ] Guardar o corpus versionado. Não depender de fetch ao vivo (o e-SAJ muda sem aviso).

### Risco residual
Baixo, comparado ao ponto de partida. O e-SAJ é HTML puro e frágil a mudanças de layout,
mas não tem defesa anti-bot. Manter o `sleep(1)` entre páginas e não paralelizar.

---

## [Corpus escolhido — Limeira/SP, 2026-08-28]

**Juíza: Graziela da Silva Nery — Vara da Fazenda Pública da Comarca de Limeira.**
110 sentenças em `data/corpus.json` (jan/2025 – ago/2026).

### Por que ela
Rodei a descoberta sobre todas as varas de Limeira que produzem sentença de mérito.
Ranking por volume de sentenças utilizáveis (relatório > 1000 chars, dispositivo > 300):

| magistrado | sent | rel_med | disp_med | vara |
|---|---:|---:|---:|---|
| **Graziela da Silva Nery** | **36** | 3470 | 1622 | Vara da Fazenda Pública |
| Gabriel Baldi de Carvalho | 11 | 1833 | 1267 | 3ª Vara Cível |
| Antonio Balthazar De Matos | 9 | 2228 | 801 | 3ª Vara Cível |
| FLAVIO DASSI VIANNA | 7 | 4888 | 2042 | 5ª Vara Cível |
| MARCELLA CALIANI | 6 | 1648 | 1408 | 2ª Vara Cível |
| Guilherme Salvatto Whitaker | 3 | 1342 | 2139 | 1ª Vara Cível |
| o magistrado-alvo | 2 | 2072 | 1002 | 4ª Vara Cível |
| RILTON JOSE DOMINGUES | 2 | 1936 | 1211 | 2ª Vara Cível |
| André Quintela Alves Rodrigues | 2 | 2024 | 1017 | Vara da Família e Sucessões |

(tabela é só 2026; ampliando para 2025 ela chega a 110)

### Qualidade do corpus (verificada)
- 110 processos únicos, sem duplicata.
- Resultados variados — não é degenerado: 49 improcedente, 30 procedente,
  16 outro, 11 extinção, 4 parcialmente procedente.
- Similaridade média entre fundamentações: **0.07** — não é sentença de template.
- Medianas: relatório 1841 chars, fundamentação 3990, dispositivo 796.
- Bônus: o relatório dela resume **a inicial E a contestação**. A entrada do juiz
  sintético fica mais realista do que só a peça do autor.
- Assuntos: Repetição de indébito (32), Adicional de Insalubridade (18),
  Anulação de Débito Fiscal (6), Base de Cálculo (6), IPTU (4), e cauda longa.

### Códigos das varas de Limeira (comarca 320)
Em `sj/limeira.py`. **Pegadinha**: a árvore `varasTreeSelect.do` lista códigos
duplicados para a mesma vara — "320-1" e "320-7011" aparecem ambos como
1ª Vara Cível, mas só "320-1" retorna resultado. Os validados:
`320-1` 1ª Cível · `320-2` 2ª Cível · `320-3` 3ª Cível · `320-4` 4ª Cível ·
`320-7029` 5ª Cível · `320-8` Fazenda Pública · `320-7031` Família e Sucessões.

### Mais duas pegadinhas do CJPG
- Janela de datas **maior que ~1 ano devolve ZERO silenciosamente**. Fatiar em
  janelas de 60 dias e deduplicar por número de processo.
- O texto tem `\xa0` e quebras de linha no meio das expressões ("Ante o\xa0exposto"),
  então os regex de split usam `\s+` entre as palavras. Sem isso, 29 de 30 sentenças
  falhavam o split silenciosamente.

### Código
- `sj/tjsp.py` — cliente + parser do CJPG
- `sj/limeira.py` — códigos das varas
- `discover_juizes.py` — ranqueia magistrados da comarca
- `build_corpus.py` — monta o corpus: `uv run python build_corpus.py "<juiz>" <vara>`

### Próximo passo
`judge.py`: prompt recebe `relatorio` → gera `fundamentacao` + `dispositivo`.
Baseline de avaliação já dá para fazer sem LLM-as-judge: o resultado bate
(procedente/improcedente/parcial/extinção)? o valor dos honorários bate?
os artigos de lei citados batem?

---

## [Documentos disponíveis — auditoria, 2026-08-28]

Auditado nos 110 processos da Graziela (e-SAJ `cpopg` + `pastadigital`).

### Temos (público, sem login)
| item | cobertura | onde |
|---|---|---|
| Sentença, inteiro teor | 110/110 | CJPG, já coletado |
| Split relatório / fundamentação / dispositivo | 110/110 | `data/corpus.json` |
| classe, assunto, comarca, foro, vara, data | 110/110 | idem |
| Partes + advogados | público | `cpopg/show.do` — ainda não coletado |
| Linha do tempo de movimentações | público | idem |
| Demais atos judiciais (liminar, saneamento, decisões interlocutórias, ED) | 32–72 docs/processo | `cpopg/abrirDocumentoVinculadoMovimentacao.do` — ainda não coletado |

### NÃO temos (e não dá para ter sem credencial)
- **Petição inicial, contestação, laudos periciais, provas.**
  A pasta digital completa (`pastadigital/abrirPastaProcessoDigital.do`) exige
  **certificado digital ICP-Brasil** ("Identificar-se"). Sem isso, as peças das
  partes aparecem na linha do tempo apenas como *tipo + data*
  ("Petição Juntada — Tipo: Contestação — 30/06/2026"), sem texto e sem link.
- Só os **atos do juízo** são linkáveis publicamente. Nada das partes.

### O que isso implica
A entrada do juiz sintético é o **relatório** — o resumo que a própria juíza faz
da inicial e da contestação. Verificado no corpus:
- **0/110 relatórios vazam o resultado.** Não há contaminação para a avaliação.
- **86/110 já incluem a contestação** e 28/110 trazem preliminares/prejudiciais.
  A entrada é mais rica do que só a peça do autor.

### Métricas objetivas viáveis (sem LLM-as-judge)
- resultado (procedente/improcedente/parcial/extinção): 110/110
- artigo de lei no dispositivo: 107/110
- honorários: 109/110
- valor em R$: 60/110

---

## [Fluxo do produto]

### Produção (o que o advogado vê)
```
1. Advogado sobe petição inicial + documentos
        ↓
2. [Estágio 0 — "Relator"]  LLM normaliza as peças em um relatório
   no formato e no nível de detalhe que a Graziela usa
        ↓
3. [Estágio 1 — "Juíza sintética"]  relatório → fundamentação + dispositivo
        ↓
4. [Estágio 2 — "Avaliador"]  compara com a sentença real, aplica rubrics, dá nota
```

### Treino/avaliação (o que dá para construir e medir HOJE)
```
relatório real (ground truth)  →  Estágio 1  →  fundamentação + dispositivo sintéticos
                                                          ↓
                                         comparar com os reais do mesmo processo
```
O Estágio 0 fica de fora do loop de avaliação por enquanto.

### O buraco conhecido: distribution shift no Estágio 0
Em produção a entrada do Estágio 1 vem de uma LLM (que leu uma petição crua,
longa e argumentativa). Na avaliação a entrada é texto da própria juíza —
curto, neutro, terceira pessoa, já com contestação e histórico processual.
São distribuições diferentes, e hoje **não dá para validar o Estágio 0**: não
temos nenhum par (petição crua → relatório dela).

Formas de fechar isso depois, em ordem de preferência:
1. Um advogado parceiro fornece petições dos próprios processos (ele tem acesso
   à pasta digital via login) — dá o par real.
2. Gerar petições sintéticas a partir do relatório e checar o round-trip
   (petição sintética → Estágio 0 → relatório ≈ o original). Mais fraco: valida
   consistência, não fidelidade.

Para o MVP, construir o Estágio 0 só para a demo e deixar claro que a nota
reportada mede o Estágio 1.

---

## [Coletor do TJSP — 2026-09-08]

Alvo confirmado: o magistrado-alvo, 4ª Vara Cível de Limeira (`JUDGE_ID`). O
`cdAgente` é a fonte da verdade — o `nmAgente` da URL é decorativo e o e-SAJ o ignora.

Entregue em `fetch_juiz.py`: as N sentenças de mérito mais recentes, cada uma
com a linha do tempo completa do processo e o PDF do inteiro teor. Hoje 10
sentenças / 1.168 movimentações / 461 KB de PDF.

### Não vamos fazer parse de PDF — o texto já vem melhor pelo CJPG
Medido nas 10 sentenças com liteparse (`ocr_enabled=False`, Apache-2.0, ~0,5s
por documento de 5 páginas):

- Os PDFs do TJSP são digitais, com camada de texto. **OCR é desnecessário.**
- O texto do CJPG é **completo**: 9 das 10 batem acima de 0.95 de similaridade
  com o parse do PDF. A décima (1005625-38.2023) deu 0.818, mas a divergência é
  formatação (`#`, `**` do markdown) — testei cinco trechos que o diff acusava
  como ausentes e todos estavam no CJPG.
- O PDF é sempre ~10% maior porque repete mobília de página em cada folha
  (`fls. NNNN`, timbre, endereço do fórum). Ou seja, **o CJPG é mais limpo**,
  não menos completo. É a fonte melhor para alimentar o juiz sintético.
- Os PDFs continuam valendo para conferência manual e como original assinado.

O parse só passaria a valer para os **301 atos do juízo** (decisões, despachos,
decisões interlocutórias de mérito) linkados nas movimentações, onde não existe
alternativa em texto — o `teor_do_ato` cobre só 171 das 1.168 movimentações.
Decisão adiada até sabermos se material interlocutório interessa.

### A peça de entrada continua fora de alcance (confirma o buraco acima)
Dos 301 documentos com PDF público nos 10 processos, **nenhum é peça de parte**.
As 176 movimentações com `tipo_da_peticao` (5 Contestação, 83 Petições Diversas)
têm zero link de documento. A Pasta Digital pública expõe o que o juízo
produziu, não o que as partes protocolaram. Segue valendo o plano das duas
opções acima: advogado parceiro com login, ou petição sintética via Estágio 0.
