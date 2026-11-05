"""
Eval da taxonomia dirigida pelos dados (sucessor de eval_extrator.py): a LLM
propõe classes a partir de 30% dos relatórios de Limeira e as aplica aos 70%
restantes, com dois modelos independentes.

    uv run python eval_taxonomia.py

Etapas, todas em cache em `data/eval/taxonomia/` (apague o arquivo para refazer):

    taxonomia.json                  proposta pelo deepseek sobre a descoberta
                                    (lotes -> candidatas -> fusão);
                                    uma vez gerada, FICA — refazê-la invalida
                                    qualquer número medido contra ela
    classes_<modelo>.jsonl          a classe que cada modelo deu a cada caso
    metricas.json                   o relatório final

O que se mede, só na avaliação:

    concordância      kappa entre os dois modelos — a taxonomia é aplicável?
    assunto do e-SAJ  quanto o cluster explica o rótulo do tribunal (NMI e
                      acurácia leave-one-out), contra os 27% do eval anterior
    procedência       Brier leave-one-out de prever procedente/improcedente pela
                      classe, contra o assunto do tribunal e contra a taxa
                      global, com IC 95% por bootstrap pareado — é a pergunta
                      do produto: a classe prevê melhor que o rótulo oficial?
"""
import argparse
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from eval_extrator import PARQUET, RELATORIO_MAX
from sj.llm import _env, _post, cliente
from sj import corpus
from sj.extrator import casos
from sj.features import features
from sj.taxonomia import (RESULTADOS_BINARIOS, PROCEDENTE, assunto_pelo_cluster,
                          brier_global_loo, brier_loo, dividir, ic_diferenca,
                          interpretar_categoria, interpretar_taxonomia, kappa,
                          lotes, nmi, pedido_fusao, pedido_proposta,
                          sistema_classificar)

# Sem raciocínio também na fusão: com "medium" e as 110 candidatas o conteúdo
# voltou vazio nas três tentativas (o raciocínio come o limite de saída).
PROPOSITOR = ("deepseek-v4.1-flash", "none")
CLASSIFICADORES = ("deepseek-v4.1-flash", "qwen3.8-27b")
MIN_GRUPO = 5  # grupos menores entram no Brier, mas ficam fora da tabela por classe


LOTE = 65  # relatórios por chamada de proposta (~15 mil tokens)


def _chamar(modelo, esforco, env, system, user, timeout=240) -> str:
    url, headers, monta, le = cliente("default", env, esforco)
    corpo = monta(modelo, system, user)
    # o cliente limita a saída a 200 tokens sem raciocínio, o que serve para um
    # rótulo e corta ao meio uma taxonomia (visto: finish_reason=length)
    corpo["max_tokens"] = 8000
    texto, _ = le(_post(requests.Session(), url, headers, corpo, timeout=timeout))
    return texto


def _taxonomia_valida(chamada, minimo, maximo, rotulo) -> list[dict]:
    for tentativa in range(3):
        try:
            return interpretar_taxonomia(chamada(), minimo, maximo)
        except (ValueError, requests.RequestException) as e:
            print(f"  {rotulo}: {type(e).__name__}: {str(e)[:80]}; tentativa "
                  f"{tentativa + 1}/3", file=sys.stderr)
    sys.exit(f"{rotulo}: sem resposta válida em 3 tentativas")


def proposta(descoberta, env, destino: pathlib.Path) -> list[dict]:
    """Map-reduce: cada lote propõe candidatas; uma chamada curta as funde.

    Uma só chamada sobre os ~390 relatórios (235 mil chars) com raciocínio ficou
    34 minutos no ar e morreu com SSLEOFError; em lotes cada chamada leva
    segundos e uma falha custa um lote, não o run.
    """
    arq = destino / "taxonomia.json"
    if arq.exists():
        return json.loads(arq.read_text())
    modelo, esforco = PROPOSITOR
    fatias = lotes(descoberta, LOTE)
    print(f"propondo taxonomia: {len(fatias)} lotes de até {LOTE} relatórios "
          f"({modelo})", file=sys.stderr)

    def um(i_fatia):
        i, fatia = i_fatia
        system, user = pedido_proposta(fatia, 10, 18)
        return _taxonomia_valida(
            lambda: _chamar(modelo, "none", env, system, user), 6, 30, f"lote {i}")

    arq_cand = destino / "taxonomia_candidatas.json"
    if arq_cand.exists():
        candidatas = json.loads(arq_cand.read_text())
    else:
        with ThreadPoolExecutor(len(fatias)) as pool:
            candidatas = list(pool.map(um, enumerate(fatias, 1)))
        arq_cand.write_text(json.dumps(candidatas, ensure_ascii=False, indent=2))
    print(f"  {sum(map(len, candidatas))} candidatas; fundindo", file=sys.stderr)

    system, user = pedido_fusao(candidatas)
    tax = _taxonomia_valida(
        lambda: _chamar(modelo, esforco, env, system, user, timeout=600),
        12, 40, "fusão")
    arq.write_text(json.dumps(tax, ensure_ascii=False, indent=2))
    print(f"  {len(tax)} categorias", file=sys.stderr)
    return tax


def ler_classes(arq: pathlib.Path, cs: list[dict]) -> dict[str, str | None]:
    """As classes já gravadas, por `id`.

    Linhas antigas só têm o número do processo; valem só quando ele é
    inequívoco entre os casos (um documento por processo). As ambíguas ficam de
    fora e são reclassificadas.
    """
    if not arq.exists():
        return {}
    por_proc: dict[str, list[str]] = {}
    for c in cs:
        por_proc.setdefault(c["processo"], []).append(c["id"])
    feitos = {}
    for r in map(json.loads, arq.read_text().splitlines()):
        if "id" in r:
            feitos[r["id"]] = r["classe"]
        elif len(por_proc.get(r["processo"], [])) == 1:
            feitos[por_proc[r["processo"]][0]] = r["classe"]
    return feitos


def classificar(modelo, avaliacao, taxonomia, env, destino, paralelo) -> dict[str, str | None]:
    slug = modelo.replace("/", "_")
    arq = destino / f"classes_{slug}.jsonl"
    feitos = ler_classes(arq, avaliacao)
    pendentes = [c for c in avaliacao if c["id"] not in feitos]
    print(f"{modelo}: {len(pendentes)} a classificar", file=sys.stderr)
    if pendentes:
        url, headers, monta, le = cliente("default", env, "none")
        system = sistema_classificar(taxonomia)
        validos = {c["nome"] for c in taxonomia}
        sessao = requests.Session()

        def um(c):
            texto, _ = le(_post(sessao, url, headers,
                                monta(modelo, system, c["relatorio"][:RELATORIO_MAX])))
            return {"id": c["id"], "processo": c["processo"],
                    "classe": interpretar_categoria(texto, validos)}

        with arq.open("a", encoding="utf-8") as f, ThreadPoolExecutor(paralelo) as pool:
            for r in pool.map(um, pendentes):
                feitos[r["id"]] = r["classe"]
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
    return feitos


def relatorio_final(avaliacao, classes: dict[str, dict], resultados, taxonomia) -> dict:
    m0, m1 = CLASSIFICADORES
    ambos = [c for c in avaliacao
             if classes[m0].get(c["id"]) and classes[m1].get(c["id"])]
    out: dict = {"n_avaliacao": len(avaliacao), "n_com_as_duas_classes": len(ambos),
                 "kappa_entre_modelos": kappa(
                     [classes[m0][c["id"]] for c in ambos],
                     [classes[m1][c["id"]] for c in ambos]),
                 "concordancia_bruta": sum(
                     classes[m0][c["id"]] == classes[m1][c["id"]]
                     for c in ambos) / len(ambos)}

    for m in CLASSIFICADORES:
        cs = [c for c in avaliacao if classes[m].get(c["id"])]
        cl = [classes[m][c["id"]] for c in cs]
        ass = [c["assunto"] for c in cs]
        bin_ = [(c, classes[m][c["id"]]) for c in cs
                if resultados.get(c["id"]) in RESULTADOS_BINARIOS]
        y = [int(resultados[c["id"]] in PROCEDENTE) for c, _ in bin_]
        g_cl = [k for _, k in bin_]
        g_as = [c["assunto"] for c, _ in bin_]
        b_cl, b_as, b_gl = brier_loo(g_cl, y), brier_loo(g_as, y), brier_global_loo(y)
        out[m] = {
            "n": len(cs), "sem_classe": 1 - len(cs) / len(avaliacao),
            "n_classes_usadas": len(set(cl)),
            "nmi_com_assunto_tribunal": nmi(cl, ass),
            "assunto_pelo_cluster_loo": assunto_pelo_cluster(cl, ass),
            "n_com_resultado": len(y), "taxa_procedencia": sum(y) / len(y),
            "brier": {"global": sum(b_gl) / len(y), "assunto_tribunal": sum(b_as) / len(y),
                      "classe": sum(b_cl) / len(y)},
            "classe_vs_global": ic_diferenca(b_cl, b_gl),
            "classe_vs_assunto": ic_diferenca(b_cl, b_as),
            "assunto_vs_global": ic_diferenca(b_as, b_gl),
        }
        por: dict = {}
        for (c, k), v in zip(bin_, y):
            p = por.setdefault(k, [0, 0])
            p[0] += v
            p[1] += 1
        out[m]["por_classe"] = sorted(
            ({"classe": k, "n": n, "procedencia": pos / n}
             for k, (pos, n) in por.items() if n >= MIN_GRUPO),
            key=lambda r: -r["n"])
    return out


def imprimir(r: dict) -> None:
    print(f"\navaliação: {r['n_avaliacao']} casos; {r['n_com_as_duas_classes']} com "
          f"classe dos dois modelos")
    print(f"concordância entre modelos: {r['concordancia_bruta']:.1%} "
          f"(kappa {r['kappa_entre_modelos']:.2f})")
    for m in CLASSIFICADORES:
        x = r[m]
        print(f"\n== {m}: {x['n_classes_usadas']} classes usadas, "
              f"{x['sem_classe']:.1%} sem classe")
        print(f"   NMI com o assunto do tribunal {x['nmi_com_assunto_tribunal']:.2f}; "
              f"assunto previsto pelo cluster (LOO) {x['assunto_pelo_cluster_loo']:.1%}")
        b = x["brier"]
        print(f"   procedência, n={x['n_com_resultado']} (taxa {x['taxa_procedencia']:.1%}); "
              f"Brier LOO — global {b['global']:.4f}, assunto do tribunal "
              f"{b['assunto_tribunal']:.4f}, classe {b['classe']:.4f}")
        for nome in ("classe_vs_global", "classe_vs_assunto", "assunto_vs_global"):
            d, lo, hi = x[nome]
            a, b_ = nome.split("_vs_")
            print(f"   Δ Brier {a} − {b_}: {d:+.4f}  IC95% [{lo:+.4f}, {hi:+.4f}]")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--paralelo", type=int, default=12)
    ap.add_argument("--saida", default="data/eval/taxonomia")
    ap.add_argument("--taxonomia", help="JSON com as classes (formato de "
                    "sj/taxonomia_limeira.json); sem ele, a LLM propõe uma")
    args = ap.parse_args()

    env = _env()
    destino = pathlib.Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)

    docs = corpus.ler(PARQUET)
    todos = casos(docs)
    # do próprio documento do caso: indexar por número de processo errava o
    # rótulo de 8 dos 942 casos (a decisão posterior sobrescrevia a sentença)
    resultados = {c["id"]: features(c["doc"]).get("resultado")
                  for c in casos(docs, so_split_ok=False)}
    descoberta, avaliacao = dividir(todos)
    print(f"{len(todos)} casos: {len(descoberta)} descoberta, {len(avaliacao)} avaliação",
          file=sys.stderr)

    if args.taxonomia:
        t = json.loads(pathlib.Path(args.taxonomia).read_text())
        taxonomia = t["classes"] if isinstance(t, dict) else t
    else:
        taxonomia = proposta(descoberta, env, destino)
    classes = {m: classificar(m, avaliacao, taxonomia, env, destino, args.paralelo)
               for m in CLASSIFICADORES}
    r = relatorio_final(avaliacao, classes, resultados, taxonomia)
    (destino / "metricas.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))
    imprimir(r)


if __name__ == "__main__":
    main()
