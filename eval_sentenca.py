"""Eval v1: a sentença sintética contra a sentença real do juiz.

    uv run python eval_sentenca.py --approve-harness          # só com --strict-harness
    uv run python eval_sentenca.py --limit 5                   # piloto
    uv run python eval_sentenca.py --reps 2                    # passada completa
    uv run python eval_sentenca.py --selftest oracle --limit 20
    uv run python eval_sentenca.py --selftest null --limit 20

Escreve em `data/eval/sentenca/<variante>/` (gitignored: nomes reais de partes):
`results.jsonl` (uma linha por caso e rep, escrita assim que o caso termina),
`traces/<id>_rep<k>.json` (a conversa inteira, com a leitura do juiz) e
`errors.jsonl` (tentativas que não geraram saída avaliável: nunca viram nota).
O relatório sai de `build-report-lite.mjs` da skill `claude-api`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from sj import sentenca as S
from sj.llm import _env, _post, cliente

FLUXO = Path("data/eval/sentenca")
CASOS = FLUXO / "cases.jsonl"
GERADOR = "deepseek-v4.1-flash"
JUIZ = "qwen3.8-27b"
MAX_TOKENS_GERADOR = 6000   # a sentença real tem p90 de ~14 mil caracteres
MAX_TOKENS_JUIZ = 800   # B1 devolve duas citações literais; 300 cortava o JSON
# O que o runner executa: se algum mudar, o próximo run para até você aprovar.
HARNESS = ("eval_sentenca.py", "build_casos_sentenca.py", "sj/sentenca.py",
           "sj/features.py", "sj/llm.py", "uv.lock")

NULOS = {"vazia": "", "nao_sei": "Não sei.",
         "constante": "Ante o exposto, JULGO PROCEDENTE a ação."}


# --- harness ----------------------------------------------------------------


def _sha_harness() -> str:
    h = hashlib.sha256()
    for nome in HARNESS:
        p = Path(nome)
        h.update(nome.encode())
        h.update(p.read_bytes() if p.exists() else b"")
    return h.hexdigest()


def conferir_harness(aprovar: bool, estrito: bool) -> None:
    """Só para o run se `--strict-harness`: é a trava do hillclimb sem supervisão,
    onde um subagente edita o prompt e não pode editar o avaliador junto."""
    arq = FLUXO / ".harness_sha"
    atual = _sha_harness()
    if not (aprovar or estrito):
        return
    if aprovar:
        arq.write_text(atual)
        sys.exit(f"harness aprovado ({atual[:12]}); rode de novo sem --approve-harness")
    if not arq.exists() or arq.read_text().strip() != atual:
        sys.exit("o harness mudou (ou nunca foi aprovado). Leia o diff de "
                 f"{', '.join(HARNESS)} e rode `--approve-harness` você mesmo.")


# --- chamadas ---------------------------------------------------------------


class Modelo:
    """Uma chamada de chat na inferência configurada, com o modelo servido conferido."""

    def __init__(self, nome: str, max_tokens: int, env: dict, raciocinio: str = "none"):
        self.nome, self.max_tokens, self.raciocinio = nome, max_tokens, raciocinio
        self.url, self.headers, _, _ = cliente("default", env, raciocinio)
        self.sessao = requests.Session()

    def __call__(self, system: str, user: str) -> dict:
        corpo = {"model": self.nome, "temperature": 0, "reasoning_effort": self.raciocinio,
                 "max_tokens": self.max_tokens,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": user}]}
        t0 = time.time()
        j = _post(self.sessao, self.url, self.headers, corpo, timeout=180)
        servido = j.get("model", "")
        if self.nome not in servido:
            raise RuntimeError(f"pedi {self.nome} e serviu {servido!r}")
        u = j.get("usage", {})
        return {"texto": j["choices"][0]["message"]["content"] or "",
                "parada": j["choices"][0].get("finish_reason"),
                "modelo": servido, "latencia": time.time() - t0,
                "usage": {"input_tokens": u.get("prompt_tokens", 0),
                          "output_tokens": u.get("completion_tokens", 0)}}


class Falha(Exception):
    def __init__(self, classe: str, msg: str, usage: dict | None = None):
        super().__init__(msg)
        self.classe, self.usage = classe, usage


def _soma(*us: dict) -> dict:
    return {k: sum(u.get(k, 0) for u in us) for k in ("input_tokens", "output_tokens")}


# --- um caso ----------------------------------------------------------------


def rodar_caso(c: dict, rep: int, gerar, juiz, sintetica_fixa: str | None,
               teto_s: float) -> tuple[dict, list]:
    """(linha de results.jsonl, trace). Levanta `Falha` se não houver saída avaliável."""
    t0 = time.time()
    real_txt = f"{c['expected']['fundamentacao']}\n{c['expected']['dispositivo']}"
    trace = [{"role": "system", "content": S.SISTEMA_GERADOR},
             {"role": "user", "content": c["relatorio"]}]

    def prazo():
        if time.time() - t0 > teto_s:
            raise Falha("timeout", f"passou de {teto_s:.0f}s no caso")

    # 1. a sentença sintética
    uso_g, lat, parada, modelo = {}, 0.0, "end_turn", GERADOR
    if sintetica_fixa is None:
        try:
            g = gerar(S.SISTEMA_GERADOR, c["relatorio"])
        except Exception as e:
            raise Falha("serving_error", repr(e)) from e
        sint, uso_g, lat, parada, modelo = (g["texto"], g["usage"], g["latencia"],
                                            g["parada"], g["modelo"])
    else:
        sint = sintetica_fixa
    trace.append({"role": "assistant", "content": sint})
    row = {"prompt_id": c["id"], "prompt": c["relatorio"], "tags": c["tags"],
           "rep": rep, "model": modelo, "judge_model": JUIZ, "usage": uso_g,
           "latency_s": round(lat, 2), "stop_reason": parada,
           "meta": {"classe": c["classe"], "origem_gabarito": c["expected"]["origem"]}}
    if parada == "length":
        # cortada no max_tokens: aparece, mas fica fora das médias
        return {**row, "status": "truncated", "grade": {}, "judge_usage": {}}, trace
    prazo()

    # 2. as notas por regra
    real = {"resultado": c["expected"]["resultado"],
            "dm_concedido": c["expected"]["dm_concedido"],
            "dm_valor": c["expected"]["dm_valor"],
            "artigos": S._artigos(real_txt)}
    sintex = S.extrair(c["relatorio"], sint)
    notas, expl = S.notas_por_regra(real, sintex)
    notas["parseavel"] = float(sintex["parseavel"])
    expl["parseavel"] = "dispositivo reconhecido" if sintex["parseavel"] \
        else "nenhum dispositivo reconhecível na saída"

    row["detalhes_novos"] = S.detalhes_novos(c["relatorio"], sint)
    row["detalhes_novos_real"] = S.detalhes_novos(c["relatorio"], real_txt)
    if not sintex["parseavel"]:
        # sem dispositivo não há sentença para o juiz ler: "sem resposta" não
        # ganha nota por não ter errado nada
        notas.update(S.NOTAS_B_ZERO)
        for k in S.NOTAS_B_ZERO:
            expl[k] = "sem dispositivo reconhecível; juiz não consultado"
        return {**row, "status": "ok", "grade": notas, "explanation": expl,
                "judge_usage": {}}, trace

    # 3. as notas por juiz, uma pergunta por chamada
    sint_a = S.ordem_ab(c["id"], rep)
    perguntas = {"mesma_razao": S.pergunta_b1(c["relatorio"], real_txt, sint, sint_a),
                 "sem_contradicao": S.pergunta_b2(c["relatorio"], sint),
                 "fundamentacao_sustenta": S.pergunta_b3(sint)}
    sims, usos = {}, []
    trace.append({"role": "tool_call", "name": "gabarito", "content": "{}"})
    trace.append({"role": "tool_result", "content": real_txt})
    for nome, p in perguntas.items():
        prazo()
        try:
            r = juiz(S.SISTEMA_JUIZ, p)
            usos.append(r["usage"])
            if nome == "mesma_razao":
                a, b = (sint, real_txt) if sint_a else (real_txt, sint)
                sim, motivo = S.ler_b1(r["texto"], a, b)
            else:
                sim, motivo = S.ler_veredito(r["texto"])
        except Exception as e:
            raise Falha("grader_error", f"{nome}: {e!r}", _soma(uso_g, *usos)) from e
        sims[nome] = sim
        expl[nome] = motivo
        trace.append({"role": "tool_call", "name": f"juiz_{nome}", "content": p})
        trace.append({"role": "tool_result", "content": r["texto"]})
    notas.update(S.notas_b(sims["mesma_razao"], sims["sem_contradicao"],
                           sims["fundamentacao_sustenta"]))
    meta = {**row["meta"], "ordem_b1": "sintética=A" if sint_a else "sintética=B"}
    return {**row, "status": "ok", "grade": notas, "explanation": expl,
            "judge_usage": _soma(*usos), "meta": meta}, trace


# --- o laço -----------------------------------------------------------------


def _ja_feitos(arq: Path) -> set[tuple[str, int]]:
    if not arq.exists():
        return set()
    return {(r["prompt_id"], r["rep"]) for r in map(json.loads, arq.open())}


def estado(flux: Path) -> None:
    """`_state.json`: as métricas e o que o relatório mostra, a primeira é a headline."""
    m = lambda i, l, k="binary": {"id": i, "label": l, "kind": k}  # noqa: E731
    (flux / "_state.json").write_text(json.dumps({
        "metrics": [m("resultado", "Resultado igual"), m("dm_concedido", "Dano moral igual"),
                    m("dm_valor", "Valor ±50%"), m("artigos", "Artigos", "float"),
                    m("mesma_razao", "Mesma razão"),
                    m("sem_contradicao", "Sem contradição"),
                    m("fundamentacao_sustenta", "Fund. sustenta"),
                    m("parseavel", "Dispositivo ok")],
        "perf_fields": [{"id": "latency_s", "label": "latência", "unit": "s"},
                        {"id": "detalhes_novos", "label": "detalhes novos"},
                        {"id": "detalhes_novos_real", "label": "det. novos (real)"}],
        "harness_paths": list(HARNESS),
    }, ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--model", default=GERADOR)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout-s", type=float, default=600)
    ap.add_argument("--selftest", choices=["oracle", "null"])
    ap.add_argument("--approve-harness", action="store_true")
    ap.add_argument("--strict-harness", action="store_true",
                    help="para se o avaliador mudou desde o último --approve-harness")
    args = ap.parse_args()

    conferir_harness(args.approve_harness, args.strict_harness)
    env = _env()
    gerar, juiz = Modelo(args.model, MAX_TOKENS_GERADOR, env), Modelo(JUIZ, MAX_TOKENS_JUIZ, env)

    casos = [json.loads(l) for l in CASOS.open()]
    # `--limit` pega os primeiros em ordem fixa embaralhada, não os 5 primeiros do
    # arquivo (que são todos de um resultado): o piloto precisa ter mistura.
    random.Random(0).shuffle(casos)
    if args.limit:
        casos = casos[:args.limit]

    destino = FLUXO / (f"_selftest/{args.selftest}" if args.selftest else args.variant)
    (destino / "traces").mkdir(parents=True, exist_ok=True)
    estado(FLUXO)
    res, erros = destino / "results.jsonl", destino / "errors.jsonl"
    feitos = _ja_feitos(res)
    trava = threading.Lock()

    # no selftest cada caso roda uma vez por sintética fixa
    tarefas = []
    for c in casos:
        for rep in range(args.reps):
            if args.selftest == "oracle":
                tarefas.append((c, rep, f"{c['expected']['fundamentacao']}\n"
                                        f"{c['expected']['dispositivo']}", "oracle"))
            elif args.selftest == "null":
                for nome, txt in NULOS.items():
                    tarefas.append((c, rep, txt, nome))
            else:
                tarefas.append((c, rep, None, ""))
    # a chave do resume inclui a variante nula, para as três não colidirem
    chave = lambda c, rep, tag: (c["id"] + (f"#{tag}" if tag else ""), rep)  # noqa: E731
    pend = [t for t in tarefas if chave(t[0], t[1], t[3]) not in feitos]
    print(f"{len(pend)} de {len(tarefas)} a rodar em {destino}", flush=True)

    feito = falhou = 0
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        fut = {pool.submit(rodar_caso, c, rep, gerar, juiz, fixa, args.timeout_s):
               (c, rep, tag) for c, rep, fixa, tag in pend}
        for f in as_completed(fut):
            c, rep, tag = fut[f]
            cid = chave(c, rep, tag)[0]
            try:
                linha, trace = f.result()
                linha["prompt_id"] = cid
                with trava:
                    with res.open("a") as o:
                        o.write(json.dumps(linha, ensure_ascii=False) + "\n")
                    (destino / "traces" / f"{cid.replace('|', '_').replace('#', '-')}"
                     f"_rep{rep}.json").write_text(
                        json.dumps(trace, ensure_ascii=False, indent=1))
                feito += 1
            except Falha as e:
                with trava, erros.open("a") as o:
                    o.write(json.dumps({"prompt_id": cid, "rep": rep, "class": e.classe,
                                        "error": str(e), "usage": e.usage,
                                        "ts": time.time()}, ensure_ascii=False) + "\n")
                falhou += 1
            n = feito + falhou
            if n % 10 == 0 or n == len(fut):
                dt = time.time() - t0
                print(f"{n}/{len(fut)} (erros {falhou}) ~{dt / n * (len(fut) - n):.0f}s "
                      f"restantes", flush=True)
    resumo(destino)


def resumo(destino: Path) -> None:
    rows = [json.loads(l) for l in (destino / "results.jsonl").open()]
    ok = [r for r in rows if r["status"] == "ok"]
    print(f"\n{len(ok)} ok, {len(rows) - len(ok)} truncados "
          f"({destino / 'errors.jsonl'} tem as falhas)")
    ids = sorted({k for r in ok for k in r["grade"]})
    for k in ids:
        v = [r["grade"][k] for r in ok if k in r["grade"]]
        lo, hi = S.wilson(sum(v), len(v))
        print(f"  {k:24s} {sum(v) / len(v):6.1%}  IC95 [{lo:.1%}, {hi:.1%}]  n={len(v)}")


if __name__ == "__main__":
    main()
