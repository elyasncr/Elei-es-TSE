import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Comparacao, Decomposicao, Linha, Meta, Nivel } from './modelos';

/** Filtros geográficos aplicáveis a qualquer consulta. */
export interface Filtro {
  nivel: Nivel;
  regiao?: string | null;
  uf?: string | null;
  incluirExterior?: boolean;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  private base = '/api';

  private params(f: Filtro): HttpParams {
    let p = new HttpParams().set('nivel', f.nivel);
    if (f.regiao) p = p.set('regiao', f.regiao);
    if (f.uf) p = p.set('uf', f.uf);
    if (f.incluirExterior === false) p = p.set('incluir_exterior', 'false');
    return p;
  }

  meta(): Observable<Meta> {
    return this.http.get<Meta>(`${this.base}/meta`);
  }

  agregado(ano: number, turno: number, f: Filtro): Observable<Linha[]> {
    const p = this.params(f).set('ano', ano).set('turno', turno);
    return this.http.get<Linha[]>(`${this.base}/agregado`, { params: p });
  }

  decomposicao(c: Comparacao, f: Filtro): Observable<Decomposicao> {
    const p = this.params(f)
      .set('ano_de', c.ano_de).set('turno_de', c.turno_de)
      .set('ano_para', c.ano_para).set('turno_para', c.turno_para);
    return this.http.get<Decomposicao>(`${this.base}/decomposicao`, { params: p });
  }
}

/** As comparações que fazem sentido com os dados disponíveis. */
export const COMPARACOES: Comparacao[] = [
  { rotulo: '2026: 1º → 2º turno', ano_de: 2026, turno_de: 1, ano_para: 2026, turno_para: 2,
    descricao: 'Para onde foram os votos dos eliminados no 1º turno de 2026.' },
  { rotulo: '2022: 1º → 2º turno', ano_de: 2022, turno_de: 1, ano_para: 2022, turno_para: 2,
    descricao: 'O mesmo movimento quatro anos antes, para comparar.' },
  { rotulo: '2º turno: 2022 → 2026', ano_de: 2022, turno_de: 2, ano_para: 2026, turno_para: 2,
    descricao: 'Onde a base mudou entre as duas eleições — adversários diferentes.' },
  { rotulo: '1º turno: 2022 → 2026', ano_de: 2022, turno_de: 1, ano_para: 2026, turno_para: 1,
    descricao: 'Mudança no voto de primeiro turno, sem o efeito da polarização.' },
];
