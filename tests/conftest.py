"""Um processo sintético com a forma exata do que `fetch_juiz.py` grava.

Nada aqui é texto real: os testes de resumo não carregam trechos de sentença
de verdade. A conferência contra o corpus real é feita por `build_resumos.py`
e por `tests/test_resumos_reais.py`, que lê `data/` em tempo de execução.

O caso é montado para exercer, de propósito, três armadilhas:

- a `distribuicao` da capa é 100 dias posterior à primeira movimentação
  (processo redistribuído), então ela não serve como data de ajuizamento;
- o `dispositivo` do split de `sj.tjsp` começa cedo demais, no "Portanto,
  julgo improcedente a reconvenção" da fundamentação;
- ação e reconvenção têm resultados opostos.
"""
from datetime import date

import pytest

RELATORIO = """SENTENÇA
Processo Digital nº:\t1000000-00.2025.8.26.0320
Classe - Assunto\tProcedimento Comum Cível - Cobrança de Aluguéis - Sem despejo
Requerente:\tAutora Sintética
Requerido:\tRé Sintética Ltda
Justiça Gratuita
Juiz(a) de Direito: Dr(a). Juiz Sintético de Teste
1. RELATÓRIO
Autora Sintética ajuizou ação de cobrança contra Ré Sintética Ltda, alegando
inadimplemento de aluguéis e requerendo indenização por danos morais. Sustenta
que celebrou com a ré contrato de locação do imóvel descrito na inicial, que a
ré deixou de pagar os aluguéis vencidos a partir de janeiro, e que as
notificações extrajudiciais enviadas não foram respondidas. Requer a condenação
ao pagamento dos valores em aberto, acrescidos de correção monetária e juros,
além de indenização pelos danos morais decorrentes da cobrança frustrada.
Citada, a ré apresentou contestação, na qual alega que os aluguéis não foram
pagos porque o imóvel apresentava vícios que impediam o uso para o fim
contratado, e que comunicou o fato à autora em tempo hábil. Em reconvenção,
pede a devolução dos valores já pagos e a rescisão do contrato por culpa da
autora. A autora manifestou-se sobre a contestação, reiterando os termos da
inicial e impugnando os documentos juntados. Foi determinada a produção de
prova pericial contábil, cujo laudo foi juntado e sobre o qual as partes se
manifestaram. É o relatório."""

FUNDAMENTACAO = """2. FUNDAMENTAÇÃO
O laudo pericial apurou o débito. A reconvenção não veio acompanhada de prova
do alegado pagamento. Portanto, julgo improcedente a reconvenção."""

DISPOSITIVO = """Ante o exposto, JULGO PARCIALMENTE PROCEDENTES os pedidos
deduzidos na petição inicial, extinguindo o processo com resolução do mérito,
nos termos do artigo 487, inciso I, do Código de Processo Civil, para condenar
a ré ao pagamento de R$ 5.000,00 (cinco mil reais) a título de danos morais.
Diante da sucumbência recíproca, cada parte arcará com metade das custas e com
os honorários de seus advogados, fixados em 10% sobre o valor da condenação."""

TEXTO = f"{RELATORIO}\n{FUNDAMENTACAO}\n{DISPOSITIVO}"

# Da mais recente para a mais antiga, como o CPOPG devolve. Os títulos e os
# `tipo_da_peticao` são os do vocabulário do e-SAJ, observados no corpus real —
# é o `detalhe` e o `teor_do_ato` que aqui são inventados.
MOVIMENTACOES = [
    {"data": "04/09/2026", "titulo": "Certidão de Publicação Expedida",
     "detalhe": "", "meta": {"data_da_publicacao": "04/09/2026"}, "url_documento": ""},
    {"data": "03/09/2026", "titulo": "Remetido ao DJE",
     "detalhe": "", "meta": {"teor_do_ato": "teor sintético"}, "url_documento": ""},
    {"data": "02/09/2026", "titulo": "Julgada Procedente em Parte a Ação",
     "detalhe": "", "meta": {"teor_do_ato": "teor sintético"}, "url_documento": ""},
    {"data": "28/08/2026", "titulo": "Conclusos para Sentença",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "15/08/2026", "titulo": "Petição Juntada",
     "detalhe": "", "meta": {"tipo_da_peticao": "Petições Diversas"}, "url_documento": ""},
    {"data": "10/07/2026", "titulo": "Petição Juntada", "detalhe": "",
     "meta": {"tipo_da_peticao": "Laudo Pericial - Peticionamento Eletrônico - Petição Peritos"},
     "url_documento": ""},
    {"data": "02/05/2026", "titulo": "Nomeado Perito",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "20/03/2026", "titulo": "Decisão",
     "detalhe": "", "meta": {"teor_do_ato": "teor sintético"}, "url_documento": ""},
    {"data": "05/02/2026", "titulo": "Suspensão do Prazo",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "01/12/2025", "titulo": "Audiência de Instrução e Julgamento",
     "detalhe": "Realizada", "meta": {"situacao": "Realizada"}, "url_documento": ""},
    # O mesmo ato, gravado duas vezes na mesma data: uma como título próprio,
    # outra como petição juntada. A linha do tempo tem de virar uma linha só.
    {"data": "10/05/2025", "titulo": "Contestação Juntada",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "10/05/2025", "titulo": "Petição Juntada",
     "detalhe": "", "meta": {"tipo_da_peticao": "Contestação",
                             "advogados": ["Advogada Sintética"]}, "url_documento": ""},
    {"data": "02/04/2025", "titulo": "AR Positivo Juntado",
     "detalhe": "", "meta": {"juntada_de_ar": "Positivo"}, "url_documento": ""},
    {"data": "20/03/2025", "titulo": "Mandado de Citação Expedido",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "18/03/2025", "titulo": "Conclusos para Despacho",
     "detalhe": "", "meta": {}, "url_documento": ""},
    # Título que não existe no e-SAJ: garante que o relatório de não
    # classificadas continue tendo o que reportar quando a tabela crescer.
    {"data": "15/03/2025", "titulo": "Movimentação Nunca Vista",
     "detalhe": "", "meta": {}, "url_documento": ""},
    {"data": "12/03/2025", "titulo": "Distribuído Livremente (por Sorteio)",
     "detalhe": "", "meta": {}, "url_documento": ""},
]


@pytest.fixture
def julgado() -> dict:
    """Uma linha do Parquet, como `sj.corpus.ler` devolve.

    Não tem CPOPG: sem capa, sem movimentações, sem `data_de_disponibilização`
    (a coluna se chama `data`). Em compensação traz `distribuicao` e
    `dias_tramitacao`, que o `sj.cnj` estimou do número CNJ na hora de gravar.
    """
    return {
        "processo": "1000000-00.2025.8.26.0320",
        "data": date(2026, 9, 2),
        "tipo": "SENTENÇA",
        "classe": "Procedimento Comum Cível",
        "assunto": "Cobrança de Aluguéis - Sem despejo",
        "comarca": "Limeira",
        "foro": "Foro de Limeira",
        "vara": "4ª Vara Cível",
        "magistrado": "Juiz Sintético de Teste",
        "url_pdf": "https://exemplo.invalido/sentenca.pdf",
        "n_chars": len(TEXTO),
        "split_ok": True,
        "texto": TEXTO,
        "relatorio": RELATORIO,
        "fundamentacao": FUNDAMENTACAO,
        "dispositivo": DISPOSITIVO,
        "distribuicao": date(2025, 3, 8),
        "dias_tramitacao": 543,
    }


@pytest.fixture
def processo() -> dict:
    return {
        "processo": "1000000-00.2025.8.26.0320",
        "tipo": "SENTENÇA",
        "classe": "Procedimento Comum Cível",
        "assunto": "Cobrança de Aluguéis - Sem despejo",
        "magistrado": "Juiz Sintético de Teste",
        "comarca": "Limeira",
        "foro": "Foro de Limeira",
        "vara": "4ª Vara Cível",
        "data_de_disponibilização": "02/09/2026",
        "url_pdf": "https://exemplo.invalido/sentenca.pdf",
        "arquivo_pdf": "",
        "texto": TEXTO,
        "n_chars": len(TEXTO),
        "relatorio": RELATORIO,
        "fundamentacao": FUNDAMENTACAO,
        # O split de sj.tjsp casa o PRIMEIRO marcador e corta na reconvenção.
        "dispositivo": FUNDAMENTACAO[FUNDAMENTACAO.index("Portanto"):]
                       + "\n" + DISPOSITIVO,
        "split_ok": True,
        "capa": {
            "incidente": "",
            "processo_principal": "",
            "processo": "1000000-00.2025.8.26.0320",
            "classe": "Procedimento Comum Cível",
            "assunto": "Cobrança de Aluguéis - Sem despejo",
            "foro": "Foro de Limeira",
            "vara": "4ª Vara Cível",
            "juiz": "Juiz Sintético de Teste",
            "area": "Cível",
            # 100 dias depois da primeira movimentação: redistribuição.
            "distribuicao": "20/06/2025 às 10:00 - Livre",
            "valor_acao": "R$ 48.320,00",
            "controle": "2025/000001",
            "partes": [
                {"tipo": "Reqte", "nome": "Autora Sintética",
                 "advogados": ["Advogado Sintético"]},
                {"tipo": "Reqda", "nome": "Ré Sintética Ltda",
                 "advogados": ["Advogada Sintética"]},
            ],
        },
        "movimentacoes": MOVIMENTACOES,
    }
