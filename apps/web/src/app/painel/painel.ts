import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { of, switchMap } from 'rxjs';
import { Api, COMPARACOES, Filtro } from '../core/api';
import { Geo } from '../core/geo';
import { Comparacao, Decomposicao, ItemDecomposicao, Meta, Nivel } from '../core/modelos';
import { Mapa } from '../mapa/mapa';

@Component({
  selector: 'app-painel',
  imports: [FormsModule, DecimalPipe, Mapa],
  templateUrl: './painel.html',
  styleUrl: './painel.css',
})
export class Painel {
  private api = inject(Api);
  private geo = inject(Geo);

  readonly comparacoes = COMPARACOES;
  readonly niveis: { v: Nivel; r: string }[] = [
    { v: 'regiao', r: 'Região' }, { v: 'uf', r: 'Estado' }, { v: 'municipio', r: 'Município' },
  ];

  // --- estado ---
  meta = signal<Meta | null>(null);
  dados = signal<Decomposicao | null>(null);
  carregando = signal(false);
  erro = signal<string | null>(null);

  vista = signal<'mapa' | 'lista'>('mapa');
  comparacao = signal<Comparacao>(COMPARACOES[0]);
  nivelLista = signal<Nivel>('uf');
  regiao = signal<string | null>(null);
  uf = signal<string | null>(null);
  ordenarPor = signal<'swing' | 'contribuicao' | 'nome'>('swing');
  limite = signal(40);
  escuro = signal(false);

  /** No mapa o nível é consequência do zoom: Brasil → UFs, dentro de uma UF → municípios. */
  nivel = computed<Nivel>(() =>
    this.vista() === 'mapa' ? (this.uf() ? 'municipio' : 'uf') : this.nivelLista());

  /** O que o mapa deve desenhar agora. Declarado antes de `malha` de propósito:
   *  campos de classe inicializam em ordem. */
  private fonteMalha = computed(() => ({ vista: this.vista(), uf: this.uf() }));

  malha = toSignal(
    toObservable(this.fonteMalha).pipe(
      switchMap(({ vista, uf }) =>
        vista !== 'mapa' ? of(null) : uf ? this.geo.municipios(uf) : this.geo.ufs())),
    { initialValue: null });

  constructor() {
    this.api.meta().subscribe({
      next: m => this.meta.set(m),
      error: () => this.erro.set('Não consegui falar com a API. Ela está rodando na porta 8000?'),
    });

    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const sincTema = () => this.escuro.set(
      document.documentElement.dataset['theme'] === 'dark' ||
      (mq.matches && document.documentElement.dataset['theme'] !== 'light'));
    sincTema();
    mq.addEventListener('change', sincTema);

    effect(() => this.buscar());
  }

  private buscar(): void {
    const f: Filtro = {
      nivel: this.nivel(),
      regiao: this.vista() === 'mapa' ? null : this.regiao(),
      uf: this.uf(),
    };
    this.carregando.set(true);
    this.api.decomposicao(this.comparacao(), f).subscribe({
      next: d => { this.dados.set(d); this.carregando.set(false); this.erro.set(null); },
      error: () => { this.carregando.set(false); this.erro.set('Falha ao carregar os dados.'); },
    });
  }

  // --- derivados ---
  ufsVisiveis = computed(() => {
    const m = this.meta(); if (!m) return [];
    const r = this.regiao();
    return m.ufs.filter(u => !r || u.regiao === r);
  });

  rotulos = computed(() => {
    const m = this.meta(); const c = this.comparacao();
    const p = m?.pleitos.find(x => x.ano === c.ano_para && x.turno === c.turno_para);
    return { esq: p?.esq.apelido ?? 'Esquerda', dir: p?.dir.apelido ?? 'Direita' };
  });

  /** Índice por código IBGE — é a chave que casa com a malha geográfica. */
  porCodigo = computed(() => {
    const m = new Map<string, ItemDecomposicao>();
    for (const i of this.dados()?.itens ?? []) if (i.cd_ibge) m.set(i.cd_ibge, i);
    return m;
  });

  itens = computed<ItemDecomposicao[]>(() => {
    const d = this.dados(); if (!d) return [];
    const por = this.ordenarPor();
    const arr = [...d.itens];
    if (por === 'nome') arr.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    else arr.sort((a, b) => b[por === 'swing' ? 'swing_esq' : 'contribuicao']
                          - a[por === 'swing' ? 'swing_esq' : 'contribuicao']);
    return arr.slice(0, this.limite());
  });

  /** O recorte que os tiles de resumo estão descrevendo. */
  escopo = computed(() => {
    const u = this.uf(), r = this.vista() === 'lista' ? this.regiao() : null;
    return u ?? r ?? 'nacional';
  });

  divergente = computed(() => {
    const v = this.itens().map(i => i.swing_esq);
    return v.some(x => x > 0) && v.some(x => x < 0);
  });

  escala = computed(() => {
    const max = Math.max(0.5, ...this.itens().map(i => Math.abs(i.swing_esq)));
    return Math.ceil(max * 2) / 2;
  });

  largura(v: number): number {
    const frac = Math.abs(v) / this.escala();
    return this.divergente() ? frac * 50 : frac * 100;
  }

  offset(v: number): number {
    if (!this.divergente()) return v >= 0 ? 0 : 100 - this.largura(v);
    return v >= 0 ? 50 : 50 - this.largura(v);
  }

  // --- navegação ---
  trocarRegiao(v: string): void { this.regiao.set(v || null); this.uf.set(null); }

  /** Clique numa UF do mapa: entra nos municípios dela. */
  entrarNoMapa(i: ItemDecomposicao): void {
    if (!this.uf()) this.uf.set(i.id);
  }

  voltarAoBrasil(): void { this.uf.set(null); }
}
