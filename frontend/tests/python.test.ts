import { describe, expect, test } from 'vitest';
import {
  chamarApi,
  ErroDeEntrada,
  ErroDoPipeline,
  raizDoRepo,
  type Executor,
} from '../lib/python';

function executor(code: number | null, stdout: string, stderr = ''): Executor & { chamadas: unknown[][] } {
  const chamadas: unknown[][] = [];
  const f = (async (comando, args, stdin, opcoes) => {
    chamadas.push([comando, args, stdin, opcoes]);
    return { code, stdout, stderr };
  }) as Executor & { chamadas: unknown[][] };
  f.chamadas = chamadas;
  return f;
}

describe('chamarApi', () => {
  test('chama uv run python prognosticar.py --api <acao> com o JSON no stdin', async () => {
    const e = executor(0, '{"classes": []}');
    const r = await chamarApi('taxonomia', { a: 1 }, e, { SJ_REPO_ROOT: '/repo' });

    expect(r).toEqual({ classes: [] });
    expect(e.chamadas[0]).toEqual([
      'uv',
      ['run', 'python', 'prognosticar.py', '--api', 'taxonomia'],
      '{"a":1}',
      { cwd: '/repo', timeoutMs: 20_000 },
    ]);
  });

  test('a estruturação, que chama uma LLM, tem prazo maior', async () => {
    const e = executor(0, '{}');
    await chamarApi('estruturar', { texto: 'x' }, e, { SJ_REPO_ROOT: '/r' });
    expect((e.chamadas[0][3] as { timeoutMs: number }).timeoutMs).toBe(60_000);
  });

  test('SJ_UV troca o executável', async () => {
    const e = executor(0, '{}');
    await chamarApi('calcular', {}, e, { SJ_UV: '/opt/uv', SJ_REPO_ROOT: '/r' });
    expect(e.chamadas[0][0]).toBe('/opt/uv');
  });

  test('código 2 é erro de entrada com a mensagem do Python', async () => {
    const e = executor(2, '{"erro": "classe desconhecida: \'Z\'"}');
    const falha = chamarApi('calcular', { classe: 'Z' }, e, {});
    await expect(falha).rejects.toBeInstanceOf(ErroDeEntrada);
    await expect(falha).rejects.toThrow("classe desconhecida: 'Z'");
  });

  test('código 2 com saída ilegível ainda é erro de entrada', async () => {
    await expect(chamarApi('calcular', {}, executor(2, 'lixo'), {})).rejects.toThrow(
      'Entrada inválida.',
    );
  });

  test('outro código é falha do pipeline e sugere build_base quando falta a base', async () => {
    const e = executor(1, '', 'Traceback...\nFileNotFoundError: data/prognostico/base.jsonl não existe; rode build_base.py');
    const falha = chamarApi('calcular', {}, e, {});
    await expect(falha).rejects.toBeInstanceOf(ErroDoPipeline);
    await expect(falha).rejects.toThrow('build_base.py');
  });

  test('saída que não é JSON é falha do pipeline', async () => {
    await expect(chamarApi('taxonomia', {}, executor(0, 'oi'), {})).rejects.toBeInstanceOf(
      ErroDoPipeline,
    );
  });
});

describe('raizDoRepo', () => {
  test('SJ_REPO_ROOT vence; sem ele, a pasta acima de frontend/', () => {
    expect(raizDoRepo({ SJ_REPO_ROOT: ' /x ' })).toBe('/x');
    expect(raizDoRepo({})).toMatch(/synthetic-judge$/);
  });
});
