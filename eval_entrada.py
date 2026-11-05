"""
Fecha a lacuna da entrada de docs/prognostico.md: o pipeline classifica o texto
do ADVOGADO tão bem quanto o relatório do juiz?

    uv run python build_base.py && uv run python eval_entrada.py [--n 300]

Por caso da amostra (só os 942 de avaliação, que a taxonomia nunca viu):

    1. o qwen reescreve o relatório como o advogado do autor descreveria o caso
       antes de ajuizar (sj/entrada.py), em estilo curto, médio ou detalhado
    2. o `estruturar` do pipeline (deepseek) classifica a descrição
    3. compara com a classe que o caso já tem pelo relatório e calcula o Brier de
       procedência de ponta a ponta com a classe inferida

Geração e classificação usam modelos diferentes, para a descrição não ser lida
pelo mesmo modelo que a escreveu. Tudo em cache em `data/eval/entrada/`.

LIMITE: é um advogado simulado, mais limpo que o real. Os números são um teto.
"""
import argparse
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from eval_extrator import PARQUET, RELATORIO_MAX
from sj import corpus, entrada, estruturar, referencia
from sj.extrator import amostra, casos
from sj.llm import _env, _post, cliente
from sj.referencia import Consulta
from sj.taxonomia import dividir

GERADOR = "qwen3.8-27b"
CLASSIFICADOR = "deepseek-v4.1-flash"
BASE = pathlib.Path("data/prognostico/base.jsonl")
DESTINO = pathlib.Path("data/eval/entrada")


def _cache(arq: pathlib.Path) -> dict[str, dict]:
    if not arq.exists():
        return {}
    return {r["id"]: r for r in map(json.loads, arq.read_text().splitlines())}


def _rodar(pendentes, fn, arq: pathlib.Path, paralelo: int) -> None:
    with arq.open("a", encoding="utf-8") as f, ThreadPoolExecutor(paralelo) as pool:
        for r in pool.map(fn, pendentes):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--paralelo", type=int, default=12)
    ap.add_argument("--saida", default=str(DESTINO))
    ap.add_argument("--ids-de", help="descricoes_*.jsonl de uma rodada anterior: "
                    "reusa os mesmos casos e as mesmas descrições (comparação pareada "
                    "entre versões da taxonomia)")
    args = ap.parse_args()
    destino = pathlib.Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    env = _env()

    base = [json.loads(l) for l in BASE.read_text().splitlines()]
    por_id = {r["id"]: r for r in base}
    taxonomia = estruturar.carregar_taxonomia()
    validos = {c["nome"] for c in taxonomia}
    grupo_de = {c["nome"]: c["grupo"] for c in taxonomia}

    _, avaliacao = dividir(casos(corpus.ler(PARQUET)))
    # `amostra` estratifica pela chave "assunto": aqui, a classe verdadeira
    cand = [{"id": c["id"], "assunto": por_id[c["id"]]["classe"],
             "relatorio": c["relatorio"]} for c in avaliacao]
    if args.ids_de:
        # as descrições não dependem da taxonomia: copiam-se e só se reclassifica
        antes = pathlib.Path(args.ids_de)
        arq_desc = destino / f"descricoes_{GERADOR}.jsonl"
        if not arq_desc.exists():
            arq_desc.write_text(antes.read_text())
        ids = set(_cache(antes))
        alvo = [c for c in cand if c["id"] in ids]
    else:
        alvo = amostra(cand, args.n)
    print(f"{len(alvo)} casos de {len({c['assunto'] for c in alvo})} classes",
          file=sys.stderr)

    # 1. geração
    arq_g = destino / f"descricoes_{GERADOR}.jsonl"
    feitos = _cache(arq_g)
    url, h, monta, le = cliente("default", env, "none")
    sessao = requests.Session()

    def gerar(c):
        est = entrada.estilo(c["id"])
        corpo = monta(GERADOR, "Você é um advogado brasileiro experiente.",
                      entrada.pedido_reescrita(c["relatorio"][:RELATORIO_MAX], est))
        corpo["max_tokens"] = 800
        return {"id": c["id"], "estilo": est,
                "texto": entrada.limpar(le(_post(sessao, url, h, corpo))[0])}

    pend = [c for c in alvo if c["id"] not in feitos]
    print(f"gerando {len(pend)} descrições ({GERADOR})", file=sys.stderr)
    _rodar(pend, gerar, arq_g, args.paralelo)
    descricoes = _cache(arq_g)

    # 2. classificação com o estruturar do pipeline
    arq_c = destino / f"classes_{CLASSIFICADOR}.jsonl"
    feitos = _cache(arq_c)
    system = estruturar.sistema(taxonomia)
    sessao2 = requests.Session()

    def classificar(c):
        corpo = monta(CLASSIFICADOR, system, descricoes[c["id"]]["texto"])
        corpo["max_tokens"] = 400
        e = estruturar.interpretar(le(_post(sessao2, url, h, corpo))[0], validos)
        return {"id": c["id"], "classe": e.classe, "alternativas": e.alternativas,
                "pede_dano_moral": e.pede_dano_moral}

    pend = [c for c in alvo if c["id"] not in feitos and c["id"] in descricoes]
    print(f"classificando {len(pend)} descrições ({CLASSIFICADOR})", file=sys.stderr)
    _rodar(pend, classificar, arq_c, args.paralelo)
    classes = _cache(arq_c)

    # 3. métricas
    linhas, brier = [], {"global": [], "inferida": [], "verdadeira": []}
    for c in alvo:
        i, r = c["id"], por_id[c["id"]]
        inf = classes[i]["classe"]
        linhas.append({"id": i, "estilo": descricoes[i]["estilo"],
                       "verdadeira": r["classe"], "grupo_verdadeiro": r["grupo"],
                       "inferida": inf, "grupo_inferido": grupo_de.get(inf),
                       "alternativas": classes[i]["alternativas"],
                       "dm_pedido": r["dm_pedido"],
                       "pede_dano_moral": classes[i]["pede_dano_moral"]})
        if r["procedente"] is None:
            continue
        for nome, q in (("global", Consulta()),
                        ("inferida", Consulta(inf, grupo_de.get(inf))),
                        ("verdadeira", Consulta(r["classe"], r["grupo"]))):
            p = referencia.procedencia(base, q, excluir=i)["probabilidade"]
            brier[nome].append((p - r["procedente"]) ** 2)

    m = entrada.metricas(linhas)
    n_b = len(brier["global"])
    out = {"n": len(linhas), "gerador": GERADOR, "classificador": CLASSIFICADOR,
           "traducao": m, "confusoes": entrada.confusoes(linhas),
           "n_brier": n_b, "brier": {k: sum(v) / n_b for k, v in brier.items()},
           "brier_por_estilo": {}}
    for e in entrada.ESTILOS:
        ix = [k for k, l in enumerate(
            [l for l in linhas if por_id[l["id"]]["procedente"] is not None])
            if l["estilo"] == e]
        if ix:
            out["brier_por_estilo"][e] = {
                k: sum(v[j] for j in ix) / len(ix) for k, v in brier.items()}
    # o dano moral: o advogado diz que pede?
    pedem = [l for l in linhas if l["dm_pedido"]]
    out["dm_recall_pede"] = (sum(l["pede_dano_moral"] is True for l in pedem)
                             / len(pedem)) if pedem else None
    (destino / "metricas.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    (destino / "linhas.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=2))

    print(f"\n{out['n']} casos; modelo gerador {GERADOR}, classificador {CLASSIFICADOR}")
    print(f"{'':11}{'n':>5}{'classe':>9}{'top-3':>8}{'grupo':>8}{'não ident.':>12}")
    for k in ("geral", *entrada.ESTILOS):
        x = m[k]
        print(f"{k:11}{x['n']:>5}{x['classe']:>9.1%}{x['top3']:>8.1%}"
              f"{x['grupo']:>8.1%}{x['nao_identificada']:>12.1%}")
    b = out["brier"]
    print(f"\nBrier de procedência (n={n_b}): global {b['global']:.4f}  |  "
          f"classe inferida do texto do advogado {b['inferida']:.4f}  |  "
          f"classe verdadeira {b['verdadeira']:.4f}")
    for e, x in out["brier_por_estilo"].items():
        print(f"   {e:10} global {x['global']:.4f}  inferida {x['inferida']:.4f}  "
              f"verdadeira {x['verdadeira']:.4f}")
    print(f"\nrecall de 'pede dano moral' onde o relatório registra o pedido: "
          f"{out['dm_recall_pede']:.1%}")
    print("\nconfusões mais frequentes (verdadeira -> inferida):")
    for c in out["confusoes"][:8]:
        print(f"  {c['n']:3}  {c['verdadeira']}  ->  {c['inferida']}")


if __name__ == "__main__":
    main()
