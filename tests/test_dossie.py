from sj.dossie import dossie
from sj.estruturar import Estruturada
from sj.referencia import Consulta, prognosticar


def _base():
    b = []
    for i in range(60):
        b.append({"id": f"c{i}", "processo": f"p{i}", "data": f"2025-02-{i % 28 + 1:02}",
                  "classe": "A" if i < 40 else "B", "grupo": "G", "procedente": int(i % 3 > 0),
                  "dias": 200 + i, "dm_pedido": True, "dm_concedido": i % 2 == 0,
                  "dm_valor": 6000.0 if i % 2 == 0 else None, "dm_razao": None,
                  "url_pdf": f"http://x/{i}", "resultado": "procedente"})
    return b


def test_dossie_traz_n_e_degrau_em_cada_numero():
    base = _base()
    r = prognosticar(base, Consulta("A", "G"))
    t = dossie("texto do advogado", Estruturada("A", ["B"], True, "motivo"), r)
    assert "classe: **A**" in t and "também plausível: B" in t
    assert t.count("n=") >= 3                       # procedência, prazo, dano moral
    assert "na classe «A»" in t
    assert "confira" in t.lower() and "aconselhamento jurídico" in t


def test_dossie_diz_quando_desceu():
    r = prognosticar(_base(), Consulta("B", "G"))   # B tem 20 casos < 30
    t = dossie(None, Estruturada("B", [], None, ""), r)
    assert "no grupo de classes «G»" in t and "não tinha casos suficientes" in t


def test_dossie_omite_dano_moral_quando_nao_pede():
    r = prognosticar(_base(), Consulta("A", "G"))
    assert "Dano moral" not in dossie(None, Estruturada("A", [], False, ""), r)
    assert "Dano moral" in dossie(None, Estruturada("A", [], None, ""), r)


def test_dossie_sem_classe_avisa_que_e_o_numero_do_juizo():
    r = prognosticar(_base(), Consulta())
    t = dossie("vago", Estruturada(None, [], None, "vago"), r)
    assert "não identificada" in t and "todo o Procedimento Comum" in t


def test_texto_em_portugues_sem_contracao_errada_nem_ponto_decimal():
    r = prognosticar(_base(), Consulta("B", "G"))
    t = dossie("x", Estruturada("B", [], True, ""), r)
    for errado in ("em a classe", "em o grupo", "a o caso"):
        assert errado not in t
    assert "meses" in t and ". " not in t.split("mediana ")[1].split(" meses")[0] and "," in t.split("mediana ")[1][:6]
