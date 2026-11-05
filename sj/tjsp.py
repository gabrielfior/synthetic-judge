"""
Cliente do e-SAJ / CJPG do TJSP (Consulta de Julgados de Primeiro Grau).

Fonte pública, sem login, sem WAF, sem JS. Ver ToDo.md para a spec completa
e as pegadinhas (UTF-8, texto duplicado, filtro por juiz).
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field

import requests

BASE = "https://esaj.tjsp.jus.br/cjpg"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
PAUSA = 1.0  # segundos entre páginas; não paralelizar
RELATORIO_MINIMO = 800  # chars abaixo disso não é relatório, é despacho

BLOCO_RE = re.compile(r'<tr class="fundocinza1">(.*?)</tr>\s*</table>', re.S)
MARCADOR_RE = re.compile(r"^(SENTEN[ÇC]A|DECIS[ÃA]O|DESPACHO)", re.M)
PROC_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
CAMPOS = ("Classe", "Assunto", "Magistrado", "Comarca", "Foro", "Vara",
          "Data de Disponibilização")
# O link do inteiro teor é montado em JS a partir do name da âncora
# (cjpg/jsp/consulta.js): "cdProcesso-cdForo-nmAlias-cdDocumento".
ANCORA_PDF = re.compile(r'<a[^>]*title="Visualizar Inteiro Teor"[^>]*name="([^"]+)"')

def _frase(*variantes: str) -> re.Pattern:
    """Regex tolerante: as palavras podem estar separadas por \n, \r ou \xa0."""
    alt = "|".join(r"\s+".join(map(re.escape, v.split())) for v in variantes)
    return re.compile(f"({alt})", re.I)


FIM_RELATORIO = _frase(
    "é o relatório", "é o relatorio", "é a síntese do necessário",
    "relatório dispensado", "fundamento e decido", "passo a decidir",
    "decido.", "É o breve relatório")
INICIO_DISPOSITIVO = _frase(
    "ante o exposto", "diante do exposto", "isto posto", "isso posto",
    "pelo exposto", "posto isso", "em face do exposto", "do exposto,",
    "por todo o exposto", "assim, julgo", "portanto, julgo")


@dataclass
class Consulta:
    pesquisa_livre: str = ""
    dt_inicio: str = "01/01/2026"
    dt_fim: str = "25/08/2026"
    classes: str = ""      # classeTreeSelection.values
    assuntos: str = ""     # assuntoTreeSelection.values
    varas: str = ""        # varasTreeSelection.values
    cd_agente: str = ""    # código do magistrado; o nmAgente é decorativo

    def params(self) -> dict:
        agente = {
            "contadoragente": "1",
            "contadorMaioragente": "1",
            "cdAgente": self.cd_agente,
            "dadosConsulta.agentes[0].cdAgente": self.cd_agente,
        } if self.cd_agente else {
            "contadoragente": "0",
            "contadorMaioragente": "0",
            "cdAgente": "",
            "nmAgente": "",
        }
        return {
            "conversationId": "",
            "dadosConsulta.pesquisaLivre": self.pesquisa_livre,
            "tipoNumero": "UNIFICADO",
            "dadosConsulta.nuProcesso": "",
            "classeTreeSelection.values": self.classes,
            "assuntoTreeSelection.values": self.assuntos,
            **agente,
            "dadosConsulta.dtInicio": self.dt_inicio,
            "dadosConsulta.dtFim": self.dt_fim,
            "varasTreeSelection.values": self.varas,
            "dadosConsulta.ordenacao": "DESC",
        }


def _url_pdf(name: str, processo: str) -> str:
    """Abre a Sentença na Pasta Digital — a mesma janela do ícone de PDF no e-SAJ."""
    cd_processo, cd_foro, nm_alias, cd_documento = name.split("-")
    return (f"{BASE}/obterArquivo.do?cdProcesso={cd_processo}&cdForo={cd_foro}"
            f"&nmAlias={nm_alias}&cdDocumento={cd_documento}&nmProcesso={processo}")


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "\n", s))


def parse_bloco(bloco: str) -> dict | None:
    txt = _strip(bloco).replace("\xa0", " ").replace("\r", "")
    txt = re.sub(r"\n[ \t]*", "\n", txt)
    txt = re.sub(r"\n{2,}", "\n", txt).strip()

    proc = PROC_RE.search(txt)
    marcas = list(MARCADOR_RE.finditer(txt))
    if not proc or not marcas:
        return None
    ancora = ANCORA_PDF.search(bloco)

    # O e-SAJ repete o texto: preview truncado, depois a íntegra.
    corpo = txt[marcas[-1].start():]

    meta = {}
    for c in CAMPOS:
        m = re.search(rf"{re.escape(c)}:\n(.+)", txt)
        if m:
            meta[c.lower().replace(" ", "_")] = m.group(1).strip()

    return {
        "processo": proc.group(0),
        "tipo": marcas[-1].group(1),
        **meta,
        "url_pdf": _url_pdf(ancora.group(1), proc.group(0)) if ancora else "",
        "texto": corpo,
        "n_chars": len(corpo),
        **split_sentenca(corpo),
    }


def split_sentenca(corpo: str) -> dict:
    """Divide em relatório (proxy da peça), fundamentação e dispositivo."""
    m_disp = INICIO_DISPOSITIVO.search(corpo)
    dispositivo = corpo[m_disp.start():] if m_disp else ""
    antes = corpo[: m_disp.start()] if m_disp else corpo

    m_rel = FIM_RELATORIO.search(antes)
    relatorio, fundamentacao = (
        (antes[: m_rel.end()], antes[m_rel.end():]) if m_rel else (antes, ""))

    return {
        "relatorio": relatorio.strip(),
        "fundamentacao": fundamentacao.strip(),
        "dispositivo": dispositivo.strip(),
        "split_ok": bool(m_disp and m_rel),
    }


def de_merito(d: dict) -> bool:
    """Sentença que julga o mérito: tem relatório (o resumo do caso) e dispositivo.

    O CJPG rotula como SENTENÇA também as decisões de execução, cumprimento e
    liquidação — curtas, sem relatório, logo sem par (peça -> sentença). No
    corpus completo do magistrado-alvo elas são a maioria: a mediana de `n_chars`
    dos 24.368 julgados é 1.243.
    """
    return (d.get("tipo") == "SENTENÇA" and bool(d.get("split_ok"))
            and len(d.get("relatorio") or "") > RELATORIO_MINIMO)


def buscar(consulta: Consulta, paginas: int = 1) -> list[dict]:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get(f"{BASE}/", timeout=30)

    r = s.get(f"{BASE}/pesquisar.do", params=consulta.params(), timeout=90)
    r.encoding = "utf-8"
    htmls = [r.text]

    for p in range(2, paginas + 1):
        time.sleep(PAUSA)
        rp = s.get(f"{BASE}/trocarDePagina.do", params={"pagina": p}, timeout=90)
        rp.encoding = "utf-8"
        if not BLOCO_RE.search(rp.text):
            break  # acabaram os resultados
        htmls.append(rp.text)

    docs = []
    for h in htmls:
        for bloco in BLOCO_RE.findall(h):
            d = parse_bloco(bloco)
            if d:
                docs.append(d)
    return docs
