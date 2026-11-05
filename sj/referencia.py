"""A escada da classe de referência: tudo que o prognóstico calcula, sem LLM.

Dada uma consulta (a classe estruturada) e a base de casos, cada eixo — procedência,
prazo, dano moral — desce a escada por conta própria até um degrau com casos
suficientes:

    classe  →  grupo de classes  →  piso (todo o Procedimento Comum de Limeira)

e devolve o número, o `n` em que ele se apoia, o degrau atingido e se desceu.
O degrau faz parte da resposta: um número sem `n` e sem degrau é o único bug que
a UI não pode ter (docs/prognostico.md).

Os eixos descem independentemente: a classe pode ter 90 casos de resultado e 8
de dano moral, e então a procedência fica na classe e o valor sobe ao grupo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEGRAUS = ("classe", "grupo", "piso")

# `n` mínimo para falar num degrau, por eixo. O dano moral tem piso menor porque
# a base dele é pequena (233 concessões em 1.331 casos); abaixo disso o número
# é declarado insuficiente em vez de entregue.
PISO_N = {"procedencia": 30, "prazo": 30, "dano_moral": 15}
MIN_RAZAO = 10  # a razão concedido/pedido só é legível em ~70 casos


@dataclass(frozen=True)
class Consulta:
    classe: str | None = None
    grupo: str | None = None  # preenchido pelo chamador a partir da classe


def wilson(pos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson para uma proporção; não degenera em 0 ou 1."""
    if not n:
        return (0.0, 1.0)
    p = pos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centro - m), min(1.0, centro + m))


def quantis(xs: list[float], qs=(0.25, 0.5, 0.75)) -> list[float]:
    """Quantis por interpolação linear; lista vazia dá lista vazia."""
    if not xs:
        return []
    s = sorted(xs)
    out = []
    for q in qs:
        pos = q * (len(s) - 1)
        lo, hi = math.floor(pos), math.ceil(pos)
        out.append(s[lo] + (s[hi] - s[lo]) * (pos - lo))
    return out


def _filtro(degrau: str, q: Consulta):
    if degrau == "classe":
        return (lambda r: r["classe"] == q.classe) if q.classe else None
    if degrau == "grupo":
        return (lambda r: r["grupo"] == q.grupo) if q.grupo else None
    return lambda r: True


def descer(base: list[dict], q: Consulta, valores, piso: int,
           excluir: str | None = None) -> dict:
    """O primeiro degrau cujo `valores(linhas)` tem ao menos `piso` itens.

    `valores` recebe as linhas do degrau e devolve a lista de que o eixo se
    alimenta (pode filtrar: nem toda linha tem resultado ou valor de dano moral).
    `excluir` tira um caso pelo `id` — é o leave-one-out dos evals.

    Se nem o piso tem `piso` itens, devolve o piso com `insuficiente=True`.
    """
    ultimo = None
    for i, degrau in enumerate(DEGRAUS):
        f = _filtro(degrau, q)
        if f is None:
            continue  # sem classe (ou grupo) o degrau não existe
        linhas = [r for r in base if f(r) and r["id"] != excluir]
        vs = valores(linhas)
        ultimo = {"degrau": degrau, "n": len(vs), "valores": vs, "linhas": linhas}
        if len(vs) >= piso:
            break
    else:
        ultimo["insuficiente"] = True
    ultimo.setdefault("insuficiente", False)
    # "desceu" é relativo ao degrau em que a consulta COMEÇOU: sem classe, o
    # grupo é o ponto de partida e não uma descida
    inicial = next(d for d in DEGRAUS if _filtro(d, q) is not None)
    ultimo["desceu"] = ultimo["degrau"] != inicial
    return ultimo


def procedencia(base, q: Consulta, excluir=None) -> dict:
    r = descer(base, q, lambda ls: [x["procedente"] for x in ls
                                    if x["procedente"] is not None],
               PISO_N["procedencia"], excluir)
    vs = r.pop("valores")
    r.pop("linhas", None)
    r["probabilidade"] = sum(vs) / len(vs) if vs else None
    r["ic95"] = wilson(sum(vs), len(vs)) if vs else None
    return r


def prazo(base, q: Consulta, excluir=None) -> dict:
    r = descer(base, q, lambda ls: [x["dias"] for x in ls if x["dias"] is not None],
               PISO_N["prazo"], excluir)
    vs = r.pop("valores")
    r.pop("linhas", None)
    r["quartis_dias"] = quantis(vs)  # [p25, mediana, p75]
    return r


def dano_moral(base, q: Consulta, excluir=None) -> dict:
    """Dois números: a chance de ser concedido, dado que se pede, e o valor.

    Os dois descem a escada separados: a concessão tem base em todos os casos que
    pedem; o valor só nos que concederam e trazem o montante legível.
    """
    conc = descer(base, q, lambda ls: [int(x["dm_concedido"]) for x in ls
                                       if x["dm_pedido"]],
                  PISO_N["dano_moral"], excluir)
    vs = conc.pop("valores")
    conc.pop("linhas", None)
    conc["probabilidade_concessao"] = sum(vs) / len(vs) if vs else None
    conc["ic95"] = wilson(sum(vs), len(vs)) if vs else None

    val = descer(base, q, lambda ls: [x["dm_valor"] for x in ls
                                      if x["dm_concedido"] and x["dm_valor"]],
                 PISO_N["dano_moral"], excluir)
    vv = val.pop("valores")
    val.pop("linhas", None)
    val["quartis_reais"] = quantis(vv)

    raz = descer(base, q, lambda ls: [x["dm_razao"] for x in ls
                                      if x["dm_razao"] is not None],
                 MIN_RAZAO, excluir)
    rv = raz.pop("valores")
    raz.pop("linhas", None)
    raz["mediana"] = quantis(rv, (0.5,))[0] if rv else None
    return {"concessao": conc, "valor": val, "razao": raz}


def comparaveis(base: list[dict], q: Consulta, k: int = 3) -> list[dict]:
    """As `k` sentenças mais recentes da classe (ou do grupo, se a classe é vazia)."""
    for degrau in ("classe", "grupo"):
        f = _filtro(degrau, q)
        if f is None:
            continue
        ls = sorted((r for r in base if f(r) and r["url_pdf"]),
                    key=lambda r: r["data"], reverse=True)
        if ls:
            return [{"processo": r["processo"], "data": r["data"],
                     "resultado": r["resultado"], "url_pdf": r["url_pdf"],
                     "degrau": degrau} for r in ls[:k]]
    return []


def prognosticar(base: list[dict], q: Consulta) -> dict:
    return {"consulta": {"classe": q.classe, "grupo": q.grupo},
            "procedencia": procedencia(base, q),
            "prazo": prazo(base, q),
            "dano_moral": dano_moral(base, q),
            "comparaveis": comparaveis(base, q)}
