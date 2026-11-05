"""Vocabulário fechado de eventos do processo.

O CPOPG usa 94 títulos distintos de movimentação nos 10 processos do corpus, e
a cauda é curta: os cinco mais frequentes somam 55% do total e nenhum deles diz
nada sobre o caso. Em vez de lista negra, mapeamos para um vocabulário fechado:

- `classificar` devolve o evento canônico, ou None;
- `agregados` conta o cartório por rótulo ("31 publicações"), para o cabeçalho;
- `nao_classificadas` devolve o que nenhuma das duas tabelas cobriu — é esse
  relatório que impede a lista branca de falhar em silêncio quando o corpus
  crescer.

`meta.tipo_da_peticao` é o que permite tipar o evento: "Petição Juntada" é o
título de 130 movimentações e não distingue contestação de petição diversa.
Por isso o `meta` é consultado antes do título.
"""
from __future__ import annotations

import re
from collections import Counter

from sj.datas import parse_data


def _tab(pares: tuple[tuple[str, str], ...]) -> tuple[tuple[re.Pattern, str], ...]:
    return tuple((re.compile(rx, re.I), rotulo) for rx, rotulo in pares)


# Consultadas na ordem: a primeira que casar ganha.
PETICOES = _tab((
    (r"reconven", "reconvencao"),
    (r"^contesta", "contestacao"),
    (r"sobre a contesta|^r[ée]plica", "replica"),
    (r"perit|pericial|vistoria|quesitos", "pericia"),
    (r"emenda à inicial", "emenda_inicial"),
    (r"liminar|antecipa", "tutela"),
    (r"apela|agravo", "recurso"),
    (r"cumprimento", "cumprimento"),
    (r"habilita", "incidente"),
    (r"provas|testemunha", "provas"),
    (r"^parecer do mp|mp ao juiz|do mp$", "manifestacao_mp"),
))

EVENTOS = _tab((
    (r"^redistribuído livremente", "redistribuicao"),
    (r"^distribuído livremente", "distribuicao"),
    (r"emenda à inicial", "emenda_inicial"),
    (r"^recebida a petição inicial", "recebimento_inicial"),
    (r"^contestação com reconven", "reconvencao"),
    (r"^contestação juntada", "contestacao"),
    (r"^r[ée]plica juntada", "replica"),
    (r"^decisão de saneamento", "saneamento"),
    (r"perito|pericial", "pericia"),
    (r"audiência", "audiencia"),
    (r"citação expedido|^ar positivo|devolvido cumprido positivo"
     r"|citação em novo endereço", "citacao"),
    (r"^ar negativo|devolvido cumprido negativo|devolvido sem cumprimento",
     "citacao_frustrada"),
    (r"assistência judiciária gratuita", "gratuidade_negada"),
    (r"liminar|antecipação de tutela", "tutela"),
    (r"^conclusos para sentença", "conclusao_sentenca"),
    (r"^julgad|extinta a execução", "sentenca"),
    (r"apela|agravo", "recurso"),
    (r"trânsito em julgado", "transito"),
    (r"cumprimento de sentença", "cumprimento"),
    (r"^arquivado", "arquivamento"),
    (r"mp ao juiz|^parecer juntado", "manifestacao_mp"),
    (r"^incidente processual|habilitação", "incidente"),
    (r"provas juntada|rol de testemunha", "provas"),
    (r"^decisão|^proferidas outras decisões", "decisao"),
))

RUIDO_PETICOES = _tab((
    (r"petições diversas|petição intermediária|^petição -|^petição juntando"
     r"|documentos solicitados|^pedido de prazo|^pedido de expedição"
     r"|^pedido de citação|^petição de diligência|^petição solicitando"
     r"|^comprovante|^manifesta", "petições"),
))

# Sem catch-all de propósito: um título novo que não casar aqui aparece em
# `nao_classificadas`, e não desaparece silenciosamente como "cartório".
RUIDO = _tab((
    (r"^certidão de publicação|remessa da intimação", "publicações"),
    (r"remetido ao dje|^ato ordinatório - intima", "intimações"),
    (r"^conclusos para", "conclusões"),
    (r"prazo", "prazos"),
    (r"^certidão|^ato ordinat|despacho de mero expediente|^documento juntado"
     r"|^carta |^ofício|^mensagem eletrônica|^e-mail|^protocolo juntado"
     r"|^mandado juntado|^expedição de documento|^complemento do peticionamento"
     r"|^petição intermediária|^determinada a manifestação|^manifestação sobre"
     r"|^remetidos os autos|^recebidos os autos|^determinada a inclusão"
     r"|^decisão interlocutória de 2|^contrarrazões|^comprovante"
     r"|^pedido de inclusão em pauta", "expedientes"),
))


def _casar(tabela, texto: str) -> str | None:
    for rx, rotulo in tabela:
        if texto and rx.search(texto):
            return rotulo
    return None


def _tipo_peticao(mov: dict) -> str:
    return (mov.get("meta") or {}).get("tipo_da_peticao", "")


def classificar(mov: dict) -> str | None:
    """O evento canônico da movimentação, ou None se ela não for evento."""
    tipo = _tipo_peticao(mov)
    if tipo:
        return _casar(PETICOES, tipo)
    return _casar(EVENTOS, mov.get("titulo", ""))


def rotulo_ruido(mov: dict) -> str | None:
    """O rótulo de agregação do expediente de cartório, ou None se desconhecido."""
    if classificar(mov):
        return None
    tipo = _tipo_peticao(mov)
    if tipo:
        return _casar(RUIDO_PETICOES, tipo)
    return _casar(RUIDO, mov.get("titulo", ""))


def linha_do_tempo(movs: list[dict]) -> list[dict]:
    """Os eventos, em ordem cronológica, um por (evento, data)."""
    vistos, linha = set(), []
    for mov in reversed(movs):
        evento, data = classificar(mov), parse_data(mov.get("data"))
        if not evento or not data or (evento, data) in vistos:
            continue
        vistos.add((evento, data))
        linha.append({"data": data.isoformat(), "evento": evento,
                      "titulo": mov.get("titulo", ""),
                      "detalhe": mov.get("detalhe", "").strip()})
    linha.sort(key=lambda e: e["data"])
    return linha


def agregados(movs: list[dict]) -> dict[str, int]:
    """Contagem do cartório por rótulo, para o cabeçalho da ficha."""
    c = Counter(r for mov in movs if (r := rotulo_ruido(mov)))
    return dict(c.most_common())


def nao_classificadas(movs: list[dict]) -> dict[str, int]:
    """Títulos que nem viraram evento nem casaram com o cartório conhecido."""
    c = Counter(mov.get("titulo", "") for mov in movs
                if not classificar(mov) and not rotulo_ruido(mov))
    return dict(c.most_common())
