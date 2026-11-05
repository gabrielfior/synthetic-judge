"""
Prognóstico de um caso em Limeira, do texto livre ao dossiê.

    uv run python prognosticar.py "Idoso aposentado do INSS descobriu desconto ..."
    uv run python prognosticar.py --classe "Negativação indevida" --dano-moral
    uv run python prognosticar.py --json entradas.json     # lista de entradas
    echo '{"texto": "..."}' | uv run python prognosticar.py --api estruturar

`--api <ação>` é a fronteira JSON da UI (sj/api.py): lê um objeto JSON no stdin e
escreve outro no stdout. Erro de entrada sai com código 2 e {"erro": ...}.

Cada entrada tem `texto`, `classe` e/ou `pede_dano_moral` (ver sj/pipeline.py).
Pré-requisito: `uv run python build_base.py`. A estruturação usa o deepseek da
inferência configurada no `.env` (credenciais do `.env`); com `--classe` não há chamada
de rede.
"""
import argparse
import json
import sys

from sj import pipeline
from sj.api import ACOES, EntradaInvalida, executar
from sj.estruturar import carregar_taxonomia
from sj.llm import _env, _post, cliente

MODELO = "deepseek-v4.1-flash"


def chamador():
    url, headers, monta, le = cliente("default", _env(), "none")
    import requests
    sessao = requests.Session()

    def chamar(system: str, user: str) -> str:
        corpo = monta(MODELO, system, user)
        corpo["max_tokens"] = 400
        return le(_post(sessao, url, headers, corpo))[0]

    return chamar


def rodar_api(acao: str) -> int:
    try:
        bruto = sys.stdin.read().strip()
        entrada = json.loads(bruto) if bruto else {}
        if not isinstance(entrada, dict):
            raise EntradaInvalida("o corpo deve ser um objeto JSON")
        saida = executar(acao, entrada, pipeline.carregar_base(), carregar_taxonomia(),
                         chamador() if acao == "estruturar" else None)
    except (EntradaInvalida, json.JSONDecodeError) as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(saida, ensure_ascii=False))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("texto", nargs="?", help="descrição livre do caso")
    ap.add_argument("--classe", help="nome da classe (dispensa a LLM)")
    dm = ap.add_mutually_exclusive_group()
    dm.add_argument("--dano-moral", dest="dm", action="store_true", default=None)
    dm.add_argument("--sem-dano-moral", dest="dm", action="store_false")
    ap.add_argument("--json", dest="arquivo", help="arquivo JSON com uma lista de entradas")
    ap.add_argument("--saida-json", help="grava também o resultado estruturado")
    ap.add_argument("--api", choices=ACOES, help="modo JSON: stdin -> stdout")
    args = ap.parse_args()

    if args.api:
        sys.exit(rodar_api(args.api))

    if args.arquivo:
        entradas = json.load(open(args.arquivo, encoding="utf-8"))
    else:
        entradas = [{"texto": args.texto, "classe": args.classe,
                     "pede_dano_moral": args.dm}]

    base = pipeline.carregar_base()
    taxonomia = carregar_taxonomia()
    precisa_llm = any(e.get("texto") and not e.get("classe") for e in entradas)
    chamar = chamador() if precisa_llm else None

    saidas = []
    for i, entrada in enumerate(entradas, 1):
        try:
            r = pipeline.prognosticar(entrada, base, taxonomia, chamar)
        except ValueError as e:
            sys.exit(f"entrada {i}: {e}")
        print(r["dossie"])
        if len(entradas) > 1 and i < len(entradas):
            print("\n" + "=" * 78 + "\n")
        saidas.append({"entrada": entrada, "estruturada": r["estruturada"].__dict__,
                       "resultado": r["resultado"]})
    if args.saida_json:
        with open(args.saida_json, "w", encoding="utf-8") as f:
            json.dump(saidas, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
