import { describe, expect, test } from 'vitest';
import { generateText, type ModelMessage, type SystemModelMessage } from 'ai';
import { criarModelo, mensagemDeSistema } from '../lib/provider';
import type { ChatConfig } from '../lib/config';

const CONFIG: ChatConfig = {
  apiKey: 'sk-teste',
  baseURL: 'https://opencode.ai/zen/v1',
  model: 'claude-opus-5',
  truncChars: 2000,
};

type Capturado = { url: string; headers: Record<string, string>; body: unknown };

/**
 * Captura o request e aborta. Não simula a resposta: o que este teste verifica é
 * a fronteira com o gateway — endpoint, auth e corpo.
 */
async function capturar(
  config = CONFIG,
  instructions?: SystemModelMessage,
): Promise<Capturado> {
  const messages: ModelMessage[] = [{ role: 'user', content: 'olá' }];
  let capturado: Capturado | undefined;

  const espiao: typeof fetch = async (input, init) => {
    capturado = {
      url: String(input),
      headers: Object.fromEntries(new Headers(init?.headers).entries()),
      body: JSON.parse(String(init?.body)),
    };
    throw new Error('parado-de-proposito');
  };

  const falha = await generateText({
    model: criarModelo(config, espiao),
    instructions,
    messages,
    maxRetries: 0,
  }).then(
    () => undefined,
    (e: Error) => e,
  );

  if (!capturado) {
    throw new Error(`o provider não fez requisição nenhuma; falhou antes com: ${falha?.message}`);
  }
  return capturado;
}

describe('criarModelo', () => {
  test('fala com o endpoint /messages do Zen, nao /chat/completions', async () => {
    const { url } = await capturar();

    expect(url).toBe('https://opencode.ai/zen/v1/messages');
  });

  test('autentica com x-api-key, nao com Authorization Bearer', async () => {
    const { headers } = await capturar();

    expect(headers['x-api-key']).toBe('sk-teste');
    expect(headers['authorization']).toBeUndefined();
  });

  test('respeita o baseURL configurado', async () => {
    const { url } = await capturar({ ...CONFIG, baseURL: 'http://localhost:8787' });

    expect(url).toBe('http://localhost:8787/messages');
  });

  test('manda o modelo configurado', async () => {
    const { body } = await capturar();

    expect(body).toMatchObject({ model: 'claude-opus-5' });
  });

});

describe('mensagemDeSistema', () => {
  test('marca o system prompt para cache — ele é estático e caro', async () => {
    const { body } = await capturar(CONFIG, mensagemDeSistema('prompt de sistema'));

    expect(body).toMatchObject({
      system: [
        { type: 'text', text: 'prompt de sistema', cache_control: { type: 'ephemeral' } },
      ],
    });
  });

  test('sem a marcação, o Anthropic nao cacheia — o contraste que justifica o cache', async () => {
    const { body } = await capturar(CONFIG, {
      role: 'system',
      content: 'prompt de sistema',
    });

    const system = (body as { system: Array<Record<string, unknown>> }).system;
    expect(system[0]).not.toHaveProperty('cache_control');
  });
});
