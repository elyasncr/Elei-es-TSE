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

// Ramps de um matiz só, do fraco ao intenso. Os steps dark foram escolhidos
// para a superfície escura (não são um flip dos claros) e validados com
// `validate_palette.js --mode dark --ordinal`: luminosidade monotônica,
// ΔL >= 0.06 entre degraus vizinhos e o degrau mais fraco acima de 3:1
// contra o fundo — antes ele ficava em 2,2:1 e sumia no mapa.
const SEQ_ESQ = ['#fdeceb', '#f8c4c3', '#ef9391', '#e05f5d', '#c22e2c'];
const SEQ_DIR = ['#e8f1fd', '#bcd8f8', '#86b6ef', '#4a8ce3', '#205fb4'];
const SEQ_ESQ_DARK = ['#8f4340', '#b35550', '#cf6d67', '#e58a80', '#f7aea5'];
const SEQ_DIR_DARK = ['#24598f', '#3173b5', '#428fd8', '#62abf0', '#94c9fb'];

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

export function escalaAuto(valores: number[], escuro: boolean,
                           rotEsq: string, rotDir: string,
                           centro = 0, sufixo = 'pp',
                           bandaNeutra = true,
                           pontas?: [string, string]): Escala {
  // `pontas` nomeia explicitamente os dois extremos. Importa porque os polos
  // nem sempre são dois candidatos: na variação de UM candidato eles são
  // "fulano perde" / "fulano ganha". Tratá-los como dois candidatos só parece
  // certo quando a soma é zero (2o turno contra 2o turno) — entre 1o e 2o
  // turno, um subir não implica o outro descer.
  const [pEsq, pDir] = pontas ?? [`${rotDir} à frente`, `${rotEsq} à frente`];
  // com centro 0 o sinal é informação ("+2,3 pp"); com centro 50 o número já é
  // um percentual e o "+" só polui.
  const fmt = (x: number) =>
    (centro === 0 && x > 0 ? '+' : '') + x.toFixed(1) + (sufixo === '%' ? '%' : '');
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
  const divergente = min < centro && max > centro;

  if (!divergente) {
    // um lado só: ramp sequencial sobre o intervalo real
    const ramp = max > centro ? seqEsq : seqDir;
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
    // de um lado só: as pontas são "menos"/"mais" do mesmo extremo
    const base = pontas ? (max > centro ? pDir : pEsq)
                        : `${max > centro ? rotEsq : rotDir} à frente`;
    return { cor, classes, divergente: false,
             pontaEsq: `${base}: menos`, pontaDir: `${base}: mais` };
  }

  // divergente simétrica em torno do centro: mesma amplitude dos dois lados
  const amp = Math.max(Math.abs(min - centro), Math.abs(max - centro));
  const b = (d: number) => fmt(centro + d);       // rótulo da fronteira

  if (!bandaNeutra) {
    // O centro é uma divisa categórica (50% = quem está à frente). Um degrau
    // neutro em volta dele pintaria de cinza justamente as disputas apertadas,
    // que são as que mais importam — então aqui a divisa é nítida.
    const cortes = [0.35, 0.7].map(f => +(f * amp).toFixed(2));
    const [c1, c2] = cortes;
    const cor = (x: number | null | undefined) => {
      if (x === null || x === undefined || !Number.isFinite(x)) return semDado;
      const dx = x - centro, a = Math.abs(dx);
      const ramp = dx > 0 ? seqEsq : seqDir;
      return a < c1 ? ramp[1] : a < c2 ? ramp[3] : ramp[4];
    };
    const classes: Classe[] = [
      { cor: seqDir[4], rotulo: `até ${b(-c2)}`, borda: b(-c2) },
      { cor: seqDir[3], rotulo: `${b(-c2)} a ${b(-c1)}`, borda: b(-c1) },
      { cor: seqDir[1], rotulo: `${b(-c1)} a ${b(0)}`, borda: b(0) },
      { cor: seqEsq[1], rotulo: `${b(0)} a ${b(c1)}`, borda: b(c1) },
      { cor: seqEsq[3], rotulo: `${b(c1)} a ${b(c2)}`, borda: b(c2) },
      { cor: seqEsq[4], rotulo: `${b(c2)} ou mais`, borda: null },
    ];
    return { cor, classes, divergente: true, pontaEsq: pEsq, pontaDir: pDir };
  }

  const cortes = [0.12, 0.4, 0.72].map(f => +(f * amp).toFixed(2));
  const cor = (x: number | null | undefined) => {
    if (x === null || x === undefined || !Number.isFinite(x)) return semDado;
    const dx = x - centro, a = Math.abs(dx);
    if (a < cortes[0]) return neutro;
    const ramp = dx > 0 ? seqEsq : seqDir;
    return a < cortes[1] ? ramp[2] : a < cortes[2] ? ramp[3] : ramp[4];
  };
  const [c0, c1, c2] = cortes;
  const classes: Classe[] = [
    { cor: seqDir[4], rotulo: `até ${b(-c2)}`, borda: b(-c2) },
    { cor: seqDir[3], rotulo: `${b(-c2)} a ${b(-c1)}`, borda: b(-c1) },
    { cor: seqDir[2], rotulo: `${b(-c1)} a ${b(-c0)}`, borda: b(-c0) },
    { cor: neutro, rotulo: `${b(-c0)} a ${b(c0)}`, borda: b(c0) },
    { cor: seqEsq[2], rotulo: `${b(c0)} a ${b(c1)}`, borda: b(c1) },
    { cor: seqEsq[3], rotulo: `${b(c1)} a ${b(c2)}`, borda: b(c2) },
    { cor: seqEsq[4], rotulo: `${b(c2)} ou mais`, borda: null },
  ];
  return { cor, classes, divergente: true, pontaEsq: pEsq, pontaDir: pDir };
}
