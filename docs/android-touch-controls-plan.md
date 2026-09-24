# Controles de toque na tela (A1)

Levantamento e caminho aprovado em 2026-09-24. Detalha a seção 4 de [android-export-plan.md](android-export-plan.md).

## Contexto

O A1 completo é o próximo passo do plano Android. Ele cobre direcional e botões na tela, multitoque e, mais adiante, analógico.

Hoje o toque só funciona porque o SDL converte **um** dedo em mouse:
- o arrastar vira olhar em volta pelo cursor virtual;
- o tap vira clique.

O que falta:
- `GHOST_SystemSDL.cpp` não trata `SDL_FINGER*`, então o segundo dedo se perde.
- A página não tem overlay nem Pointer Events.
- O `MainActivity.kt` não tem ponte JS nem código de input.

O usuário pediu:
- um levantamento de como as outras engines fazem;
- o que já vem de graça;
- se deve implementar na engine;
- como aproveitar os dois lados (página Web e engine);
- se vale uma "API nova de input".

## Como as outras engines fazem

| Engine | Onde fica o controle | Para onde manda o input |
|---|---|---|
| Unity (Input System) | Componentes `OnScreenStick` e `OnScreenButton` na UI | Um **dispositivo virtual**: o stick escreve em `<Gamepad>/leftStick`, então o jogo lê igual a um gamepad físico |
| Unreal | "Touch Interface" padrão (`DefaultVirtualJoysticks`, com 2 sticks) ou `LeftVirtualJoystickOnly` | O eixo do gamepad. Liga e desliga nas Project Settings |
| Godot 4.7 | Nó nativo `VirtualJoystick` (fixo, dinâmico ou que segue o dedo) e `TouchScreenButton` | **Ações nomeadas** do InputMap, as mesmas do teclado e do gamepad |
| Defold / GameMaker / Construct | Nada pronto no núcleo; usam assets da comunidade | O script lê o multitoque |
| Web puro | nipplejs (MIT), um overlay HTML | Callbacks em JS |

O padrão das engines maduras é sempre o mesmo:
- O controle na tela é só visual e captura de toque.
- Ele **alimenta o mesmo sistema de input** do teclado e do gamepad, como dispositivo virtual ou como ação.
- O jogo não precisa saber que é toque.
- A engine traz layouts prontos para usar: o "brinde".

## O que já temos de graça

- **No navegador e no WebView:**
  - Pointer Events com `pointerId`, que dão multitoque real;
  - `touch-action: none`;
  - `visibilitychange` e `blur`, para soltar os toques;
  - CSS para desenhar os controles.
- **Na engine:**
  - O **Range Input System** (`KX_InputSystem.cpp`, `KX_InputTable.cpp`). Os mapas ficam em `KeyMapping/*.json` e têm tipos de controle (valor, vetor 1D, 2D e 3D), bindings de `KEYBOARD`, `MOUSE` e `JOYSTICK` e processadores como deadzone. É o equivalente ao InputMap do Godot e às Input Actions do Unity.
  - O gamepad (`DEV_Joystick`), que já chega em `logic.joysticks`, no sensor Joystick e nos bindings `JOYSTICK` do Input System.
  - A ponte **JS → C++ por polling**, já usada no sensor de movimento: a página escreve em `Module.rangeMotion` e a engine lê por `EM_JS` em `KX_PythonMotion.cpp:34-77`. É o molde exato para o pad virtual.
- **O que não vem de graça:**
  - O joystick virtual do SDL (`SDL_JoystickAttachVirtualEx`). `SDL_config_emscripten.h` não define `SDL_JOYSTICK_VIRTUAL` (conferido no emsdk local). Usar esse caminho exigiria mais um patch na porta SDL2, por isso não é o recomendado.
  - Injetar um gamepad falso em `navigator.getGamepads()`. O plano já proíbe isso.

## Resposta: "API nova de input?"

Sim, mas **como extensão do Range Input System, não como um sistema paralelo**. O usuário confirmou esta escolha: estender mantém a compatibilidade com o que já existe. Quase tudo que uma "API nova" teria já existe lá: ações, eixos, deadzone e vários periféricos.

O que falta é um **periférico novo**: o pad virtual da tela. Assim, um mapa como `"Mover": VECTOR2D` com bindings de teclado (WASD), gamepad (stick esquerdo) e toque passa a funcionar sozinho no PC, no gamepad e no celular.

A API de toque cru em Python (`logic.touches`, com cada dedo e sua posição) é **outra peça**. Ela serve para gestos, pinça e jogos de tocar em objetos. Fica para depois, e o caminho dela é tratar `SDL_FINGER*` no GHOST.

## Caminho recomendado

Cada coisa no lado em que ela é mais barata e mais sólida:

```
Página (JS/CSS) ──────────────────────────────────────┐   Engine (C++)
 overlay: stick, d-pad, botões                        │
 Pointer Events por pointerId (multitoque)            │
 solta tudo em blur/visibilitychange/pointercancel     │
 escreve Module.rangePad = {axes[6], buttons, keys, t} ├─> EM_JS poll a cada frame (molde do rangeMotion)
                                                      │    ├─ alvo "pad": vira o gamepad 0 (junta com o físico)
                                                      │    │    → logic.joysticks[0], sensor Joystick, Input System
                                                      │    └─ alvo "tecla": teclas seguradas pelo toque,
                                                      │         com origem separada do teclado físico
Android (Kotlin): nada para o overlay; só pausa → soltar entradas (A2)
```

Por que o overlay fica em HTML, e não desenhado pela engine nem nativo em Kotlin:
- **Multitoque sem mexer no GHOST.** O Pointer Events já entrega cada dedo.
- **Sem cliques falsos.** Toques em cima do overlay não chegam ao canvas, então o SDL não gera clique. Toques fora dos controles continuam indo ao canvas, e o arrastar para olhar do First Person segue funcionando.
- **Um código só serve para o APK e para o Chrome do celular.** Também dá para testar no PC com `?touch=1`, como o `-faketouches` do Unreal.
- **Não depende do renderizador** e não custa desenho na GPU da cena.

Cada controle tem um **alvo**, como o "control path" do Unity:
- **`pad:`**, por exemplo `pad:leftStick` ou `pad:a`. Analógico de verdade, pelo mesmo caminho do gamepad físico. Jogos que leem gamepad ou Input System funcionam sem mudar nada.
- **`key:`**, por exemplo `key:W` ou `key:SPACE`. É a compatibilidade com jogos que leem teclado, como o First Person com WASD. No modo tecla, o stick vira 4 teclas digitais por limiar. A origem fica separada: soltar o toque não solta a tecla que o teclado físico ainda segura. Esse é o risco apontado no plano, linha 67.

Os layouts prontos são o "brinde":
- nenhum;
- stick + 2 botões;
- d-pad + 4 botões;
- dois sticks.

Os layouts ficam num JSON do projeto e podem ser escolhidos no painel do editor. Posição, tamanho, deadzone e o modo do stick (fixo ou dinâmico) são ajustáveis.

## Etapas

1. **T0, prova da ponte (curta), feita em 2026-09-24:** `verify-pad.cjs` 7/7 no Edge headless; com controle USB real, físico e virtual juntos (maior eixo vence, botões somados) e o físico segue sozinho ao desligar o pad (ver changelog). Mapa `JOYSTICK` do Input System conferido na T3. Falta o celular.
   - `Module.rangePad` com eixos e botões fixos no JS.
   - Leitura por `EM_JS` em `DEV_Joystick` (`DEV_JoystickEvents.cpp`: fonte virtual no `SyncLiveState`, junta no índice 0; se não houver gamepad físico, cria a instância virtual).
   - Critério: no navegador do PC, o valor aparece em `logic.joysticks[0]` e num mapa `JOYSTICK` do Input System.
2. **T1, overlay, feita em 2026-09-24:** `verify-touch.cjs` 10/10 no Edge headless com toque emulado (dois dedos
   pelo CDP); d-pad na diagonal conferido. Layouts `stick`, `dpad` e `twin` já no template, escolhidos por
   `package-web.py --touch-layout/--touch-stick` (a T3 liga isso ao painel). Falta o celular.
   - Módulo JS no template de `tools/web/package-web.py`, com stick fixo e dinâmico, d-pad e botões.
   - Pointer capture, `touch-action: none` e respeito ao entalhe da tela.
   - Soltar tudo ao perder o foco.
   - Aparece só em `pointer: coarse` ou com `?touch=1`.
3. **T2, alvo tecla, feita em 2026-09-24:** `verify-touch.cjs` 16/16 (gamepad e teclas, com teclado físico emulado
   pelo CDP). A página manda códigos de `bge.events` em `Module.rangePad.keys`; `DEV_InputDevice` guarda teclado físico
   e toque em separado e é lido por `LA_Launcher::EngineNextFrame` logo depois dos eventos do sistema (o
   `DEV_EventConsumer` só recebe eventos, então o poll ficou no laço do quadro). Layouts `wasd` e `arrows`.
   Aceita pelo usuário no Edge do PC (mouse simulando o dedo, junto com o teclado físico).
   - Teclas seguradas pelo toque lidas no mesmo poll.
   - Em `DEV_EventConsumer.cpp`, o estado do teclado físico e o do toque ficam separados, e a tecla só muda quando o estado combinado muda.
   - Remover o `printf("[web-input] ...")` que sobrou na linha 67.
4. **T3, configuração e editor, feita em 2026-09-24.** Decisão: o layout fica na config do export Web (propriedade
   da cena `range_web.touch_layout`/`touch_stick`, no `.range`), não no `android-export.json`; o APK embute o pacote
   Web e herda o layout (o painel Android mostra o mesmo campo). O pacote registra o layout em
   `manifest.json` (`touch_controls`). Aviso WEB-INPUT-001 (`range_web/touch.py`) para sensor Keyboard/Joystick e ação
   do Input System que o layout não aperta; sem controle na tela, um só aviso informativo. Os mapas
   `KeyMapping/*.json` não iam no pacote Web (o Input System ficava vazio no navegador); agora vão, e
   `verify-touch.cjs` confere uma ação com binding JOYSTICK (botão A do toque) e KEYBOARD (espaço do `wasd`), 19/19.
   Leitura de `logic.keyboard` em Python não é detectada pelo aviso.
   - Seção `touchControls` na config do export Web, que o Android herda. Hoje o plano diz `android-export.json`; o overlay serve aos dois, então a decisão será registrada no plano.
   - Seletor de layout no painel.
   - Aviso de ação sem mapeamento móvel (plano, linha 130).
   - Traduções pt/es/ru.
5. **T4, testes e documentação: parte automática feita em 2026-09-24; falta o celular.** Mudanças do plano
   original: a cena de teste é a do pad (`tools/tests/web_profile/make_pad_project.py`, `projects-teste/pad`), que já
   imprime eixos, botões, teclas e a ação do Input System (`[pad] ...`, que no APK sai no logcat `RangeWeb`), em
   vez de um `create_web_touch_scene.py` repetido; o multitoque fica em `verify-touch.cjs` (já usa dois dedos pelo
   CDP), não em um modo novo do `verify-capabilities.cjs`. `verify-touch.cjs` passou a conferir também a checklist
   abaixo no navegador: dois botões juntos (A+B, engine vê `buttons=[0, 1]`), dedo do stick arrastado até em cima
   do botão A (segue no stick, A não aperta, soltar zera), `touchcancel` com stick e botão apertados, e página
   escondida (`visibilitychange`, como na troca de app) com o stick apertado. 25/25.

   **Roteiro no celular (pendente):**
   1. Gerar a cena: `build/bin/RangeEngine.exe -b --python tools/tests/web_profile/make_pad_project.py`.
   2. Abrir `projects-teste/pad/pad.range` no editor. Em Android (Range), usar um applicationId de teste (ex.:
      `com.anastaciogames.pad`), gerar o APK debug e instalar com "Instalar no celular". Log:
      `adb logcat -s RangeWeb`, com o app aberto com `?debug=1` (`--es query "debug=1"`).
   3. Com o layout padrão (stick + 2 botões), conferir:
      - mover + agir: segurar o stick e apertar A; o cubo anda e pula, e o log mostra `axes=[...]` com `buttons=[0]`;
      - dois botões juntos: A e B, log `buttons=[0, 1]`;
      - arrastar para fora: levar o dedo do stick até o outro lado da tela; o cubo continua andando, B não é
        apertado, e ao soltar para;
      - toque cancelado: puxar a barra de notificações com o dedo no stick; ao voltar, o cubo está parado;
      - troca de app: Home com o dedo no stick e no botão; ao voltar, nada fica preso;
      - toque fora dos controles não aperta botão.
   4. Trocar Controle na tela para "Stick como WASD + Espaço", gerar de novo e conferir `[pad] key W down/up` e
      `[pad] map Pular down` pelo botão.
   5. Jogo real: First Person com o layout WASD (andar + olhar arrastando fora dos controles ao mesmo tempo).

Teclado: não desenhar teclado QWERTY na tela. Texto (nome, chat) usa o teclado do sistema Android, que vem de graça,
quando a engine pedir "abrir teclado"; entra só se algum jogo precisar.

Depois, fora deste escopo:
- `logic.touches` (dedos crus via `SDL_FINGER*`);
- vibração;
- editor visual de layout arrastando os controles.

## Arquivos principais

- `tools/web/package-web.py`: template HTML (overlay, `Module.rangePad`).
- `source/source/gameengine/Device/DEV_Joystick*.{h,cpp}`: fonte virtual no índice 0.
- `source/source/gameengine/Device/DEV_EventConsumer.cpp`: teclas vindas do toque, com origem separada.
- Referência a reusar: `source/source/gameengine/Ketsji/KX_PythonMotion.cpp` (padrão `EM_JS` + dado velho > 1 s).
- `source/release/scripts/modules/range_web/` (painel e config), `translations_android.py`.
- `tools/web/verify-capabilities.cjs`, `docs/android-export-plan.md`.

## Verificação

- **Build do runtime Web:** stick e botão com `?touch=1` no Chrome do PC, e dois toques simultâneos pelo CDP no `verify-capabilities.cjs`.
- **APK debug no Find X3 Pro** (versionCode maior que o instalado), com dois jogos:
  - First Person em modo tecla (WASD + pulo);
  - a cena de teste em modo pad, com valores no logcat.
- **Critérios do plano:** a checklist da linha 71, executada no aparelho.
- **Regressões:**
  - arrastar para olhar fora dos controles continua igual;
  - o gamepad físico no PC continua aceito;
  - `test_android.py` e `engine_i18n.py` passam sem falhas.
