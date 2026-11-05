import { resolve } from 'node:path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // O corpus vive em `data/` na raiz do repo, fora de `frontend/`. Sem isto o
  // build de producao nao empacota o JSON e a rota /api/chat sobe sem corpus.
  outputFileTracingRoot: resolve(import.meta.dirname, '..'),
  outputFileTracingIncludes: {
    '/api/chat': ['../data/sentencas_juiz.json'],
  },
};

export default nextConfig;
