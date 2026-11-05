from sj.extrator import amostra, casos, entrada, interpretar, metricas, sistema

VALIDOS = {"Seguro", "Bancários", "Contratos Bancários"}


def test_entrada_tira_a_linha_que_carrega_o_assunto(processo):
    """O carimbo do e-SAJ diz `Classe - Assunto <classe> - <assunto>`: o gabarito."""
    r = entrada(processo)
    assert "Classe - Assunto" not in r
    assert "Cobrança de Aluguéis" not in r
    assert "Processo Digital" not in r
    assert "Juiz Sintético" not in r
    assert "ajuizou ação de cobrança" in r  # a narrativa fica
    assert r.rstrip().endswith("É o relatório")  # e para antes da fundamentação


def test_entrada_nao_vaza_fundamentacao_nem_dispositivo(processo):
    r = entrada(processo)
    assert "Portanto, julgo" not in r
    assert "Ante o exposto" not in r


def _doc(n, assunto, **kw):
    base = {"processo": f"p{n:03}", "data": "2026-01-01", "assunto": assunto, "comarca": "Limeira",
            "classe": "Procedimento Comum Cível", "split_ok": True,
            "texto": "Vistos. Narrativa. É o relatório\nAnte o exposto, julgo."}
    return base | kw


def test_casos_filtra_comarca_classe_e_split():
    docs = [_doc(1, "Seguro"),
            _doc(2, "Seguro", comarca="Santa Bárbara d'Oeste"),
            _doc(3, "Seguro", classe="Cumprimento de Sentença"),
            _doc(4, "Seguro", split_ok=False),
            _doc(5, "")]
    assert [c["processo"] for c in casos(docs)] == ["p001"]


def test_amostra_estratifica_em_rodizio():
    cs = [{"id": f"a{i}", "assunto": "A"} for i in range(10)] + [
          {"id": "b0", "assunto": "B"}, {"id": "c0", "assunto": "C"}]
    assert sorted(c["assunto"] for c in amostra(cs, 6)) == ["A", "A", "A", "A", "B", "C"]
    assert len(amostra(cs, 99)) == 12  # pedir mais que existe devolve tudo


def test_sistema_lista_os_assuntos_ordenados():
    s = sistema(["Seguro", "Bancários"])
    assert s.endswith("- Bancários\n- Seguro")


def test_interpretar_descarta_invalidos_e_repetidos():
    r = '```json\n{"assuntos": ["Seguro", "Inventado", "Seguro", "Bancários"]}\n```'
    assert interpretar(r, VALIDOS) == ["Seguro", "Bancários"]


def test_interpretar_resposta_quebrada_devolve_vazio():
    assert interpretar("não sei", VALIDOS) == []
    assert interpretar('{"assuntos": "Seguro"}', VALIDOS) == []
    assert interpretar('{"outra": []}', VALIDOS) == []


def test_metricas():
    rs = [{"assunto": "A", "previsto": ["A", "B", "C"]},   # top-1
          {"assunto": "A", "previsto": ["B", "A", "C"]},   # só top-3
          {"assunto": "B", "previsto": ["C", "A", "B"]},   # só top-3
          {"assunto": "C", "previsto": []}]                # sem resposta
    m = metricas(rs)
    assert (m["n"], m["top1"], m["top3"]) == (4, 0.25, 0.75)
    assert m["sem_resposta"] == 0.25
    assert (m["moda"], m["baseline"]) == ("A", 0.5)
    assert {"real": "A", "previsto": "B", "n": 1} in m["confundidos"]


def test_metricas_vazio():
    assert metricas([]) == {"n": 0}


def test_casos_pode_incluir_os_truncados():
    docs = [_doc(1, "Seguro"), _doc(2, "Seguro", split_ok=False)]
    assert len(casos(docs)) == 1
    assert len(casos(docs, so_split_ok=False)) == 2


def test_id_distingue_documentos_do_mesmo_processo():
    docs = [_doc(1, "Seguro", data="2025-11-10"), _doc(1, "Seguro", data="2026-01-27")]
    ids = [c["id"] for c in casos(docs)]
    assert ids == ["p001|2025-11-10", "p001|2026-01-27"]
