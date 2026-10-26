# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-10-26 (`HEAD` `37e1fccf`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (631 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.720 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.620 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 146, `GPU_material_construct_begin` 191, `gpu_material_construct_end` 295 (compila e cria o pass), `GPU_material_free` 585, `gpu_material_add_node` 1318 |
| Instancing e skinning | `GPU_material_use_instancing` 630, `GPU_material_bind_instancing_attrib` 635, `GPU_material_use_skinning` 682, `GPU_material_bind_bone_matrices` 693 |
| Bind por desenho | `GPU_material_update_lamps` 702, `GPU_material_bind` 791, `GPU_material_bind_uniforms` 936 (uniforms por objeto), `GPU_material_unbind` 1069, `GPU_material_load_images` 1096, `GPU_material_set_foliage_reference_position` 1103 |
| SSGI | `GPU_material_ssgi_slot` 1136, `GPU_material_ssgi_disabled_reason` 1152, `GPU_material_ssgi_approximate` 1165, `gpu_ssgi_closure` 1235, `GPU_material_ssgi_outputs` 1292 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1176, `GPU_material_shadow_color_link` 1186, `gpu_material_link_shadow_color` 1199 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1310, `GPU_material_vertex_offset` 1324, `GPU_material_shells` 1334, `GPU_material_outline` 1355, `GPU_material_strands` 1363, `GPU_material_explode` 1374, `GPU_material_planar_reflection` 1390 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1402, `GPU_material_has_error` 1469, `gpu_material_add_script_uniform` 1493, `GPU_material_script_uniform_set` 1506, `GPU_material_node_error` 1562 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1805, `gpu_material_link_display_transform` 1823, `GPU_material_do_color_management` 1837 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1855, `ramp_diffuse_result` 2007, `shade_light_textures` 2154, `shade_one_light` 2273 (≈460 linhas), `material_lights` 2741, `do_material_tex` 2880 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3672, `GPU_shaderesult_set` 3780 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3707, `GPU_horizon_update_color` 3719, `GPU_update_exposure_range` 3741, `GPU_sky_texture_slot` 3750, `GPU_sky_texture_follow_sun` 3764, `do_world_tex` 4268, `gpu_material_old_world` 4414, `GPU_material_world` 4545, `GPU_material_world_prefetch` 4587, `GPU_material_world_env` 4612 |
| Entrada principal e cache | `GPU_blender_material` 4188, `GPU_material_matcap` 4225, **`GPU_material_from_blender`** 4718, `GPU_material_prefetch` 4824, `GPU_material_moves_vertices` 4897, `GPU_materials_free_text` 4921, `GPU_materials_free` 4937 |
| Lâmpadas | `GPU_lamp_update` 4986, `GPU_lamp_update_colors` 5039, `gpu_lamp_from_blender` 5070, `GPU_lamp_from_blender` 5418, `GPU_lamp_free` 5567, `GPU_lamp_get_data` 6440 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5216, `gpu_lamp_create_shadow_buffer` 5241, `gpu_lamp_create_cascade` 5323 (CSM), `gpu_lamp_create_point_shadow_buffer` 5371, `GPU_lamp_shadow_set_size` 5624, `gpu_lamp_csm_auto_bias` 5703, `GPU_lamp_shadow_buffer_bind` 5731, `GPU_lamp_shadow_buffer_unbind` 5510, `GPU_lamp_shadow_color_begin` 5822, `GPU_lamp_shadow_static_ensure` 5882 (sombra estática), `GPU_lamp_shadow_static_matches` 5932 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 6023, `GPU_material_bind_probe` 6202, `GPU_material_bind_probe2` 6253, `GPU_material_bind_planar` 6306, `GPU_material_bind_damage` 6360, `GPU_material_bind_scene_lights` 6023 |

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

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.712 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 231 |
| Atributos, coordenadas e mapping | `vcol_attribute` 277, `uv_attribute` 282, `particle_info` 304, `mapping_point` 457, `texco_uv` 1297, `texco_object` 1321 |
| Math, mix e conversores | `math_add` 495 … `math_sqrt` 650, `vec_math_add` 663, `curves_rgb` 752, `mix_blend` 835 … `mix_linear` 1090, `hue_sat` 1128, `separate_rgb` 1143 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1365 … `mtex_value_blend` 1548, `mtex_cube_map` 1757, `mtex_bump_init_objspace` 1862, `mtex_nspace_tangent` 2127 |
| Lâmpada legada | `lamp_visibility_sun` 2150, `lamp_falloff_invlinear` 2178, `shade_diffuse_oren_nayar` 2983, `shade_phong_spec` 3159, `shade_toon_spec` 3231 |
| Mundo, estrelas e céu | `world_paper_view` 2320, `world_stars` 2334, `sky_atmosphere` 2548, `sky_aurora` 2670, `sky_moon` 2694, `do_sky_simple` 2729, `do_sky_atmospheric` 2778, `world_blend_paper_real` 2811 |
| Ambiente e sondas | `env_sky` 3343, `env_irradiance_dir` 3376, `env_brdf_approx` 3406, `env_cube_tex` 3415, `env_probe_sample` 3454, `env_apply` 3549, `probe_cube_tex` 4402 |
| Sombras | `test_shadow_simple` 3697, `test_shadow_pcf` 3786, `test_shadow_vsm` 3892, `shadow_pcf` 3932, `csm_reference_distance` 4037, `csm_debug_tint` 4191, `shadow_fade` 4211, `shadow_color_output` 4232, `shadow_color_tint` 4276, `csm_shadow_color_tint` 4281, `shade_shadow_tint` 4291, `shade_shadow_tint_csm` 4299, `shadow_point` 4764 |
| Névoa, exposição e saída | `shade_exposure_correct` 4437, `shade_mist_factor` 4467, `shade_alpha_opaque` 4508, `shade_gbuffer0` 4520 |
| Luz da cena (nós novos) | `scene_light_shadow` 4870, `scene_light_shadow_tint` 4930, `scene_light_ies` 4957, `scene_light_dir` 4969, `scene_light_visibility` 5007 |
| BSDFs | `node_bsdf_diffuse_ambient` 5022, `node_bsdf_diffuse_ambient_ssgi` 5042, `node_bsdf_diffuse` 5079, `node_bsdf_glossy` 5089, `node_bsdf_glass` 5240, `node_bsdf_toon` 5280, `node_bsdf_principled` 5375, `node_bsdf_translucent` 5570, `node_bsdf_hair` 5664, `node_bsdf_refraction` 5800 |
| Lightmap e light volume | `lightmap_sample` 5320, `lightmap_mark_ao` 5330, `lightvol_sample` 5359 |
| Emissão, mix e SSGI | `node_emission` 5831, `node_background` 5862, `node_mix_shader` 5869, `ssgi_blend_closures` 5880, `ssgi_approximate_closure` 5909, `node_fresnel` 5923, `node_layer_weight` 5934 |
| Entradas | `node_attribute` 5968, `node_uvmap` 5975, `node_geometry` 5980, `node_tex_coord` 6000, `node_light_path` 7011, `node_object_info` 7055 |
| Texturas procedurais e imagem | `node_tex_gradient` 6090, `node_tex_checker` 6099, `node_tex_brick` 6156, `node_tex_image` 6206, `node_tex_image_box` 6212, `node_tex_noise` 6467, `node_tex_musgrave` 6680, `node_tex_sky` 6824, `node_tex_voronoi` 6885, `node_tex_wave` 6982 |
| Vetor, volume e saída | `node_bump` 7068, `node_displacement_object` 7099, `node_vector_displacement_tangent` 7111, `node_volume_absorption` 7208, `node_output_material` 7249, `node_output_world` 7254 |
| Parallax e preview | `mtex_parallax` 7259, `parallax_uv_in` 7334, `material_preview_matcap` 7346 |
| Valores por objeto (user) | `user_get_A` 7379, `user_get` 7404, `user_set_material` 7450, `user_set_world` 7485 |
| Vértice e geometria (nós da engine) | `node_damage` 7497, `node_vertex_offset` 7535, `node_vertex_wind` 7565, `node_vertex_wave` 7577, `node_shell_layer` 7592, `node_fur_shells` 7607, `node_outline` 7627, `node_billboard` 7638, `node_strands_info` 7665, `node_explode` 7673, `node_planar_reflection` 7696 |
