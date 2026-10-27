"""De-para entre o codigo de municipio do TSE e o codigo do IBGE.

O TSE usa codigo proprio (5 digitos); as malhas geograficas do IBGE usam o
codigo IBGE (7 digitos). O cruzamento e' feito por nome normalizado dentro da
mesma UF, que resolve 99,7% dos casos; o resto e' tratado por similaridade e,
onde a similaridade erra, por correcao explicita.

Saida: dados/processado/municipios_ibge.parquet
"""
import difflib
import unicodedata
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "dados" / "processado"
API = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

# Casos em que o nome do TSE nao se aproxima do nome do IBGE por escrita.
# Boa Saude e' o nome anterior de Januario Cicco (RN); por similaridade o
# vizinho mais parecido seria "Lagoa Salgada", que e' outro municipio.
# Verificados um a um contra a lista completa da UF no IBGE:
#   RN BOA SAUDE  -> nome anterior de Januario Cicco. Por similaridade o vizinho
#                    mais parecido seria "Lagoa Salgada", que e' outro municipio.
#   GO BOM JESUS  -> GO tem um unico "Bom Jesus": Bom Jesus de Goias. No TSE as
#                    duas grafias dividem o mesmo codigo (92690).
#   RR SAO LUIZ   -> RR tem 15 municipios e um unico "Sao Luiz": Sao Luiz do Anaua.
CORRECOES = {
    ("RN", "BOA SAUDE"): "2405306",
    ("GO", "BOM JESUS"): "5203500",
    ("RR", "SAO LUIZ"): "1400605",
}

LIMIAR = 0.90   # abaixo disso a sugestao automatica nao e' aceita sem revisao


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().replace("'", " ").replace("-", " ").split())


def uf_de(m: dict) -> str | None:
    n = m.get("microrregiao") or m.get("regiao-imediata")
    while n and "UF" not in n:
        n = n.get("mesorregiao") or n.get("regiao-intermediaria")
    return n["UF"]["sigla"] if n else None


def main() -> None:
    bruto = requests.get(API, timeout=180).json()
    ibge = pd.DataFrame([{"cd_ibge": str(m["id"]), "uf": uf_de(m), "nome_ibge": m["nome"]}
                         for m in bruto])
    ibge["n"] = ibge.nome_ibge.map(norm)
    print(f"IBGE: {len(ibge)} municipios")

    p = pd.read_parquet(PROC / "painel.parquet")
    tse = (p[p.uf != "ZZ"][["uf", "cd_mun", "municipio", "ano"]]
           .sort_values("ano").groupby(["uf", "cd_mun"], as_index=False)
           .municipio.last())                      # grafia do pleito mais recente
    tse["n"] = tse.municipio.map(norm)
    print(f"TSE : {len(tse)} municipios")

    j = tse.merge(ibge[["uf", "n", "cd_ibge", "nome_ibge"]], on=["uf", "n"], how="left")
    print(f"match exato: {j.cd_ibge.notna().sum()}/{len(j)}")

    baixa = []
    for idx in j.index[j.cd_ibge.isna()]:
        r = j.loc[idx]
        chave = (r.uf, r.n)
        if chave in CORRECOES:
            alvo = ibge[ibge.cd_ibge == CORRECOES[chave]].iloc[0]
            j.loc[idx, ["cd_ibge", "nome_ibge"]] = [alvo.cd_ibge, alvo.nome_ibge]
            print(f"  correcao explicita: {r.uf} {r.municipio} -> {alvo.nome_ibge}")
            continue
        cand = ibge[ibge.uf == r.uf]
        best = difflib.get_close_matches(r.n, cand.n.tolist(), n=1, cutoff=0.5)
        if not best:
            continue
        sc = difflib.SequenceMatcher(None, r.n, best[0]).ratio()
        alvo = cand[cand.n == best[0]].iloc[0]
        if sc >= LIMIAR:
            j.loc[idx, ["cd_ibge", "nome_ibge"]] = [alvo.cd_ibge, alvo.nome_ibge]
            print(f"  similaridade {sc:.3f}: {r.uf} {r.municipio} -> {alvo.nome_ibge}")
        else:
            baixa.append((r.uf, r.municipio, alvo.nome_ibge, sc))

    if baixa:
        print("\nABAIXO DO LIMIAR — nao aceitos automaticamente:")
        for uf, a, b, sc in baixa:
            print(f"  {uf} {a} -> {b} ({sc:.3f})")

    falta = j.cd_ibge.isna().sum()
    dupes = j.cd_ibge.dropna().duplicated().sum()
    print(f"\nresolvidos: {len(j)-falta}/{len(j)}  | sem match: {falta} | "
          f"cd_ibge repetido: {dupes}")
    if dupes:
        d = j[j.cd_ibge.duplicated(keep=False) & j.cd_ibge.notna()]
        print(d[["uf", "municipio", "nome_ibge", "cd_ibge"]].to_string(index=False))

    j[["uf", "cd_mun", "municipio", "cd_ibge", "nome_ibge"]].to_parquet(
        PROC / "municipios_ibge.parquet", index=False)
    print(f"-> {PROC / 'municipios_ibge.parquet'}")


if __name__ == "__main__":
    main()
