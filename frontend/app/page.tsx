import { MODELO_PADRAO } from '@/lib/config';
import { loadCorpus } from '@/lib/corpus';
import { Chat, type Acervo } from './chat';

// O corpus vem do disco, então esta página não pode ser pré-renderizada no build.
export const dynamic = 'force-dynamic';

function lerAcervo(): { acervo: Acervo } | { falha: string } {
  try {
    const corpus = loadCorpus();
    const primeira = corpus[0];
    return {
      acervo: {
        total: corpus.length,
        vara: primeira.vara,
        comarca: primeira.comarca,
        modelo: process.env.SJ_MODEL?.trim() || MODELO_PADRAO,
      },
    };
  } catch (e) {
    return { falha: (e as Error).message };
  }
}

export default function Page() {
  const resultado = lerAcervo();

  if ('falha' in resultado) {
    return (
      <div className="tela">
        <header className="cabeca">
          <h1 className="juizo">Sem corpus para consultar</h1>
        </header>
        <main className="autos">
          <div className="falha" role="alert">
            <p>{resultado.falha}</p>
          </div>
        </main>
      </div>
    );
  }

  return <Chat {...resultado.acervo} />;
}
