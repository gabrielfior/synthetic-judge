from datetime import date

from sj.datas import (ajuizamento, dias, distribuicao_estimada, inicio, iso,
                      parse_data, redistribuicao, sentenca)


def test_parse_data_do_formato_das_movimentacoes():
    assert parse_data("06/09/2026") == date(2026, 9, 6)


def test_parse_data_ignora_a_cauda_da_distribuicao_da_capa():
    assert parse_data("24/02/2025 às 16:12 - Livre") == date(2025, 2, 24)


def test_parse_data_deixa_passar_a_date_que_o_parquet_ja_entrega():
    assert parse_data(date(2025, 3, 8)) == date(2025, 3, 8)


def test_parse_data_devolve_none_no_lugar_de_estourar():
    assert parse_data("") is None
    assert parse_data(None) is None
    assert parse_data("sem data") is None


def test_ajuizamento_e_a_movimentacao_mais_antiga_nao_a_capa(processo):
    """A `distribuicao` da capa marca a chegada nesta vara, não o ajuizamento."""
    assert ajuizamento(processo) == date(2025, 3, 12)


def test_redistribuicao_aparece_quando_a_capa_esta_muito_depois(processo):
    assert redistribuicao(processo) == date(2025, 6, 20)


def test_sem_redistribuicao_a_capa_bate_com_a_primeira_movimentacao(processo):
    processo["capa"]["distribuicao"] = "13/03/2025 às 09:00 - Livre"
    assert redistribuicao(processo) is None


def test_dias_entre_duas_datas():
    assert dias(date(2025, 3, 12), date(2026, 9, 2)) == 539


def test_dias_com_data_faltando():
    assert dias(None, date(2026, 9, 2)) is None


def test_iso_normaliza_para_a_ordem_que_a_llm_le_sem_ambiguidade():
    assert iso("12/03/2025") == "2025-03-12"
    assert iso("") == ""


def test_sentenca_aceita_a_coluna_data_do_parquet(julgado):
    """No JSON o campo é `data_de_disponibilização`; no Parquet é `data`."""
    assert sentenca(julgado) == date(2026, 9, 2)


def test_distribuicao_estimada_e_lida_nunca_recalculada(julgado):
    """A estimativa do `sj.cnj` ancora a interpolação no conjunto inteiro que foi
    gravado. Recalculá-la numa fatia dá outro número — por isso ela é coluna."""
    assert distribuicao_estimada(julgado) == date(2025, 3, 8)


def test_sem_a_coluna_nao_ha_estimativa(processo):
    """O JSON do fetch_juiz.py não passa pelo cnj: 10 processos não ancoram nada."""
    assert distribuicao_estimada(processo) is None


def test_inicio_prefere_a_data_exata_a_estimada(processo):
    assert inicio(processo) == (date(2025, 3, 12), "movimentacao")


def test_inicio_cai_na_estimativa_quando_nao_ha_cpopg(julgado):
    assert inicio(julgado) == (date(2025, 3, 8), "cnj")


def test_inicio_sem_nenhuma_das_duas():
    assert inicio({"processo": "x"}) == (None, "")


def test_a_estimativa_nao_e_a_distribuicao_da_capa(processo, julgado):
    """Mesmo nome, coisas diferentes: a da capa é a chegada NESTA vara
    (redistribuição), a do Parquet é o ajuizamento original estimado."""
    processo["distribuicao"] = julgado["distribuicao"]
    assert redistribuicao(processo) == date(2025, 6, 20)
    assert distribuicao_estimada(processo) == date(2025, 3, 8)
