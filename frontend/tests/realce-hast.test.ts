import { describe, expect, test } from 'vitest';
import type { Element, Root } from 'hast';
import { rehypeProcessos } from '../lib/realce-hast';

function arvore(...children: Element['children']): Root {
  return { type: 'root', children: [{ type: 'element', tagName: 'p', properties: {}, children }] };
}

function paragrafo(raiz: Root): Element {
  return raiz.children[0] as Element;
}

function transformar(raiz: Root): Root {
  rehypeProcessos()(raiz);
  return raiz;
}

describe('rehypeProcessos', () => {
  test('envolve o numero de processo num span com a classe processo', () => {
    const raiz = transformar(arvore({ type: 'text', value: '1006468-61.2024.8.26.0344' }));

    expect(paragrafo(raiz).children).toEqual([
      {
        type: 'element',
        tagName: 'span',
        properties: { className: ['processo'] },
        children: [{ type: 'text', value: '1006468-61.2024.8.26.0344' }],
      },
    ]);
  });

  test('preserva o texto ao redor do processo', () => {
    const raiz = transformar(
      arvore({ type: 'text', value: 'Na sentença 1006468-61.2024.8.26.0344 ele decidiu.' }),
    );
    const filhos = paragrafo(raiz).children;

    expect(filhos).toHaveLength(3);
    expect(filhos[0]).toEqual({ type: 'text', value: 'Na sentença ' });
    expect((filhos[1] as Element).tagName).toBe('span');
    expect(filhos[2]).toEqual({ type: 'text', value: ' ele decidiu.' });
  });

  test('deixa texto sem processo intocado', () => {
    const raiz = transformar(arvore({ type: 'text', value: 'Julgou procedente.' }));

    expect(paragrafo(raiz).children).toEqual([{ type: 'text', value: 'Julgou procedente.' }]);
  });

  test('desce em elementos aninhados — o processo costuma vir dentro de strong', () => {
    const raiz = transformar(
      arvore({
        type: 'element',
        tagName: 'strong',
        properties: {},
        children: [{ type: 'text', value: '1006468-61.2024.8.26.0344' }],
      }),
    );
    const forte = paragrafo(raiz).children[0] as Element;

    expect((forte.children[0] as Element).properties).toEqual({ className: ['processo'] });
  });

  test('nao mexe em texto dentro de code — quebraria bloco de codigo', () => {
    const raiz = transformar(
      arvore({
        type: 'element',
        tagName: 'code',
        properties: {},
        children: [{ type: 'text', value: '1006468-61.2024.8.26.0344' }],
      }),
    );
    const codigo = paragrafo(raiz).children[0] as Element;

    expect(codigo.children).toEqual([{ type: 'text', value: '1006468-61.2024.8.26.0344' }]);
  });
});
