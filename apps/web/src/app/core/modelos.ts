export interface Candidato { nr: string; nome: string; apelido: string; }

export interface Pleito {
  ano: number; turno: number;
  esq: Candidato; dir: Candidato;
  pct_esq: number; pct_dir: number;
  validos: number; comparecimento: number;
}

export interface Meta {
  pleitos: Pleito[];
  regioes: string[];
  ufs: { uf: string; regiao: string }[];
}

export interface Linha {
  id: string; nome: string; uf: string | null; regiao: string | null;
  cd_ibge: string | null;
  esq: number; dir: number; outros: number; branco_nulo: number;
  validos: number; comparecimento: number;
  pct_esq: number; pct_dir: number;
}

export interface LinhaSwing {
  id: string; nome: string; uf: string | null; regiao: string | null;
  cd_ibge: string | null;
  pct_esq_de: number; pct_esq_para: number; swing_esq: number;
  validos_de: number; validos_para: number;
  votos_esq_de: number; votos_esq_para: number;
  delta_comparecimento: number;
}

export interface ItemDecomposicao extends LinhaSwing {
  peso: number; contribuicao: number;
}

export interface Decomposicao {
  swing_nacional: number;
  pct_esq_de: number; pct_esq_para: number;
  soma_contribuicoes: number;
  itens: ItemDecomposicao[];
}

export type Nivel = 'regiao' | 'uf' | 'municipio';

/** Um par de pleitos a comparar. */
export interface Comparacao {
  rotulo: string;
  ano_de: number; turno_de: number;
  ano_para: number; turno_para: number;
  descricao: string;
}

/** O que o mapa pinta. Variação responde "para onde o eleitorado se moveu";
 *  resultado responde "quem está na frente" — são perguntas diferentes e
 *  podem ter respostas opostas no mesmo recorte. */
export type Metrica = 'variacao' | 'chegada' | 'partida';
