# Mapa de código — editor de Logic Bricks (`logic_window.c`)

Índice do desenho do editor de Logic Bricks: sensores, controladores, atuadores, grupos e o realce ao vivo.
Não descreve arquitetura; serve para achar a função certa sem ler 3.800 linhas.

**Linhas conferidas em 2026-10-26 (`HEAD` `1a63417a`).** Os números envelhecem a cada edição: confirme com
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

## `source/source/blender/editors/space_logic/logic_window.c` (3.798 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Eventos e nomes | `do_logic_buts` 104, `sensor_name` 340, `controller_name` 381, `actuator_name` 404, `set_sca_ob` 459, `get_selected_and_linked_obs` 476, `get_armature_bone_constraint` 646 |
| Menus de adicionar e estados | `do_sensor_menu` 661, `sensor_menu` 690, `do_controller_menu` 710, `controller_menu` 739, `do_actuator_menu` 759, `actuator_menu` 788, `controller_state_mask_menu` 818, `is_sensor_linked` 858 |
| Sensores | `draw_sensor_header` 900, `draw_sensor_internal_header` 952, `draw_sensor_animation_event` 984, `draw_sensor_collision` 1106, `draw_sensor_joystick` 1150, `draw_sensor_keyboard` 1189, `draw_sensor_mouse` 1223, `draw_sensor_property` 1270, `draw_sensor_ray` 1356, `draw_sensor_movement` 1391, `draw_sensor_vr_head` 1400, `draw_brick_sensor` 1412 (switch) |
| Controladores | `draw_controller_header` 1481, `draw_controller_expression` 1529, `draw_controller_python` 1534, `draw_controller_state` 1550, `draw_brick_controller` 1555 (switch) |
| Atuadores (A–F) | `draw_actuator_header` 1591, `draw_actuator_action` 1642, `draw_actuator_armature` 1690, `draw_actuator_camera` 1762, `draw_actuator_constraint` 1778, `draw_actuator_edit_object` 1878 |
| 2D Filter | `filter2d_choice_menu` 2004, `filter2d_choice_draw` 2023, `draw_filter2d_uniforms` 2053, `draw_actuator_filter_2d` 2131 |
| Atuadores (G–Z) | `draw_actuator_game` 2164, `draw_actuator_message` 2178, `draw_actuator_motion` 2201, `draw_actuator_parent` 2345, `draw_actuator_property` 2362, `draw_actuator_random` 2476, `draw_actuator_scene` 2541, `draw_actuator_sound` 2567, `draw_actuator_state` 2604, `draw_actuator_vibration` 2617, `draw_actuator_wait` 2643, `draw_actuator_video` 2652, `draw_actuator_visibility` 2666, `draw_actuator_steering` 2676, `draw_actuator_mouse` 2722, `draw_brick_actuator` 2784 (switch) |
| Brick completo (caixa e links) | `draw_controller_brick` 2862, `draw_sensor_brick` 2938, `draw_actuator_brick` 2996, `sensor_is_shown` 3039 |
| Grupos | `do_sensor_group_toggle` 3087, `logic_group_move` 3112, `draw_group_move_buttons` 3187, `draw_group_header_button` 3202 |
| Colunas | `draw_sensor_column` 3218, `draw_controller_column` 3274, `draw_actuator_column` 3338 |
| Realce ao vivo | `logic_debug_link_owner` 3407, `logic_debug_draw_wire` 3421, `logic_debug_draw` 3462 |
| Entrada | **`logic_buttons`** 3559 (monta o bloco inteiro) |
