'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useChat } from '@ai-sdk/react';
import type { UIMessage } from 'ai';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { mensagemDeErro } from '@/lib/errors';
import { rehypeProcessos } from '@/lib/realce-hast';

const EXEMPLOS = [
  'Como ele fundamenta habilitação de crédito?',
  'Que critérios usa em acidente de trânsito?',
  'Como ele trata os contratos bancários?',
];

function textoDe(mensagem: UIMessage): string {
  return mensagem.parts
    .map((parte) => (parte.type === 'text' ? parte.text : ''))
    .join('');
}

// O modelo responde em markdown; sem renderizar, os ** e ## apareceriam crus.
const REHYPE = [rehypeProcessos];

// Tabela é GFM, não CommonMark: sem o remark-gfm os pipes chegam como texto.
const REMARK = [remarkGfm];

const COMPONENTES: Components = {
  // A tabela rola dentro do próprio invólucro; a página nunca rola na horizontal.
  table: ({ children }) => (
    <div className="tabela">
      <table>{children}</table>
    </div>
  ),
};

function Resposta({ texto, escrevendo }: { texto: string; escrevendo: boolean }) {
  return (
    <div className="resposta">
      <Markdown remarkPlugins={REMARK} rehypePlugins={REHYPE} components={COMPONENTES}>
        {texto}
      </Markdown>
      {escrevendo && <span className="caret" aria-hidden="true" />}
    </div>
  );
}

export type Acervo = {
  total: number;
  vara: string;
  comarca: string;
  modelo: string;
};

export function Chat({ total, vara, comarca, modelo }: Acervo) {
  const { messages, sendMessage, status, error, stop, clearError, regenerate } = useChat();
  const [rascunho, setRascunho] = useState('');
  const escritaRef = useRef<HTMLTextAreaElement>(null);
  const fimRef = useRef<HTMLDivElement>(null);

  const ocupado = status === 'submitted' || status === 'streaming';

  // A caixa cresce com o texto até o limite de altura do CSS.
  useEffect(() => {
    const caixa = escritaRef.current;
    if (caixa) {
      caixa.style.height = 'auto';
      caixa.style.height = `${caixa.scrollHeight}px`;
    }
  }, [rascunho]);

  useEffect(() => {
    fimRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, status]);

  function enviar() {
    const texto = rascunho.trim();
    if (!texto || ocupado) return;
    sendMessage({ text: texto });
    setRascunho('');
  }

  function perguntar(exemplo: string) {
    sendMessage({ text: exemplo });
    setRascunho('');
  }

  return (
    <div className="tela">
      <header className="cabeca cabeca-linha">
        <div>
          {/* O juízo, não o juiz: o nome do magistrado não aparece na interface. */}
          <h1 className="juizo">
            {vara} — {comarca}
          </h1>
          <p className="acervo">
            {total} {total === 1 ? 'sentença' : 'sentenças'}, respondidas por {modelo}
          </p>
        </div>
        <Link className="ligacao" href="/prognostico">
          Estimar um caso
        </Link>
      </header>

      <main className="autos">
        {messages.length === 0 && (
          <div className="vazio">
            <p className="convite">Comece por uma pergunta.</p>
            <div className="exemplos">
              {EXEMPLOS.map((exemplo) => (
                <button className="exemplo" key={exemplo} onClick={() => perguntar(exemplo)}>
                  {exemplo}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((mensagem, i) => {
          const ultima = i === messages.length - 1;
          return mensagem.role === 'user' ? (
            <div className="turno turno-usuario" key={mensagem.id}>
              <p className="pergunta">{textoDe(mensagem)}</p>
            </div>
          ) : (
            <div className="turno" key={mensagem.id}>
              <Resposta texto={textoDe(mensagem)} escrevendo={ultima && status === 'streaming'} />
            </div>
          );
        })}

        {status === 'submitted' && (
          <div className="turno">
            <p className="pensando">Consultando os autos</p>
          </div>
        )}

        {error && (
          <div className="falha" role="alert">
            <p>{mensagemDeErro(error)}</p>
            <button
              className="tentar"
              onClick={() => {
                clearError();
                regenerate();
              }}
            >
              Tentar de novo
            </button>
          </div>
        )}

        <div ref={fimRef} />
      </main>

      <form
        className="compositor"
        onSubmit={(e) => {
          e.preventDefault();
          enviar();
        }}
      >
        <textarea
          className="escrita"
          ref={escritaRef}
          rows={1}
          value={rascunho}
          placeholder="Pergunte sobre as sentenças"
          aria-label="Pergunte sobre as sentenças"
          onChange={(e) => setRascunho(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              enviar();
            }
          }}
        />
        {ocupado ? (
          <button className="enviar enviar-parar" type="button" onClick={stop}>
            Parar
          </button>
        ) : (
          <button className="enviar" type="submit" disabled={rascunho.trim() === ''}>
            Enviar
          </button>
        )}
      </form>
    </div>
  );
}
