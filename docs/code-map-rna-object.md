# Mapa de código — RNA do objeto (`rna_object.c`, `rna_object_game.c`)

Índice de `rna_object.c` e `rna_object_game.c`: propriedades Python e UI do Object, incluindo as da engine
(física de jogo, destruição, explosivo, deformação, partículas GPU, reverb, raio, rede, LOD). Não descreve
arquitetura.

**Linhas conferidas em 2026-10-26 (`HEAD` `1a63417a`).** Os números envelhecem a cada edição: confirme com
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

## `source/source/blender/makesrna/intern/rna_object.c` (4.024 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Toggles de jogo (veículo, destruição, explosivo, deformação) | `rna_GameObjectSettings_is_vehicle_set` 223, `rna_GameObjectSettings_use_destruction_set` 247, `rna_GameObjectSettings_use_explosive_set` 267, `rna_GameObjectSettings_use_deform_set` 289 |
| Partículas GPU, reverb e raio (liga/desliga) | `rna_Object_use_gpu_particles_update` 327, `rna_Object_use_reverb_area_update` 341, `rna_Object_use_lightning_update` 365 |
| Matrizes, camadas e Base | `rna_Object_matrix_local_get` 399, `rna_Object_matrix_basis_get` 425, `rna_Object_layer_update` 517, `rna_Base_collection_get` 541, `rna_Object_layer_set` 1366, `rna_Base_layer_set` 1376 |
| Data, parent e dupli | `rna_Object_data_set` 582, `rna_Object_data_typef` 632, `rna_Object_parent_set` 653, `rna_Object_parent_type_itemf` 670, `rna_Object_collision_bounds_itemf` 711, `rna_Object_dup_group_set` 748 |
| Vertex groups, UV e cor | `rna_VertexGroup_name_set` 767, `rna_Object_active_vertex_group_index_set` 794, `rna_object_uvlayer_name_set` 847, `rna_Object_vgroup_new` 1775, `rna_VertexGroup_vertex_add` 1805 |
| Materiais e slots | `rna_Object_active_material_index_set` 899, `rna_Object_active_material_set` 930, `rna_MaterialSlot_material_set` 1104, `rna_MaterialSlot_link_set` 1122, `rna_MaterialSlot_path` 1174 |
| Transformação | `rna_Object_rotation_axis_angle_get` 984, `rna_Object_rotation_mode_set` 1005, `rna_Object_dimensions_set` 1022, `rna_Object_location_editable` 1028 |
| Jogo: Load Mode, física, estados | `rna_Object_game_load_mode_get` 1184, `rna_Object_convert_object_set` 1200, `rna_GameObjectSettings_physics_type_get` 1216, `rna_GameObjectSettings_physics_type_set` 1257, `rna_GameObjectSettings_state_set` 1400, `rna_GameStateName_name_set` 1441, `rna_GameObjectSettings_col_group_set` 1532, `rna_GameObjectSettings_col_mask_set` 1561 |
| Grupos de bricks e componentes | `rna_object_brick_group_rename` 1447, `rna_LogicBrickGroups_new` 1479, `rna_GameObjectSettings_components_new` 1726, `rna_GameObjectSettings_components_remove` 1746 |
| Constraints, modifiers, shape keys | `rna_Object_active_shape_key_index_range` 1581, `rna_Object_constraints_new` 1664, `rna_Object_modifier_new` 1700, `rna_Object_boundbox_get` 1762 |
| Polls e LOD | `rna_Mesh_object_poll` 1862, `rna_Camera_object_poll` 1867, `rna_Object_lod_distance_update` 1889 |
| Definições: auxiliares | `rna_def_vertex_group` 1901, `rna_def_material_slot` 1965, `rna_def_game_object_activity_culling` 2006 |
| Definições: jogo | `rna_def_game_state_name` 2046, `rna_def_logic_brick_group` 2069, `rna_def_object_game_components` 2106, **`rna_def_object_game_settings`** 2134 (≈470 linhas: física, colisão, estados) |
| Definições: coleções e veículo | `rna_def_object_constraints` 2593, `rna_def_object_modifiers` 2641, `rna_def_object_vertex_groups` 2726, `rna_def_object_lodlevel` 2775, `rna_def_object_wheel_settings` 2851, `rna_def_object_gear_ratio` 2965, `rna_def_object_animation_event` 2983 |
| Definição principal | **`rna_def_object`** 3033 (≈870 linhas), `rna_def_dupli_object` 3901, `rna_def_object_base` 3959, `RNA_def_object` 4004 |

## `source/source/blender/makesrna/intern/rna_object_game.c` (1.612 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Rede, destruição, explosivo, deformação (callbacks) | `rna_RangeNetObjectSettings_replicate_set` 113, `rna_explosive_style_colors` 130, `rna_RangeExplosiveSettings_use_particle_explosion_set` 163, `rna_RangeDeformSettings_mode_set` 181, `rna_RangeDeformSettings_decal_set` 194, `rna_RangeDestructionSettings_fragments_set` 213, `rna_RangeExplosiveSettings_use_light_flash_set` 245, `rna_RangeExplosiveSettings_use_ground_mark_set` 263 |
| Partículas GPU, reverb e raio (callbacks) | `rna_GPUParticleSettings_particle_look_update` 283, `rna_reverb_area_apply_preset` 436, `rna_ReverbAreaSettings_preset_update` 491, `rna_Object_lightning_preview_update` 513, `rna_GPUParticles_use_size_curve_update` 521 |
| Definições: sistemas da engine | `rna_def_object_gpu_particles` 543 (≈300 linhas), `rna_def_object_lightning` 878, `rna_def_object_reverb_area` 992, `rna_def_object_network` 1083, `rna_def_object_destruction` 1142, `rna_def_object_explosive` 1208, `rna_def_object_deform` 1441, `RNA_def_object_game` 1601 |
