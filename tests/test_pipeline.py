import pytest

from sj import pipeline

TAX = [{"nome": "A", "definicao": "x", "grupo": "G"},
       {"nome": "B", "definicao": "y", "grupo": "G"}]


def _base():
    return [{"id": f"c{i}", "processo": f"p{i}", "data": "2025-03-01",
             "classe": "A" if i < 40 else "B", "grupo": "G", "procedente": i % 2,
             "dias": 300, "dm_pedido": True, "dm_concedido": i % 2 == 0,
             "dm_valor": 5000.0 if i % 2 == 0 else None, "dm_razao": None,
             "url_pdf": f"http://x/{i}", "resultado": "procedente"} for i in range(60)]


class Dubla:
    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def __call__(self, system, user):
        self.chamadas.append((system, user))
        return self.resposta


def test_classe_informada_dispensa_a_llm():
    d = Dubla("não deveria ser chamada")
    r = pipeline.prognosticar({"classe": "A"}, _base(), TAX, d)
    assert d.chamadas == [] and r["estruturada"].classe == "A"
    assert r["resultado"]["procedencia"]["degrau"] == "classe"


def test_texto_livre_passa_pela_llm_e_o_advogado_sobrepoe_o_dano_moral():
    d = Dubla('{"classe": "B", "pede_dano_moral": true, "motivo": "m"}')
    r = pipeline.prognosticar({"texto": "descrição", "pede_dano_moral": False},
                              _base(), TAX, d)
    assert len(d.chamadas) == 1 and d.chamadas[0][1] == "descrição"
    assert r["estruturada"].classe == "B"
    assert r["estruturada"].pede_dano_moral is False        # o do advogado vence
    assert "Dano moral" not in r["dossie"]
    assert r["resultado"]["procedencia"]["degrau"] == "grupo"  # B tem 20 < 30


def test_llm_devolve_classe_invalida_cai_no_piso():
    r = pipeline.prognosticar({"texto": "x"}, _base(), TAX, Dubla('{"classe": "Z"}'))
    assert r["estruturada"].classe is None
    assert r["resultado"]["procedencia"]["degrau"] == "piso"
    assert "não identificada" in r["dossie"]


def test_sem_texto_nem_classe_e_o_piso_e_nao_chama_llm():
    d = Dubla("x")
    r = pipeline.prognosticar({}, _base(), TAX, d)
    assert d.chamadas == [] and r["resultado"]["consulta"]["classe"] is None


def test_classe_desconhecida_levanta():
    with pytest.raises(ValueError, match="desconhecida"):
        pipeline.prognosticar({"classe": "Z"}, _base(), TAX, None)


def test_texto_sem_cliente_levanta_em_vez_de_ignorar():
    with pytest.raises(ValueError, match="nenhum cliente"):
        pipeline.prognosticar({"texto": "x"}, _base(), TAX, None)
