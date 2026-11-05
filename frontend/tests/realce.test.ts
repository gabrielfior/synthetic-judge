import { describe, expect, test } from 'vitest';
import { segmentarProcessos } from '../lib/realce';

describe('segmentarProcessos', () => {
  test('devolve um unico segmento de texto quando nao ha processo', () => {
    expect(segmentarProcessos('Ele julgou procedente.')).toEqual([
      { tipo: 'texto', valor: 'Ele julgou procedente.' },
    ]);
  });

  test('reconhece um numero de processo isolado', () => {
    expect(segmentarProcessos('1006468-61.2024.8.26.0344')).toEqual([
      { tipo: 'processo', valor: '1006468-61.2024.8.26.0344' },
    ]);
  });

  test('separa o processo do texto ao redor', () => {
    expect(segmentarProcessos('Na sentença 1006468-61.2024.8.26.0344 ele arbitrou.')).toEqual([
      { tipo: 'texto', valor: 'Na sentença ' },
      { tipo: 'processo', valor: '1006468-61.2024.8.26.0344' },
      { tipo: 'texto', valor: ' ele arbitrou.' },
    ]);
  });

  test('reconhece varios processos na mesma frase', () => {
    const segmentos = segmentarProcessos(
      '1006468-61.2024.8.26.0344 e 1012534-71.2020.8.26.0320 divergem.',
    );

    expect(segmentos.filter((s) => s.tipo === 'processo').map((s) => s.valor)).toEqual([
      '1006468-61.2024.8.26.0344',
      '1012534-71.2020.8.26.0320',
    ]);
  });

  test('nao confunde valores em reais com processo', () => {
    const segmentos = segmentarProcessos('Fixou R$ 15.000,00 de indenização em 25/08/2026.');

    expect(segmentos.every((s) => s.tipo === 'texto')).toBe(true);
  });

  test('nao reconhece numero de processo incompleto', () => {
    expect(segmentarProcessos('1006468-61.2024.8.26')).toEqual([
      { tipo: 'texto', valor: '1006468-61.2024.8.26' },
    ]);
  });

  test('devolve lista vazia para texto vazio', () => {
    expect(segmentarProcessos('')).toEqual([]);
  });
});
