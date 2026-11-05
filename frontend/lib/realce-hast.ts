import type { Element, ElementContent, Root } from 'hast';
import { segmentarProcessos } from './realce';

// Dentro destes, o texto é literal: mexer quebraria o conteúdo.
const INTOCAVEIS = new Set(['code', 'pre']);

function transformarFilhos(filhos: ElementContent[]): ElementContent[] {
  const saida: ElementContent[] = [];

  for (const filho of filhos) {
    if (filho.type === 'text') {
      for (const segmento of segmentarProcessos(filho.value)) {
        saida.push(
          segmento.tipo === 'processo'
            ? {
                type: 'element',
                tagName: 'span',
                properties: { className: ['processo'] },
                children: [{ type: 'text', value: segmento.valor }],
              }
            : { type: 'text', value: segmento.valor },
        );
      }
      continue;
    }

    if (filho.type === 'element' && !INTOCAVEIS.has(filho.tagName)) {
      filho.children = transformarFilhos(filho.children);
    }
    saida.push(filho);
  }

  return saida;
}

/**
 * Plugin rehype que isola os números de processo CNJ do markdown da resposta em
 * spans próprios, para a UI compô-los em dígitos tabulares.
 */
export function rehypeProcessos() {
  return (raiz: Root): void => {
    raiz.children = transformarFilhos(raiz.children as ElementContent[]) as Root['children'];
  };
}

export type { Element };
