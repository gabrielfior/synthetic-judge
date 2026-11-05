import datetime as dt

from sj import cnj

FORO = "0320"
# 60 números do bloco digital de 2024, sequências de 1000001 a 1018000
NUMEROS = [f"{1000001 + i * 288:07d}-11.2024.8.26.{FORO}" for i in range(60)]


def test_decompor():
    assert cnj.decompor("1002364-64.2025.8.26.0320") == (1002364, 2025, "0320")
    assert cnj.decompor("nao-e-um-numero") is None


def test_bloco_digital_separa_o_legado():
    assert cnj.e_digital("1002364-64.2025.8.26.0320")
    assert not cnj.e_digital("0017476-37.2018.8.26.0320")   # legado físico


def test_faixas_exige_observacoes_suficientes():
    assert cnj.faixas(NUMEROS[:5]) == {}                     # menos que MIN_OBS
    assert cnj.faixas(NUMEROS)[(FORO, 2024)] == (1000001, 1016993)


def test_distribuicao_interpola_dentro_do_ano():
    f = cnj.faixas(NUMEROS)
    assert cnj.distribuicao(NUMEROS[0], f) == dt.date(2024, 1, 1)
    assert cnj.distribuicao(NUMEROS[-1], f) == dt.date(2024, 12, 30)
    meio = cnj.distribuicao(NUMEROS[30], f)
    assert dt.date(2024, 6, 1) < meio < dt.date(2024, 8, 1)


def test_legado_nao_estima():
    """O bloco 0xxxxxx é numeração paralela; estimar por ele daria data errada."""
    f = cnj.faixas(NUMEROS)
    assert cnj.distribuicao("0017476-37.2024.8.26.0320", f) is None


def test_tramitacao_recusa_sentenca_anterior_a_distribuicao():
    f = cnj.faixas(NUMEROS)
    assert cnj.tramitacao(NUMEROS[-1], dt.date(2024, 1, 5), f) is None
    assert cnj.tramitacao(NUMEROS[0], dt.date(2024, 7, 1), f) == 182
