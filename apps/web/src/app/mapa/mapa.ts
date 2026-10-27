import { DecimalPipe } from '@angular/common';
import { Component, computed, input, output, signal } from '@angular/core';
import { Malha } from '../core/geo';
import { ItemDecomposicao, Metrica } from '../core/modelos';
import { escalaAuto } from './escala';

@Component({
  selector: 'app-mapa',
  imports: [DecimalPipe],
  templateUrl: './mapa.html',
  styleUrl: './mapa.css',
})
export class Mapa {
  malha = input<Malha | null>(null);
  /** chave = código IBGE da área */
  valores = input<Map<string, ItemDecomposicao>>(new Map());
  rotuloEsq = input('Esquerda');
  rotuloDir = input('Direita');
  escuro = input(false);
  metrica = input<Metrica>('variacao');
  podeEntrar = input(true);

  entrar = output<ItemDecomposicao>();

  hover = signal<ItemDecomposicao | null>(null);
  pos = signal({ x: 0, y: 0 });

  /** Campo e centro de referência de cada métrica. */
  private cfg = computed(() => {
    switch (this.metrica()) {
      case 'chegada': return { campo: (i: ItemDecomposicao) => i.pct_esq_para,
                               centro: 50, sufixo: '%', neutro: false };
      case 'partida': return { campo: (i: ItemDecomposicao) => i.pct_esq_de,
                               centro: 50, sufixo: '%', neutro: false };
      default:        return { campo: (i: ItemDecomposicao) => i.swing_esq,
                               centro: 0, sufixo: 'pp', neutro: true };
    }
  });

  escala = computed(() => {
    const { campo, centro, sufixo, neutro } = this.cfg();
    return escalaAuto([...this.valores().values()].map(campo),
                      this.escuro(), this.rotuloEsq(), this.rotuloDir(),
                      centro, sufixo, neutro);
  });

  unidade = computed(() => this.cfg().sufixo === '%'
    ? `% dos votos válidos de ${this.rotuloEsq()}` : 'pontos percentuais');

  formas = computed(() => {
    const m = this.malha(); if (!m) return [];
    const vals = this.valores(); const { cor } = this.escala();
    const { campo } = this.cfg();
    return m.formas.map(f => {
      const item = vals.get(f.codarea) ?? null;
      return { ...f, item, cor: cor(item ? campo(item) : null) };
    });
  });

  aoMover(e: MouseEvent, item: ItemDecomposicao | null): void {
    this.hover.set(item);
    const alvo = (e.currentTarget as SVGElement).ownerSVGElement?.parentElement;
    const r = alvo?.getBoundingClientRect();
    if (r) this.pos.set({ x: e.clientX - r.left, y: e.clientY - r.top });
  }

  aoSair(): void { this.hover.set(null); }

  aoClicar(item: ItemDecomposicao | null): void {
    if (item && this.podeEntrar()) this.entrar.emit(item);
  }
}
