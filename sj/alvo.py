"""O magistrado-alvo, configurado por ambiente (nunca no código).

`JUDGE_ID` é o `cdAgente` do e-SAJ (CJPG); `JUDGE_NAME` é o nome como o e-SAJ o
grafa. Ambos vêm do `.env` do repo ou do ambiente; veja `.env.example`.
"""
from sj.llm import _env


def juiz_id() -> str:
    v = _env().get("JUDGE_ID", "").strip()
    if not v:
        raise SystemExit("defina JUDGE_ID (cdAgente do e-SAJ) no .env; veja .env.example")
    return v


def juiz_nome() -> str:
    v = _env().get("JUDGE_NAME", "").strip()
    if not v:
        raise SystemExit("defina JUDGE_NAME no .env; veja .env.example")
    return v
