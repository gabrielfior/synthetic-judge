"""Roda uma variante do preditor de resultado e escreve o que o hillclimb lê.

    uv run python eval_preditor.py --variante baseline            # validação (A + B)
    uv run python eval_preditor.py --variante v1 --conjunto teste # só no fim
    uv run python eval_preditor.py --variante v1 --limit 5        # canário

Layout (o contrato de results.jsonl, traces/ e errors.jsonl da skill claude-api):

    data/eval/decisao/hill/<variante>/{prompt.md, config.json, results.jsonl,
                                       summary.json, errors.jsonl, traces/}

A validação de `build_decisao.py` é partida em A (o analisador lê os traces) e B
(só é pontuada: escolhe a variante). O teste temporal não é aberto antes do fim.
`config.json`: modelo, raciocinio, k (vizinhos), prior, lr, max_tokens.
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval_sentenca import Modelo
from sj import decisao as D
from sj import preditor as P
from sj.llm import _env

DIR = Path("data/eval/decisao")
HILL = DIR / "hill"
SPLIT = HILL / "split.json"
CONJUNTOS = ("A", "B", "val", "teste")


def carregar() -> list[dict]:
    return [json.loads(l) for l in (DIR / "casos.jsonl").open()]


def dividir_val(casos: list[dict]) -> dict:
    """A e B: a validação partida ao acaso, estratificada por resultado. Fixa."""
    if SPLIT.exists():
        return json.loads(SPLIT.read_text())
    val = sorted((c for c in casos if c["conjunto"] == "val"), key=lambda c: c["id"])
    rng = random.Random(11)
    por: dict[str, list[str]] = {}
    for c in val:
        por.setdefault(c["resultado"], []).append(c["id"])
    a, b = [], []
    for ids in por.values():
        rng.shuffle(ids)
        meio = len(ids) * 4 // 10   # A fica com 40%: o analisador lê pouco, B pontua mais
        a += ids[:meio]
        b += ids[meio:]
    HILL.mkdir(parents=True, exist_ok=True)
    SPLIT.write_text(json.dumps({"A": sorted(a), "B": sorted(b)}))
    return {"A": sorted(a), "B": sorted(b)}


def estado() -> None:
    m = lambda i, l, k="binary", **kw: {"id": i, "label": l, "kind": k, **kw}  # noqa: E731
    (HILL / "_state.json").write_text(json.dumps({
        "goal": {"target": "resultado", "direction": "higher", "hold": ["procedencia"]},
        "approve_each_round": False,
        "metrics": [m("resultado", "Resultado"), m("procedencia", "Procedência"),
                    m("ordinal", "Ordinal", "float"),
                    m("brier", "Brier", "float", better="lower")],
        "perf_fields": [{"id": "latency_s", "label": "latência", "unit": "s"}],
        "split": "A e B em split.json; teste temporal em casos.jsonl (conjunto=teste)",
    }, ensure_ascii=False, indent=1))


def rodar_caso(c: dict, rep: int, cfg: dict, sistema: str, modelo: Modelo, rec,
               lr: dict, treino: list[dict], n_treino: int, grupo: str) -> tuple[dict, list]:
    viz = rec.vizinhos(c, cfg["k"]) if cfg.get("k") and rec else None
    user = P.montar(c, cfg, treino=treino, vizinhos=viz, lr=lr.get(c["id"]), n_treino=n_treino)
    r = modelo(sistema, user)
    trace = [{"role": "system", "content": sistema}, {"role": "user", "content": user},
             {"role": "assistant", "content": r["texto"]}]
    row = {"prompt_id": c["id"], "prompt": c["relatorio"], "rep": rep,
           "tags": [c.get("classe") or c.get("grupo") or "sem classe", c["resultado"]],
           "model": r["modelo"], "usage": r["usage"], "latency_s": round(r["latencia"], 2),
           "stop_reason": r["parada"], "meta": {"conjunto": grupo}}
    if r["parada"] == "length":
        return {**row, "status": "truncated", "grade": {}}, trace
    p = P.ler(r["texto"])
    notas, expl = P.notas(c["resultado"], p)
    return {**row, "status": "ok", "grade": notas, "explanation": expl}, trace


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", required=True)
    ap.add_argument("--conjunto", choices=CONJUNTOS, default="val")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    casos = carregar()
    ab = dividir_val(casos)
    pasta = HILL / args.variante
    cfg = json.loads((pasta / "config.json").read_text())
    sistema = (pasta / "prompt.md").read_text().strip()
    estado()

    treino = [c for c in casos if c["conjunto"] == "treino"]
    if args.conjunto == "teste":
        alvo = [c for c in casos if c["conjunto"] == "teste"]
        pool = treino + [c for c in casos if c["conjunto"] == "val"]
        grupos = {c["id"]: "teste" for c in alvo}
    else:
        ids = {"A": set(ab["A"]), "B": set(ab["B"]), "val": set(ab["A"]) | set(ab["B"])}[
            args.conjunto]
        alvo = [c for c in casos if c["id"] in ids]
        pool = treino
        grupos = {c["id"]: ("A" if c["id"] in ab["A"] else "B") for c in alvo}
    if args.limit:
        random.Random(0).shuffle(alvo)
        alvo = alvo[:args.limit]

    env = _env()
    modelo = Modelo(cfg["modelo"], cfg.get("max_tokens", 300), env, cfg.get("raciocinio", "none"))
    rec = P.Recuperador(pool) if cfg.get("k") else None
    lr = P.probs_lr(pool, alvo) if cfg.get("lr") else {}

    (pasta / "traces").mkdir(exist_ok=True)
    res, erros = pasta / "results.jsonl", pasta / "errors.jsonl"
    feitos = {(json.loads(l)["prompt_id"], json.loads(l)["rep"]) for l in res.open()} \
        if res.exists() else set()
    pend = [c for c in alvo if (c["id"], 0) not in feitos]
    print(f"{args.variante}: {len(pend)} de {len(alvo)} a rodar ({args.conjunto}) "
          f"modelo={cfg['modelo']} k={cfg.get('k', 0)} prior={cfg.get('prior', False)} "
          f"lr={cfg.get('lr', False)} raciocinio={cfg.get('raciocinio', 'none')}", flush=True)

    trava, t0, ok, falhas = threading.Lock(), time.time(), 0, 0
    with ThreadPoolExecutor(args.workers) as pool_ex:
        fut = {pool_ex.submit(rodar_caso, c, 0, cfg, sistema, modelo, rec, lr, pool, len(pool),
                              grupos[c["id"]]): c for c in pend}
        for f in as_completed(fut):
            c = fut[f]
            try:
                linha, trace = f.result()
                with trava:
                    with res.open("a") as o:
                        o.write(json.dumps(linha, ensure_ascii=False) + "\n")
                    (pasta / "traces" / f"{c['id'].replace('|', '_')}_rep0.json").write_text(
                        json.dumps(trace, ensure_ascii=False, indent=1))
                ok += 1
            except Exception as e:  # ilegível ou erro de serviço: não vira "previu errado"
                falhas += 1
                with trava, erros.open("a") as o:
                    o.write(json.dumps({"prompt_id": c["id"], "rep": 0,
                                        "class": "serving_or_parse", "error": repr(e)[:300],
                                        "ts": time.time()}, ensure_ascii=False) + "\n")
            n = ok + falhas
            if n % 50 == 0 or n == len(fut):
                print(f"{n}/{len(fut)} (erros {falhas}) {time.time() - t0:.0f}s", flush=True)
    resumo(pasta, args.conjunto)


def resumo(pasta: Path, conjunto: str) -> None:
    rows = [json.loads(l) for l in (pasta / "results.jsonl").open()]
    out = {}
    for nome in ("A", "B", "teste"):
        rs = [r for r in rows if r["meta"]["conjunto"] == nome and r["status"] == "ok"]
        if not rs:
            continue
        def med(k):
            v = [r["grade"][k] for r in rs if k in r["grade"]]
            return sum(v) / len(v), len(v), v
        linha = {"n": len(rs)}
        for k in ("resultado", "procedencia", "ordinal", "brier"):
            m, n, v = med(k)
            linha[k] = round(m, 4)
            if k in ("resultado", "procedencia"):
                linha[k + "_ic"] = [round(x, 3) for x in D.wilson(sum(v), n)]
            else:
                linha[k + "_ic"] = [round(x, 3) for x in D.bootstrap(v)]
        linha["parcial_prevista"] = round(sum("previsto=parcialmente_procedente" in
                                              r["explanation"]["resultado"] for r in rs) / len(rs), 3)
        out[nome] = linha
        print(f"{nome:6s} n={linha['n']:3d} resultado {linha['resultado']:.1%} "
              f"{linha['resultado_ic']} | procedência {linha['procedencia']:.1%} "
              f"{linha['procedencia_ic']} | ordinal {linha['ordinal']:.3f} | Brier "
              f"{linha['brier']:.3f} | %parcial {linha['parcial_prevista']:.0%}")
    sj = pasta / "summary.json"
    antigo = json.loads(sj.read_text()) if sj.exists() else {}
    sj.write_text(json.dumps({**antigo, "resultado": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
