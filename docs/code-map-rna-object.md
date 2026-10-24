# Mapa de código — RNA do objeto (`rna_object.c`, `rna_object_game.c`)

Índice de `rna_object.c` e `rna_object_game.c`: propriedades Python e UI do Object, incluindo as da engine
(física de jogo, destruição, explosivo, deformação, partículas GPU, reverb, raio, rede, LOD). Não descreve
arquitetura.

**Linhas conferidas em 2026-10-23 (`HEAD` `7a93da6c`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Cada arquivo tem duas metades: callbacks `rna_*` (get, set, update) dentro de `#ifdef RNA_RUNTIME` e definições
`rna_def_*`, que declaram as propriedades. Uma propriedade nova costuma mexer nas duas: o `RNA_def_property` na
`rna_def_` do domínio e, se precisar, um callback perto dos irmãos.

**Como o split funciona.** O makesrna compila cada `rna_*.c` duas vezes (gerador, sem `RNA_RUNTIME`; depois
incluído no `*_gen.c`, com `RNA_RUNTIME`). O código gerado de cada struct vai para o `_gen.c` do item de
`PROCESS_ITEMS` (em `makesrna.c`) que a definiu, então os callbacks de um struct precisam morar no mesmo arquivo
da sua `rna_def_`. Por isso `rna_object_game.c` é um item próprio (`RNA_def_object_game`, logo depois de
`RNA_def_object`), listado também em `DEFSRC` do `CMakeLists.txt`. Funções usadas pelos dois arquivos
(`rna_reverb_area_apply_preset`, `rna_reverb_area_sync_empty_draw`, `rna_Object_lightning_preview_update`) são
não-static e declaradas em `rna_internal.h`.

## Receitas

**Propriedade nova de jogo no objeto.** 1) Campo em `DNA_object_types.h`, com default no `do_versions` se
zero não servir (arquivos da Range original pulam nosso versioning). 2) `RNA_def_property` em
`rna_def_object_game_settings` (`rna_object.c`) ou na `rna_def_object_<domínio>` (`rna_object_game.c`). 3) UI em
`source/release/scripts/startup/bl_ui/properties_game*.py`. 4) O Converter lê o campo.

**Toggle que liga outro sistema (ex.: Explosive cria Destruction).** Ver os `*_set` de `use_*` no topo de
`rna_object.c` (`rna_GameObjectSettings_use_explosive_set` e vizinhos); os `*_set` internos de cada sistema ficam
em `rna_object_game.c`.

## `source/source/blender/makesrna/intern/rna_object.c` (4.048 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Toggles de jogo (veículo, destruição, explosivo, deformação) | `rna_GameObjectSettings_is_vehicle_set` 223, `rna_GameObjectSettings_use_destruction_set` 247, `rna_GameObjectSettings_use_explosive_set` 267, `rna_GameObjectSettings_use_deform_set` 289 |
| Partículas GPU, reverb e raio (liga/desliga) | `rna_Object_use_gpu_particles_update` 327, `rna_Object_use_reverb_area_update` 365, `rna_Object_use_lightning_update` 389 |
| Matrizes, camadas e Base | `rna_Object_matrix_local_get` 423, `rna_Object_matrix_basis_get` 449, `rna_Object_layer_update` 541, `rna_Base_collection_get` 565, `rna_Object_layer_set` 1390, `rna_Base_layer_set` 1400 |
| Data, parent e dupli | `rna_Object_data_set` 606, `rna_Object_data_typef` 656, `rna_Object_parent_set` 677, `rna_Object_parent_type_itemf` 694, `rna_Object_collision_bounds_itemf` 735, `rna_Object_dup_group_set` 772 |
| Vertex groups, UV e cor | `rna_VertexGroup_name_set` 791, `rna_Object_active_vertex_group_index_set` 818, `rna_object_uvlayer_name_set` 871, `rna_Object_vgroup_new` 1799, `rna_VertexGroup_vertex_add` 1829 |
| Materiais e slots | `rna_Object_active_material_index_set` 923, `rna_Object_active_material_set` 954, `rna_MaterialSlot_material_set` 1128, `rna_MaterialSlot_link_set` 1146, `rna_MaterialSlot_path` 1198 |
| Transformação | `rna_Object_rotation_axis_angle_get` 1008, `rna_Object_rotation_mode_set` 1029, `rna_Object_dimensions_set` 1046, `rna_Object_location_editable` 1052 |
| Jogo: Load Mode, física, estados | `rna_Object_game_load_mode_get` 1208, `rna_Object_convert_object_set` 1224, `rna_GameObjectSettings_physics_type_get` 1240, `rna_GameObjectSettings_physics_type_set` 1281, `rna_GameObjectSettings_state_set` 1424, `rna_GameStateName_name_set` 1465, `rna_GameObjectSettings_col_group_set` 1556, `rna_GameObjectSettings_col_mask_set` 1585 |
| Grupos de bricks e componentes | `rna_object_brick_group_rename` 1471, `rna_LogicBrickGroups_new` 1503, `rna_GameObjectSettings_components_new` 1750, `rna_GameObjectSettings_components_remove` 1770 |
| Constraints, modifiers, shape keys | `rna_Object_active_shape_key_index_range` 1605, `rna_Object_constraints_new` 1688, `rna_Object_modifier_new` 1724, `rna_Object_boundbox_get` 1786 |
| Polls e LOD | `rna_Mesh_object_poll` 1886, `rna_Camera_object_poll` 1891, `rna_Object_lod_distance_update` 1913 |
| Definições: auxiliares | `rna_def_vertex_group` 1925, `rna_def_material_slot` 1989, `rna_def_game_object_activity_culling` 2030 |
| Definições: jogo | `rna_def_game_state_name` 2070, `rna_def_logic_brick_group` 2093, `rna_def_object_game_components` 2130, **`rna_def_object_game_settings`** 2158 (≈470 linhas: física, colisão, estados) |
| Definições: coleções e veículo | `rna_def_object_constraints` 2617, `rna_def_object_modifiers` 2665, `rna_def_object_vertex_groups` 2750, `rna_def_object_lodlevel` 2799, `rna_def_object_wheel_settings` 2875, `rna_def_object_gear_ratio` 2989, `rna_def_object_animation_event` 3007 |
| Definição principal | **`rna_def_object`** 3057 (≈870 linhas), `rna_def_dupli_object` 3925, `rna_def_object_base` 3983, `RNA_def_object` 4028 |

## `source/source/blender/makesrna/intern/rna_object_game.c` (1.562 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Rede, destruição, explosivo, deformação (callbacks) | `rna_RangeNetObjectSettings_replicate_set` 113, `rna_explosive_style_colors` 130, `rna_RangeExplosiveSettings_use_particle_explosion_set` 163, `rna_RangeDeformSettings_mode_set` 181, `rna_RangeDeformSettings_decal_set` 194, `rna_RangeDestructionSettings_fragments_set` 213, `rna_RangeExplosiveSettings_use_light_flash_set` 245, `rna_RangeExplosiveSettings_use_ground_mark_set` 263 |
| Partículas GPU, reverb e raio (callbacks) | `rna_GPUParticleSettings_particle_look_update` 283, `rna_reverb_area_apply_preset` 436, `rna_ReverbAreaSettings_preset_update` 467, `rna_Object_lightning_preview_update` 489, `rna_GPUParticles_use_size_curve_update` 497 |
| Definições: sistemas da engine | `rna_def_object_gpu_particles` 519 (≈300 linhas), `rna_def_object_lightning` 828, `rna_def_object_reverb_area` 942, `rna_def_object_network` 1033, `rna_def_object_destruction` 1092, `rna_def_object_explosive` 1158, `rna_def_object_deform` 1391, `RNA_def_object_game` 1551 |
