import { chamarApi } from '@/lib/python';
import { erro, lerCorpo, responder } from '@/lib/rotas-prognostico';

// Chama uma LLM por trás do subprocesso: pode levar dezenas de segundos.
export const maxDuration = 90;

const TEXTO_MAX = 8000;

export async function POST(req: Request): Promise<Response> {
  const corpo = await lerCorpo(req);
  if (!corpo) return erro('Corpo inválido: esperado um objeto JSON.', 400);

  const texto = typeof corpo.texto === 'string' ? corpo.texto.trim() : '';
  if (!texto) return erro('Descreva o caso antes de analisar.', 400);
  if (texto.length > TEXTO_MAX) {
    return erro(`A descrição passa de ${TEXTO_MAX} caracteres; resuma o caso.`, 400);
  }

  return responder(() => chamarApi('estruturar', { texto }));
}
