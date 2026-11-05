"""Testa a extração dos parâmetros do visualizador da Pasta Digital."""
import pathlib

import pytest

from sj import pastadigital

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "pastadigital_visualizador.html"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="fixture real fora do repo (veja tests/fixtures/README.md)")


def test_extrai_um_parametro_por_faixa_de_paginas():
    pars = pastadigital.parametros(FIXTURE.read_text())
    assert len(pars) == 1
    assert "cdDocumento=156951103" in pars[0]
    assert "nuProcesso=1002364-64.2025.8.26.0320" in pars[0]


def test_visualizador_sem_documento_da_erro_claro():
    with pytest.raises(pastadigital.DocumentoIndisponivel):
        pastadigital.parametros("<html><body>Não foi possível validar o seu acesso</body></html>")


def test_nome_do_arquivo_e_derivado_do_processo():
    assert pastadigital.nome_arquivo("1002364-64.2025.8.26.0320", "Sentença") == \
        "1002364-64.2025.8.26.0320_sentenca.pdf"
    assert pastadigital.nome_arquivo("0008303-42.2025.8.26.0320", "Ato Ordinatório - DJE") == \
        "0008303-42.2025.8.26.0320_ato-ordinatorio-dje.pdf"
