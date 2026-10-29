# Mapa de código — desenho da viewport 3D (`view3d_draw.c`)

Índice de `view3d_draw.c` e dos arquivos separados dele (`view3d_draw_shadows.c`, `view3d_draw_warmup.c`): grade, cursor, bordas de câmera, profundidade e seleção, sombras na viewport,
offscreen, overlays e o aquecimento de shaders. Não descreve arquitetura.

**Linhas conferidas em 2026-10-29 (`HEAD` `2976bd78`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Regra da casa: não mudar o shading dos meshes na viewport; ajustes visuais vão nos overlays.

## `source/source/blender/editors/space_view3d/view3d_draw.c` (4.843 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Clipping | `view3d_draw_clipping` 164, `ED_view3d_clipping_set` 192, `ED_view3d_clipping_test` 236 |
| Grade, chão e cursor | `drawgrid` 282, `ED_view3d_grid_scale` 478, `drawfloor_shader` 574, `drawfloor` 651, `drawcursor` 763 |
| Eixos e textos | `draw_view_axis` 865, `draw_rotation_guide` 966, `draw_viewport_name` 1162, `draw_selected_name` 1218 |
| Borda da câmera | `ED_view3d_calc_camera_border` 1375, `drawviewborder` 1453 |
| Backbuffer (seleção por cor) | `backdrawview3d` 1677, `ED_view3d_backbuf_sample` 1837, `ED_view3d_backbuf_read` 1858 |
| Imagens de fundo | `view3d_draw_bgpic` 2004 |
| Transparência e X-ray | `view3d_draw_transp` 2327, `view3d_draw_xray` 2345 |
| Dupli | `draw_dupli_objects_color` 2444, `draw_dupli_objects` 2605 |
| Profundidade e seleção | `ED_view3d_depth_update` 2676, `view3d_draw_depth_loop` 2749, `ED_view3d_draw_depth` 2831, `ED_view3d_draw_select_loop` 2881 |
| Matrizes e objetos | `ED_view3d_update_viewmat` 2980, **`view3d_draw_objects`** 3063, `view3d_main_region_setup_view` 3266, `view3d_main_region_clear` 3330 |
| Offscreen (render OpenGL, thumbnails) | `ED_view3d_draw_offscreen` 3411, `ED_view3d_draw_offscreen_imbuf` 3563 |
| FPS e engine de render | `ED_scene_draw_fps` 3806, `view3d_main_region_draw_engine` 3908 |
| Estéreo e LOD | `view3d_stereo3d_setup` 4045, `update_lods` 4113 |
| Região principal | `view3d_main_region_draw_objects` 4139, `draw_paint_hints` 4385 (dicas de pintura), `view3d_main_region_draw_info` 4452, `view3d_draw_floating_controls` 4543, **`view3d_main_region_draw`** 4700 (entrada) |
| Debug draw | `bl_debug_draw_quad_add` 4766, `bl_debug_draw` 4794 |

## `source/source/blender/editors/space_view3d/view3d_draw_shadows.c` (438 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Lâmpadas e sombras (CSM) | `gpu_render_lamp_update` 123, `view3d_compute_cascade_shadow_matrix` 162, `gpu_update_lamps_shadows_world` 243 |

## `source/source/blender/editors/space_view3d/view3d_draw_warmup.c` (369 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Perfil por camada | `view3d_layer_profile_begin` 125, `view3d_layer_prefetch_materials` 162, `view3d_layer_profile_draw_begin` 198, `view3d_layer_profile_draw_end` 204 |
| Aquecimento de shaders | `ED_view3d_shader_warmup_reset` 236, `warmup_job_start` 258, `view3d_warmup_step` 271 |
