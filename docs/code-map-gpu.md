# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-10-26 (`HEAD` `1a63417a`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (631 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.705 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.502 linhas)

Structs `GPUMaterial`/`GPULamp` ficam em `gpu_material_intern.h`, compartilhado com os arquivos abaixo.

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 116, `GPU_material_construct_begin` 161, `gpu_material_construct_end` 265 (compila e cria o pass), `GPU_material_free` 543, `gpu_material_add_node` 1276 |
| Instancing e skinning | `GPU_material_use_instancing` 588, `GPU_material_bind_instancing_attrib` 593, `GPU_material_use_skinning` 640, `GPU_material_bind_bone_matrices` 651 |
| Bind por desenho | `GPU_material_update_lamps` 660, `GPU_material_bind` 749, `GPU_material_bind_uniforms` 894 (uniforms por objeto), `GPU_material_unbind` 1027, `GPU_material_load_images` 1054, `GPU_material_set_foliage_reference_position` 1061 |
| SSGI | `GPU_material_ssgi_slot` 1094, `GPU_material_ssgi_disabled_reason` 1110, `GPU_material_ssgi_approximate` 1123, `gpu_ssgi_closure` 1193, `GPU_material_ssgi_outputs` 1250 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1134, `GPU_material_shadow_color_link` 1144, `gpu_material_link_shadow_color` 1157 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1268, `GPU_material_vertex_offset` 1282, `GPU_material_shells` 1292, `GPU_material_outline` 1313, `GPU_material_strands` 1321, `GPU_material_explode` 1332, `GPU_material_planar_reflection` 1348 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1360, `GPU_material_has_error` 1427, `gpu_material_add_script_uniform` 1451, `GPU_material_script_uniform_set` 1464, `GPU_material_node_error` 1520 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1763, `gpu_material_link_display_transform` 1781, `GPU_material_do_color_management` 1795 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1813, `ramp_diffuse_result` 1965, `shade_light_textures` 2112, `shade_one_light` 2231 (≈460 linhas), `material_lights` 2698, `do_material_tex` 2837 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3629, `GPU_shaderesult_set` 3737 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3664, `GPU_horizon_update_color` 3676, `GPU_update_exposure_range` 3698, `GPU_sky_texture_slot` 3707, `GPU_sky_texture_follow_sun` 3721, `do_world_tex` 4225, `gpu_material_old_world` 4371, `GPU_material_world` 4502, `GPU_material_world_prefetch` 4544, `GPU_material_world_env` 4569 |
| Entrada principal e cache | `GPU_blender_material` 4145, `GPU_material_matcap` 4182, **`GPU_material_from_blender`** 4675, `GPU_material_prefetch` 4781, `GPU_material_moves_vertices` 4854, `GPU_materials_free_text` 4878, `GPU_materials_free` 4894 |
| Lâmpadas | `GPU_lamp_update` 4943, `GPU_lamp_update_colors` 4996, `gpu_lamp_from_blender` 5027, `GPU_lamp_from_blender` 5375, `GPU_lamp_free` 5515, `GPU_lamp_get_data` 6323 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5173, `gpu_lamp_create_shadow_buffer` 5198, `gpu_lamp_create_cascade` 5280 (CSM), `gpu_lamp_create_point_shadow_buffer` 5328, `GPU_lamp_shadow_set_size` 5570, `gpu_lamp_csm_auto_bias` 5649, `GPU_lamp_shadow_buffer_bind` 5677, `GPU_lamp_shadow_buffer_unbind` 5458, `GPU_lamp_shadow_color_begin` 5768, `GPU_lamp_shadow_static_ensure` 5828 (sombra estática), `GPU_lamp_shadow_static_matches` 5878 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 5969, `GPU_material_bind_probe` 6085, `GPU_material_bind_probe2` 6136, `GPU_material_bind_planar` 6189, `GPU_material_bind_damage` 6243, `GPU_material_bind_scene_lights` 5969 |

## `source/source/blender/gpu/intern/gpu_material_export.c` (330 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Exportação e OpenSubdiv | `GPU_shader_export` 78, `GPU_material_update_fvar_offset` 282 |

## `source/source/blender/gpu/intern/gpu_material_ies.c` (376 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| IES | `ies_parse` 182, `GPU_lamp_ies_slot` 320, `gpu_ies_atlas` 357 |

## `source/source/blender/gpu/intern/gpu_material_intern.h` (277 linhas)

Definições internas de `struct GPUMaterial` e `struct GPULamp` e o protótipo de `gpu_ies_atlas` (usado pelo bind de luzes da cena).

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.668 linhas)

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
| Luz da cena (nós novos) | `scene_light_shadow` 4847, `scene_light_shadow_tint` 4886, `scene_light_ies` 4913, `scene_light_dir` 4925, `scene_light_visibility` 4963 |
| BSDFs | `node_bsdf_diffuse_ambient` 4978, `node_bsdf_diffuse_ambient_ssgi` 4998, `node_bsdf_diffuse` 5035, `node_bsdf_glossy` 5045, `node_bsdf_glass` 5196, `node_bsdf_toon` 5236, `node_bsdf_principled` 5331, `node_bsdf_translucent` 5526, `node_bsdf_hair` 5620, `node_bsdf_refraction` 5756 |
| Lightmap e light volume | `lightmap_sample` 5276, `lightmap_mark_ao` 5286, `lightvol_sample` 5315 |
| Emissão, mix e SSGI | `node_emission` 5787, `node_background` 5818, `node_mix_shader` 5825, `ssgi_blend_closures` 5836, `ssgi_approximate_closure` 5865, `node_fresnel` 5879, `node_layer_weight` 5890 |
| Entradas | `node_attribute` 5924, `node_uvmap` 5931, `node_geometry` 5936, `node_tex_coord` 5956, `node_light_path` 6967, `node_object_info` 7011 |
| Texturas procedurais e imagem | `node_tex_gradient` 6046, `node_tex_checker` 6055, `node_tex_brick` 6112, `node_tex_image` 6162, `node_tex_image_box` 6168, `node_tex_noise` 6423, `node_tex_musgrave` 6636, `node_tex_sky` 6780, `node_tex_voronoi` 6841, `node_tex_wave` 6938 |
| Vetor, volume e saída | `node_bump` 7024, `node_displacement_object` 7055, `node_vector_displacement_tangent` 7067, `node_volume_absorption` 7164, `node_output_material` 7205, `node_output_world` 7210 |
| Parallax e preview | `mtex_parallax` 7215, `parallax_uv_in` 7290, `material_preview_matcap` 7302 |
| Valores por objeto (user) | `user_get_A` 7335, `user_get` 7360, `user_set_material` 7406, `user_set_world` 7441 |
| Vértice e geometria (nós da engine) | `node_damage` 7453, `node_vertex_offset` 7491, `node_vertex_wind` 7521, `node_vertex_wave` 7533, `node_shell_layer` 7548, `node_fur_shells` 7563, `node_outline` 7583, `node_billboard` 7594, `node_strands_info` 7621, `node_explode` 7629, `node_planar_reflection` 7652 |
