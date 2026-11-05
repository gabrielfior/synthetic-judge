import { chamarApi } from '@/lib/python';
import { erro, lerCorpo, responder } from '@/lib/rotas-prognostico';

// Só aritmética sobre a base, sem LLM: o advogado edita a classe e isto recalcula.
export const maxDuration = 30;

export async function POST(req: Request): Promise<Response> {
  const corpo = await lerCorpo(req);
  if (!corpo) return erro('Corpo inválido: esperado um objeto JSON.', 400);

  const { classe = null, pedeDanoMoral = null } = corpo;
  if (classe !== null && typeof classe !== 'string') {
    return erro('"classe" deve ser o nome de uma classe ou null.', 400);
  }
  if (pedeDanoMoral !== null && typeof pedeDanoMoral !== 'boolean') {
    return erro('"pedeDanoMoral" deve ser true, false ou null.', 400);
  }

  return responder(() => chamarApi('calcular', { classe, pede_dano_moral: pedeDanoMoral }));
}
