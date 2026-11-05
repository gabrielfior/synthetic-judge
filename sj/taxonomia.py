"""Taxonomia dirigida pelos dados: classes que o relatório distingue.

O `assunto` do e-SAJ é cadastrado na distribuição por quem protocola, e vários
se sobrepõem ("Bancários" / "Contratos Bancários", "Rescisão / Resolução" /
"Rescisão do contrato e devolução do dinheiro"). Aqui a LLM propõe as classes a
partir de uma parte dos relatórios (descoberta) e as aplica ao resto (avaliação);
o assunto do tribunal vira só um termo de comparação.

Módulo sem rede: divisão, enunciados, parse e métricas. O cliente fica em
`eval_taxonomia.py`.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict

TRECHO = 600  # chars de cada relatório que entram no pedido de taxonomia
PROCEDENTE = {"procedente", "parcialmente_procedente"}
RESULTADOS_BINARIOS = PROCEDENTE | {"improcedente"}


def dividir(cs: list[dict], frac_descoberta: float = 0.3
            ) -> tuple[list[dict], list[dict]]:
    """(descoberta, avaliação), decidido pelo hash do número do processo.

    Hash e não sorteio: a divisão não muda quando o corpus ganha casos, e a
    taxonomia gerada de um lado nunca é avaliada nos casos de onde saiu.
    """
    def balde(c: dict) -> float:
        h = hashlib.md5(c["processo"].encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    return ([c for c in cs if balde(c) < frac_descoberta],
            [c for c in cs if balde(c) >= frac_descoberta])


def trecho(relatorio: str, n: int = TRECHO) -> str:
    """O começo da narrativa, sem o "Vistos." — onde o juiz diz de que se trata."""
    t = re.sub(r"^\s*Vistos[.,\s]*(etc\.?)?\s*", "", relatorio, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()[:n]


PROPOSTA = """\
Você é um jurista organizando as ações cíveis de uma vara de Limeira/SP. Abaixo \
há trechos de relatórios de sentença, cada um com um número. Proponha uma \
taxonomia de entre {min} e {max} categorias que separe os casos pelo que está \
em disputa — o tipo de relação e o pedido central —, de modo que um advogado \
reconheça a categoria do seu caso.

Regras:
- categorias mutuamente exclusivas: cada caso cabe numa só, a mais específica \
que ainda reúna muitos casos;
- sem categorias genéricas do tipo "Direito Civil" ou "Outros";
- nome curto (até 6 palavras) e uma definição de uma frase que diga o que entra \
e o que fica de fora.

Responda apenas com JSON:
{{"categorias": [{{"nome": "...", "definicao": "..."}}]}}"""


def pedido_proposta(descoberta: list[dict], minimo: int = 18, maximo: int = 30
                    ) -> tuple[str, str]:
    """(system, user) do pedido de taxonomia."""
    linhas = [f"[{i}] {trecho(c['relatorio'])}" for i, c in enumerate(descoberta, 1)]
    return PROPOSTA.format(min=minimo, max=maximo), "\n\n".join(linhas)


FUSAO = """\
Abaixo há categorias candidatas, propostas em separado por vários juristas que \
leram lotes diferentes de relatórios das mesmas ações cíveis. Muitas se \
repetem ou se sobrepõem. Funda-as numa única taxonomia de entre {min} e {max} \
categorias, com as mesmas regras:
- mutuamente exclusivas: cada caso cabe numa só, a mais específica que ainda \
reúna muitos casos;
- sem categorias genéricas do tipo "Direito Civil" ou "Outros";
- nome curto (até 6 palavras) e definição de uma frase dizendo o que entra e o \
que fica de fora.

Responda apenas com JSON:
{{"categorias": [{{"nome": "...", "definicao": "..."}}]}}"""


def lotes(descoberta: list[dict], n: int) -> list[list[dict]]:
    """Fatias de no máximo `n` casos, na ordem — o map do map-reduce."""
    return [descoberta[i:i + n] for i in range(0, len(descoberta), n)]


def pedido_fusao(propostas: list[list[dict]], minimo: int = 18, maximo: int = 30
                 ) -> tuple[str, str]:
    """(system, user) que funde as propostas dos lotes numa taxonomia só."""
    user = "\n".join(f"- {c['nome']}: {c['definicao']}"
                     for prop in propostas for c in prop)
    return FUSAO.format(min=minimo, max=maximo), user


def interpretar_taxonomia(resposta: str, minimo: int = 8, maximo: int = 60
                          ) -> list[dict]:
    """As categorias da resposta; ValueError se não der para confiar nela."""
    m = re.search(r"\{.*\}", resposta, re.S)
    try:
        cats = json.loads(m.group(0))["categorias"] if m else None
    except (json.JSONDecodeError, KeyError, TypeError):
        cats = None
    if not isinstance(cats, list):
        raise ValueError("resposta sem lista de categorias")
    saida, vistos = [], set()
    for c in cats:
        if not (isinstance(c, dict) and isinstance(c.get("nome"), str)
                and isinstance(c.get("definicao"), str)):
            raise ValueError(f"categoria malformada: {c!r}")
        if c["nome"] in vistos:
            raise ValueError(f"nome repetido: {c['nome']}")
        vistos.add(c["nome"])
        saida.append({"nome": c["nome"].strip(), "definicao": c["definicao"].strip()})
    if not minimo <= len(saida) <= maximo:
        raise ValueError(f"{len(saida)} categorias, esperava {minimo}–{maximo}")
    return saida


CLASSIFICAR = """\
Você classifica ações cíveis do TJSP. Recebe o relatório de uma sentença e \
escolhe a UMA categoria da lista que melhor descreve o que está em disputa. \
Use o nome exatamente como na lista. Responda apenas com JSON: \
{{"categoria": "..."}}

Categorias:
{lista}"""


def sistema_classificar(taxonomia: list[dict]) -> str:
    return CLASSIFICAR.format(lista="\n".join(
        f"- {c['nome']}: {c['definicao']}" for c in taxonomia))


def interpretar_categoria(resposta: str, validos: set[str]) -> str | None:
    m = re.search(r"\{.*\}", resposta, re.S)
    try:
        c = json.loads(m.group(0))["categoria"] if m else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return c if isinstance(c, str) and c in validos else None


# --- métricas -----------------------------------------------------------------

def kappa(a: list, b: list) -> float:
    """Kappa de Cohen entre dois rotuladores sobre os mesmos itens."""
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _entropia(c: Counter) -> float:
    n = sum(c.values())
    return -sum(v / n * math.log(v / n) for v in c.values())


def nmi(a: list, b: list) -> float:
    """Informação mútua normalizada (média aritmética das entropias)."""
    n = len(a)
    ca, cb, cab = Counter(a), Counter(b), Counter(zip(a, b))
    mi = sum(v / n * math.log(v * n / (ca[x] * cb[y])) for (x, y), v in cab.items())
    h = (_entropia(ca) + _entropia(cb)) / 2
    return mi / h if h else 0.0


def assunto_pelo_cluster(clusters: list, assuntos: list) -> float:
    """Acurácia de prever o assunto do tribunal pelo cluster, leave-one-out.

    Para cada caso, o assunto mais frequente dos OUTROS casos do mesmo cluster.
    Mede quanto do rótulo do tribunal o cluster explica; o teto é o quanto o
    rótulo é determinado pelo conteúdo, não pelo cadastro.
    """
    por: dict = defaultdict(Counter)
    for c, a in zip(clusters, assuntos):
        por[c][a] += 1
    acertos = 0
    for c, a in zip(clusters, assuntos):
        resto = por[c].copy()
        resto[a] -= 1
        resto += Counter()  # tira os zeros
        if resto and resto.most_common(1)[0][0] == a:
            acertos += 1
    return acertos / len(clusters)


def brier_loo(grupos: list, y: list[int], k: float = 2.0) -> list[float]:
    """Erro quadrático por caso, com a taxa do grupo sem o próprio caso.

    A taxa é suavizada para a global com peso `k` casos — sem isso, um grupo de
    n=1 prevê 0 ou 1 e o Brier explode por motivo nenhum.
    """
    por: dict = defaultdict(lambda: [0, 0])  # [positivos, n]
    for g, v in zip(grupos, y):
        por[g][0] += v
        por[g][1] += 1
    total_pos, total_n = sum(y), len(y)
    erros = []
    for g, v in zip(grupos, y):
        p0 = (total_pos - v) / (total_n - 1)
        pos, n = por[g][0] - v, por[g][1] - 1
        p = (pos + k * p0) / (n + k)
        erros.append((p - v) ** 2)
    return erros


def brier_global_loo(y: list[int]) -> list[float]:
    return brier_loo([0] * len(y), y)


def ic_diferenca(a: list[float], b: list[float], reps: int = 2000,
                 semente: int = 0) -> tuple[float, float, float]:
    """Média de (a - b) por caso e o IC 95% por bootstrap pareado.

    Negativo quer dizer que `a` erra menos. Se o IC cruza zero, a diferença
    não se distingue de ruído nesta amostra.
    """
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(semente)
    n = len(d)
    medias = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n
                    for _ in range(reps))
    return sum(d) / n, medias[int(reps * 0.025)], medias[int(reps * 0.975)]
