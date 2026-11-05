"""Monta os casos do eval da sentença sintética (v1).

Cada caso é um julgado real da 4ª Vara Cível de Limeira: a entrada é o relatório
(sem o carimbo "Classe - Assunto" que traz o rótulo) e o gabarito é a sentença
que o juiz de fato escreveu. O resultado e o dano moral do gabarito vêm de
`data/prognostico/base.jsonl`, extraídos do dispositivo por `sj/features.py`.

A amostra é determinística (ordem por hash do id) e estratificada por grupo da
taxonomia e por resultado; extintos sem mérito entram sobre-representados
porque o eval precisa de casos em que a resposta certa é "não julgar o mérito".

Saída em `data/eval/sentenca/` (gitignored: tem nomes reais de partes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sj import corpus
from sj.extrator import casos
from sj.ficha import secoes

PARQUET = "data/corpus.parquet"
BASE = "data/prognostico/base.jsonl"
SAIDA = Path("data/eval/sentenca")

# Quantos de cada resultado. A mistura real é 42/32/22/3%; aqui o extinto sobe
# para 8 de 100 e o resto segue a proporção.
COTA = {"procedente": 38, "improcedente": 30, "parcialmente_procedente": 24,
        "extinto_sem_merito": 8}


def _chave(i: str) -> str:
    return hashlib.sha256(i.encode()).hexdigest()


def escolher(base: list[dict], cota: dict[str, int]) -> list[dict]:
    """Por resultado, em rodízio entre os grupos, na ordem do hash do id."""
    escolhidos: list[dict] = []
    for resultado, n in cota.items():
        por_grupo: dict[str, list[dict]] = defaultdict(list)
        for b in sorted((b for b in base if b["resultado"] == resultado),
                        key=lambda b: _chave(b["id"])):
            por_grupo[b["grupo"]].append(b)
        filas = [por_grupo[g] for g in sorted(por_grupo)]
        pegos: list[dict] = []
        while len(pegos) < n and any(filas):
            for fila in filas:
                if fila and len(pegos) < n:
                    pegos.append(fila.pop(0))
        escolhidos += pegos
    return escolhidos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()

    base = {b["id"]: b for b in map(json.loads, open(BASE))}
    doc = {c["id"]: c for c in casos(corpus.ler(PARQUET))}
    elegiveis = [b for i, b in base.items() if i in doc]
    sel = escolher(elegiveis, COTA)

    args.saida.mkdir(parents=True, exist_ok=True)
    with open(args.saida / "cases.jsonl", "w") as f:
        for b in sel:
            c = doc[b["id"]]
            _, fundamentacao, dispositivo = secoes(c["doc"]["texto"])
            f.write(json.dumps({
                "id": b["id"], "tags": [b["grupo"], b["resultado"]],
                "classe": b["classe"], "relatorio": c["relatorio"],
                "expected": {"resultado": b["resultado"],
                             "dm_pedido": b["dm_pedido"],
                             "dm_concedido": b["dm_concedido"],
                             "dm_valor": b["dm_valor"],
                             "fundamentacao": fundamentacao,
                             "dispositivo": dispositivo,
                             "origem": "sentença real do juiz; resultado e dano "
                                       "moral extraídos por regex de sj/features.py"},
            }, ensure_ascii=False) + "\n")
    print(f"{len(sel)} casos em {args.saida / 'cases.jsonl'}")


if __name__ == "__main__":
    main()
