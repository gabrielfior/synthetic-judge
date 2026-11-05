# Synthetic Judge

[Português](README.pt-BR.md)

Estimate how **one specific Brazilian judge** is likely to rule on a civil case,
using that judge's own published rulings as the only evidence.

Given a lawyer's free-text description of a case, the system returns an
**outcome estimate with its sample size and uncertainty**: probability of the
claim being upheld, expected time to judgment, and the typical moral-damages award.
It is built for lawyers and firms, not laypeople, and every number is traceable to
a count of real decisions.

> **Status: research prototype.** The pipeline and UI work end to end and have
> been evaluated on held-out rulings. It has **not** been tested with free text
> written by real lawyers (all validation uses the judge's own case summaries or
> a simulated lawyer), and the rule-based extractor has not been checked by a
> human annotator. Nothing here is legal advice.

## How it works

```
 lawyer's text ──► LLM picks a class from a closed taxonomy (29 classes, 6 groups)
                          │
                          ▼
        deterministic Python: historical rates for that class,
        falling back class → group → whole court, with n and intervals
                          │
                          ▼
              dossier: P(upheld), time to judgment, moral damages
```

The LLM is only allowed to **choose from a closed list**; it never produces a
number. All statistics come from deterministic code over the corpus.

Three components, in order of maturity:

1. **Reference-class forecast** (`prognosticar.py`, `/prognostico` UI): the
   pipeline above.
2. **Outcome predictor** (`sj/preditor.py`): predicts the ruling from the case
   summary (prior, nearest neighbours, logistic regression). Evaluated with a
   **temporal split** (train on older rulings, test on the most recent 20%).
3. **Synthetic ruling with LLM-as-a-judge** (`eval_sentenca.py`): an LLM writes
   the ruling from the case summary; a second LLM compares it to the real one.
   The eval harness and baseline exist; the grader is validated by automated
   checks only.

### Measured results (held-out, temporal split)

| Piece | Result |
|---|---|
| Rule-based extractor (outcome / moral damages / amount) vs. LLM second reading | 99.1% / 99.8% / 99.3% agreement |
| Taxonomy v2: Brier score of "upheld" with class vs. without | 0.162 vs. 0.221 |
| Outcome predictor v3: 4-class accuracy / "upheld" accuracy / Brier | 70.1% / 87.0% / 0.114 |

Methodology and baselines: the scripts (`build_*.py`, `eval_*.py`) document their own protocol in their docstrings; the design notes are kept out of this repository.

## Repository layout

| Path | Contents |
|---|---|
| `sj/` | Library: HTML parsers for the TJSP e-SAJ portal (`tjsp.py`, `cpopg.py`, `pastadigital.py`), rule-based extractor (`features.py`), taxonomy and reference classes, forecast pipeline, predictor, LLM client |
| `coletar_corpus.py`, `fetch_*.py` | Corpus collection from the public court portal |
| `build_*.py`, `eval_*.py` | Dataset builders and evaluation harnesses |
| `prognosticar.py` | CLI for the forecast (`--api` emits JSON for the UI) |
| `frontend/` | Next.js app: chat over the rulings (`/`) and forecast UI (`/prognostico`) |
| `tests/` | 366 Python tests, mostly on synthetic data |

## Getting started

Requires [`uv`](https://docs.astral.sh/uv/) and, for the UI, `pnpm`.

```bash
cp .env.example .env     # fill in the values below
uv sync
uv run pytest            # Python tests
```

Configuration lives in `.env` (git-ignored):

| Variable | Meaning |
|---|---|
| `JUDGE_ID` | The judge's `cdAgente` in the e-SAJ CJPG search |
| `JUDGE_NAME` | The judge's name as e-SAJ spells it (used only by tests that read real portal pages) |
| `INFERENCE_API_KEY`, `INFERENCE_BASE_URL` | Anthropic-Messages-compatible inference endpoint |

The target judge is deliberately **not** hard-coded or named anywhere in the repo.

```bash
uv run python coletar_corpus.py data/corpus.parquet     # collect rulings (~18 min)
uv run python prognosticar.py "describe the case here"  # forecast from the CLI
cd frontend && pnpm install && pnpm dev                 # http://localhost:3000/prognostico
```

## Regenerating the data

Nothing under `data/` is committed; everything is rebuilt from the public portal
plus LLM calls. With `JUDGE_ID` set in `.env`:

| Artifact | Command |
|---|---|
| `data/corpus.parquet` (all of the judge's rulings) | `uv run python coletar_corpus.py data/corpus.parquet` (~18 min) |
| `data/prognostico/base.jsonl` (one row per ruling) | `uv run python build_base.py --classes data/eval/taxonomia_v2` |
| `data/eval/taxonomia_v2/classes_*.jsonl` (LLM class labels) | `eval_taxonomia.py`, then `classificar_corpus.py` (costs LLM calls; changing it invalidates the reported numbers) |
| `data/eval/decisao/` (outcome task and temporal split) | `uv run python build_decisao.py` |
| `data/eval/decisao/hill/<variant>/` (predictor variants) | `uv run python eval_preditor.py --variante vN` |
| `data/eval/sentenca/` (synthetic-ruling eval) | `build_casos_sentenca.py`, then `eval_sentenca.py` |

Run `build_base.py` with `--classes`; without it, it falls back to the v1 taxonomy
and leaves a truncated `base.jsonl`.

## Data and privacy

Rulings are public court records from TJSP, but the corpus is **not
distributed** with this repository: `data/` and the real portal pages used by a
few parser tests (`tests/fixtures/`) are git-ignored because they contain the
names of parties and lawyers. Those tests skip when the fixtures are absent.
See [`tests/fixtures/README.md`](tests/fixtures/README.md).

## Known limitations

- Single judge, single court (Limeira/SP, ~4,000 rulings in a ~2.7-year window),
  so intervals are wide for rare classes.
- Validation inputs are not real lawyer-written text; the input gap is
  measured only with a simulated lawyer.
- The extractor's accuracy is measured against a second LLM reading, not a human.
- Temporal drift: the model assumes the judge's past behaviour predicts future behaviour.
