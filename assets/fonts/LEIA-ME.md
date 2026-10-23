# Fontes do relatório em PDF

Inter e Space Grotesk, ambas sob a licença SIL Open Font License 1.1 (textos em `OFL-Inter.txt` e `OFL-SpaceGrotesk.txt`).
Nenhuma das duas declara nome reservado no aviso de copyright.

## Origem (baixadas uma única vez, em 2026-10-08)

Repositório oficial do Google Fonts, https://github.com/google/fonts (pasta `ofl/`):

- `Inter-Variable.ttf`: `ofl/inter/Inter[opsz,wght].ttf`
- `SpaceGrotesk-Variable.ttf`: `ofl/spacegrotesk/SpaceGrotesk[wght].ttf`

Depois disso a geração do PDF é totalmente offline: o HTML só referencia estes arquivos locais.

## Versões estáticas (as usadas no PDF)

O Chrome embute fontes variáveis no PDF como "Type 3" (sem nome de fonte verificável). Para embutir TrueType de verdade,
foram geradas instâncias estáticas a partir dos arquivos variáveis, sem alterar os desenhos das letras:

```
fonttools varLib.instancer Inter-Variable.ttf wght=400 opsz=14 -o Inter-Regular.ttf --update-name-table
fonttools varLib.instancer Inter-Variable.ttf wght=600 opsz=14 -o Inter-SemiBold.ttf --update-name-table
fonttools varLib.instancer Inter-Variable.ttf wght=700 opsz=14 -o Inter-Bold.ttf --update-name-table
fonttools varLib.instancer SpaceGrotesk-Variable.ttf wght=500 -o SpaceGrotesk-Medium.ttf --update-name-table
fonttools varLib.instancer SpaceGrotesk-Variable.ttf wght=700 -o SpaceGrotesk-Bold.ttf --update-name-table
```

(`pip install fonttools`; só necessário para regenerar, não faz parte do projeto.)

Uso no relatório: títulos em Space Grotesk (500 e 700), texto em Inter (400, 600 e 700).
