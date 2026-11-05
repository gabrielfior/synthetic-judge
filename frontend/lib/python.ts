import { spawn } from 'node:child_process';
import { resolve } from 'node:path';

/**
 * Ponte para o pipeline do prognóstico, que mora em Python (`prognosticar.py
 * --api`). A lógica de referência existe num lugar só; aqui só se fala JSON por
 * stdin/stdout. Roda a partir da raiz do repo, que é onde estão `data/` e `sj/`.
 */
export type AcaoApi = 'taxonomia' | 'estruturar' | 'calcular';

/** O chamador pode corrigir (vira 400). */
export class ErroDeEntrada extends Error {}
/** O pipeline falhou por dentro (vira 500). */
export class ErroDoPipeline extends Error {}

export type Execucao = { code: number | null; stdout: string; stderr: string };
export type Executor = (
  comando: string,
  args: string[],
  stdin: string,
  opcoes: { cwd: string; timeoutMs: number },
) => Promise<Execucao>;

// A estruturação chama uma LLM; o cálculo é só aritmética sobre a base.
const TIMEOUT_MS: Record<AcaoApi, number> = {
  taxonomia: 20_000,
  calcular: 20_000,
  estruturar: 60_000,
};

export function raizDoRepo(env: Record<string, string | undefined> = process.env): string {
  return env.SJ_REPO_ROOT?.trim() || resolve(process.cwd(), '..');
}

export const executarProcesso: Executor = (comando, args, stdin, { cwd, timeoutMs }) =>
  new Promise((ok, falha) => {
    const filho = spawn(comando, args, { cwd, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    const prazo = setTimeout(() => {
      filho.kill('SIGKILL');
      falha(new ErroDoPipeline(`O pipeline não respondeu em ${timeoutMs / 1000}s.`));
    }, timeoutMs);

    filho.stdout.on('data', (d) => (stdout += d));
    filho.stderr.on('data', (d) => (stderr += d));
    filho.on('error', (e) => {
      clearTimeout(prazo);
      falha(
        new ErroDoPipeline(
          `Não consegui executar "${comando}": ${e.message}. ` +
            'Instale o uv ou aponte SJ_UV para o executável.',
        ),
      );
    });
    filho.on('close', (code) => {
      clearTimeout(prazo);
      ok({ code, stdout, stderr });
    });
    filho.stdin.on('error', () => {}); // o filho pode sair antes de ler tudo
    filho.stdin.end(stdin);
  });

export async function chamarApi<T>(
  acao: AcaoApi,
  corpo: Record<string, unknown> = {},
  executor: Executor = executarProcesso,
  env: Record<string, string | undefined> = process.env,
): Promise<T> {
  const uv = env.SJ_UV?.trim() || 'uv';
  const { code, stdout, stderr } = await executor(
    uv,
    ['run', 'python', 'prognosticar.py', '--api', acao],
    JSON.stringify(corpo),
    { cwd: raizDoRepo(env), timeoutMs: TIMEOUT_MS[acao] },
  );

  if (code === 2) {
    let mensagem = 'Entrada inválida.';
    try {
      mensagem = JSON.parse(stdout).erro ?? mensagem;
    } catch {
      /* o Python sempre escreve {"erro": ...} no código 2; senão, a genérica */
    }
    throw new ErroDeEntrada(mensagem);
  }
  if (code !== 0) {
    const ultima = stderr.trim().split('\n').pop() ?? '';
    const dica = /base\.jsonl|build_base/.test(stderr)
      ? ' Rode `uv run python build_base.py` na raiz do repo.'
      : '';
    throw new ErroDoPipeline(`O pipeline do prognóstico falhou: ${ultima}.${dica}`.trim());
  }
  try {
    return JSON.parse(stdout) as T;
  } catch {
    throw new ErroDoPipeline('O pipeline respondeu algo que não é JSON.');
  }
}
