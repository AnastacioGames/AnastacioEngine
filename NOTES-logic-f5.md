# Notas: Logic Bricks → Python, fase 5 (branch `logic/convert-f5`)

Sessão automática (2026-10-04). Escopo: actuators **Camera, Constraint, Steering e Mouse Look** que pertencem a
um objeto diferente do que tem o controller (bricks ligados entre objetos). Antes ficavam como brick
(`LEFT_AS_BRICK`) porque o código usa helpers do componente (`self._follow` etc.), que liam `self.object`.

## O que mudou

- `logic_to_python.py`: `_follow`, `_mouse_look`, `_cst_loc/_ori/_ray/_dist/_fh`, `_steer` e `_steer_face`
  ganharam o argumento opcional `own=` (objeto sobre o qual agem; padrão `self.object`). O gerador sempre emite
  `own=ob`; para actuator de outro objeto o `on()` troca `ob` pela variável local do dono
  (`o_<nome> = scene.objects.get('<nome>')`), então tudo age em `scene.objects[nome]`.
- Chaves de estado (`cst:`, `str:`, `mlk:`) usam o rótulo `Dono/Actuator` para actuators de outro objeto
  (iguais a antes para o próprio objeto), evitando colisão entre actuators de mesmo nome em donos diferentes.
- A checagem que rejeitava `self.` em actuator de outro dono agora aceita só essas chamadas (`_OWN_CALLS`) e o
  `self._ticks.pop`. Os demais helpers (Track To, Sound, VR…) continuam como brick nesse caso.
- Se o dono do actuator for removido, o actuator para (mesma regra dos outros links entre objetos).
- Valores (alvo, eixos, distância, damping, sensibilidade, limites) continuam vindo dos args do brick original.

## Validado aqui (Linux, sem engine)

Não compilei a engine nesta sessão (build `linux-editor` leva horas; ver `notes-logic-f4.md`). Validado:

- `python3 tools/test_logic_convert_f5_codegen.py`: bpy simulado, converte um Driver com os 4 actuators em outros
  objetos; confere 0 TODO, código compilável, `own=o_<dono>` nos 4, chaves por dono, e que o `update()` chama cada
  helper com o objeto dono; regressão do actuator no próprio objeto (chave simples). Resultado: OK.
- **Não validado:** a matemática dos helpers em runtime (só mudou a origem do objeto) e CHECK idêntico.

## O que testar localmente no Windows

1. Gerar as cenas (editor):
   ```
   RangeEngine -b --python tools/create_logic_convert_scene_f5.py -- f5_bricks.range
   RangeEngine -b --python tools/create_logic_convert_scene_f5.py -- f5_comp.range convert
   RangeEngine -b --python tools/create_logic_convert_scene_f5.py -- f5_mod.range convert:MODULE
   RangeEngine -b --python tools/create_logic_convert_scene_f5.py -- f5_scr.range convert:SCRIPT
   ```
   (compilar antes com a skill `build-anastacio`: o código Python do operador vem de `source/release/scripts`, mas
   use a instalação de `build/bin/`).
2. Rodar cada uma: `RangeRuntime f5_bricks.range`, `RangeRuntime f5_comp.range`, etc.
3. **Esperado:** a linha `CHECK cam=... camori=... slider=... chaser=... chaserori=... looker=...` idêntica nos 4
   modos, e na geração `LEFT_AS_BRICK 0 []` nos 3 modos com `convert`.
   Diferença conhecida de F4 (ordem de avaliação do Camera entre objetos) pode aparecer em Module/Script no `cam`;
   se aparecer, compare só com bricks e anote.
4. Regressão: `tools/create_logic_convert_scene.py` (cena antiga) continua com CHECK idêntico e `LEFT_AS_BRICK 0`.
5. Mouse Look no teste headless não recebe mouse: o `looker` fica parado nos dois lados; teste à mão no editor com
   mouse real (objeto Looker girando igual com bricks e com o componente de outro objeto).

## Limites

- Steering com simulação de obstáculos, normal up e path following sem navmesh continuam brick (como antes).
- `_steer`/Camera: o componente roda dentro do Driver; se o Driver for removido, os actuators param (bricks
  originais continuariam no dono). Mesmo comportamento dos demais links entre objetos.
