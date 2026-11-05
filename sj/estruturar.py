"""Texto livre do advogado -> consulta estruturada (classe + sinais).

A LLM só escolhe, de uma lista fechada, a classe da taxonomia de Limeira e diz se
o advogado pretende pedir dano moral; não calcula nada. Módulo sem rede: o
enunciado e o parse. O cliente fica em `prognosticar.py`.

A saída vira "chips" que o advogado confere antes de o cálculo valer: uma
extração confiante e errada não é detectável em runtime, então a mitigação é de
interface (docs/prognostico.md, "Modos de falha").
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field

TAXONOMIA = pathlib.Path(__file__).with_name("taxonomia_limeira.json")


def carregar_taxonomia() -> list[dict]:
    return json.loads(TAXONOMIA.read_text(encoding="utf-8"))["classes"]


SISTEMA = """\
Você recebe a descrição, escrita por um advogado, de uma ação cível a propor ou em \
curso na 4ª Vara Cível de Limeira/SP, e a classifica numa taxonomia fechada.

Escolha a UMA classe da lista que melhor descreve o que está em disputa, com o \
nome exatamente como na lista. Se a descrição for vaga demais para decidir — por \
exemplo, não diz quem é a parte contrária nem o que se pede —, devolva \
"classe": null em vez de chutar. Liste até 2 outras classes plausíveis em \
"alternativas".

"pede_dano_moral": true se a descrição diz ou deixa claro que se pedirá \
indenização por dano moral; false se descreve o pedido e não inclui dano moral; \
null se não dá para saber.

Responda apenas com JSON:
{{"classe": "..." ou null, "alternativas": ["..."], "pede_dano_moral": true|false|null, \
"motivo": "uma frase"}}

Classes:
{lista}"""


def sistema(taxonomia: list[dict]) -> str:
    return SISTEMA.format(lista="\n".join(
        f"- {c['nome']}: {c['definicao']}" for c in taxonomia))


@dataclass
class Estruturada:
    classe: str | None = None
    alternativas: list[str] = field(default_factory=list)
    pede_dano_moral: bool | None = None
    motivo: str = ""


def interpretar(resposta: str, validos: set[str]) -> Estruturada:
    """A consulta da resposta; o que não confere vira `None`, nunca é aproximado.

    Uma classe fora da lista não é "corrigida" para a mais parecida: a escada só
    sabe indexar nomes que existem, e uma classe inventada que desce em silêncio
    para o piso entregaria o número geral com cara de específico.
    """
    m = re.search(r"\{.*\}", resposta, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    if not isinstance(d, dict):
        d = {}
    classe = d.get("classe")
    alts = d.get("alternativas")
    dm = d.get("pede_dano_moral")
    return Estruturada(
        classe=classe if isinstance(classe, str) and classe in validos else None,
        alternativas=[a for a in (alts if isinstance(alts, list) else [])
                      if isinstance(a, str) and a in validos and a != classe][:2],
        pede_dano_moral=dm if isinstance(dm, bool) else None,
        motivo=d.get("motivo") if isinstance(d.get("motivo"), str) else "")
