"""Monta o conjunto da tarefa de decidir (resultado a partir do relatório).

    uv run python build_decisao.py     # escreve data/eval/decisao/ (gitignored)

Universo: toda sentença legível de Procedimento Comum Cível do juiz, em qualquer
comarca, com resultado reconhecido pelo extrator. Limeira é o foro alvo (o
produto); Santa Bárbara d'Oeste é o mesmo juiz em outra comarca e só entra no
treino. A divisão está em `sj/decisao.py`.
"""
import json
from pathlib import Path

from sj import corpus
from sj.decisao import RESULTADOS, dividir
from sj.extrator import entrada
from sj.features import features

PARQUET = "data/corpus.parquet"
BASE = Path("data/prognostico/base.jsonl")
SAIDA = Path("data/eval/decisao")
RELATORIO_MAX = 6000


def universo() -> list[dict]:
    classe = {b["id"]: b for b in map(json.loads, BASE.open())}
    out = []
    for d in corpus.ler(PARQUET):
        if d["classe"] != "Procedimento Comum Cível" or not d["split_ok"]:
            continue
        f = features(d)
        if f["resultado"] not in RESULTADOS:
            continue
        cid = f"{d['processo']}|{d['data']}"
        b = classe.get(cid, {})
        out.append({"id": cid, "processo": d["processo"], "data": str(d["data"]),
                    "comarca": d["comarca"], "resultado": f["resultado"],
                    "classe": b.get("classe"), "grupo": b.get("grupo"),
                    "dm_pedido": bool(f["dano_moral_pedido"]),
                    "dm_concedido": bool(f["dano_moral_concedido"]),
                    "dm_valor": f["valor_dano_moral"],
                    "relatorio": entrada(d)[:RELATORIO_MAX]})
    return out


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    casos = universo()
    # `dividir` compara datas como texto ISO
    conj, manifesto = dividir(casos)
    with open(SAIDA / "casos.jsonl", "w") as f:
        for c in casos:
            if c["id"] in conj:
                f.write(json.dumps({**c, "conjunto": conj[c["id"]]},
                                   ensure_ascii=False) + "\n")
    ids_eval = {json.loads(l)["id"] for l in open("data/eval/sentenca/cases.jsonl")}
    manifesto["eval_sentenca_por_conjunto"] = {
        k: sum(1 for i in ids_eval if conj.get(i) == k)
        for k in ("treino", "val", "teste")} | {
            "fora": sum(1 for i in ids_eval if i not in conj)}
    (SAIDA / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=1))
    print(json.dumps(manifesto, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
