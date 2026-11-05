"""Onde fica o `data/`.

`data/` está no .gitignore, logo não viaja para as worktrees de
`.claude/worktrees/`. Subir a árvore até achá-lo é o mesmo truque que
`frontend/lib/corpus.ts` usa, e pela mesma razão.

O nome é `dados` e não `corpus` porque `sj.corpus` é o corpus em Parquet: este
módulo só localiza e lê o JSON que o `fetch_juiz.py` grava.
"""
from __future__ import annotations

import json
import os
import pathlib

CORPUS = "sentencas_juiz.json"


def caminho_dados(inicio: pathlib.Path | str = ".") -> pathlib.Path:
    """O primeiro `data/` subindo a partir de `inicio`. `SJ_DATA_DIR` manda."""
    if forcado := os.environ.get("SJ_DATA_DIR"):
        return pathlib.Path(forcado)

    dir_ = pathlib.Path(inicio).resolve()
    for candidato in (dir_, *dir_.parents):
        if (candidato / "data").is_dir():
            return candidato / "data"
    raise FileNotFoundError(
        f"subi de {dir_} até a raiz sem achar um diretório data/. Rode "
        f"fetch_juiz.py para gerá-lo, ou aponte SJ_DATA_DIR para ele.")


def carregar(inicio: pathlib.Path | str = ".") -> list[dict]:
    """As sentenças gravadas por `fetch_juiz.py`."""
    arquivo = caminho_dados(inicio) / CORPUS
    if not arquivo.exists():
        raise FileNotFoundError(f"{arquivo} não existe. Rode fetch_juiz.py.")
    return json.loads(arquivo.read_text(encoding="utf-8"))
