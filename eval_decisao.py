"""Linhas de base e métricas da tarefa de decidir (resultado a partir do relatório).

    uv run python eval_decisao.py --baseline majority classe lr
    uv run python eval_decisao.py --baseline gerador        # chama o LLM (val e teste)
    uv run python eval_decisao.py --tabela                  # compara tudo o que já rodou

As previsões de cada método ficam em `data/eval/decisao/preds_<nome>.jsonl` (uma
linha por caso: `id`, `conjunto`, `pred`, `p_proc`), para comparar métodos caso a
caso depois. A validação serve para iterar; o teste temporal só para o relatório
final, e as linhas de base não são ajustadas nele.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sj import decisao as D
from sj import sentenca as S

DIR = Path("data/eval/decisao")
METODOS = ("majority", "classe", "lr", "gerador")
MIN_N = 10  # casos mínimos numa classe ou grupo para a moda valer


def carregar() -> list[dict]:
    return [json.loads(l) for l in (DIR / "casos.jsonl").open()]


def _gravar(nome: str, preds: list[dict]) -> None:
    with open(DIR / f"preds_{nome}.jsonl", "w") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def _dist(cs: list[dict]) -> dict[str, int]:
    return dict(Counter(c["resultado"] for c in cs))


# --- as linhas de base sem LLM ----------------------------------------------


def base_majority(casos: list[dict]) -> list[dict]:
    """Sempre o resultado mais comum do treino, com a taxa de procedência dele."""
    treino = [c for c in casos if c["conjunto"] == "treino"]
    dist = _dist(treino)
    m, p = D.moda(dist), D.p_procedencia(dist)
    return [{"id": c["id"], "conjunto": c["conjunto"], "pred": m, "p_proc": p}
            for c in casos if c["conjunto"] in ("val", "teste")]


def base_classe(casos: list[dict]) -> list[dict]:
    """O resultado mais comum da classe do caso (Limeira, treino); sem n, o do grupo."""
    treino = [c for c in casos if c["conjunto"] == "treino"]
    por_classe, por_grupo = D.taxa_por("classe", treino), D.taxa_por("grupo", treino)
    glob = _dist(treino)
    out = []
    for c in casos:
        if c["conjunto"] not in ("val", "teste"):
            continue
        dist = glob
        for chave, tabela in (("classe", por_classe), ("grupo", por_grupo)):
            d = tabela.get(c.get(chave) or "")
            if d and sum(d.values()) >= MIN_N:
                dist = d
                break
        out.append({"id": c["id"], "conjunto": c["conjunto"], "pred": D.moda(dist),
                    "p_proc": D.p_procedencia(dist)})
    return out


def _lr(treino: list[dict], alvo: list[dict]) -> list[dict]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    # hiperparâmetros fixos, escolhidos antes de olhar a validação ou o teste
    m = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True,
                                      max_features=80000),
                      LogisticRegression(C=3, max_iter=3000))
    m.fit([c["relatorio"] for c in treino], [c["resultado"] for c in treino])
    classes = list(m.classes_)
    out = []
    for c, pr in zip(alvo, m.predict_proba([c["relatorio"] for c in alvo])):
        p = dict(zip(classes, pr))
        merito = sum(p.get(r, 0) for r in D.ORDINAL)
        out.append({"id": c["id"], "conjunto": c["conjunto"],
                    "pred": max(p, key=p.get),
                    "p_proc": sum(p.get(r, 0) for r in D.PROCEDENCIA) / merito})
    return out


def base_lr(casos: list[dict]) -> list[dict]:
    """TF-IDF + regressão logística. A validação usa só o treino; o teste, treino + validação."""
    treino = [c for c in casos if c["conjunto"] == "treino"]
    val = [c for c in casos if c["conjunto"] == "val"]
    teste = [c for c in casos if c["conjunto"] == "teste"]
    return _lr(treino, val) + _lr(treino + val, teste)


# --- a linha de base com LLM: o gerador de hoje, lido pelo extrator ----------


def base_gerador(casos: list[dict], workers: int = 8) -> list[dict]:
    """O gerador zero-shot escreve a sentença; o extrator lê o resultado dela.

    É o app de hoje: a decisão que ele toma ao escrever. Saída cortada no limite de
    tokens ou sem dispositivo reconhecível fica com `pred` vazio e conta como erro.
    """
    from eval_sentenca import GERADOR, MAX_TOKENS_GERADOR, Modelo
    from sj.llm import _env
    modelo = Modelo(GERADOR, MAX_TOKENS_GERADOR, _env())
    arq = DIR / "preds_gerador.jsonl"
    feitos = {json.loads(l)["id"]: json.loads(l) for l in arq.open()} if arq.exists() else {}
    alvo = [c for c in casos if c["conjunto"] in ("val", "teste") and c["id"] not in feitos]
    print(f"gerador: {len(alvo)} a gerar, {len(feitos)} já feitos", flush=True)
    trava, t0 = threading.Lock(), time.time()

    def um(c):
        r = modelo(S.SISTEMA_GERADOR, c["relatorio"])
        pred = (S.extrair(c["relatorio"], r["texto"])["resultado"]
                if r["parada"] != "length" else None)
        return {"id": c["id"], "conjunto": c["conjunto"], "pred": pred, "p_proc": None,
                "sintetica": r["texto"], "parada": r["parada"]}

    n = erros = 0
    with ThreadPoolExecutor(workers) as pool, arq.open("a") as o:
        fut = {pool.submit(um, c): c for c in alvo}
        for f in as_completed(fut):
            n += 1
            try:
                linha = f.result()
                with trava:
                    o.write(json.dumps(linha, ensure_ascii=False) + "\n")
                    o.flush()
                feitos[linha["id"]] = linha
            except Exception as e:  # nunca vira "previu errado": fica de fora e é contado
                erros += 1
                with trava, (DIR / "erros_gerador.jsonl").open("a") as eo:
                    eo.write(json.dumps({"id": fut[f]["id"], "erro": repr(e)}) + "\n")
            if n % 50 == 0:
                print(f"{n}/{len(alvo)} (erros {erros}) {time.time() - t0:.0f}s", flush=True)
    return list(feitos.values())


BASES = {"majority": base_majority, "classe": base_classe, "lr": base_lr,
         "gerador": base_gerador}


# --- a tabela ---------------------------------------------------------------


def tabela(casos: list[dict]) -> None:
    real = {c["id"]: c["resultado"] for c in casos}
    base = {c["id"]: c["conjunto"] for c in casos}
    linhas = []
    for nome in METODOS:
        arq = DIR / f"preds_{nome}.jsonl"
        if not arq.exists():
            continue
        preds = [json.loads(l) for l in arq.open()]
        for conj in ("val", "teste"):
            ps = [p for p in preds if p["conjunto"] == conj]
            if not ps:
                continue
            m = D.metricas([(real[p["id"]], p["pred"], p["p_proc"]) for p in ps])
            linhas.append((nome, conj, m))
    print(f"{'método':10s} {'conj':6s} {'n':>4s}  {'resultado (IC95)':22s} "
          f"{'procedência (IC95)':22s} {'ordinal':>8s} {'Brier':>7s} {'%parcial':>8s} "
          f"{'extinto':>8s}")
    for nome, conj, m in linhas:
        r, p = m["resultado_ic"], m["procedencia_ic"]
        brier = f"{m['brier']:.3f}" if "brier" in m else "    -"
        ext = f"{m['extinto_recall']:.0%}" if m["extinto_recall"] is not None else "-"
        print(f"{nome:10s} {conj:6s} {m['n']:4d}  "
              f"{m['resultado']:.1%} [{r[0]:.0%},{r[1]:.0%}]".ljust(44)
              + f" {m['procedencia']:.1%} [{p[0]:.0%},{p[1]:.0%}]".ljust(24)
              + f" {m['ordinal']:8.3f} {brier:>7s} {m['parcial_prevista']:8.0%} {ext:>8s}")
    real_dist = {conj: Counter(c["resultado"] for c in casos if c["conjunto"] == conj)
                 for conj in ("val", "teste")}
    for conj, d in real_dist.items():
        n = sum(d.values())
        print(f"real {conj}: " + ", ".join(f"{k} {v / n:.0%}" for k, v in d.most_common()))
    (DIR / "metricas.json").write_text(json.dumps(
        [{"metodo": n, "conjunto": c, **m} for n, c, m in linhas],
        ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", nargs="*", choices=METODOS + ("todos",), default=[])
    ap.add_argument("--tabela", action="store_true")
    args = ap.parse_args()
    casos = carregar()
    for nome in (METODOS if "todos" in args.baseline else args.baseline):
        preds = BASES[nome](casos)
        _gravar(nome, preds)
        print(f"{nome}: {len(preds)} previsões")
    tabela(casos)


if __name__ == "__main__":
    main()
