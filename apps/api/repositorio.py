"""Camada de acesso a dados.

Unica parte que sabe que os dados vivem em parquet. Carrega uma vez na memoria
(22 mil linhas) e serve consultas. Trocar por um banco mudaria so este arquivo.
"""
import json
from functools import cache
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PROC = RAIZ / "dados" / "processado"

NIVEIS = {
    "regiao": ["regiao"],
    "uf": ["regiao", "uf"],
    "municipio": ["regiao", "uf", "cd_mun", "municipio", "cd_ibge"],
}

# Codigo IBGE de cada UF — as malhas geograficas vem chaveadas por ele.
UF_IBGE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
IBGE_UF = {v: k for k, v in UF_IBGE.items()}
SOMAR = ["esq", "dir", "outros", "branco_nulo", "validos", "comparecimento", "secoes"]


@cache
def painel() -> pd.DataFrame:
    df = pd.read_parquet(PROC / "painel.parquet")
    df["secoes"] = df.secoes.fillna(0).astype("int64")
    return df


@cache
def meta() -> dict:
    return json.loads((PROC / "meta.json").read_text(encoding="utf-8"))


def filtrar(df: pd.DataFrame, regiao: str | None = None, uf: str | None = None,
            incluir_exterior: bool = True) -> pd.DataFrame:
    if not incluir_exterior:
        df = df[df.uf != "ZZ"]
    if regiao:
        df = df[df.regiao == regiao]
    if uf:
        df = df[df.uf == uf]
    return df


def agregar(ano: int, turno: int, nivel: str, **f) -> pd.DataFrame:
    """Agrega o painel no nivel pedido para um pleito."""
    if nivel not in NIVEIS:
        raise ValueError(f"nivel invalido: {nivel}")
    d = filtrar(painel().query("ano == @ano and turno == @turno"), **f)
    g = d.groupby(NIVEIS[nivel], as_index=False)[SOMAR].sum()
    g["pct_esq"] = (100 * g.esq / g.validos.where(g.validos > 0)).round(3)
    g["pct_dir"] = (100 * g.dir / g.validos.where(g.validos > 0)).round(3)
    return g


def chave_e_nome(g: pd.DataFrame, nivel: str) -> pd.DataFrame:
    """Normaliza qualquer nivel para as colunas id/nome."""
    g = g.copy()
    if nivel == "regiao":
        g["id"], g["nome"], g["uf"] = g.regiao, g.regiao, None
        g["cd_ibge"] = None
    elif nivel == "uf":
        g["id"], g["nome"] = g.uf, g.uf
        g["cd_ibge"] = g.uf.map(IBGE_UF)
    else:
        g["id"] = g.uf + "-" + g.cd_mun.astype(str)
        g["nome"] = g.municipio
    return g
