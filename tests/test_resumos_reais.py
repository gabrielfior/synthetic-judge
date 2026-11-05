"""Confere os resumos contra o corpus de verdade, sem guardar nada dele no repo.

Estes testes leem `data/sentencas_juiz.json` em tempo de execução e se autopulam
quando ele não existe — em CI, ou numa worktree sem o `data/` do repo principal.
Nenhum trecho de sentença real mora aqui; o que se afirma são propriedades.
"""
import pytest

from sj.dados import carregar
from sj.eventos import nao_classificadas
from sj.features import dispositivo, features
from sj.ficha import ficha, ficha_censurada

RESULTADOS = {"procedente", "parcialmente_procedente", "improcedente",
              "extinto_sem_merito", "extinta_execucao", "homologacao"}


@pytest.fixture(scope="module")
def corpus():
    try:
        return carregar()
    except FileNotFoundError as e:
        pytest.skip(f"corpus real indisponível: {e}")


def test_todo_processo_tem_resultado_reconhecido(corpus):
    sem = [f["processo"] for d in corpus if (f := features(d))["resultado"]
           not in RESULTADOS]
    assert sem == []


def test_nenhuma_movimentacao_fica_sem_classificacao(corpus):
    assert nao_classificadas([m for d in corpus for m in d["movimentacoes"]]) == {}


def test_toda_ficha_tem_as_tres_secoes(corpus):
    faltando = [d["processo"] for d in corpus
                if not all(s in ficha(d) for s in
                           ("## Relatório", "## Fundamentação", "## Dispositivo"))]
    assert faltando == []


def test_a_censurada_nunca_traz_o_nome_do_magistrado(corpus):
    vazam = [d["processo"] for d in corpus
             if d.get("magistrado", "").lower() in ficha_censurada(d).lower()]
    assert vazam == []


def test_a_censurada_nunca_traz_o_dispositivo(corpus):
    """Procurar por "ante o exposto" não serve: o relatório cita decisões
    interlocutórias que começam assim ("Ante o exposto, INDEFIRO o pedido de
    gratuidade") e isso é input legítimo. O que não pode aparecer é o texto do
    dispositivo da sentença."""
    def vaza(d):
        disp = " ".join(dispositivo(d["texto"]).split())
        return bool(disp) and disp[:200] in " ".join(ficha_censurada(d).split())

    assert [d["processo"] for d in corpus if vaza(d)] == []


def test_as_fichas_cabem_em_uma_fracao_do_json(corpus):
    """Alvo do doc: ~10% do volume atual, sem perder o que sustenta raciocínio."""
    import json
    bruto = len(json.dumps(corpus, ensure_ascii=False))
    resumido = sum(len(ficha(d)) for d in corpus)
    assert resumido < bruto * 0.35
