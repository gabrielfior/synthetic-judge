"""Descobre os magistrados de 1ª instância de Limeira/SP com sentenças utilizáveis."""
import statistics as st
from collections import Counter, defaultdict
from datetime import date, timedelta

from sj.limeira import ALVO, VALUES
from sj.tjsp import Consulta, buscar

# O CJPG devolve ZERO silenciosamente se a janela passa de ~1 ano -> fatiar.
INICIO, FIM, JANELA = date(2026, 1, 1), date(2026, 8, 25), 60


def janelas(inicio, fim, dias):
    cur = inicio
    while cur < fim:
        prox = min(cur + timedelta(days=dias), fim)
        yield cur.strftime("%d/%m/%Y"), prox.strftime("%d/%m/%Y")
        cur = prox + timedelta(days=1)


vistos, docs = set(), []
for ini, fim in janelas(INICIO, FIM, JANELA):
    lote = buscar(Consulta(dt_inicio=ini, dt_fim=fim, varas=VALUES), paginas=20)
    novos = [d for d in lote if d["processo"] not in vistos]
    vistos.update(d["processo"] for d in novos)
    docs += novos
    print(f"  {ini}–{fim}: {len(lote)} docs ({len(novos)} novos)")

sent = [d for d in docs
        if d["tipo"] == "SENTENÇA" and d["split_ok"]
        and len(d["relatorio"]) > 1000 and len(d["dispositivo"]) > 300]
print(f"\n{len(docs)} documentos | {len(sent)} sentenças utilizáveis")
print("varas:", dict(Counter(d.get("vara", "?") for d in sent).most_common()))

por_juiz = defaultdict(list)
for d in sent:
    por_juiz[d.get("magistrado", "?")].append(d)

print(f"\n{'magistrado':<40} {'sent':>4} {'rel_med':>7} {'disp_med':>8} {'assuntos':>8}  vara")
print("-" * 104)
for nome, ds in sorted(por_juiz.items(), key=lambda kv: -len(kv[1])):
    vara = Counter(d.get("vara", "?") for d in ds).most_common(1)[0][0]
    print(f"{nome[:38]:<40} {len(ds):>4} "
          f"{st.median(len(d['relatorio']) for d in ds):>7.0f} "
          f"{st.median(len(d['dispositivo']) for d in ds):>8.0f} "
          f"{len(set(d.get('assunto') for d in ds)):>8}  {vara[:30]}")
