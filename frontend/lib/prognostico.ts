// Os tipos espelham o JSON de sj/api.py; a lógica de referência fica no Python.

export type Degrau = 'classe' | 'grupo' | 'piso';

export type Eixo = {
  degrau: Degrau;
  n: number;
  desceu: boolean;
  insuficiente: boolean;
};

export type Intervalo = [number, number];

export type Procedencia = Eixo & { probabilidade: number | null; ic95: Intervalo | null };
export type Prazo = Eixo & { quartis_dias: number[] };
export type DanoMoral = {
  concessao: Eixo & { probabilidade_concessao: number | null; ic95: Intervalo | null };
  valor: Eixo & { quartis_reais: number[] };
  razao: Eixo & { mediana: number | null };
};
export type Comparavel = {
  processo: string;
  data: string;
  resultado: string | null;
  url_pdf: string;
  degrau: Degrau;
};
export type Resultado = {
  consulta: { classe: string | null; grupo: string | null };
  procedencia: Procedencia;
  prazo: Prazo;
  dano_moral: DanoMoral;
  comparaveis: Comparavel[];
};

export type Juizo = Pick<Resultado, 'procedencia' | 'prazo' | 'dano_moral'>;

export type Classe = { nome: string; grupo: string; definicao: string };
export type Estruturada = {
  classe: string | null;
  alternativas: string[];
  pede_dano_moral: boolean | null;
  motivo: string;
};

const DIAS_POR_MES = 30.44;

export const emMeses = (dias: number): number => dias / DIAS_POR_MES;

export function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

export function meses(dias: number): string {
  return emMeses(dias).toFixed(1).replace('.', ',');
}

export function reais(x: number): string {
  return `R$ ${Math.round(x).toLocaleString('pt-BR')}`;
}

/** Posição de `valor` na régua, de 0 a 100, presa às pontas. */
export function posicao(valor: number, min: number, max: number): number {
  return Math.min(100, Math.max(0, ((valor - min) / (max - min)) * 100));
}

const RESULTADOS: Record<string, string> = {
  procedente: 'procedente',
  parcialmente_procedente: 'parcialmente procedente',
  improcedente: 'improcedente',
  extinto_sem_merito: 'extinto sem mérito',
  homologacao: 'homologação',
};

export function resultadoLegivel(r: string | null): string {
  return r ? (RESULTADOS[r] ?? r.replaceAll('_', ' ')) : 'resultado não lido';
}

/** As classes agrupadas, na ordem em que aparecem, para o <optgroup>. */
export function porGrupo(classes: Classe[]): { grupo: string; classes: Classe[] }[] {
  const grupos = new Map<string, Classe[]>();
  for (const c of classes) grupos.set(c.grupo, [...(grupos.get(c.grupo) ?? []), c]);
  return [...grupos].map(([grupo, cs]) => ({ grupo, classes: cs }));
}

/** A frase que avisa que a escada desceu, ou null se a classe sustenta o número. */
export function avisoDeDegrau(e: Eixo, consulta: { classe: string | null; grupo: string | null }): string | null {
  if (e.insuficiente) {
    return `Nem o juízo inteiro tem casos suficientes aqui (n=${e.n}); não confie neste número.`;
  }
  if (!e.desceu) return null;
  const origem =
    e.degrau === 'grupo'
      ? `do grupo «${consulta.grupo}»`
      : 'de todo o Procedimento Comum de Limeira';
  return `Poucos casos nesta classe: o número vem ${origem} (n=${e.n}).`;
}

/** "da classe «X»", "do grupo «Y»" ou "do juízo todo", conforme o degrau. */
export function escopo(e: Eixo, consulta: { classe: string | null; grupo: string | null }): string {
  if (e.degrau === 'classe') return `da classe «${consulta.classe}»`;
  if (e.degrau === 'grupo') return `do grupo «${consulta.grupo}»`;
  return 'do juízo todo';
}
