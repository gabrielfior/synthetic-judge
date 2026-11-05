"""
Avalia a escada de referência nos três eixos, leave-one-out sobre a base.

    uv run python build_base.py && uv run python eval_eixos.py

Para cada caso, o prognóstico é calculado SEM ele e comparado ao que de fato
aconteceu — a entrada é a classe que a LLM deu ao relatório, então isto mede o
pipeline inteiro dado um texto do juiz (não do advogado: ver docs/prognostico.md).

    procedência   Brier da probabilidade
    prazo         erro absoluto da mediana, e cobertura do intervalo p25–p75
                  (nominal 50%)
    dano moral    Brier da concessão (entre quem pede); erro do valor mediano,
                  em razão (previsto/real) e acerto dentro de ±50%

contra a referência sem classe nenhuma (o piso). Varre o piso de `n` para
responder quanto vale a regra de descer a escada.
"""
import json
import math
import pathlib
import statistics

from sj import referencia as R
from sj.referencia import Consulta

BASE = pathlib.Path("data/prognostico/base.jsonl")
SAIDA = pathlib.Path("data/prognostico/eval_eixos.json")


def media(xs):
    return sum(xs) / len(xs)


def avaliar(base: list[dict], piso_n: int | None) -> dict:
    """`piso_n=None` é o baseline: ignora a classe e fica no piso."""
    if piso_n is not None:
        R.PISO_N.update(procedencia=piso_n, prazo=piso_n,
                        dano_moral=max(5, piso_n // 2))
    brier, err_p, cob, brier_dm, razoes, graus = [], [], [], [], [], []
    for r in base:
        q = Consulta() if piso_n is None else Consulta(r["classe"], r["grupo"])
        if r["procedente"] is not None:
            p = R.procedencia(base, q, excluir=r["id"])
            brier.append((p["probabilidade"] - r["procedente"]) ** 2)
            graus.append(p["degrau"])
        if r["dias"] is not None:
            z = R.prazo(base, q, excluir=r["id"])["quartis_dias"]
            err_p.append(abs(z[1] - r["dias"]))
            cob.append(z[0] <= r["dias"] <= z[2])
        if r["dm_pedido"]:
            c = R.dano_moral(base, q, excluir=r["id"])
            brier_dm.append((c["concessao"]["probabilidade_concessao"]
                             - int(r["dm_concedido"])) ** 2)
            if r["dm_concedido"] and r["dm_valor"] and not c["valor"]["insuficiente"]:
                razoes.append(c["valor"]["quartis_reais"][1] / r["dm_valor"])
    return {
        "procedencia_brier": media(brier), "n_procedencia": len(brier),
        "degraus": {g: graus.count(g) / len(graus) for g in R.DEGRAUS},
        "prazo_mae_dias": media(err_p), "prazo_cobertura_p25_p75": media(cob),
        "n_prazo": len(err_p),
        "dm_concessao_brier": media(brier_dm), "n_dm_concessao": len(brier_dm),
        "dm_valor_erro_log2_mediano": statistics.median(abs(math.log2(x)) for x in razoes),
        "dm_valor_dentro_de_50pct": media([0.5 <= x <= 1.5 for x in razoes]),
        "n_dm_valor": len(razoes),
    }


def main() -> None:
    base = [json.loads(l) for l in BASE.read_text().splitlines()]
    orig = dict(R.PISO_N)
    out = {"baseline_sem_classe": avaliar(base, None)}
    for piso in (10, 20, 30, 50, 80):
        out[f"piso_{piso}"] = avaliar(base, piso)
    R.PISO_N.update(orig)
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    b = out["baseline_sem_classe"]
    print(f"{'':22}{'Brier proc':>11}{'MAE prazo':>11}{'cob p25-75':>11}"
          f"{'Brier DM':>10}{'erro valor':>11}{'±50%':>7}   degraus (classe/grupo/piso)")
    for nome, x in out.items():
        g = x["degraus"]
        print(f"{nome:22}{x['procedencia_brier']:>11.4f}{x['prazo_mae_dias']:>11.0f}"
              f"{x['prazo_cobertura_p25_p75']:>11.1%}{x['dm_concessao_brier']:>10.4f}"
              f"{x['dm_valor_erro_log2_mediano']:>11.2f}{x['dm_valor_dentro_de_50pct']:>7.0%}"
              f"   {g['classe']:.0%}/{g['grupo']:.0%}/{g['piso']:.0%}")
    print(f"\nn: procedência {b['n_procedencia']}, prazo {b['n_prazo']}, "
          f"concessão DM {b['n_dm_concessao']}, valor DM {b['n_dm_valor']}")
    print("erro valor = |log2(previsto/real)| mediano: 1,0 quer dizer errar por um fator 2")


if __name__ == "__main__":
    main()
