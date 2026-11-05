from datetime import date, timedelta

import pytest

from sj import decisao as D


def casos():
    out = []
    for i in range(40):  # Limeira, um por dia
        out.append({"id": f"L{i}|d", "processo": f"L{i}", "data": date(2025, 1, 1) + timedelta(i),
                    "comarca": "Limeira", "resultado": "procedente"})
    for i in range(10):  # outro foro, antes e depois do corte
        out.append({"id": f"S{i}|d", "processo": f"S{i}", "data": date(2024, 6, 1) + timedelta(i),
                    "comarca": "SB", "resultado": "improcedente"})
        out.append({"id": f"T{i}|d", "processo": f"T{i}", "data": date(2025, 12, 1) + timedelta(i),
                    "comarca": "SB", "resultado": "improcedente"})
    # outro documento de um processo do teste, anterior ao corte
    out.append({"id": "L39|antigo", "processo": "L39", "data": date(2025, 1, 1),
                "comarca": "Limeira", "resultado": "procedente"})
    return out


def test_teste_sao_os_mais_recentes_do_foro_alvo():
    conj, man = D.dividir(casos())
    teste = {i for i, c in conj.items() if c == "teste"}
    assert len(teste) == 8 and {f"L{i}|d" for i in range(32, 40)} == teste
    assert man["corte"] == "2025-02-02"


def test_nada_posterior_ao_corte_nem_do_processo_do_teste_vaza():
    cs = casos()
    conj, man = D.dividir(cs)
    corte = date.fromisoformat(man["corte"])
    por_id = {c["id"]: c for c in cs}
    proc_teste = {por_id[i]["processo"] for i, c in conj.items() if c == "teste"}
    for i, c in conj.items():
        if c != "teste":
            assert por_id[i]["data"] < corte
            assert por_id[i]["processo"] not in proc_teste
    assert "L39|antigo" not in conj  # mesmo processo do teste
    assert not any(i.startswith("T") for i in conj)  # outro foro, depois do corte


def test_outro_foro_anterior_ao_corte_so_entra_no_treino():
    conj, _ = D.dividir(casos())
    assert {conj[f"S{i}|d"] for i in range(10)} == {"treino"}


def test_validacao_e_so_do_foro_alvo_e_a_divisao_e_estavel():
    cs = casos()
    a, _ = D.dividir(cs)
    b, _ = D.dividir(list(reversed(cs)))
    assert a == b
    assert all(i.startswith("L") for i, c in a.items() if c == "val")


def test_metricas_do_previsor_perfeito():
    pares = [("procedente", "procedente", 0.9), ("improcedente", "improcedente", 0.1),
             ("parcialmente_procedente", "parcialmente_procedente", 0.8)]
    m = D.metricas(pares)
    assert m["resultado"] == m["procedencia"] == 1.0 and m["ordinal"] == 0.0
    assert m["brier"] == pytest.approx((0.01 + 0.01 + 0.04) / 3)


def test_extinto_fica_fora_da_procedencia_e_do_ordinal_mas_conta_no_resultado():
    m = D.metricas([("extinto_sem_merito", "procedente", 0.9),
                    ("procedente", "procedente", 0.9)])
    assert m["resultado"] == 0.5 and m["procedencia"] == 1.0 and m["n_merito"] == 1
    assert m["extinto_n"] == 1 and m["extinto_recall"] == 0.0


def test_sem_decisao_erra_em_tudo():
    m = D.metricas([("procedente", None, None), ("improcedente", None, None)])
    assert m["resultado"] == 0.0 and m["procedencia"] == 0.0 and m["ordinal"] == 1.0


def test_parcial_por_procedente_e_meio_ponto_na_ordinal_e_acerta_a_procedencia():
    m = D.metricas([("procedente", "parcialmente_procedente", None)])
    assert m["ordinal"] == 0.5 and m["procedencia"] == 1.0 and m["resultado"] == 0.0


def test_p_procedencia_e_moda():
    d = {"procedente": 6, "parcialmente_procedente": 2, "improcedente": 2, "extinto_sem_merito": 90}
    assert D.p_procedencia(d) == 0.8 and D.moda(d) == "extinto_sem_merito"
    assert D.p_procedencia({"extinto_sem_merito": 3}) is None
