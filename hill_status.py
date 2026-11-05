"""Tabela de status do hillclimb do preditor: cada variante contra o baseline, em A e B.

    uv run python hill_status.py [variantes...]     # padrão: todas as que têm resultados

O delta contra o baseline é pareado por caso, com IC95 por bootstrap sobre as
diferenças. Só B decide (A é o que o analisador lê).
"""
import json
import sys
from pathlib import Path

from sj import decisao as D

HILL = Path("data/eval/decisao/hill")


def linhas(v: str) -> dict:
    p = HILL / v / "results.jsonl"
    return {json.loads(l)["prompt_id"]: json.loads(l) for l in p.open()} if p.exists() else {}


def media(rs, k):
    v = [r["grade"][k] for r in rs if r["status"] == "ok" and k in r["grade"]]
    return sum(v) / len(v) if v else float("nan")


def main() -> None:
    vs = sys.argv[1:] or sorted(d.name for d in HILL.iterdir()
                               if d.is_dir() and (d / "results.jsonl").exists())
    vs = sorted(vs, key=lambda v: (v != "baseline", v))
    base = linhas("baseline")
    print(f"{'variante':10s} {'A resultado':>11s} {'B resultado':>11s} {'B procedência':>13s} "
          f"{'B ordinal':>9s} {'B Brier':>7s} {'%parcial B':>10s}   Δ resultado B vs baseline (IC95)")
    for v in vs:
        L = linhas(v)
        A = [r for r in L.values() if r["meta"]["conjunto"] == "A"]
        B = [r for r in L.values() if r["meta"]["conjunto"] == "B"]
        parc = sum("previsto=parcialmente_procedente" in r["explanation"]["resultado"]
                   for r in B if r["status"] == "ok") / max(1, len(B))
        delta = ""
        if v != "baseline":
            d = [r["grade"]["resultado"] - base[r["prompt_id"]]["grade"]["resultado"]
                 for r in B if r["status"] == "ok" and r["prompt_id"] in base]
            lo, hi = D.bootstrap(d)
            delta = f"{sum(d) / len(d):+.3f} [{lo:+.3f}, {hi:+.3f}] n={len(d)}"
        print(f"{v:10s} {media(A, 'resultado'):11.1%} {media(B, 'resultado'):11.1%} "
              f"{media(B, 'procedencia'):13.1%} {media(B, 'ordinal'):9.3f} "
              f"{media(B, 'brier'):7.3f} {parc:10.0%}   {delta}")


if __name__ == "__main__":
    main()
