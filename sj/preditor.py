"""O preditor de resultado: relatório -> probabilidade de cada resultado.

A decisão da sentença sem escrevê-la (`sj/decisao.py` tem a tarefa e a divisão).
O que o hillclimb mexe vive em uma variante: `prompt.md` e `config.json`. Este
módulo monta o pedido e lê a resposta; não toca a rede nem o disco.

Fontes de informação que uma variante pode ligar, todas calculadas só com o
treino (nunca com o caso previsto nem com o futuro dele):

- `prior`: a distribuição de resultados da classe do caso nas sentenças do juiz;
- `k`: os k casos mais parecidos do treino, com o resultado de cada um;
- `lr`: as probabilidades de um TF-IDF + regressão logística treinado no treino.
"""
from __future__ import annotations

import json
import re

from sj.decisao import ORDINAL, PROCEDENCIA, RESULTADOS

NOMES = {"procedente": "procedente", "parcialmente_procedente": "parcialmente procedente",
         "improcedente": "improcedente", "extinto_sem_merito": "extinto sem mérito"}
TRECHO_EXEMPLO = 500   # chars do relatório de cada caso recuperado
MIN_N_PRIOR = 10       # casos mínimos na classe para o prior valer


def pct(d: dict[str, float], total: float | None = None) -> str:
    total = total or sum(d.get(r, 0) for r in RESULTADOS) or 1
    return ", ".join(f"{NOMES[r]} {100 * d.get(r, 0) / total:.0f}%" for r in RESULTADOS)


def texto_prior(c: dict, treino: list[dict]) -> str | None:
    """A taxa de cada resultado na classe do caso (ou no grupo, ou no juízo todo)."""
    from collections import Counter
    for chave, rotulo in (("classe", "Nesta classe de caso"), ("grupo", "Neste grupo de casos")):
        if not c.get(chave):
            continue
        d = Counter(x["resultado"] for x in treino if x.get(chave) == c[chave])
        if sum(d.values()) >= MIN_N_PRIOR:
            return (f"{rotulo} ({c[chave]}), em {sum(d.values())} sentenças deste juiz: "
                    f"{pct(d)}.")
    d = Counter(x["resultado"] for x in treino)
    return f"Em {sum(d.values())} sentenças deste juiz: {pct(d)}."


def texto_exemplo(c: dict) -> str:
    rel = re.sub(r"\s+", " ", c["relatorio"]).strip()[:TRECHO_EXEMPLO]
    dm = "concedeu dano moral" if c.get("dm_concedido") else "sem dano moral"
    return f"Relatório: {rel}\nDecisão: {NOMES[c['resultado']]}; {dm}."


class Recuperador:
    """Os casos mais parecidos do treino, por TF-IDF e cosseno."""

    def __init__(self, pool: list[dict]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.pool = pool
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                   max_features=80000)
        self.m = self.vec.fit_transform([c["relatorio"] for c in pool])

    def vizinhos(self, c: dict, k: int) -> list[dict]:
        sims = (self.m @ self.vec.transform([c["relatorio"]]).T).toarray().ravel()
        out = []
        for i in sims.argsort()[::-1]:
            v = self.pool[i]
            if v["processo"] == c["processo"]:
                continue  # o próprio caso e o outro documento do mesmo processo
            out.append(v)
            if len(out) == k:
                break
        return out[::-1]  # o mais parecido por último, perto da pergunta


def probs_lr(treino: list[dict], alvo: list[dict]) -> dict[str, dict[str, float]]:
    """`id -> {resultado: prob}` de TF-IDF + regressão logística treinada no treino."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    m = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True,
                                      max_features=80000),
                      LogisticRegression(C=3, max_iter=3000))
    m.fit([c["relatorio"] for c in treino], [c["resultado"] for c in treino])
    return {c["id"]: dict(zip(m.classes_, map(float, p)))
            for c, p in zip(alvo, m.predict_proba([c["relatorio"] for c in alvo]))}


def texto_lr(p: dict[str, float], n_treino: int) -> str:
    return (f"Um modelo estatístico treinado em {n_treino} sentenças deste juiz, que lê só "
            f"o texto do relatório, estima: {pct(p, 1.0)}.")


def montar(c: dict, config: dict, *, treino: list[dict] | None = None,
           vizinhos: list[dict] | None = None, lr: dict | None = None,
           n_treino: int = 0) -> str:
    """O pedido do usuário para um caso: o relatório e o que a variante liga."""
    partes = []
    if vizinhos:
        partes.append("Casos parecidos já decididos por este juiz, do mais distante ao "
                      "mais próximo:\n\n" + "\n\n".join(texto_exemplo(v) for v in vizinhos))
    if config.get("prior") and treino:
        partes.append(texto_prior(c, treino))
    if config.get("lr") and lr:
        partes.append(texto_lr(lr, n_treino))
    partes.append("Relatório do caso a decidir:\n" + c["relatorio"].strip())
    return "\n\n".join(p for p in partes if p)


def ler(texto: str) -> dict[str, float]:
    """As probabilidades, normalizadas. Resposta ilegível é erro, não uma previsão."""
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        raise ValueError(f"sem JSON: {(texto or '')[:100]!r}")
    j = json.loads(m.group(0))
    j = j.get("probabilidades", j)
    p = {r: float(j.get(r, j.get(NOMES[r], 0)) or 0) for r in RESULTADOS}
    total = sum(p.values())
    if total <= 0 or any(v < 0 for v in p.values()):
        raise ValueError(f"probabilidades inválidas: {j!r}")
    return {r: v / total for r, v in p.items()}


def previsao(p: dict[str, float]) -> str:
    return max(RESULTADOS, key=lambda r: (p[r], -RESULTADOS.index(r)))


def p_procedencia(p: dict[str, float]) -> float | None:
    merito = sum(p[r] for r in ORDINAL)
    return sum(p[r] for r in PROCEDENCIA) / merito if merito > 0 else None


def notas(real: str, p: dict[str, float]) -> tuple[dict, dict]:
    """(notas, explicação) de um caso. Os itens de mérito não valem para extinto."""
    pred = previsao(p)
    q = p_procedencia(p)
    n = {"resultado": float(pred == real)}
    expl = {"resultado": f"real={real} previsto={pred} " + pct(p, 1.0)}
    if real in ORDINAL:
        # pedido acolhido (procedente ou parcial) ou não (improcedente ou extinto)
        n["procedencia"] = float((pred in PROCEDENCIA) == (real in PROCEDENCIA))
        n["ordinal"] = 1.0 - (abs(ORDINAL[real] - ORDINAL[pred]) if pred in ORDINAL else 1.0)
        if q is not None:
            n["brier"] = (q - float(real in PROCEDENCIA)) ** 2
    return n, expl
