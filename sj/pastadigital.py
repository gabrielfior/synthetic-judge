"""
Download dos PDFs da Pasta Digital do e-SAJ.

O link que o e-SAJ expõe (`cjpg/obterArquivo.do` para a sentença,
`cpopg/abrirDocumentoVinculadoMovimentacao.do` para os documentos de cada
movimentação) não devolve o PDF: devolve o visualizador, uma página que traz
um `var requestScope = [...]` em JS. É de lá que sai o `parametros`, e só então
`pastadigital/getPDF.do?<parametros>` entrega os bytes.

Duas condições que o e-SAJ não explica:
  - o download tem que sair da MESMA sessão que abriu o visualizador;
  - `parametros` vai como query string crua, não como um valor único urlencoded
    (funciona dos dois jeitos, mas a SPA manda cru).
"""
from __future__ import annotations

import json
import re
import unicodedata

import requests

from sj.cpopg import ESAJ
from sj.tjsp import UA

GETPDF = f"{ESAJ}/pastadigital/getPDF.do"
SCOPE_RE = re.compile(r"var requestScope = (\[.*?\]);", re.S)


class DocumentoIndisponivel(RuntimeError):
    """O visualizador não trouxe documento — acesso negado ou documento sigiloso."""


def parametros(visualizador: str) -> list[str]:
    """Um `parametros` por faixa de páginas do documento."""
    m = SCOPE_RE.search(visualizador)
    if not m:
        raise DocumentoIndisponivel("visualizador sem requestScope")
    pars = [filho["data"]["parametros"]
            for raiz in json.loads(m.group(1))
            for filho in raiz.get("children", [])]
    if not pars:
        raise DocumentoIndisponivel("visualizador sem páginas")
    return pars


def nome_arquivo(processo: str, titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", sem_acento.lower())).strip("-")
    return f"{processo}_{slug}.pdf"


def nova_sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get(f"{ESAJ}/cjpg/", timeout=30)
    return s


def baixar(url_visualizador: str, s: requests.Session) -> bytes:
    """Bytes do PDF. Documento em várias faixas vem concatenado numa lista."""
    v = s.get(url_visualizador, timeout=60)
    v.encoding = "utf-8"
    v.raise_for_status()

    pedacos = []
    for par in parametros(v.text):
        r = s.get(f"{GETPDF}?{par}", headers={"Referer": v.url}, timeout=120)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF-"):
            raise DocumentoIndisponivel(f"getPDF não devolveu PDF ({len(r.content)} bytes)")
        pedacos.append(r.content)

    if len(pedacos) > 1:
        raise DocumentoIndisponivel(
            f"documento em {len(pedacos)} faixas de páginas; juntar exige um lib de PDF")
    return pedacos[0]
