"""Transforma os BUs brutos em (a) tabela por secao e (b) a serie da apuracao.

Saidas em dados/processado/:
    secoes_<ano>_<turno>t.parquet  -> 1 linha por secao eleitoral
    serie_<ano>_<turno>t.parquet   -> curva acumulada = o grafico da TV

A serie e' construida ordenando as secoes por DT_BU_RECEBIDO e acumulando os
votos. Isso reproduz a "PROGRESSAO DA APURACAO" que as emissoras exibem.
"""
import sys
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "bruto"
PROC = RAIZ / "dados" / "processado"

COLUNAS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
    "DS_CARGO_PERGUNTA", "DS_TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL",
    "QT_VOTOS", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES",
    "DT_BU_RECEBIDO", "DT_ABERTURA", "DT_ENCERRAMENTO", "NR_URNA_EFETIVADA",
]


def carregar(ano: int, turno: int) -> pd.DataFrame:
    pasta = BRUTO / f"{ano}_{turno}t"
    arquivos = sorted(pasta.glob("*.csv"))
    if not arquivos:
        raise SystemExit(f"Nada em {pasta}. Rode antes: python src/baixar_tse.py {ano} {turno}")

    partes = []
    for i, arq in enumerate(arquivos, 1):
        df = pd.read_csv(arq, sep=";", encoding="latin-1", usecols=COLUNAS,
                         dtype=str, low_memory=False)
        df = df[df["DS_CARGO_PERGUNTA"] == "Presidente"]
        partes.append(df)
        print(f"[{i:>2}/{len(arquivos)}] {arq.name[:24]:<24} {len(df):>8} linhas")
    return pd.concat(partes, ignore_index=True)


def por_secao(bruto: pd.DataFrame) -> pd.DataFrame:
    """Pivota: 1 linha por secao, 1 coluna por candidato + brancos/nulos."""
    for c in ("QT_VOTOS", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"):
        bruto[c] = pd.to_numeric(bruto[c], errors="coerce").fillna(0).astype(int)
    for c in ("DT_BU_RECEBIDO", "DT_ABERTURA", "DT_ENCERRAMENTO"):
        bruto[c] = pd.to_datetime(bruto[c], format="%d/%m/%Y %H:%M:%S", errors="coerce")

    chave = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO"]

    # rotulo da coluna: numero do candidato, ou "Branco"/"Nulo"
    bruto["coluna"] = bruto["NR_VOTAVEL"].where(
        bruto["DS_TIPO_VOTAVEL"] == "Nominal", bruto["DS_TIPO_VOTAVEL"]
    )
    votos = (bruto.pivot_table(index=chave, columns="coluna", values="QT_VOTOS",
                               aggfunc="sum", fill_value=0)
                  .add_prefix("votos_").reset_index())

    meta = (bruto.groupby(chave, as_index=False)
                 .agg(aptos=("QT_APTOS", "max"),
                      comparecimento=("QT_COMPARECIMENTO", "max"),
                      abstencoes=("QT_ABSTENCOES", "max"),
                      recebido=("DT_BU_RECEBIDO", "min"),
                      abertura=("DT_ABERTURA", "min"),
                      encerramento=("DT_ENCERRAMENTO", "max"),
                      urna=("NR_URNA_EFETIVADA", "first")))

    s = meta.merge(votos, on=chave).sort_values("recebido").reset_index(drop=True)
    s["minuto"] = ((s["recebido"] - s["recebido"].min()).dt.total_seconds() // 60).astype("Int64")
    return s


def serie(secoes: pd.DataFrame) -> pd.DataFrame:
    """Curva acumulada na ordem de chegada dos BUs."""
    cand = sorted(c for c in secoes.columns
                  if c.startswith("votos_") and c.split("_")[1].isdigit())
    ac = secoes[cand].cumsum()
    validos = ac.sum(axis=1)

    out = pd.DataFrame({
        "minuto": secoes["minuto"],
        "recebido": secoes["recebido"],
        "secoes_apuradas": range(1, len(secoes) + 1),
        "pct_secoes": 100 * pd.Series(range(1, len(secoes) + 1)) / len(secoes),
        "votos_validos": validos,
    })
    for c in cand:
        out[f"pct_{c.split('_')[1]}"] = (100 * ac[c] / validos).round(4)
    return out


if __name__ == "__main__":
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    turno = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    PROC.mkdir(parents=True, exist_ok=True)

    s = por_secao(carregar(ano, turno))
    s.to_parquet(PROC / f"secoes_{ano}_{turno}t.parquet", index=False)
    print(f"\n{len(s):,} secoes -> secoes_{ano}_{turno}t.parquet")

    t = serie(s)
    t.to_parquet(PROC / f"serie_{ano}_{turno}t.parquet", index=False)
    print(f"{len(t):,} pontos -> serie_{ano}_{turno}t.parquet")

    pcts = [c for c in t.columns if c.startswith("pct_") and c != "pct_secoes"]
    print(f"\nResultado final: " + "  ".join(f"{c}={t[c].iloc[-1]:.2f}%" for c in pcts))
    print(f"Janela de apuracao: {t['recebido'].min()}  ->  {t['recebido'].max()}")
