import { convertToModelMessages, streamText, type UIMessage } from 'ai';
import { readChatConfig } from '@/lib/config';
import { loadCorpus } from '@/lib/corpus';
import { buildSystemPrompt } from '@/lib/prompt';
import { criarModelo, mensagemDeSistema } from '@/lib/provider';

// Roda no runtime Node (o default), porque o corpus é lido do disco com node:fs.
export const maxDuration = 60;

function erro(mensagem: string, status: number): Response {
  return Response.json({ error: mensagem }, { status });
}

export async function POST(req: Request): Promise<Response> {
  let config;
  try {
    config = readChatConfig(process.env);
  } catch (e) {
    return erro((e as Error).message, 500);
  }

  let messages: UIMessage[];
  try {
    const body = await req.json();
    if (!Array.isArray(body?.messages)) {
      return erro('Corpo inválido: esperado um campo "messages" com uma lista.', 400);
    }
    messages = body.messages;
  } catch {
    return erro('Corpo inválido: JSON malformado.', 400);
  }

  let system: string;
  try {
    system = buildSystemPrompt(loadCorpus(), config.truncChars);
  } catch (e) {
    return erro((e as Error).message, 500);
  }

  const result = streamText({
    model: criarModelo(config),
    instructions: mensagemDeSistema(system),
    messages: await convertToModelMessages(messages),
    onFinish: ({ usage }) => {
      // Prova de que o cache do corpus está pegando: da segunda pergunta em
      // diante, cacheRead deve subir para ~o tamanho do system prompt.
      const d = usage.inputTokenDetails;
      console.log(
        `[chat] input=${usage.inputTokens} cacheRead=${d?.cacheReadTokens ?? 0} ` +
          `cacheWrite=${d?.cacheWriteTokens ?? 0} output=${usage.outputTokens}`,
      );
    },
  });

  return result.toUIMessageStreamResponse();
}
