import pytest

from sj import sentenca as S

REL = "O autor pede dano moral de R$ 10.000,00. O réu contestou. É o relatório."
SINT = ("FUNDAMENTO E DECIDO. Aplica-se o art. 14 do CDC e o art. 186 do Código "
        "Civil. Ante o exposto, JULGO PARCIALMENTE PROCEDENTE o pedido para "
        "condenar o réu a pagar R$ 5.000,00 a título de danos morais.")


def test_extrair_le_resultado_dano_moral_e_artigos():
    e = S.extrair(REL, SINT)
    assert e["parseavel"] and e["resultado"] == "parcialmente_procedente"
    assert e["dm_concedido"] and e["dm_valor"] == 5000.0
    assert "14" in " ".join(e["artigos"])


def test_sem_dispositivo_nao_e_parseavel():
    e = S.extrair(REL, "Não sei.")
    assert not e["parseavel"] and e["resultado"] is None


def real(**kw):
    return {"resultado": "parcialmente_procedente", "dm_concedido": True,
            "dm_valor": 5000.0, "artigos": ["14", "186"], **kw}


def test_notas_por_regra_oraculo_nota_tudo():
    notas, _ = S.notas_por_regra(real(), real())
    assert notas == {"resultado": 1.0, "dm_concedido": 1.0, "dm_valor": 1.0,
                     "artigos": 1.0}


def test_valor_fora_de_50_por_cento_zera_e_dentro_acerta():
    fora, _ = S.notas_por_regra(real(), real(dm_valor=8000.0))
    dentro, _ = S.notas_por_regra(real(), real(dm_valor=7400.0))
    assert fora["dm_valor"] == 0.0 and dentro["dm_valor"] == 1.0


def test_item_que_nao_se_aplica_fica_de_fora_e_nao_vira_zero():
    notas, _ = S.notas_por_regra(real(dm_valor=None, artigos=[]),
                                 real(dm_valor=None, artigos=[]))
    assert "dm_valor" not in notas and "artigos" not in notas


def test_nao_conceder_quando_o_real_concedeu_zera_o_valor():
    notas, _ = S.notas_por_regra(real(), real(dm_concedido=False, dm_valor=None))
    assert notas["dm_concedido"] == 0.0 and notas["dm_valor"] == 0.0


def test_artigos_e_a_fracao_dos_citados_no_real():
    notas, _ = S.notas_por_regra(real(), real(artigos=["14"]))
    assert notas["artigos"] == 0.5


def test_ordem_ab_e_estavel_e_varia():
    assert S.ordem_ab("x|1", 0) == S.ordem_ab("x|1", 0)
    assert len({S.ordem_ab(f"c{i}", 0) for i in range(40)}) == 2


def test_b1_nao_rotula_qual_e_a_real():
    p = S.pergunta_b1("rel", "TEXTO_REAL", "TEXTO_SINT", True)
    assert p.index("TEXTO_SINT") < p.index("TEXTO_REAL")
    assert "real" not in p.lower().replace("texto_real", "")
    p2 = S.pergunta_b1("rel", "TEXTO_REAL", "TEXTO_SINT", False)
    assert p2.index("TEXTO_REAL") < p2.index("TEXTO_SINT")


def test_b2_pergunta_contradicao_e_nao_fato_novo():
    p = S.pergunta_b2("rel", "TEXTO_SINT")
    assert "contradiz" in p and "não é contradição" in p


def test_detalhes_novos_conta_o_que_o_relatorio_nao_traz():
    rel = "O autor foi negativado em 10/03/2020 em R$ 500,00."
    assert S.detalhes_novos(rel, "negativado em 10/03/2020, R$ 500,00") == 0
    assert S.detalhes_novos(rel, "em 11/03/2020, R$ 500,00, fls. 12 e 15 de maio de 2021") == 3


def test_b2_nao_ve_a_sentenca_real_e_b3_so_ve_a_sintetica():
    assert "TEXTO_REAL" not in S.pergunta_b2("rel", "TEXTO_SINT")
    assert "rel" not in S.pergunta_b3("TEXTO_SINT").replace("relat", "")


def test_ler_veredito():
    assert S.ler_veredito('```json\n{"sim": true, "motivo": "ok"}\n```') == (True, "ok")
    assert S.ler_veredito('{"sim": false}') == (False, "")


@pytest.mark.parametrize("ruim", ["", "talvez", '{"sim": "sim"}', "{}"])
def test_veredito_ilegivel_levanta_em_vez_de_virar_nao(ruim):
    with pytest.raises(ValueError):
        S.ler_veredito(ruim)


def test_wilson():
    lo, hi = S.wilson(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert S.wilson(0, 0) == (0.0, 1.0)


def test_ler_b1_confere_a_citacao():
    a = "O art. 344 do CPC presume verdadeiros os fatos não contestados."
    b = "Houve revelia, de modo que se presumem verdadeiros os fatos alegados."
    ok = ('{"sim": true, "razao_a": "presume verdadeiros os fatos não contestados", '
          '"razao_b": "se presumem verdadeiros os fatos alegados", "motivo": "m"}')
    assert S.ler_b1(ok, a, b) == (True, "m")


def test_ler_b1_citacao_inventada_vira_nao():
    inventada = ('{"sim": true, "razao_a": "a abusividade do reajuste por idade", '
                 '"razao_b": "se presumem verdadeiros os fatos alegados", "motivo": "m"}')
    sim, motivo = S.ler_b1(inventada, "JULGO PROCEDENTE a ação.",
                           "se presumem verdadeiros os fatos alegados")
    assert not sim and "razao_a" in motivo
