"""Cliente das duas inferências usadas pelos evals e pelo pipeline.

`default` é a inferência configurada no `.env` (OpenAI-compatible, deepseek); `zen` é o
OpenCode Zen (Anthropic Messages). Credenciais vêm do `.env` do repo, com o
ambiente por cima — nunca de argumento de linha de comando.
"""
import os
import pathlib
import sys
import time

import requests

MODELOS = {"default": "deepseek-v4.1-flash", "zen": "claude-haiku-5-5"}
RETRIAVEIS = (429, 500, 502, 503, 529)


def _env(caminho: str = ".env") -> dict[str, str]:
    """O `.env` do repo como dicionário; o ambiente tem precedência."""
    p = pathlib.Path(caminho)
    arquivo = {}
    if p.exists():
        for linha in p.read_text().splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                k, v = linha.split("=", 1)
                arquivo[k.strip()] = v.strip().strip("\"'")
    return {**arquivo, **os.environ}


def _post(sessao: requests.Session, url: str, headers: dict, corpo: dict,
          timeout: int = 120) -> dict:
    """POST com 5 tentativas em 429/5xx e em falha de rede (timeout, conexão).

    Num run de ~1.900 chamadas paralelas, um ReadTimeout isolado derrubou o
    script inteiro: o retry só olhava o status HTTP.
    """
    erro: Exception | None = None
    for tentativa in range(5):
        try:
            r = sessao.post(url, json=corpo, headers=headers, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as e:
            erro = e
            time.sleep(2 ** tentativa)
            continue
        if r.status_code in RETRIAVEIS:
            erro = requests.HTTPError(f"HTTP {r.status_code}", response=r)
            time.sleep(2 ** tentativa)
            continue
        r.raise_for_status()
        return r.json()
    raise erro or RuntimeError("sem resposta")


def cliente(provedor: str, env: dict[str, str], raciocinio: str):
    """(url, headers, monta, le) do provedor. Falta de chave encerra com mensagem."""
    if provedor == "default":
        chave = env.get("INFERENCE_API_KEY")
        base = env.get("INFERENCE_BASE_URL")
        if not (chave and base):
            sys.exit("faltam INFERENCE_API_KEY/_BASE_URL no .env")

        def monta(modelo, system, relatorio):
            # sem `reasoning_effort` o deepseek gasta até 4 mil tokens pensando
            # numa classificação e ainda trunca 1 em 4 respostas vazias
            return {"model": modelo, "temperature": 0,
                    "reasoning_effort": raciocinio,
                    "max_tokens": 200 if raciocinio == "none" else 8000,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": relatorio}]}

        def le(j):
            u = j.get("usage", {})
            return j["choices"][0]["message"]["content"] or "", {
                "input_tokens": u.get("prompt_tokens", 0),
                "output_tokens": u.get("completion_tokens", 0)}

        return (f"{base.rstrip('/')}/chat/completions",
                {"Authorization": f"Bearer {chave}"}, monta, le)

    chave = env.get("OPENCODE_API_KEY")
    if not chave:
        sys.exit("falta OPENCODE_API_KEY (chave em https://opencode.ai/auth)")
    base = env.get("SJ_BASE_URL", "https://opencode.ai/zen/v1")

    def monta(modelo, system, relatorio):
        return {"model": modelo, "max_tokens": 200, "temperature": 0,
                "system": [{"type": "text", "text": system,
                            "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": relatorio}]}

    def le(j):
        return j["content"][0]["text"], j.get("usage", {})

    return (f"{base.rstrip('/')}/messages",
            {"x-api-key": chave, "anthropic-version": "2023-06-01"}, monta, le)
