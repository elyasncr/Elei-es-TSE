"""ETL: votacao_secao_<ano>_BR.csv  ->  agregado por municipio e por UF.

Le os CSVs grandes (1,5 GB cada) em blocos e agrega. Saida pequena o bastante
para a API servir da memoria.

    python src/agregar_municipios.py
"""
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "bruto" / "secao"
PROC = RAIZ / "dados" / "processado"
COLS = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA",
        "NR_SECAO", "DS_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]
CHAVE = ["ano", "turno", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_VOTAVEL", "NM_VOTAVEL"]


def agregar(ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    arq = next((BRUTO / str(ano)).glob("*.csv"))
    votos, secoes = [], []

    for i, ch in enumerate(pd.read_csv(arq, sep=";", encoding="latin-1", usecols=COLS,
                                       dtype=str, chunksize=1_000_000, low_memory=False), 1):
        ch = ch[ch.DS_CARGO.str.upper() == "PRESIDENTE"]
        if ch.empty:
            continue
        ch["QT_VOTOS"] = pd.to_numeric(ch.QT_VOTOS, errors="coerce").fillna(0).astype("int64")
        ch["ano"] = ano
        ch["turno"] = ch.NR_TURNO.astype(int)

        votos.append(ch.groupby(CHAVE, observed=True, as_index=False).QT_VOTOS.sum())
        secoes.append(ch[["ano", "turno", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]]
                      .drop_duplicates())
        print(f"  bloco {i:>3}  acumulado {sum(len(v) for v in votos):>9,} linhas".replace(",", "."))

    v = (pd.concat(votos).groupby(CHAVE, observed=True, as_index=False).QT_VOTOS.sum()
         .rename(columns={"QT_VOTOS": "votos"}))
    s = (pd.concat(secoes).drop_duplicates()
         .groupby(["ano", "turno", "SG_UF", "CD_MUNICIPIO"], as_index=False)
         .size().rename(columns={"size": "secoes"}))
    return v, s


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    vs, ss = [], []
    for ano in (2022, 2026):
        print(f"=== {ano}")
        v, s = agregar(ano)
        vs.append(v); ss.append(s)
        for t in sorted(v.turno.unique()):
            w = v[v.turno == t]
            nom = w[~w.NM_VOTAVEL.str.upper().str.startswith("VOTO")]
            tot = nom.votos.sum()
            top = nom.groupby("NM_VOTAVEL").votos.sum().nlargest(3)
            print(f"  {t}o turno: {w.CD_MUNICIPIO.nunique():,} municipios, "
                  f"{tot:,} votos nominais".replace(",", "."))
            for n, q in top.items():
                print(f"     {n[:32]:<32} {q:>12,}  {100*q/tot:>5.2f}%".replace(",", "."))

    pd.concat(vs).to_parquet(PROC / "votos_municipio.parquet", index=False)
    pd.concat(ss).to_parquet(PROC / "secoes_municipio.parquet", index=False)
    print("\n-> dados/processado/votos_municipio.parquet + secoes_municipio.parquet")
