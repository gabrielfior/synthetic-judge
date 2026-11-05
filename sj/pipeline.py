"""O pipeline do prognóstico: propriedades de um processo -> dossiê.

    entrada  →  estruturar (LLM, só se faltar a classe)  →  escada  →  dossiê

A entrada é um dicionário com qualquer destes campos:

    texto            descrição livre do caso, escrita pelo advogado
    classe           nome de uma das 29 classes (dispensa a LLM)
    pede_dano_moral  true / false / null (sobrepõe o que a LLM inferiu do texto)

Sem `texto` nem `classe` o resultado é o piso do juízo inteiro. A LLM entra por
`chamar(system, user) -> str`, injetada: o pipeline não conhece provedor e os
testes passam um dublê.
"""
from __future__ import annotations

import json
import pathlib
from typing import Callable

from sj import dossie as fmt
from sj import estruturar, referencia

BASE = pathlib.Path("data/prognostico/base.jsonl")


def carregar_base(caminho: pathlib.Path = BASE) -> list[dict]:
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não existe; rode build_base.py")
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines()]


def estruturar_entrada(entrada: dict, taxonomia: list[dict],
                       chamar: Callable[[str, str], str] | None
                       ) -> estruturar.Estruturada:
    validos = {c["nome"] for c in taxonomia}
    classe = entrada.get("classe")
    if classe is not None and classe not in validos:
        raise ValueError(f"classe desconhecida: {classe!r}")
    pede = entrada.get("pede_dano_moral")

    if classe is not None:
        return estruturar.Estruturada(classe=classe, pede_dano_moral=pede,
                                      motivo="classe informada")
    texto = (entrada.get("texto") or "").strip()
    if not texto:
        return estruturar.Estruturada(pede_dano_moral=pede,
                                      motivo="sem texto nem classe")
    if chamar is None:
        raise ValueError("há texto livre e nenhum cliente de LLM para estruturá-lo")
    e = estruturar.interpretar(chamar(estruturar.sistema(taxonomia), texto), validos)
    if pede is not None:  # o que o advogado disse vale mais que a inferência
        e.pede_dano_moral = pede
    return e


def prognosticar(entrada: dict, base: list[dict], taxonomia: list[dict],
                 chamar: Callable[[str, str], str] | None = None) -> dict:
    """{"estruturada", "resultado", "dossie"} para uma entrada."""
    e = estruturar_entrada(entrada, taxonomia, chamar)
    grupo = {c["nome"]: c["grupo"] for c in taxonomia}.get(e.classe)
    resultado = referencia.prognosticar(base, referencia.Consulta(e.classe, grupo))
    return {"estruturada": e, "resultado": resultado,
            "dossie": fmt.dossie(entrada.get("texto"), e, resultado)}
