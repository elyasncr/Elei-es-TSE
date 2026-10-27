"""Baixa os Boletins de Urna (BU Web) do TSE via API de dados abertos.

O BU e' o arquivo cru de cada secao eleitoral, com o campo DT_BU_RECEBIDO
(data/hora em que a urna transmitiu). E' o unico arquivo publico que permite
reconstruir a progressao da apuracao minuto a minuto.

Uso:
    python src/baixar_tse.py 2022 2    # 2o turno de 2022 (completo)
    python src/baixar_tse.py 2026 1    # 1o turno de 2026
"""
import sys, zipfile, io, json
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "dados" / "bruto"
API = "https://dadosabertos.tse.jus.br/api/3/action/package_show"


def recursos(ano: int, turno: int) -> list[str]:
    r = requests.get(API, params={"id": f"resultados-{ano}-boletim-de-urna"}, timeout=60)
    r.raise_for_status()
    urls = [x["url"] for x in r.json()["result"]["resources"]]
    alvo = [u for u in urls if f"_{turno}t_" in u and u.endswith(".zip")]
    if not alvo:
        disponivel = sorted({u.split("/")[-1].split("_")[1] for u in urls if u.endswith(".zip")})
        raise SystemExit(
            f"Nenhum arquivo do {turno}o turno de {ano}. Turnos publicados: {disponivel}\n"
            f"O TSE leva alguns dias/semanas para publicar os BUs apos a eleicao."
        )
    return sorted(alvo)


def baixar(ano: int, turno: int) -> None:
    pasta = DESTINO / f"{ano}_{turno}t"
    pasta.mkdir(parents=True, exist_ok=True)
    urls = recursos(ano, turno)
    print(f"{len(urls)} arquivos (UFs) para {ano} / {turno}o turno -> {pasta}")

    for i, url in enumerate(urls, 1):
        nome = url.split("/")[-1]
        uf = nome.split("_")[2]
        if list(pasta.glob(f"bweb_{turno}t_{uf}_*.csv")):
            print(f"[{i:>2}/{len(urls)}] {uf}  ja existe, pulando")
            continue
        print(f"[{i:>2}/{len(urls)}] {uf}  baixando...", end="", flush=True)
        resp = requests.get(url, timeout=600)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for membro in z.namelist():
                if membro.lower().endswith(".csv"):
                    z.extract(membro, pasta)
        print(f" ok ({len(resp.content) / 1e6:.0f} MB)")


if __name__ == "__main__":
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    turno = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    baixar(ano, turno)
