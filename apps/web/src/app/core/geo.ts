import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, of, shareReplay } from 'rxjs';

export interface Feature {
  properties: { codarea: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: any };
}

/** Uma forma já projetada e pronta para virar <path d="…">. */
export interface Forma { codarea: string; d: string; }

export interface Malha { formas: Forma[]; viewBox: string; }

/**
 * Carrega as malhas do IBGE e as converte em paths SVG.
 *
 * A projeção é equiretangular com correção de longitude por cos(lat média).
 * Para a faixa do Brasil (5°N a 34°S) a distorção é pequena e evita trazer uma
 * biblioteca de projeções só para desenhar um mapa de referência.
 */
@Injectable({ providedIn: 'root' })
export class Geo {
  private http = inject(HttpClient);
  private cache = new Map<string, Observable<Malha>>();

  /** Malha nacional por UF. */
  ufs(): Observable<Malha> { return this.carregar('geo/uf.json'); }

  /** Malha municipal de uma UF. */
  municipios(uf: string): Observable<Malha> { return this.carregar(`geo/mun/${uf}.json`); }

  private carregar(url: string): Observable<Malha> {
    const hit = this.cache.get(url);
    if (hit) return hit;
    const obs = this.http.get<{ features: Feature[] }>(url).pipe(
      map(fc => this.projetar(fc.features)),
      shareReplay(1),
    );
    this.cache.set(url, obs);
    return obs;
  }

  private projetar(features: Feature[]): Malha {
    // bbox em graus
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const visitar = (f: Feature, fn: (lon: number, lat: number) => void) => {
      const polis = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const poli of polis) for (const anel of poli) for (const [lon, lat] of anel) fn(lon, lat);
    };
    for (const f of features) visitar(f, (lon, lat) => {
      if (lon < minLon) minLon = lon; if (lon > maxLon) maxLon = lon;
      if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
    });

    const k = Math.cos((minLat + maxLat) / 2 * Math.PI / 180);
    const px = (lon: number) => (lon - minLon) * k;
    const py = (lat: number) => (maxLat - lat);               // y cresce para baixo
    const w = (maxLon - minLon) * k, h = maxLat - minLat;

    const r = (n: number) => Math.round(n * 1000) / 1000;      // 3 casas bastam
    const formas: Forma[] = features.map(f => {
      const polis = f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates] : f.geometry.coordinates;
      const partes: string[] = [];
      for (const poli of polis) {
        for (const anel of poli) {
          const pts = anel.map(([lon, lat]: number[]) => `${r(px(lon))},${r(py(lat))}`);
          partes.push(`M${pts.join('L')}Z`);
        }
      }
      return { codarea: f.properties.codarea, d: partes.join('') };
    });

    const pad = Math.max(w, h) * 0.02;
    return { formas, viewBox: `${-pad} ${-pad} ${w + pad * 2} ${h + pad * 2}` };
  }
}
