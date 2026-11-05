"""A ficha em Markdown de um processo — o que a LLM lê.

Duas variantes, emitidas lado a lado:

- `ficha`: o processo inteiro, incluindo as três seções da sentença;
- `ficha_censurada`: só até a conclusão para sentença, sem fundamentação, sem
  dispositivo e sem nada que identifique o juízo. É a entrada de qualquer
  tarefa de previsão de resultado — o gabarito correspondente é o registro de
  `sj.features`.

O JSON continua sendo a fonte: a ficha é projeção derivada, sempre regenerável.
"""
from __future__ import annotations

import re

from sj.datas import dias, inicio, redistribuicao, sentenca
from sj.eventos import agregados, linha_do_tempo
from sj.features import MARCADOR
from sj.tjsp import FIM_RELATORIO

# "SENTENÇA / Processo Digital nº / Classe - Assunto / ... / Juiz(a) de Direito:
# Dr(a). Fulano" — o cabeçalho que o e-SAJ carimba antes do relatório.
CABECALHO = re.compile(r"^.*?\b\d\.?\s*RELAT[ÓO]RIO\b[.:]?\s*", re.S | re.I)
LINHA_JUIZ = re.compile(r"^.*ju[ií]z\(a\).*$", re.M | re.I)
DETALHE_MAX = 120  # chars do detalhe que cabem numa linha de marco
# Nos demais eventos o `detalhe` é metadado do e-SAJ — número de protocolo,
# código de AR, nome do oficial de justiça — e não diz nada sobre o caso.
COM_DETALHE = frozenset({"decisao", "sentenca", "saneamento", "tutela",
                         "audiencia", "gratuidade_negada"})


def secoes(texto: str) -> tuple[str, str, str]:
    """Relatório, fundamentação e dispositivo, repartindo pelo ÚLTIMO marcador.

    `sj.tjsp.split_sentenca` casa o primeiro marcador e, quando a fundamentação
    já traz um "portanto, julgo...", o que está entre os dois marcadores acaba
    dentro do dispositivo. Aqui esse trecho volta para a fundamentação.
    """
    marcas = list(MARCADOR.finditer(texto or ""))
    corte = marcas[-1].start() if marcas else len(texto or "")
    antes, dispositivo = (texto or "")[:corte], (texto or "")[corte:]

    m = FIM_RELATORIO.search(antes)
    relatorio, fundamentacao = ((antes[:m.end()], antes[m.end():]) if m
                                else (antes, ""))
    return relatorio.strip(), fundamentacao.strip(), dispositivo.strip()


def _tramitacao(d: dict, censurada: bool) -> str:
    """A linha de datas, marcando a estimada com til e nota de origem.

    Sem CPOPG não há data exata de ajuizamento, e a estimativa do número CNJ
    erra 35 dias no p90: apresentá-la sem marca faria a ficha afirmar mais do
    que sabe. Na censurada os dias de tramitação também saem — somados à
    distribuição, devolvem a data da sentença.
    """
    data, origem = inicio(d)
    fim = sentenca(d)
    if origem == "cnj":
        partes = [f"Distribuído ~{data.isoformat()} (estimado do nº CNJ)"]
        corridos = d.get("dias_tramitacao")
        corridos = f"~{corridos}" if corridos is not None else None
    else:
        partes = [f"Ajuizado {data.isoformat()}"] if data else []
        corridos = dias(data, fim)

    if redist := redistribuicao(d):
        partes += [f"redistribuído em {redist.isoformat()}"]
    if not censurada and fim:
        partes += [f"Sentenciado {fim.isoformat()}"]
        if corridos is not None:
            partes += [f"{corridos} dias"]
    if movs := d.get("movimentacoes"):
        partes += [f"{len(movs)} movimentações"]
    return " · ".join(partes)


def _cabecalho(d: dict, censurada: bool) -> list[str]:
    capa = d.get("capa") or {}
    classe = d.get("classe") or capa.get("classe", "")
    assunto = d.get("assunto") or capa.get("assunto", "")
    # Vara, foro e magistrado identificam o juízo com a mesma força do nome.
    juizo = " · ".join(p for p in (capa.get("vara") or d.get("vara"),
                                   capa.get("foro") or d.get("foro"),
                                   capa.get("juiz") or d.get("magistrado")) if p)

    linhas = [f"# {d.get('processo', '')}", f"{classe} — {assunto}".strip(" —")]
    if juizo and not censurada:
        linhas.append(juizo)
    if valor := capa.get("valor_acao"):
        linhas.append(f"Valor da causa: {valor}")
    if tramitacao := _tramitacao(d, censurada):
        linhas.append(tramitacao)
    if cartorio := agregados(d.get("movimentacoes") or []):
        linhas.append("Cartório: " + " · ".join(f"{n} {rotulo}"
                                                for rotulo, n in cartorio.items()))
    return linhas


def _partes(d: dict) -> list[str]:
    linhas = []
    for parte in (d.get("capa") or {}).get("partes") or []:
        advogados = ", ".join(parte.get("advogados") or [])
        linhas.append(f"{parte['tipo']}: {parte['nome']}"
                      + (f" — adv. {advogados}" if advogados else ""))
    return ["## Partes", *linhas] if linhas else []


def _detalhe(texto: str) -> str:
    """Um marco é uma linha. Em 1014337-65.2015 o `detalhe` de uma decisão traz
    o ato inteiro — sem corte, a linha do tempo volta a ser o JSON."""
    corpo = " ".join((texto or "").split())
    if len(corpo) <= DETALHE_MAX:
        return corpo
    return corpo[:DETALHE_MAX].rsplit(" ", 1)[0] + "…"


def _marcos(d: dict, censurada: bool) -> list[str]:
    linha = linha_do_tempo(d.get("movimentacoes") or [])
    if censurada:
        # Tudo a partir da sentença entrega o resultado: recurso, trânsito e
        # cumprimento denunciam quem ganhou tanto quanto o dispositivo.
        corte = next((i for i, e in enumerate(linha) if e["evento"] == "sentenca"),
                     len(linha))
        linha = linha[:corte]
    if not linha:
        return []
    return ["## Marcos", *(f"{e['data']}  {e['evento']}"
                          + (f"  ({_detalhe(e['detalhe'])})"
                             if e["detalhe"] and e["evento"] in COM_DETALHE else "")
                          for e in linha)]


def _sem_cabecalho(relatorio: str) -> str:
    """Corta o carimbo do e-SAJ; se não houver marcador, tira a linha do juiz."""
    if CABECALHO.search(relatorio):
        return CABECALHO.sub("", relatorio).strip()
    return LINHA_JUIZ.sub("", relatorio).strip()


def _anonimizar(texto: str, d: dict) -> str:
    nome = (d.get("capa") or {}).get("juiz") or d.get("magistrado") or ""
    return re.sub(re.escape(nome), "[magistrado]", texto, flags=re.I) if nome else texto


def _bloco(titulo: str, corpo: str) -> list[str]:
    return [f"## {titulo}", corpo] if corpo else []


def ficha(d: dict) -> str:
    relatorio, fundamentacao, dispositivo = secoes(d.get("texto", ""))
    blocos = [
        "\n".join(_cabecalho(d, censurada=False)),
        *map("\n".join, filter(None, (_partes(d), _marcos(d, censurada=False)))),
        *_bloco("Relatório", relatorio),
        *_bloco("Fundamentação", fundamentacao),
        *_bloco("Dispositivo", dispositivo),
    ]
    return "\n\n".join(blocos) + "\n"


def ficha_censurada(d: dict) -> str:
    relatorio, _, _ = secoes(d.get("texto", ""))
    blocos = [
        "\n".join(_cabecalho(d, censurada=True)),
        *map("\n".join, filter(None, (_partes(d), _marcos(d, censurada=True)))),
        *_bloco("Relatório", _sem_cabecalho(relatorio)),
    ]
    return _anonimizar("\n\n".join(blocos) + "\n", d)
