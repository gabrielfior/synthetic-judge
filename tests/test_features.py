import pytest

from sj.features import dispositivo, features


def test_dispositivo_casa_o_ultimo_marcador_nao_o_primeiro(processo):
    """O split de sj.tjsp corta no "Portanto, julgo improcedente a reconvenção"
    da fundamentação. Uma regex ingênua de resultado leria "improcedente" onde a
    ação principal foi procedente em parte."""
    assert dispositivo(processo["texto"]).startswith("Ante o exposto")


def test_o_dispositivo_do_json_e_o_que_erra(processo):
    """Guarda contra a tentação de reusar o campo pronto."""
    assert processo["dispositivo"].startswith("Portanto")


@pytest.mark.parametrize("trecho,esperado", [
    ("Ante o exposto, JULGO PROCEDENTE o pedido", "procedente"),
    ("Ante o exposto, julgo procedentes os pedidos", "procedente"),
    ("Ante o exposto, JULGO PARCIALMENTE PROCEDENTES os pedidos",
     "parcialmente_procedente"),
    ("Ante o exposto, julgo parcialmente procedente a ação", "parcialmente_procedente"),
    ("Ante o exposto, JULGO IMPROCEDENTE o pedido", "improcedente"),
    ("Ante o exposto, julgo improcedentes os pedidos", "improcedente"),
    ("Ante o exposto, julgo extinto o processo sem resolução do mérito, nos termos "
     "do artigo 485, inciso VI, do CPC", "extinto_sem_merito"),
    ("Ante o exposto, HOMOLOGO o acordo celebrado entre as partes", "homologacao"),
    ("Ante o exposto, julgo extinta a execução, nos termos do artigo 924, inciso II, "
     "do CPC", "extinta_execucao"),
])
def test_resultado_normaliza_a_caixa_e_o_plural(trecho, esperado):
    assert features({"texto": trecho})["resultado"] == esperado


def test_resultado_sem_marcador_conhecido_fica_indeterminado():
    assert features({"texto": "Ante o exposto, defiro o requerido."})["resultado"] is None


def test_a_reconvencao_nao_contamina_o_resultado_da_acao(processo):
    f = features(processo)
    assert f["resultado"] == "parcialmente_procedente"
    assert f["resultado_reconvencao"] == "improcedente"


def test_sem_reconvencao_o_campo_fica_vazio():
    f = features({"texto": "Ante o exposto, JULGO PROCEDENTE o pedido"})
    assert f["resultado_reconvencao"] is None


def test_fundamento_legal_sai_do_dispositivo(processo):
    assert features(processo)["fundamento_legal"] == ["487 I"]


def test_fundamento_legal_aceita_abreviacao_e_repeticao():
    f = features({"texto": "Ante o exposto, extingo nos termos do art. 485, VI, e do "
                           "artigo 485, inciso VI, do CPC"})
    assert f["fundamento_legal"] == ["485 VI"]


def test_dano_moral_pedido_e_concedido_sao_perguntas_diferentes(processo):
    f = features(processo)
    assert f["dano_moral_pedido"] is True
    assert f["dano_moral_concedido"] is True
    assert f["valor_dano_moral"] == 5000.0


def test_dano_moral_pedido_no_relatorio_e_negado_no_dispositivo():
    """O caso mais comum do corpus: o assunto é dano moral, o pedido é rejeitado
    na fundamentação e o dispositivo sequer menciona a palavra."""
    f = features({
        "assunto": "Indenização por Dano Moral",
        "relatorio": "Requer a condenação da ré ao pagamento de indenização por "
                     "danos morais no valor de R$ 10.000,00.",
        "texto": "Ante o exposto, JULGO PARCIALMENTE PROCEDENTE o pedido para "
                 "declarar a inexigibilidade do débito."})
    assert f["dano_moral_pedido"] is True
    assert f["dano_moral_concedido"] is False
    assert f["valor_dano_moral"] is None


def test_o_assunto_sozinho_basta_para_o_pedido():
    f = features({"assunto": "Indenização por Dano Moral",
                  "texto": "Ante o exposto, julgo improcedente o pedido."})
    assert f["dano_moral_pedido"] is True


def test_dano_moral_negado_dentro_do_proprio_dispositivo():
    f = features({"texto": "Ante o exposto, JULGO PARCIALMENTE PROCEDENTE o pedido "
                           "para condenar a ré a R$ 1.000,00 de dano material. "
                           "Afasto o pedido de indenização por danos morais."})
    assert f["dano_moral_concedido"] is False
    assert f["valor_dano_moral"] is None


def test_sem_dano_moral_em_lugar_nenhum():
    f = features({"texto": "Ante o exposto, JULGO PROCEDENTE o pedido de cobrança"})
    assert f["dano_moral_pedido"] is False
    assert f["dano_moral_concedido"] is False
    assert f["valor_dano_moral"] is None


def test_honorarios_percentual_e_base(processo):
    f = features(processo)
    assert f["honorarios_pct"] == 10.0
    assert f["honorarios_base"] == "condenacao"


@pytest.mark.parametrize("trecho,base", [
    ("Condeno o réu a honorários de 15% sobre o valor da causa", "causa"),
    ("Condeno o réu a honorários de 10% sobre o proveito econômico", "proveito"),
    ("Fixo os honorários por equidade, nos termos do art. 85, § 8º, em R$ 2.000,00",
     "equidade"),
])
def test_honorarios_base_reconhece_as_variantes(trecho, base):
    assert features({"texto": f"Ante o exposto, julgo procedente. {trecho}"})[
        "honorarios_base"] == base


def test_sucumbencia_reciproca(processo):
    assert features(processo)["sucumbencia_reciproca"] is True


def test_justica_gratuita_vem_do_cabecalho_da_sentenca(processo):
    assert features(processo)["justica_gratuita"] is True


def test_julgamento_antecipado_e_a_citacao_ao_art_355():
    f = features({"texto": "Ante o exposto, julgo procedente.",
                  "fundamentacao": "Julgo antecipadamente o mérito, na forma do "
                                   "artigo 355, inciso I, do CPC."})
    assert f["julgamento_antecipado"] is True


def test_julgamento_antecipado_falso_no_processo_que_teve_pericia(processo):
    assert features(processo)["julgamento_antecipado"] is False


def test_revelia():
    f = features({"texto": "Ante o exposto, julgo procedente.",
                  "fundamentacao": "O réu, citado, não contestou: é revel."})
    assert f["revelia"] is True


def test_contagens_e_prazos_saem_das_movimentacoes(processo):
    f = features(processo)
    assert f["houve_pericia"] is True
    assert f["n_audiencias"] == 1
    assert f["n_movimentacoes"] == 17
    assert f["dias_ate_sentenca"] == 539
    assert f["dias_ate_1a_decisao"] == 373


def test_no_json_a_data_exata_manda_e_a_estimada_fica_vazia(processo):
    f = features(processo)
    assert f["data_ajuizamento"] == "2025-03-12"
    assert f["dias_ate_sentenca"] == 539
    assert f["data_distribuicao_estimada"] == ""
    assert f["dias_tramitacao_estimados"] is None
    assert f["origem_data_inicio"] == "movimentacao"


def test_no_parquet_so_ha_a_estimada_e_ela_nao_vira_exata(julgado):
    """Sem CPOPG não há data exata. A estimada não pode preencher o campo exato:
    um erro mediano de 6 dias não é uma data de ajuizamento."""
    f = features(julgado)
    assert f["data_ajuizamento"] == ""
    assert f["dias_ate_sentenca"] is None
    assert f["data_distribuicao_estimada"] == "2025-03-08"
    assert f["dias_tramitacao_estimados"] == 543
    assert f["origem_data_inicio"] == "cnj"


def test_os_dias_estimados_saem_da_coluna_e_nao_da_subtracao(julgado):
    """543 é o que o cnj gravou; a subtração das duas datas daria 544."""
    julgado["dias_tramitacao"] = 999
    assert features(julgado)["dias_tramitacao_estimados"] == 999


def test_o_parquet_tambem_alimenta_o_resto_das_features(julgado):
    f = features(julgado)
    assert f["resultado"] == "parcialmente_procedente"
    assert f["data_sentenca"] == "2026-09-02"
    assert f["honorarios_pct"] == 10.0


def test_valor_da_causa_vira_numero(processo):
    assert features(processo)["valor_causa"] == 48320.0


def test_advogados_sem_repeticao(processo):
    assert features(processo)["advogados"] == ["Advogada Sintética", "Advogado Sintético"]


def test_procedimento_comum_nao_e_incidente(processo):
    assert features(processo)["incidente"] is False


@pytest.mark.parametrize("classe", [
    "Habilitação de Crédito",
    "Cumprimento de sentença",
])
def test_incidente_marcado_para_nao_contaminar_a_taxa_agregada(processo, classe):
    """Incidente não tem mérito no mesmo sentido; misturá-lo suja qualquer média."""
    processo["classe"] = processo["capa"]["classe"] = classe
    assert features(processo)["incidente"] is True


def test_processo_sem_capa_nem_movimentacoes_nao_estoura():
    """`fetch_juiz.py` grava capa=None e movimentacoes=[] quando o CPOPG falha."""
    f = features({"texto": "Ante o exposto, julgo procedente.",
                  "capa": None, "movimentacoes": []})
    assert f["resultado"] == "procedente"
    assert f["valor_causa"] is None
    assert f["n_movimentacoes"] == 0
    assert f["dias_ate_sentenca"] is None


@pytest.mark.parametrize("trecho,base", [
    ("honorários que fixo em 10% sobre o valor atualizado da causa", "causa"),
    ("honorários que arbitro em 15% sobre o valor total da condenação", "condenacao"),
    # "valor updated da causa" é erro de digitação do próprio dispositivo
    # (1012623-55.2024): a base não pode depender do adjetivo do meio.
    ("honorários que fixo em 10% sobre o valor updated da causa", "causa"),
])
def test_honorarios_base_ignora_o_adjetivo_entre_valor_e_base(trecho, base):
    assert features({"texto": f"Ante o exposto, julgo procedente. {trecho}"})[
        "honorarios_base"] == base


@pytest.mark.parametrize("trecho,pct", [
    # O rateio da sucumbência vem antes do percentual de verdade, na mesma frase.
    ("condeno ao pagamento de honorários advocatícios, na proporção de 50% para "
     "cada, fixando os honorários em 10% sobre o valor da causa", 10.0),
    # Tabela DPE/OAB: o 70% é fração do que já foi arbitrado, não o arbitramento.
    ("condeno ao pagamento de honorários no máximo previsto na Tabela de Convênio "
     "DPE/OAB, facultada a expedição do equivalente a 70% do arbitrado", None),
    ("condeno ao pagamento de honorários sucumbenciais e 30% a título de "
     "honorários contratuais", None),
    ("condeno ao pagamento de honorários de advogado e multa moratória no "
     "percentual de 2%", None),
    ("condeno ao pagamento de honorários advocatícios na forma supra, acrescidos "
     "de juros de 1% ao mês a partir do vencimento", None),
])
def test_percentual_alheio_nao_vira_honorario(trecho, pct):
    """Nos 6.459 julgados do Parquet a janela larga capturava juros, multa,
    rateio de sucumbência, honorário contratual e fração de tabela."""
    assert features({"texto": f"Ante o exposto, julgo procedente. {trecho}."}
                    )["honorarios_pct"] == pct


def test_extincao_da_execucao_ganha_da_homologacao_do_laudo():
    """"homologo o laudo ... e declaro extinto o cumprimento" é extinção, não
    homologação de acordo: quem manda é o art. 924."""
    f = features({"texto": "Diante do exposto, homologo o laudo pericial complementar "
                           "e declaro extinto o presente cumprimento de sentença, com "
                           "fundamento no artigo 924, inciso II, do CPC."})
    assert f["resultado"] == "extinta_execucao"


def test_acao_e_reconvencao_julgadas_na_mesma_oracao():
    """Sem período entre elas, descartar a oração inteira apagaria a ação principal."""
    f = features({"texto": "Ante o exposto, JULGO PROCEDENTE a ação principal e JULGO "
                           "IMPROCEDENTE a reconvenção, resolvendo o mérito nos termos "
                           "do art. 487, I, do CPC."})
    assert f["resultado"] == "procedente"
    assert f["resultado_reconvencao"] == "improcedente"


# --- regressões da segunda leitura (eval_features.py): cada texto abaixo é uma
# forma de dispositivo em que o regex errava, reescrita sem partes reais.

def _f(disp: str) -> dict:
    return features({"texto": disp})


@pytest.mark.parametrize("disp,esperado", [
    ("Ante o exposto, JULGO TOTALMENTE PROCEDENTES os pedidos da inicial.", "procedente"),
    ("Ante o exposto, resolvo o mérito para JULGAR PROCEDENTES os pedidos.", "procedente"),
    ("Ante o exposto, JULGO PROCEDENTES, EM PARTE, os pedidos da inicial.",
     "parcialmente_procedente"),
    ("Ante o exposto, julgo: PARCIALMENTE PROCEDENTE a ação principal para: (A) declarar.",
     "parcialmente_procedente"),
    ("Isto posto, com fundamento no art. 485, inciso III, do CPC, declaro EXTINTA a ação.",
     "extinto_sem_merito"),
    ("Ante o exposto, INDEFIRO A PETIÇÃO INICIAL e JULGO EXTINTO o processo, sem resolução "
     "de mérito, com fundamento no art. 330, inciso IV, do CPC.", "extinto_sem_merito"),
    # prescrição: o juiz escreve "extinto com resolução de mérito", o resultado é de
    # improcedência
    ("Ante o exposto, JULGO EXTINTO o processo, com resolução de mérito, nos termos do "
     "artigo 487, inciso II, do CPC, reconhecendo a prescrição.", "improcedente"),
])
def test_resultado_das_formas_que_o_regex_perdia(disp, esperado):
    assert _f(disp)["resultado"] == esperado


def test_suspensao_do_processo_nao_e_resultado():
    assert _f("Ante o exposto, suspendo o andamento do processo pelo prazo de seis "
              "meses (art. 313, V, a, do CPC).")["resultado"] is None


@pytest.mark.parametrize("disp", [
    "Ante o exposto, julgo PROCEDENTE o pedido formulado na ação principal e IMPROCEDENTE "
    "o pedido formulado na reconvenção, nos termos do art. 487, I, do CPC.",
    "Ante o exposto, julgo procedente a ação. De outro lado, julgo igualmente "
    "improcedente a reconvenção. Declaro extinto o processo com resolução do mérito "
    "(art. 487, I, do CPC).",
])
def test_reconvencao_com_verbo_elidido_ou_adverbio_nao_vira_o_resultado_da_acao(disp):
    assert _f(disp)["resultado"] == "procedente"


def test_itens_com_resultados_diferentes_dao_parcial():
    disp = ("Ante o exposto, julgo: a) improcedente a ação em face de X; sucumbente, "
            "arcará a autora com as custas; b) procedente a ação em face de Y, para "
            "condená-la a pagar R$ 1.000,00.")
    assert _f(disp)["resultado"] == "parcialmente_procedente"


def test_itens_iguais_dao_o_proprio_resultado_e_a_reconvencao_fica_de_fora():
    disp = ("Ante o exposto, julgo: a) improcedente a ação ajuizada por X; "
            "b) procedente a reconvenção apresentada por Y.")
    assert _f(disp)["resultado"] == "improcedente"


@pytest.mark.parametrize("disp", [
    "Ante o exposto, julgo improcedente a ação. Condeno o autor ao pagamento de "
    "honorários de 10% sobre o valor do pedido de danos morais (R$ 15.000,00).",
    "Ante o exposto, julgo procedente em parte. Diante da sucumbência recíproca, em que a "
    "autora decaiu apenas quanto ao pedido de indenização por danos morais, condeno a ré ao "
    "pagamento de 80% das custas.",
    "Ante o exposto, julgo procedente a ação. Fica afastada a condenação ao pagamento de "
    "indenização por danos morais.",
    "Ante o exposto, julgo: a) declarar a dívida; c) indeferir o pedido de indenização "
    "por danos morais. Condeno a ré às custas.",
    "Ante o exposto, julgo procedente o pedido de ANAIDE DE MORAIS SOARES para condenar os "
    "réus ao pagamento de R$ 2.862,17.",
    "Ante o exposto, JULGO PARCIALMENTE PROCEDENTES os pedidos da Ação de Rescisão c.c. "
    "Indenização por Dano Moral, nos termos do art. 487, I, do CPC, para: declarar a "
    "rescisão e condenar a ré a restituir R$ 5.000,00.",
    "Ante o exposto, julgo procedente a ação. Para a autora, fixo honorários de 10% sobre a "
    "diferença entre o valor pleiteado (R$ 22.600,00 + R$ 10.000,00 de danos morais) e o "
    "valor da condenação.",
    "Ante o exposto, julgo procedente a ação principal e a reconvenção, para condenar a "
    "reconvinda ao pagamento de indenização por danos morais de R$ 20.000,00.",
])
def test_dano_moral_que_nao_e_condenacao(disp):
    assert _f(disp)["dano_moral_concedido"] is False


def test_negacao_fraca_antes_da_condenacao_nao_nega_o_dano_moral():
    disp = ("Ante o exposto, julgo procedente a ação para restituir o valor do desconto "
            "indevido CONDENAR o réu ao pagamento de indenização por danos morais no "
            "valor de R$ 5.000,00, com correção monetária.")
    f = _f(disp)
    assert f["dano_moral_concedido"] is True and f["valor_dano_moral"] == 5000.0


def test_item_de_lista_com_valor_concede_dano_moral():
    disp = ("Ante o exposto, julgo procedente para condenar a ré a pagar: a) Danos "
            "materiais no valor de R$ 25.000,00; d) Danos morais no valor de R$ 15.000,00, "
            "corrigidos desde esta data.")
    f = _f(disp)
    assert f["dano_moral_concedido"] is True and f["valor_dano_moral"] == 15000.0


@pytest.mark.parametrize("trecho,valor", [
    ("pagar ao autor R$ 7.000,00, a título de danos morais; restituir R$ 550,00", 7000.0),
    ("pagamento de cinco mil reais a título de danos morais, corrigidos", 5000.0),
    ("pagamento de R$ 4.000,00 (oito mil reais), a título de danos morais", 4000.0),
    ("Indenização por Danos Morais: Condenar o réu a pagar a quantia de R$ 15.000,00", 15000.0),
])
def test_valor_do_dano_moral_e_a_quantia_mais_proxima(trecho, valor):
    f = _f(f"Ante o exposto, julgo procedente para condenar o réu ao {trecho}.")
    assert f["valor_dano_moral"] == valor


def test_homologar_desistencia_extingue_sem_merito():
    assert _f("Ante o exposto, HOMOLOGO o pedido de desistência da ação e julgo extinto o "
              "processo (art. 485, VIII, do CPC).")["resultado"] == "extinto_sem_merito"


def test_art_487_iii_e_homologacao_nao_procedencia():
    assert _f('Ante o exposto, julgo extinto o processo, com resolução do mérito, nos '
              'termos do artigo 487, III, "a" do CPC.')["resultado"] == "homologacao"
