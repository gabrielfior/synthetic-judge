"""Testa o parser do CJPG contra uma busca real filtrada por magistrado."""
import pathlib

import pytest

from sj import alvo
from sj.tjsp import BLOCO_RE, Consulta, parse_bloco

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "cjpg_agente.html"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="fixture real fora do repo (veja tests/fixtures/README.md)")


def test_consulta_sem_agente_mantem_os_params_antigos():
    p = Consulta().params()
    assert p["contadoragente"] == "0"
    assert p["nmAgente"] == ""
    assert "dadosConsulta.agentes[0].cdAgente" not in p


def test_consulta_com_agente():
    p = Consulta(cd_agente="12345").params()
    assert p["contadoragente"] == "1"
    assert p["cdAgente"] == "12345"
    assert p["dadosConsulta.agentes[0].cdAgente"] == "12345"


def test_o_filtro_por_agente_so_traz_o_magistrado_pedido():
    docs = [d for b in BLOCO_RE.findall(FIXTURE.read_text()) if (d := parse_bloco(b))]
    assert len(docs) == 10
    assert {d["magistrado"] for d in docs} == {alvo.juiz_nome()}


def test_cada_sentenca_traz_o_link_do_inteiro_teor():
    docs = [d for b in BLOCO_RE.findall(FIXTURE.read_text()) if (d := parse_bloco(b))]
    d = next(d for d in docs if d["processo"] == "0008678-77.2024.8.26.0320")
    assert d["url_pdf"] == (
        "https://esaj.tjsp.jus.br/cjpg/obterArquivo.do?cdProcesso=8W000F6050000"
        "&cdForo=320&nmAlias=&cdDocumento=156832798"
        "&nmProcesso=0008678-77.2024.8.26.0320")
    assert all(d["url_pdf"] for d in docs)
