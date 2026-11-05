from conferir import tramitacao


def test_tramitacao_conta_do_ajuizamento_e_avisa_da_redistribuicao(processo):
    assert tramitacao(processo) == "539 dias (redistribuído em 20/06/2025)"


def test_tramitacao_sem_redistribuicao_e_so_o_numero(processo):
    processo["capa"]["distribuicao"] = "13/03/2025 às 09:00 - Livre"
    assert tramitacao(processo) == "539 dias"


def test_tramitacao_sem_movimentacoes_nao_estoura(processo):
    processo["movimentacoes"] = []
    assert tramitacao(processo) == "?"
