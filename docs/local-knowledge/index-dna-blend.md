# Indice de codigo: dna-blend

> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).
> Arquivos com mais de 1500 linhas estao marcados com **grande**: nao leia inteiros; veja `docs/code-map-*.md` quando existir.

## source/source/blender/makesdna

| arquivo | linhas | classes |
|---|---:|---|
| DNA_ID.h | 447 |  |
| DNA_action_types.h | 786 |  |
| DNA_actuator_types.h | 651 |  |
| DNA_anim_types.h | 1005 |  |
| DNA_armature_types.h | 249 |  |
| DNA_boid_types.h | 231 |  |
| DNA_brush_types.h | 352 |  |
| DNA_cachefile_types.h | 84 |  |
| DNA_camera_types.h | 181 |  |
| DNA_cloth_types.h | 117 |  |
| DNA_color_types.h | 182 |  |
| DNA_constraint_types.h | 867 |  |
| DNA_controller_types.h | 90 |  |
| DNA_curve_types.h | 470 |  |
| DNA_customdata_types.h | 200 |  |
| DNA_defs.h | 61 |  |
| DNA_documentation.h | 83 |  |
| DNA_dynamicpaint_types.h | 253 |  |
| DNA_effect_types.h | 133 |  |
| DNA_fileglobal_types.h | 59 |  |
| DNA_freestyle_types.h | 150 |  |
| DNA_genfile.h | 104 |  |
| DNA_gpencil_types.h | 342 |  |
| DNA_gpu_types.h | 48 |  |
| DNA_group_types.h | 57 |  |
| DNA_image_types.h | 204 |  |
| DNA_ipo_types.h | 501 |  |
| DNA_key_types.h | 130 |  |
| DNA_lamp_types.h | 240 |  |
| DNA_lattice_types.h | 76 |  |
| DNA_linestyle_types.h | 568 |  |
| DNA_listBase.h | 59 |  |
| DNA_mask_types.h | 228 |  |
| DNA_material_types.h | 511 |  |
| DNA_mesh_types.h | 233 |  |
| DNA_meshdata_types.h | 516 |  |
| DNA_meta_types.h | 122 |  |
| DNA_modifier_types.h **grande** | 1634 |  |
| DNA_movieclip_types.h | 159 |  |
| DNA_nla_types.h | 96 |  |
| DNA_node_types.h | 1227 |  |
| DNA_object_enums.h | 45 |  |
| DNA_object_fluidsim_types.h | 185 |  |
| DNA_object_force_types.h | 471 |  |
| DNA_object_types.h | 956 |  |
| DNA_outliner_types.h | 101 |  |
| DNA_packedFile_types.h | 51 |  |
| DNA_particle_types.h | 616 |  |
| DNA_property_types.h | 57 |  |
| DNA_python_component_types.h | 68 |  |
| DNA_rigidbody_types.h | 313 |  |
| DNA_scene_types.h **grande** | 2522 |  |
| DNA_screen_types.h | 441 |  |
| DNA_sdna_types.h | 76 |  |
| DNA_sensor_types.h | 417 |  |
| DNA_sequence_types.h | 592 |  |
| DNA_smoke_types.h | 289 |  |
| DNA_sound_types.h | 130 |  |
| DNA_space_types.h | 1496 |  |
| DNA_speaker_types.h | 75 |  |
| DNA_text_types.h | 72 |  |
| DNA_texture_types.h | 702 |  |
| DNA_tracking_types.h | 518 |  |
| DNA_userdef_types.h | 980 |  |
| DNA_vec_types.h | 88 |  |
| DNA_vfont_types.h | 65 |  |
| DNA_view2d_types.h | 166 |  |
| DNA_view3d_types.h | 398 |  |
| DNA_windowmanager_types.h | 411 |  |
| DNA_world_types.h | 247 |  |

## source/source/blender/makesdna/intern

| arquivo | linhas | classes |
|---|---:|---|
| dna_genfile.c | 1383 |  |
| makesdna.c | 1354 |  |

## source/source/blender/blenloader

| arquivo | linhas | classes |
|---|---:|---|
| BLO_blend_defs.h | 80 |  |
| BLO_readfile.h | 163 | `BlendFileReadParams` |
| BLO_runtime.h | 44 |  |
| BLO_undofile.h | 63 |  |
| BLO_writefile.h | 39 |  |

## source/source/blender/blenloader/intern

| arquivo | linhas | classes |
|---|---:|---|
| blend_validate.c | 145 |  |
| readblenentry.c | 482 |  |
| readfile.c **grande** | 11015 |  |
| readfile.h | 172 |  |
| runtime.c | 141 |  |
| undofile.c | 186 |  |
| versioning_250.c **grande** | 2748 |  |
| versioning_260.c **grande** | 2727 |  |
| versioning_270.c **grande** | 1879 |  |
| versioning_defaults.c | 423 |  |
| versioning_legacy.c **grande** | 3530 |  |
| versioning_range.c | 470 |  |
| versioning_upbge.c | 354 |  |
| versioning_userdef.c | 1297 |  |
| writefile.c **grande** | 4324 |  |
