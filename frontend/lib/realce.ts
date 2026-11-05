export type Segmento = { tipo: 'texto' | 'processo'; valor: string };

// Numeração unificada do CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
const PROCESSO = /\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}/g;

/**
 * Quebra o texto em segmentos, isolando os números de processo para que a UI os
 * componha em dígitos tabulares.
 */
export function segmentarProcessos(texto: string): Segmento[] {
  const segmentos: Segmento[] = [];
  let cursor = 0;

  for (const achado of texto.matchAll(PROCESSO)) {
    if (achado.index > cursor) {
      segmentos.push({ tipo: 'texto', valor: texto.slice(cursor, achado.index) });
    }
    segmentos.push({ tipo: 'processo', valor: achado[0] });
    cursor = achado.index + achado[0].length;
  }

  if (cursor < texto.length) {
    segmentos.push({ tipo: 'texto', valor: texto.slice(cursor) });
  }

  return segmentos;
}
