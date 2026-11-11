# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-11-11 (`HEAD` `baa73ea8`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (657 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.798 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.951 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 148, `GPU_material_construct_begin` 193, `gpu_material_construct_end` 297 (compila e cria o pass), `GPU_material_free` 648, `gpu_material_add_node` 1470 |
| Instancing e skinning | `GPU_material_use_instancing` 685, `GPU_material_bind_instancing_attrib` 690, `GPU_material_use_skinning` 757, `GPU_material_bind_bone_matrices` 768 |
| Bind por desenho | `GPU_material_update_lamps` 805, `GPU_material_bind` 894, `GPU_material_bind_uniforms` 1053 (uniforms por objeto), `GPU_material_unbind` 1186, `GPU_material_load_images` 1213, `GPU_material_set_foliage_reference_position` 1220 |
| SSGI | `GPU_material_ssgi_slot` 1253, `GPU_material_ssgi_disabled_reason` 1304, `GPU_material_ssgi_approximate` 1317, `gpu_ssgi_closure` 1387, `GPU_material_ssgi_outputs` 1444 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1328, `GPU_material_shadow_color_link` 1338, `gpu_material_link_shadow_color` 1351 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1462, `GPU_material_vertex_offset` 1476, `GPU_material_shells` 1486, `GPU_material_outline` 1507, `GPU_material_strands` 1515, `GPU_material_explode` 1526, `GPU_material_planar_reflection` 1542 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1554, `GPU_material_has_error` 1621, `gpu_material_add_script_uniform` 1645, `GPU_material_script_uniform_set` 1658, `GPU_material_node_error` 1714 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1981, `gpu_material_link_display_transform` 1998, `GPU_material_do_color_management` 2012 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 2036, `ramp_diffuse_result` 2199, `shade_light_textures` 2346, `shade_one_light` 2465 (≈460 linhas), `material_lights` 2937, `do_material_tex` 3076 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3868, `GPU_shaderesult_set` 3976 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3903, `GPU_horizon_update_color` 3915, `GPU_update_exposure_range` 3937, `GPU_sky_texture_slot` 3946, `GPU_sky_texture_follow_sun` 3960, `do_world_tex` 4464, `gpu_material_old_world` 4610, `GPU_material_world` 4758, `GPU_material_world_prefetch` 4800, `GPU_material_world_env` 4825 |
| Entrada principal e cache | `GPU_blender_material` 4384, `GPU_material_matcap` 4421, **`GPU_material_from_blender`** 4931, `GPU_material_prefetch` 5039, `GPU_material_moves_vertices` 5112, `GPU_materials_free_text` 5136, `GPU_materials_free` 5152 |
| Lâmpadas | `GPU_lamp_update` 5201, `GPU_lamp_update_colors` 5254, `gpu_lamp_from_blender` 5295, `GPU_lamp_from_blender` 5644, `GPU_lamp_free` 5793, `GPU_lamp_get_data` 6771 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5442, `gpu_lamp_create_shadow_buffer` 5467, `gpu_lamp_create_cascade` 5549 (CSM), `gpu_lamp_create_point_shadow_buffer` 5597, `GPU_lamp_shadow_set_size` 5850, `gpu_lamp_csm_auto_bias` 5929, `GPU_lamp_shadow_buffer_bind` 5991, `GPU_lamp_shadow_buffer_unbind` 5736, `GPU_lamp_shadow_color_begin` 6082, `GPU_lamp_shadow_static_ensure` 6142 (sombra estática), `GPU_lamp_shadow_static_matches` 6192 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6283, `GPU_material_bind_probe` 6456, `GPU_material_bind_probe2` 6507, `GPU_material_bind_planar` 6610, `GPU_material_bind_damage` 6677, `GPU_material_bind_scene_lights` 6283 |

## `source/source/blender/gpu/intern/gpu_material_export.c` (330 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Exportação e OpenSubdiv | `GPU_shader_export` 78, `GPU_material_update_fvar_offset` 282 |

## `source/source/blender/gpu/intern/gpu_material_ies.c` (376 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| IES | `ies_parse` 182, `GPU_lamp_ies_slot` 320, `gpu_ies_atlas` 357 |

## `source/source/blender/gpu/intern/gpu_material_intern.h` (291 linhas)

Definições internas de `struct GPUMaterial` e `struct GPULamp` e o protótipo de `gpu_ies_atlas` (usado pelo bind de luzes da cena).

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.910 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 236 |
| Atributos, coordenadas e mapping | `vcol_attribute` 295, `uv_attribute` 300, `particle_info` 322, `mapping_point` 475, `texco_uv` 1315, `texco_object` 1339 |
| Math, mix e conversores | `math_add` 513 … `math_sqrt` 668, `vec_math_add` 681, `curves_rgb` 770, `mix_blend` 853 … `mix_linear` 1108, `hue_sat` 1146, `separate_rgb` 1161 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1383 … `mtex_value_blend` 1566, `mtex_cube_map` 1775, `mtex_bump_init_objspace` 1881, `mtex_nspace_tangent` 2147 |
| Lâmpada legada | `lamp_visibility_sun` 2170, `lamp_falloff_invlinear` 2198, `shade_diffuse_oren_nayar` 3080, `shade_phong_spec` 3256, `shade_toon_spec` 3328 |
| Mundo, estrelas e céu | `world_paper_view` 2350, `world_stars` 2364, `sky_atmosphere` 2600, `sky_aurora` 2722, `sky_moon` 2746, `do_sky_simple` 2815, `do_sky_atmospheric` 2874, `world_blend_paper_real` 2908 |
| Ambiente e sondas | `env_sky` 3440, `env_irradiance_dir` 3473, `env_brdf_approx` 3503, `env_cube_tex` 3525, `env_probe_sample` 3576, `env_apply` 3723, `probe_cube_tex` 4576 |
| Sombras | `test_shadow_simple` 3871, `test_shadow_pcf` 3960, `test_shadow_vsm` 4066, `shadow_pcf` 4106, `csm_reference_distance` 4211, `csm_debug_tint` 4365, `shadow_fade` 4385, `shadow_color_output` 4406, `shadow_color_tint` 4450, `csm_shadow_color_tint` 4455, `shade_shadow_tint` 4465, `shade_shadow_tint_csm` 4473, `shadow_point` 4938 |
| Névoa, exposição e saída | `shade_exposure_correct` 4611, `shade_mist_factor` 4641, `shade_alpha_opaque` 4682, `shade_gbuffer0` 4694 |
| Luz da cena (nós novos) | `scene_light_shadow` 5044, `scene_light_shadow_tint` 5104, `scene_light_ies` 5131, `scene_light_dir` 5143, `scene_light_visibility` 5181 |
| BSDFs | `node_bsdf_diffuse_ambient` 5196, `node_bsdf_diffuse_ambient_ssgi` 5216, `node_bsdf_diffuse` 5253, `node_bsdf_glossy` 5263, `node_bsdf_glass` 5414, `node_bsdf_toon` 5454, `node_bsdf_principled` 5549, `node_bsdf_translucent` 5768, `node_bsdf_hair` 5862, `node_bsdf_refraction` 5998 |
| Lightmap e light volume | `lightmap_sample` 5494, `lightmap_mark_ao` 5504, `lightvol_sample` 5533 |
| Emissão, mix e SSGI | `node_emission` 6029, `node_background` 6060, `node_mix_shader` 6067, `ssgi_blend_closures` 6078, `ssgi_approximate_closure` 6107, `node_fresnel` 6121, `node_layer_weight` 6132 |
| Entradas | `node_attribute` 6166, `node_uvmap` 6173, `node_geometry` 6178, `node_tex_coord` 6198, `node_light_path` 7209, `node_object_info` 7253 |
| Texturas procedurais e imagem | `node_tex_gradient` 6288, `node_tex_checker` 6297, `node_tex_brick` 6354, `node_tex_image` 6404, `node_tex_image_box` 6410, `node_tex_noise` 6665, `node_tex_musgrave` 6878, `node_tex_sky` 7022, `node_tex_voronoi` 7083, `node_tex_wave` 7180 |
| Vetor, volume e saída | `node_bump` 7266, `node_displacement_object` 7297, `node_vector_displacement_tangent` 7309, `node_volume_absorption` 7406, `node_output_material` 7447, `node_output_world` 7452 |
| Parallax e preview | `mtex_parallax` 7457, `parallax_uv_in` 7532, `material_preview_matcap` 7544 |
| Valores por objeto (user) | `user_get_A` 7577, `user_get` 7602, `user_set_material` 7648, `user_set_world` 7683 |
| Vértice e geometria (nós da engine) | `node_damage` 7695, `node_vertex_offset` 7733, `node_vertex_wind` 7763, `node_vertex_wave` 7775, `node_shell_layer` 7790, `node_fur_shells` 7805, `node_outline` 7825, `node_billboard` 7836, `node_strands_info` 7863, `node_explode` 7871, `node_planar_reflection` 7894 |
