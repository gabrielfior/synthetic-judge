import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { POST } from '../app/api/chat/route';

const ambienteOriginal = { ...process.env };

function pedido(body: unknown): Request {
  return new Request('http://localhost/api/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

const mensagemValida = {
  messages: [{ id: '1', role: 'user', parts: [{ type: 'text', text: 'olá' }] }],
};

beforeEach(() => {
  delete process.env.OPENCODE_API_KEY;
});

afterEach(() => {
  process.env = { ...ambienteOriginal };
});

describe('POST /api/chat', () => {
  test('responde 500 com erro legivel quando falta a API key', async () => {
    const resposta = await POST(pedido(mensagemValida));

    expect(resposta.status).toBe(500);
    await expect(resposta.json()).resolves.toMatchObject({
      error: expect.stringContaining('OPENCODE_API_KEY'),
    });
  });

  test('responde 400 quando o corpo nao tem a lista de mensagens', async () => {
    process.env.OPENCODE_API_KEY = 'sk-teste';

    const resposta = await POST(pedido({ nada: true }));

    expect(resposta.status).toBe(400);
    await expect(resposta.json()).resolves.toMatchObject({
      error: expect.stringContaining('messages'),
    });
  });

  test('responde 400 quando o corpo nao e JSON', async () => {
    process.env.OPENCODE_API_KEY = 'sk-teste';
    const bruto = new Request('http://localhost/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: 'nao é json',
    });

    const resposta = await POST(bruto);

    expect(resposta.status).toBe(400);
  });

  test('nao devolve a API key no corpo da resposta de erro', async () => {
    process.env.OPENCODE_API_KEY = 'sk-segredo';

    const resposta = await POST(pedido({ nada: true }));

    expect(await resposta.text()).not.toContain('sk-segredo');
  });
});
