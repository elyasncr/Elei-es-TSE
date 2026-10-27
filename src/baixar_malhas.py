"""Baixa as malhas geograficas do IBGE para o mapa.

    apps/web/public/geo/uf.json        27 UFs (carregado no boot)
    apps/web/public/geo/mun/<UF>.json  municipios da UF (carregado sob demanda)

Qualidade 'intermediaria' no mapa nacional (as UFs ficam com contorno decente) e
'minima' nos municipios, onde ha muito mais poligonos por tela.
"""
import json
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "apps" / "web" / "public" / "geo"
BASE = "https://servicodados.ibge.gov.br/api/v3/malhas"
FMT = "application/vnd.geo+json"

UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB",
       "PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]


def baixar(url: str, destino: Path) -> int:
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    d = r.json()
    # grava compacto: o arquivo vai pela rede a cada visita
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    return len(d["features"])


def main() -> None:
    n = baixar(f"{BASE}/paises/BR?formato={FMT}&intrarregiao=UF&qualidade=intermediaria",
               DEST / "uf.json")
    print(f"uf.json: {n} features, {(DEST/'uf.json').stat().st_size/1024:.0f} KB")

    total = 0
    for i, uf in enumerate(UFS, 1):
        alvo = DEST / "mun" / f"{uf}.json"
        if alvo.exists():
            print(f"[{i:>2}/27] {uf}  ja existe"); continue
        n = baixar(f"{BASE}/estados/{uf}?formato={FMT}&intrarregiao=municipio"
                   f"&qualidade=minima", alvo)
        kb = alvo.stat().st_size / 1024
        total += kb
        print(f"[{i:>2}/27] {uf}  {n:>4} municipios  {kb:>6.0f} KB")
    print(f"\ntotal municipios: {total/1024:.1f} MB (carregados sob demanda, 1 UF por vez)")


if __name__ == "__main__":
    main()
