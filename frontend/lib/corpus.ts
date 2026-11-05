import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

/** Uma sentença como gravada por `fetch_juiz.py` em `data/sentencas_juiz.json`. */
export type Sentenca = {
  processo: string;
  tipo: string;
  classe: string;
  assunto: string;
  magistrado: string;
  comarca: string;
  foro: string;
  vara: string;
  data_de_disponibilização: string;
  texto: string;
};

const CAMPOS: (keyof Sentenca)[] = [
  'processo',
  'tipo',
  'classe',
  'assunto',
  'magistrado',
  'comarca',
  'foro',
  'vara',
  'data_de_disponibilização',
  'texto',
];

const NOME_ARQUIVO = 'sentencas_juiz.json';

/**
 * Sobe a árvore de diretórios a partir de `startDir` procurando
 * `data/sentencas_juiz.json`.
 *
 * O walk-up existe porque `data/` está no .gitignore e portanto não viaja para
 * os worktrees: rodando de `.claude/worktrees/<x>/frontend`, isto acha o `data/`
 * do repo principal.
 */
export function resolveCorpusPath(startDir: string): string {
  let dir = resolve(startDir);

  for (;;) {
    const candidato = join(dir, 'data', NOME_ARQUIVO);
    if (existsSync(candidato)) {
      return candidato;
    }
    const pai = dirname(dir);
    if (pai === dir) {
      throw new Error(
        `Corpus não encontrado: subi de ${resolve(startDir)} até a raiz sem achar ` +
          `data/${NOME_ARQUIVO}. Rode fetch_juiz.py para gerá-lo, ou aponte ` +
          `SJ_CORPUS_PATH para o arquivo.`,
      );
    }
    dir = pai;
  }
}

function validarSentenca(valor: unknown, indice: number): Sentenca {
  if (typeof valor !== 'object' || valor === null || Array.isArray(valor)) {
    throw new Error(`Corpus inválido: [${indice}] não é um objeto.`);
  }
  const registro = valor as Record<string, unknown>;

  for (const campo of CAMPOS) {
    if (typeof registro[campo] !== 'string') {
      throw new Error(
        `Corpus inválido: [${indice}] não tem o campo obrigatório "${campo}" como string.`,
      );
    }
  }

  // Só os campos que o prompt usa; o corpus real traz relatorio, capa,
  // movimentacoes etc., que aqui são descartados de propósito.
  return Object.fromEntries(CAMPOS.map((campo) => [campo, registro[campo]])) as Sentenca;
}

/** Faz o parse e valida o conteúdo bruto do arquivo de corpus. */
export function parseCorpus(raw: string): Sentenca[] {
  let dados: unknown;
  try {
    dados = JSON.parse(raw);
  } catch (erro) {
    throw new Error(`Corpus inválido: JSON malformado (${(erro as Error).message}).`);
  }

  if (!Array.isArray(dados)) {
    throw new Error('Corpus inválido: o JSON precisa ser uma lista de sentenças.');
  }
  if (dados.length === 0) {
    throw new Error('Corpus inválido: a lista de sentenças está vazia.');
  }

  return dados.map(validarSentenca);
}

let cache: Sentenca[] | undefined;

/**
 * Carrega o corpus do disco uma vez por processo.
 *
 * Falha alto e claro se o arquivo não existir ou estiver inválido — melhor não
 * subir do que servir um chat com system prompt vazio.
 */
export function loadCorpus(): Sentenca[] {
  if (cache === undefined) {
    const caminho = process.env.SJ_CORPUS_PATH
      ? resolve(process.env.SJ_CORPUS_PATH)
      : resolveCorpusPath(process.cwd());
    cache = parseCorpus(readFileSync(caminho, 'utf8'));
  }
  return cache;
}
