import { createAnthropic } from '@ai-sdk/anthropic';
import type { LanguageModel, SystemModelMessage } from 'ai';
import type { ChatConfig } from './config';

/**
 * Monta a mensagem de sistema marcada para prompt caching.
 *
 * O corpus é o mesmo byte a byte em toda requisição e custa ~7k tokens, então
 * cacheá-lo derruba o custo de input das mensagens seguintes. O cache é por
 * prefixo (`system` vem antes de `messages`), e como só o system está marcado,
 * a pergunta do usuário — que muda a cada turno — fica depois do breakpoint.
 *
 * Vai no parâmetro `instructions` do AI SDK v7 (`system` está deprecado) como
 * mensagem, e não como string: é do `providerOptions` da mensagem que o
 * provider lê o `cache_control`.
 */
export function mensagemDeSistema(system: string): SystemModelMessage {
  return {
    role: 'system',
    content: system,
    providerOptions: { anthropic: { cacheControl: { type: 'ephemeral' } } },
  };
}

/**
 * Monta o modelo apontado para o OpenCode Zen.
 *
 * O Zen serve cada família de modelo no formato nativo do provedor, não num
 * formato único: os modelos Claude falam a Anthropic Messages API em
 * `{baseURL}/messages` com auth `x-api-key`. Em `/chat/completions` com
 * `Authorization: Bearer` eles devolvem 500 — por isso aqui é
 * `@ai-sdk/anthropic` e não `@ai-sdk/openai-compatible`.
 *
 * `fetchImpl` existe para os testes interceptarem o request.
 */
export function criarModelo(config: ChatConfig, fetchImpl?: typeof fetch): LanguageModel {
  const zen = createAnthropic({
    baseURL: config.baseURL,
    apiKey: config.apiKey,
    fetch: fetchImpl,
  });

  return zen(config.model);
}
