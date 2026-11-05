# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-11-05 (`HEAD` `934d2d1c`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (645 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.751 linhas): monta o GLSL final
  a partir do grafo de nós; cola `gpu_shader_material.glsl` inteiro como biblioteca de funções.
- Nós de shader do editor: `source/source/blender/nodes/shader/nodes/node_shader_*.c`. Cada um chama
  `GPU_stack_link(mat, "nome_glsl", in, out)`, que é o nome da função em `gpu_shader_material.glsl`.

## Receitas

**Novo nó de shader (ou mudar um existente).** 1) Função GLSL em `gpu_shader_material.glsl`, perto das irmãs
(tabela abaixo). 2) `node_shader_<nome>.c`: sockets e `GPU_stack_link` com o mesmo nome. 3) Nó novo: registrar
em `nodes/NOD_static_types.h`, `NOD_shader.h`, `blenkernel/intern/node.c` e no menu Python. 4) Rebuild do
alvo `bf_gpu` (o GLSL vira C pelo `data_to_c_simple`, só recompila se o alvo rodar).

**Novo uniform de mundo/cena (céu, névoa, exposição).** Valor global em `gpu_material.c` (seção "Mundo, céu e
névoa"), `GPUDynamicType` novo em `GPU_material.h`, ligação em `GPU_material_bind_uniforms` e uso no GLSL.

**Sombra.** Buffers e cascatas em `gpu_material.c` ("Lâmpadas e sombras"); amostragem no GLSL ("Sombras").
Sombra colorida = `GPU_lamp_shadow_color_*` + `shadow_color_*`/`csm_shadow_color_tint`.

## `source/source/blender/gpu/intern/gpu_material.c` (6.793 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 148, `GPU_material_construct_begin` 193, `gpu_material_construct_end` 297 (compila e cria o pass), `GPU_material_free` 638, `gpu_material_add_node` 1397 |
| Instancing e skinning | `GPU_material_use_instancing` 675, `GPU_material_bind_instancing_attrib` 680, `GPU_material_use_skinning` 747, `GPU_material_bind_bone_matrices` 758 |
| Bind por desenho | `GPU_material_update_lamps` 767, `GPU_material_bind` 856, `GPU_material_bind_uniforms` 1015 (uniforms por objeto), `GPU_material_unbind` 1148, `GPU_material_load_images` 1175, `GPU_material_set_foliage_reference_position` 1182 |
| SSGI | `GPU_material_ssgi_slot` 1215, `GPU_material_ssgi_disabled_reason` 1231, `GPU_material_ssgi_approximate` 1244, `gpu_ssgi_closure` 1314, `GPU_material_ssgi_outputs` 1371 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1255, `GPU_material_shadow_color_link` 1265, `gpu_material_link_shadow_color` 1278 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1389, `GPU_material_vertex_offset` 1403, `GPU_material_shells` 1413, `GPU_material_outline` 1434, `GPU_material_strands` 1442, `GPU_material_explode` 1453, `GPU_material_planar_reflection` 1469 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1481, `GPU_material_has_error` 1548, `gpu_material_add_script_uniform` 1572, `GPU_material_script_uniform_set` 1585, `GPU_material_node_error` 1641 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1904, `gpu_material_link_display_transform` 1921, `GPU_material_do_color_management` 1935 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1953, `ramp_diffuse_result` 2105, `shade_light_textures` 2252, `shade_one_light` 2371 (≈460 linhas), `material_lights` 2839, `do_material_tex` 2978 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3770, `GPU_shaderesult_set` 3878 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3805, `GPU_horizon_update_color` 3817, `GPU_update_exposure_range` 3839, `GPU_sky_texture_slot` 3848, `GPU_sky_texture_follow_sun` 3862, `do_world_tex` 4366, `gpu_material_old_world` 4512, `GPU_material_world` 4660, `GPU_material_world_prefetch` 4702, `GPU_material_world_env` 4727 |
| Entrada principal e cache | `GPU_blender_material` 4286, `GPU_material_matcap` 4323, **`GPU_material_from_blender`** 4833, `GPU_material_prefetch` 4939, `GPU_material_moves_vertices` 5012, `GPU_materials_free_text` 5036, `GPU_materials_free` 5052 |
| Lâmpadas | `GPU_lamp_update` 5101, `GPU_lamp_update_colors` 5154, `gpu_lamp_from_blender` 5185, `GPU_lamp_from_blender` 5533, `GPU_lamp_free` 5682, `GPU_lamp_get_data` 6613 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5331, `gpu_lamp_create_shadow_buffer` 5356, `gpu_lamp_create_cascade` 5438 (CSM), `gpu_lamp_create_point_shadow_buffer` 5486, `GPU_lamp_shadow_set_size` 5739, `gpu_lamp_csm_auto_bias` 5818, `GPU_lamp_shadow_buffer_bind` 5846, `GPU_lamp_shadow_buffer_unbind` 5625, `GPU_lamp_shadow_color_begin` 5937, `GPU_lamp_shadow_static_ensure` 5997 (sombra estática), `GPU_lamp_shadow_static_matches` 6047 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6138, `GPU_material_bind_probe` 6311, `GPU_material_bind_probe2` 6362, `GPU_material_bind_planar` 6465, `GPU_material_bind_damage` 6519, `GPU_material_bind_scene_lights` 6138 |

## `source/source/blender/gpu/intern/gpu_material_export.c` (330 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Exportação e OpenSubdiv | `GPU_shader_export` 78, `GPU_material_update_fvar_offset` 282 |

## `source/source/blender/gpu/intern/gpu_material_ies.c` (376 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| IES | `ies_parse` 182, `GPU_lamp_ies_slot` 320, `gpu_ies_atlas` 357 |

## `source/source/blender/gpu/intern/gpu_material_intern.h` (287 linhas)

Definições internas de `struct GPUMaterial` e `struct GPULamp` e o protótipo de `gpu_ies_atlas` (usado pelo bind de luzes da cena).

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.876 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 236 |
| Atributos, coordenadas e mapping | `vcol_attribute` 282, `uv_attribute` 287, `particle_info` 309, `mapping_point` 462, `texco_uv` 1302, `texco_object` 1326 |
| Math, mix e conversores | `math_add` 500 … `math_sqrt` 655, `vec_math_add` 668, `curves_rgb` 757, `mix_blend` 840 … `mix_linear` 1095, `hue_sat` 1133, `separate_rgb` 1148 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1370 … `mtex_value_blend` 1553, `mtex_cube_map` 1762, `mtex_bump_init_objspace` 1867, `mtex_nspace_tangent` 2132 |
| Lâmpada legada | `lamp_visibility_sun` 2155, `lamp_falloff_invlinear` 2183, `shade_diffuse_oren_nayar` 3046, `shade_phong_spec` 3222, `shade_toon_spec` 3294 |
| Mundo, estrelas e céu | `world_paper_view` 2325, `world_stars` 2339, `sky_atmosphere` 2575, `sky_aurora` 2697, `sky_moon` 2721, `do_sky_simple` 2790, `do_sky_atmospheric` 2840, `world_blend_paper_real` 2874 |
| Ambiente e sondas | `env_sky` 3406, `env_irradiance_dir` 3439, `env_brdf_approx` 3469, `env_cube_tex` 3491, `env_probe_sample` 3542, `env_apply` 3689, `probe_cube_tex` 4542 |
| Sombras | `test_shadow_simple` 3837, `test_shadow_pcf` 3926, `test_shadow_vsm` 4032, `shadow_pcf` 4072, `csm_reference_distance` 4177, `csm_debug_tint` 4331, `shadow_fade` 4351, `shadow_color_output` 4372, `shadow_color_tint` 4416, `csm_shadow_color_tint` 4421, `shade_shadow_tint` 4431, `shade_shadow_tint_csm` 4439, `shadow_point` 4904 |
| Névoa, exposição e saída | `shade_exposure_correct` 4577, `shade_mist_factor` 4607, `shade_alpha_opaque` 4648, `shade_gbuffer0` 4660 |
| Luz da cena (nós novos) | `scene_light_shadow` 5010, `scene_light_shadow_tint` 5070, `scene_light_ies` 5097, `scene_light_dir` 5109, `scene_light_visibility` 5147 |
| BSDFs | `node_bsdf_diffuse_ambient` 5162, `node_bsdf_diffuse_ambient_ssgi` 5182, `node_bsdf_diffuse` 5219, `node_bsdf_glossy` 5229, `node_bsdf_glass` 5380, `node_bsdf_toon` 5420, `node_bsdf_principled` 5515, `node_bsdf_translucent` 5734, `node_bsdf_hair` 5828, `node_bsdf_refraction` 5964 |
| Lightmap e light volume | `lightmap_sample` 5460, `lightmap_mark_ao` 5470, `lightvol_sample` 5499 |
| Emissão, mix e SSGI | `node_emission` 5995, `node_background` 6026, `node_mix_shader` 6033, `ssgi_blend_closures` 6044, `ssgi_approximate_closure` 6073, `node_fresnel` 6087, `node_layer_weight` 6098 |
| Entradas | `node_attribute` 6132, `node_uvmap` 6139, `node_geometry` 6144, `node_tex_coord` 6164, `node_light_path` 7175, `node_object_info` 7219 |
| Texturas procedurais e imagem | `node_tex_gradient` 6254, `node_tex_checker` 6263, `node_tex_brick` 6320, `node_tex_image` 6370, `node_tex_image_box` 6376, `node_tex_noise` 6631, `node_tex_musgrave` 6844, `node_tex_sky` 6988, `node_tex_voronoi` 7049, `node_tex_wave` 7146 |
| Vetor, volume e saída | `node_bump` 7232, `node_displacement_object` 7263, `node_vector_displacement_tangent` 7275, `node_volume_absorption` 7372, `node_output_material` 7413, `node_output_world` 7418 |
| Parallax e preview | `mtex_parallax` 7423, `parallax_uv_in` 7498, `material_preview_matcap` 7510 |
| Valores por objeto (user) | `user_get_A` 7543, `user_get` 7568, `user_set_material` 7614, `user_set_world` 7649 |
| Vértice e geometria (nós da engine) | `node_damage` 7661, `node_vertex_offset` 7699, `node_vertex_wind` 7729, `node_vertex_wave` 7741, `node_shell_layer` 7756, `node_fur_shells` 7771, `node_outline` 7791, `node_billboard` 7802, `node_strands_info` 7829, `node_explode` 7837, `node_planar_reflection` 7860 |
