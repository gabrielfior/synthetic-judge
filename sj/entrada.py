"""A lacuna da entrada: o advogado descreve o caso, não o juiz.

Os evals anteriores classificaram o RELATÓRIO da sentença. O produto recebe o
texto do advogado, que não temos (as petições não são públicas). Este módulo tem
o que o experimento precisa para aproximá-lo: um pedido de reescrita do relatório
no lugar do advogado, em três estilos, e as métricas da tradução. Sem rede.

A aproximação é otimista e o experimento declara isso: um modelo escrevendo "como
um advogado" é mais limpo e mais coerente que um advogado real, e vê o relatório
do juiz que decidiu. Serve para medir a queda de acerto por estilo e o efeito no
número final, não para prometer o acerto em produção.
"""
from __future__ import annotations

import hashlib
from collections import Counter

ESTILOS = ("curto", "medio", "detalhado")

_INSTRUCAO = {
    "curto": "Em 1 ou 2 frases, no tom de uma anotação rápida, sem valores nem datas.",
    "medio": "Em 3 a 5 frases, com os fatos principais e o que se pretende pedir.",
    "detalhado": ("Num parágrafo de 6 a 9 frases, com os fatos, valores e datas "
                  "relevantes e a lista do que se pretende pedir."),
}

REESCRITA = """\
Você é um advogado do autor, descrevendo para um colega um caso que PRETENDE \
ajuizar, antes de ajuizar. Abaixo está o relatório de uma sentença desse caso, \
escrito pelo juiz. Reescreva o caso como o advogado do autor o descreveria.

Regras:
- use só o que o autor sabe e pretende: os fatos que ele alega e o que vai pedir; \
NÃO mencione contestação, defesa do réu, provas produzidas, andamento do processo, \
audiência, perícia, juiz, sentença nem resultado;
- escreva na voz do advogado ("meu cliente", "pretendo pedir"), não na do juiz;
- não copie o rótulo jurídico do cabeçalho nem frases do relatório; reformule;
- {instrucao}

Responda apenas com o texto da descrição, sem título nem aspas.

RELATÓRIO:
{relatorio}"""


def estilo(id_: str) -> str:
    """O estilo do caso, decidido pelo hash do `id`: estável e equilibrado."""
    h = int(hashlib.md5(id_.encode()).hexdigest()[:8], 16)
    return ESTILOS[h % len(ESTILOS)]


def pedido_reescrita(relatorio: str, est: str) -> str:
    return REESCRITA.format(instrucao=_INSTRUCAO[est], relatorio=relatorio.strip())


def limpar(texto: str) -> str:
    """Tira cercas de código e aspas que o modelo põe em volta da descrição."""
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`").removeprefix("text").removeprefix("markdown").strip()
    return t.strip().strip('"“”').strip()


def metricas(linhas: list[dict]) -> dict:
    """Acerto da tradução, geral e por estilo.

    Cada linha: {"estilo", "verdadeira", "inferida" (ou None), "grupo_verdadeiro",
    "grupo_inferido" (ou None), "alternativas": [...]}. `top3` conta a classe
    verdadeira entre a inferida e as duas alternativas — é o que o advogado vê
    nos chips e pode corrigir em um clique.
    """
    def uma(ls: list[dict]) -> dict:
        n = len(ls)
        return {"n": n,
                "classe": sum(l["inferida"] == l["verdadeira"] for l in ls) / n,
                "top3": sum(l["verdadeira"] in ([l["inferida"]] + l["alternativas"])
                            for l in ls) / n,
                "grupo": sum(l["grupo_inferido"] == l["grupo_verdadeiro"]
                             for l in ls) / n,
                "nao_identificada": sum(l["inferida"] is None for l in ls) / n}

    out = {"geral": uma(linhas)}
    for e in ESTILOS:
        sub = [l for l in linhas if l["estilo"] == e]
        if sub:
            out[e] = uma(sub)
    return out


def confusoes(linhas: list[dict], k: int = 10) -> list[dict]:
    c = Counter((l["verdadeira"], l["inferida"]) for l in linhas
                if l["inferida"] != l["verdadeira"])
    return [{"verdadeira": a, "inferida": b, "n": n} for (a, b), n in c.most_common(k)]
