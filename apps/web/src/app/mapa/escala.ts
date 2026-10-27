/**
 * Escala de cor do mapa coroplético, em classes discretas.
 *
 * Classes em vez de gradiente contínuo: no mapa o olho compara áreas vizinhas,
 * e degraus nomeáveis são lidos com muito mais precisão que um contínuo.
 *
 * A escala se adapta ao dado, pelo mesmo motivo das barras:
 *  - há ganhos E perdas  -> DIVERGENTE, simétrica, cinza neutro no zero.
 *  - tudo para um lado   -> SEQUENCIAL de um matiz só, esticada sobre o
 *    intervalo real [min, max]. Forçar divergente aqui jogaria metade das
 *    classes fora e achataria todo o mapa num tom só.
 */

// ramps de um matiz, claro -> escuro
const SEQ_ESQ = ['#fdeceb', '#f8c4c3', '#ef9391', '#e05f5d', '#c22e2c'];
const SEQ_DIR = ['#e8f1fd', '#bcd8f8', '#86b6ef', '#4a8ce3', '#205fb4'];
const SEQ_ESQ_DARK = ['#4a2322', '#71302f', '#9c4240', '#c45653', '#e66767'];
const SEQ_DIR_DARK = ['#16304d', '#1d4a7d', '#2868ad', '#3380d6', '#4a97ee'];

const NEUTRO = '#eceae5', NEUTRO_DARK = '#35352f';
const SEM_DADO = '#f6f5f2', SEM_DADO_DARK = '#232321';

/** `borda` é o valor da fronteira DIREITA do degrau (null no último).
 *  A legenda rotula fronteiras, não degraus: um número por divisa ocupa
 *  metade do espaço de um intervalo por degrau e não colide. */
export interface Classe { cor: string; rotulo: string; borda: string | null; }

export interface Escala {
  cor: (v: number | null | undefined) => string;
  classes: Classe[];
  divergente: boolean;
  /** rótulo da ponta esquerda da legenda; null quando a escala é de um lado só */
  pontaDir: string | null;
  pontaEsq: string | null;
}

const fmt = (x: number) => (x > 0 ? '+' : '') + x.toFixed(1);

export function escalaAuto(valores: number[], escuro: boolean,
                           rotEsq: string, rotDir: string): Escala {
  const semDado = escuro ? SEM_DADO_DARK : SEM_DADO;
  const seqEsq = escuro ? SEQ_ESQ_DARK : SEQ_ESQ;
  const seqDir = escuro ? SEQ_DIR_DARK : SEQ_DIR;
  const neutro = escuro ? NEUTRO_DARK : NEUTRO;

  const v = valores.filter(x => Number.isFinite(x));
  if (!v.length) {
    return { cor: () => semDado, classes: [], divergente: false,
             pontaDir: null, pontaEsq: null };
  }

  const min = Math.min(...v), max = Math.max(...v);
  const divergente = min < 0 && max > 0;

  if (!divergente) {
    // um lado só: ramp sequencial sobre o intervalo real
    const ramp = max > 0 ? seqEsq : seqDir;
    const lo = Math.min(min, max), hi = Math.max(min, max);
    const passo = (hi - lo) / ramp.length || 1;
    const limites = ramp.slice(1).map((_, i) => lo + passo * (i + 1));

    const cor = (x: number | null | undefined) => {
      if (x === null || x === undefined || !Number.isFinite(x)) return semDado;
      let i = 0;
      while (i < limites.length && x >= limites[i]) i++;
      return ramp[i];
    };
    const bordas = [lo, ...limites, hi];
    const classes = ramp.map((cor, i) => ({
      cor,
      rotulo: `${fmt(bordas[i])} a ${fmt(bordas[i + 1])}`,
      borda: i < ramp.length - 1 ? fmt(limites[i]) : null,
    }));
    // na sequencial as pontas da legenda são os extremos, não dois candidatos
    return { cor, classes, divergente: false,
             pontaEsq: max > 0 ? `${rotEsq} ganha menos` : `${rotDir} ganha mais`,
             pontaDir: max > 0 ? `${rotEsq} ganha mais` : `${rotDir} ganha menos` };
  }

  // divergente simétrica: mesma amplitude dos dois lados
  const amp = Math.max(Math.abs(min), Math.abs(max));
  const cortes = [0.12, 0.4, 0.72].map(f => +(f * amp).toFixed(2));
  const cor = (x: number | null | undefined) => {
    if (x === null || x === undefined || !Number.isFinite(x)) return semDado;
    const a = Math.abs(x);
    if (a < cortes[0]) return neutro;
    const ramp = x > 0 ? seqEsq : seqDir;
    return a < cortes[1] ? ramp[2] : a < cortes[2] ? ramp[3] : ramp[4];
  };
  const n = (x: number) => x.toFixed(1);
  const [c0, c1, c2] = cortes;
  const classes: Classe[] = [
    { cor: seqDir[4], rotulo: `≤ −${n(c2)}`, borda: `−${n(c2)}` },
    { cor: seqDir[3], rotulo: `−${n(c2)} a −${n(c1)}`, borda: `−${n(c1)}` },
    { cor: seqDir[2], rotulo: `−${n(c1)} a −${n(c0)}`, borda: `−${n(c0)}` },
    { cor: neutro, rotulo: `±${n(c0)}`, borda: `+${n(c0)}` },
    { cor: seqEsq[2], rotulo: `${n(c0)} a ${n(c1)}`, borda: `+${n(c1)}` },
    { cor: seqEsq[3], rotulo: `${n(c1)} a ${n(c2)}`, borda: `+${n(c2)}` },
    { cor: seqEsq[4], rotulo: `≥ ${n(c2)}`, borda: null },
  ];
  return { cor, classes, divergente: true,
           pontaEsq: `${rotDir} ganha`, pontaDir: `${rotEsq} ganha` };
}
