# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-10-29 (`HEAD` `2976bd78`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (631 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.732 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.621 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 146, `GPU_material_construct_begin` 191, `gpu_material_construct_end` 295 (compila e cria o pass), `GPU_material_free` 586, `gpu_material_add_node` 1319 |
| Instancing e skinning | `GPU_material_use_instancing` 631, `GPU_material_bind_instancing_attrib` 636, `GPU_material_use_skinning` 683, `GPU_material_bind_bone_matrices` 694 |
| Bind por desenho | `GPU_material_update_lamps` 703, `GPU_material_bind` 792, `GPU_material_bind_uniforms` 937 (uniforms por objeto), `GPU_material_unbind` 1070, `GPU_material_load_images` 1097, `GPU_material_set_foliage_reference_position` 1104 |
| SSGI | `GPU_material_ssgi_slot` 1137, `GPU_material_ssgi_disabled_reason` 1153, `GPU_material_ssgi_approximate` 1166, `gpu_ssgi_closure` 1236, `GPU_material_ssgi_outputs` 1293 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1177, `GPU_material_shadow_color_link` 1187, `gpu_material_link_shadow_color` 1200 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1311, `GPU_material_vertex_offset` 1325, `GPU_material_shells` 1335, `GPU_material_outline` 1356, `GPU_material_strands` 1364, `GPU_material_explode` 1375, `GPU_material_planar_reflection` 1391 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1403, `GPU_material_has_error` 1470, `gpu_material_add_script_uniform` 1494, `GPU_material_script_uniform_set` 1507, `GPU_material_node_error` 1563 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1806, `gpu_material_link_display_transform` 1824, `GPU_material_do_color_management` 1838 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1856, `ramp_diffuse_result` 2008, `shade_light_textures` 2155, `shade_one_light` 2274 (≈460 linhas), `material_lights` 2742, `do_material_tex` 2881 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3673, `GPU_shaderesult_set` 3781 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3708, `GPU_horizon_update_color` 3720, `GPU_update_exposure_range` 3742, `GPU_sky_texture_slot` 3751, `GPU_sky_texture_follow_sun` 3765, `do_world_tex` 4269, `gpu_material_old_world` 4415, `GPU_material_world` 4546, `GPU_material_world_prefetch` 4588, `GPU_material_world_env` 4613 |
| Entrada principal e cache | `GPU_blender_material` 4189, `GPU_material_matcap` 4226, **`GPU_material_from_blender`** 4719, `GPU_material_prefetch` 4825, `GPU_material_moves_vertices` 4898, `GPU_materials_free_text` 4922, `GPU_materials_free` 4938 |
| Lâmpadas | `GPU_lamp_update` 4987, `GPU_lamp_update_colors` 5040, `gpu_lamp_from_blender` 5071, `GPU_lamp_from_blender` 5419, `GPU_lamp_free` 5568, `GPU_lamp_get_data` 6441 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5217, `gpu_lamp_create_shadow_buffer` 5242, `gpu_lamp_create_cascade` 5324 (CSM), `gpu_lamp_create_point_shadow_buffer` 5372, `GPU_lamp_shadow_set_size` 5625, `gpu_lamp_csm_auto_bias` 5704, `GPU_lamp_shadow_buffer_bind` 5732, `GPU_lamp_shadow_buffer_unbind` 5511, `GPU_lamp_shadow_color_begin` 5823, `GPU_lamp_shadow_static_ensure` 5883 (sombra estática), `GPU_lamp_shadow_static_matches` 5933 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6024, `GPU_material_bind_probe` 6203, `GPU_material_bind_probe2` 6254, `GPU_material_bind_planar` 6307, `GPU_material_bind_damage` 6361, `GPU_material_bind_scene_lights` 6024 |

## `source/source/blender/gpu/intern/gpu_material_export.c` (330 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Exportação e OpenSubdiv | `GPU_shader_export` 78, `GPU_material_update_fvar_offset` 282 |

## `source/source/blender/gpu/intern/gpu_material_ies.c` (376 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| IES | `ies_parse` 182, `GPU_lamp_ies_slot` 320, `gpu_ies_atlas` 357 |

## `source/source/blender/gpu/intern/gpu_material_intern.h` (281 linhas)

Definições internas de `struct GPUMaterial` e `struct GPULamp` e o protótipo de `gpu_ies_atlas` (usado pelo bind de luzes da cena).

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.773 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 231 |
| Atributos, coordenadas e mapping | `vcol_attribute` 277, `uv_attribute` 282, `particle_info` 304, `mapping_point` 457, `texco_uv` 1297, `texco_object` 1321 |
| Math, mix e conversores | `math_add` 495 … `math_sqrt` 650, `vec_math_add` 663, `curves_rgb` 752, `mix_blend` 835 … `mix_linear` 1090, `hue_sat` 1128, `separate_rgb` 1143 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1365 … `mtex_value_blend` 1548, `mtex_cube_map` 1757, `mtex_bump_init_objspace` 1862, `mtex_nspace_tangent` 2127 |
| Lâmpada legada | `lamp_visibility_sun` 2150, `lamp_falloff_invlinear` 2178, `shade_diffuse_oren_nayar` 3007, `shade_phong_spec` 3183, `shade_toon_spec` 3255 |
| Mundo, estrelas e céu | `world_paper_view` 2320, `world_stars` 2334, `sky_atmosphere` 2570, `sky_aurora` 2692, `sky_moon` 2716, `do_sky_simple` 2751, `do_sky_atmospheric` 2801, `world_blend_paper_real` 2835 |
| Ambiente e sondas | `env_sky` 3367, `env_irradiance_dir` 3400, `env_brdf_approx` 3430, `env_cube_tex` 3452, `env_probe_sample` 3491, `env_apply` 3586, `probe_cube_tex` 4439 |
| Sombras | `test_shadow_simple` 3734, `test_shadow_pcf` 3823, `test_shadow_vsm` 3929, `shadow_pcf` 3969, `csm_reference_distance` 4074, `csm_debug_tint` 4228, `shadow_fade` 4248, `shadow_color_output` 4269, `shadow_color_tint` 4313, `csm_shadow_color_tint` 4318, `shade_shadow_tint` 4328, `shade_shadow_tint_csm` 4336, `shadow_point` 4801 |
| Névoa, exposição e saída | `shade_exposure_correct` 4474, `shade_mist_factor` 4504, `shade_alpha_opaque` 4545, `shade_gbuffer0` 4557 |
| Luz da cena (nós novos) | `scene_light_shadow` 4907, `scene_light_shadow_tint` 4967, `scene_light_ies` 4994, `scene_light_dir` 5006, `scene_light_visibility` 5044 |
| BSDFs | `node_bsdf_diffuse_ambient` 5059, `node_bsdf_diffuse_ambient_ssgi` 5079, `node_bsdf_diffuse` 5116, `node_bsdf_glossy` 5126, `node_bsdf_glass` 5277, `node_bsdf_toon` 5317, `node_bsdf_principled` 5412, `node_bsdf_translucent` 5631, `node_bsdf_hair` 5725, `node_bsdf_refraction` 5861 |
| Lightmap e light volume | `lightmap_sample` 5357, `lightmap_mark_ao` 5367, `lightvol_sample` 5396 |
| Emissão, mix e SSGI | `node_emission` 5892, `node_background` 5923, `node_mix_shader` 5930, `ssgi_blend_closures` 5941, `ssgi_approximate_closure` 5970, `node_fresnel` 5984, `node_layer_weight` 5995 |
| Entradas | `node_attribute` 6029, `node_uvmap` 6036, `node_geometry` 6041, `node_tex_coord` 6061, `node_light_path` 7072, `node_object_info` 7116 |
| Texturas procedurais e imagem | `node_tex_gradient` 6151, `node_tex_checker` 6160, `node_tex_brick` 6217, `node_tex_image` 6267, `node_tex_image_box` 6273, `node_tex_noise` 6528, `node_tex_musgrave` 6741, `node_tex_sky` 6885, `node_tex_voronoi` 6946, `node_tex_wave` 7043 |
| Vetor, volume e saída | `node_bump` 7129, `node_displacement_object` 7160, `node_vector_displacement_tangent` 7172, `node_volume_absorption` 7269, `node_output_material` 7310, `node_output_world` 7315 |
| Parallax e preview | `mtex_parallax` 7320, `parallax_uv_in` 7395, `material_preview_matcap` 7407 |
| Valores por objeto (user) | `user_get_A` 7440, `user_get` 7465, `user_set_material` 7511, `user_set_world` 7546 |
| Vértice e geometria (nós da engine) | `node_damage` 7558, `node_vertex_offset` 7596, `node_vertex_wind` 7626, `node_vertex_wave` 7638, `node_shell_layer` 7653, `node_fur_shells` 7668, `node_outline` 7688, `node_billboard` 7699, `node_strands_info` 7726, `node_explode` 7734, `node_planar_reflection` 7757 |
