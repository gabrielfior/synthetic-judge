"""
Eval do extrator de assunto (passo 1 de docs/prognostico.md): dado só o relatório
de uma sentença de Limeira, a LLM acerta o `assunto` que o e-SAJ registrou?

    uv run python eval_extrator.py --amostra 150          # valida prompt e custo
    uv run python eval_extrator.py                        # os ~1.300 de Limeira
    uv run python eval_extrator.py --provedor zen --modelo claude-haiku-5-5

Dois provedores, escolhidos por `--provedor`:

    default (padrão) inferência configurada em INFERENCE_*, OpenAI-compatible, deepseek-v4.1-flash;
         INFERENCE_API_KEY e _BASE_URL vêm do `.env`
    zen  OpenCode Zen, Anthropic Messages; OPENCODE_API_KEY no ambiente

Cada resposta vai para `data/eval/extrator_<modelo>.jsonl` assim que chega, e uma
nova execução pula o que já está lá — uma queda no meio não custa o run inteiro.
O Zen fala Anthropic Messages (`/messages` com `x-api-key`), não OpenAI.
"""
import argparse
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from sj import corpus
from sj.llm import MODELOS, _env, _post, cliente
from sj.extrator import amostra, casos, interpretar, metricas, sistema

PARQUET = "data/corpus.parquet"
RELATORIO_MAX = 6000  # a mediana é ~1,9 mil; o corte só protege de um outlier
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--provedor", choices=MODELOS, default="default")
    ap.add_argument("--modelo", help="padrão: o do provedor")
    ap.add_argument("--raciocinio", default="none", choices=["none", "low", "medium", "high"],
                    help="reasoning_effort do provedor default (padrão: none)")
    ap.add_argument("--amostra", type=int, help="N casos, estratificados por assunto")
    ap.add_argument("--paralelo", type=int, default=8)
    ap.add_argument("--saida", default="data/eval")
    args = ap.parse_args()

    args.modelo = args.modelo or MODELOS[args.provedor]
    url, headers, monta, le = cliente(args.provedor, _env(), args.raciocinio)

    todos = casos(corpus.ler(PARQUET))
    validos = sorted({c["assunto"] for c in todos})
    alvo = amostra(todos, args.amostra) if args.amostra else todos
    system = sistema(validos)

    destino = pathlib.Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    slug = args.modelo.replace("/", "_")
    if args.provedor == "default" and args.raciocinio != "none":
        slug += f"_{args.raciocinio}"
    arq = destino / f"extrator_{slug}.jsonl"
    feitos = {}
    if arq.exists():
        feitos = {r["processo"]: r for r in map(json.loads, arq.read_text().splitlines())}
    pendentes = [c for c in alvo if c["processo"] not in feitos]
    print(f"{len(alvo)} casos, {len(validos)} assuntos, {len(pendentes)} a rodar "
          f"({args.modelo})", file=sys.stderr)

    sessao = requests.Session()

    def um(c: dict) -> dict:
        corpo = monta(args.modelo, system, c["relatorio"][:RELATORIO_MAX])
        texto, uso = le(_post(sessao, url, headers, corpo))
        return {"processo": c["processo"], "assunto": c["assunto"],
                "previsto": interpretar(texto, set(validos)),
                "resposta": texto, "uso": uso}

    with arq.open("a", encoding="utf-8") as f, \
            ThreadPoolExecutor(args.paralelo) as pool:
        for i, r in enumerate(pool.map(um, pendentes), 1):
            feitos[r["processo"]] = r
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                print(f"  {i}/{len(pendentes)}", file=sys.stderr)

    rs = [feitos[c["processo"]] for c in alvo]
    m = metricas(rs)
    uso = {k: sum(r["uso"].get(k, 0) for r in rs)
           for k in ("input_tokens", "output_tokens",
                     "cache_creation_input_tokens", "cache_read_input_tokens")}
    (destino / f"extrator_{slug}_metricas.json").write_text(
        json.dumps({**m, "uso": uso}, ensure_ascii=False, indent=2))
    print(f"\nn={m['n']}  top-1 {m['top1']:.1%}  top-3 {m['top3']:.1%}  "
          f"baseline {m['baseline']:.1%} ({m['moda']})  "
          f"sem resposta {m['sem_resposta']:.1%}")
    print(f"tokens: {uso}")
    print("\nmais confundidos (real -> previsto):")
    for p in m["confundidos"]:
        print(f"  {p['n']:3}  {p['real']}  ->  {p['previsto']}")


if __name__ == "__main__":
    main()
