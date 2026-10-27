"""API HTTP. So traduz query string -> servico -> JSON."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import repositorio as repo
import servicos as svc
from modelos import Linha, LinhaSwing, Pleito

app = FastAPI(title="Apuração TSE", version="1.0",
              description="Resultados presidenciais por região — 2022 e 2026.")

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["GET"], allow_headers=["*"])

NIVEL = Query("uf", pattern="^(regiao|uf|municipio)$")


@app.get("/api/meta")
def get_meta():
    df = repo.painel()
    ufs = (df[["uf", "regiao"]].drop_duplicates().sort_values("uf")
           .to_dict("records"))
    return {"pleitos": svc.pleitos(),
            "regioes": sorted(df.regiao.unique().tolist()),
            "ufs": ufs}


@app.get("/api/pleitos", response_model=list[Pleito])
def get_pleitos():
    return svc.pleitos()


@app.get("/api/agregado", response_model=list[Linha])
def get_agregado(ano: int, turno: int, nivel: str = NIVEL,
                 regiao: str | None = None, uf: str | None = None,
                 incluir_exterior: bool = True):
    try:
        return svc.linhas(ano, turno, nivel, regiao=regiao, uf=uf,
                          incluir_exterior=incluir_exterior)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/swing", response_model=list[LinhaSwing])
def get_swing(ano_de: int, turno_de: int, ano_para: int, turno_para: int,
              nivel: str = NIVEL, regiao: str | None = None,
              uf: str | None = None, incluir_exterior: bool = True):
    """Ganho/perda de apoio entre dois pleitos quaisquer."""
    try:
        return svc.swing(ano_de, turno_de, ano_para, turno_para, nivel,
                         regiao=regiao, uf=uf, incluir_exterior=incluir_exterior)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/decomposicao")
def get_decomposicao(ano_de: int, turno_de: int, ano_para: int, turno_para: int,
                     nivel: str = NIVEL, regiao: str | None = None,
                     uf: str | None = None, incluir_exterior: bool = True):
    """Quanto cada recorte contribuiu para a variacao nacional."""
    return svc.decomposicao(ano_de, turno_de, ano_para, turno_para, nivel,
                            regiao=regiao, uf=uf, incluir_exterior=incluir_exterior)


@app.get("/api/saude")
def saude():
    df = repo.painel()
    return {"status": "ok", "linhas": len(df),
            "pleitos": sorted({f"{a}-{t}t" for a, t in
                               zip(df.ano, df.turno)})}
