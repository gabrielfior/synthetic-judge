"""O extrator de assunto: relatório em texto livre -> assunto canônico do e-SAJ.

É a camada de estruturação da abordagem A de `docs/prognostico.md`. A LLM só
escolhe, numa lista fechada, o assunto de um caso descrito em prosa; tudo que
vem depois (taxa, prazo, valor) é Python determinístico. Este módulo tem o que
o eval precisa e não toca a rede: o enunciado, o parse da resposta, a entrada
sem vazamento e as métricas. O cliente HTTP vive em `eval_extrator.py`.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from sj.ficha import secoes

CLASSE = "Procedimento Comum Cível"
COMARCA = "Limeira"

# O carimbo do e-SAJ antes do relatório traz "Classe - Assunto  <classe> -
# <assunto>": o próprio rótulo. Sem tirar essas linhas o eval mediria leitura de
# cabeçalho. "Processo Digital nº", "SENTENÇA" e a linha do juiz não vazam o
# rótulo, mas também não dizem nada sobre o caso.
_CARIMBO = re.compile(
    r"^\s*(?:SENTEN[ÇC]A|Processo Digital.*|Classe\s*-\s*Assunto.*|Juiz\(a\).*)\s*$",
    re.I | re.M)


def entrada(d: dict) -> str:
    """O relatório de um julgado, sem o carimbo que carrega o assunto."""
    relatorio, _, _ = secoes(d.get("texto", ""))
    return _CARIMBO.sub("", relatorio).strip()


def casos(docs: list[dict], so_split_ok: bool = True) -> list[dict]:
    """Os julgados que o produto v1 cobre, com a entrada e o rótulo prontos.

    `so_split_ok=False` inclui os truncados do CJPG (sem marcador de dispositivo),
    cuja entrada é o texto inteiro que o tribunal serviu.

    O mesmo número de processo aparece mais de uma vez no corpus (301 documentos
    em 147 processos de Limeira: a sentença e decisões posteriores). `id` é
    processo|data e é a chave única; indexar por `processo` faz o último
    documento sobrescrever os outros.
    """
    return [{"processo": d["processo"], "id": f"{d['processo']}|{d['data']}",
             "assunto": d["assunto"], "relatorio": entrada(d), "doc": d}
            for d in docs
            if d["comarca"] == COMARCA and d["classe"] == CLASSE
            and (d["split_ok"] or not so_split_ok) and d["assunto"]]


def amostra(cs: list[dict], n: int) -> list[dict]:
    """`n` casos, o mesmo número de cada assunto até onde houver — em rodízio.

    Estratificar por rodízio e não proporcionalmente: a amostra proporcional de
    150 casos teria 17 de "Práticas Abusivas" e quase nenhum dos assuntos raros,
    e o eval não diria nada sobre a cauda.
    """
    por_assunto: dict[str, list[dict]] = {}
    for c in sorted(cs, key=lambda c: c["id"]):
        por_assunto.setdefault(c["assunto"], []).append(c)
    filas = list(por_assunto.values())
    saida: list[dict] = []
    while len(saida) < n and any(filas):
        for fila in filas:
            if fila and len(saida) < n:
                saida.append(fila.pop(0))
    return saida


SISTEMA = """\
Você classifica o assunto de ações cíveis do TJSP. Recebe o relatório de uma \
sentença — a narrativa do caso, escrita a partir da petição inicial e da \
contestação — e escolhe, entre os assuntos da lista, os 3 mais prováveis, do \
mais para o menos provável.

Use somente assuntos da lista, escritos exatamente como nela. Vários assuntos \
se sobrepõem; escolha pelo que o relatório descreve, não pela palavra solta. \
Responda apenas com JSON: {"assuntos": ["...", "...", "..."]}

Assuntos:
"""


def sistema(assuntos: list[str]) -> str:
    return SISTEMA + "\n".join(f"- {a}" for a in sorted(assuntos))


def interpretar(resposta: str, validos: set[str]) -> list[str]:
    """Os assuntos da resposta, na ordem, sem inventados nem repetidos.

    Um assunto fora da lista é descartado em vez de aproximado: o extrator
    existe para devolver um valor que a camada determinística consiga indexar.
    """
    m = re.search(r"\{.*\}", resposta, re.S)
    try:
        brutos = json.loads(m.group(0))["assuntos"] if m else []
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    saida: list[str] = []
    for a in brutos if isinstance(brutos, list) else []:
        if isinstance(a, str) and a in validos and a not in saida:
            saida.append(a)
    return saida[:3]


def metricas(resultados: list[dict]) -> dict:
    """Top-1, top-3, baseline da classe majoritária e os pares mais confundidos.

    Cada resultado: {"assunto": rótulo real, "previsto": [até 3 assuntos]}.
    O baseline usa a moda do próprio conjunto avaliado.
    """
    n = len(resultados)
    if not n:
        return {"n": 0}
    top1 = sum(r["previsto"][:1] == [r["assunto"]] for r in resultados)
    top3 = sum(r["assunto"] in r["previsto"][:3] for r in resultados)
    moda, freq = Counter(r["assunto"] for r in resultados).most_common(1)[0]
    pares = Counter((r["assunto"], r["previsto"][0]) for r in resultados
                    if r["previsto"] and r["previsto"][0] != r["assunto"])
    return {"n": n, "top1": top1 / n, "top3": top3 / n,
            "sem_resposta": sum(not r["previsto"] for r in resultados) / n,
            "baseline": freq / n, "moda": moda,
            "confundidos": [{"real": a, "previsto": b, "n": k}
                            for (a, b), k in pares.most_common(15)]}
