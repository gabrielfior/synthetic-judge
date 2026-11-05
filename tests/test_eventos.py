import pytest

from sj.eventos import (agregados, classificar, linha_do_tempo,
                        nao_classificadas, rotulo_ruido)


def mov(titulo: str, data: str = "01/01/2026", **meta) -> dict:
    return {"data": data, "titulo": titulo, "detalhe": "", "meta": meta,
            "url_documento": ""}


@pytest.mark.parametrize("titulo,evento", [
    ("Distribuído Livremente (por Sorteio) (movimentação exclusiva do distribuidor)",
     "distribuicao"),
    ("Redistribuído Livremente (por Sorteio) (movimentação exclusiva do distribuidor)",
     "redistribuicao"),
    ("Determinada a Emenda à Inicial", "emenda_inicial"),
    ("Emenda à Inicial Juntada", "emenda_inicial"),
    ("Recebida a Petição Inicial", "recebimento_inicial"),
    ("Mandado de Citação Expedido", "citacao"),
    ("AR Positivo Juntado", "citacao"),
    ("AR Negativo Juntado - Não Procurado", "citacao_frustrada"),
    ("Mandado Devolvido Cumprido Negativo", "citacao_frustrada"),
    ("Contestação Juntada", "contestacao"),
    ("Contestação com Reconvenção - Juntada", "reconvencao"),
    ("Réplica Juntada", "replica"),
    ("Decisão de Saneamento e de Organização do Processo", "saneamento"),
    ("Nomeado Perito", "pericia"),
    ("Audiência de Instrução e Julgamento", "audiencia"),
    ("Decisão", "decisao"),
    ("Decisão Interlocutória de Mérito", "decisao"),
    ("Proferidas Outras Decisões não Especificadas", "decisao"),
    ("Não Concedida a Assistência Judiciária Gratuita", "gratuidade_negada"),
    ("Não Concedida a Antecipação de tutela", "tutela"),
    ("Conclusos para Sentença", "conclusao_sentenca"),
    ("Julgada Procedente em Parte a Ação", "sentenca"),
    ("Julgada improcedente a ação", "sentenca"),
    ("Julgado Procedente o Pedido e Improcedência da Reconvenção", "sentenca"),
    ("Extinta a Execução/Cumprimento da Sentença pela Satisfação da Obrigação",
     "sentenca"),
    ("Apelação/Razões Juntada", "recurso"),
    ("Agravo de Instrumento - Acórdão e Demais Peças Juntados - Com Trânsito em "
     "Julgado - Agravo Destruído", "recurso"),
    ("Certidão de Trânsito em Julgado com Baixa Expedida", "transito"),
    ("Execução/Cumprimento de Sentença Iniciada (o)", "cumprimento"),
    ("Arquivado Definitivamente", "arquivamento"),
    ("Manifestação MP ao Juiz Juntada", "manifestacao_mp"),
    ("Incidente Processual Instaurado", "incidente"),
    ("Especificação de Provas Juntada", "provas"),
])
def test_titulos_reais_viram_eventos_do_vocabulario(titulo, evento):
    assert classificar(mov(titulo)) == evento


@pytest.mark.parametrize("tipo,evento", [
    ("Contestação", "contestacao"),
    ("Contestação com Reconvenção", "reconvencao"),
    ("Manifestação Sobre a Contestação", "replica"),
    ("Laudo Pericial - Peticionamento Eletrônico - Petição Peritos", "pericia"),
    ("Manifestação do Perito", "pericia"),
    ("Emenda à Inicial", "emenda_inicial"),
    ("Pedido de Liminar/Antecipação de Tutela", "tutela"),
    ("Razões de Apelação", "recurso"),
    ("Impugnação ao Cumprimento da Sentença", "cumprimento"),
    ("Rol de Testemunha", "provas"),
])
def test_o_tipo_da_peticao_tipa_o_evento_que_o_titulo_nao_tipa(tipo, evento):
    """"Petição Juntada" é o título de 130 movimentações; só o meta as separa."""
    assert classificar(mov("Petição Juntada", tipo_da_peticao=tipo)) == evento


@pytest.mark.parametrize("titulo", [
    "Certidão de Publicação Expedida",
    "Remetido ao DJE",
    "Conclusos para Despacho",
    "Conclusos para Decisão",
    "Suspensão do Prazo",
    "Certidão de Cartório Expedida",
    "Proferido Despacho de Mero Expediente",
    "Ato Ordinatório - Intimação - DJE",
    "Determinada a Manifestação do Requerente/Exequente",
    "Documento Juntado",
])
def test_cartorio_nao_vira_evento(titulo):
    assert classificar(mov(titulo)) is None


def test_peticao_diversa_nao_vira_evento():
    assert classificar(mov("Petição Juntada", tipo_da_peticao="Petições Diversas")) is None


def test_titulo_desconhecido_nao_vira_evento():
    assert classificar(mov("Movimentação Nunca Vista")) is None


def test_linha_do_tempo_e_cronologica_e_so_de_eventos(processo):
    linha = linha_do_tempo(processo["movimentacoes"])
    assert [(e["data"], e["evento"]) for e in linha] == [
        ("2025-03-12", "distribuicao"),
        ("2025-03-20", "citacao"),
        ("2025-04-02", "citacao"),
        ("2025-05-10", "contestacao"),
        ("2025-12-01", "audiencia"),
        ("2026-03-20", "decisao"),
        ("2026-05-02", "pericia"),
        ("2026-07-10", "pericia"),
        ("2026-08-28", "conclusao_sentenca"),
        ("2026-09-02", "sentenca"),
    ]


def test_o_mesmo_ato_gravado_duas_vezes_na_mesma_data_vira_uma_linha(processo):
    """"Contestação Juntada" e "Petição Juntada"/Contestação, ambas em 10/05/2025."""
    contestacoes = [e for e in linha_do_tempo(processo["movimentacoes"])
                    if e["evento"] == "contestacao"]
    assert len(contestacoes) == 1


def test_agregados_contam_o_cartorio_por_rotulo(processo):
    assert agregados(processo["movimentacoes"]) == {
        "publicações": 1, "intimações": 1, "petições": 1,
        "conclusões": 1, "prazos": 1,
    }


def test_o_rotulo_generico_nao_repete_a_palavra_do_cabecalho(processo):
    """O cabeçalho já diz "Cartório:"; "Cartório: 10 cartório" não informa nada."""
    assert rotulo_ruido(mov("Certidão de Cartório Expedida")) == "expedientes"


def test_nao_classificadas_reportam_o_que_a_tabela_nao_cobre(processo):
    assert nao_classificadas(processo["movimentacoes"]) == {"Movimentação Nunca Vista": 1}


@pytest.mark.parametrize("titulo", [
    "Comprovante de Depósito Juntada",
    "Pedido de Inclusão em Pauta",
])
def test_cartorio_agregado_cobre_o_que_sobrou_do_corpus_real(titulo):
    """As duas únicas não classificadas nas 1.168 movimentações dos 10 processos."""
    assert rotulo_ruido(mov(titulo)) == "expedientes"
