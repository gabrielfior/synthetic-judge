import { ErroDeEntrada, ErroDoPipeline } from '@/lib/python';

/** Traduz as falhas da ponte para respostas HTTP; o resto propaga como 500. */
export async function responder(trabalho: () => Promise<unknown>): Promise<Response> {
  try {
    return Response.json(await trabalho());
  } catch (e) {
    if (e instanceof ErroDeEntrada) return Response.json({ error: e.message }, { status: 400 });
    if (e instanceof ErroDoPipeline) return Response.json({ error: e.message }, { status: 500 });
    throw e;
  }
}

export async function lerCorpo(req: Request): Promise<Record<string, unknown> | null> {
  try {
    const corpo = await req.json();
    return corpo && typeof corpo === 'object' && !Array.isArray(corpo) ? corpo : null;
  } catch {
    return null;
  }
}

export const erro = (mensagem: string, status: number) =>
  Response.json({ error: mensagem }, { status });
