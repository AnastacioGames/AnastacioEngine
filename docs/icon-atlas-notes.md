# Atlas de ícones

## Formato atual

A interface usa dois atlas raster:

- `blender_icons16.png`, com tamanho mínimo de 602 × 640;
- `blender_icons32.png`, com tamanho mínimo de 1204 × 1280.

O estilo é escolhido em `User Preferences > Interface > Icons` (`view.icon_style`, `U.icon_style`):

- `Range` (padrão): atlas embutido, ícones brancos tingidos pelo tema (`MONO_TEXTURE`);
- `UPBGE`: atlas coloridos da UPBGE 0.2.5b em `datafiles/icons_upbge/`, desenhados como `TEXTURE` sem tinta;
- `Blender 5`: ícones monocromáticos do Blender 5.0 em `datafiles/icons_blender5/`, tingidos pelo tema.

Um diretório em `User Preferences > Files > Icons` sobrepõe o estilo e deve conter os dois PNGs diretamente.
A engine valida os arquivos e usa o atlas embutido se algum estiver ausente ou inválido. Trocar o estilo ou o
diretório recarrega a textura na hora (`UI_icons_reload_internal`).

## Atlas UPBGE

`tools/upbge_icons/build_upbge_icon_atlas.py` extrai os dois atlas do `blender.exe` da UPBGE
(`tools/upbge-0.2.5b/Release`), lê a ordem 2.79 em `tools/upbge_icons/UI_icons_upbge.h` (cópia do Blender
v2.79b) e copia cada ícone, pelo nome, para a célula correspondente do `UI_icons.h` da Range. Ícones que só
existem na Range (RangeArmor, Discord, Patreon) usam o próprio desenho. Rode de novo sempre que o
`UI_icons.h` da Range ganhar, perder ou reordenar ícones; `--report` lista os fallbacks.

## Atlas Blender 5

`tools/blender5_icons/build_blender5_icon_atlas.py` rasteriza os SVGs de `tools/blender5_icons/icons_svg/`
(cópia de `release/datafiles/icons_svg` do branch `blender-v5.0-release`) com `render_svgs.cjs`
(`@resvg/resvg-js`, instalado via npm fora do repo; passe `--node-modules`). Remapeia por nome com uma
tabela de apelidos. `GAME`, `LOGIC`, `SPACE2`, `SPACE3`, `POTATO` e os ícones da Range mantêm o desenho da Range.

## Conversão futura

SVGs individuais da UPBGE podem servir como fonte artística, mas não podem ser copiados diretamente. Uma
conversão precisa rasterizar os dois tamanhos acima e preservar a ordem definida em
`source/source/blender/editors/include/UI_icons.h`.

Não dependa de um caminho absoluto para outra cópia local da UPBGE; registre no próprio repositório qualquer
fonte que venha a fazer parte do processo suportado.
