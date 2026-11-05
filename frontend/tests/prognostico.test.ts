import { describe, expect, test } from 'vitest';
import {
  avisoDeDegrau,
  escopo,
  meses,
  pct,
  porGrupo,
  posicao,
  reais,
  resultadoLegivel,
} from '../lib/prognostico';

describe('formatação', () => {
  test('pct arredonda para inteiro', () => {
    expect(pct(0.3412)).toBe('34%');
    expect(pct(1)).toBe('100%');
  });

  test('meses usa vírgula decimal', () => {
    expect(meses(228)).toBe('7,5');
    expect(meses(30.44)).toBe('1,0');
  });

  test('reais separa milhar à brasileira', () => {
    expect(reais(8000)).toMatch(/^R\$ 8\.000$/);
    expect(reais(12750)).toMatch(/^R\$ 12\.750$/);
  });

  test('resultadoLegivel traduz os códigos e admite ausência', () => {
    expect(resultadoLegivel('parcialmente_procedente')).toBe('parcialmente procedente');
    expect(resultadoLegivel(null)).toBe('resultado não lido');
    expect(resultadoLegivel('algo_novo')).toBe('algo novo');
  });
});

describe('posicao', () => {
  test('mapeia para 0–100 e prende nas pontas', () => {
    expect(posicao(5, 0, 10)).toBe(50);
    expect(posicao(-3, 0, 10)).toBe(0);
    expect(posicao(99, 0, 10)).toBe(100);
  });
});

describe('porGrupo', () => {
  test('agrupa mantendo a ordem de aparição', () => {
    const cs = [
      { nome: 'a', grupo: 'G', definicao: '' },
      { nome: 'b', grupo: 'H', definicao: '' },
      { nome: 'c', grupo: 'G', definicao: '' },
    ];
    expect(porGrupo(cs).map((g) => [g.grupo, g.classes.map((c) => c.nome)])).toEqual([
      ['G', ['a', 'c']],
      ['H', ['b']],
    ]);
  });
});

describe('avisoDeDegrau', () => {
  const consulta = { classe: 'A', grupo: 'G' };

  test('sem descida, sem aviso', () => {
    expect(avisoDeDegrau({ degrau: 'classe', n: 90, desceu: false, insuficiente: false }, consulta)).toBeNull();
  });

  test('descida ao grupo diz qual e o n', () => {
    const a = avisoDeDegrau({ degrau: 'grupo', n: 239, desceu: true, insuficiente: false }, consulta);
    expect(a).toContain('«G»');
    expect(a).toContain('n=239');
  });

  test('descida ao piso diz que é o juízo inteiro, em português certo', () => {
    const a = avisoDeDegrau({ degrau: 'piso', n: 1260, desceu: true, insuficiente: false }, consulta);
    expect(a).toContain('vem de todo o Procedimento Comum de Limeira');
  });

  test('base insuficiente avisa para não confiar, mesmo sem descer', () => {
    const a = avisoDeDegrau({ degrau: 'classe', n: 6, desceu: false, insuficiente: true }, consulta);
    expect(a).toContain('não confie');
  });
});

describe('escopo', () => {
  const consulta = { classe: 'A', grupo: 'G' };
  const eixo = (degrau: 'classe' | 'grupo' | 'piso') => ({ degrau, n: 1, desceu: false, insuficiente: false });

  test('nomeia o degrau em que o número foi calculado', () => {
    expect(escopo(eixo('classe'), consulta)).toBe('da classe «A»');
    expect(escopo(eixo('grupo'), consulta)).toBe('do grupo «G»');
    expect(escopo(eixo('piso'), consulta)).toBe('do juízo todo');
  });
});
