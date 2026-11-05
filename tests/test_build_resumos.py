import json

import pytest

from build_resumos import (FICHAS, FICHAS_CENSURADAS, carregar_fonte,
                           conferencia, gerar, selecionar)


def linhas(arquivo):
    return [json.loads(x) for x in arquivo.read_text(encoding="utf-8").splitlines()]


def test_gerar_escreve_tres_arquivos(processo, tmp_path):
    gerar([processo], tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "features.json", "fichas.jsonl", "fichas_censuradas.jsonl"]


def test_a_censurada_e_a_resposta_nao_moram_no_mesmo_registro(processo, tmp_path):
    """Separação de arquivos é o que impede entregar o gabarito junto com o
    enunciado; num registro só, basta um consumidor distraído."""
    gerar([processo], tmp_path)
    censurada = linhas(tmp_path / FICHAS_CENSURADAS)[0]
    assert set(censurada) == {"processo", "ficha"}
    assert "Ante o exposto" not in censurada["ficha"]
    assert "resultado" not in censurada


def test_cada_linha_do_jsonl_e_um_processo(processo, tmp_path):
    gerar([processo, {**processo, "processo": "2"}], tmp_path)
    assert [x["processo"] for x in linhas(tmp_path / FICHAS)] == [
        "1000000-00.2025.8.26.0320", "2"]


def test_o_jsonl_sobrevive_a_quebra_de_linha_do_markdown(processo, tmp_path):
    """A ficha tem \\n aos montes: uma linha do JSONL não pode virar duas."""
    gerar([processo], tmp_path)
    bruto = (tmp_path / FICHAS).read_text(encoding="utf-8")
    assert bruto.count("\n") == 1
    assert "## Marcos" in json.loads(bruto)["ficha"]


def test_o_features_json_e_uma_lista_de_registros(processo, tmp_path):
    gerar([processo], tmp_path)
    registros = json.loads((tmp_path / "features.json").read_text(encoding="utf-8"))
    assert [r["processo"] for r in registros] == ["1000000-00.2025.8.26.0320"]
    assert registros[0]["resultado"] == "parcialmente_procedente"


def test_gerar_devolve_os_registros_para_a_conferencia(processo, tmp_path):
    assert gerar([processo], tmp_path)[0]["processo"] == "1000000-00.2025.8.26.0320"


def test_conferencia_mostra_resultado_e_honorarios(processo):
    saida = conferencia([processo])
    assert "parcialmente_procedente" in saida
    assert "10.0%" in saida


def test_conferencia_reporta_as_nao_classificadas(processo):
    """Sem este aviso a lista branca de eventos falha em silêncio."""
    assert "Movimentação Nunca Vista" in conferencia([processo])


def test_carregar_fonte_le_o_json(processo, tmp_path):
    arquivo = tmp_path / "sentencas.json"
    arquivo.write_text(json.dumps([processo], ensure_ascii=False), encoding="utf-8")
    assert carregar_fonte(arquivo)[0]["processo"] == "1000000-00.2025.8.26.0320"


def test_carregar_fonte_le_o_parquet(processo, tmp_path):
    corpus = pytest.importorskip("sj.corpus")
    arquivo = corpus.escrever([processo], tmp_path / "corpus.parquet")
    lido = carregar_fonte(arquivo)
    assert lido[0]["processo"] == "1000000-00.2025.8.26.0320"
    assert lido[0]["dispositivo"].startswith("Portanto")  # o split de sj.tjsp


def test_selecionar_descarta_o_que_nao_tem_relatorio(processo, julgado):
    """No Parquet a mediana de `n_chars` é 1.243: a maior parte são atos curtos
    de execução fiscal, sem relatório nem dispositivo destacáveis."""
    curto = {**julgado, "relatorio": "Vistos. Homologo.", "processo": "curto"}
    sem_split = {**julgado, "split_ok": False, "processo": "sem_split"}
    despacho = {**julgado, "tipo": "DESPACHO", "processo": "despacho"}
    escolhidos = selecionar([processo, curto, sem_split, despacho, julgado], None)
    assert [d["processo"] for d in escolhidos] == ["1000000-00.2025.8.26.0320",
                                                   "1000000-00.2025.8.26.0320"]


def test_limite_corta_depois_do_filtro(processo, julgado):
    """Cortar antes devolveria uma amostra de lixo: o filtro é que dá o corpus."""
    curto = {**julgado, "relatorio": "Vistos.", "processo": "curto"}
    assert len(selecionar([curto, processo, julgado], 1)) == 1
    assert selecionar([curto, processo, julgado], 1)[0]["tipo"] == "SENTENÇA"


def test_sem_limite_vem_tudo(processo):
    assert len(selecionar([processo] * 5, None)) == 5


def test_a_ficha_do_parquet_sai_sem_adaptador(julgado, tmp_path):
    gerar([julgado], tmp_path)
    ficha = linhas(tmp_path / FICHAS)[0]["ficha"]
    assert "Distribuído ~2025-03-08 (estimado do nº CNJ)" in ficha
