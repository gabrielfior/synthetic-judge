"""A tarefa de decidir: do relatório ao resultado, sem escrever a sentença.

O eval da sentença sintética mistura duas coisas: decidir (procedente, parcial,
improcedente, extinto) e escrever. Medir só a decisão é mais barato, tem menos
ruído e dá para repetir em centenas de casos. Este módulo tem a divisão sem
vazamento e as métricas; não toca a rede nem o disco.

A divisão é **temporal**: o teste são as sentenças de Limeira mais recentes e
nada que o hillclimb leia vem de depois do corte. O mesmo processo nunca está
em dois conjuntos (a sentença e a decisão de embargos do mesmo número).
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from datetime import date

RESULTADOS = ("procedente", "parcialmente_procedente", "improcedente",
              "extinto_sem_merito")
PROCEDENCIA = {"procedente", "parcialmente_procedente"}
ORDINAL = {"procedente": 1.0, "parcialmente_procedente": 0.5, "improcedente": 0.0}
FRACAO_TESTE = 0.2   # as mais recentes de Limeira
FRACAO_VAL = 0.25    # do que sobra, sorteado por processo


def _quarto(processo: str, semente: str = "decisao-v1") -> float:
    """Um número em [0, 1) estável por processo, para sortear a validação."""
    h = hashlib.sha256(f"{semente}|{processo}".encode()).hexdigest()
    return int(h[:8], 16) / 0x100000000


def dividir(casos: list[dict], foro_alvo: str = "Limeira") -> tuple[dict, dict]:
    """(conjunto de cada id, manifesto). `casos` tem id, processo, data e comarca.

    - teste: os `FRACAO_TESTE` mais recentes do foro alvo; o corte é a data do
      primeiro deles. Os processos do teste somem dos outros conjuntos.
    - treino: tudo que é anterior ao corte, de qualquer foro (o mesmo juiz em
      outra comarca entra aqui) e não é do teste ou da validação.
    - validação: `FRACAO_VAL` dos processos do foro alvo anteriores ao corte,
      sorteados por hash do número do processo.
    - o que é do corte em diante e não é do teste (outro foro, mais novo) fica fora.
    """
    alvo = sorted((c for c in casos if c["comarca"] == foro_alvo),
                  key=lambda c: (c["data"], c["id"]))
    n_teste = round(len(alvo) * FRACAO_TESTE)
    teste = alvo[len(alvo) - n_teste:]
    corte = teste[0]["data"]
    proc_teste = {c["processo"] for c in teste}
    id_teste = {t["id"] for t in teste}
    conj: dict[str, str] = {}
    for c in casos:
        if c["id"] in id_teste:
            conj[c["id"]] = "teste"
        elif c["processo"] in proc_teste or c["data"] >= corte:
            continue  # vazaria o teste ou é do futuro
        elif c["comarca"] == foro_alvo and _quarto(c["processo"]) < FRACAO_VAL:
            conj[c["id"]] = "val"
        else:
            conj[c["id"]] = "treino"
    manifesto = {
        "corte": str(corte),
        "n": dict(Counter(conj.values())),
        "treino_por_comarca": dict(Counter(
            c["comarca"] for c in casos if conj.get(c["id"]) == "treino")),
        "resultado": {k: dict(Counter(c["resultado"] for c in casos
                                      if conj.get(c["id"]) == k))
                      for k in ("treino", "val", "teste")},
    }
    return conj, manifesto


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def bootstrap(valores: list[float], n: int = 2000, semente: int = 0) -> tuple[float, float]:
    """IC de 95% da média por bootstrap sobre os casos."""
    if not valores:
        return 0.0, 1.0
    r = random.Random(semente)
    medias = sorted(sum(r.choices(valores, k=len(valores))) / len(valores)
                    for _ in range(n))
    return medias[int(0.025 * n)], medias[int(0.975 * n)]


def metricas(pares: list[tuple[str, str | None, float | None]]) -> dict:
    """Métricas de `(real, previsto, p_procedencia)` por caso.

    - `resultado`: acerto nas 4 classes; previsto `None` (sem decisão) erra.
    - `procedencia`: procedente ou parcial contra improcedente, sem os extintos.
    - `ordinal`: erro absoluto médio em procedente 1, parcial 0,5, improcedente 0
      (menor é melhor), sem os extintos; `None` previsto conta o pior erro, 1.
    - `brier`: da probabilidade de procedência, onde o previsor dá uma; sem os extintos.
    - `parcial_prevista`: fração de previsões "parcial", que o preditor tende a inflar.
    """
    acerto = [float(r == p) for r, p, _ in pares]
    merito = [(r, p, q) for r, p, q in pares if r in ORDINAL]
    binaria = [float((r in PROCEDENCIA) == (p in PROCEDENCIA)) if p else 0.0
               for r, p, _ in merito]
    erro_ord = [abs(ORDINAL[r] - ORDINAL[p]) if p in ORDINAL else 1.0
                for r, p, _ in merito]
    com_p = [(r, q) for r, _, q in merito if q is not None]
    brier = [(q - float(r in PROCEDENCIA)) ** 2 for r, q in com_p]
    extintos = [(r, p) for r, p, _ in pares if r == "extinto_sem_merito"]
    out = {
        "n": len(pares), "n_merito": len(merito),
        "resultado": sum(acerto) / len(acerto),
        "resultado_ic": wilson(sum(acerto), len(acerto)),
        "procedencia": sum(binaria) / len(binaria),
        "procedencia_ic": wilson(sum(binaria), len(binaria)),
        "ordinal": sum(erro_ord) / len(erro_ord),
        "ordinal_ic": bootstrap(erro_ord),
        "parcial_prevista": sum(p == "parcialmente_procedente" for _, p, _ in pares) / len(pares),
        "extinto_n": len(extintos),
        "extinto_recall": (sum(p == "extinto_sem_merito" for _, p in extintos) / len(extintos)
                           if extintos else None),
    }
    if brier:
        out["brier"] = sum(brier) / len(brier)
        out["brier_ic"] = bootstrap(brier)
        out["brier_n"] = len(brier)
    return out


def taxa_por(chave: str, treino: list[dict]) -> dict[str, dict]:
    """Distribuição de resultado por valor de `chave` (classe, grupo) no treino."""
    por: dict[str, Counter] = defaultdict(Counter)
    for c in treino:
        if c.get(chave):
            por[c[chave]][c["resultado"]] += 1
    return {k: dict(v) for k, v in por.items()}


def p_procedencia(dist: dict[str, int]) -> float | None:
    """P(procedente ou parcial | mérito) numa distribuição de resultados."""
    merito = sum(dist.get(r, 0) for r in ORDINAL)
    return sum(dist.get(r, 0) for r in PROCEDENCIA) / merito if merito else None


def moda(dist: dict[str, int]) -> str:
    return max(RESULTADOS, key=lambda r: (dist.get(r, 0), -RESULTADOS.index(r)))


def antes(d: date | str, corte: date | str) -> bool:
    return str(d) < str(corte)
