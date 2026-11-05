"""
Cliente do e-SAJ / CPOPG do TJSP (Consulta de Processos do 1º Grau).

Complementa o CJPG (`sj.tjsp`): lá está o texto da sentença, aqui está a capa
do processo e a linha do tempo das movimentações — a matéria-prima da
jurimetria (quanto tempo até a liminar, até a sentença).

Pegadinhas descobertas na marra:
  - `search.do` só devolve o processo com o conjunto MÍNIMO de parâmetros.
    Mandar `numeroDigitoAnoUnificado`/`foroNumeroUnificado` faz o e-SAJ
    devolver o formulário de busca de volta, com HTTP 200 e sem erro nenhum.
    Mandar `gateway=true` joga pro login do sajcas.
  - Os campos da capa são `<div id=...>`, não `<span>`. Casar até o primeiro
    `</span>` arrasta o menu inteiro da página junto.
  - A tabela de movimentações aparece duas vezes: um preview com as últimas e
    o `tabelaTodasMovimentacoes` escondido com todas. Parsear as duas duplica.
"""
from __future__ import annotations

import html
import re
import time
import unicodedata

import requests

from sj.tjsp import UA

ESAJ = "https://esaj.tjsp.jus.br"
BASE = f"{ESAJ}/cpopg"

# id do <div> na página -> nome do campo na nossa saída
CAPA = {
    "numeroProcesso": "processo",
    "classeProcesso": "classe",
    "assuntoProcesso": "assunto",
    "foroProcesso": "foro",
    "varaProcesso": "vara",
    "juizProcesso": "juiz",
    "areaProcesso": "area",
    "dataHoraDistribuicaoProcesso": "distribuicao",
    "valorAcaoProcesso": "valor_acao",
    "numeroControleProcesso": "controle",
}

MOV_LINHA = re.compile(
    r'<td[^>]*class="dataMovimentacao"[^>]*>(.*?)</td>.*?'
    r'<td[^>]*class="descricaoMovimentacao"[^>]*>(.*?)</td>', re.S)
PARTE_LINHA = re.compile(
    r'<span class="mensagemExibindo tipoDeParticipacao">(.*?)</span>.*?'
    r'<td[^>]*class="nomeParteEAdvogado"[^>]*>(.*?)</td>', re.S)
ROTULO_ADVOGADO = re.compile(r'<span class="mensagemExibindo">Advogad[oa]s?:.*?</span>', re.S)
# Link do documento da movimentação. Só abre na sessão que acabou de visitar o
# show.do do processo — fora dela o e-SAJ responde "não foi possível validar o
# seu acesso". No navegador isso é transparente; num script, reusar a sessão.
DOC_MOV = re.compile(r'<a[^>]*class="linkMovVincProc"[^>]*href="([^"]+)"')
# O detalhe da movimentação vem como linhas "Chave: valor" — Relação, Teor do
# ato, Advogados(s), Tipo da Petição, Número do Diário, Situação, Local.
CHAVE_META = re.compile(r"^([A-Za-zÀ-ú()\s/]{2,40}?):\s*(.*)$")
CHAVES = {"advogados_s": "advogados"}  # "Advogados(s)" viraria advogados_s
# Allowlist: sem ela, uma frase que abre linha ("Diante do exposto: ...") vira
# rótulo. Rótulo novo que não esteja aqui não some — fica no `detalhe`, inteiro.
ROTULOS = frozenset({
    "relacao", "teor_do_ato", "advogados", "data", "data_da_publicacao",
    "data_da_disponibilizacao", "numero_do_diario", "pagina", "tipo_da_peticao",
    "situacao", "local", "modelo", "destinatario", "diligencia", "juntada_de_ar",
    "foro_destino", "processo_principal",
})
BR = re.compile(r"<br\s*/?>", re.I)

# Incidentes (execução/liquidação de sentença) trocam a capa por um cabeçalho
# próprio: sem numeroProcesso, sem classeProcesso, sem juiz.
INCIDENTE = re.compile(
    r'<span class="unj-label">([^<]+)</span>\s*<div>\s*'
    r'<span class="unj-larger">\s*(.*?)\s*\((\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\)', re.S)
PRINCIPAL = re.compile(
    r'Processo principal.*?<a[^>]*>\s*(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', re.S)


class ProcessoIndisponivel(RuntimeError):
    """Segredo de justiça, número inexistente, ou o e-SAJ devolveu o formulário."""


class RespostaTruncada(ProcessoIndisponivel):
    """Capa veio, bloco de movimentações não. Intermitente — vale tentar de novo."""


def _chave(rotulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", rotulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", sem_acento.lower())).strip("_")
    return CHAVES.get(slug, slug)


def _meta(detalhe: str) -> dict:
    """Linhas 'Chave: valor'; linha sem chave continua o valor anterior."""
    meta, atual = {}, None
    for linha in html.unescape(re.sub(r"<[^>]+>", "", detalhe)).splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if (m := CHAVE_META.match(linha)) and _chave(m.group(1)) in ROTULOS:
            atual = _chave(m.group(1))
            meta[atual] = m.group(2).strip()
        elif atual:
            meta[atual] = f"{meta[atual]} {linha}".strip()
    return meta


def _texto(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _conteudo(pagina: str, i: int, tag: str) -> str:
    """Conteúdo a partir de `i` até o `</tag>` que fecha a abertura, com aninhamento."""
    abre = re.compile(rf"<{tag}\b", re.I)
    fecha = re.compile(rf"</{tag}\s*>", re.I)
    nivel, pos = 1, i
    while True:
        a, f = abre.search(pagina, pos), fecha.search(pagina, pos)
        if not f:
            return pagina[i:]
        if a and a.start() < f.start():
            nivel, pos = nivel + 1, a.end()
        else:
            nivel, pos = nivel - 1, f.end()
            if not nivel:
                return pagina[i:f.start()]


def _por_id(pagina: str, elem_id: str) -> str:
    m = re.search(rf'<(\w+)[^>]*\bid="{elem_id}"[^>]*>', pagina)
    return _conteudo(pagina, m.end(), m.group(1)) if m else ""


def _movimentacoes(pagina: str) -> list[dict]:
    if "tabelaUltimasMovimentacoes" not in pagina:
        # Sem aviso, sem erro HTTP: alguns nós do e-SAJ servem a capa sozinha.
        raise RespostaTruncada("página sem o bloco de movimentações")
    bloco = _por_id(pagina, "tabelaTodasMovimentacoes") or _por_id(pagina, "tabelaUltimasMovimentacoes")
    movs = []
    for data, descricao in MOV_LINHA.findall(bloco):
        titulo, *resto = BR.split(descricao, maxsplit=1)  # o detalhe vem depois do <br />
        detalhe = resto[0] if resto else ""
        doc = DOC_MOV.search(descricao)
        movs.append({"data": _texto(data),
                     "titulo": _texto(titulo),
                     "detalhe": _texto(detalhe),
                     "meta": _meta(detalhe),
                     "url_documento": ESAJ + html.unescape(doc.group(1)) if doc else ""})
    return movs


def _partes(pagina: str) -> list[dict]:
    bloco = _por_id(pagina, "tableTodasPartes") or _por_id(pagina, "tablePartesPrincipais")
    partes = []
    for tipo, celula in PARTE_LINHA.findall(bloco):
        nome, *blocos_adv = ROTULO_ADVOGADO.split(celula)
        advogados = [a for b in blocos_adv for p in BR.split(b) if (a := _texto(p))]
        partes.append({"tipo": _texto(tipo), "nome": _texto(nome), "advogados": advogados})
    return partes


def _capa_incidente(pagina: str) -> dict:
    m = INCIDENTE.search(pagina)
    if not m:
        return {}
    principal = PRINCIPAL.search(pagina)
    return {"incidente": _texto(m.group(1)),
            "classe": _texto(m.group(2)),
            "processo": m.group(3),
            "processo_principal": principal.group(1) if principal else ""}


def parse_processo(pagina: str) -> dict:
    capa = {campo: _texto(_por_id(pagina, elem_id)) for elem_id, campo in CAPA.items()}
    capa = {"incidente": "", "processo_principal": "", **capa}
    if not capa["processo"]:
        capa.update(_capa_incidente(pagina))
    if not capa["processo"]:
        raise ProcessoIndisponivel("página sem capa de processo")
    return {**capa,
            "partes": _partes(pagina),
            "movimentacoes": _movimentacoes(pagina)}


def nova_sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get(f"{BASE}/open.do", timeout=30)
    return s


def _buscar_uma_vez(numero: str, s: requests.Session) -> dict:
    r = s.get(f"{BASE}/search.do", timeout=60, params={
        "cbPesquisa": "NUMPROC",
        "dadosConsulta.valorConsulta": numero,
        "dadosConsulta.tipoNroProcesso": "UNIFICADO",
    })
    r.encoding = "utf-8"
    r.raise_for_status()
    if "/show.do" not in r.url:
        raise ProcessoIndisponivel(f"{numero}: e-SAJ não abriu o processo ({r.url})")
    return parse_processo(r.text)


def buscar_processo(numero: str, tentativas: int = 8, pausa: float = 3.0) -> dict:
    """Capa + movimentações de um processo pelo número unificado.

    Cada tentativa usa uma sessão nova: a resposta truncada parece vir de
    afinidade de sessão com um nó ruim, então reusar a sessão repete o erro.
    """
    for n in range(1, tentativas + 1):
        try:
            return _buscar_uma_vez(numero, nova_sessao())
        except RespostaTruncada:
            if n == tentativas:
                raise
            time.sleep(pausa * n)
    raise AssertionError("inalcançável")
