import datetime as dt

from sj import corpus


def doc(texto, relatorio, fundamentacao, dispositivo, **kw):
    base = {"processo": "1002364-64.2025.8.26.0320", "tipo": "SENTENÇA",
            "classe": "Procedimento Comum Cível", "assunto": "Cobrança",
            "magistrado": "Fulano", "comarca": "Limeira", "foro": "Foro de Limeira",
            "vara": "4ª Vara Cível", "data_de_disponibilização": "02/09/2026",
            "url_pdf": "https://x/y", "texto": texto, "n_chars": len(texto),
            "relatorio": relatorio, "fundamentacao": fundamentacao,
            "dispositivo": dispositivo, "split_ok": bool(relatorio and dispositivo)}
    return {**base, **kw}


COMPLETO = doc("SENTENÇA\nRelato os fatos. É o relatório.\nFundamento aqui.\nAnte o exposto, julgo.",
               "SENTENÇA\nRelato os fatos. É o relatório.",
               "Fundamento aqui.",
               "Ante o exposto, julgo.")
SEM_DISPOSITIVO = doc("DESPACHO\nVista às partes.", "DESPACHO\nVista às partes.", "", "")


def test_roundtrip_preserva_as_tres_partes(tmp_path):
    f = corpus.escrever([COMPLETO], tmp_path / "c.parquet")
    (lido,) = corpus.ler(f)
    for k in ("relatorio", "fundamentacao", "dispositivo"):
        assert lido[k] == COMPLETO[k]


def test_roundtrip_sem_dispositivo(tmp_path):
    f = corpus.escrever([SEM_DISPOSITIVO], tmp_path / "c.parquet")
    (lido,) = corpus.ler(f)
    assert lido["relatorio"] == SEM_DISPOSITIVO["relatorio"]
    assert lido["fundamentacao"] == ""
    assert lido["dispositivo"] == ""
    assert lido["split_ok"] is False


def test_metadados_e_tipos(tmp_path):
    f = corpus.escrever([COMPLETO], tmp_path / "c.parquet")
    (lido,) = corpus.ler(f)
    assert lido["data"] == dt.date(2026, 9, 2)
    assert lido["vara"] == "4ª Vara Cível"
    assert lido["n_chars"] == len(COMPLETO["texto"])


def test_nao_guarda_as_colunas_duplicadas(tmp_path):
    """O ganho de tamanho vem de não gravar as três fatias; se voltarem, o arquivo dobra."""
    import pyarrow.parquet as pq
    f = corpus.escrever([COMPLETO], tmp_path / "c.parquet")
    nomes = set(pq.read_schema(f).names)
    assert {"fim_relatorio", "inicio_dispositivo"} <= nomes
    assert not ({"relatorio", "fundamentacao", "dispositivo"} & nomes)


def test_grava_distribuicao_e_tramitacao():
    """Estimativa materializada: derivá-la na leitura daria outro número por recorte."""
    import datetime as dt
    import pyarrow.parquet as pq
    import tempfile, pathlib
    # 40 processos do bloco digital de 2024, distribuídos ao longo do ano
    docs = [doc(f"SENTENÇA\nX. É o relatório.\nY.\nAnte o exposto, julgo.",
                "SENTENÇA\nX. É o relatório.", "Y.", "Ante o exposto, julgo.",
                processo=f"{1000001 + i * 400:07d}-11.2024.8.26.0320",
                data_de_disponibilização="15/12/2024")
            for i in range(40)]
    with tempfile.TemporaryDirectory() as tmp:
        f = corpus.escrever(docs, pathlib.Path(tmp) / "c.parquet")
        assert {"distribuicao", "dias_tramitacao"} <= set(pq.read_schema(f).names)
        lidos = corpus.ler(f)
    assert lidos[0]["distribuicao"] == dt.date(2024, 1, 1)
    assert lidos[0]["dias_tramitacao"] == (dt.date(2024, 12, 15) - dt.date(2024, 1, 1)).days
    # quem entrou em janeiro tramitou mais que quem entrou em julho
    assert lidos[0]["dias_tramitacao"] > lidos[20]["dias_tramitacao"] > 0
    # e o último do ano tem distribuição estimada DEPOIS da sentença: recusa, não negativo
    assert lidos[-1]["distribuicao"] > dt.date(2024, 12, 15)
    assert lidos[-1]["dias_tramitacao"] is None


def test_tramitacao_e_none_no_bloco_legado(tmp_path):
    docs = [doc("DESPACHO\nX.", "DESPACHO\nX.", "", "",
                processo=f"{i:07d}-11.2024.8.26.0320") for i in range(1, 41)]
    (lido, *_) = corpus.ler(corpus.escrever(docs, tmp_path / "c.parquet"))
    assert lido["distribuicao"] is None
    assert lido["dias_tramitacao"] is None
