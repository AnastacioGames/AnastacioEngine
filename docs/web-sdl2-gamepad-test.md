# Roteiro de teste: patch SDL2 (gamepad) e runtime Web

Cobre o que mudou em 2026-09-20: patch do SDL2 versionado (`tools/web/patch-sdl2-gamepad.py`), aplicado no
configure, `RangeRuntime` Web relinkado (`build-web-release`) e caches Web com `WITH_INTERNATIONAL=OFF`.

## Já verificado (automático)

- `python tools/web/patch-sdl2-gamepad.py --check` retorna 0 (patch aplicado).
- `cmake --preset web-runtime-release` (a partir de `source/`, com o ambiente do emsdk) imprime
  "SDL2 gamepad: patch ja aplicado." e gera sem erro.

## 1. Exportar e abrir

1. No editor, abra um projeto de teste (o mesmo dos pacotes 8201–8211, se possível).
2. Properties > Export Game > **Web (Range)**: **Validar Web**, depois **Exportar Web**, depois **Abrir no navegador**.
3. Esperado: o pré-voo não aponta erro novo e o jogo abre no navegador.

## 2. Regressão geral no navegador

- Render: a cena aparece com luz, sombras e texturas como antes.
- Teclado e mouse respondem.
- Save: salve, recarregue a página e confira que o estado persiste (IDBFS).
- Console do navegador (F12): sem erro novo de shader ou de wasm.

## 3. Gamepad físico (foco do patch)

1. Conecte o controle **antes** de abrir a página e aperte um botão para o navegador reconhecê-lo.
2. Aperte e **solte** cada direção do D-pad. Esperado: a entrada ativa ao apertar e **volta a inativa ao soltar**.
   Falha antiga: ficava presa em ACTIVE.
3. Repita com os botões de face e com os analógicos (soltar no centro deve zerar o eixo).
4. Segure um botão e solte com o jogo em foco; depois troque de aba, volte e repita.
5. Repita em um segundo navegador, se tiver (Chrome e Firefox se comportam diferente com `timestamp`).

## 4. Idioma no editor Windows (opcional, não relacionado ao Web)

Preferences > System > **International Fonts**: escolha **Language**, ligue **Interface** e confira o texto,
os acentos (pt, es) e o cirílico (ru).

## Registrar

Se algo falhar, anote navegador, controle, qual entrada e a mensagem do console. Se tudo passar, o item
"falta reconferir o gamepad físico" de `docs/roadmap.md` pode ser removido.
