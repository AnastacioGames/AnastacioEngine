# Notas: Logic Bricks → Python, fase 4 (branch `logic/convert-f4`)

Sessão automática (2026-10-04), sem perguntas ao usuário; dúvidas e bloqueios ficam aqui.

## Base da branch

- A `main` local do container tinha divergido do remoto (50 à frente, 76 atrás; `git pull` recusou por
  histórico divergente). A branch foi criada a partir de `origin/main` (84d3e83), que é a main de fato.

## Ambiente de build (Linux headless, preset `linux-editor`)

- `tools/linux/quickstart-editor.sh` não roda como está nesta nuvem: usa `sudo` (somos root, sem sudo) e baixa o
  Python 3.11.9 de `python.org`, que o proxy bloqueia. Contornos usados:
  - `apt-get install` direto da lista do script, mais **`libopenexr-dev libimath-dev libopenjp2-7-dev libtiff-dev
    libwebp-dev libpugixml-dev libjemalloc-dev`** (o script não os lista e o CMake para sem OpenEXR).
  - Python do sistema (3.11.15, com headers e `libpython3.11.so`): `-DPYTHON_ROOT_DIR=/usr`.
  - `-DWITH_CYCLES=OFF -DWITH_IMAGE_OPENEXR=OFF`: Cycles quer OpenEXR 2/ilmbase; o Ubuntu 24.04 só tem OpenEXR 3 +
    Imath. Cycles não faz parte da validação.
- Comando: `cmake --preset linux-editor -S source -DPYTHON_ROOT_DIR=/usr -DWITH_CYCLES=OFF -DWITH_IMAGE_OPENEXR=OFF`
  e `cmake --build build-linux-editor --target RangeEngine RangeRuntime -j4`.

## Decisões de conversão

- **Ray por material com x-ray**: o `rayCast` do Python só filtra por propriedade, e a engine filtra por material
  *antes* do teste (enxerga através de quem não tem o material). Convertido com `_mat_mark`: marca, numa
  propriedade privada (`__lcmat_<material>`), os objetos da cena que usam o material, e o `rayCast` x-ray filtra
  por ela. Mesmo comportamento; custo: um laço por `scene.objects` a cada avaliação do sensor, e a propriedade
  privada aparece nos objetos. Vale também para o eixo VR Gaze.
- **Collision/Near/Radar de sensor ligado de outro objeto**: `_near`/`_radar` agora recebem o objeto dono;
  Collision usa `_take(objeto)` (callback próprio por objeto, registrado já no `start`, lista lida uma vez por
  frame). Os helpers que leem `self.object` (`_act_on`, `_anim_event`, `_moved`, `_gaze`, `_vr_head`) seguem como
  brick quando o sensor é de outro objeto. `_moved`/`_gaze`/`_vr_head` antes passavam sem aviso e liam o objeto
  errado: agora ficam como brick com o motivo registrado.
- **Actuators de outro objeto que usam helper do próprio componente** (Camera, Mouse Look, Constraint, Steering,
  Track To, Sound...): continuam como brick. Não estavam no escopo; precisariam do mesmo tratamento de `on()` por
  helper.
- **Sound em ping-pong**: `LOOPBIDIRECTIONAL` e `LOOPBIDIRECTIONALSTOP` via `aud.Sound.file(...).pingpong()`,
  loop infinito; pulso negativo termina a volta (`loop_count = 0`) ou corta (`stop()`), como o actuator.
- **Track To com pai**: porta de `vectomat` + interpolação por Euler (`Mat3ToEulOld`/`EulToMat3`) do
  `KX_TrackToActuator`, com a orientação local inicial do pai guardada no `start` (a engine guarda no
  carregamento). Fica como brick: **pai de vértice** (a engine ignora o pai e grava a orientação de mundo como
  local; não dá para reproduzir com a API de Python) e Track To por propriedade/objeto dinâmico (já era brick).
