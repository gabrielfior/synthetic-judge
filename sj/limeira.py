"""
Códigos das varas da comarca de Limeira/SP (comarca 320) no e-SAJ do TJSP.

Extraídos de GET https://esaj.tjsp.jus.br/cjpg/varasTreeSelect.do e validados
um a um. Cuidado: a árvore lista códigos duplicados para a mesma vara
(ex.: "320-1" e "320-7011" ambos como 1ª Vara Cível). Só os daqui retornam
resultado — os outros devolvem zero.
"""

CIVEIS = {
    "320-1": "1ª Vara Cível",
    "320-2": "2ª Vara Cível",
    "320-3": "3ª Vara Cível",
    "320-4": "4ª Vara Cível",
    "320-7029": "5ª Vara Cível",
}
FAZENDA = {"320-8": "Vara da Fazenda Pública"}
FAMILIA = {"320-7031": "Vara da Família e das Sucessões"}

# Juizado Especial dispensa relatório (art. 38 da Lei 9.099/95) -> sem peça de entrada.
JUIZADOS = {"320-7": "Juizado Especial Cível e Criminal",
            "320-22": "Vara do Juizado Especial Cível e Criminal"}

ALVO = {**CIVEIS, **FAZENDA, **FAMILIA}
VALUES = ",".join(ALVO)
