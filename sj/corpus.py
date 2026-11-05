"""
Corpus de julgados em Parquet.

Duas decisões de esquema, por motivos opostos.

O `texto` de um julgado já contém relatório, fundamentação e dispositivo — as
três chaves que o `tjsp.split_sentenca` devolve são fatias dele. Guardar as
quatro colunas duplica o texto inteiro e dobra o arquivo (25,2 MB contra
12,6 MB nos 24.368 julgados do magistrado-alvo), então aqui guardamos `texto`
mais os dois offsets e reconstruímos na leitura.

Já `distribuicao` e `dias_tramitacao` são gravados mesmo sendo deriváveis, pelo
motivo inverso: eles **não** são deriváveis de uma linha sozinha. A data de
distribuição é estimada por `cnj.distribuicao`, que ancora a interpolação na
menor e maior sequência de cada foro-ano do conjunto inteiro — então recalcular
sobre um recorte devolve outro número. Materializar congela a estimativa no
universo em que ela foi feita, que é o que torna a coluna reproduzível.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sj import cnj

# Baixa cardinalidade: vale dicionário. `assunto` tem algumas centenas de
# valores em dezenas de milhares de linhas, então entra também.
CATEGORICAS = ("tipo", "classe", "assunto", "comarca", "foro", "vara", "magistrado")
TEXTUAIS = ("processo", "url_pdf")

AUSENTE = -1  # offset de parte que não existe (sentença sem dispositivo achável)


def _offsets(doc: dict) -> tuple[int, int]:
    """Onde o relatório termina e o dispositivo começa, dentro de `texto`."""
    txt = doc["texto"]
    fim_rel = txt.find(doc["relatorio"]) + len(doc["relatorio"]) if doc["relatorio"] else AUSENTE
    ini_disp = txt.find(doc["dispositivo"]) if doc["dispositivo"] else AUSENTE
    return fim_rel, ini_disp


def _data(s: str | None) -> dt.date | None:
    return dt.datetime.strptime(s, "%d/%m/%Y").date() if s else None


def tabela(docs: list[dict]) -> pa.Table:
    offs = [_offsets(d) for d in docs]
    # Ancorado no conjunto que está sendo gravado — ver o cabeçalho do módulo.
    faixas = cnj.faixas([d.get("processo", "") for d in docs])
    datas = [_data(d.get("data_de_disponibilização")) for d in docs]
    dist = [cnj.distribuicao(d.get("processo", ""), faixas) for d in docs]
    dias = [(s - x).days if x and s and s > x else None for x, s in zip(dist, datas)]
    cols = {
        "processo": pa.array([d.get("processo") for d in docs], pa.string()),
        "data": pa.array(datas, pa.date32()),
    }
    for c in CATEGORICAS:
        cols[c] = pa.array([d.get(c) or None for d in docs], pa.string()).dictionary_encode()
    cols["url_pdf"] = pa.array([d.get("url_pdf") or None for d in docs], pa.string())
    cols["n_chars"] = pa.array([int(d["n_chars"]) for d in docs], pa.int32())
    cols["split_ok"] = pa.array([bool(d["split_ok"]) for d in docs], pa.bool_())
    cols["texto"] = pa.array([d.get("texto") for d in docs], pa.string())
    cols["fim_relatorio"] = pa.array([o[0] for o in offs], pa.int32())
    cols["inicio_dispositivo"] = pa.array([o[1] for o in offs], pa.int32())
    cols["distribuicao"] = pa.array(dist, pa.date32())
    cols["dias_tramitacao"] = pa.array(dias, pa.int32())
    return pa.table(cols)


def escrever(docs: list[dict], caminho: str | Path) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela(docs), caminho, compression="zstd", compression_level=19)
    return caminho


def partes(texto: str, fim_relatorio: int, inicio_dispositivo: int) -> dict[str, str]:
    """Refaz relatório/fundamentação/dispositivo a partir dos offsets."""
    r, s = fim_relatorio, inicio_dispositivo
    if r == AUSENTE:
        # Sem marcador de fim de relatório: tudo antes do dispositivo é relatório.
        return {"relatorio": (texto if s == AUSENTE else texto[:s]).strip(),
                "fundamentacao": "",
                "dispositivo": texto[s:].strip() if s != AUSENTE else ""}
    return {"relatorio": texto[:r].strip(),
            "fundamentacao": texto[r:s if s != AUSENTE else None].strip(),
            "dispositivo": texto[s:].strip() if s != AUSENTE else ""}


def ler(caminho: str | Path) -> list[dict]:
    """Devolve os julgados com relatório/fundamentação/dispositivo reconstruídos."""
    t = pq.read_table(caminho).to_pylist()
    for d in t:
        d.update(partes(d["texto"], d.pop("fim_relatorio"), d.pop("inicio_dispositivo")))
    return t
