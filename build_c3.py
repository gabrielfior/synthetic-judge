"""Planilha cega para calibrar o juiz do eval da sentença (C3).

Sorteia 30 sentenças sintéticas (15 em que o juiz disse que a razão de decidir é a
mesma, 15 em que disse que não) e monta um markdown com o relatório e as duas
sentenças como A e B, na mesma ordem sorteada que o juiz viu e sem a nota dele.
O gabarito do juiz fica em `c3_juiz.json`, num arquivo à parte.

    uv run python build_c3.py
    # responda em data/eval/sentenca/c3_planilha.md, depois:
    uv run python build_c3.py --corrigir
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from sj.sentenca import wilson

FLUXO = Path("data/eval/sentenca")
N_POR_LADO = 15


def _traco(trace: list[dict]) -> str:
    return next(t["content"] for t in trace if t["role"] == "assistant")


def montar() -> None:
    casos = {c["id"]: c for c in map(json.loads, (FLUXO / "cases.jsonl").open())}
    rows = [r for r in map(json.loads, (FLUXO / "baseline/results.jsonl").open())
            if r["rep"] == 0]
    rng = random.Random(3)
    sim = [r for r in rows if r["grade"]["mesma_razao"] == 1.0]
    nao = [r for r in rows if r["grade"]["mesma_razao"] == 0.0]
    rng.shuffle(sim)
    rng.shuffle(nao)
    escolhidos = sim[:N_POR_LADO] + nao[:N_POR_LADO]
    rng.shuffle(escolhidos)

    out = ["# C3: sua leitura, sem ver a nota do juiz\n",
           "Para cada caso, leia o relatório e as sentenças A e B. Responda **sim** "
           "ou **não** à pergunta:\n",
           "> A razão central que decide o caso (o fato ou a regra que faz o pedido "
           "ser aceito, em parte ou rejeitado) é a mesma nas duas sentenças? Palavras "
           "diferentes para a mesma razão contam como a mesma.\n",
           "Escreva a resposta na linha `Resposta:`. Uma das duas é a do juiz e a "
           "outra é do gerador; não diga qual é qual (a ordem foi sorteada).\n"]
    gab = {}
    for i, r in enumerate(escolhidos, 1):
        c = casos[r["prompt_id"]]
        trace = json.loads(next((FLUXO / "baseline/traces").glob(
            f"{r['prompt_id'].replace('|', '_')}_rep0.json")).read_text())
        sint = _traco(trace)
        real = f"{c['expected']['fundamentacao']}\n{c['expected']['dispositivo']}"
        a, b = (sint, real) if r["meta"]["ordem_b1"] == "sintética=A" else (real, sint)
        out += [f"\n---\n\n## Caso {i}\n", "**Relatório**\n", "````text",
                c["relatorio"], "````\n", "**Sentença A**\n", "````text", a.strip(),
                "````\n", "**Sentença B**\n", "````text", b.strip(), "````\n",
                "Resposta: \n"]
        gab[str(i)] = {"id": r["prompt_id"], "juiz": r["grade"]["mesma_razao"] == 1.0,
                       "motivo": r["explanation"]["mesma_razao"]}
    (FLUXO / "c3_planilha.md").write_text("\n".join(out))
    (FLUXO / "c3_juiz.json").write_text(json.dumps(gab, ensure_ascii=False, indent=1))
    print(f"{len(gab)} casos em {FLUXO / 'c3_planilha.md'}")


def corrigir() -> None:
    gab = json.loads((FLUXO / "c3_juiz.json").read_text())
    texto = (FLUXO / "c3_planilha.md").read_text()
    respostas = re.findall(r"^Resposta:\s*(\S.*)$", texto, re.M)
    if len(respostas) != len(gab):
        raise SystemExit(f"{len(respostas)} respostas preenchidas, esperava {len(gab)}")
    humano = [r.strip().lower().startswith("s") for r in respostas]
    igual = [h == g["juiz"] for h, g in zip(humano, gab.values())]
    lo, hi = wilson(sum(igual), len(igual))
    print(f"concordância {sum(igual)}/{len(igual)} = {sum(igual) / len(igual):.0%} "
          f"(IC95 {lo:.0%} a {hi:.0%})")
    for (k, g), h, ok in zip(gab.items(), humano, igual):
        if not ok:
            print(f"  caso {k}: você={'sim' if h else 'não'} juiz="
                  f"{'sim' if g['juiz'] else 'não'}  {g['motivo'][:160]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrigir", action="store_true")
    corrigir() if ap.parse_args().corrigir else montar()
