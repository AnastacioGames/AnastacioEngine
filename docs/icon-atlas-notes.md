# Atlas de ícones

## Formato atual

A interface usa dois atlas raster:

- `blender_icons16.png`, com tamanho mínimo de 602 × 640;
- `blender_icons32.png`, com tamanho mínimo de 1204 × 1280.

O diretório é configurado em `User Preferences > Files > Icons` e deve conter os dois PNGs diretamente. A
engine valida os arquivos na inicialização e usa o atlas embutido se algum deles estiver ausente ou inválido.
O seletor antigo `Icon Style` foi removido; a troca do atlas externo não exige recompilação.

## Conversão futura

SVGs individuais da UPBGE podem servir como fonte artística, mas não podem ser copiados diretamente. Uma
conversão precisa rasterizar os dois tamanhos acima e preservar a ordem definida em
`source/source/blender/editors/include/UI_icons.h`.

Não dependa de um caminho absoluto para outra cópia local da UPBGE; registre no próprio repositório qualquer
fonte que venha a fazer parte do processo suportado.
