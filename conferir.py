"""
Imprime as sentenças coletadas em formato de conferência manual: o link do
inteiro teor no e-SAJ ao lado do que o parser extraiu de cada uma.

    uv run python conferir.py            # todas
    uv run python conferir.py 3          # só as 3 primeiras
"""
import json
import sys
import textwrap

from sj.datas import ajuizamento, dias, redistribuicao, sentenca

ARQ = "data/sentencas_juiz.json"


def tramitacao(d: dict) -> str:
    """Da primeira movimentação até a sentença. Ver `sj.datas` para o porquê."""
    corridos = dias(ajuizamento(d), sentenca(d))
    if corridos is None:
        return "?"
    redist = redistribuicao(d)
    return (f"{corridos} dias"
            + (f" (redistribuído em {redist:%d/%m/%Y})" if redist else ""))


def trecho(texto: str, n: int = 420) -> str:
    corpo = " ".join(texto.split())
    corpo = corpo if len(corpo) <= n else corpo[:n].rsplit(" ", 1)[0] + " […]"
    return textwrap.fill(corpo, 96, initial_indent="    ", subsequent_indent="    ")


def main(limite: int) -> None:
    for i, d in enumerate(json.load(open(ARQ))[:limite], 1):
        c = d["capa"]
        autor = next((p["nome"] for p in c["partes"] if p["tipo"].startswith(("Reqte", "Autor", "Exeq"))), "?")
        reu = next((p["nome"] for p in c["partes"] if p["tipo"].startswith(("Reqd", "Réu", "Exec"))), "?")
        print(f"\n[{i}] {d['processo']}  —  {c['classe']}")
        print(f"    {c['assunto']}  ·  {autor}  x  {reu}")
        print(f"    ajuizada {d['movimentacoes'][-1]['data']} · sentença publicada "
              f"{d['data_de_disponibilização']} · {tramitacao(d)} · "
              f"{len(d['movimentacoes'])} movimentações")
        print(f"    PDF: {d['url_pdf']}")
        print(f"\n    RELATÓRIO — o resumo do processo ({len(d['relatorio'])} chars):")
        print(trecho(d["relatorio"]))
        print(f"\n    DISPOSITIVO ({len(d['dispositivo'])} chars):")
        print(trecho(d["dispositivo"]))
        print("    " + "-" * 96)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 99)
