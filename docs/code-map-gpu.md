# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-11-05 (`HEAD` `6cb8d768`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (645 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.756 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.797 linhas)

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
| Color management (Filmic) | `gpu_view_transform_contrast` 1908, `gpu_material_link_display_transform` 1925, `GPU_material_do_color_management` 1939 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1957, `ramp_diffuse_result` 2109, `shade_light_textures` 2256, `shade_one_light` 2375 (≈460 linhas), `material_lights` 2843, `do_material_tex` 2982 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3774, `GPU_shaderesult_set` 3882 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3809, `GPU_horizon_update_color` 3821, `GPU_update_exposure_range` 3843, `GPU_sky_texture_slot` 3852, `GPU_sky_texture_follow_sun` 3866, `do_world_tex` 4370, `gpu_material_old_world` 4516, `GPU_material_world` 4664, `GPU_material_world_prefetch` 4706, `GPU_material_world_env` 4731 |
| Entrada principal e cache | `GPU_blender_material` 4290, `GPU_material_matcap` 4327, **`GPU_material_from_blender`** 4837, `GPU_material_prefetch` 4943, `GPU_material_moves_vertices` 5016, `GPU_materials_free_text` 5040, `GPU_materials_free` 5056 |
| Lâmpadas | `GPU_lamp_update` 5105, `GPU_lamp_update_colors` 5158, `gpu_lamp_from_blender` 5189, `GPU_lamp_from_blender` 5537, `GPU_lamp_free` 5686, `GPU_lamp_get_data` 6617 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5335, `gpu_lamp_create_shadow_buffer` 5360, `gpu_lamp_create_cascade` 5442 (CSM), `gpu_lamp_create_point_shadow_buffer` 5490, `GPU_lamp_shadow_set_size` 5743, `gpu_lamp_csm_auto_bias` 5822, `GPU_lamp_shadow_buffer_bind` 5850, `GPU_lamp_shadow_buffer_unbind` 5629, `GPU_lamp_shadow_color_begin` 5941, `GPU_lamp_shadow_static_ensure` 6001 (sombra estática), `GPU_lamp_shadow_static_matches` 6051 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6142, `GPU_material_bind_probe` 6315, `GPU_material_bind_probe2` 6366, `GPU_material_bind_planar` 6469, `GPU_material_bind_damage` 6523, `GPU_material_bind_scene_lights` 6142 |

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

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.900 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 236 |
| Atributos, coordenadas e mapping | `vcol_attribute` 295, `uv_attribute` 300, `particle_info` 322, `mapping_point` 475, `texco_uv` 1315, `texco_object` 1339 |
| Math, mix e conversores | `math_add` 513 … `math_sqrt` 668, `vec_math_add` 681, `curves_rgb` 770, `mix_blend` 853 … `mix_linear` 1108, `hue_sat` 1146, `separate_rgb` 1161 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1383 … `mtex_value_blend` 1566, `mtex_cube_map` 1775, `mtex_bump_init_objspace` 1881, `mtex_nspace_tangent` 2147 |
| Lâmpada legada | `lamp_visibility_sun` 2170, `lamp_falloff_invlinear` 2198, `shade_diffuse_oren_nayar` 3070, `shade_phong_spec` 3246, `shade_toon_spec` 3318 |
| Mundo, estrelas e céu | `world_paper_view` 2340, `world_stars` 2354, `sky_atmosphere` 2590, `sky_aurora` 2712, `sky_moon` 2736, `do_sky_simple` 2805, `do_sky_atmospheric` 2864, `world_blend_paper_real` 2898 |
| Ambiente e sondas | `env_sky` 3430, `env_irradiance_dir` 3463, `env_brdf_approx` 3493, `env_cube_tex` 3515, `env_probe_sample` 3566, `env_apply` 3713, `probe_cube_tex` 4566 |
| Sombras | `test_shadow_simple` 3861, `test_shadow_pcf` 3950, `test_shadow_vsm` 4056, `shadow_pcf` 4096, `csm_reference_distance` 4201, `csm_debug_tint` 4355, `shadow_fade` 4375, `shadow_color_output` 4396, `shadow_color_tint` 4440, `csm_shadow_color_tint` 4445, `shade_shadow_tint` 4455, `shade_shadow_tint_csm` 4463, `shadow_point` 4928 |
| Névoa, exposição e saída | `shade_exposure_correct` 4601, `shade_mist_factor` 4631, `shade_alpha_opaque` 4672, `shade_gbuffer0` 4684 |
| Luz da cena (nós novos) | `scene_light_shadow` 5034, `scene_light_shadow_tint` 5094, `scene_light_ies` 5121, `scene_light_dir` 5133, `scene_light_visibility` 5171 |
| BSDFs | `node_bsdf_diffuse_ambient` 5186, `node_bsdf_diffuse_ambient_ssgi` 5206, `node_bsdf_diffuse` 5243, `node_bsdf_glossy` 5253, `node_bsdf_glass` 5404, `node_bsdf_toon` 5444, `node_bsdf_principled` 5539, `node_bsdf_translucent` 5758, `node_bsdf_hair` 5852, `node_bsdf_refraction` 5988 |
| Lightmap e light volume | `lightmap_sample` 5484, `lightmap_mark_ao` 5494, `lightvol_sample` 5523 |
| Emissão, mix e SSGI | `node_emission` 6019, `node_background` 6050, `node_mix_shader` 6057, `ssgi_blend_closures` 6068, `ssgi_approximate_closure` 6097, `node_fresnel` 6111, `node_layer_weight` 6122 |
| Entradas | `node_attribute` 6156, `node_uvmap` 6163, `node_geometry` 6168, `node_tex_coord` 6188, `node_light_path` 7199, `node_object_info` 7243 |
| Texturas procedurais e imagem | `node_tex_gradient` 6278, `node_tex_checker` 6287, `node_tex_brick` 6344, `node_tex_image` 6394, `node_tex_image_box` 6400, `node_tex_noise` 6655, `node_tex_musgrave` 6868, `node_tex_sky` 7012, `node_tex_voronoi` 7073, `node_tex_wave` 7170 |
| Vetor, volume e saída | `node_bump` 7256, `node_displacement_object` 7287, `node_vector_displacement_tangent` 7299, `node_volume_absorption` 7396, `node_output_material` 7437, `node_output_world` 7442 |
| Parallax e preview | `mtex_parallax` 7447, `parallax_uv_in` 7522, `material_preview_matcap` 7534 |
| Valores por objeto (user) | `user_get_A` 7567, `user_get` 7592, `user_set_material` 7638, `user_set_world` 7673 |
| Vértice e geometria (nós da engine) | `node_damage` 7685, `node_vertex_offset` 7723, `node_vertex_wind` 7753, `node_vertex_wave` 7765, `node_shell_layer` 7780, `node_fur_shells` 7795, `node_outline` 7815, `node_billboard` 7826, `node_strands_info` 7853, `node_explode` 7861, `node_planar_reflection` 7884 |
