"""
Aplica a taxonomia de `eval_taxonomia.py` a TODOS os casos de Procedimento Comum
de Limeira, inclusive os truncados pelo CJPG, e compara a mistura de classes dos
truncados com a dos legíveis.

    uv run python classificar_corpus.py

Lê `data/eval/taxonomia/taxonomia.json` (não a refaz) e reaproveita as classes
do deepseek já gravadas pelo eval. Escreve `classes_todos.jsonl` e `vies.json`.

A pergunta é a fragilidade nº 3 de docs/prognostico.md: se o truncamento
correlaciona com o tipo de ação, a taxa de procedência medida só nos legíveis
está enviesada. Só dá para medir a MISTURA de classes — nos truncados não há
resultado para comparar a taxa.

"Truncado" aqui é uma SENTENÇA sem marcador de dispositivo num processo que não
tem outra decisão legível. Ficam de fora, com a contagem no relatório, os
documentos "DECISÃO" (não são sentenças) e os truncados cujo processo já está
representado por uma sentença legível (a mesma ação contada duas vezes).
"""
import json
import pathlib
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

import random
import re

from eval_extrator import PARQUET, RELATORIO_MAX
from sj.llm import _env, _post, cliente
from eval_taxonomia import ler_classes
from sj import corpus
from sj.extrator import casos
from sj.taxonomia import interpretar_categoria, sistema_classificar

MODELO = "deepseek-v4.1-flash"
DESTINO = pathlib.Path("data/eval/taxonomia")


def distancia_total(a: Counter, b: Counter) -> float:
    """Variação total entre duas distribuições: metade da soma das diferenças."""
    na, nb = sum(a.values()), sum(b.values())
    return sum(abs(a[k] / na - b[k] / nb) for k in a.keys() | b.keys()) / 2


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--saida", default=str(DESTINO))
    ap.add_argument("--taxonomia", help="JSON das classes; padrão: <saida>/taxonomia.json")
    args = ap.parse_args()
    destino = pathlib.Path(args.saida)
    t = json.loads(pathlib.Path(args.taxonomia or destino / "taxonomia.json").read_text())
    taxonomia = t["classes"] if isinstance(t, dict) else t
    validos = {c["nome"] for c in taxonomia}
    docs = corpus.ler(PARQUET)
    legiveis = {c["id"] for c in casos(docs)}
    todos = casos(docs, so_split_ok=False)

    arq = destino / "classes_todos.jsonl"
    feitos = ler_classes(destino / f"classes_{MODELO}.jsonl", todos)
    feitos |= ler_classes(arq, todos)
    pendentes = [c for c in todos if c["id"] not in feitos]
    print(f"{len(todos)} documentos ({len(legiveis)} legíveis); {len(pendentes)} a classificar",
          file=sys.stderr)

    if pendentes:
        url, headers, monta, le = cliente("default", _env(), "none")
        system = sistema_classificar(taxonomia)
        sessao = requests.Session()

        def um(c):
            texto, _ = le(_post(sessao, url, headers,
                                monta(MODELO, system, c["relatorio"][:RELATORIO_MAX])))
            return {"id": c["id"], "processo": c["processo"],
                    "classe": interpretar_categoria(texto, validos)}

        with arq.open("a", encoding="utf-8") as f, ThreadPoolExecutor(12) as pool:
            for r in pool.map(um, pendentes):
                feitos[r["id"]] = r["classe"]
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()

    proc_legivel = {c["processo"] for c in todos if c["id"] in legiveis}
    sentenca = lambda c: bool(re.match(r"\s*SENTEN", c["doc"]["texto"], re.I))
    nao_leg = [c for c in todos if c["id"] not in legiveis]
    decisoes = [c for c in nao_leg if not sentenca(c)]
    irmaos = [c for c in nao_leg if sentenca(c) and c["processo"] in proc_legivel]
    truncados = [c for c in nao_leg if sentenca(c) and c["processo"] not in proc_legivel]
    classe = {c["id"]: feitos.get(c["id"]) for c in todos}
    leg = Counter(classe[c["id"]] for c in todos if c["id"] in legiveis)
    tru = Counter(classe[c["id"]] for c in truncados)
    n_leg, n_tru = sum(leg.values()), sum(tru.values())
    tvd = distancia_total(leg, tru)

    # referência de ruído: a mesma distância entre uma amostra ALEATÓRIA dos
    # legíveis do tamanho dos truncados e o resto, para saber o que é acaso
    rng = random.Random(0)
    ids = sorted(legiveis)
    ruido = []
    for _ in range(500):
        a = set(rng.sample(ids, n_tru))
        ruido.append(distancia_total(Counter(classe[i] for i in a),
                                     Counter(classe[i] for i in ids if i not in a)))
    ruido.sort()
    linhas = sorted(({"classe": k, "legiveis": leg[k] / n_leg, "truncados": tru[k] / n_tru,
                      "n_truncados": tru[k]} for k in leg.keys() | tru.keys()),
                    key=lambda r: r["truncados"] - r["legiveis"])
    out = {"n_legiveis": n_leg, "n_truncados": n_tru,
           "fora_decisoes": len(decisoes), "fora_irmaos_de_legivel": len(irmaos),
           "variacao_total": tvd,
           "variacao_total_por_acaso_p95": ruido[int(len(ruido) * 0.95)],
           "sem_classe_truncados": tru[None] / n_tru, "por_classe": linhas}
    (destino / "vies.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"\nlegíveis {n_leg}; truncados {n_tru}; fora da comparação: "
          f"{len(decisoes)} DECISÃO e {len(irmaos)} truncados de processo já legível")
    print(f"variação total das misturas: {tvd:.3f} "
          f"(p95 do acaso com n={n_tru}: {out['variacao_total_por_acaso_p95']:.3f})")
    print(f"truncados sem classe: {out['sem_classe_truncados']:.1%}\n")
    print("classes que mais mudam de peso (truncados − legíveis):")
    for r in linhas[:4] + linhas[-4:]:
        print(f"  {r['truncados'] - r['legiveis']:+.1%}  {r['classe']}  "
              f"({r['legiveis']:.1%} → {r['truncados']:.1%}, n={r['n_truncados']})")


if __name__ == "__main__":
    main()
