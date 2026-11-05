"""O dossiê em texto: o que o advogado lê. Só formata; todo número vem de
`sj.referencia`, que o calcula com `n` e degrau.

Regra de ouro (docs/prognostico.md): nenhum número sai sem o `n` e o degrau de
onde veio, e uma descida na escada é dita, não escondida.
"""
from __future__ import annotations

MESES = 30.44
# a preposição já contraída ("na classe", "no grupo"): "em a classe" é erro
NOMES_DEGRAU = {"classe": "na classe", "grupo": "no grupo de classes",
                "piso": "em todo o Procedimento Comum de Limeira"}


def _num(x: float, casas: int = 1) -> str:
    """Decimal com vírgula."""
    return f"{x:.{casas}f}".replace(".", ",")


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _reais(x: float) -> str:
    return "R$ " + f"{x:,.0f}".replace(",", ".")


def _origem(r: dict, consulta: dict, unidade: str = "casos") -> str:
    """"n=131, na classe X" — e, se desceu, por quê."""
    deg = r["degrau"]
    nome = {"classe": consulta.get("classe"), "grupo": consulta.get("grupo"),
            "piso": None}[deg]
    onde = NOMES_DEGRAU[deg] + (f" «{nome}»" if nome else "")
    s = f"n={r['n']} {unidade}, {onde}"
    if r["desceu"]:
        s += (" — a classe não tinha casos suficientes, então o número é do "
              "degrau mais largo")
    if r["insuficiente"]:
        s += " — **mesmo assim a base é pequena; não confie neste número**"
    return s


def procedencia(r: dict, consulta: dict) -> list[str]:
    lo, hi = r["ic95"]
    return ["## Procedência (procedente ou parcialmente procedente)",
            f"**{_pct(r['probabilidade'])}**  (IC 95%: {_pct(lo)}–{_pct(hi)}); "
            f"{_origem(r, consulta)}.",
            "Vale para casos que chegam a sentença: acordos e desistências "
            "não estão na base."]


def prazo(r: dict, consulta: dict) -> list[str]:
    p25, med, p75 = (d / MESES for d in r["quartis_dias"])
    return ["## Prazo até a sentença",
            f"**mediana {_num(med)} meses** (metade dos casos entre {_num(p25)} e "
            f"{_num(p75)}); {_origem(r, consulta)}.",
            "Prazo estimado do número do processo (erro mediano de 6 dias), e "
            "enviesado para cima: só casos que chegaram a sentença."]


def dano_moral(r: dict, consulta: dict) -> list[str]:
    c, v, z = r["concessao"], r["valor"], r["razao"]
    lo, hi = c["ic95"]
    out = ["## Dano moral (se pedido)",
           f"Concedido em **{_pct(c['probabilidade_concessao'])}** dos casos em que "
           f"é pedido (IC 95%: {_pct(lo)}–{_pct(hi)}); {_origem(c, consulta, 'pedidos')}."]
    if v["quartis_reais"]:
        q1, med, q3 = v["quartis_reais"]
        out.append(f"Valor arbitrado, quando concedido: **mediana {_reais(med)}** "
                   f"(metade entre {_reais(q1)} e {_reais(q3)}); "
                   f"{_origem(v, consulta, 'concessões com valor')}.")
    if z["mediana"] is not None and not z["insuficiente"]:
        out.append(f"Razão concedido/pedido: mediana {_num(z['mediana'], 2)} "
                   f"({_origem(z, consulta)}).")
    return out


def comparaveis(cs: list[dict]) -> list[str]:
    if not cs:
        return []
    return ["## Sentenças comparáveis (mais recentes da " +
            ("classe" if cs[0]["degrau"] == "classe" else "grupo") + ")"] + [
        f"- {c['processo']} ({c['data']}): {c['resultado'] or 'resultado não lido'}"
        f" — {c['url_pdf']}" for c in cs]


LIMITES = ["## Limites",
           "- A classe foi inferida do texto; **confira** e corrija se estiver errada.",
           "- Em prazo e valor de dano moral a classe não reduziu o erro em "
           "validação: trate-os como a referência geral do juízo, não como "
           "estimativa do caso.",
           "- Só Limeira (2024-01 a 2026-09); janela curta, sem como separar "
           "tendência de ruído.",
           "- Isto é uma estatística do juízo, não aconselhamento jurídico."]


def dossie(entrada_texto: str | None, estruturada, resultado: dict) -> str:
    c = resultado["consulta"]
    topo = ["# Prognóstico — 4ª Vara Cível de Limeira, Procedimento Comum"]
    if entrada_texto:
        topo += ["", "> " + " ".join(entrada_texto.split())[:400]]
    topo += ["", "**Consulta estruturada**"]
    if c["classe"]:
        topo.append(f"- classe: **{c['classe']}** (grupo: {c['grupo']})")
    else:
        topo.append("- classe: **não identificada** — o texto não permite escolher; "
                    "os números abaixo são os do juízo inteiro")
    if estruturada is not None:
        if estruturada.alternativas:
            topo.append("- também plausível: " + "; ".join(estruturada.alternativas))
        dm = {True: "sim", False: "não", None: "não informado"}[estruturada.pede_dano_moral]
        topo.append(f"- pede dano moral: {dm}")
        if estruturada.motivo:
            topo.append(f"- porquê: {estruturada.motivo}")

    corpo = procedencia(resultado["procedencia"], c) + [""] + prazo(resultado["prazo"], c)
    pede = estruturada.pede_dano_moral if estruturada is not None else None
    if pede is not False:
        corpo += [""] + dano_moral(resultado["dano_moral"], c)
    cmp = comparaveis(resultado["comparaveis"])
    return "\n".join(topo + [""] + corpo + ([""] + cmp if cmp else []) + [""] + LIMITES) + "\n"
