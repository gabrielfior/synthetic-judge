"""
Spike validado: baixa decisões recentes de um ministro do STF.

Descobertas:
  - jurisprudencia.stf.jus.br é protegido por AWS WAF (cookie `aws-waf-token`).
    curl direto -> 202/403. POST arbitrário via fetch() na página -> 403.
    Só funciona navegando pela SPA com browser real (Playwright resolve o desafio).
  - A SPA dispara POST /api/search/search (Elasticsearch) só quando há `queryString`.
    `ministro_facet` sozinho não dispara busca.
  - `decisao_texto` traz o inteiro teor da decisão monocrática (~9k-18k chars).

Uso: uv run python spikes/stf_fetch_decisoes.py
"""
import json
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

MINISTRO = "ALEXANDRE DE MORAES"
BASE = "decisoes"  # decisoes | acordaos | sumulas | informativos
N = 10
OUT = Path("data/stf_decisoes.json")


def search_url(ministro: str, base: str, page_size: int) -> str:
    params = {
        "base": base,
        "queryString": ministro.lower(),
        "ministro_facet": ministro,
        "pesquisa_inteiro_teor": "false",
        "sinonimo": "true",
        "plural": "true",
        "radicais": "false",
        "buscaExata": "true",
        "page": "1",
        "pageSize": str(page_size),
        "sort": "julgamento_data",
        "sortBy": "desc",
    }
    return "https://jurisprudencia.stf.jus.br/pages/search?" + urllib.parse.urlencode(params)


def fetch(ministro: str, base: str, page_size: int) -> list[dict]:
    captured: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(locale="pt-BR", user_agent=UA).new_page()
        page.on("response", lambda r: captured.append(r.json())
                if "search/search" in r.url and r.status == 200 else None)
        page.goto(search_url(ministro, base, page_size), wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(5_000)
        browser.close()
    if not captured:
        raise RuntimeError("nenhuma resposta da API capturada (WAF ou seletor mudou)")
    return [h["_source"] for h in captured[-1]["result"]["hits"]["hits"]]


def main() -> None:
    docs = fetch(MINISTRO, BASE, N)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(docs, ensure_ascii=False, indent=1))
    for d in docs:
        texto = d.get("decisao_texto") or d.get("ementa_texto") or ""
        print(f"{d['julgamento_data']} | {d['titulo']:<20} | {len(texto):>6} chars | {d['inteiro_teor_url']}")
    print(f"\n{len(docs)} decisões -> {OUT}")


if __name__ == "__main__":
    main()
