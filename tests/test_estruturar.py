from sj.estruturar import carregar_taxonomia, interpretar, sistema

V = {"A", "B", "C"}


def test_taxonomia_versionada_tem_29_classes_com_grupo():
    t = carregar_taxonomia()
    assert len(t) == 29
    assert all(c["nome"] and c["definicao"] and c["grupo"] for c in t)
    assert len({c["nome"] for c in t}) == 29


def test_sistema_lista_classes_com_definicao():
    s = sistema([{"nome": "A", "definicao": "x", "grupo": "G"}])
    assert "- A: x" in s and '"classe": null' in s


def test_interpretar_resposta_boa():
    e = interpretar('```json\n{"classe": "A", "alternativas": ["B", "C", "A"], '
                    '"pede_dano_moral": true, "motivo": "porque"}\n```', V)
    assert (e.classe, e.alternativas, e.pede_dano_moral, e.motivo) == (
        "A", ["B", "C"], True, "porque")


def test_classe_fora_da_lista_vira_none_e_nao_e_aproximada():
    e = interpretar('{"classe": "Inventada", "alternativas": ["Z", "B"]}', V)
    assert e.classe is None and e.alternativas == ["B"]


def test_classe_null_explicita():
    assert interpretar('{"classe": null, "pede_dano_moral": null}', V).classe is None


def test_resposta_quebrada_nao_levanta():
    for r in ("não sei", "[1,2]", '{"classe": 5, "pede_dano_moral": "sim"}', ""):
        e = interpretar(r, V)
        assert e.classe is None and e.pede_dano_moral is None
