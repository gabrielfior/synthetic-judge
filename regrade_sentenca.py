"""Recalcula as notas por regra (A1 a A4) do eval da sentença com o extrator de hoje.

O gabarito e a leitura da sintética vêm de `sj/features.py`. Quando o extrator
muda, as saídas do gerador e as notas do juiz (B1 a B3) continuam valendo; só o
gabarito e as notas por regra mudam. Nenhuma chamada de modelo.

    uv run python regrade_sentenca.py
"""
import json
import shutil
from pathlib import Path

from sj import sentenca as S

FLUXO = Path("data/eval/sentenca")
A = ("resultado", "dm_concedido", "dm_valor", "artigos", "parseavel")


def main() -> None:
    casos = {c["id"]: c for c in map(json.loads, (FLUXO / "cases.jsonl").open())}
    mudou = 0
    for c in casos.values():
        e = c["expected"]
        x = S.extrair(c["relatorio"], f"{e['fundamentacao']}\n{e['dispositivo']}")
        novo = {"resultado": x["resultado"], "dm_concedido": x["dm_concedido"],
                "dm_valor": x["dm_valor"]}
        if any(e[k] != v for k, v in novo.items()):
            mudou += 1
        e.update(novo)
        c["tags"] = [c["tags"][0], x["resultado"]]
    shutil.copy(FLUXO / "cases.jsonl", FLUXO / "cases.jsonl.pre_regrade")
    (FLUXO / "cases.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in casos.values()) + "\n")

    arq = FLUXO / "baseline/results.jsonl"
    shutil.copy(arq, FLUXO / "baseline/results.jsonl.pre_regrade")
    rows = [json.loads(l) for l in arq.open()]
    for r in rows:
        c = casos[r["prompt_id"]]
        e = c["expected"]
        real = {"resultado": e["resultado"], "dm_concedido": e["dm_concedido"],
                "dm_valor": e["dm_valor"],
                "artigos": S._artigos(f"{e['fundamentacao']}\n{e['dispositivo']}")}
        trace = json.loads(next((FLUXO / "baseline/traces").glob(
            f"{r['prompt_id'].replace('|', '_')}_rep{r['rep']}.json")).read_text())
        sint = next(t["content"] for t in trace if t["role"] == "assistant")
        sx = S.extrair(c["relatorio"], sint)
        notas, expl = S.notas_por_regra(real, sx)
        notas["parseavel"] = float(sx["parseavel"])
        for k in A:
            r["grade"].pop(k, None)
            r["explanation"].pop(k, None)
        r["grade"].update(notas)
        r["explanation"].update(expl)
        r["tags"] = c["tags"]
    arq.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"{mudou} dos {len(casos)} gabaritos mudaram; {len(rows)} linhas recalculadas")


if __name__ == "__main__":
    main()
