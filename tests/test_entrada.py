from collections import Counter

from sj.entrada import (ESTILOS, confusoes, estilo, limpar, metricas,
                        pedido_reescrita)


def test_estilo_e_estavel_e_equilibrado():
    ids = [f"{i:07}-00.2025.8.26.0320|2026-01-01" for i in range(900)]
    assert [estilo(i) for i in ids] == [estilo(i) for i in ids]
    c = Counter(estilo(i) for i in ids)
    assert set(c) == set(ESTILOS) and min(c.values()) > 250


def test_pedido_de_reescrita_proibe_o_que_o_advogado_nao_sabe():
    p = pedido_reescrita("  Trata-se de ação...  ", "curto")
    assert "Trata-se de ação..." in p and "1 ou 2 frases" in p
    for proibido in ("contestação", "sentença", "resultado"):
        assert proibido in p.split("RELATÓRIO:")[0]  # listados como vedados


def test_pedido_muda_a_instrucao_por_estilo():
    assert "6 a 9 frases" in pedido_reescrita("x", "detalhado")
    assert "3 a 5 frases" in pedido_reescrita("x", "medio")


def test_limpar():
    assert limpar('```\nMeu cliente...\n```') == "Meu cliente..."
    assert limpar('  "Meu cliente."  ') == "Meu cliente."
    assert limpar("Meu cliente.") == "Meu cliente."


def _l(est, v, i, gv="G", gi="G", alt=()):
    return {"estilo": est, "verdadeira": v, "inferida": i, "grupo_verdadeiro": gv,
            "grupo_inferido": gi if i else None, "alternativas": list(alt)}


def test_metricas_por_estilo():
    ls = [_l("curto", "A", "A"), _l("curto", "A", "B", alt=["A"]),
          _l("curto", "A", None), _l("medio", "A", "A"),
          _l("medio", "A", "C", gi="H")]
    m = metricas(ls)
    assert m["geral"]["n"] == 5 and m["geral"]["classe"] == 2 / 5
    assert m["curto"]["classe"] == 1 / 3 and m["curto"]["top3"] == 2 / 3
    assert m["curto"]["nao_identificada"] == 1 / 3
    assert m["medio"]["grupo"] == 1 / 2          # o segundo errou o grupo também
    assert "detalhado" not in m


def test_confusoes_ignora_acertos():
    ls = [_l("curto", "A", "A"), _l("curto", "A", "B"), _l("curto", "A", "B"),
          _l("curto", "A", None)]
    assert confusoes(ls)[0] == {"verdadeira": "A", "inferida": "B", "n": 2}
    assert len(confusoes(ls)) == 2
