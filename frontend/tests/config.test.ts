import { describe, expect, test } from 'vitest';
import { readChatConfig } from '../lib/config';

const comChave = { OPENCODE_API_KEY: 'sk-teste' };

describe('readChatConfig', () => {
  test('falha nomeando a variavel quando nao ha API key', () => {
    expect(() => readChatConfig({})).toThrow(/OPENCODE_API_KEY/);
  });

  test('trata API key em branco como ausente', () => {
    expect(() => readChatConfig({ OPENCODE_API_KEY: '   ' })).toThrow(/OPENCODE_API_KEY/);
  });

  test('usa o endpoint do OpenCode Zen por padrao', () => {
    expect(readChatConfig(comChave).baseURL).toBe('https://opencode.ai/zen/v1');
  });

  test('usa claude-opus-5 como modelo padrao', () => {
    expect(readChatConfig(comChave).model).toBe('claude-opus-5');
  });

  test('SJ_MODEL sobrescreve o modelo', () => {
    expect(readChatConfig({ ...comChave, SJ_MODEL: 'big-pickle' }).model).toBe('big-pickle');
  });

  test('trunca em 4000 caracteres por padrao — o corte que alcanca o dispositivo', () => {
    expect(readChatConfig(comChave).truncChars).toBe(4000);
  });

  test('SJ_TRUNC_CHARS sobrescreve o limite, como numero', () => {
    expect(readChatConfig({ ...comChave, SJ_TRUNC_CHARS: '500' }).truncChars).toBe(500);
  });

  test('rejeita SJ_TRUNC_CHARS nao numerico em vez de cair no default', () => {
    expect(() => readChatConfig({ ...comChave, SJ_TRUNC_CHARS: 'muito' })).toThrow(
      /SJ_TRUNC_CHARS/,
    );
  });

  test('rejeita SJ_TRUNC_CHARS igual a zero', () => {
    expect(() => readChatConfig({ ...comChave, SJ_TRUNC_CHARS: '0' })).toThrow(/SJ_TRUNC_CHARS/);
  });

  test('nao devolve a API key dentro de uma mensagem de erro', () => {
    try {
      readChatConfig({ OPENCODE_API_KEY: 'sk-segredo', SJ_TRUNC_CHARS: 'muito' });
      throw new Error('deveria ter lancado');
    } catch (erro) {
      expect((erro as Error).message).not.toContain('sk-segredo');
    }
  });
});
