import { DecimalPipe } from '@angular/common';
import { Component, computed, input, output, signal } from '@angular/core';
import { Malha } from '../core/geo';
import { ItemDecomposicao } from '../core/modelos';
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
  podeEntrar = input(true);

  entrar = output<ItemDecomposicao>();

  hover = signal<ItemDecomposicao | null>(null);
  pos = signal({ x: 0, y: 0 });

  escala = computed(() => escalaAuto(
    [...this.valores().values()].map(i => i.swing_esq),
    this.escuro(), this.rotuloEsq(), this.rotuloDir()));

  formas = computed(() => {
    const m = this.malha(); if (!m) return [];
    const vals = this.valores(); const { cor } = this.escala();
    return m.formas.map(f => {
      const item = vals.get(f.codarea) ?? null;
      return { ...f, item, cor: cor(item?.swing_esq) };
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
