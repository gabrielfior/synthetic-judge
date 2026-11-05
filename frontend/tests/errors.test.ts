import { describe, expect, test } from 'vitest';
import { mensagemDeErro } from '../lib/errors';

describe('mensagemDeErro', () => {
  test('extrai o campo error do JSON que a rota devolve', () => {
    const erro = new Error('{"error":"OPENCODE_API_KEY não configurada."}');

    expect(mensagemDeErro(erro)).toBe('OPENCODE_API_KEY não configurada.');
  });

  test('usa a mensagem crua quando nao e JSON', () => {
    expect(mensagemDeErro(new Error('failed to fetch'))).toBe('failed to fetch');
  });

  test('usa a mensagem crua quando o JSON nao tem campo error', () => {
    expect(mensagemDeErro(new Error('{"detail":"outro formato"}'))).toBe('{"detail":"outro formato"}');
  });

  test('da um texto acionavel quando a mensagem esta vazia', () => {
    expect(mensagemDeErro(new Error(''))).toMatch(/servidor/i);
  });

  test('lida com undefined', () => {
    expect(mensagemDeErro(undefined)).toMatch(/servidor/i);
  });
});
