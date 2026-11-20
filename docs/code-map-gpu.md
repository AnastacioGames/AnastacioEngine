# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-11-20 (`HEAD` `d09c51a4`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (676 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (4.048 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (7.019 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 148, `GPU_material_construct_begin` 209, `gpu_material_construct_end` 313 (compila e cria o pass), `GPU_material_free` 665, `gpu_material_add_node` 1495 |
| Instancing e skinning | `GPU_material_use_instancing` 702, `GPU_material_bind_instancing_attrib` 707, `GPU_material_use_skinning` 774, `GPU_material_bind_bone_matrices` 785 |
| Bind por desenho | `GPU_material_update_lamps` 822, `GPU_material_bind` 911, `GPU_material_bind_uniforms` 1070 (uniforms por objeto), `GPU_material_unbind` 1203, `GPU_material_load_images` 1230, `GPU_material_set_foliage_reference_position` 1237 |
| SSGI | `GPU_material_ssgi_slot` 1270, `GPU_material_ssgi_disabled_reason` 1321, `GPU_material_ssgi_approximate` 1334, `gpu_ssgi_closure` 1412, `GPU_material_ssgi_outputs` 1469 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1345, `GPU_material_shadow_color_link` 1366, `gpu_material_link_shadow_color` 1379 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1487, `GPU_material_vertex_offset` 1501, `GPU_material_shells` 1511, `GPU_material_outline` 1532, `GPU_material_strands` 1540, `GPU_material_explode` 1551, `GPU_material_planar_reflection` 1567 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1579, `GPU_material_has_error` 1646, `gpu_material_add_script_uniform` 1670, `GPU_material_script_uniform_set` 1683, `GPU_material_node_error` 1739 |
| Color management (Filmic) | `gpu_view_transform_contrast` 2006, `gpu_material_link_display_transform` 2023, `GPU_material_do_color_management` 2037 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 2061, `ramp_diffuse_result` 2224, `shade_light_textures` 2371, `shade_one_light` 2490 (≈460 linhas), `material_lights` 2962, `do_material_tex` 3101 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3899, `GPU_shaderesult_set` 4007 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3934, `GPU_horizon_update_color` 3946, `GPU_update_exposure_range` 3968, `GPU_sky_texture_slot` 3977, `GPU_sky_texture_follow_sun` 3991, `do_world_tex` 4495, `gpu_material_old_world` 4641, `GPU_material_world` 4789, `GPU_material_world_prefetch` 4831, `GPU_material_world_env` 4856 |
| Entrada principal e cache | `GPU_blender_material` 4415, `GPU_material_matcap` 4452, **`GPU_material_from_blender`** 4961, `GPU_material_prefetch` 5069, `GPU_material_moves_vertices` 5142, `GPU_materials_free_text` 5166, `GPU_materials_free` 5182 |
| Lâmpadas | `GPU_lamp_update` 5231, `GPU_lamp_update_colors` 5284, `gpu_lamp_from_blender` 5325, `GPU_lamp_from_blender` 5674, `GPU_lamp_free` 5823, `GPU_lamp_get_data` 6839 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5472, `gpu_lamp_create_shadow_buffer` 5497, `gpu_lamp_create_cascade` 5579 (CSM), `gpu_lamp_create_point_shadow_buffer` 5627, `GPU_lamp_shadow_set_size` 5880, `gpu_lamp_csm_auto_bias` 5959, `GPU_lamp_shadow_buffer_bind` 6021, `GPU_lamp_shadow_buffer_unbind` 5766, `GPU_lamp_shadow_color_begin` 6120, `GPU_lamp_shadow_static_ensure` 6197 (sombra estática), `GPU_lamp_shadow_static_matches` 6247 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6338, `GPU_material_bind_probe` 6511, `GPU_material_bind_probe2` 6562, `GPU_material_bind_planar` 6665, `GPU_material_bind_damage` 6745, `GPU_material_bind_scene_lights` 6338 |

## `source/source/blender/gpu/intern/gpu_material_export.c` (330 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Exportação e OpenSubdiv | `GPU_shader_export` 78, `GPU_material_update_fvar_offset` 282 |

## `source/source/blender/gpu/intern/gpu_material_ies.c` (376 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| IES | `ies_parse` 182, `GPU_lamp_ies_slot` 320, `gpu_ies_atlas` 357 |

## `source/source/blender/gpu/intern/gpu_material_intern.h` (293 linhas)

Definições internas de `struct GPUMaterial` e `struct GPULamp` e o protótipo de `gpu_ies_atlas` (usado pelo bind de luzes da cena).

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.926 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 236 |
| Atributos, coordenadas e mapping | `vcol_attribute` 295, `uv_attribute` 300, `particle_info` 322, `mapping_point` 482, `texco_uv` 1322, `texco_object` 1346 |
| Math, mix e conversores | `math_add` 520 … `math_sqrt` 675, `vec_math_add` 688, `curves_rgb` 777, `mix_blend` 860 … `mix_linear` 1115, `hue_sat` 1153, `separate_rgb` 1168 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1390 … `mtex_value_blend` 1573, `mtex_cube_map` 1782, `mtex_bump_init_objspace` 1888, `mtex_nspace_tangent` 2154 |
| Lâmpada legada | `lamp_visibility_sun` 2177, `lamp_falloff_invlinear` 2205, `shade_diffuse_oren_nayar` 3087, `shade_phong_spec` 3263, `shade_toon_spec` 3335 |
| Mundo, estrelas e céu | `world_paper_view` 2357, `world_stars` 2371, `sky_atmosphere` 2607, `sky_aurora` 2729, `sky_moon` 2753, `do_sky_simple` 2822, `do_sky_atmospheric` 2881, `world_blend_paper_real` 2915 |
| Ambiente e sondas | `env_sky` 3447, `env_irradiance_dir` 3480, `env_brdf_approx` 3510, `env_cube_tex` 3532, `env_probe_sample` 3583, `env_apply` 3730, `probe_cube_tex` 4583 |
| Sombras | `test_shadow_simple` 3878, `test_shadow_pcf` 3967, `test_shadow_vsm` 4073, `shadow_pcf` 4113, `csm_reference_distance` 4218, `csm_debug_tint` 4372, `shadow_fade` 4392, `shadow_color_output` 4413, `shadow_color_tint` 4457, `csm_shadow_color_tint` 4462, `shade_shadow_tint` 4472, `shade_shadow_tint_csm` 4480, `shadow_point` 4945 |
| Névoa, exposição e saída | `shade_exposure_correct` 4618, `shade_mist_factor` 4648, `shade_alpha_opaque` 4689, `shade_gbuffer0` 4701 |
| Luz da cena (nós novos) | `scene_light_shadow` 5051, `scene_light_shadow_tint` 5111, `scene_light_ies` 5138, `scene_light_dir` 5150, `scene_light_visibility` 5188 |
| BSDFs | `node_bsdf_diffuse_ambient` 5203, `node_bsdf_diffuse_ambient_ssgi` 5223, `node_bsdf_diffuse` 5260, `node_bsdf_glossy` 5270, `node_bsdf_glass` 5421, `node_bsdf_toon` 5461, `node_bsdf_principled` 5556, `node_bsdf_translucent` 5775, `node_bsdf_hair` 5869, `node_bsdf_refraction` 6005 |
| Lightmap e light volume | `lightmap_sample` 5501, `lightmap_mark_ao` 5511, `lightvol_sample` 5540 |
| Emissão, mix e SSGI | `node_emission` 6036, `node_background` 6067, `node_mix_shader` 6074, `ssgi_blend_closures` 6085, `ssgi_approximate_closure` 6114, `node_fresnel` 6128, `node_layer_weight` 6139 |
| Entradas | `node_attribute` 6173, `node_uvmap` 6180, `node_geometry` 6185, `node_tex_coord` 6205, `node_light_path` 7216, `node_object_info` 7260 |
| Texturas procedurais e imagem | `node_tex_gradient` 6295, `node_tex_checker` 6304, `node_tex_brick` 6361, `node_tex_image` 6411, `node_tex_image_box` 6417, `node_tex_noise` 6672, `node_tex_musgrave` 6885, `node_tex_sky` 7029, `node_tex_voronoi` 7090, `node_tex_wave` 7187 |
| Vetor, volume e saída | `node_bump` 7273, `node_displacement_object` 7304, `node_vector_displacement_tangent` 7316, `node_volume_absorption` 7413, `node_output_material` 7454, `node_output_world` 7459 |
| Parallax e preview | `mtex_parallax` 7464, `parallax_uv_in` 7539, `material_preview_matcap` 7551 |
| Valores por objeto (user) | `user_get_A` 7584, `user_get` 7609, `user_set_material` 7655, `user_set_world` 7690 |
| Vértice e geometria (nós da engine) | `node_damage` 7702, `node_vertex_offset` 7740, `node_vertex_wind` 7770, `node_vertex_wave` 7782, `node_shell_layer` 7797, `node_fur_shells` 7812, `node_outline` 7832, `node_billboard` 7843, `node_strands_info` 7879, `node_explode` 7887, `node_planar_reflection` 7910 |
