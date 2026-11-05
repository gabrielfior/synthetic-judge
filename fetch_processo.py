"""
Baixa um processo do CPOPG pelo número (ou por uma URL do e-SAJ) e grava o JSON.

    uv run python fetch_processo.py 1017657-45.2023.8.26.0320
    uv run python fetch_processo.py "https://esaj.tjsp.jus.br/cpopg/show.do?...&processo.numero=..."
"""
import json
import re
import sys

from sj.cpopg import buscar_processo

PROC_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")


def main(alvo: str) -> None:
    m = PROC_RE.search(alvo)
    if not m:
        sys.exit(f"não achei um número de processo em {alvo!r}")
    proc = buscar_processo(m.group(0))

    saida = f"data/processo_{m.group(0)}.json"
    with open(saida, "w") as f:
        json.dump(proc, f, ensure_ascii=False, indent=1)

    com_meta = sum(1 for x in proc["movimentacoes"] if x["meta"])
    com_doc = sum(1 for x in proc["movimentacoes"] if x["url_documento"])
    print(f"{proc['processo']} — {proc['classe']} / {proc['assunto']}")
    print(f"{proc['vara']}, {proc['foro']} · juiz: {proc['juiz'] or '(não informado)'}")
    print(f"{len(proc['movimentacoes'])} movimentações "
          f"({com_meta} com metadados, {com_doc} com documento) -> {saida}")


if __name__ == "__main__":
    main(sys.argv[1])
