# Frontend — chat sobre as sentenças

Chat que responde perguntas sobre o corpus de sentenças de um magistrado do
TJSP. Next.js (App Router) + Vercel AI SDK, com o LLM servido pelo
[OpenCode Zen](https://opencode.ai/docs/zen/).

**O Zen serve cada família de modelo no formato nativo do provedor, não num
formato único.** Os modelos Claude falam a Anthropic Messages API em
`{baseURL}/messages` com auth `x-api-key`; em `/chat/completions` com
`Authorization: Bearer` eles devolvem 500. Por isso o provider aqui é
`@ai-sdk/anthropic` com `baseURL` apontado para o Zen, e não
`@ai-sdk/openai-compatible`. Trocar `SJ_MODEL` para um modelo de outra família
(GPT, Gemini) exige trocar o provider também. Os modelos `-free` do Zen não
servem por API: devolvem `OpenCode's free tier can only be used in OpenCode`.
Para gastar menos, desça de Claude: `claude-sonnet-5` ou `claude-haiku-4-5`.

## Rodar

```bash
cd frontend
pnpm install
cp .env.local.example .env.local   # preencha OPENCODE_API_KEY
pnpm dev                           # http://localhost:3000
```

A chave sai de <https://opencode.ai/auth>. Sem ela a app sobe, mostra o cabeçalho
do corpus e explica na tela o que falta configurar.

```bash
pnpm test    # 57 testes
pnpm build   # build de produção
```

## Como o corpus chega ao LLM

Não há tools nem RAG neste v1. Todo o corpus entra no system prompt de cada
requisição: metadados de cada sentença (processo, classe, assunto, vara, data)
mais os primeiros `SJ_TRUNC_CHARS` caracteres do texto.

Números medidos com as 10 sentenças de `data/sentencas_juiz.json`:

| `SJ_TRUNC_CHARS` | System prompt | Alcança o dispositivo? |
| ---------------- | ------------- | ---------------------- |
| 2000             | 10.453 tokens | Não, na maioria        |
| **4000 (default)** | 18.634 tokens | Sim                  |

O corte de 2000 costuma cair antes do dispositivo (as sentenças deste juiz têm
3.363 caracteres em média), e o modelo então responde que não consegue afirmar o
resultado — o que é honesto, mas inútil. Daí o default de 4000.

O system prompt é marcado para **prompt caching** (`cache_control: ephemeral`).
Ele é idêntico byte a byte em toda requisição, então da segunda pergunta em
diante o corpus é lido do cache a ~0,1x do preço. A rota loga
`cacheRead`/`cacheWrite` a cada resposta para você conferir que está pegando.

O corpus é lido do disco uma vez por processo. O caminho vem de
`SJ_CORPUS_PATH`; sem ele a app sobe a árvore de diretórios procurando
`data/sentencas_juiz.json`, o que acha o `data/` do repo principal mesmo rodando
de dentro de um worktree (`data/` está no `.gitignore`, então não é copiado).

## Configuração

| Variável           | Default                       | Para quê                                     |
| ------------------ | ----------------------------- | -------------------------------------------- |
| `OPENCODE_API_KEY` | —                             | Obrigatória                                  |
| `SJ_MODEL`         | `claude-opus-5`               | Modelo Claude do Zen (ver nota acima)        |
| `SJ_TRUNC_CHARS`   | `4000`                        | Corte do texto de cada sentença              |
| `SJ_CORPUS_PATH`   | walk-up até `data/`           | Caminho do JSON do corpus                    |
| `SJ_BASE_URL`      | `https://opencode.ai/zen/v1`  | Outro endpoint Anthropic-compatible          |

## Estrutura

| Arquivo                 | Papel                                                    |
| ----------------------- | -------------------------------------------------------- |
| `lib/config.ts`         | Lê e valida o ambiente                                   |
| `lib/corpus.ts`         | Resolve o caminho, faz parse e valida o JSON             |
| `lib/prompt.ts`         | Monta o system prompt com o corpus embutido              |
| `lib/provider.ts`       | Monta o modelo no Zen e marca o system prompt para cache  |
| `lib/realce.ts`         | Isola números de processo CNJ num texto                   |
| `lib/realce-hast.ts`    | Plugin rehype que aplica o realce no markdown renderizado |
| `lib/errors.ts`         | Traduz o erro da transport em texto para a pessoa         |
| `app/api/chat/route.ts` | `streamText` contra o Zen                                |
| `app/page.tsx`          | Server component: lê o corpus e passa o acervo            |
| `app/chat.tsx`          | Client component: `useChat`, streaming, composição        |

## Fora do escopo deste v1

Tools/function calling, RAG com embeddings, seletor de juiz, upload de peça e
persistência de conversa. O corpus da juíza Graziela (`data/corpus.json`, 110
sentenças, ≈480 mil tokens no corte de 4000) não cabe nesta abordagem — precisa
de tools ou RAG.

## Uma pegadinha do ambiente

**O `next dev` reescreve `AGENTS.md` e `CLAUDE.md`.** Ele os regenera a cada
boot; estão commitados para o tree ficar limpo. Para desligar, ponha
`agentRules: false` no `next.config.ts`.

## Por que pnpm

Duas razões concretas, não preferência:

- **O npm quebrava o vitest.** Todo `npm install <pacote>` deixava o binding
  nativo do rolldown faltando ([npm/cli#4828](https://github.com/npm/cli/issues/4828)),
  e o `npm test` morria com `Cannot find native binding`, exigindo apagar
  `node_modules` a cada instalação. Com pnpm isso não acontece.
- **O node_modules estrito do pnpm pega dependência não declarada.** Ele
  flagrou que `lib/realce-hast.ts` importava tipos de `hast` sem `@types/hast`
  no `package.json` — funcionava só pelo hoisting do npm, via `react-markdown`.
