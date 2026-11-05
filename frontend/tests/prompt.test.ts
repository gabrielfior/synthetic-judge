import { describe, expect, test } from 'vitest';
import { buildSystemPrompt } from '../lib/prompt';
import type { Sentenca } from '../lib/corpus';

function sentenca(overrides: Partial<Sentenca> = {}): Sentenca {
  return {
    processo: '1006468-61.2024.8.26.0344',
    tipo: 'SENTENÇA',
    classe: 'Procedimento Comum Cível',
    assunto: 'Indenização por Dano Moral',
    magistrado: 'Juiz Sintético de Teste',
    comarca: 'Marília',
    foro: 'Foro de Marília',
    vara: '1ª Vara Cível',
    data_de_disponibilização: '25/08/2026',
    texto: 'Vistos. Julgo procedente o pedido.',
    ...overrides,
  };
}

describe('buildSystemPrompt', () => {
  test('nomeia o magistrado do corpus como persona', () => {
    const prompt = buildSystemPrompt([sentenca()], 2000);

    expect(prompt).toContain('Juiz Sintético de Teste');
  });

  test('inclui todas as sentencas do corpus, numeradas', () => {
    const corpus = [
      sentenca({ processo: 'AAA' }),
      sentenca({ processo: 'BBB' }),
      sentenca({ processo: 'CCC' }),
    ];

    const prompt = buildSystemPrompt(corpus, 2000);

    expect(prompt).toContain('Sentença 1/3 — AAA');
    expect(prompt).toContain('Sentença 2/3 — BBB');
    expect(prompt).toContain('Sentença 3/3 — CCC');
  });

  test('inclui os metadados de cada sentenca no cabecalho', () => {
    const prompt = buildSystemPrompt([sentenca()], 2000);

    expect(prompt).toContain('Classe: Procedimento Comum Cível');
    expect(prompt).toContain('Assunto: Indenização por Dano Moral');
    expect(prompt).toContain('Vara: 1ª Vara Cível — Marília');
    expect(prompt).toContain('Disponibilização: 25/08/2026');
  });

  test('trunca o texto no limite de caracteres informado', () => {
    const corpus = [sentenca({ texto: 'x'.repeat(500) })];

    const prompt = buildSystemPrompt(corpus, 100);

    expect(prompt).toContain('x'.repeat(100));
    expect(prompt).not.toContain('x'.repeat(101));
  });

  test('marca explicitamente quando o texto foi truncado', () => {
    const corpus = [sentenca({ texto: 'x'.repeat(500) })];

    const prompt = buildSystemPrompt(corpus, 100);

    expect(prompt).toContain('[...texto truncado em 100 de 500 caracteres]');
  });

  test('nao marca truncagem quando o texto cabe no limite', () => {
    const corpus = [sentenca({ texto: 'Vistos. Julgo improcedente.' })];

    const prompt = buildSystemPrompt(corpus, 2000);

    expect(prompt).toContain('Vistos. Julgo improcedente.');
    expect(prompt).not.toContain('[...texto truncado');
  });

  test('preserva a ordem das sentencas do corpus', () => {
    const corpus = [sentenca({ processo: 'PRIMEIRO' }), sentenca({ processo: 'SEGUNDO' })];

    const prompt = buildSystemPrompt(corpus, 2000);

    expect(prompt.indexOf('PRIMEIRO')).toBeLessThan(prompt.indexOf('SEGUNDO'));
  });

  test('rejeita corpus vazio em vez de gerar um prompt sem sentencas', () => {
    expect(() => buildSystemPrompt([], 2000)).toThrow(/corpus vazio/i);
  });

  test('rejeita limite de truncagem nao positivo', () => {
    expect(() => buildSystemPrompt([sentenca()], 0)).toThrow(/truncChars/);
  });
});
