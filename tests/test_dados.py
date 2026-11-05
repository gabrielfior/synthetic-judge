import json

import pytest

from sj.dados import carregar, caminho_dados


def test_acha_o_data_subindo_a_arvore(tmp_path):
    """`data/` está no .gitignore e não viaja para as worktrees: rodando de
    .claude/worktrees/<x>, isto acha o data/ do repo principal."""
    (tmp_path / "data").mkdir()
    fundo = tmp_path / ".claude" / "worktrees" / "x"
    fundo.mkdir(parents=True)
    assert caminho_dados(fundo) == tmp_path / "data"


def test_sem_data_em_lugar_nenhum_o_erro_diz_o_que_fazer(tmp_path, monkeypatch):
    monkeypatch.delenv("SJ_DATA_DIR", raising=False)
    with pytest.raises(FileNotFoundError, match="fetch_juiz.py"):
        caminho_dados(tmp_path)


def test_a_variavel_de_ambiente_manda(tmp_path, monkeypatch):
    outro = tmp_path / "outro"
    outro.mkdir()
    monkeypatch.setenv("SJ_DATA_DIR", str(outro))
    (tmp_path / "data").mkdir()
    assert caminho_dados(tmp_path) == outro


def test_carregar_le_o_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("SJ_DATA_DIR", str(tmp_path))
    (tmp_path / "sentencas_juiz.json").write_text(
        json.dumps([{"processo": "1"}]), encoding="utf-8")
    assert carregar(tmp_path) == [{"processo": "1"}]
