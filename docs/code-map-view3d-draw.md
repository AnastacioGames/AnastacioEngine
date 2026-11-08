# Mapa de código — desenho da viewport 3D (`view3d_draw.c`)

Índice de `view3d_draw.c` e dos arquivos separados dele (`view3d_draw_shadows.c`, `view3d_draw_warmup.c`): grade, cursor, bordas de câmera, profundidade e seleção, sombras na viewport,
offscreen, overlays e o aquecimento de shaders. Não descreve arquitetura.

**Linhas conferidas em 2026-11-08 (`HEAD` `fa834071`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Regra da casa: não mudar o shading dos meshes na viewport; ajustes visuais vão nos overlays.

## `source/source/blender/editors/space_view3d/view3d_draw.c` (4.850 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Clipping | `view3d_draw_clipping` 164, `ED_view3d_clipping_set` 192, `ED_view3d_clipping_test` 236 |
| Grade, chão e cursor | `drawgrid` 282, `ED_view3d_grid_scale` 478, `drawfloor_shader` 574, `drawfloor` 651, `drawcursor` 763 |
| Eixos e textos | `draw_view_axis` 865, `draw_rotation_guide` 967, `draw_viewport_name` 1163, `draw_selected_name` 1219 |
| Borda da câmera | `ED_view3d_calc_camera_border` 1376, `drawviewborder` 1454 |
| Backbuffer (seleção por cor) | `backdrawview3d` 1678, `ED_view3d_backbuf_sample` 1838, `ED_view3d_backbuf_read` 1859 |
| Imagens de fundo | `view3d_draw_bgpic` 2005 |
| Transparência e X-ray | `view3d_draw_transp` 2328, `view3d_draw_xray` 2346 |
| Dupli | `draw_dupli_objects_color` 2445, `draw_dupli_objects` 2606 |
| Profundidade e seleção | `ED_view3d_depth_update` 2677, `view3d_draw_depth_loop` 2750, `ED_view3d_draw_depth` 2832, `ED_view3d_draw_select_loop` 2882 |
| Matrizes e objetos | `ED_view3d_update_viewmat` 2981, **`view3d_draw_objects`** 3064, `view3d_main_region_setup_view` 3267, `view3d_main_region_clear` 3331 |
| Offscreen (render OpenGL, thumbnails) | `ED_view3d_draw_offscreen` 3412, `ED_view3d_draw_offscreen_imbuf` 3564 |
| FPS e engine de render | `ED_scene_draw_fps` 3807, `view3d_main_region_draw_engine` 3909 |
| Estéreo e LOD | `view3d_stereo3d_setup` 4046, `update_lods` 4114 |
| Região principal | `view3d_main_region_draw_objects` 4140, `draw_paint_hints` 4386 (dicas de pintura), `view3d_main_region_draw_info` 4453, `view3d_draw_floating_controls` 4544, **`view3d_main_region_draw`** 4707 (entrada) |
| Debug draw | `bl_debug_draw_quad_add` 4773, `bl_debug_draw` 4801 |

## `source/source/blender/editors/space_view3d/view3d_draw_shadows.c` (442 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Lâmpadas e sombras (CSM) | `gpu_render_lamp_update` 123, `view3d_compute_cascade_shadow_matrix` 166, `gpu_update_lamps_shadows_world` 247 |

## `source/source/blender/editors/space_view3d/view3d_draw_warmup.c` (369 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Perfil por camada | `view3d_layer_profile_begin` 125, `view3d_layer_prefetch_materials` 162, `view3d_layer_profile_draw_begin` 198, `view3d_layer_profile_draw_end` 204 |
| Aquecimento de shaders | `ED_view3d_shader_warmup_reset` 236, `warmup_job_start` 258, `view3d_warmup_step` 271 |
