# Notas: Logic Bricks → Python, fase 6 (branch `logic/convert-f6`)

Sessão automática (2026-10-04). Escopo: fechar lacunas que ainda ficavam como brick (`Unsupported(...)` → `# TODO:`
no código gerado) e cobrir sensores/actuators ligados entre objetos. Seguiu o padrão da F5 (`own=` nos helpers,
estado por `Dono/Actuator`).

## Levantamento (o que ainda era brick no começo da F6)

- Já cobertos desde a F4/F5 (só faltava cena de teste): Ray material + x-ray / sem x-ray, Collision, Near e Radar
  de sensor de outro objeto, Track To de objeto com pai (só do próprio Driver), Sound loop/ping-pong (só no Driver).
- Brick por causa de `self.object`/estado do dono: Track To com pai e Sound em outro objeto; sensores Movement e
  Animation Event de outro objeto.
- `Unsupported` sem relação com entre-objetos: Delay em segundos, Sound 3D.

## O que mudou (`logic_to_python.py`)

- **Track To com pai em outro objeto:** `_track_parent(..., own=)`; o pai e a orientação local inicial ficam em
  `self._plm[nome_do_objeto]` (novo `_plm_init(obj)`, chamado no `start()` por dono). Track To sem pai já funcionava
  em outro objeto (só usa `ob`/`scene`).
- **Sound:** reescrito em helpers `_snd_play` / `_snd_stop` / `_snd_update` com `own=` e chave `Dono/Actuator`.
  Reproduz a flag `m_isplaying` de `KX_SoundActuator`: depois de um pulso negativo o próximo positivo **recomeça** o
  som mesmo que a volta anterior (LOOPEND, LOOPBIDIRECTIONAL, PLAYEND) ainda esteja tocando; antes o código gerado
  ignorava o positivo enquanto o handle tocava. Ping-pong = `Sound.pingpong()` + `loop_count = -1`.
- **Sound 3D** (antes brick): mesmos ajustes do actuator (`relative`, ganho min/max, distâncias, rolloff, cone) e
  posição/velocidade/orientação relativas à câmera ativa atualizadas todo frame por `_snd_update()` enquanto toca.
  Os valores 3D saem fixos no código (não viram args). Sound empacotado continua brick.
- **Delay em segundos** (`use_deltatime`): `_delay(..., seconds)` soma `logic.deltaTime()` na fase de atraso e
  frames na duração, igual a `SCA_DelaySensor::Evaluate` (o `GetEngineDeltaTime` é o mesmo de `logic.deltaTime()`).
- **Movement e Animation Event de outro objeto:** `_moved`/`_anim_event` aceitam `own=`.
- `_OWN_CALLS` agora inclui `track_parent`, `snd_play`, `snd_stop`.

## Validado aqui (Linux, sem engine)

Não compilei a engine (sem build nesta máquina; o build completo leva horas). Validado:

- `python3 tools/test_logic_convert_f6_codegen.py` (bpy simulado): converte um Driver com Ray x-ray, Ray sem x-ray,
  Collision, Near, Radar, Movement, Delay em segundos (sensores em outros objetos) e Track To com pai, Sound
  Loop/PingPong/3D (actuators em outro objeto): 0 TODO, código compila, `o_<dono>`/`own=` corretos, chaves
  `Dono/Actuator`, `_plm_init` por dono. Executa o fluxo do Sound com um módulo `aud` falso (não recomeça tocando,
  recomeça após pulso negativo, stop/end, ping-pong, 3D). Resultado: OK.
- `python3 tools/test_logic_convert_f5_codegen.py` (regressão): OK.
- **Não validado:** matemática em runtime, CHECK idêntico entre bricks e componente, nomes dos atributos do
  `aud.Handle` 3D (`relative`, `volume_minimum`, `cone_angle_*`, `orientation` como `(w, x, y, z)`), `Sound.pingpong`
  e áudio de verdade.

## O que testar localmente no Windows

1. Gerar as cenas (`tools/create_logic_convert_scene_f6.py`; cria também `f6_tone.wav` ao lado do `.range`):
   ```
   RangeEngine -b --python tools/create_logic_convert_scene_f6.py -- f6_bricks.range
   RangeEngine -b --python tools/create_logic_convert_scene_f6.py -- f6_comp.range convert
   RangeEngine -b --python tools/create_logic_convert_scene_f6.py -- f6_mod.range convert:MODULE
   RangeEngine -b --python tools/create_logic_convert_scene_f6.py -- f6_scr.range convert:SCRIPT
   ```
2. Rodar cada uma com `RangeRuntime` (a cena termina sozinha aos 120 frames).
3. **Esperado:** a linha `CHECK rayx=1 rayplain=1 col=1 near=1 radar=1 moved=1 delayed=1 turret=...` idêntica nos 4
   modos e `LEFT_AS_BRICK 0 []` nos 3 modos com `convert`. O CHECK só lê valores estáveis (propriedades que
   ficam em 1 e a orientação do Turret parado), então não deve haver diferença de 1 frame entre Checker/Driver.
   Se `radar`/`near` vierem 0 nos dois lados, a cena está mal posicionada (compare só bricks × componente).
4. Regressão: cenas F5 e `create_logic_convert_scene.py` (CHECK idêntico, `LEFT_AS_BRICK 0`).
5. À mão, com áudio: Speaker com Loop/PingPong/Pos3D (volume 0 na cena; suba o volume): confirmar que o som
   recomeça após o controller desligar e ligar de novo, que o ping-pong vai e volta e que o 3D acompanha a câmera.
   Se o `aud` reclamar de atributo 3D, o erro aparece no log (`AttributeError` em `_snd_play`).

## Continua como brick (motivo)

- Track To com pai de vértice (a engine grava orientação de mundo como local; não há conta equivalente em Python).
- Sensores de outro objeto: Actuator (estado `_act_on` só do próprio dono), Ray Gaze e VR Head (usam câmera/HMD do
  objeto do componente).
- Mouse Over com x-ray/material; Property sensor com runtime API (`GetRuntimeProperty` da engine); Sound empacotado;
  controller Python (já é código); os motivos de Steering da F5 (obstáculos, normal up, path sem navmesh).
- Actuators de outro objeto que chamam helpers que não são da lista `_OWN_CALLS` (ex.: VR walk/teleport).

## Validação local (Windows, MSVC, 2026-10-04)

- Geração: `LEFT_AS_BRICK 0 []` em Component, Module e Script.
- Runtime: `CHECK rayx=1 rayplain=1 col=1 near=1 radar=1 moved=1 delayed=1 turret=0.71,0.68,-0.19,...` idêntico nos 4
  modos (sem a diferença de 1 frame da F5, como previsto). O `RangeRuntime` não escreve no console quando o stdout é
  redirecionado; o resultado sai em `Scene_check_f6.txt` ao lado do `.range`.
- Corrigido na cena de teste: `material("Red")` criava um material novo a cada chamada, então o Glass2 ficava com
  `Red.001` e o Ray sem x-ray dava `rayplain=0` também com bricks. O helper agora reaproveita pelo nome.
- Regressão: F5 igual à validação anterior (slider/looker idênticos, `cam`/`chaser` com 1 frame de leitura); cena
  antiga com CHECK idêntico, só `cam y` -0,04 × -0,03 (já conhecido). `LEFT_AS_BRICK 0` em todas.
- Não testado: o áudio à mão (passo 5).
