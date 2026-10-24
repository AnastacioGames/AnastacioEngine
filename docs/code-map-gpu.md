# Mapa de código — materiais e shaders da GPU

Guia de navegação para os arquivos de material e shader da GPU, que mais mudam junto com o visual da
engine (sombra, céu, Filmic, SSGI, nós de shader, sondas, lightmap). Não descreve arquitetura; é só um
índice para achar a função certa sem ler 7 mil linhas.

**Linhas conferidas em 2026-10-23 (`HEAD` `6960d5e7`).** Os números envelhecem a cada edição: use-os como
ponto de partida e confirme com `grep -n "nome_da_funcao" arquivo`. `python tools/check_docs.py --fix`
corrige os números deste mapa.

Arquivos vizinhos:

- [`GPU_material.h`](../source/source/blender/gpu/GPU_material.h) (628 linhas): API pública. Enums
  `GPUBuiltin` e `GPUDynamicType` (uniforms dinâmicos), `GPUShadeInput`/`GPUShadeResult`.
- [`gpu_codegen.c`](../source/source/blender/gpu/intern/gpu_codegen.c) (3.702 linhas): monta o GLSL final
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

## `source/source/blender/gpu/intern/gpu_material.c` (6.996 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Construção do material | `GPU_material_builtin` 355, `GPU_material_construct_begin` 400, `gpu_material_construct_end` 460 (compila e cria o pass), `GPU_material_free` 723, `gpu_material_add_node` 1456 |
| Instancing e skinning | `GPU_material_use_instancing` 768, `GPU_material_bind_instancing_attrib` 773, `GPU_material_use_skinning` 820, `GPU_material_bind_bone_matrices` 831 |
| Bind por desenho | `GPU_material_update_lamps` 840, `GPU_material_bind` 929, `GPU_material_bind_uniforms` 1074 (uniforms por objeto), `GPU_material_unbind` 1207, `GPU_material_load_images` 1234, `GPU_material_set_foliage_reference_position` 1241 |
| SSGI | `GPU_material_ssgi_slot` 1274, `GPU_material_ssgi_disabled_reason` 1290, `GPU_material_ssgi_approximate` 1303, `gpu_ssgi_closure` 1373, `GPU_material_ssgi_outputs` 1430 |
| Passe de sombra (lado material) | `GPU_shadow_depth_pass_set` 1314, `GPU_material_shadow_color_link` 1324, `gpu_material_link_shadow_color` 1337 |
| Alpha e efeitos de geometria | `GPU_material_alpha_blend` 1448, `GPU_material_vertex_offset` 1462, `GPU_material_shells` 1472, `GPU_material_outline` 1493, `GPU_material_strands` 1501, `GPU_material_explode` 1512, `GPU_material_planar_reflection` 1528 |
| GLSL Script e erros de nó | `gpu_material_add_script` 1540, `GPU_material_has_error` 1607, `gpu_material_add_script_uniform` 1631, `GPU_material_script_uniform_set` 1644, `GPU_material_node_error` 1700 |
| Color management (Filmic) | `gpu_view_transform_contrast` 1745, `gpu_material_link_display_transform` 1763, `GPU_material_do_color_management` 1777 |
| Shading legado (Blender Internal) | `lamp_get_visibility` 1795, `ramp_diffuse_result` 1947, `shade_light_textures` 2094, `shade_one_light` 2213 (≈460 linhas), `material_lights` 2676, `do_material_tex` 2815 (≈790 linhas, texturas mtex), `GPU_shadeinput_set` 3607, `GPU_shaderesult_set` 3715 |
| Mundo, céu e névoa | `GPU_mist_update_values` 3642, `GPU_horizon_update_color` 3654, `GPU_update_exposure_range` 3676, `GPU_sky_texture_slot` 3685, `GPU_sky_texture_follow_sun` 3699, `do_world_tex` 4200, `gpu_material_old_world` 4346, `GPU_material_world` 4477, `GPU_material_world_prefetch` 4519, `GPU_material_world_env` 4544 |
| Entrada principal e cache | `GPU_blender_material` 4120, `GPU_material_matcap` 4157, **`GPU_material_from_blender`** 4647, `GPU_material_prefetch` 4753, `GPU_material_moves_vertices` 4826, `GPU_materials_free_text` 4850, `GPU_materials_free` 4866 |
| Lâmpadas | `GPU_lamp_update` 4915, `GPU_lamp_update_colors` 4968, `gpu_lamp_from_blender` 4999, `GPU_lamp_from_blender` 5347, `GPU_lamp_free` 5487, `GPU_lamp_get_data` 6274 |
| Lâmpadas e sombras | `gpu_lamp_shadow_color_create` 5145, `gpu_lamp_create_shadow_buffer` 5170, `gpu_lamp_create_cascade` 5252 (CSM), `gpu_lamp_create_point_shadow_buffer` 5300, `GPU_lamp_shadow_set_size` 5542, `gpu_lamp_csm_auto_bias` 5621, `GPU_lamp_shadow_buffer_bind` 5649, `GPU_lamp_shadow_buffer_unbind` 5714, `GPU_lamp_shadow_color_begin` 5740, `GPU_lamp_shadow_static_ensure` 5800 (sombra estática), `GPU_lamp_shadow_static_matches` 5850 |
| Bind de lâmpadas, sondas e dano | `GPU_material_bind_shadow_lamps` 5952, `GPU_material_bind_probe` 6045, `GPU_material_bind_probe2` 6091, `GPU_material_bind_planar` 6139, `GPU_material_bind_damage` 6193, `GPU_material_bind_scene_lights` 6219 |
| Exportação e OpenSubdiv | `GPU_shader_export` 6441, `GPU_material_update_fvar_offset` 6645 |
| IES | `ies_parse` 6802, `GPU_lamp_ies_slot` 6940, `gpu_ies_atlas` 6977 |

## `source/source/blender/gpu/shaders/gpu_shader_material.glsl` (7.449 linhas)

Funções GLSL chamadas pelos nós via `GPU_stack_link`/`GPU_link`. Nomes com o mesmo prefixo ficam juntos.

| Domínio | Funções (linha inicial) |
|---|---|
| Cor e Filmic | `rgb_to_hsv` 85, `srgb_to_linearrgb` 156, `game_filmic_curve` 192, `game_view_transform` 202, `game_view_untransform` 231 |
| Atributos, coordenadas e mapping | `vcol_attribute` 277, `uv_attribute` 282, `particle_info` 304, `mapping_point` 457, `texco_uv` 1297, `texco_object` 1321 |
| Math, mix e conversores | `math_add` 495 … `math_sqrt` 650, `vec_math_add` 663, `curves_rgb` 752, `mix_blend` 835 … `mix_linear` 1090, `hue_sat` 1128, `separate_rgb` 1143 |
| Texturas legadas (mtex) | `mtex_rgb_blend` 1365 … `mtex_value_blend` 1548, `mtex_cube_map` 1757, `mtex_bump_init_objspace` 1862, `mtex_nspace_tangent` 2111 |
| Lâmpada legada | `lamp_visibility_sun` 2137, `lamp_falloff_invlinear` 2165, `shade_diffuse_oren_nayar` 2900, `shade_phong_spec` 3076, `shade_toon_spec` 3148 |
| Mundo, estrelas e céu | `world_paper_view` 2307, `world_stars` 2321, `sky_atmosphere` 2498, `sky_aurora` 2600, `sky_moon` 2624, `do_sky_simple` 2659, `do_sky_atmospheric` 2708, `world_blend_paper_real` 2741 |
| Ambiente e sondas | `env_sky` 3259, `env_irradiance_dir` 3288, `env_brdf_approx` 3301, `env_cube_tex` 3310, `env_probe_sample` 3345, `env_apply` 3428, `probe_cube_tex` 4207 |
| Sombras | `test_shadow_simple` 3577, `test_shadow_pcf` 3677, `test_shadow_vsm` 3716, `shadow_pcf` 3756, `csm_reference_distance` 3860, `csm_debug_tint` 3996, `shadow_fade` 4016, `shadow_color_output` 4037, `shadow_color_tint` 4081, `csm_shadow_color_tint` 4086, `shade_shadow_tint` 4096, `shade_shadow_tint_csm` 4104, `shadow_point` 4567 |
| Névoa, exposição e saída | `shade_exposure_correct` 4242, `shade_mist_factor` 4272, `shade_alpha_opaque` 4313, `shade_gbuffer0` 4325 |
| Luz da cena (nós novos) | `scene_light_shadow` 4628, `scene_light_shadow_tint` 4667, `scene_light_ies` 4694, `scene_light_dir` 4706, `scene_light_visibility` 4744 |
| BSDFs | `node_bsdf_diffuse_ambient` 4759, `node_bsdf_diffuse_ambient_ssgi` 4779, `node_bsdf_diffuse` 4816, `node_bsdf_glossy` 4826, `node_bsdf_glass` 4976, `node_bsdf_toon` 5016, `node_bsdf_principled` 5111, `node_bsdf_translucent` 5304, `node_bsdf_hair` 5398, `node_bsdf_refraction` 5534 |
| Lightmap e light volume | `lightmap_sample` 5056, `lightmap_mark_ao` 5066, `lightvol_sample` 5095 |
| Emissão, mix e SSGI | `node_emission` 5565, `node_background` 5596, `node_mix_shader` 5603, `ssgi_blend_closures` 5614, `ssgi_approximate_closure` 5643, `node_fresnel` 5657, `node_layer_weight` 5668 |
| Entradas | `node_attribute` 5702, `node_uvmap` 5709, `node_geometry` 5714, `node_tex_coord` 5734, `node_light_path` 6745, `node_object_info` 6789 |
| Texturas procedurais e imagem | `node_tex_gradient` 5824, `node_tex_checker` 5833, `node_tex_brick` 5890, `node_tex_image` 5940, `node_tex_image_box` 5946, `node_tex_noise` 6201, `node_tex_musgrave` 6414, `node_tex_sky` 6558, `node_tex_voronoi` 6619, `node_tex_wave` 6716 |
| Vetor, volume e saída | `node_bump` 6805, `node_displacement_object` 6836, `node_vector_displacement_tangent` 6848, `node_volume_absorption` 6945, `node_output_material` 6986, `node_output_world` 6991 |
| Parallax e preview | `mtex_parallax` 6996, `parallax_uv_in` 7071, `material_preview_matcap` 7083 |
| Valores por objeto (user) | `user_get_A` 7116, `user_get` 7141, `user_set_material` 7187, `user_set_world` 7222 |
| Vértice e geometria (nós da engine) | `node_damage` 7234, `node_vertex_offset` 7272, `node_vertex_wind` 7302, `node_vertex_wave` 7314, `node_shell_layer` 7329, `node_fur_shells` 7344, `node_outline` 7364, `node_billboard` 7375, `node_strands_info` 7402, `node_explode` 7410, `node_planar_reflection` 7433 |
