# Mapa de código — desenho da viewport 3D (`view3d_draw.c`)

Índice de `view3d_draw.c`: grade, cursor, bordas de câmera, profundidade e seleção, sombras na viewport,
offscreen, overlays e o aquecimento de shaders. Não descreve arquitetura.

**Linhas conferidas em 2026-10-23 (`HEAD` `d1f20408`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Regra da casa: não mudar o shading dos meshes na viewport; ajustes visuais vão nos overlays.

## `source/source/blender/editors/space_view3d/view3d_draw.c` (5.391 linhas)

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
| Lâmpadas e sombras (CSM) | `gpu_render_lamp_update` 2913, `view3d_compute_cascade_shadow_matrix` 2952, `gpu_update_lamps_shadows_world` 3033 |
| Matrizes e objetos | `ED_view3d_update_viewmat` 3278, **`view3d_draw_objects`** 3361, `view3d_main_region_setup_view` 3564, `view3d_main_region_clear` 3628 |
| Offscreen (render OpenGL, thumbnails) | `ED_view3d_draw_offscreen` 3709, `ED_view3d_draw_offscreen_imbuf` 3861 |
| FPS e engine de render | `ED_scene_draw_fps` 4104, `view3d_main_region_draw_engine` 4206 |
| Estéreo e LOD | `view3d_stereo3d_setup` 4343, `update_lods` 4411 |
| Região principal | `view3d_main_region_draw_objects` 4438, `draw_paint_hints` 4684 (dicas de pintura), `view3d_main_region_draw_info` 4751, `view3d_draw_floating_controls` 4838, **`view3d_main_region_draw`** 5087 (entrada) |
| Perfil por camada | `view3d_layer_profile_begin` 5015, `view3d_layer_prefetch_materials` 5052 |
| Debug draw | `bl_debug_draw_quad_add` 5158, `bl_debug_draw` 5186 |
| Aquecimento de shaders | `ED_view3d_shader_warmup_reset` 5258, `warmup_job_start` 5280, `view3d_warmup_step` 5293 |
