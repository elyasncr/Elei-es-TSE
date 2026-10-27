"""Experimento 0 — separar o que e' matematica do que e' informacao.

Tres paineis:
  A) a curva real da apuracao (o grafico da TV)
  B) a mesma curva com a ordem das urnas EMBARALHADA, varias vezes
  C) o funil teorico (+-1.96 erro-padrao de uma amostragem aleatoria)

Se a curva real sair do envelope de B/C, a ordem de chegada carrega informacao
que a aleatoriedade nao explica. E' esse excesso que uma rede neural pode aprender.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "dados" / "processado"
FIG = RAIZ / "figuras"
RNG = np.random.default_rng(42)
N_SHUFFLE = 30


def curva(votos_a: np.ndarray, votos_b: np.ndarray, ordem: np.ndarray) -> np.ndarray:
    """% acumulado do candidato A seguindo uma dada ordem de urnas."""
    a = np.cumsum(votos_a[ordem])
    t = a + np.cumsum(votos_b[ordem])
    return np.where(t > 0, 100 * a / np.maximum(t, 1), np.nan)


def main(ano: int, turno: int) -> None:
    s = pd.read_parquet(PROC / f"secoes_{ano}_{turno}t.parquet")
    cands = sorted(c for c in s.columns
                   if c.startswith("votos_") and c.split("_")[1].isdigit())
    top = sorted(cands, key=lambda c: s[c].sum(), reverse=True)[:2]
    a_col, b_col = top
    nome_a, nome_b = a_col.split("_")[1], b_col.split("_")[1]

    s = s.sort_values("recebido").reset_index(drop=True)
    va = s[a_col].to_numpy(np.int64)
    vb = s[b_col].to_numpy(np.int64)
    n = len(s)
    x = 100 * np.arange(1, n + 1) / n
    final = 100 * va.sum() / (va.sum() + vb.sum())

    real = curva(va, vb, np.arange(n))
    shuf = np.stack([curva(va, vb, RNG.permutation(n)) for _ in range(N_SHUFFLE)])

    # funil teorico: amostragem aleatoria sem reposicao de urnas
    p = final / 100
    tam = (va + vb).mean()
    k = np.arange(1, n + 1)
    fpc = np.sqrt(np.maximum((n - k) / (n - 1), 0))          # correcao de populacao finita
    ep = 100 * np.sqrt(p * (1 - p) / (k * tam)) * fpc * 2.2  # 2.2 ~ efeito de desenho
    envelope = 1.96 * ep

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    lim = (final - 12, final + 12)

    for ax, titulo in zip(axes, [
        f"A) ordem real de chegada",
        f"B) ordem embaralhada ({N_SHUFFLE}x)",
        "C) funil teorico (amostra aleatoria)"]):
        ax.axhline(final, color="#888", ls="--", lw=1, zorder=1)
        ax.set_xscale("log"); ax.set_xlim(0.05, 100); ax.set_ylim(*lim)
        ax.set_xlabel("% de secoes apuradas (escala log)")
        ax.set_title(titulo, fontsize=11)
        ax.grid(alpha=.2)

    axes[0].plot(x, real, color="#c0392b", lw=1.6, zorder=3)
    for c in shuf:
        axes[1].plot(x, c, color="#2980b9", lw=.7, alpha=.35)
    axes[2].fill_between(x, final - envelope, final + envelope,
                         color="#27ae60", alpha=.25)
    axes[2].plot(x, final + envelope, color="#27ae60", lw=1)
    axes[2].plot(x, final - envelope, color="#27ae60", lw=1)

    axes[0].set_ylabel(f"% dos votos validos — candidato {nome_a}")
    fig.suptitle(
        f"Apuracao {ano} / {turno}o turno — {n:,} secoes — final {nome_a}={final:.2f}% "
        f"vs {nome_b}={100-final:.2f}%".replace(",", "."), fontsize=13)
    fig.tight_layout()
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"exp0_funil_{ano}_{turno}t.png", dpi=130)

    # --- quantificacao ---
    print(f"\nFinal: candidato {nome_a} = {final:.2f}%   ({n:,} secoes)".replace(",", "."))
    print(f"\n{'% apur.':>8} {'real':>9} {'erro real':>10} {'erro embaralhado (p50 / p95)':>30}")
    for alvo in (0.1, 0.5, 1, 5, 10, 25, 50, 75, 90):
        i = max(int(n * alvo / 100) - 1, 0)
        e_real = abs(real[i] - final)
        e_shuf = np.abs(shuf[:, i] - final)
        print(f"{alvo:>7}% {real[i]:>8.2f}% {e_real:>9.2f} "
              f"{np.median(e_shuf):>17.2f} / {np.percentile(e_shuf, 95):>8.2f}")

    # em quantos % da apuracao a curva real fica fora do envelope do shuffle?
    p95 = np.percentile(np.abs(shuf - final), 95, axis=0)
    fora = np.abs(real - final) > p95
    jan = fora[int(n * .001):int(n * .5)]
    print(f"\nCurva real fora do p95 do embaralhado em {100*jan.mean():.1f}% "
          f"do intervalo 0,1%-50% da apuracao.")
    print(f"figura -> figuras/exp0_funil_{ano}_{turno}t.png")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2022,
         int(sys.argv[2]) if len(sys.argv) > 2 else 2)
