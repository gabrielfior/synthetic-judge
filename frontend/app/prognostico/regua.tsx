import { posicao } from '@/lib/prognostico';

export type Marca = { valor: number; rotulo: string };

type Props = {
  /** Extremos da escala. */
  dominio: [number, number];
  /** Onde ficam os números impressos na escala. */
  escala: Marca[];
  /** O intervalo (IC 95% ou p25–p75), em unidades do domínio. */
  faixa: [number, number] | null;
  /** A estimativa pontual. */
  ponto: number;
  /** Onde o juízo todo cai na mesma escala, para situar a classe. */
  referencia?: Marca;
  /** O que um leitor de tela deve dizer no lugar do desenho. */
  descricao: string;
};

/**
 * Um trecho da régua dos autos: o intervalo vai em vinho sobre o traço, a
 * estimativa é a marca vertical e o juízo todo é a linha tracejada. O desenho
 * repete o que o texto ao lado já diz; por isso é `role="img"` com descrição.
 */
export function Regua({ dominio, escala, faixa, ponto, referencia, descricao }: Props) {
  const [min, max] = dominio;
  const x = (v: number) => posicao(v, min, max);
  // Rótulo que passaria da borda direita encosta nela em vez de vazar.
  const aoFim = (v: number) => x(v) > 72;

  return (
    <div className="regua" role="img" aria-label={descricao}>
      <div className="regua-trilho">
        {referencia && (
          <span className="regua-ref" style={{ left: `${x(referencia.valor)}%` }}>
            <span
              className={aoFim(referencia.valor) ? 'regua-ref-rotulo regua-ref-fim' : 'regua-ref-rotulo'}
            >
              {referencia.rotulo}
            </span>
          </span>
        )}
        {faixa && (
          <span
            className="regua-faixa"
            style={{ left: `${x(faixa[0])}%`, width: `${Math.max(0.8, x(faixa[1]) - x(faixa[0]))}%` }}
          />
        )}
        <span className="regua-ponto" style={{ left: `${x(ponto)}%` }} />
      </div>
      <div className="regua-escala" aria-hidden="true">
        {escala.map((m) => (
          <span
            key={m.valor}
            style={{
              left: `${x(m.valor)}%`,
              transform: `translateX(${m.valor <= min ? '0' : m.valor >= max ? '-100%' : '-50%'})`,
            }}
          >
            {m.rotulo}
          </span>
        ))}
      </div>
    </div>
  );
}
