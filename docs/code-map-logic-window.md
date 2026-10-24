# Mapa de código — editor de Logic Bricks (`logic_window.c`)

Índice do desenho do editor de Logic Bricks: sensores, controladores, atuadores, grupos e o realce ao vivo.
Não descreve arquitetura; serve para achar a função certa sem ler 3.800 linhas.

**Linhas conferidas em 2026-10-23 (`HEAD` `8eea9701`).** Os números envelhecem a cada edição: confirme com
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

## `source/source/blender/editors/space_logic/logic_window.c` (3.784 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Eventos e nomes | `do_logic_buts` 103, `sensor_name` 339, `controller_name` 380, `actuator_name` 403, `set_sca_ob` 458, `get_selected_and_linked_obs` 475, `get_armature_bone_constraint` 645 |
| Menus de adicionar e estados | `do_sensor_menu` 660, `sensor_menu` 689, `do_controller_menu` 709, `controller_menu` 738, `do_actuator_menu` 758, `actuator_menu` 787, `controller_state_mask_menu` 817, `is_sensor_linked` 857 |
| Sensores | `draw_sensor_header` 899, `draw_sensor_internal_header` 951, `draw_sensor_animation_event` 983, `draw_sensor_collision` 1105, `draw_sensor_joystick` 1149, `draw_sensor_keyboard` 1188, `draw_sensor_mouse` 1222, `draw_sensor_property` 1269, `draw_sensor_ray` 1355, `draw_sensor_movement` 1390, `draw_sensor_vr_head` 1399, `draw_brick_sensor` 1411 (switch) |
| Controladores | `draw_controller_header` 1480, `draw_controller_expression` 1528, `draw_controller_python` 1533, `draw_controller_state` 1549, `draw_brick_controller` 1554 (switch) |
| Atuadores (A–F) | `draw_actuator_header` 1590, `draw_actuator_action` 1641, `draw_actuator_armature` 1689, `draw_actuator_camera` 1761, `draw_actuator_constraint` 1777, `draw_actuator_edit_object` 1877 |
| 2D Filter | `filter2d_choice_menu` 2003, `filter2d_choice_draw` 2022, `draw_filter2d_uniforms` 2052, `draw_actuator_filter_2d` 2130 |
| Atuadores (G–Z) | `draw_actuator_game` 2163, `draw_actuator_message` 2177, `draw_actuator_motion` 2200, `draw_actuator_parent` 2344, `draw_actuator_property` 2361, `draw_actuator_random` 2475, `draw_actuator_scene` 2540, `draw_actuator_sound` 2566, `draw_actuator_state` 2603, `draw_actuator_vibration` 2616, `draw_actuator_wait` 2642, `draw_actuator_video` 2651, `draw_actuator_visibility` 2665, `draw_actuator_steering` 2675, `draw_actuator_mouse` 2721, `draw_brick_actuator` 2783 (switch) |
| Brick completo (caixa e links) | `draw_controller_brick` 2861, `draw_sensor_brick` 2937, `draw_actuator_brick` 2995, `sensor_is_shown` 3038 |
| Grupos | `do_sensor_group_toggle` 3086, `logic_group_move` 3111, `draw_group_move_buttons` 3186, `draw_group_header_button` 3201 |
| Colunas | `draw_sensor_column` 3217, `draw_controller_column` 3273, `draw_actuator_column` 3337 |
| Realce ao vivo | `logic_debug_link_owner` 3406, `logic_debug_draw_wire` 3420, `logic_debug_draw` 3461 |
| Entrada | **`logic_buttons`** 3547 (monta o bloco inteiro) |
