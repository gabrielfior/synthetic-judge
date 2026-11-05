"""Datas do processo, com a pegadinha do processo redistribuído.

A `distribuicao` da capa não é a data de ajuizamento: em processo redistribuído
ela marca a chegada nesta vara. Em 1005625-38.2023 a diferença é de 47 dias
contra 1211 reais. A data de ajuizamento é a movimentação mais antiga.
"""
from __future__ import annotations

from datetime import date, datetime

REDISTRIBUICAO_MINIMA = 30  # dias de folga antes de chamar de redistribuição


def parse_data(s: str | date | None) -> date | None:
    """Lê `dd/mm/aaaa`, ignorando o que vier depois ("24/02/2025 às 16:12 - Livre").

    O Parquet guarda date32 e já devolve `date` pronto; o JSON guarda string.
    """
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    try:
        return datetime.strptime(s[:10], "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def iso(s: str | None) -> str:
    """`dd/mm/aaaa` -> `aaaa-mm-dd`; string vazia quando não dá para ler."""
    d = parse_data(s)
    return d.isoformat() if d else ""


def dias(inicio: date | None, fim: date | None) -> int | None:
    return (fim - inicio).days if inicio and fim else None


def ajuizamento(d: dict) -> date | None:
    """A movimentação mais antiga — o CPOPG devolve da mais recente para a mais antiga."""
    movs = d.get("movimentacoes") or []
    return parse_data(movs[-1]["data"]) if movs else None


def sentenca(d: dict) -> date | None:
    """No JSON o campo é `data_de_disponibilização`; no Parquet, `data`."""
    return parse_data(d.get("data_de_disponibilização")) or parse_data(d.get("data"))


def distribuicao_estimada(d: dict) -> date | None:
    """A estimativa que `sj.cnj` gravou na coluna `distribuicao` do Parquet.

    Lida, nunca recalculada: a interpolação é ancorada na menor e na maior
    sequência de cada foro-ano do conjunto INTEIRO que foi gravado, então
    refazê-la sobre uma fatia devolve outro número. Erro mediano de 6 dias
    contra data real, p90 de 35.

    Não confundir com `capa["distribuicao"]`, que é a chegada nesta vara e é
    exatamente o que `redistribuicao` usa.
    """
    return parse_data(d.get("distribuicao"))


def inicio(d: dict) -> tuple[date | None, str]:
    """A melhor data de início disponível, com a origem — nunca as duas somadas.

    Exata (a movimentação mais antiga, do CPOPG) ganha da estimada (do número
    CNJ). Os dois corpora são complementares: o JSON tem movimentações e não
    tem estimativa, o Parquet tem estimativa nos 24 mil e não tem movimentação.
    """
    if exata := ajuizamento(d):
        return exata, "movimentacao"
    if estimada := distribuicao_estimada(d):
        return estimada, "cnj"
    return None, ""


def redistribuicao(d: dict) -> date | None:
    """A data da capa, quando ela está longe demais do ajuizamento para ser ele."""
    ini, dist = ajuizamento(d), parse_data((d.get("capa") or {}).get("distribuicao"))
    if ini and dist and (dist - ini).days > REDISTRIBUICAO_MINIMA:
        return dist
    return None
