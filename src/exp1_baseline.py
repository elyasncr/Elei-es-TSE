"""Experimento 1 — baselines sem rede neural.

Dado X% da apuracao, estimar o resultado final. Qualquer rede neural precisa
bater estes numeros para justificar sua existencia.

Nada aqui usa o resultado final. A unica informacao externa e' QT_APTOS (o
cadastro eleitoral, publico ANTES da eleicao), que diz o tamanho de cada secao
que ainda falta. E' exatamente o que um analista teria ao vivo.

Estimadores:
  B0 naive          parcial bruto — o que a TV mostra
  B1 razao/UF       estimador de razao pos-estratificado por UF
  B2 razao/municipio  idem, estratos mais finos
  B3 shrinkage      B2 com encolhimento para a UF quando o estrato tem pouco dado
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "dados" / "processado"
CORTES = [0.5, 1, 2, 5, 10, 25, 50, 75, 90]
K_SHRINK = 3000.0  # pseudo-contagem (em votos) usada no encolhimento


def estimar(df: pd.DataFrame, k: int, chave: str | None, shrink: bool = False) -> float:
    """% final estimado do candidato A vendo apenas as k primeiras secoes.

    Estimador de razao por estrato: para cada estrato, a taxa de votos validos
    por apto observada nas secoes apuradas e' extrapolada para as faltantes.
    """
    ap = df.iloc[:k]
    falta = df.iloc[k:]
    a_ap, b_ap = ap.a.sum(), ap.b.sum()

    if chave is None or len(falta) == 0:
        return 100 * a_ap / (a_ap + b_ap)

    p_nac = a_ap / (a_ap + b_ap)

    g = ap.groupby(chave, observed=True).agg(a=("a", "sum"), b=("b", "sum"),
                                             aptos=("aptos", "sum"))
    g["val"] = g.a + g.b
    g["p"] = g.a / g.val
    g["taxa"] = g.val / g.aptos.replace(0, np.nan)      # validos por apto no estrato

    if shrink:
        uf_de = ap.groupby(chave, observed=True).SG_UF.first()
        guf = ap.groupby("SG_UF", observed=True).agg(a=("a", "sum"), b=("b", "sum"))
        p_uf = (guf.a / (guf.a + guf.b)).reindex(uf_de.values).to_numpy()
        p_uf = np.where(np.isnan(p_uf), p_nac, p_uf)
        g["p"] = (g.val * g.p + K_SHRINK * p_uf) / (g.val + K_SHRINK)

    f = falta.groupby(chave, observed=True).aptos.sum().rename("aptos_falta")
    j = f.to_frame().join(g[["p", "taxa"]])

    # estrato sem nenhuma secao apurada: cai para a media nacional parcial
    taxa_nac = (a_ap + b_ap) / max(ap.aptos.sum(), 1)
    j["p"] = j.p.fillna(p_nac)
    j["taxa"] = j.taxa.fillna(taxa_nac)

    val_falta = j.aptos_falta * j.taxa
    a_tot = a_ap + (val_falta * j.p).sum()
    tot = (a_ap + b_ap) + val_falta.sum()
    return 100 * a_tot / tot


def main(ano: int, turno: int) -> None:
    s = pd.read_parquet(PROC / f"secoes_{ano}_{turno}t.parquet")
    cands = sorted((c for c in s.columns
                    if c.startswith("votos_") and c.split("_")[1].isdigit()),
                   key=lambda c: s[c].sum(), reverse=True)[:2]
    nome_a, nome_b = (c.split("_")[1] for c in cands)

    df = pd.DataFrame({
        "a": s[cands[0]].to_numpy(np.int64),
        "b": s[cands[1]].to_numpy(np.int64),
        "aptos": s.aptos.to_numpy(np.int64),
        "SG_UF": s.SG_UF.astype("category"),
        "mun": (s.SG_UF.astype(str) + s.CD_MUNICIPIO.astype(str)).astype("category"),
        "recebido": s.recebido,
    }).sort_values("recebido").reset_index(drop=True)

    n = len(df)
    final = 100 * df.a.sum() / (df.a.sum() + df.b.sum())
    print(f"{ano} / {turno}o turno — {n:,} secoes — final: {nome_a}={final:.2f}%"
          .replace(",", "."))
    print(f"\nErro absoluto em pontos percentuais (candidato {nome_a}):\n")
    print(f"{'% apur.':>8} {'B0 naive':>10} {'B1 UF':>9} {'B2 munic':>10} "
          f"{'B3 shrink':>11}   {'ganho B3/B0':>12}")

    linhas = []
    for c in CORTES:
        k = max(int(n * c / 100), 1)
        e = [abs(estimar(df, k, *args) - final) for args in
             ((None,), ("SG_UF",), ("mun",), ("mun", True))]
        linhas.append((c, *e))
        print(f"{c:>7}% {e[0]:>10.3f} {e[1]:>9.3f} {e[2]:>10.3f} {e[3]:>11.3f}"
              f"   {e[0]/max(e[3],1e-9):>11.1f}x")

    r = pd.DataFrame(linhas, columns=["pct", "B0", "B1", "B2", "B3"])
    PROC.mkdir(exist_ok=True)
    r.to_csv(PROC / f"exp1_baseline_{ano}_{turno}t.csv", index=False)

    # a que ponto da apuracao cada metodo fica estavel abaixo de 0,5 pp
    print()
    for col in ("B0", "B1", "B2", "B3"):
        ok = r.pct[(r[col] < 0.5)]
        # exige que continue abaixo de 0,5 em todos os cortes seguintes
        est = next((p for p in ok if (r[col][r.pct >= p] < 0.5).all()), None)
        print(f"  {col}: erro < 0,5 pp de forma estavel a partir de "
              + (f"{est:g}% apurado" if est else "nunca (dentro dos cortes testados)"))
    print(f"\ncsv -> dados/processado/exp1_baseline_{ano}_{turno}t.csv")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2022,
         int(sys.argv[2]) if len(sys.argv) > 2 else 2)
