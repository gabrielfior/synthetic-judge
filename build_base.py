"""
Monta a base de casos que a escada de referência consulta: uma linha por
sentença legível de Procedimento Comum em Limeira, com a classe da taxonomia e
os três alvos (resultado, prazo, dano moral).

    uv run python build_base.py        # escreve data/prognostico/base.jsonl

As classes vêm das gravações de `eval_taxonomia.py` e `classificar_corpus.py`
(deepseek); um caso sem classe aborta o build em vez de entrar sem ela, porque
uma linha sem classe só serviria ao piso e distorceria a contagem.
"""
import json
import pathlib
import sys

from eval_extrator import PARQUET
from eval_taxonomia import ler_classes
from sj import corpus
from sj.extrator import casos
from sj.features import features
from sj.taxonomia import PROCEDENTE, RESULTADOS_BINARIOS

CLASSES = pathlib.Path("data/eval/taxonomia")
TAXONOMIA = pathlib.Path("sj/taxonomia_limeira.json")
SAIDA = pathlib.Path("data/prognostico/base.jsonl")


def linha(c: dict, f: dict, classe: str, grupo: str) -> dict:
    d = c["doc"]
    r = f.get("resultado")
    return {
        "id": c["id"], "processo": c["processo"], "data": str(d["data"]),
        "classe": classe, "grupo": grupo, "assunto_tribunal": c["assunto"],
        "resultado": r,
        "procedente": int(r in PROCEDENTE) if r in RESULTADOS_BINARIOS else None,
        "dias": f.get("dias_tramitacao_estimados"),
        # `False` do features.py é "a expressão não apareceu", não "não pediu":
        # só `True` é informação.
        "dm_pedido": bool(f.get("dano_moral_pedido")),
        "dm_concedido": bool(f.get("dano_moral_concedido")),
        "dm_valor": f.get("valor_dano_moral"),
        "dm_valor_pedido": f.get("valor_dano_moral_pedido"),
        "dm_razao": f.get("razao_dano_moral"),
        "url_pdf": d.get("url_pdf"),
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--classes", default=str(CLASSES), help="diretório das classes")
    ap.add_argument("--saida", default=str(SAIDA))
    args = ap.parse_args()
    classes_dir, saida = pathlib.Path(args.classes), pathlib.Path(args.saida)
    grupo_de = {c["nome"]: c["grupo"]
                for c in json.loads(TAXONOMIA.read_text())["classes"]}
    cs = casos(corpus.ler(PARQUET))
    classe = {}
    for arq in ("classes_todos.jsonl", "classes_deepseek-v4.1-flash.jsonl"):
        for k, v in ler_classes(classes_dir / arq, cs).items():
            classe.setdefault(k, v)
    sem = [c["id"] for c in cs if not classe.get(c["id"])]
    if sem:
        sys.exit(f"{len(sem)} casos sem classe (ex.: {sem[:3]}); rode "
                 f"classificar_corpus.py")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8") as f:
        for c in cs:
            k = classe[c["id"]]
            f.write(json.dumps(linha(c, features(c["doc"]), k, grupo_de[k]),
                               ensure_ascii=False) + "\n")
    print(f"{len(cs)} casos em {saida}")


if __name__ == "__main__":
    main()
