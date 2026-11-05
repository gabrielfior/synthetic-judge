import pytest

from sj.referencia import (Consulta, comparaveis, dano_moral, descer, prazo,
                           procedencia, prognosticar, quantis, wilson)


def _r(i, classe, grupo, procedente=1, dias=200, **kw):
    base = {"id": f"c{i}", "processo": f"p{i}", "data": f"2025-01-{i % 28 + 1:02}",
            "classe": classe, "grupo": grupo, "procedente": procedente, "dias": dias,
            "dm_pedido": False, "dm_concedido": False, "dm_valor": None,
            "dm_razao": None, "url_pdf": f"http://x/{i}", "resultado": "procedente"}
    return base | kw


def _base():
    """A: 40 casos, 10% procedentes; B: 5 casos; mesmo grupo G; C: outro grupo."""
    A = [_r(i, "A", "G", int(i < 4)) for i in range(40)]
    B = [_r(100 + i, "B", "G", 1) for i in range(5)]
    C = [_r(200 + i, "C", "H", 1) for i in range(40)]
    return A + B + C


def test_wilson_nao_degenera_nos_extremos():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0.2 < hi < 0.4
    assert wilson(0, 0) == (0.0, 1.0)


def test_quantis():
    assert quantis([1, 2, 3, 4, 5]) == [2.0, 3.0, 4.0]
    assert quantis([10]) == [10.0, 10.0, 10.0]
    assert quantis([]) == []


def test_fica_na_classe_quando_tem_casos():
    r = procedencia(_base(), Consulta("A", "G"))
    assert (r["degrau"], r["n"], r["desceu"], r["insuficiente"]) == ("classe", 40, False, False)
    assert r["probabilidade"] == pytest.approx(0.1)


def test_desce_ao_grupo_e_declara():
    r = procedencia(_base(), Consulta("B", "G"))  # B tem 5 < 30; o grupo G tem 45
    assert (r["degrau"], r["n"], r["desceu"]) == ("grupo", 45, True)


def test_desce_ao_piso_sem_classe():
    r = procedencia(_base(), Consulta())
    assert (r["degrau"], r["n"], r["desceu"]) == ("piso", 85, False)


def test_sem_classe_mas_com_grupo_comeca_no_grupo():
    r = procedencia(_base(), Consulta(grupo="H"))
    assert (r["degrau"], r["desceu"]) == ("grupo", False)


def test_piso_insuficiente_e_declarado():
    r = procedencia(_base()[:10], Consulta("A", "G"))
    assert r["degrau"] == "piso" and r["n"] == 10 and r["insuficiente"] is True


def test_excluir_tira_o_proprio_caso():
    base = _base()
    r = procedencia(base, Consulta("A", "G"), excluir="c0")  # c0 é procedente
    assert r["n"] == 39
    assert r["probabilidade"] == pytest.approx(3 / 39)


def test_casos_sem_resultado_nao_contam_no_n():
    base = [_r(i, "A", "G", None) for i in range(50)] + [_r(100 + i, "A", "G", 1) for i in range(10)]
    r = procedencia(base, Consulta("A", "G"))
    assert r["degrau"] == "piso" or r["n"] == 10  # só 10 têm resultado: abaixo de 30
    assert r["n"] == 10 and r["insuficiente"]


def test_prazo_quartis():
    base = [_r(i, "A", "G", dias=100 + i) for i in range(40)]
    r = prazo(base, Consulta("A", "G"))
    assert r["degrau"] == "classe" and r["quartis_dias"][1] == pytest.approx(119.5)


def test_dano_moral_so_conta_quem_pede():
    base = ([_r(i, "A", "G", dm_pedido=True, dm_concedido=i < 6, dm_valor=5000.0 if i < 6 else None)
             for i in range(20)]
            + [_r(100 + i, "A", "G") for i in range(30)])  # não pedem: fora da concessão
    r = dano_moral(base, Consulta("A", "G"))
    assert r["concessao"]["n"] == 20 and r["concessao"]["degrau"] == "classe"
    assert r["concessao"]["probabilidade_concessao"] == pytest.approx(0.3)
    # só 6 concessões com valor, em toda a base: nenhum degrau chega a 15
    assert r["valor"]["n"] == 6 and r["valor"]["insuficiente"] is True


def test_valor_desce_enquanto_a_concessao_fica():
    pedem = [_r(i, "A", "G", dm_pedido=True, dm_concedido=i < 3,
                dm_valor=4000.0 if i < 3 else None) for i in range(20)]
    outros = [_r(100 + i, "B", "G", dm_pedido=True, dm_concedido=True, dm_valor=8000.0)
              for i in range(20)]
    r = dano_moral(pedem + outros, Consulta("A", "G"))
    assert r["concessao"]["degrau"] == "classe"          # 20 >= 15
    assert r["valor"]["degrau"] == "grupo"               # 3 < 15; o grupo tem 23
    assert r["valor"]["quartis_reais"][1] == pytest.approx(8000.0)


def test_comparaveis_pega_os_mais_recentes_da_classe():
    base = _base()
    cs = comparaveis(base, Consulta("A", "G"), k=3)
    assert len(cs) == 3 and all(c["degrau"] == "classe" for c in cs)
    assert [c["data"] for c in cs] == sorted((c["data"] for c in cs), reverse=True)


def test_comparaveis_sobe_ao_grupo_se_a_classe_nao_tem():
    assert comparaveis(_base(), Consulta("Z", "H"))[0]["degrau"] == "grupo"
    assert comparaveis(_base(), Consulta()) == []


def test_prognosticar_junta_os_eixos():
    out = prognosticar(_base(), Consulta("A", "G"))
    assert set(out) == {"consulta", "procedencia", "prazo", "dano_moral", "comparaveis"}
