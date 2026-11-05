export type ChatConfig = {
  apiKey: string;
  baseURL: string;
  model: string;
  truncChars: number;
};

const BASE_URL_PADRAO = 'https://opencode.ai/zen/v1';

/**
 * Medido, não estimado: com 2000 o corte cai antes do dispositivo na maioria das
 * sentenças deste juiz (média de 3.363 caracteres) e o modelo responde que não
 * consegue afirmar o resultado. Com 4000 ele alcança o dispositivo integralmente.
 * Custo do system prompt: 10.453 → 18.634 tokens, cacheados a partir da segunda
 * pergunta de cada conversa.
 */
const TRUNC_PADRAO = 4000;

export const MODELO_PADRAO = 'claude-opus-5';

/**
 * Lê a configuração do chat do ambiente.
 *
 * Recebe o `env` por parâmetro (em vez de ler `process.env` direto) para ser
 * testável e para não vazar a chave em mensagem de erro.
 */
export function readChatConfig(env: Record<string, string | undefined>): ChatConfig {
  const apiKey = env.OPENCODE_API_KEY?.trim();
  if (!apiKey) {
    throw new Error(
      'OPENCODE_API_KEY não configurada. Gere uma chave em https://opencode.ai/auth ' +
        'e coloque em frontend/.env.local.',
    );
  }

  let truncChars = TRUNC_PADRAO;
  const bruto = env.SJ_TRUNC_CHARS?.trim();
  if (bruto) {
    const valor = Number(bruto);
    if (!Number.isInteger(valor) || valor <= 0) {
      throw new Error(`SJ_TRUNC_CHARS deve ser um inteiro positivo, recebido: "${bruto}".`);
    }
    truncChars = valor;
  }

  return {
    apiKey,
    baseURL: env.SJ_BASE_URL?.trim() || BASE_URL_PADRAO,
    model: env.SJ_MODEL?.trim() || MODELO_PADRAO,
    truncChars,
  };
}
