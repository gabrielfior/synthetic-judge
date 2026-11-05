"""
Baixa as N sentenças mais recentes de um magistrado do TJSP, cada uma com a
linha do tempo do processo que a originou.

    uv run python fetch_juiz.py                 # 10 sentenças do JUDGE_ID
    uv run python fetch_juiz.py <cdAgente> 10

O código do magistrado (`cdAgente`) é a fonte da verdade — o `nmAgente` que
aparece na URL do e-SAJ é decorativo e o e-SAJ o ignora.
"""
import json
import pathlib
import sys
import time
from datetime import date, timedelta

from sj import alvo, pastadigital
from sj.cpopg import ProcessoIndisponivel, buscar_processo
from sj.tjsp import PAUSA, Consulta, buscar, de_merito

JANELA = 60  # o CJPG devolve zero silenciosamente se a janela passa de ~1 ano
OUT = "data/sentencas_juiz.json"
PDFS = pathlib.Path("data/pdfs")


def sentencas_recentes(cd_agente: str, quantas: int) -> list[dict]:
    """Caminha para trás em janelas de datas até juntar `quantas` sentenças."""
    fim, vistos, out = date.today(), set(), []
    while len(out) < quantas and fim > date.today() - timedelta(days=730):
        ini = fim - timedelta(days=JANELA)
        lote = buscar(Consulta(dt_inicio=ini.strftime("%d/%m/%Y"),
                               dt_fim=fim.strftime("%d/%m/%Y"),
                               cd_agente=cd_agente), paginas=3)
        novas = [d for d in lote if de_merito(d) and d["processo"] not in vistos]
        vistos.update(d["processo"] for d in novas)
        out += novas
        print(f"  CJPG {ini:%d/%m/%Y}–{fim:%d/%m/%Y}: {len(lote):>3} docs, "
              f"+{len(novas)} sentenças de mérito")
        fim = ini - timedelta(days=1)
    return out[:quantas]


def main(cd_agente: str, quantas: int) -> None:
    sentencas = sentencas_recentes(cd_agente, quantas)
    if not sentencas:
        sys.exit(f"nenhuma sentença de mérito para cdAgente={cd_agente}")

    for d in sentencas:
        time.sleep(PAUSA)
        try:
            proc = buscar_processo(d["processo"])
            d["capa"] = {k: v for k, v in proc.items() if k != "movimentacoes"}
            d["movimentacoes"] = proc["movimentacoes"]
            print(f"  CPOPG {d['processo']}: {len(proc['movimentacoes'])} movimentações")
        except (ProcessoIndisponivel, OSError) as e:
            d["capa"], d["movimentacoes"], d["erro_cpopg"] = None, [], str(e)
            print(f"  CPOPG {d['processo']}: FALHOU — {e}")

    PDFS.mkdir(parents=True, exist_ok=True)
    s = pastadigital.nova_sessao()
    for d in sentencas:
        time.sleep(PAUSA)
        destino = PDFS / pastadigital.nome_arquivo(d["processo"], "Sentença")
        try:
            destino.write_bytes(pastadigital.baixar(d["url_pdf"], s))
            d["arquivo_pdf"] = str(destino)
            print(f"  PDF   {destino} ({destino.stat().st_size // 1024} KB)")
        except (pastadigital.DocumentoIndisponivel, OSError) as e:
            d["arquivo_pdf"], d["erro_pdf"] = "", str(e)
            print(f"  PDF   {d['processo']}: FALHOU — {e}")

    with open(OUT, "w") as f:
        json.dump(sentencas, f, ensure_ascii=False, indent=1)

    com_mov = [d for d in sentencas if d["movimentacoes"]]
    com_pdf = [d for d in sentencas if d["arquivo_pdf"]]
    print(f"\n{len(sentencas)} sentenças de {sentencas[0].get('magistrado')}")
    print(f"  movimentações: {len(com_mov)}/{len(sentencas)} -> {OUT}")
    print(f"  PDFs:          {len(com_pdf)}/{len(sentencas)} -> {PDFS}/")
    for d in com_pdf:
        print(f"    {d['arquivo_pdf']}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    main(argv[0] if argv else alvo.juiz_id(),
         int(argv[1]) if len(argv) > 1 else 10)
