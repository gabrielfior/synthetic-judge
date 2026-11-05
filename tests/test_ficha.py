from sj.ficha import ficha, ficha_censurada, secoes


def test_secoes_reparticionam_o_texto_sem_perder_nada(processo):
    """Relatório e fundamentação vêm do split de sj.tjsp, que corta o dispositivo
    cedo demais. Repartindo pelo último marcador, o trecho entre os dois
    marcadores fica na fundamentação em vez de sumir."""
    relatorio, fundamentacao, dispositivo = secoes(processo["texto"])
    assert relatorio.startswith("SENTENÇA")
    # O FIM_RELATORIO de sj.tjsp casa a frase e deixa o ponto final para o
    # trecho seguinte; o que importa aqui é que nada se perca no caminho.
    assert relatorio.rstrip().endswith("É o relatório")
    assert "Portanto, julgo improcedente a reconvenção" in fundamentacao
    assert dispositivo.startswith("Ante o exposto")
    assert len(relatorio) + len(fundamentacao) + len(dispositivo) >= len(
        processo["texto"]) - 4  # só os strips de borda


def test_cabecalho_da_ficha(processo):
    linhas = ficha(processo).splitlines()
    assert linhas[0] == "# 1000000-00.2025.8.26.0320"
    assert linhas[1] == "Procedimento Comum Cível — Cobrança de Aluguéis - Sem despejo"
    assert linhas[2] == "4ª Vara Cível · Foro de Limeira · Juiz Sintético de Teste"
    assert linhas[3] == "Valor da causa: R$ 48.320,00"
    assert linhas[4] == ("Ajuizado 2025-03-12 · redistribuído em 2025-06-20 · "
                         "Sentenciado 2026-09-02 · 539 dias · 17 movimentações")


def test_cabecalho_do_parquet_marca_a_data_como_estimada(julgado):
    """O til e a nota de origem existem para que ninguém leia 2025-03-08 como
    data de ajuizamento: é interpolação do número CNJ, p90 de 35 dias de erro."""
    linhas = ficha(julgado).splitlines()
    assert linhas[3] == ("Distribuído ~2025-03-08 (estimado do nº CNJ) · "
                         "Sentenciado 2026-09-02 · ~543 dias")


def test_a_ficha_do_parquet_nao_finge_ter_o_que_nao_tem(julgado):
    f = ficha(julgado)
    assert "Ajuizado" not in f
    assert "## Partes" not in f
    assert "## Marcos" not in f
    assert "## Dispositivo" in f


def test_a_censurada_do_parquet_nao_deixa_calcular_a_data_da_sentenca(julgado):
    """Distribuição estimada + dias de tramitação devolvem a data da sentença."""
    f = ficha_censurada(julgado)
    assert "Distribuído ~2025-03-08" in f
    assert "543" not in f
    assert "2026-09-02" not in f


def test_cabecalho_avisa_da_redistribuicao(processo):
    assert "redistribuído em 2025-06-20" in ficha(processo)


def test_o_cartorio_vira_contagem_e_nao_linha(processo):
    f = ficha(processo)
    assert "1 publicações" in f and "1 conclusões" in f
    assert "Certidão de Publicação Expedida" not in f
    assert "Conclusos para Despacho" not in f


def test_partes_com_advogados(processo):
    f = ficha(processo)
    assert "Reqte: Autora Sintética — adv. Advogado Sintético" in f
    assert "Reqda: Ré Sintética Ltda — adv. Advogada Sintética" in f


def test_marcos_sao_a_linha_do_tempo_comprimida(processo):
    marcos = ficha(processo).split("## Marcos\n")[1].split("\n\n")[0].splitlines()
    assert marcos[0] == "2025-03-12  distribuicao"
    assert marcos[-1] == "2026-09-02  sentenca"
    assert len(marcos) == 10


def test_o_detalhe_do_marco_e_truncado(processo):
    """No 1014337-65.2015 o `detalhe` de uma decisão traz o ato inteiro; um marco
    é uma linha, não um bloco de texto."""
    processo["movimentacoes"][7]["detalhe"] = "Defiro a perícia. " * 40
    marco = next(linha for linha in ficha(processo).splitlines()
                 if linha.startswith("2026-03-20"))
    assert len(marco) <= 160
    assert marco.endswith("…)")


def test_o_detalhe_so_acompanha_o_evento_que_decide(processo):
    """O `detalhe` de uma citação ou emenda é metadado de máquina — número de
    protocolo, código de AR, nome do oficial. Só o de um ato decisório informa."""
    processo["movimentacoes"][12]["detalhe"] = "Juntada de AR : AA79 Situação : ok"
    f = ficha(processo)
    assert "2025-04-02  citacao\n" in f
    assert "AA79" not in f


def test_as_tres_secoes_da_sentenca_estao_na_ficha(processo):
    f = ficha(processo)
    assert "## Relatório" in f and "## Fundamentação" in f and "## Dispositivo" in f
    assert "Ante o exposto" in f


def test_a_ficha_e_menor_que_o_json_do_processo(processo):
    import json
    assert len(ficha(processo)) < len(json.dumps(processo, ensure_ascii=False))


def test_censurada_nao_entrega_o_resultado(processo):
    f = ficha_censurada(processo)
    assert "Ante o exposto" not in f
    assert "## Dispositivo" not in f
    assert "## Fundamentação" not in f
    assert "  sentenca" not in f  # o marco; "conclusao_sentenca" pode ficar
    assert "2026-09-02" not in f


def test_censurada_nao_entrega_a_identidade_do_juizo(processo):
    """O cabeçalho do relatório traz o nome do magistrado de graça; a vara e o
    foro identificam o juiz igualmente bem."""
    f = ficha_censurada(processo)
    assert "Juiz Sintético de Teste" not in f
    assert "Juiz(a) de Direito" not in f
    assert "4ª Vara Cível" not in f
    assert "Foro de Limeira" not in f


def test_censurada_mantem_o_caso(processo):
    f = ficha_censurada(processo)
    assert "Autora Sintética ajuizou ação de cobrança" in f
    assert "## Relatório" in f
    assert "2025-03-12  distribuicao" in f
    assert "Valor da causa: R$ 48.320,00" in f


def test_censurada_corta_a_linha_do_tempo_antes_da_sentenca(processo):
    marcos = ficha_censurada(processo).split("## Marcos\n")[1].split("\n\n")[0]
    assert "2026-08-28  conclusao_sentenca" in marcos
    assert "sentenca\n" not in marcos.replace("conclusao_sentenca", "")


def test_ficha_de_processo_sem_capa_nem_movimentacoes(processo):
    """`fetch_juiz.py` grava capa=None e movimentacoes=[] quando o CPOPG falha."""
    processo["capa"], processo["movimentacoes"] = None, []
    f = ficha(processo)
    assert f.startswith("# 1000000-00.2025.8.26.0320")
    assert "## Partes" not in f
    assert "## Marcos" not in f
    assert "Ante o exposto" in f
