import { afterEach, describe, expect, test } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseCorpus, resolveCorpusPath } from '../lib/corpus';

const temporarios: string[] = [];

function dirTemporario(): string {
  const dir = mkdtempSync(join(tmpdir(), 'sj-corpus-'));
  temporarios.push(dir);
  return dir;
}

afterEach(() => {
  while (temporarios.length > 0) {
    rmSync(temporarios.pop()!, { recursive: true, force: true });
  }
});

const sentencaValida = {
  processo: '1006468-61.2024.8.26.0344',
  tipo: 'SENTENÇA',
  classe: 'Procedimento Comum Cível',
  assunto: 'Indenização por Dano Moral',
  magistrado: 'Juiz Sintético de Teste',
  comarca: 'Marília',
  foro: 'Foro de Marília',
  vara: '1ª Vara Cível',
  data_de_disponibilização: '25/08/2026',
  texto: 'Vistos. Julgo procedente.',
};

describe('resolveCorpusPath', () => {
  test('encontra data/sentencas_juiz.json no proprio diretorio inicial', () => {
    const raiz = dirTemporario();
    mkdirSync(join(raiz, 'data'));
    writeFileSync(join(raiz, 'data', 'sentencas_juiz.json'), '[]');

    expect(resolveCorpusPath(raiz)).toBe(join(raiz, 'data', 'sentencas_juiz.json'));
  });

  test('sobe diretorios ate achar data/ — o caso do worktree', () => {
    const raiz = dirTemporario();
    mkdirSync(join(raiz, 'data'));
    writeFileSync(join(raiz, 'data', 'sentencas_juiz.json'), '[]');
    const fundo = join(raiz, '.claude', 'worktrees', 'frontend-chat', 'frontend');
    mkdirSync(fundo, { recursive: true });

    expect(resolveCorpusPath(fundo)).toBe(join(raiz, 'data', 'sentencas_juiz.json'));
  });

  test('para no data/ mais proximo quando existe mais de um', () => {
    const raiz = dirTemporario();
    mkdirSync(join(raiz, 'data'));
    writeFileSync(join(raiz, 'data', 'sentencas_juiz.json'), '[]');
    const proximo = join(raiz, 'sub');
    mkdirSync(join(proximo, 'data'), { recursive: true });
    writeFileSync(join(proximo, 'data', 'sentencas_juiz.json'), '[]');

    expect(resolveCorpusPath(proximo)).toBe(join(proximo, 'data', 'sentencas_juiz.json'));
  });

  test('falha com mensagem acionavel quando nao acha o corpus', () => {
    const raiz = dirTemporario();

    expect(() => resolveCorpusPath(raiz)).toThrow(/SJ_CORPUS_PATH/);
  });
});

describe('parseCorpus', () => {
  test('devolve as sentencas de um JSON valido', () => {
    const corpus = parseCorpus(JSON.stringify([sentencaValida]));

    expect(corpus).toHaveLength(1);
    expect(corpus[0].processo).toBe('1006468-61.2024.8.26.0344');
    expect(corpus[0].magistrado).toBe('Juiz Sintético de Teste');
  });

  test('rejeita JSON malformado', () => {
    expect(() => parseCorpus('{nao é json}')).toThrow(/JSON/i);
  });

  test('rejeita corpus que nao e uma lista', () => {
    expect(() => parseCorpus('{"processo": "x"}')).toThrow(/lista/i);
  });

  test('rejeita lista vazia', () => {
    expect(() => parseCorpus('[]')).toThrow(/vazi/i);
  });

  test('rejeita sentenca sem os campos obrigatorios, dizendo qual falta', () => {
    const { texto, ...semTexto } = sentencaValida;

    expect(() => parseCorpus(JSON.stringify([semTexto]))).toThrow(/texto/);
  });

  test('aponta o indice da sentenca invalida', () => {
    const { vara, ...semVara } = sentencaValida;

    expect(() => parseCorpus(JSON.stringify([sentencaValida, semVara]))).toThrow(/\[1\]/);
  });

  test('ignora campos extras do JSON — o corpus real tem relatorio, capa etc', () => {
    const comExtras = { ...sentencaValida, relatorio: 'x', capa: {}, movimentacoes: [] };

    const corpus = parseCorpus(JSON.stringify([comExtras]));

    expect(corpus[0].texto).toBe('Vistos. Julgo procedente.');
  });
});
