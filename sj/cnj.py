"""
Data de distribuição estimada a partir do número CNJ.

O número unificado é `NNNNNNN-DD.AAAA.J.TR.OOOO`: `AAAA` é o ano de
distribuição e `NNNNNNN` é um contador que zera todo 1º de janeiro e cresce a
cada novo caso do foro `OOOO`. Logo a sequência é monotônica com o dia da
distribuição — verificado com correlação de postos +1,00 em todos os anos
testados contra datas reais do CPOPG.

Isso permite datar a distribuição **sem uma requisição sequer**: para cada
(foro, ano), a menor e a maior sequência observadas no corpus ancoram o 1º de
janeiro e o 31 de dezembro, e o resto é interpolação linear. Validado contra 43
processos com data real de movimentação: erro mediano de 6 dias, média 12, p90
35, máximo 65. O chute ingênuo (meio do ano) erra 69 dias na mediana.

Só vale no bloco digital (1000000–1099999). Os outros blocos são numeração
paralela — 0xxxxxx é legado físico, quase todo cumprimento de sentença de casos
antigos, cuja sequência não se compara com a dos digitais do mesmo ano.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict

NUMERO = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")
DIGITAL = range(1_000_000, 1_100_000)
MIN_OBS = 30   # abaixo disso o min/max observado não ancora o ano de forma confiável


def decompor(numero: str) -> tuple[int, int, str] | None:
    """(sequência, ano, foro) — ou None se o número não for CNJ unificado."""
    m = NUMERO.match(numero)
    return (int(m.group(1)), int(m.group(3)), m.group(6)) if m else None


def e_digital(numero: str) -> bool:
    p = decompor(numero)
    return bool(p) and p[0] in DIGITAL


def faixas(numeros: list[str]) -> dict[tuple[str, int], tuple[int, int]]:
    """Menor e maior sequência do bloco digital por (foro, ano)."""
    vistos = defaultdict(list)
    for n in numeros:
        p = decompor(n)
        if p and p[0] in DIGITAL:
            vistos[(p[2], p[1])].append(p[0])
    return {k: (min(v), max(v)) for k, v in vistos.items() if len(v) >= MIN_OBS}


def distribuicao(numero: str, faixas_: dict[tuple[str, int], tuple[int, int]]) -> dt.date | None:
    """Data estimada de distribuição, ou None quando o número não permite estimar."""
    p = decompor(numero)
    if not p or p[0] not in DIGITAL:
        return None
    seq, ano, foro = p
    if (foro, ano) not in faixas_:
        return None
    lo, hi = faixas_[(foro, ano)]
    if hi <= lo:
        return None
    dia = round(364 * (seq - lo) / (hi - lo))
    return dt.date(ano, 1, 1) + dt.timedelta(days=max(0, min(364, dia)))


def tramitacao(numero: str, sentenca: dt.date,
               faixas_: dict[tuple[str, int], tuple[int, int]]) -> int | None:
    """Dias entre a distribuição estimada e a data da sentença."""
    d = distribuicao(numero, faixas_)
    return (sentenca - d).days if d and sentenca > d else None
