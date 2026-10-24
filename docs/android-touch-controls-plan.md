# Controles de toque na tela (A1)

Caminho aprovado em 2026-09-24; T0–T6 feitas. Histórico em [changelog-arquivo.md](changelog-arquivo.md)
(entradas de 2026-09-24) e testes em aparelho em [android-manual-tests.md](android-manual-tests.md).
Pendências gerais em [roadmap.md](roadmap.md) (seção "Android / iOS").

## Como funciona

Overlay HTML (Pointer Events por `pointerId`) no template de `tools/web/package-web.py`, compartilhado pelo Web e
pelo APK. A página escreve `Module.rangePad = {axes, buttons, keys, look, t}` e a engine lê por `EM_JS` a cada
quadro (molde de `KX_PythonMotion.cpp`). Estende o Range Input System; não é sistema paralelo. SDL virtual
joystick não existe na porta Emscripten.

Alvos de cada controle:
- **`pad:`** (`pad:leftStick`, `pad:a`): vira o gamepad 0, somado ao físico (`DEV_JoystickEvents.cpp`). Chega em
  `logic.joysticks[0]`, sensor Joystick e Input System.
- **`key:`** (`key:W`, `key:SPACE`, botões do mouse): teclas com origem separada do teclado/mouse físico
  (`DEV_InputDevice.cpp`, lido em `LA_Launcher::EngineNextFrame`).
- **`look`**: o stick move o cursor virtual em `GHOST_SystemSDL.cpp` (só com mouse-look).
- **`axis`**: pedais nos gatilhos (layout `race`).

Layouts: nenhum, `stick`, `dpad`, `twin`, `wasd`, `arrows`, `fps`, `race`. O layout fica na config do export Web
(`range_web.touch_layout`/`touch_stick`, no `.range`) e o APK herda. Aviso WEB-INPUT-001 (`range_web/touch.py`)
para sensor/ação que o layout não aperta; leitura de `logic.keyboard` em Python não é detectada.
Botão **Controles: ligados/desligados** para menus (2026-10-14). Aparece só em `pointer: coarse` ou `?touch=1`.

Exemplo para iniciante: template de componente `03_jogador_celular.py` (Text Editor > Templates > Components).

## Pendências

- **T6, corrida (2026-10-09):** layout `race` (stick, setas ou inclinar, trocados por botão `switch`) só conferido
  no Edge headless. Falta o celular e o jogo real (RolimaRacer).
- **Alternância para menus (2026-10-14):** falta validar em celular real (menu, retorno à partida, rotação),
  incluindo iframe do itch.io.
- Fora do escopo por ora: `logic.touches` (dedos crus via `SDL_FINGER*` no GHOST), vibração, editor visual de
  layout, teclado do sistema para texto.

## Verificação

- Navegador: `tools/web/verify-touch.cjs` (multitoque pelo CDP, alvos pad/tecla/look, cancelamento, página
  escondida, alternância) e `tools/web/verify-pad.cjs`.
- Regressões: arrastar para olhar fora dos controles; gamepad físico no PC; `test_android.py` e
  `engine_i18n.py`.

**Roteiro no celular** (cena `pad`):
1. Gerar: `build/bin/AnastacioEngine.exe -b --python tools/tests/web_profile/make_pad_project.py`.
2. Abrir `projects-teste/pad/pad.range`; em Android (Range), applicationId de teste (ex.:
   `com.anastaciogames.pad`), gerar APK debug e "Instalar no celular". Log: `adb logcat -s RangeWeb`, app aberto com
   `--es query "debug=1"`.
3. Layout padrão (stick + 2 botões): mover + agir (`axes=[...]` com `buttons=[0]`); A e B juntos
   (`buttons=[0, 1]`); arrastar o dedo do stick para o outro lado (continua andando, B não aperta); puxar a barra
   de notificações com o dedo no stick; Home com stick e botão; toque fora dos controles não aperta botão.
4. Layout "Stick como WASD + Espaço" (ou `--es query "touchlayout=wasd"`): `[pad] key W down/up` e
   `[pad] map Pular down`.
5. Jogo real com o layout do jogo (andar + olhar ao mesmo tempo).
