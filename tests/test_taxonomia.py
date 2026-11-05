import math

import pytest

from sj.taxonomia import (assunto_pelo_cluster, brier_global_loo, brier_loo,
                          dividir, ic_diferenca, interpretar_categoria,
                          interpretar_taxonomia, kappa, nmi, pedido_proposta,
                          sistema_classificar, trecho)


def _cs(n):
    return [{"processo": f"{i:07}-00.2025.8.26.0320", "relatorio": f"Vistos. Caso {i}."}
            for i in range(n)]


def test_dividir_e_deterministico_e_particiona():
    cs = _cs(500)
    d1, a1 = dividir(cs)
    d2, a2 = dividir(list(reversed(cs)))
    assert {c["processo"] for c in d1} == {c["processo"] for c in d2}
    assert len(d1) + len(a1) == 500
    assert not {c["processo"] for c in d1} & {c["processo"] for c in a1}
    assert 0.2 < len(d1) / 500 < 0.4


def test_dividir_nao_muda_quando_o_corpus_cresce():
    cs = _cs(300)
    d_antes, _ = dividir(cs[:200])
    d_depois, _ = dividir(cs)
    assert {c["processo"] for c in d_antes} <= {c["processo"] for c in d_depois}


def test_trecho_tira_o_vistos_e_corta():
    assert trecho("Vistos.\n\nTrata-se   de ação.", 100) == "Trata-se de ação."
    assert len(trecho("a" * 1000, 50)) == 50


def test_pedido_proposta_numera_os_trechos():
    system, user = pedido_proposta(_cs(2))
    assert "[1] Caso 0." in user and "[2] Caso 1." in user
    assert "18" in system and "30" in system


def _tax(n):
    return '{"categorias": [' + ",".join(
        f'{{"nome": "C{i}", "definicao": "d{i}"}}' for i in range(n)) + "]}"


def test_interpretar_taxonomia():
    cats = interpretar_taxonomia("```json\n" + _tax(10) + "\n```")
    assert [c["nome"] for c in cats][:2] == ["C0", "C1"]


@pytest.mark.parametrize("resp", [
    "sem json", _tax(3), '{"categorias": "x"}',
    '{"categorias": [{"nome": "A"}]}',
    '{"categorias": [' + ",".join(['{"nome": "A", "definicao": "d"}'] * 10) + "]}",
])
def test_interpretar_taxonomia_rejeita_o_que_nao_e_confiavel(resp):
    with pytest.raises(ValueError):
        interpretar_taxonomia(resp)


def test_interpretar_categoria():
    assert interpretar_categoria('{"categoria": "A"}', {"A"}) == "A"
    assert interpretar_categoria('{"categoria": "Z"}', {"A"}) is None
    assert interpretar_categoria("não sei", {"A"}) is None


def test_sistema_classificar_lista_definicoes():
    s = sistema_classificar([{"nome": "A", "definicao": "x"}])
    assert "- A: x" in s


def test_kappa():
    assert kappa(list("aabb"), list("aabb")) == 1.0
    assert kappa(list("aabb"), list("abab")) == pytest.approx(0.0)
    assert math.isnan(kappa([], []))


def test_nmi_extremos():
    assert nmi(list("aabb"), list("xxyy")) == pytest.approx(1.0)
    assert nmi(list("aabb"), list("xyxy")) == pytest.approx(0.0)


def test_assunto_pelo_cluster_leave_one_out():
    # cluster 1 é quase todo "A"; cluster 2 é misto
    clusters = [1, 1, 1, 1, 2, 2]
    assuntos = ["A", "A", "A", "B", "A", "B"]
    # acerta os três "A" do cluster 1; erra o "B" dele; no cluster 2 os
    # restos são unitários e o "mais frequente" do outro é o oposto
    assert assunto_pelo_cluster(clusters, assuntos) == pytest.approx(3 / 6)


def test_brier_loo_grupo_informativo_vence_o_global():
    grupos = ["x"] * 20 + ["y"] * 20
    y = [1] * 20 + [0] * 20
    com = sum(brier_loo(grupos, y)) / 40
    sem = sum(brier_global_loo(y)) / 40
    assert com < sem


def test_brier_loo_nao_explode_com_grupo_unitario():
    erros = brier_loo(["a", "b", "b", "b"], [1, 0, 0, 1])
    assert all(0 <= e <= 1 for e in erros)


def test_ic_diferenca():
    m, lo, hi = ic_diferenca([0.1] * 50, [0.3] * 50)
    assert m == pytest.approx(-0.2) and lo <= m <= hi
    m, lo, hi = ic_diferenca([0.1, 0.5] * 50, [0.5, 0.1] * 50)
    assert lo < 0 < hi  # diferença nula: o IC cruza zero


def test_lotes_cobrem_tudo_sem_repetir():
    from sj.taxonomia import lotes
    cs = _cs(10)
    fatias = lotes(cs, 4)
    assert [len(f) for f in fatias] == [4, 4, 2]
    assert [c for f in fatias for c in f] == cs


def test_pedido_fusao_junta_as_candidatas_de_todos_os_lotes():
    from sj.taxonomia import pedido_fusao
    system, user = pedido_fusao([[{"nome": "A", "definicao": "a"}],
                                 [{"nome": "B", "definicao": "b"}]])
    assert "- A: a" in user and "- B: b" in user
    assert "18" in system and "30" in system
