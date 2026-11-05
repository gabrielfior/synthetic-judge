"""Testa o parser do CPOPG contra uma página real salva em fixtures/."""
import pathlib
import re

import pytest

from sj import alvo, cpopg

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "cpopg_1002364-64.2025.8.26.0320.html"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="fixture real fora do repo (veja tests/fixtures/README.md)")


@pytest.fixture(scope="module")
def proc() -> dict:
    return cpopg.parse_processo(FIXTURE.read_text())


def test_capa(proc):
    assert proc["processo"] == "1002364-64.2025.8.26.0320"
    assert proc["classe"] == "Procedimento Comum Cível"
    assert proc["assunto"] == "Cobrança de Aluguéis - Sem despejo"
    assert proc["juiz"] == alvo.juiz_nome()
    assert proc["vara"] == "4ª Vara Cível"
    assert proc["area"] == "Cível"


def test_capa_nao_vaza_o_resto_da_pagina(proc):
    """Os campos são <div id=...>; casar até </span> arrasta o menu junto."""
    assert proc["valor_acao"] == "R$ 10.000,00"
    assert proc["controle"] == "2025/000289"
    assert proc["distribuicao"].startswith("24/02/2025")


def test_movimentacoes_ordenadas_da_mais_nova(proc):
    movs = proc["movimentacoes"]
    assert len(movs) > 50
    assert movs[0]["data"] == "06/09/2026"
    assert movs[0]["titulo"] == "Suspensão do Prazo"
    assert movs[0]["detalhe"].startswith("Prazo referente ao usuário")
    assert movs[-1]["data"].endswith("/2025")


def test_movimentacoes_sem_duplicata_do_preview(proc):
    """A página traz um tbody com as últimas movimentações e outro com todas."""
    movs = proc["movimentacoes"]
    primeira = (movs[0]["data"], movs[0]["titulo"])
    assert [(m["data"], m["titulo"]) for m in movs].count(primeira) == 1


def test_partes(proc):
    reqte = next(p for p in proc["partes"] if p["tipo"] == "Reqte")
    assert reqte["nome"].strip()
    assert reqte["advogados"]


INCIDENTE = FIXTURE.parent / "cpopg_incidente_0008303-42.2025.8.26.0320.html"


@pytest.fixture(scope="module")
def inc() -> dict:
    """Execução/Liquidação de sentença: cabeçalho sem os ids da capa normal."""
    return cpopg.parse_processo(INCIDENTE.read_text())


def test_incidente_tem_capa(inc):
    assert inc["processo"] == "0008303-42.2025.8.26.0320"
    assert inc["classe"] == "Liquidação de Sentença pelo Procedimento Comum"
    assert inc["incidente"] == "Execução de Sentença"
    assert inc["processo_principal"] == "1004305-88.2021.8.26.0320"
    assert inc["assunto"] == "Práticas Abusivas"
    assert inc["vara"] == "4ª Vara Cível"


def test_incidente_tem_movimentacoes(inc):
    assert len(inc["movimentacoes"]) > 5
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", inc["movimentacoes"][0]["data"])


def test_processo_normal_tem_as_mesmas_chaves(proc, inc):
    assert set(proc) == set(inc)


TRUNCADA = FIXTURE.parent / "cpopg_truncada.html"


def test_pagina_truncada_nao_passa_por_processo_sem_movimentacao():
    """O e-SAJ às vezes devolve a capa sem o bloco de movimentações, sem erro."""
    with pytest.raises(cpopg.RespostaTruncada):
        cpopg.parse_processo(TRUNCADA.read_text())


def test_pagina_completa_nao_e_confundida_com_truncada():
    assert cpopg.parse_processo(FIXTURE.read_text())["movimentacoes"]


TEOR = FIXTURE.parent / "cpopg_1017657-45.2023.8.26.0320.html"


@pytest.fixture(scope="module")
def dje() -> dict:
    """A movimentação 'Remetido ao DJE' carrega o teor integral do ato."""
    movs = cpopg.parse_processo(TEOR.read_text())["movimentacoes"]
    return next(m for m in movs if m["data"] == "04/09/2026" and m["titulo"] == "Remetido ao DJE")


def test_metadados_da_movimentacao(dje):
    assert dje["meta"]["relacao"] == "1578/2026"
    assert dje["meta"]["advogados"] == "Carina Dirce Grotta Benedetti (OAB 188688/SP)"


def test_teor_do_ato_vem_inteiro(dje):
    teor = dje["meta"]["teor_do_ato"]
    assert teor.startswith("Vistos, etc. Ante o pagamento do débito")
    assert "artigo 924, inciso II" in teor
    assert teor.endswith("arquivem-se. P.R.I.C.")   # não pode engolir o "Advogados(s):"


def test_movimentacao_com_documento_traz_o_link():
    movs = cpopg.parse_processo(TEOR.read_text())["movimentacoes"]
    com_doc = [m for m in movs if m["url_documento"]]
    assert len(com_doc) > 10
    assert com_doc[0]["url_documento"].startswith(
        "https://esaj.tjsp.jus.br/cpopg/abrirDocumentoVinculadoMovimentacao.do?")


def test_movimentacao_sem_metadados_nao_quebra():
    movs = cpopg.parse_processo(FIXTURE.read_text())["movimentacoes"]
    assert all(isinstance(m["meta"], dict) for m in movs)
    assert any(m["meta"] == {} for m in movs)


def test_so_rotulos_conhecidos_viram_metadado():
    """'Diante do exposto:' abre frase, não rótulo — o texto fica só no detalhe."""
    assert cpopg._meta("Diante do exposto: Determino a intimação do Banco do Brasil.") == {}
    assert cpopg._meta("Vista dos autos à parte autora para: Manifestar-se em 05 dias.") == {}


def test_rotulos_conhecidos_com_valor_multilinha():
    meta = cpopg._meta("Relação: 1578/2026\nTeor do ato: Vistos, etc.\n"
                       "Diante do exposto, extingo.\nAdvogados(s): Fulano (OAB 1/SP)")
    assert meta == {"relacao": "1578/2026",
                    "teor_do_ato": "Vistos, etc. Diante do exposto, extingo.",
                    "advogados": "Fulano (OAB 1/SP)"}
