# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-10-28 (`HEAD` `ec38b049`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (631 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.726 linhas): monta o GLSL final
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

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.736 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 231 |
| Atributos, coordenadas e mapping | `vcol_attribute` 277, `uv_attribute` 282, `particle_info` 304, `mapping_point` 457, `texco_uv` 1297, `texco_object` 1321 |
| Math, mix e conversores | `math_add` 495 … `math_sqrt` 650, `vec_math_add` 663, `curves_rgb` 752, `mix_blend` 835 … `mix_linear` 1090, `hue_sat` 1128, `separate_rgb` 1143 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1365 … `mtex_value_blend` 1548, `mtex_cube_map` 1757, `mtex_bump_init_objspace` 1862, `mtex_nspace_tangent` 2127 |
| Lâmpada legada | `lamp_visibility_sun` 2150, `lamp_falloff_invlinear` 2178, `shade_diffuse_oren_nayar` 3007, `shade_phong_spec` 3183, `shade_toon_spec` 3255 |
| Mundo, estrelas e céu | `world_paper_view` 2320, `world_stars` 2334, `sky_atmosphere` 2570, `sky_aurora` 2692, `sky_moon` 2716, `do_sky_simple` 2751, `do_sky_atmospheric` 2801, `world_blend_paper_real` 2835 |
| Ambiente e sondas | `env_sky` 3367, `env_irradiance_dir` 3400, `env_brdf_approx` 3430, `env_cube_tex` 3439, `env_probe_sample` 3478, `env_apply` 3573, `probe_cube_tex` 4426 |
| Sombras | `test_shadow_simple` 3721, `test_shadow_pcf` 3810, `test_shadow_vsm` 3916, `shadow_pcf` 3956, `csm_reference_distance` 4061, `csm_debug_tint` 4215, `shadow_fade` 4235, `shadow_color_output` 4256, `shadow_color_tint` 4300, `csm_shadow_color_tint` 4305, `shade_shadow_tint` 4315, `shade_shadow_tint_csm` 4323, `shadow_point` 4788 |
| Névoa, exposição e saída | `shade_exposure_correct` 4461, `shade_mist_factor` 4491, `shade_alpha_opaque` 4532, `shade_gbuffer0` 4544 |
| Luz da cena (nós novos) | `scene_light_shadow` 4894, `scene_light_shadow_tint` 4954, `scene_light_ies` 4981, `scene_light_dir` 4993, `scene_light_visibility` 5031 |
| BSDFs | `node_bsdf_diffuse_ambient` 5046, `node_bsdf_diffuse_ambient_ssgi` 5066, `node_bsdf_diffuse` 5103, `node_bsdf_glossy` 5113, `node_bsdf_glass` 5264, `node_bsdf_toon` 5304, `node_bsdf_principled` 5399, `node_bsdf_translucent` 5594, `node_bsdf_hair` 5688, `node_bsdf_refraction` 5824 |
| Lightmap e light volume | `lightmap_sample` 5344, `lightmap_mark_ao` 5354, `lightvol_sample` 5383 |
| Emissão, mix e SSGI | `node_emission` 5855, `node_background` 5886, `node_mix_shader` 5893, `ssgi_blend_closures` 5904, `ssgi_approximate_closure` 5933, `node_fresnel` 5947, `node_layer_weight` 5958 |
| Entradas | `node_attribute` 5992, `node_uvmap` 5999, `node_geometry` 6004, `node_tex_coord` 6024, `node_light_path` 7035, `node_object_info` 7079 |
| Texturas procedurais e imagem | `node_tex_gradient` 6114, `node_tex_checker` 6123, `node_tex_brick` 6180, `node_tex_image` 6230, `node_tex_image_box` 6236, `node_tex_noise` 6491, `node_tex_musgrave` 6704, `node_tex_sky` 6848, `node_tex_voronoi` 6909, `node_tex_wave` 7006 |
| Vetor, volume e saída | `node_bump` 7092, `node_displacement_object` 7123, `node_vector_displacement_tangent` 7135, `node_volume_absorption` 7232, `node_output_material` 7273, `node_output_world` 7278 |
| Parallax e preview | `mtex_parallax` 7283, `parallax_uv_in` 7358, `material_preview_matcap` 7370 |
| Valores por objeto (user) | `user_get_A` 7403, `user_get` 7428, `user_set_material` 7474, `user_set_world` 7509 |
| Vértice e geometria (nós da engine) | `node_damage` 7521, `node_vertex_offset` 7559, `node_vertex_wind` 7589, `node_vertex_wave` 7601, `node_shell_layer` 7616, `node_fur_shells` 7631, `node_outline` 7651, `node_billboard` 7662, `node_strands_info` 7689, `node_explode` 7697, `node_planar_reflection` 7720 |
