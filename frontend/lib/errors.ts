const GENERICA = 'O servidor não respondeu. Verifique se o `npm run dev` ainda está rodando.';

/**
 * Traduz o erro do `useChat` em texto para a pessoa.
 *
 * A transport do AI SDK lança `new Error(await response.text())`, então quando a
 * rota falha a mensagem chega como o JSON cru `{"error":"..."}`.
 */
export function mensagemDeErro(erro: Error | undefined): string {
  const bruto = erro?.message?.trim();
  if (!bruto) {
    return GENERICA;
  }

  try {
    const corpo = JSON.parse(bruto);
    if (typeof corpo?.error === 'string' && corpo.error.trim()) {
      return corpo.error;
    }
  } catch {
    // Não era JSON: a mensagem crua já é o melhor que temos.
  }

  return bruto;
}
