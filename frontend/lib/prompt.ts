import type { Sentenca } from './corpus';

function renderSentenca(s: Sentenca, indice: number, total: number, truncChars: number): string {
  const texto = s.texto.slice(0, truncChars);
  const marca =
    s.texto.length > truncChars
      ? `\n[...texto truncado em ${truncChars} de ${s.texto.length} caracteres]`
      : '';

  return [
    `### Sentença ${indice}/${total} — ${s.processo}`,
    `Classe: ${s.classe}`,
    `Assunto: ${s.assunto}`,
    `Vara: ${s.vara} — ${s.comarca}`,
    `Disponibilização: ${s.data_de_disponibilização}`,
    '',
    texto + marca,
  ].join('\n');
}

/**
 * Monta o system prompt com o corpus embutido: metadados de cada sentença mais
 * os primeiros `truncChars` caracteres do texto.
 */
export function buildSystemPrompt(corpus: Sentenca[], truncChars: number): string {
  if (corpus.length === 0) {
    throw new Error('Corpus vazio: nenhuma sentença para montar o system prompt.');
  }
  if (!Number.isInteger(truncChars) || truncChars <= 0) {
    throw new Error(`truncChars deve ser um inteiro positivo, recebido: ${truncChars}`);
  }

  const magistrado = corpus[0].magistrado;
  const total = corpus.length;

  const preambulo = [
    `Você é um assistente especializado nas sentenças do magistrado ${magistrado}.`,
    '',
    `Abaixo estão ${total} sentenças reais desse magistrado, extraídas do TJSP. Cada`,
    'uma vem com seus metadados e um trecho inicial do texto (o texto pode estar',
    'truncado — quando estiver, isso é sinalizado explicitamente).',
    '',
    'Regras:',
    '- Responda em português do Brasil.',
    '- Fundamente as respostas nas sentenças abaixo e cite o número do processo.',
    '- Se a informação não estiver nos trechos disponíveis, diga isso claramente em',
    '  vez de supor. Lembre-se de que você vê apenas o começo de cada sentença.',
    '- Não invente jurisprudência, número de processo, dispositivo ou valor.',
    '',
    '---',
    '',
  ].join('\n');

  const sentencas = corpus
    .map((s, i) => renderSentenca(s, i + 1, total, truncChars))
    .join('\n\n---\n\n');

  return preambulo + sentencas;
}
