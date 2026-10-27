"""Regras de negocio. Nao sabe nada de HTTP nem de parquet."""
import pandas as pd
from repositorio import agregar, chave_e_nome, meta, painel


def registros(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    """DataFrame -> list[dict] com NaN virando None.

    Campos opcionais (cd_ibge do exterior, uf de um agregado por regiao) saem do
    pandas como float nan, que nao e' str nem None e o Pydantic rejeita.
    """
    return df[cols].astype(object).where(pd.notna(df[cols]), None).to_dict("records")


def pleitos() -> list[dict]:
    df = painel()
    m = meta()
    out = []
    for (ano, turno), w in df.groupby(["ano", "turno"]):
        v = w.validos.sum()
        out.append({
            "ano": int(ano), "turno": int(turno),
            "esq": m[str(ano)]["esq"], "dir": m[str(ano)]["dir"],
            "pct_esq": round(100 * w.esq.sum() / v, 3),
            "pct_dir": round(100 * w.dir.sum() / v, 3),
            "validos": int(v), "comparecimento": int(w.comparecimento.sum()),
        })
    return out


def linhas(ano: int, turno: int, nivel: str, **f) -> list[dict]:
    g = chave_e_nome(agregar(ano, turno, nivel, **f), nivel)
    cols = ["id", "nome", "uf", "regiao", "cd_ibge", "esq", "dir", "outros",
            "branco_nulo", "validos", "comparecimento", "pct_esq", "pct_dir"]
    return registros(g, cols)


def swing(ano_de: int, turno_de: int, ano_para: int, turno_para: int,
          nivel: str, **f) -> list[dict]:
    """Variacao de apoio entre dois pleitos, no nivel pedido.

    swing_esq > 0  => a esquerda ganhou pontos percentuais naquele recorte.
    Compara participacao relativa (%), nao votos absolutos: o eleitorado muda
    entre pleitos e votos brutos nao sao comparaveis.
    """
    a = chave_e_nome(agregar(ano_de, turno_de, nivel, **f), nivel)
    b = chave_e_nome(agregar(ano_para, turno_para, nivel, **f), nivel)
    chaves = ["id", "nome", "cd_ibge"] + (["uf", "regiao"] if nivel != "regiao" else ["regiao"])
    chaves = [c for c in dict.fromkeys(chaves) if c in a.columns]

    j = a.merge(b, on=chaves, suffixes=("_de", "_para"))
    j["swing_esq"] = (j.pct_esq_para - j.pct_esq_de).round(3)
    j["delta_comparecimento"] = (
        100 * (j.comparecimento_para - j.comparecimento_de)
        / j.comparecimento_de.where(j.comparecimento_de > 0)).round(3)
    j = j.rename(columns={"esq_de": "votos_esq_de", "esq_para": "votos_esq_para"})

    cols = chaves + ["pct_esq_de", "pct_esq_para", "swing_esq", "validos_de",
                     "validos_para", "votos_esq_de", "votos_esq_para",
                     "delta_comparecimento"]
    for c in ("uf", "regiao", "cd_ibge"):
        if c not in cols:
            j[c] = None
            cols.append(c)
    return registros(j.sort_values("swing_esq"), cols)


def decomposicao(ano_de: int, turno_de: int, ano_para: int, turno_para: int,
                 nivel: str = "uf", **f) -> dict:
    """Quanto da variacao nacional veio de cada recorte.

    contribuicao_h = peso_h * swing_h, com peso_h = fatia do recorte nos votos
    validos do pleito de chegada. Soma das contribuicoes ~ swing nacional
    (a diferenca e' o efeito de mudanca de peso entre os pleitos).
    """
    s = pd.DataFrame(swing(ano_de, turno_de, ano_para, turno_para, nivel, **f))
    total = s.validos_para.sum()
    s["peso"] = (100 * s.validos_para / total).round(3)
    s["contribuicao"] = (s.swing_esq * s.validos_para / total).round(4)

    nac_de = 100 * s.votos_esq_de.sum() / s.validos_de.sum()
    nac_para = 100 * s.votos_esq_para.sum() / s.validos_para.sum()
    return {
        "swing_nacional": round(nac_para - nac_de, 3),
        "pct_esq_de": round(nac_de, 3),
        "pct_esq_para": round(nac_para, 3),
        "soma_contribuicoes": round(s.contribuicao.sum(), 3),
        "itens": registros(s.sort_values("contribuicao"), list(s.columns)),
    }
