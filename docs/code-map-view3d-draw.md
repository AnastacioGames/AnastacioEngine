# Mapa de código — desenho da viewport 3D (`view3d_draw.c`)

Índice de `view3d_draw.c` e dos arquivos separados dele (`view3d_draw_shadows.c`, `view3d_draw_warmup.c`): grade, cursor, bordas de câmera, profundidade e seleção, sombras na viewport,
offscreen, overlays e o aquecimento de shaders. Não descreve arquitetura.

**Linhas conferidas em 2026-10-23 (`HEAD` `7a93da6c`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Regra da casa: não mudar o shading dos meshes na viewport; ajustes visuais vão nos overlays.

## `source/source/blender/editors/space_view3d/view3d_draw.c` (4.822 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Clipping | `view3d_draw_clipping` 163, `ED_view3d_clipping_set` 191, `ED_view3d_clipping_test` 235 |
| Grade, chão e cursor | `drawgrid` 281, `ED_view3d_grid_scale` 477, `drawfloor_shader` 573, `drawfloor` 650, `drawcursor` 762 |
| Eixos e textos | `draw_view_axis` 864, `draw_rotation_guide` 965, `draw_viewport_name` 1161, `draw_selected_name` 1191 |
| Borda da câmera | `ED_view3d_calc_camera_border` 1348, `drawviewborder` 1426 |
| Backbuffer (seleção por cor) | `backdrawview3d` 1650, `ED_view3d_backbuf_sample` 1810, `ED_view3d_backbuf_read` 1831 |
| Imagens de fundo | `view3d_draw_bgpic` 1977 |
| Transparência e X-ray | `view3d_draw_transp` 2300, `view3d_draw_xray` 2318 |
| Dupli | `draw_dupli_objects_color` 2417, `draw_dupli_objects` 2578 |
| Profundidade e seleção | `ED_view3d_depth_update` 2649, `view3d_draw_depth_loop` 2722, `ED_view3d_draw_depth` 2804, `ED_view3d_draw_select_loop` 2854 |
| Matrizes e objetos | `ED_view3d_update_viewmat` 2953, **`view3d_draw_objects`** 3036, `view3d_main_region_setup_view` 3239, `view3d_main_region_clear` 3303 |
| Offscreen (render OpenGL, thumbnails) | `ED_view3d_draw_offscreen` 3384, `ED_view3d_draw_offscreen_imbuf` 3536 |
| FPS e engine de render | `ED_scene_draw_fps` 3779, `view3d_main_region_draw_engine` 3881 |
| Estéreo e LOD | `view3d_stereo3d_setup` 4018, `update_lods` 4086 |
| Região principal | `view3d_main_region_draw_objects` 4112, `draw_paint_hints` 4358 (dicas de pintura), `view3d_main_region_draw_info` 4425, `view3d_draw_floating_controls` 4512, **`view3d_main_region_draw`** 4679 (entrada) |
| Debug draw | `bl_debug_draw_quad_add` 4745, `bl_debug_draw` 4773 |

## `source/source/blender/editors/space_view3d/view3d_draw_shadows.c` (438 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Lâmpadas e sombras (CSM) | `gpu_render_lamp_update` 123, `view3d_compute_cascade_shadow_matrix` 162, `gpu_update_lamps_shadows_world` 243 |

## `source/source/blender/editors/space_view3d/view3d_draw_warmup.c` (369 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Perfil por camada | `view3d_layer_profile_begin` 125, `view3d_layer_prefetch_materials` 162, `view3d_layer_profile_draw_begin` 198, `view3d_layer_profile_draw_end` 204 |
| Aquecimento de shaders | `ED_view3d_shader_warmup_reset` 236, `warmup_job_start` 258, `view3d_warmup_step` 271 |
