import pytest
from sj.features import features

def sentenca(relatorio, dispositivo, **kw):
    texto = f"SENTENÇA\n{relatorio}\nÉ o relatório.\nFundamento.\nAnte o exposto, {dispositivo}"
    return {"processo": "1002364-64.2025.8.26.0320", "classe": "Procedimento Comum Cível",
            "assunto": "Indenização por Dano Moral", "texto": texto,
            "relatorio": f"SENTENÇA\n{relatorio}\nÉ o relatório.",
            "fundamentacao": "Fundamento.",
            "dispositivo": f"Ante o exposto, {dispositivo}", **kw}

def test_extrai_o_valor_pedido_do_relatorio():
    d = sentenca("Pede indenização por danos morais no valor de R$ 20.000,00.",
                 "julgo procedente e condeno a ré a pagar R$ 8.000,00 a título de danos morais.")
    f = features(d)
    assert f["valor_dano_moral_pedido"] == 20000.0
    assert f["valor_dano_moral"] == 8000.0
    assert f["razao_dano_moral"] == 0.4

def test_ordem_invertida_do_pedido():
    d = sentenca("Requer R$ 15.000,00 a título de danos morais.",
                 "julgo procedente e condeno ao pagamento de R$ 15.000,00 por danos morais.")
    assert features(d)["valor_dano_moral_pedido"] == 15000.0
    assert features(d)["razao_dano_moral"] == 1.0

def test_proximidade_solta_nao_conta_como_pedido():
    """'moral' perto de um R$ qualquer pega outro número e infla a razão."""
    d = sentenca("Alega negativação. Contratou empréstimo de R$ 3.000,00 e sofreu danos morais.",
                 "julgo procedente e condeno a ré a pagar R$ 8.000,00 a título de danos morais.")
    assert features(d)["valor_dano_moral_pedido"] is None
    assert features(d)["razao_dano_moral"] is None

def test_ultra_petita_e_erro_de_extracao():
    """Juiz não concede mais do que se pediu; quando aparece, a razão é descartada."""
    d = sentenca("Pede danos morais no valor de R$ 2.000,00.",
                 "julgo procedente e condeno a ré a pagar R$ 8.000,00 a título de danos morais.")
    f = features(d)
    assert f["valor_dano_moral_pedido"] == 2000.0   # os dois valores ficam
    assert f["valor_dano_moral"] == 8000.0
    assert f["razao_dano_moral"] is None            # só a razão é recusada

def test_sem_pedido_de_valor():
    d = sentenca("Pede indenização por danos morais a ser arbitrada.",
                 "julgo procedente e condeno a ré a pagar R$ 8.000,00 a título de danos morais.")
    assert features(d)["valor_dano_moral_pedido"] is None
    assert features(d)["razao_dano_moral"] is None
