# Mapa de código — editor de Logic Bricks (`logic_window.c`)

Índice do desenho do editor de Logic Bricks: sensores, controladores, atuadores, grupos e o realce ao vivo.
Não descreve arquitetura; serve para achar a função certa sem ler 3.800 linhas.

**Linhas conferidas em 2026-11-08 (`HEAD` `fa834071`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Arquivos vizinhos:

- `source/source/blender/makesdna/DNA_sensor_types.h`, `DNA_controller_types.h`, `DNA_actuator_types.h`:
  structs e enums de cada brick.
- `source/source/blender/makesrna/intern/rna_sensor.c`, `rna_controller.c`, `rna_actuator.c`: propriedades
  que os `draw_*` mostram com `uiItemR`.
- `source/source/blender/blenkernel/intern/sca.c`: criar, copiar e liberar bricks.

## Receitas

**Brick novo (ou campo novo num brick).** 1) Struct/enum no `DNA_*_types.h`. 2) RNA em `rna_sensor.c` ou
`rna_actuator.c`. 3) `sca.c` (init e cópia). 4) Aqui: `draw_sensor_<nome>`/`draw_actuator_<nome>` e o `case`
em `draw_brick_sensor`/`draw_brick_actuator`; nome no menu em `sensor_name`/`actuator_name`. 5) Conversão
para a engine em `Converter/BL_ConvertSensors.cpp` ou `BL_ConvertActuators.cpp`.

**Layout das colunas e grupos.** `draw_*_column` desenha cada coluna; grupos em `logic_group_move`,
`draw_group_*` e `do_*_group_toggle`.

**Realce ao vivo (Highlight Active).** `logic_debug_*`, chamado no fim de `logic_buttons`.

## `source/source/blender/editors/space_logic/logic_window.c` (3.867 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Eventos e nomes | `do_logic_buts` 104, `sensor_name` 340, `controller_name` 383, `actuator_name` 406, `set_sca_ob` 463, `get_selected_and_linked_obs` 480, `get_armature_bone_constraint` 650 |
| Menus de adicionar e estados | `do_sensor_menu` 665, `sensor_menu` 694, `do_controller_menu` 714, `controller_menu` 743, `do_actuator_menu` 763, `actuator_menu` 792, `controller_state_mask_menu` 822, `is_sensor_linked` 862 |
| Sensores | `draw_sensor_header` 904, `draw_sensor_internal_header` 956, `draw_sensor_animation_event` 988, `draw_sensor_collision` 1110, `draw_sensor_joystick` 1154, `draw_sensor_keyboard` 1193, `draw_sensor_mouse` 1227, `draw_sensor_property` 1274, `draw_sensor_ray` 1360, `draw_sensor_movement` 1395, `draw_sensor_vr_head` 1404, `draw_brick_sensor` 1432 (switch) |
| Controladores | `draw_controller_header` 1504, `draw_controller_expression` 1552, `draw_controller_python` 1557, `draw_controller_state` 1573, `draw_brick_controller` 1578 (switch) |
| Atuadores (A–F) | `draw_actuator_header` 1614, `draw_actuator_action` 1665, `draw_actuator_armature` 1713, `draw_actuator_camera` 1785, `draw_actuator_constraint` 1801, `draw_actuator_edit_object` 1901 |
| 2D Filter | `filter2d_choice_menu` 2027, `filter2d_choice_draw` 2046, `draw_filter2d_uniforms` 2076, `draw_actuator_filter_2d` 2154 |
| Atuadores (G–Z) | `draw_actuator_game` 2187, `draw_actuator_message` 2201, `draw_actuator_motion` 2224, `draw_actuator_parent` 2371, `draw_actuator_property` 2388, `draw_actuator_random` 2502, `draw_actuator_scene` 2567, `draw_actuator_sound` 2593, `draw_actuator_state` 2647, `draw_actuator_vibration` 2660, `draw_actuator_wait` 2686, `draw_actuator_video` 2695, `draw_actuator_visibility` 2732, `draw_actuator_steering` 2742, `draw_actuator_mouse` 2788, `draw_brick_actuator` 2850 (switch) |
| Brick completo (caixa e links) | `draw_controller_brick` 2931, `draw_sensor_brick` 3007, `draw_actuator_brick` 3065, `sensor_is_shown` 3108 |
| Grupos | `do_sensor_group_toggle` 3156, `logic_group_move` 3181, `draw_group_move_buttons` 3256, `draw_group_header_button` 3271 |
| Colunas | `draw_sensor_column` 3287, `draw_controller_column` 3343, `draw_actuator_column` 3407 |
| Realce ao vivo | `logic_debug_link_owner` 3476, `logic_debug_draw_wire` 3490, `logic_debug_draw` 3531 |
| Entrada | **`logic_buttons`** 3628 (monta o bloco inteiro) |
