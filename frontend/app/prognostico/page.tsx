import Link from 'next/link';
import type { Classe } from '@/lib/prognostico';
import { chamarApi } from '@/lib/python';
import { Prognostico } from './prognostico';

// A taxonomia vem do pipeline Python em tempo de requisição; não há o que pré-renderizar.
export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Prognóstico — Juiz sintético',
  description: 'Estime procedência, prazo e dano moral de um caso em Limeira.',
};

export default async function Page() {
  let classes: Classe[];
  try {
    classes = (await chamarApi<{ classes: Classe[] }>('taxonomia')).classes;
  } catch (e) {
    return (
      <div className="folha">
        <header className="cabeca">
          <h1 className="juizo">Prognóstico indisponível</h1>
        </header>
        <main className="conteudo">
          <div className="falha" role="alert">
            <p>{(e as Error).message}</p>
          </div>
          <p className="nota-pagina">
            <Link href="/">Voltar à conversa</Link>
          </p>
        </main>
      </div>
    );
  }

  return <Prognostico classes={classes} />;
}
