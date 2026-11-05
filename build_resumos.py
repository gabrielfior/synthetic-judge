"""
Gera os resumos que vão para a LLM, do JSON do `fetch_juiz.py` ou do Parquet do
`coletar_corpus.py`:

    uv run python build_resumos.py                                 # os 10 do JSON
    uv run python build_resumos.py data/corpus.parquet   # os 24 mil
    uv run python build_resumos.py data/corpus.parquet --limite 500

Três arquivos, e a separação entre eles é o ponto:

    fichas.jsonl             a ficha completa, com as três seções da sentença
    fichas_censuradas.jsonl  só o relatório, sem juízo, sem dispositivo
    features.json            a extração determinística — o gabarito

O enunciado e a resposta não podem morar no mesmo registro: num só, basta um
consumidor distraído para vazar o resultado numa tarefa de previsão.

JSONL e não um arquivo por processo porque a ficha mediana tem 8 KB e o Parquet
tem 6.459 julgados utilizáveis — 13 mil arquivos soltos e ~100 MB. Para ler uma
ficha à mão: `jq -r '.ficha' fichas.jsonl | head -40`.
"""
import argparse
import json
import pathlib

from sj.dados import caminho_dados, carregar
from sj.eventos import nao_classificadas
from sj.features import features
from sj.ficha import ficha, ficha_censurada
from sj.tjsp import de_merito

FICHAS = "fichas.jsonl"
FICHAS_CENSURADAS = "fichas_censuradas.jsonl"
FEATURES = "features.json"


def carregar_fonte(caminho: pathlib.Path | str | None) -> list[dict]:
    """O JSON do fetch_juiz.py ou o Parquet do coletar_corpus.py, pela extensão."""
    if caminho is None:
        return carregar()
    caminho = pathlib.Path(caminho)
    if caminho.suffix == ".parquet":
        from sj import corpus  # importa pyarrow; só quando for preciso
        return corpus.ler(caminho)
    return json.loads(caminho.read_text(encoding="utf-8"))


def selecionar(processos: list[dict], limite: int | None) -> list[dict]:
    """Só o que tem relatório e dispositivo, e no máximo `limite` deles.

    O corte vem antes do limite: cortar primeiro devolveria uma amostra do que o
    CJPG serve em ordem de data, que no Parquet é majoritariamente execução
    fiscal sem relatório.
    """
    uteis = [d for d in processos if de_merito(d)]
    return uteis[:limite] if limite else uteis


def _jsonl(destino: pathlib.Path, nome: str, registros: list[dict]) -> None:
    with (destino / nome).open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def gerar(processos: list[dict], destino: pathlib.Path) -> list[dict]:
    """Escreve os três arquivos e devolve os registros de features."""
    destino.mkdir(parents=True, exist_ok=True)
    _jsonl(destino, FICHAS,
           [{"processo": d.get("processo", ""), "ficha": ficha(d)} for d in processos])
    _jsonl(destino, FICHAS_CENSURADAS,
           [{"processo": d.get("processo", ""), "ficha": ficha_censurada(d)}
            for d in processos])

    registros = [features(d) for d in processos]
    (destino / FEATURES).write_text(
        json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    return registros


def conferencia(processos: list[dict], amostra: int = 10) -> str:
    """A tabela de conferência manual, no espírito do `conferir.py`.

    O confronto que importa é entre o `resultado` extraído do dispositivo e o
    título que o cartório deu ao julgamento: são duas fontes independentes, e
    quando divergem costuma ser o cartório que errou.
    """
    linhas = []
    for d in processos[:amostra]:
        f = features(d)
        titulo = next((m["titulo"] for m in d.get("movimentacoes") or []
                       if m["titulo"].lower().startswith(("julgad", "extinta a exec"))),
                      "—")
        honorarios = (f"{f['honorarios_pct']}% {f['honorarios_base'] or '?'}"
                      if f["honorarios_pct"] else "—")
        dias = (f"{f['dias_ate_sentenca']} dias"
                if f["dias_ate_sentenca"] is not None
                else f"~{f['dias_tramitacao_estimados']} dias (CNJ)"
                if f["dias_tramitacao_estimados"] is not None else "? dias")
        linhas += [
            f"{f['processo']}  {'incidente' if f['incidente'] else '         '}  "
            f"{f['resultado']}"
            + (f" / reconvenção {f['resultado_reconvencao']}"
               if f["resultado_reconvencao"] else ""),
            f"    e-SAJ: {titulo}",
            f"    honorários {honorarios} · {f['n_movimentacoes']} movimentações · "
            f"{dias} · arts {', '.join(f['fundamento_legal'])}",
        ]
    if len(processos) > amostra:
        linhas += [f"    […] e mais {len(processos) - amostra} processos"]

    todas = [m for d in processos for m in d.get("movimentacoes") or []]
    sobraram = nao_classificadas(todas)
    linhas += ["", f"{len(todas)} movimentações · "
                   f"{sum(sobraram.values())} não classificadas"]
    linhas += [f"    {n:>3}  {titulo}" for titulo, n in sobraram.items()]
    return "\n".join(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fonte", nargs="?",
                   help="JSON do fetch_juiz.py ou Parquet do coletar_corpus.py "
                        "(padrão: data/sentencas_juiz.json)")
    p.add_argument("--limite", type=int, help="no máximo N processos")
    p.add_argument("--saida", help="diretório de saída (padrão: data/resumos)")
    args = p.parse_args()

    brutos = carregar_fonte(args.fonte)
    processos = selecionar(brutos, args.limite)
    saida = pathlib.Path(args.saida) if args.saida else caminho_dados() / "resumos"

    registros = gerar(processos, saida)
    print(conferencia(processos))

    tamanho = sum((saida / n).stat().st_size for n in (FICHAS, FICHAS_CENSURADAS))
    print(f"\n{len(processos)} de {len(brutos)} julgados "
          f"({len(brutos) - len(processos)} sem relatório ou dispositivo) "
          f"-> {saida}/")
    print(f"  {FICHAS} + {FICHAS_CENSURADAS} ({tamanho // 1024} KB) + {FEATURES}")
    print(f"  {len(registros)} registros de features")


if __name__ == "__main__":
    main()
