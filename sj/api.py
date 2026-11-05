"""A fronteira JSON do pipeline, para a UI.

Três ações, cada uma uma função pura de dicionário para dicionário:

    taxonomia   as 29 classes com grupo e definição (para o seletor da UI)
    estruturar  {texto} -> a consulta estruturada pela LLM (os chips)
    calcular    {classe, pede_dano_moral} -> a escada, sem LLM

`estruturar` e `calcular` são separadas de propósito: o advogado edita os chips e
cada edição recalcula sem nova chamada à LLM. O frontend as chama por subprocesso
(`prognosticar.py --api <ação>`), então a lógica de referência existe num só lugar.
"""
from __future__ import annotations

from typing import Callable

from sj import estruturar as est
from sj import referencia

ACOES = ("taxonomia", "estruturar", "calcular")


class EntradaInvalida(ValueError):
    """Entrada que o chamador pode corrigir; vira 400, não 500."""


def _estruturada(e: est.Estruturada) -> dict:
    return {"classe": e.classe, "alternativas": e.alternativas,
            "pede_dano_moral": e.pede_dano_moral, "motivo": e.motivo}


def _pede(v) -> bool | None:
    if v is None or isinstance(v, bool):
        return v
    raise EntradaInvalida("pede_dano_moral deve ser true, false ou null")


def executar(acao: str, entrada: dict, base: list[dict], taxonomia: list[dict],
             chamar: Callable[[str, str], str] | None = None) -> dict:
    if acao not in ACOES:
        raise EntradaInvalida(f"ação desconhecida: {acao!r}")

    if acao == "taxonomia":
        return {"classes": [{"nome": c["nome"], "grupo": c["grupo"],
                             "definicao": c["definicao"]} for c in taxonomia]}

    validos = {c["nome"] for c in taxonomia}
    grupo_de = {c["nome"]: c["grupo"] for c in taxonomia}

    if acao == "estruturar":
        texto = entrada.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise EntradaInvalida("texto vazio")
        if chamar is None:
            raise EntradaInvalida("sem cliente de LLM para estruturar")
        e = est.interpretar(chamar(est.sistema(taxonomia), texto.strip()), validos)
        return {"estruturada": _estruturada(e),
                "grupo": grupo_de.get(e.classe)}

    classe = entrada.get("classe")
    if classe is not None and classe not in validos:
        raise EntradaInvalida(f"classe desconhecida: {classe!r}")
    pede = _pede(entrada.get("pede_dano_moral"))
    resultado = referencia.prognosticar(
        base, referencia.Consulta(classe, grupo_de.get(classe)))
    # O juízo todo, para a UI situar a classe frente à média (marca na régua).
    juizo = referencia.prognosticar(base, referencia.Consulta())
    return {"pede_dano_moral": pede, "resultado": resultado,
            "juizo": {k: juizo[k] for k in ("procedencia", "prazo", "dano_moral")}}
