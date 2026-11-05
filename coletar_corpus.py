"""
Varre o CJPG inteiro de um magistrado e grava o corpus em Parquet.

    uv run python coletar_corpus.py [cdAgente] data/corpus.parquet   # padrão: JUDGE_ID

Duas coisas aqui não são detalhe, são o que fez a primeira coleta sair errada:

1. **Sem teto de páginas.** Uma versão anterior parava na página 40 e perdeu 358
   julgados em duas janelas, sem erro nenhum — só um número menor.
2. **Confere o contador do cabeçalho.** O CJPG diz "Resultados 1 a 10 de N";
   quando N não bate com o que o parser devolveu, a janela vai para o relatório
   final em vez de passar em silêncio. Essa é a única defesa contra as duas
   formas de perda conhecidas: parar no meio da paginação, e as linhas de
   resultado que o CJPG serve com a capa completa e sem texto de documento
   (atos em massa, que o `parse_bloco` corretamente recusa).
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import time

import requests

from sj import alvo, corpus
from sj.tjsp import BASE, BLOCO_RE, UA, Consulta, parse_bloco

JANELA = 60          # dias; janela maior que ~1 ano faz o CJPG devolver zero
VAZIAS_ATE_PARAR = 8
PAUSA = 0.4
TOTAL_RE = re.compile(r"Resultados\s*<strong>.*?</strong>\s*de\s*(\d+)", re.S)


def nova_sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get(f"{BASE}/", timeout=30)
    return s


def uma_janela(s: requests.Session, cd_agente: str, ini: dt.date, fim: dt.date):
    """Devolve (docs, total_declarado_pelo_cjpg, n_paginas)."""
    c = Consulta(dt_inicio=ini.strftime("%d/%m/%Y"), dt_fim=fim.strftime("%d/%m/%Y"),
                 cd_agente=cd_agente)
    r = s.get(f"{BASE}/pesquisar.do", params=c.params(), timeout=120)
    r.encoding = "utf-8"
    m = TOTAL_RE.search(r.text)
    declarado = int(m.group(1)) if m else 0

    htmls, pagina = [r.text], 1
    while True:
        pagina += 1
        time.sleep(PAUSA)
        rp = s.get(f"{BASE}/trocarDePagina.do", params={"pagina": pagina}, timeout=120)
        rp.encoding = "utf-8"
        if not BLOCO_RE.search(rp.text):
            break
        htmls.append(rp.text)
    docs = [d for h in htmls for b in BLOCO_RE.findall(h) if (d := parse_bloco(b))]
    return docs, declarado, len(htmls)


def coletar(cd_agente: str, ate: dt.date | None = None) -> tuple[list[dict], list[str]]:
    ate = ate or dt.date.today()
    chave = lambda d: (d["processo"], d.get("data_de_disponibilização"), d["n_chars"])
    vistos, todos, avisos, vazias = set(), [], [], 0
    s, fim = nova_sessao(), ate

    for i in range(200):
        ini = fim - dt.timedelta(days=JANELA - 1)
        try:
            docs, declarado, pags = uma_janela(s, cd_agente, ini, fim)
        except Exception as e:
            avisos.append(f"{ini}..{fim}: {type(e).__name__}: {e}")
            s = nova_sessao()
            time.sleep(5)
            fim = ini - dt.timedelta(days=1)
            continue

        if len(docs) != declarado:
            avisos.append(f"{ini}..{fim}: CJPG declara {declarado}, parser devolveu {len(docs)}")
        novos = [d for d in docs if chave(d) not in vistos]
        vistos.update(map(chave, novos))
        todos += novos
        print(f"{ini}..{fim}  pags={pags:3d}  docs={len(docs):4d}  acumulado={len(todos):6d}",
              flush=True)

        vazias = vazias + 1 if declarado == 0 else 0
        if vazias >= VAZIAS_ATE_PARAR:
            break
        fim = ini - dt.timedelta(days=1)
        if i % 12 == 11:
            s = nova_sessao()
    return todos, avisos


def main() -> None:
    cd_agente = sys.argv[1] if len(sys.argv) > 1 else alvo.juiz_id()
    saida = sys.argv[2] if len(sys.argv) > 2 else f"data/corpus_{cd_agente}.parquet"
    docs, avisos = coletar(cd_agente)
    f = corpus.escrever(docs, saida)
    print(f"\n{len(docs)} julgados -> {f} ({f.stat().st_size / 1e6:.1f} MB)")
    if avisos:
        print(f"\n{len(avisos)} janelas com divergência ou erro:")
        for a in avisos:
            print(f"  {a}")


if __name__ == "__main__":
    main()
