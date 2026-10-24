# Mapa de código — RNA do objeto (`rna_object.c`)

Índice de `rna_object.c`: propriedades Python e UI do Object, incluindo as da engine (física de jogo,
destruição, explosivo, deformação, partículas GPU, reverb, raio, rede, LOD). Não descreve arquitetura.

**Linhas conferidas em 2026-10-23 (`HEAD` `8eea9701`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

O arquivo tem duas metades: callbacks `rna_*` (get, set, update; até ~2.330) e definições `rna_def_*`, que
declaram as propriedades. Uma propriedade nova costuma mexer nas duas: o `RNA_def_property` na `rna_def_` do
domínio e, se precisar, um callback perto dos irmãos.

## Receitas

**Propriedade nova de jogo no objeto.** 1) Campo em `DNA_object_types.h`, com default no `do_versions` se
zero não servir (arquivos da Range original pulam nosso versioning). 2) `RNA_def_property` em
`rna_def_object_game_settings` ou na `rna_def_object_<domínio>`. 3) UI em
`source/release/scripts/startup/bl_ui/properties_game*.py`. 4) O Converter lê o campo.

**Toggle que liga outro sistema (ex.: Explosive cria Destruction).** Ver os `*_set` de `use_*` no topo
(`rna_GameObjectSettings_use_explosive_set` e vizinhos).

## `source/source/blender/makesrna/intern/rna_object.c` (5.492 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Toggles de jogo (veículo, rede, destruição, explosivo, deformação) | `rna_GameObjectSettings_is_vehicle_set` 223, `rna_RangeNetObjectSettings_replicate_set` 246, `rna_GameObjectSettings_use_destruction_set` 264, `rna_explosive_style_colors` 285, `rna_GameObjectSettings_use_explosive_set` 336, `rna_RangeDeformSettings_mode_set` 358, `rna_GameObjectSettings_use_deform_set` 389, `rna_RangeExplosiveSettings_use_light_flash_set` 447, `rna_RangeExplosiveSettings_use_ground_mark_set` 465 |
| Partículas GPU, reverb e raio | `rna_Object_use_gpu_particles_update` 494, `rna_GPUParticleSettings_particle_look_update` 512, `rna_reverb_area_apply_preset` 665, `rna_Object_use_reverb_area_update` 720, `rna_ReverbAreaSettings_preset_update` 744, `rna_Object_lightning_preview_update` 766, `rna_Object_use_lightning_update` 774 |
| Matrizes, camadas e Base | `rna_Object_matrix_local_get` 808, `rna_Object_matrix_basis_get` 834, `rna_Object_layer_update` 926, `rna_Base_collection_get` 950, `rna_Object_layer_set` 1775, `rna_Base_layer_set` 1785 |
| Data, parent e dupli | `rna_Object_data_set` 991, `rna_Object_data_typef` 1041, `rna_Object_parent_set` 1062, `rna_Object_parent_type_itemf` 1079, `rna_Object_collision_bounds_itemf` 1120, `rna_Object_dup_group_set` 1157 |
| Vertex groups, UV e cor | `rna_VertexGroup_name_set` 1176, `rna_Object_active_vertex_group_index_set` 1203, `rna_object_uvlayer_name_set` 1256, `rna_Object_vgroup_new` 2184, `rna_VertexGroup_vertex_add` 2214 |
| Materiais e slots | `rna_Object_active_material_index_set` 1308, `rna_Object_active_material_set` 1339, `rna_MaterialSlot_material_set` 1513, `rna_MaterialSlot_link_set` 1531, `rna_MaterialSlot_path` 1583 |
| Transformação | `rna_Object_rotation_axis_angle_get` 1393, `rna_Object_rotation_mode_set` 1414, `rna_Object_dimensions_set` 1431, `rna_Object_location_editable` 1437 |
| Jogo: Load Mode, física, estados | `rna_Object_game_load_mode_get` 1593, `rna_Object_convert_object_set` 1609, `rna_GameObjectSettings_physics_type_get` 1625, `rna_GameObjectSettings_physics_type_set` 1666, `rna_GameObjectSettings_state_set` 1809, `rna_GameStateName_name_set` 1850, `rna_GameObjectSettings_col_group_set` 1941, `rna_GameObjectSettings_col_mask_set` 1970 |
| Grupos de bricks e componentes | `rna_object_brick_group_rename` 1856, `rna_LogicBrickGroups_new` 1888, `rna_GameObjectSettings_components_new` 2135, `rna_GameObjectSettings_components_remove` 2155 |
| Constraints, modifiers, shape keys | `rna_Object_active_shape_key_index_range` 1990, `rna_Object_constraints_new` 2073, `rna_Object_modifier_new` 2109, `rna_Object_boundbox_get` 2171 |
| Polls e LOD | `rna_Mesh_object_poll` 2271, `rna_Camera_object_poll` 2276, `rna_GPUParticles_use_size_curve_update` 2298, `rna_Object_lod_distance_update` 2318 |
| Definições: auxiliares | `rna_def_vertex_group` 2330, `rna_def_material_slot` 2394, `rna_def_game_object_activity_culling` 2435 |
| Definições: sistemas da engine | `rna_def_object_gpu_particles` 2475 (≈300 linhas), `rna_def_object_lightning` 2784, `rna_def_object_reverb_area` 2898, `rna_def_object_network` 2989, `rna_def_object_destruction` 3048, `rna_def_object_explosive` 3114, `rna_def_object_deform` 3347 |
| Definições: jogo | `rna_def_game_state_name` 3507, `rna_def_logic_brick_group` 3530, `rna_def_object_game_components` 3567, **`rna_def_object_game_settings`** 3595 (≈470 linhas: física, colisão, estados) |
| Definições: coleções e veículo | `rna_def_object_constraints` 4061, `rna_def_object_modifiers` 4109, `rna_def_object_vertex_groups` 4194, `rna_def_object_lodlevel` 4243, `rna_def_object_wheel_settings` 4319, `rna_def_object_gear_ratio` 4433, `rna_def_object_animation_event` 4451 |
| Definição principal | **`rna_def_object`** 4501 (≈870 linhas), `rna_def_dupli_object` 5369, `rna_def_object_base` 5427, `RNA_def_object` 5472 |
