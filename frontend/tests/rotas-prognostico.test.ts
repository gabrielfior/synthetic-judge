import { describe, expect, test, vi } from 'vitest';

vi.mock('../lib/python', async (importar) => {
  const real = await importar<typeof import('../lib/python')>();
  return { ...real, chamarApi: vi.fn() };
});

import { POST as calcular } from '../app/api/prognostico/calcular/route';
import { POST as estruturar } from '../app/api/prognostico/estruturar/route';
import { chamarApi, ErroDeEntrada, ErroDoPipeline } from '../lib/python';

const chamar = vi.mocked(chamarApi);

function pedido(rota: string, body: unknown, bruto = false): Request {
  return new Request(`http://localhost/api/prognostico/${rota}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: bruto ? (body as string) : JSON.stringify(body),
  });
}

describe('POST /api/prognostico/estruturar', () => {
  test('passa o texto aparado ao pipeline e devolve o JSON', async () => {
    chamar.mockResolvedValueOnce({ estruturada: { classe: 'A' } });
    const r = await estruturar(pedido('estruturar', { texto: '  caso  ' }));

    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ estruturada: { classe: 'A' } });
    expect(chamar).toHaveBeenCalledWith('estruturar', { texto: 'caso' });
  });

  test.each([{}, { texto: '' }, { texto: '   ' }, { texto: 5 }])(
    '400 quando o texto é vazio (%j)',
    async (body) => {
      chamar.mockClear();
      const r = await estruturar(pedido('estruturar', body));
      expect(r.status).toBe(400);
      expect((await r.json()).error).toContain('Descreva o caso');
      expect(chamar).not.toHaveBeenCalled();
    },
  );

  test('400 quando o texto é longo demais, sem chamar a LLM', async () => {
    chamar.mockClear();
    const r = await estruturar(pedido('estruturar', { texto: 'x'.repeat(8001) }));
    expect(r.status).toBe(400);
    expect(chamar).not.toHaveBeenCalled();
  });

  test('400 com corpo que não é JSON', async () => {
    const r = await estruturar(pedido('estruturar', 'não é json', true));
    expect(r.status).toBe(400);
  });

  test('500 com a mensagem do pipeline quando ele falha', async () => {
    chamar.mockRejectedValueOnce(new ErroDoPipeline('O pipeline do prognóstico falhou: x.'));
    const r = await estruturar(pedido('estruturar', { texto: 'caso' }));
    expect(r.status).toBe(500);
    expect((await r.json()).error).toContain('falhou');
  });
});

describe('POST /api/prognostico/calcular', () => {
  test('traduz pedeDanoMoral para o nome do Python', async () => {
    chamar.mockResolvedValueOnce({ resultado: {} });
    const r = await calcular(pedido('calcular', { classe: 'A', pedeDanoMoral: true }));
    expect(r.status).toBe(200);
    expect(chamar).toHaveBeenLastCalledWith('calcular', { classe: 'A', pede_dano_moral: true });
  });

  test('classe ausente vale null (o piso)', async () => {
    chamar.mockResolvedValueOnce({ resultado: {} });
    await calcular(pedido('calcular', {}));
    expect(chamar).toHaveBeenLastCalledWith('calcular', { classe: null, pede_dano_moral: null });
  });

  test.each([{ classe: 5 }, { pedeDanoMoral: 'sim' }])('400 com tipos errados (%j)', async (body) => {
    chamar.mockClear();
    const r = await calcular(pedido('calcular', body));
    expect(r.status).toBe(400);
    expect(chamar).not.toHaveBeenCalled();
  });

  test('erro de entrada do Python vira 400 com a mensagem dele', async () => {
    chamar.mockRejectedValueOnce(new ErroDeEntrada("classe desconhecida: 'Z'"));
    const r = await calcular(pedido('calcular', { classe: 'Z' }));
    expect(r.status).toBe(400);
    expect((await r.json()).error).toContain('classe desconhecida');
  });
});
