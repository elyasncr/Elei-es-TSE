"""Monta o painel analitico que a API serve.

Entrada : dados/processado/votos_municipio.parquet (saida do ETL)
Saida   : dados/processado/painel.parquet   1 linha por (ano, turno, municipio)
          dados/processado/painel_uf.parquet

Convencao: 'esq' = Lula (13), 'dir' = o adversario que foi ao 2o turno naquele
ano (Jair Bolsonaro em 2022, Flavio Bolsonaro em 2026). Os rotulos reais vao
no arquivo de metadados para a UI exibir.
"""
import json
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "dados" / "processado"

# Nome de urna (NM_URNA_CANDIDATO do TSE). O arquivo votacao_secao traz so o
# nome civil completo, do qual "Lula" nao e' derivavel por regra. Ambos os
# Bolsonaro concorreram pelo numero 22, entao a chave inclui o ano.
NOME_URNA = {
    (2022, "13"): "Lula",  (2022, "22"): "Jair Bolsonaro",
    (2026, "13"): "Lula",  (2026, "22"): "Flávio Bolsonaro",
}

REGIAO = {
    **dict.fromkeys(["AC","AM","AP","PA","RO","RR","TO"], "Norte"),
    **dict.fromkeys(["AL","BA","CE","MA","PB","PE","PI","RN","SE"], "Nordeste"),
    **dict.fromkeys(["DF","GO","MS","MT"], "Centro-Oeste"),
    **dict.fromkeys(["ES","MG","RJ","SP"], "Sudeste"),
    **dict.fromkeys(["PR","RS","SC"], "Sul"),
    "ZZ": "Exterior",
}


def main() -> None:
    v = pd.read_parquet(PROC / "votos_municipio.parquet")
    v["eh_voto"] = v.NM_VOTAVEL.str.upper().str.startswith("VOTO")

    meta, linhas = {}, []
    for ano in sorted(v.ano.unique()):
        d2 = v[(v.ano == ano) & (v.turno == 2) & (~v.eh_voto)]
        top = d2.groupby(["NR_VOTAVEL", "NM_VOTAVEL"]).votos.sum().nlargest(2)
        (nr_esq, nm_esq), (nr_dir, nm_dir) = top.index[0], top.index[1]
        if nr_dir == "13":                                  # garante esq = 13
            (nr_esq, nm_esq), (nr_dir, nm_dir) = (nr_dir, nm_dir), (nr_esq, nm_esq)
        def rotular(nr: str, nome: str) -> dict:
            return {"nr": nr, "nome": nome,
                    "apelido": NOME_URNA.get((int(ano), nr), nome.split()[0].title())}

        meta[int(ano)] = {"esq": rotular(nr_esq, nm_esq), "dir": rotular(nr_dir, nm_dir)}

        d = v[v.ano == ano]
        chave = ["ano", "turno", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]
        # so nominais no pivot: branco/nulo usam NR_VOTAVEL 95/96, que passariam
        # no teste .isdigit() e seriam contados duas vezes (em 'outros' e em
        # 'branco_nulo'). Filtrar por eh_voto, nao pelo formato do numero.
        p = d[~d.eh_voto].pivot_table(index=chave, columns="NR_VOTAVEL", values="votos",
                                      aggfunc="sum", fill_value=0).reset_index()
        cols_nom = [c for c in p.columns if isinstance(c, str) and c.isdigit()]
        brancos_nulos = (d[d.eh_voto].groupby(chave, as_index=False).votos.sum()
                         .rename(columns={"votos": "branco_nulo"}))

        out = p[chave].copy()
        out["esq"] = p.get(nr_esq, 0)
        out["dir"] = p.get(nr_dir, 0)
        out["outros"] = p[cols_nom].sum(axis=1) - out.esq - out.dir
        out = out.merge(brancos_nulos, on=chave, how="left")
        out["branco_nulo"] = out.branco_nulo.fillna(0).astype("int64")
        linhas.append(out)

    df = pd.concat(linhas, ignore_index=True)
    df = df.rename(columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd_mun", "NM_MUNICIPIO": "municipio"})
    df["regiao"] = df.uf.map(REGIAO).fillna("Exterior")
    df["validos"] = df.esq + df.dir + df.outros
    df["comparecimento"] = df.validos + df.branco_nulo
    df["pct_esq"] = (100 * df.esq / df.validos.where(df.validos > 0)).round(4)
    df["pct_dir"] = (100 * df.dir / df.validos.where(df.validos > 0)).round(4)

    sec = pd.read_parquet(PROC / "secoes_municipio.parquet").rename(
        columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd_mun"})
    df = df.merge(sec, on=["ano", "turno", "uf", "cd_mun"], how="left")

    # Seis municipios mudaram de grafia entre 2022 e 2026 (CAMACA->CAMACAN,
    # MUNHOZ DE MELO->MELLO, ...). Sem canonizar, o mesmo municipio vira duas
    # linhas e some das comparacoes entre anos, que casam por codigo E nome.
    canon = (df.sort_values("ano").groupby(["uf", "cd_mun"], as_index=False)
               .municipio.last().rename(columns={"municipio": "nome_canon"}))
    df = df.merge(canon, on=["uf", "cd_mun"], how="left")
    df["municipio"] = df.nome_canon.fillna(df.municipio)
    df = df.drop(columns="nome_canon")

    # codigo IBGE, para casar com as malhas geograficas do mapa
    cw = PROC / "municipios_ibge.parquet"
    if cw.exists():
        df = df.merge(pd.read_parquet(cw)[["uf", "cd_mun", "cd_ibge"]],
                      on=["uf", "cd_mun"], how="left")
    else:
        df["cd_ibge"] = None
        print("aviso: municipios_ibge.parquet ausente — rode src/crosswalk_ibge.py")

    df.to_parquet(PROC / "painel.parquet", index=False)

    num = ["esq", "dir", "outros", "branco_nulo", "validos", "comparecimento", "secoes"]
    uf = df.groupby(["ano", "turno", "regiao", "uf"], as_index=False)[num].sum()
    uf["pct_esq"] = (100 * uf.esq / uf.validos).round(4)
    uf["pct_dir"] = (100 * uf.dir / uf.validos).round(4)
    uf.to_parquet(PROC / "painel_uf.parquet", index=False)

    (PROC / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                    encoding="utf-8")

    print(f"painel.parquet    {len(df):,} linhas".replace(",", "."))
    print(f"painel_uf.parquet {len(uf):,} linhas".replace(",", "."))
    for ano, m in meta.items():
        print(f"  {ano}: {m['esq']['nome']} ({m['esq']['nr']}) x "
              f"{m['dir']['nome']} ({m['dir']['nr']})")
    print("\nNacional por pleito (% validos):")
    for (a, t), w in df.groupby(["ano", "turno"]):
        print(f"  {a} {t}t: esq {100*w.esq.sum()/w.validos.sum():.2f}%  "
              f"dir {100*w.dir.sum()/w.validos.sum():.2f}%")


if __name__ == "__main__":
    main()
