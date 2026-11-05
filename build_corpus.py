"""
Monta o corpus de sentenças de um magistrado de Limeira/SP.

Uso:
    uv run python scripts_corpus.py "Graziela da Silva Nery" 320-8
"""
import json
import statistics as st
import sys
from collections import Counter
from datetime import date, timedelta

from sj.tjsp import Consulta, buscar

INICIO, FIM, JANELA = date(2025, 1, 1), date(2026, 8, 25), 60
OUT = "data/corpus.json"


def janelas(inicio, fim, dias):
    """O CJPG devolve zero silenciosamente se a janela passa de ~1 ano."""
    cur = inicio
    while cur < fim:
        prox = min(cur + timedelta(days=dias), fim)
        yield cur.strftime("%d/%m/%Y"), prox.strftime("%d/%m/%Y")
        cur = prox + timedelta(days=1)


def utilizavel(d: dict, magistrado: str) -> bool:
    return (d["tipo"] == "SENTENÇA" and d["split_ok"]
            and d.get("magistrado", "").lower() == magistrado.lower()
            and len(d["relatorio"]) > 1000 and len(d["dispositivo"]) > 300)


def main(magistrado: str, vara: str) -> None:
    vistos, corpus = set(), []
    for ini, fim in janelas(INICIO, FIM, JANELA):
        lote = buscar(Consulta(dt_inicio=ini, dt_fim=fim, varas=vara), paginas=25)
        novas = [d for d in lote
                 if utilizavel(d, magistrado) and d["processo"] not in vistos]
        vistos.update(d["processo"] for d in novas)
        corpus += novas
        print(f"  {ini}–{fim}: {len(lote):>3} docs, +{len(novas)} sentenças")

    for i, d in enumerate(sorted(corpus, key=lambda x: x.get("data_de_disponibilização", ""))):
        d["id"] = f"{i:03d}"
    corpus.sort(key=lambda d: d["id"])

    with open(OUT, "w") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)

    print(f"\n{len(corpus)} sentenças de {magistrado} -> {OUT}")
    if not corpus:
        return
    print(f"relatório  mediano: {st.median(len(d['relatorio']) for d in corpus):>6.0f} chars")
    print(f"fundament. mediana: {st.median(len(d['fundamentacao']) for d in corpus):>6.0f} chars")
    print(f"dispositivo mediano:{st.median(len(d['dispositivo']) for d in corpus):>6.0f} chars")
    print("\nassuntos:")
    for a, n in Counter(d.get("assunto", "?") for d in corpus).most_common(10):
        print(f"  {n:>3}  {a}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
