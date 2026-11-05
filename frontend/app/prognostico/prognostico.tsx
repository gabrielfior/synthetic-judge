'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import {
  avisoDeDegrau,
  emMeses,
  escopo,
  meses,
  pct,
  porGrupo,
  reais,
  resultadoLegivel,
  type Classe,
  type Eixo,
  type Estruturada,
  type Juizo,
  type Resultado,
} from '@/lib/prognostico';
import { Regua } from './regua';

const EXEMPLOS = [
  'Meu cliente é aposentado do INSS e descobriu um empréstimo consignado que nunca contratou, descontando do benefício. Quero a devolução em dobro e danos morais.',
  'Cobrança de três duplicatas não pagas de uma venda de material de construção, R$ 47 mil, com canhotos assinados.',
  'Colisão traseira em semáforo; o réu destruiu a traseira do carro do meu cliente. Pedimos o conserto e dano moral.',
];

const NOTA_REFERENCIA =
  'Prazo e valor variam pouco entre as classes: leia como referência do juízo, não como estimativa deste caso.';

type Consulta = {
  classe: string | null;
  /** A classe que a LLM escolheu: a explicação (`motivo`) só vale para ela. */
  classeInferida: string | null;
  pedeDanoMoral: boolean | null;
  alternativas: string[];
  motivo: string;
};

type Calculo = { resultado: Resultado; juizo: Juizo };

async function postar<T>(rota: string, corpo: unknown, signal?: AbortSignal): Promise<T> {
  const resposta = await fetch(rota, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(corpo),
    signal,
  });
  const json = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(json.error ?? `Falha ao consultar (HTTP ${resposta.status}).`);
  return json as T;
}

export function Prognostico({ classes }: { classes: Classe[] }) {
  const [texto, setTexto] = useState('');
  const [analisando, setAnalisando] = useState(false);
  const [consulta, setConsulta] = useState<Consulta | null>(null);
  const [calculo, setCalculo] = useState<Calculo | null>(null);
  const [calculando, setCalculando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const consultaRef = useRef<HTMLElement>(null);
  const escritaRef = useRef<HTMLTextAreaElement>(null);

  const grupos = porGrupo(classes);
  const classe = consulta?.classe ?? null;

  // A caixa cresce com o texto até o limite de altura do CSS.
  useEffect(() => {
    const caixa = escritaRef.current;
    if (caixa) {
      caixa.style.height = 'auto';
      caixa.style.height = `${caixa.scrollHeight}px`;
    }
  }, [texto]);

  // Recalcula a cada troca de classe, sem LLM: é aritmética sobre a base. A
  // chamada anterior é abortada, para uma resposta atrasada não sobrescrever a nova.
  useEffect(() => {
    if (!consulta) return;
    const controle = new AbortController();
    setCalculando(true);
    postar<Calculo>('/api/prognostico/calcular', { classe }, controle.signal)
      .then((c) => {
        setCalculo(c);
        setErro(null);
      })
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setErro(e.message);
      })
      .finally(() => {
        if (!controle.signal.aborted) setCalculando(false);
      });
    return () => controle.abort();
    // `consulta` entra só pela existência: o que dispara o cálculo é a classe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classe, consulta !== null]);

  async function analisar() {
    const descricao = texto.trim();
    if (!descricao || analisando) return;
    setAnalisando(true);
    setErro(null);
    try {
      const r = await postar<{ estruturada: Estruturada }>('/api/prognostico/estruturar', {
        texto: descricao,
      });
      setConsulta({
        classe: r.estruturada.classe,
        classeInferida: r.estruturada.classe,
        pedeDanoMoral: r.estruturada.pede_dano_moral,
        alternativas: r.estruturada.alternativas,
        motivo: r.estruturada.motivo,
      });
      requestAnimationFrame(() => consultaRef.current?.scrollIntoView({ block: 'start' }));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setAnalisando(false);
    }
  }

  function escolherClasseSemTexto() {
    setErro(null);
    setConsulta({
      classe: null,
      classeInferida: null,
      pedeDanoMoral: null,
      alternativas: [],
      motivo: '',
    });
  }

  const definicao = classes.find((c) => c.nome === classe)?.definicao;
  // A leitura inicial volta como opção quando o advogado troca de classe.
  const outras = consulta
    ? [consulta.classeInferida, ...consulta.alternativas].filter(
        (a, i, todas): a is string => a !== null && a !== classe && todas.indexOf(a) === i,
      )
    : [];
  const explicacaoVale = consulta !== null && classe === consulta.classeInferida;

  return (
    <div className="folha">
      <header className="cabeca cabeca-linha">
        <div>
          <h1 className="juizo">Prognóstico</h1>
          <p className="acervo">
            4ª Vara Cível de Limeira, procedimento comum, sentenças de 2024 a 2026
          </p>
        </div>
        <Link className="ligacao" href="/">
          Conversar com as sentenças
        </Link>
      </header>

      <main className="conteudo">
        <form
          className="descricao"
          onSubmit={(e) => {
            e.preventDefault();
            analisar();
          }}
        >
          <label className="descricao-rotulo" htmlFor="descricao">
            Descreva o caso
          </label>
          <textarea
            id="descricao"
            ref={escritaRef}
            className="descricao-texto"
            rows={4}
            value={texto}
            maxLength={8000}
            placeholder="Quem é a parte contrária, o que aconteceu e o que você pretende pedir."
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                analisar();
              }
            }}
          />
          <div className="descricao-acoes">
            <button className="enviar" type="submit" disabled={analisando || texto.trim() === ''}>
              {analisando ? 'Lendo o caso…' : 'Analisar o caso'}
            </button>
            <button className="exemplo" type="button" onClick={escolherClasseSemTexto}>
              Escolher a classe sem descrever
            </button>
          </div>
          {!consulta && texto === '' && (
            <div className="exemplos">
              {EXEMPLOS.map((e) => (
                <button className="exemplo" type="button" key={e} onClick={() => setTexto(e)}>
                  {e}
                </button>
              ))}
            </div>
          )}
        </form>

        {erro && (
          <div className="falha falha-pagina" role="alert">
            <p>{erro}</p>
          </div>
        )}

        {consulta && (
          <section className="consulta" ref={consultaRef} aria-labelledby="t-consulta">
            <h2 id="t-consulta">Como entendi o caso</h2>
            <p className="orientacao">
              Confira a classe: tudo abaixo depende dela. Ao trocar, os números se recalculam.
            </p>

            <div className="campo">
              <label htmlFor="classe">Classe</label>
              <select
                id="classe"
                value={classe ?? ''}
                onChange={(e) => setConsulta({ ...consulta, classe: e.target.value || null })}
              >
                <option value="">Não identificada: usar o juízo todo</option>
                {grupos.map((g) => (
                  <optgroup key={g.grupo} label={g.grupo}>
                    {g.classes.map((c) => (
                      <option key={c.nome} value={c.nome}>
                        {c.nome}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            {definicao && <p className="definicao">{definicao}</p>}
            {!classe && consulta.motivo && explicacaoVale && (
              <p className="definicao">{consulta.motivo}</p>
            )}

            {outras.length > 0 && (
              <p className="alternativas">
                Também plausível:{' '}
                {outras.map((a) => (
                  <button
                    className="exemplo"
                    type="button"
                    key={a}
                    onClick={() => setConsulta({ ...consulta, classe: a })}
                  >
                    {a}
                  </button>
                ))}
              </p>
            )}

            <fieldset className="campo-escolha">
              <legend>Pede dano moral</legend>
              {(
                [
                  [true, 'Sim'],
                  [false, 'Não'],
                  [null, 'Não informado'],
                ] as const
              ).map(([valor, rotulo]) => (
                <button
                  key={rotulo}
                  type="button"
                  className="escolha"
                  aria-pressed={consulta.pedeDanoMoral === valor}
                  onClick={() => setConsulta({ ...consulta, pedeDanoMoral: valor })}
                >
                  {rotulo}
                </button>
              ))}
            </fieldset>
            {classe && explicacaoVale && consulta.motivo && (
              <p className="porque">Como li o caso: {consulta.motivo}</p>
            )}
          </section>
        )}

        {consulta && calculo && (
          <div className="achados" aria-live="polite" aria-busy={calculando}>
            <Achados
              calculo={calculo}
              pede={consulta.pedeDanoMoral}
              ocupado={calculando}
            />
          </div>
        )}
      </main>
    </div>
  );
}

function Achados({
  calculo,
  pede,
  ocupado,
}: {
  calculo: Calculo;
  pede: boolean | null;
  ocupado: boolean;
}) {
  const { resultado: r, juizo } = calculo;
  const c = r.consulta;
  const p = r.procedencia;
  const pz = r.prazo;
  const dm = r.dano_moral;
  const refProc = p.degrau !== 'piso' ? juizo.procedencia.probabilidade : null;
  const refPrazo = pz.degrau !== 'piso' ? emMeses(juizo.prazo.quartis_dias[1]) : null;
  const [q1, med, q3] = pz.quartis_dias.map(emMeses);

  return (
    <div className={ocupado ? 'achados-corpo achados-ocupado' : 'achados-corpo'}>
      <section className="achado" aria-labelledby="t-proc">
        <h2 id="t-proc">Procedência</h2>
        <div className="achado-corpo">
          <p className="numero">{pct(p.probabilidade ?? 0)}</p>
          <div className="achado-texto">
            <p className="frase">
              dos {p.n} casos {escopo(p, c)} terminaram procedentes ou parcialmente procedentes.
            </p>
            <Regua
              dominio={[0, 100]}
              escala={[0, 25, 50, 75, 100].map((v) => ({ valor: v, rotulo: `${v}%` }))}
              faixa={p.ic95 ? [p.ic95[0] * 100, p.ic95[1] * 100] : null}
              ponto={(p.probabilidade ?? 0) * 100}
              referencia={
                refProc !== null
                  ? { valor: refProc * 100, rotulo: `juízo todo ${pct(refProc)}` }
                  : undefined
              }
              descricao={
                `Procedência de ${pct(p.probabilidade ?? 0)}` +
                (p.ic95 ? `, com intervalo de 95% entre ${pct(p.ic95[0])} e ${pct(p.ic95[1])}.` : '.')
              }
            />
            {p.ic95 && (
              <p className="detalhe">
                Intervalo de 95%: de {pct(p.ic95[0])} a {pct(p.ic95[1])}. Vale para casos que
                chegam a sentença; acordos e desistências não estão na base.
              </p>
            )}
            <Aviso eixo={p} consulta={c} />
          </div>
        </div>
      </section>

      <section className="achado" aria-labelledby="t-prazo">
        <h2 id="t-prazo">Prazo até a sentença</h2>
        <div className="achado-corpo">
          <p className="numero">
            {meses(pz.quartis_dias[1])} <span className="unidade">meses</span>
          </p>
          <div className="achado-texto">
            <p className="frase">
              é a mediana nos {pz.n} casos {escopo(pz, c)}; metade levou entre {meses(pz.quartis_dias[0])}{' '}
              e {meses(pz.quartis_dias[2])} meses.
            </p>
            <Regua
              dominio={[0, 24]}
              escala={[0, 6, 12, 18, 24].map((v) => ({ valor: v, rotulo: String(v) }))}
              faixa={[q1, q3]}
              ponto={med}
              referencia={
                refPrazo !== null
                  ? { valor: refPrazo, rotulo: `juízo todo ${String(refPrazo.toFixed(1)).replace('.', ',')}` }
                  : undefined
              }
              descricao={`Mediana de ${meses(pz.quartis_dias[1])} meses; metade dos casos entre ${meses(pz.quartis_dias[0])} e ${meses(pz.quartis_dias[2])} meses.`}
            />
            <p className="detalhe">
              Em meses. Prazo estimado a partir do número do processo, e enviesado para cima: só
              entram casos que chegaram a sentença.
            </p>
            <p className="nota">{NOTA_REFERENCIA}</p>
            <Aviso eixo={pz} consulta={c} />
          </div>
        </div>
      </section>

      {pede === false ? (
        <section className="achado" aria-labelledby="t-dm">
          <h2 id="t-dm">Dano moral</h2>
          <p className="detalhe">
            Omitido: a consulta diz que o dano moral não será pedido. Marque “Sim” ou “Não
            informado” para ver.
          </p>
        </section>
      ) : (
        <DanoMoral dm={dm} consulta={c} ref_={juizo.dano_moral} />
      )}

      {r.comparaveis.length > 0 && (
        <section className="achado" aria-labelledby="t-cmp">
          <h2 id="t-cmp">
            Sentenças recentes {r.comparaveis[0].degrau === 'classe' ? 'desta classe' : 'deste grupo'}
          </h2>
          <ul className="comparaveis">
            {r.comparaveis.map((x) => (
              <li key={x.processo}>
                <a href={x.url_pdf} target="_blank" rel="noopener noreferrer">
                  <span className="processo-num">{x.processo}</span>
                </a>
                <span className="comp-meta">
                  {x.data}, {resultadoLegivel(x.resultado)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <details className="limites">
        <summary>Limites desta estimativa</summary>
        <ul>
          <li>A classe foi inferida do texto; confira e corrija se estiver errada.</li>
          <li>
            Só Limeira, de janeiro de 2024 a setembro de 2026: janela curta, sem como separar
            tendência de ruído.
          </li>
          <li>A base só tem casos que chegaram a sentença; acordos não aparecem.</li>
          <li>É uma estatística do juízo, não aconselhamento jurídico.</li>
        </ul>
      </details>
    </div>
  );
}

function Aviso({ eixo, consulta }: { eixo: Eixo; consulta: Resultado['consulta'] }) {
  const aviso = avisoDeDegrau(eixo, consulta);
  return aviso ? <p className="aviso">{aviso}</p> : null;
}

function DanoMoral({
  dm,
  consulta,
  ref_,
}: {
  dm: Resultado['dano_moral'];
  consulta: Resultado['consulta'];
  ref_: Juizo['dano_moral'];
}) {
  const { concessao: c, valor: v, razao: z } = dm;
  const refC = c.degrau !== 'piso' ? ref_.concessao.probabilidade_concessao : null;
  const [v1, vmed, v3] = v.quartis_reais;

  return (
    <section className="achado" aria-labelledby="t-dm">
      <h2 id="t-dm">Dano moral, se pedido</h2>
      <div className="achado-corpo">
        <p className="numero">{pct(c.probabilidade_concessao ?? 0)}</p>
        <div className="achado-texto">
          <p className="frase">
            dos {c.n} pedidos {escopo(c, consulta)} tiveram o dano moral concedido.
          </p>
          <Regua
            dominio={[0, 100]}
            escala={[0, 25, 50, 75, 100].map((x) => ({ valor: x, rotulo: `${x}%` }))}
            faixa={c.ic95 ? [c.ic95[0] * 100, c.ic95[1] * 100] : null}
            ponto={(c.probabilidade_concessao ?? 0) * 100}
            referencia={
              refC !== null ? { valor: refC * 100, rotulo: `juízo todo ${pct(refC)}` } : undefined
            }
            descricao={`Dano moral concedido em ${pct(c.probabilidade_concessao ?? 0)} dos pedidos.`}
          />
          {c.ic95 && (
            <p className="detalhe">
              Intervalo de 95%: de {pct(c.ic95[0])} a {pct(c.ic95[1])}.
            </p>
          )}
          <Aviso eixo={c} consulta={consulta} />
        </div>
      </div>

      {vmed !== undefined && (
        <div className="achado-corpo achado-seguinte">
          <p className="numero">{reais(vmed)}</p>
          <div className="achado-texto">
            <p className="frase">
              é a mediana do valor concedido em {v.n} casos {escopo(v, consulta)}; metade ficou
              entre {reais(v1)} e {reais(v3)}.
            </p>
            <Regua
              dominio={[0, 20000]}
              escala={[0, 5000, 10000, 15000, 20000].map((x) => ({
                valor: x,
                rotulo: x === 0 ? '0' : `${x / 1000} mil`,
              }))}
              faixa={[v1, v3]}
              ponto={vmed}
              descricao={`Mediana de ${reais(vmed)}; metade dos casos entre ${reais(v1)} e ${reais(v3)}.`}
            />
            {z.mediana !== null && !z.insuficiente && (
              <p className="detalhe">
                O valor concedido costuma ser {z.mediana.toFixed(2).replace('.', ',')} do pedido
                (mediana de {z.n} casos {escopo(z, consulta)}).
              </p>
            )}
            <p className="nota">{NOTA_REFERENCIA}</p>
            <Aviso eixo={v} consulta={consulta} />
          </div>
        </div>
      )}
    </section>
  );
}
