"""Extração determinística, um registro por processo.

Serve para três coisas ao mesmo tempo: contexto compacto para a LLM, base de
estatística descritiva ("em N% dos casos ele...") e gabarito de eval.

Convenção dos valores: `None` é "não encontrei", `False` é "encontrei o
contrário". Como quase tudo aqui sai de regex sobre o dispositivo, um booleano
`False` significa, na prática, "a expressão não apareceu" — não trate como
prova de que o fato não ocorreu.
"""
from __future__ import annotations

import re

from sj.datas import (ajuizamento, dias, distribuicao_estimada, inicio, iso,
                      parse_data, sentenca)
from sj.eventos import classificar

# O split de sj.tjsp casa o PRIMEIRO marcador de dispositivo e erra quando a
# fundamentação já traz um "portanto, julgo..." — em 1009769-54.2025 ele começa
# na reconvenção. Aqui casamos sempre o ÚLTIMO.
MARCADOR = re.compile(
    r"(ante o exposto|diante do exposto|isto posto|isso posto|pelo exposto"
    r"|posto isso|em face do exposto|do exposto,|por todo o exposto"
    r"|assim, julgo|portanto, julgo)", re.I)

# "julgo" e "julgar" (a sentença que escreve "para JULGAR PROCEDENTE"), com o
# advérbio entre o verbo e o resultado: "JULGO TOTALMENTE PROCEDENTES" caía fora.
_ADV = r"(?:(?:totalmente|integralmente|igualmente|também)\s+)?"
_JULGO = r"julg(?:o|ar)\s*:?\s+" + _ADV
RESULTADO = tuple((re.compile(rx, re.I), valor) for rx, valor in (
    (r"julg(?:o|ar)\s*:?\s+parcialmente\s+procedente|julg(?:o|ar)\s+procedentes?,?\s+em\s+parte"
     r"|procedentes?,?\s+em\s+parte", "parcialmente_procedente"),
    (_JULGO + r"improcedente|improcedente[s]?\s+(o|os|a|as)\b", "improcedente"),
    (_JULGO + r"procedente", "procedente"),
    # Antes de `homologacao`: em cumprimento de sentença o juiz homologa o laudo
    # e extingue a execução na mesma frase (1014337-65.2015) — quem manda é o 924.
    (r"extint[ao]\s+.{0,40}?execução|extint[ao]\s+.{0,40}?cumprimento"
     r"|extingo\s+a\s+execução|art(?:igo)?s?\.?\s*924", "extinta_execucao"),
    # Homologar a desistência é extinguir sem julgar o mérito (art. 485, VIII).
    (r"homologo\s+(?:o\s+|a\s+)?(?:pedido\s+de\s+)?desist", "extinto_sem_merito"),
    # Reconhecimento do pedido, transação e renúncia (art. 487, III) são
    # homologados: não são procedência nem improcedência.
    (r"homologo|art(?:igo)?s?\.?\s*487,?\s*(?:inciso\s+)?III\b", "homologacao"),
    # Prescrição e decadência (art. 487, II) julgam o mérito contra o autor: o
    # juiz escreve "JULGO EXTINTO o processo, com resolução de mérito", mas o
    # resultado é o de uma improcedência.
    (r"art(?:igo)?s?\.?\s*487,?\s*(?:inciso\s+)?II\b|resolução\s+d[eo]\s+mérito.{0,80}?"
     r"(?:prescri|decad)", "improcedente"),
    (r"sem\s+(?:resolução|exame|julgamento)\s+d[eo]\s+mérito|art(?:igo)?s?\.?\s*485"
     r"|indefiro\s+a\s+petição\s+inicial|declaro\s+extint[ao](?!.{0,60}com\s+resolução)", "extinto_sem_merito"),
))

# Os verbos que decidem. O alvo de cada um vai daqui até o verbo seguinte: é
# assim que "JULGO PROCEDENTE a ação principal e JULGO IMPROCEDENTE a
# reconvenção" (1009769-54.2025) devolve dois resultados em vez de nenhum.
VERBOS = re.compile(
    r"julg(?:o|ar)\s*:?\s+parcialmente\s+procedentes?|julg(?:o|ar)\s+procedentes?,?\s+em\s+parte"
    r"|julg(?:o|ar)\s*:?\s+" + _ADV + r"improcedentes?"
    r"|julg(?:o|ar)\s*:?\s+" + _ADV + r"procedentes?"
    r"|(?<=\be\s)(?:parcialmente\s+)?(?:im)?procedentes?\b"
    r"|julgo\s+extint|extingo|declaro\s+extint|homologo|indefiro\s+a\s+petição\s+inicial",
    re.I)

ARTIGO = re.compile(r"art(?:igo)?s?\.?\s*(\d{1,4})"
                    r"(?:\s*,?\s*(?:inciso\s*)?([IVX]{1,5})\b)?", re.I)
DINHEIRO = re.compile(r"R\$\s*([\d.]+,\d{2})")
PERCENTUAL = re.compile(r"(\d{1,3}(?:,\d+)?)\s*%")
# Quem governa o percentual. Basta procurar "N%" depois de "honorários" para
# capturar juros, multa moratória, rateio da sucumbência, honorário contratual
# e fração da tabela DPE/OAB — as cinco formas observadas nos 6.459 julgados do
# Parquet. O percentual só é de honorários se a âncora mais próxima antes dele
# for "honorários".
ANCORA = re.compile(r"honorári|juros|multa|propor[çc]|contratuai|corre[çc]ão"
                    r"|tabela|equivalente|desconto|índice|reajuste|corrigid", re.I)
CONTRATUAIS = re.compile(r"contratuai", re.I)
# O adjetivo entre "valor" e a base varia — "valor atualizado da causa", "valor
# total da condenação", e um "valor updated da causa" que é erro de digitação do
# próprio dispositivo (1012623-55.2024).
BASE_HONORARIOS = tuple((re.compile(rx, re.I), valor) for rx, valor in (
    (r"valor\s+(?:\S+\s+)?d[ao]\s+condenação", "condenacao"),
    (r"valor\s+(?:\S+\s+)?d[ao]\s+causa", "causa"),
    (r"proveito\s+econômico", "proveito"),
    (r"equidade|§\s*8", "equidade"),
))
MORAL = re.compile(r"mora(?:l|is)", re.I)
CONCESSAO = re.compile(r"conden|arbitr|fix[oa]|pag(?:ar|amento)|indeniz|títul[oa] de"
                       r"|no\s+valor\s+de\s+R\$|quantia\s+de\s+R\$", re.I)
# "Morais" é sobrenome: "ANAIDE DE MORAIS GALDINO" não é dano moral. O dano moral
# do dispositivo vem como "dano(s) moral(is)" ou "indenização por moral".
DANO_MORAL = re.compile(r"danos?\s+mora(?:l|is)|(?:indeniza\w+|repara\w+)\s+(?:por\s+)?mora(?:l|is)",
                        re.I)
# Negação que vale até "moral": "afasto", "deixo de condenar em dano moral". A fraca
# ("indevido", "descabido") aparece em qualquer parte da oração ("desconto indevido
# ... CONDENAR ao pagamento de danos morais"), então só vale se nenhuma condenação
# vem entre ela e o "moral".
NEGATIVA = re.compile(r"afast|rejeit|improcede|indef[ei]r|não\s+(?:há|houve|é)|deix[oa]\s+de",
                      re.I)
NEGATIVA_FRACA = re.compile(r"indevid|descab", re.I)
RECONVENCAO = re.compile(r"reconven", re.I)
RECONVINTE = re.compile(r"reconv", re.I)
INCIDENTE = re.compile(r"habilitação|cumprimento\s+de\s+sentença|liquidação"
                       r"|execução|embargos|impugnação|incidente|precatória", re.I)
# O valor PEDIDO a título de dano moral, dito no relatório. Só padrões que
# NOMEIAM o valor: aceitar a mera proximidade entre "moral" e um "R$" pega o
# valor do contrato, da dívida ou da negativação e desloca a razão
# concedido/pedido de 50% para 70% nos 615 arbitramentos do Parquet.
PEDIDO_MORAL = tuple(re.compile(rx, re.I) for rx in (
    r"(?:danos?\s+morais?|dano\s+moral)[^.;]{0,60}?"
    r"(?:no\s+valor\s+de|no\s+importe\s+de|quantia\s+de|monta\s+de"
    r"|import[âa]ncia\s+de)\s+R\$\s*([\d.]+,\d{2})",
    r"R\$\s*([\d.]+,\d{2})[^.;]{0,60}?a\s+t[íi]tulo\s+de\s+"
    r"(?:danos?\s+morais?|dano\s+moral)",
))

JANELA_MORAL = 240    # chars de cada lado de "moral" onde procurar o valor
JANELA_BASE = 120     # chars depois do percentual onde procurar a base
JANELA_ANCORA = 240   # chars antes do percentual onde procurar quem o governa
JANELA_CONTRATO = 40  # chars depois do percentual onde "contratuais" desqualifica


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "")


def dispositivo(texto: str) -> str:
    """O dispositivo de verdade: do ÚLTIMO marcador até o fim."""
    marcas = list(MARCADOR.finditer(texto or ""))
    return texto[marcas[-1].start():].strip() if marcas else ""


def zona_decisoria(texto: str) -> str:
    """Do PRIMEIRO marcador até o fim.

    A reconvenção costuma ser julgada antes do "Ante o exposto" — é o caso de
    1009769-54.2025 — logo fora do dispositivo. Procurá-la aqui é o que permite
    manter o dispositivo estrito para o resultado da ação principal.
    """
    m = MARCADOR.search(texto or "")
    return texto[m.start():].strip() if m else ""


def _resultado(trecho: str) -> str | None:
    for rx, valor in RESULTADO:
        if rx.search(trecho):
            return valor
    return None


def _decisoes(trecho: str) -> list[tuple[str, bool]]:
    """Cada verbo decisório com o seu alvo, e se o alvo é a reconvenção.

    O alvo de um verbo termina onde começa o próximo: sem esse corte, o alvo de
    "JULGO PROCEDENTE a ação principal" engoliria "a reconvenção" da oração
    seguinte e a ação principal seria lida como reconvencional.
    """
    marcas = list(VERBOS.finditer(trecho))
    out = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(trecho)
        # O primeiro alvo começa na oração do verbo: "com fundamento no art. 485,
        # inciso III, ... declaro EXTINTA a ação" diz o motivo antes do verbo.
        ini = m.start()
        if i == 0:
            ini = max(trecho.rfind(c, 0, m.start()) for c in ".;:") + 1
        alvo = trecho[ini:fim]
        out.append((alvo, bool(RECONVENCAO.search(alvo))))
    return out


ENUMERACAO = re.compile(r"julg(?:o|ar)\s*:\s*\(?[A-Za-z]\)", re.I)
ITEM = re.compile(r"(?:(?<=\s)|^)\(?[A-Za-z]\)\s+")
JANELA_ITEM = 100  # chars do item que dizem o que ele decide


def _resultado_item(item: str) -> str | None:
    t = item[:JANELA_ITEM]
    for rx, valor in ((r"parcialmente\s+procedente|procedentes?,?\s+em\s+parte",
                       "parcialmente_procedente"),
                      (r"improcedente", "improcedente"), (r"procedente", "procedente"),
                      (r"extint|art(?:igo)?s?\.?\s*485", "extinto_sem_merito")):
        if re.search(rx, t, re.I):
            return valor
    return None


def _resultado_enumerado(disp: str) -> str | None:
    """"Julgo: a) improcedente contra X; b) procedente contra Y" é parcial.

    Vários réus ou pedidos julgados em itens com resultados diferentes: o juiz não
    escreve "parcialmente", mas o resultado da ação como um todo é esse. Itens
    iguais dão o próprio resultado; só improcedência e extinção dão improcedente.
    A reconvenção fica fora, como no resto.
    """
    m = ENUMERACAO.search(disp)
    if not m:
        return None
    itens = [i for i in ITEM.split(disp[m.start():])[1:] if not RECONVENCAO.search(i)]
    achados = {r for i in itens if (r := _resultado_item(i))}
    if len(achados) <= 1:
        return next(iter(achados), None)
    return ("parcialmente_procedente" if achados & {"procedente", "parcialmente_procedente"}
            else "improcedente")


def _partir_reconvencao(disp: str, zona: str) -> tuple[str, str]:
    """Separa o que decide a reconvenção do que decide a ação principal.

    A ação principal é lida só no dispositivo. A reconvenção é procurada na zona
    decisória inteira, porque costuma ser julgada antes do "Ante o exposto".
    """
    principal = " ".join(alvo for alvo, e_recv in _decisoes(disp) if not e_recv)
    reconvencao = " ".join(alvo for alvo, e_recv in _decisoes(zona) if e_recv)
    return principal or disp, reconvencao


def _artigos(trecho: str) -> list[str]:
    vistos = {}
    for numero, inciso in ARTIGO.findall(trecho):
        chave = f"{numero} {inciso.upper()}".strip()
        vistos[chave] = None
    return list(vistos)


def _valor(s: str) -> float | None:
    m = DINHEIRO.search(s or "")
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def _valor_pedido_moral(relatorio: str) -> float | None:
    """Quanto se pediu de dano moral, segundo o relatório."""
    for padrao in PEDIDO_MORAL:
        m = padrao.search(relatorio or "")
        if m:
            return float(m.group(1).replace(".", "").replace(",", "."))
    return None


def _razao_moral(pedido: float | None, concedido: float | None) -> float | None:
    """Fração do pedido que foi concedida.

    Imune à inflação, ao contrário do valor absoluto: os dois números saem do
    mesmo caso no mesmo momento. É o que permite comparar lotações separadas
    por onze anos sem deflacionar.

    Juiz não concede mais do que se pediu (ultra petita), então concedido acima
    do pedido é erro de extração: devolve None e deixa os dois valores de pé
    para quem quiser auditar.
    """
    if not pedido or not concedido or concedido > pedido * 1.001:
        return None
    return round(concedido / pedido, 3)


def _oracoes(trecho: str) -> list[str]:
    return re.split(r"(?<=[.;:])\s+", trecho)


# O "moral" que não é condenação: base de honorários ("sobre o valor da pretensão
# de danos morais de que sucumbiu") e o pedido do qual o autor decaiu.
# `.` e não `[^.;]`: "R$ 22.600,00" tem ponto no meio, e "julgo procedente a
# pretensão deduzida" não é base de honorários, só "o valor da pretensão" é.
_MORAL_BASE = re.compile(
    r"(?:honorári|sucumb|decai|pleite|proveito|proporç|sobre\s+o\s+valor"
    r"|valor\s+d[aoe]\s+pretens).{0,400}$", re.I | re.S)
# "... c.c. Indenização por Dano Moral, nos termos do art. 487, I, para:" é o título
# da ação, não a condenação.
_TITULO = re.compile(r"^\W*(?:nos\s+termos|com\s+fundamento|para\s*:)", re.I)
# Onde a condenação começa, a negação fraca anterior já acabou.
_CONDENA = re.compile(r"\bcondeno\b|\bcondenar\b|\bcondenando\b|\bcondene\b|\bpagar\b", re.I)
JANELA_NEGATIVA = 200  # chars antes de "moral" onde uma negação ainda vale


def _dano_moral_concedido(disp: str) -> str | None:
    """A oração do dispositivo que CONCEDE o dano moral, se houver.

    "Pediu" e "ganhou" são perguntas diferentes: no corpus do Parquet o pedido de
    dano moral costuma ser rejeitado na fundamentação, e aí o dispositivo ou não
    menciona a palavra, ou a menciona para afastá-la. Procurar "moral" no
    dispositivo respondia a pergunta errada.

    A negação vale só logo antes de "moral": "juros de mora a contar do evento
    danoso (data do desconto indevido)" vem depois do valor e não nega a
    condenação, e a oração que fixa honorários "sobre o pedido de danos morais"
    não condena a pagá-los.
    """
    # "c.c." não termina oração
    for oracao in _oracoes(re.sub(r"\bc\.\s?c\.", "c/c", disp, flags=re.I)):
        if not CONCESSAO.search(oracao) or RECONVINTE.search(oracao):
            continue
        for m in DANO_MORAL.finditer(oracao):
            antes = oracao[max(0, m.start() - JANELA_NEGATIVA): m.start()]
            recente = antes
            if cortes := list(_CONDENA.finditer(antes)):
                recente = antes[cortes[-1].end():]
            if (NEGATIVA.search(antes) or NEGATIVA_FRACA.search(recente)
                    or _MORAL_BASE.search(antes)
                    or _TITULO.search(oracao[m.end():m.end() + 60])):
                continue
            return oracao
    return None


_MIL = {"um": 1, "dois": 2, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
        "oito": 8, "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30,
        "quarenta": 40, "cinquenta": 50}
POR_EXTENSO = re.compile(r"\b(" + "|".join(_MIL) + r")\s+mil\s+reais", re.I)


def _valores(trecho: str) -> list[tuple[int, float]]:
    """(posição, valor) de cada quantia do trecho, em R$ ou por extenso ("cinco mil reais")."""
    achados = [(m.start(), float(m.group(1).replace(".", "").replace(",", ".")))
               for m in DINHEIRO.finditer(trecho)]
    achados += [(m.start(), _MIL[m.group(1).lower()] * 1000.0)
                for m in POR_EXTENSO.finditer(trecho)]
    return sorted(achados)


_VALOR_DEPOIS = re.compile(r"\s*(?:,\s*)?(?:no\s+valor|na\s+quantia|no\s+montante|no\s+importe"
                           r"|de\s+R\$|:|\(|\d)", re.I)


def _valor_dano_moral(disp: str, concedido: str) -> float | None:
    """O valor da condenação por dano moral.

    A quantia vem depois de "danos morais" quando o texto diz "danos morais no
    valor de R$ 5.000,00" ou "Indenização por Danos Morais: ... R$ 15.000,00", e
    antes quando diz "pagar R$ 7.000,00 a título de danos morais". Em algarismos
    ou por extenso ("cinco mil reais"). Sem quantia por perto, vale a primeira
    da oração.
    """
    i = disp.find(concedido)
    m = DANO_MORAL.search(concedido)
    if i >= 0 and m:
        centro = i + m.start()
        inicio = max(0, centro - JANELA_MORAL)
        janela = disp[inicio: centro + JANELA_MORAL]
        ref, fim = centro - inicio, centro - inicio + len(m.group())
        achados = _valores(janela)
        # quantia em algarismos manda: "R$ 4.000,00 (oito mil reais)" é erro de
        # digitação do juiz, e o número é o que a parte executa
        achados = [a for a in achados if DINHEIRO.match(janela[a[0]:])] or achados
        antes = [a for a in achados if a[0] < ref]
        depois = [a for a in achados if a[0] >= fim]
        if depois and (_VALOR_DEPOIS.match(janela[fim:fim + 40]) or not antes):
            return depois[0][1]
        if antes:
            return antes[-1][1]
    return _valor(concedido)


def _e_de_honorarios(disp: str, m: re.Match) -> bool:
    """O percentual em `m` é de honorários sucumbenciais?

    Vale a âncora mais próxima antes dele: em "honorários, na proporção de 50%
    para cada, fixando os honorários em 10%", o 50% é governado por "proporção"
    e o 10% por "honorários". "contratuais" logo depois desqualifica: honorário
    contratual não é o sucumbencial.
    """
    ancoras = ANCORA.findall(disp[max(0, m.start() - JANELA_ANCORA): m.start()])
    return (bool(ancoras) and ancoras[-1].lower().startswith("honorári")
            and not CONTRATUAIS.search(disp[m.end(): m.end() + JANELA_CONTRATO]))


def _honorarios(disp: str) -> tuple[float | None, str | None]:
    """O percentual e a base sobre a qual ele incide.

    A base é lida na janela logo depois do percentual, e não no dispositivo
    inteiro: em 1002364-64.2025 há duas fixações de honorários, com bases
    diferentes, e a do dispositivo inteiro pegaria a errada. Sem percentual
    (arbitramento por equidade), aí sim vale o dispositivo todo.
    """
    m = next((m for m in PERCENTUAL.finditer(disp) if _e_de_honorarios(disp, m)), None)
    if not m:
        tem = re.search(r"honorários", disp, re.I)
        return None, _base_honorarios(disp) if tem else None
    return float(m.group(1).replace(",", ".")), _base_honorarios(
        disp[m.end(): m.end() + JANELA_BASE])


def _base_honorarios(trecho: str) -> str | None:
    for rx, valor in BASE_HONORARIOS:
        if rx.search(trecho):
            return valor
    return None


def _eventos(d: dict) -> list[tuple[str, str]]:
    return [(evento, mov["data"]) for mov in (d.get("movimentacoes") or [])
            if (evento := classificar(mov))]


def features(d: dict) -> dict:
    texto = _norm(d.get("texto", ""))
    disp = dispositivo(texto)
    principal, reconvencao = _partir_reconvencao(disp, zona_decisoria(texto))
    fundamentacao = _norm(d.get("fundamentacao", ""))
    cabecalho = _norm(d.get("relatorio", ""))
    capa = d.get("capa") or {}
    eventos = _eventos(d)
    pct, base = _honorarios(disp)
    concedido = _dano_moral_concedido(disp)
    valor_concedido = _valor_dano_moral(disp, concedido) if concedido else None
    valor_pedido = _valor_pedido_moral(cabecalho)
    ini, est = ajuizamento(d), distribuicao_estimada(d)
    _, origem = inicio(d)
    decisoes = [parse_data(data) for evento, data in eventos if evento == "decisao"]

    return {
        "processo": d.get("processo", ""),
        "classe": d.get("classe") or capa.get("classe", ""),
        "assunto": d.get("assunto") or capa.get("assunto", ""),
        "incidente": bool(INCIDENTE.search(d.get("classe") or capa.get("classe", ""))),
        "resultado": _resultado_enumerado(disp) or _resultado(principal),
        "resultado_reconvencao": _resultado(reconvencao) if reconvencao else None,
        "fundamento_legal": _artigos(disp),
        "dano_moral_pedido": bool(
            MORAL.search(cabecalho + " " + (d.get("assunto") or "")
                         + " " + capa.get("assunto", ""))),
        "dano_moral_concedido": bool(concedido),
        "valor_dano_moral": valor_concedido,
        "valor_dano_moral_pedido": valor_pedido,
        "razao_dano_moral": _razao_moral(valor_pedido, valor_concedido),
        "honorarios_pct": pct,
        "honorarios_base": base,
        "sucumbencia_reciproca": bool(
            re.search(r"sucumbência\s+recíproca|cada\s+parte\s+arcará", disp, re.I)),
        "justica_gratuita": bool(
            re.search(r"justiça\s+gratuita|gratuidade\s+(?:da|de)\s+justiça"
                      r"|assistência\s+judiciária", cabecalho + " " + fundamentacao,
                      re.I)),
        "julgamento_antecipado": bool(
            re.search(r"art(?:igo)?s?\.?\s*355", fundamentacao, re.I)),
        "revelia": bool(re.search(r"\brevel", fundamentacao + " " + disp, re.I)),
        "houve_pericia": any(evento == "pericia" for evento, _ in eventos),
        "n_audiencias": sum(1 for evento, _ in eventos if evento == "audiencia"),
        "n_movimentacoes": len(d.get("movimentacoes") or []),
        # Exata e estimada em campos distintos, de propósito: a estimada tem
        # erro mediano de 6 dias e p90 de 35, e preencher o campo exato com ela
        # faria qualquer média de tramitação parecer mais precisa do que é.
        "data_ajuizamento": ini.isoformat() if ini else "",
        "data_distribuicao_estimada": est.isoformat() if est else "",
        "origem_data_inicio": origem,
        "data_sentenca": (sd.isoformat() if (sd := sentenca(d)) else ""),
        "dias_ate_sentenca": dias(ini, sentenca(d)),
        "dias_tramitacao_estimados": d.get("dias_tramitacao"),
        "dias_ate_1a_decisao": dias(ini, min(filter(None, decisoes))) if decisoes else None,
        "advogados": sorted({adv for parte in capa.get("partes") or []
                             for adv in parte.get("advogados") or []}),
        "valor_causa": _valor(capa.get("valor_acao", "")),
    }
