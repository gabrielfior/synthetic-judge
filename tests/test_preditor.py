import json

import pytest

from sj import preditor as P

CASO = {"id": "1|d", "processo": "1", "relatorio": "O autor pede a restituição. O réu contestou.",
        "classe": "Cobrança", "grupo": "Crédito", "resultado": "procedente"}
TREINO = [{"id": f"t{i}|d", "processo": f"t{i}", "relatorio": f"Cobrança de dívida {i}",
           "classe": "Cobrança", "grupo": "Crédito",
           "resultado": "procedente" if i % 2 else "improcedente", "dm_concedido": False}
          for i in range(20)]


def test_ler_normaliza_e_aceita_o_json_embrulhado():
    p = P.ler('```json\n{"procedente": 6, "parcialmente_procedente": 2, '
              '"improcedente": 2, "extinto_sem_merito": 0}\n```')
    assert p["procedente"] == pytest.approx(0.6) and sum(p.values()) == pytest.approx(1)
    assert P.previsao(p) == "procedente"


@pytest.mark.parametrize("ruim", ["", "sem json", "{}", '{"procedente": -1, "improcedente": 2}'])
def test_resposta_ilegivel_levanta_em_vez_de_virar_previsao(ruim):
    with pytest.raises(ValueError):
        P.ler(ruim)


def test_empate_vai_para_o_resultado_mais_comum_da_lista():
    p = {"procedente": 0.4, "parcialmente_procedente": 0.1, "improcedente": 0.4,
         "extinto_sem_merito": 0.1}
    assert P.previsao(p) == "procedente"


def test_notas_de_um_acerto_e_de_um_extinto_previsto_em_caso_de_merito():
    ok, _ = P.notas("procedente", {"procedente": .8, "parcialmente_procedente": .1,
                                   "improcedente": .05, "extinto_sem_merito": .05})
    assert ok["resultado"] == 1.0 and ok["procedencia"] == 1.0 and ok["ordinal"] == 1.0
    assert ok["brier"] == pytest.approx((0.9 / 0.95 - 1) ** 2, abs=1e-6)
    ext, _ = P.notas("procedente", {"procedente": .1, "parcialmente_procedente": .1,
                                    "improcedente": .1, "extinto_sem_merito": .7})
    assert ext["resultado"] == 0.0 and ext["procedencia"] == 0.0 and ext["ordinal"] == 0.0


def test_caso_extinto_nao_tem_procedencia_nem_brier():
    n, _ = P.notas("extinto_sem_merito", {"procedente": .1, "parcialmente_procedente": .1,
                                          "improcedente": .1, "extinto_sem_merito": .7})
    assert n == {"resultado": 1.0}


def test_prior_usa_a_classe_quando_ha_casos_e_cai_para_o_grupo_e_o_juizo():
    assert "Cobrança" in P.texto_prior(CASO, TREINO)
    sem_classe = {**CASO, "classe": "Outra", "grupo": "Crédito"}
    assert "Neste grupo" in P.texto_prior(sem_classe, TREINO)
    sem_nada = {**CASO, "classe": None, "grupo": None}
    assert P.texto_prior(sem_nada, TREINO).startswith("Em 20 sentenças")


def test_montar_so_liga_o_que_a_variante_pede():
    base = P.montar(CASO, {}, treino=TREINO)
    assert base.startswith("Relatório do caso a decidir") and "sentenças deste juiz" not in base
    com = P.montar(CASO, {"prior": True, "lr": True}, treino=TREINO,
                   vizinhos=TREINO[:2], lr={"procedente": .5, "parcialmente_procedente": .2,
                                            "improcedente": .2, "extinto_sem_merito": .1},
                   n_treino=20)
    assert "Casos parecidos" in com and "sentenças deste juiz" in com and "modelo estatístico" in com
    assert com.rstrip().endswith(CASO["relatorio"])


def test_recuperador_nao_devolve_o_mesmo_processo():
    pool = TREINO + [{**CASO, "id": "1|outro", "relatorio": CASO["relatorio"]}]
    r = P.Recuperador(pool)
    viz = r.vizinhos(CASO, 5)
    assert len(viz) == 5 and all(v["processo"] != "1" for v in viz)
