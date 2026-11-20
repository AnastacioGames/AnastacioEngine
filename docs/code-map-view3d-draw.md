# Mapa de código — desenho da viewport 3D (`view3d_draw.c`)

Índice de `view3d_draw.c` e dos arquivos separados dele (`view3d_draw_shadows.c`, `view3d_draw_warmup.c`): grade, cursor, bordas de câmera, profundidade e seleção, sombras na viewport,
offscreen, overlays e o aquecimento de shaders. Não descreve arquitetura.

**Linhas conferidas em 2026-11-20 (`HEAD` `d09c51a4`).** Os números envelhecem a cada edição: confirme com
`grep -n "nome" arquivo`. `python tools/check_docs.py --fix` corrige os números deste mapa.

Regra da casa: não mudar o shading dos meshes na viewport; ajustes visuais vão nos overlays.

## `source/source/blender/editors/space_view3d/view3d_draw.c` (5.879 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Clipping | `view3d_draw_clipping` 174, `ED_view3d_clipping_set` 202, `ED_view3d_clipping_test` 246 |
| Grade, chão e cursor | `drawgrid` 292, `ED_view3d_grid_scale` 488, `drawfloor_shader` 589, `drawfloor` 666, `drawcursor` 778 |
| Eixos e textos | `draw_view_axis` 880, `draw_rotation_guide` 982, `draw_viewport_name` 1178, `draw_selected_name` 1234 |
| Borda da câmera | `ED_view3d_calc_camera_border` 1391, `drawviewborder` 1469 |
| Backbuffer (seleção por cor) | `backdrawview3d` 1693, `ED_view3d_backbuf_sample` 1853, `ED_view3d_backbuf_read` 1874 |
| Imagens de fundo | `view3d_draw_bgpic` 2020 |
| Transparência e X-ray | `view3d_draw_transp` 2343, `view3d_draw_xray` 2361 |
| Dupli | `draw_dupli_objects_color` 2493, `draw_dupli_objects` 2654 |
| Profundidade e seleção | `ED_view3d_depth_update` 2725, `view3d_draw_depth_loop` 2798, `ED_view3d_draw_depth` 2880, `ED_view3d_draw_select_loop` 2930 |
| Matrizes e objetos | `ED_view3d_update_viewmat` 3029, **`view3d_draw_objects`** 3112, `view3d_main_region_setup_view` 3327, `view3d_main_region_clear` 3391 |
| Offscreen (render OpenGL, thumbnails) | `ED_view3d_draw_offscreen` 4273, `ED_view3d_draw_offscreen_imbuf` 4427 |
| FPS e engine de render | `ED_scene_draw_fps` 4670, `view3d_main_region_draw_engine` 4772 |
| Estéreo e LOD | `view3d_stereo3d_setup` 4909, `update_lods` 4977 |
| Região principal | `view3d_main_region_draw_objects` 5003, `draw_paint_hints` 5270 (dicas de pintura), `view3d_main_region_draw_info` 5337, `view3d_draw_floating_controls` 5428, **`view3d_main_region_draw`** 5734 (entrada) |
| Debug draw | `bl_debug_draw_quad_add` 5802, `bl_debug_draw` 5830 |

## `source/source/blender/editors/space_view3d/view3d_draw_shadows.c` (520 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Lâmpadas e sombras (CSM) | `gpu_render_lamp_update` 123, `view3d_compute_cascade_shadow_matrix` 170, `gpu_update_lamps_shadows_world` 299 |

## `source/source/blender/editors/space_view3d/view3d_draw_warmup.c` (369 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Perfil por camada | `view3d_layer_profile_begin` 125, `view3d_layer_prefetch_materials` 162, `view3d_layer_profile_draw_begin` 198, `view3d_layer_profile_draw_end` 204 |
| Aquecimento de shaders | `ED_view3d_shader_warmup_reset` 236, `warmup_job_start` 258, `view3d_warmup_step` 271 |
