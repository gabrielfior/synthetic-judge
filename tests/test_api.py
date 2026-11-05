import json

import pytest

from sj.api import EntradaInvalida, executar

TAX = [{"nome": "A", "definicao": "x", "grupo": "G"},
       {"nome": "B", "definicao": "y", "grupo": "H"}]


def _base():
    return [{"id": f"c{i}", "processo": f"p{i}", "data": "2025-03-01",
             "classe": "A" if i < 40 else "B", "grupo": "G" if i < 40 else "H",
             "procedente": i % 2, "dias": 300, "dm_pedido": True,
             "dm_concedido": i % 2 == 0, "dm_valor": 5000.0 if i % 2 == 0 else None,
             "dm_razao": None, "url_pdf": f"http://x/{i}", "resultado": "procedente"}
            for i in range(60)]


def test_taxonomia_lista_as_classes():
    r = executar("taxonomia", {}, _base(), TAX)
    assert [c["nome"] for c in r["classes"]] == ["A", "B"]
    assert r["classes"][0] == {"nome": "A", "grupo": "G", "definicao": "x"}


def test_estruturar_devolve_os_chips_e_o_grupo():
    chamar = lambda s, u: '{"classe": "A", "alternativas": ["B"], "pede_dano_moral": true, "motivo": "m"}'
    r = executar("estruturar", {"texto": " caso "}, _base(), TAX, chamar)
    assert r["estruturada"] == {"classe": "A", "alternativas": ["B"],
                                "pede_dano_moral": True, "motivo": "m"}
    assert r["grupo"] == "G"


def test_estruturar_passa_o_texto_sem_espacos_nas_pontas():
    vistos = []
    executar("estruturar", {"texto": "  caso  "}, _base(), TAX,
             lambda s, u: vistos.append(u) or '{"classe": null}')
    assert vistos == ["caso"]


@pytest.mark.parametrize("entrada", [{}, {"texto": ""}, {"texto": "   "}, {"texto": 5}])
def test_estruturar_rejeita_texto_vazio(entrada):
    with pytest.raises(EntradaInvalida, match="texto vazio"):
        executar("estruturar", entrada, _base(), TAX, lambda s, u: "")


def test_calcular_nao_chama_llm_e_traz_os_eixos():
    r = executar("calcular", {"classe": "A", "pede_dano_moral": False}, _base(), TAX)
    assert r["pede_dano_moral"] is False
    assert set(r["resultado"]) == {"consulta", "procedencia", "prazo", "dano_moral",
                                   "comparaveis"}
    assert r["resultado"]["consulta"] == {"classe": "A", "grupo": "G"}
    assert r["resultado"]["procedencia"]["degrau"] == "classe"


def test_calcular_traz_o_juizo_todo_para_situar_a_classe():
    r = executar("calcular", {"classe": "A"}, _base(), TAX)
    assert set(r["juizo"]) == {"procedencia", "prazo", "dano_moral"}
    assert r["juizo"]["procedencia"]["degrau"] == "piso"
    assert r["juizo"]["procedencia"]["n"] == 60


def test_calcular_sem_classe_e_o_piso():
    r = executar("calcular", {"classe": None}, _base(), TAX)
    assert r["resultado"]["procedencia"]["degrau"] == "piso"


def test_resultado_e_serializavel_e_enxuto():
    r = executar("calcular", {"classe": "A"}, _base(), TAX)
    texto = json.dumps(r)
    assert "linhas" not in texto and len(texto) < 20_000


def test_calcular_rejeita_classe_e_flag_invalidas():
    with pytest.raises(EntradaInvalida, match="classe desconhecida"):
        executar("calcular", {"classe": "Z"}, _base(), TAX)
    with pytest.raises(EntradaInvalida, match="pede_dano_moral"):
        executar("calcular", {"classe": "A", "pede_dano_moral": "sim"}, _base(), TAX)


def test_acao_desconhecida():
    with pytest.raises(EntradaInvalida, match="ação desconhecida"):
        executar("apagar", {}, _base(), TAX)


def test_cli_api_taxonomia_aceita_stdin_vazio_e_erro_sai_com_codigo_2():
    import subprocess, sys
    ok = subprocess.run([sys.executable, "prognosticar.py", "--api", "taxonomia"],
                        input="", capture_output=True, text=True)
    assert ok.returncode == 0 and "classes" in json.loads(ok.stdout)
    ruim = subprocess.run([sys.executable, "prognosticar.py", "--api", "calcular"],
                          input='{"classe": "Z"}', capture_output=True, text=True)
    assert ruim.returncode == 2 and "classe desconhecida" in json.loads(ruim.stdout)["erro"]
