# Synthetic Judge

[English](README.md)

Estima como **um juiz brasileiro específico** tende a decidir um caso cível,
usando como única evidência as sentenças publicadas por esse próprio juiz.

A partir da descrição de um caso em texto livre por um advogado, o sistema devolve uma
**estimativa de resultado com tamanho de amostra e incerteza**: probabilidade de
procedência, prazo até a sentença e valor típico de dano moral. O público é
advogado ou escritório, não a parte leiga, e cada número remonta a uma contagem de
decisões reais.

> **Status: protótipo de pesquisa.** O pipeline e a UI funcionam de ponta a
> ponta e foram avaliados em sentenças separadas para teste. **Não** foram
> testados com texto escrito por advogados reais (toda a validação usa o relatório
> do próprio juiz ou um advogado simulado), e o extrator por regras não foi
> conferido por anotador humano. Nada aqui é aconselhamento jurídico.

## Como funciona

```
 texto do advogado ──► LLM escolhe uma classe de uma taxonomia fechada (29 classes, 6 grupos)
                              │
                              ▼
          Python determinístico: taxas históricas da classe, com
          recuo classe → grupo → vara inteira, com n e intervalos
                              │
                              ▼
          dossiê: P(procedência), prazo, dano moral
```

A LLM só **escolhe de uma lista fechada**; ela nunca produz um número. Toda
estatística vem de código determinístico sobre o corpus.

Três peças, em ordem de maturidade:

1. **Prognóstico por classe de referência** (`prognosticar.py`, UI `/prognostico`).
2. **Preditor de resultado** (`sj/preditor.py`): prevê o resultado a partir do
   relatório (prior, vizinhos, regressão logística), com **divisão temporal**
   (treino nas sentenças antigas, teste nos 20% mais recentes).
3. **Sentença sintética com LLM-as-a-judge** (`eval_sentenca.py`): uma LLM escreve
   a sentença a partir do relatório e outra a compara com a real. O eval e a linha
   de base existem; o juiz LLM só foi validado por automação.

### Resultados medidos (teste separado, divisão temporal)

| Peça | Resultado |
|---|---|
| Extrator por regra (resultado / dano moral / valor) contra segunda leitura por LLM | 99,1% / 99,8% / 99,3% de concordância |
| Taxonomia v2: Brier de procedência com classe vs. sem classe | 0,162 vs. 0,221 |
| Preditor v3: acerto em 4 classes / acerto de procedência / Brier | 70,1% / 87,0% / 0,114 |

Metodologia e linhas de base: cada script (`build_*.py`, `eval_*.py`) documenta o próprio protocolo na docstring; as notas de desenho não estão neste repositório.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `sj/` | Biblioteca: parsers HTML do e-SAJ (TJSP), extrator por regras, taxonomia e classes de referência, pipeline, preditor, cliente LLM |
| `coletar_corpus.py`, `fetch_*.py` | Coleta no portal público do tribunal |
| `build_*.py`, `eval_*.py` | Montagem de bases e harnesses de avaliação |
| `prognosticar.py` | CLI do prognóstico (`--api` emite JSON para a UI) |
| `frontend/` | App Next.js: chat sobre as sentenças (`/`) e prognóstico (`/prognostico`) |
| `tests/` | 366 testes Python, quase todos com dados sintéticos |

## Começando

Requer [`uv`](https://docs.astral.sh/uv/) e, para a UI, `pnpm`.

```bash
cp .env.example .env     # preencha as variáveis abaixo
uv sync
uv run pytest
```

| Variável | Significado |
|---|---|
| `JUDGE_ID` | `cdAgente` do juiz na busca CJPG do e-SAJ |
| `JUDGE_NAME` | Nome do juiz como o e-SAJ o grafa (só os testes com páginas reais usam) |
| `INFERENCE_API_KEY`, `INFERENCE_BASE_URL` | Endpoint de inferência compatível com Anthropic Messages |

O juiz-alvo **não** está escrito em nenhum lugar do repositório.

```bash
uv run python coletar_corpus.py data/corpus.parquet     # coleta (~18 min)
uv run python prognosticar.py "descreva o caso aqui"
cd frontend && pnpm install && pnpm dev                 # http://localhost:3000/prognostico
```

## Regenerando os dados

Nada em `data/` é versionado; tudo se refaz a partir do portal público e de
chamadas de LLM. Com `JUDGE_ID` no `.env`:

| Artefato | Comando |
|---|---|
| `data/corpus.parquet` (todas as sentenças do juiz) | `uv run python coletar_corpus.py data/corpus.parquet` (~18 min) |
| `data/prognostico/base.jsonl` (uma linha por sentença) | `uv run python build_base.py --classes data/eval/taxonomia_v2` |
| `data/eval/taxonomia_v2/classes_*.jsonl` (classes atribuídas por LLM) | `eval_taxonomia.py`, depois `classificar_corpus.py` (gasta chamadas de LLM; mudar isso invalida os números reportados) |
| `data/eval/decisao/` (tarefa de decidir e divisão temporal) | `uv run python build_decisao.py` |
| `data/eval/decisao/hill/<variant>/` (variantes do preditor) | `uv run python eval_preditor.py --variante vN` |
| `data/eval/sentenca/` (eval da sentença sintética) | `build_casos_sentenca.py`, depois `eval_sentenca.py` |

Rode `build_base.py` sempre com `--classes`; sem isso ele usa a taxonomia v1 e
deixa um `base.jsonl` truncado.

## Dados e privacidade

As sentenças são públicas, mas o corpus **não é distribuído** neste repositório:
`data/` e as páginas reais usadas por alguns testes de parser (`tests/fixtures/`)
ficam fora do git porque contêm nomes de partes e advogados. Esses testes são
pulados quando as fixtures não existem. Veja [`tests/fixtures/README.md`](tests/fixtures/README.md).

## Limitações conhecidas

- Um juiz, uma vara (Limeira/SP, ~4.000 sentenças em ~2,7 anos): intervalos largos nas classes raras.
- A validação não usa texto de advogado real; a lacuna de entrada só foi medida com advogado simulado.
- A acurácia do extrator é medida contra uma segunda leitura por LLM, não contra humano.
- Deriva temporal: assume que o comportamento passado do juiz prediz o futuro.
