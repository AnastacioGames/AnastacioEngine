# Plano: menus da barra da 3D View no estilo Blender 5

Data: 2026-10-25. Continuação da barra B5 (até 4532c2ce).

Regra: aparência e organização do Blender 5, **conteúdo voltado ao jogo**.
O Blender 5 é ferramenta de modelagem/animação; o que só serve a isso fica fora.
Shading dos meshes não muda (só menus/overlays).

Código: `source/release/scripts/startup/bl_ui/space_view3d.py`
(`VIEW3D_PT_shading` ~3753, `VIEW3D_PT_overlay` ~3806, `VIEW3D_PT_gizmo` ~3971,
`VIEW3D_PT_pivot_point`, `VIEW3D_PT_snapping`, `VIEW3D_PT_transform_orientations` ~4130).
Após editar, copiar para `build/bin/2.79/scripts`.

Legenda suporte: **OK** = propriedade já existe no 2.79; **Py** = dá para fazer só em Python;
**C** = precisa de código C novo; **Não** = não existe e não vale fazer.

## Grupo 1 — só visual (rápido)

### 1.1 Transform Orientations
- Hoje: campo fechado "Global" + `+`.
- B5: lista aberta com ícones.
- Decisão: lista aberta (`expand=True`) com ícones; manter `+` e as customizadas.
- Suporte: Global/Local/Normal/Gimbal/View **OK**. Cursor/Parent **Não** (fora).
- Aceite: [ ]

### 1.2 Pivot Point
- Decisão: título "Transform Pivot Point"; manter **Only Locations** (útil para posicionar cenário).
- Suporte: **OK**. Aceite: [ ]

### 1.3 Proportional Editing
- B5: bolinha liga/desliga direto; menu de falloff com **Proportional Size** embaixo; ordem começando em Smooth.
- Decisão: as três coisas.
- Suporte: `proportional_size` **OK**; Connected/Projected viram toggles abaixo do falloff.
  Os botões são desenhados em C (`view3d_header.c` ~435) → precisa build; feito depois do Python.
- Aceite: [ ]

> 2026-10-25: 1.1, 1.2, 1.4, 1.5 e 2.2 (Gizmos) reescritos em Python, aguardando aceite com janela.

### 1.4 Overlays
- B5: seções recolhíveis, 2 colunas.
- Decisão:
  - Guides: Grid, Floor Lines, Axes X/Y/Z, Scale, Subdivisions, 3D Cursor.
  - Text: View Name, Object Info, Statistics (+ Performance ligando ao menu Performance, se barato).
  - Objects: Outline Selected, Origins, Origins (All), Relationship Lines, Show Components (rótulo inteiro).
  - Motion Tracking: recolhido no fim.
- Fora: Viewer Node, Bones, Motion Paths, Annotations, Face Orientation (**Não** no 2.79).
- Suporte: **OK** (só layout). Aceite: [ ]

### 1.5 Shading (seta)
- Decisão: seções Lighting (World Background), Game Preview (World Mist, Depth Of Field, Show Invisible LODs), Display (Backface Culling, Show Components).
- Fora: Render Pass, Compositor (Cycles/EEVEE).
- Suporte: **OK**. Aceite: [ ]

## Grupo 2 — médio

### 2.1 Snapping
- B5: Snap Base / Snap Target em lista / opções / Affect / Rotation Increment.
- Decisão: reordenar — Snap Base (Closest/Center/Median/Active) em cima, alvos em lista com ícones, depois Absolute Grid Snap, Align Rotation, Project, Snap Self/Peel quando aplicável.
- Suporte: tudo atual **OK**. Backface Culling no snap, Exclude Non-Selectable, Affect, Edge Center/Perpendicular, Grid separado: **C** → grupo 3 ou fora.
- Aceite: [ ]

### 2.2 Viewport Gizmos
- Decisão: seções Viewport (Navigate: Axes + Size, Controls in Header) e Object Gizmos (Translate/Rotate/Scale).
- Fora: Active Modifier; gizmos de Empty/Light/Camera (**Não** existem no 2.79).
- Suporte: **OK**. Aceite: [ ]

## Grupo 3 — maior (decidir antes)

### 3.1 Selectability & Visibility (menu novo)
- Valor para jogo: travar cenário (Mesh), esconder Light/Empty ao mexer em lógica.
- Tipos: Mesh, Curve, Surface, Meta, Text, Armature, Lattice, Empty, Lamp, Camera, Speaker.
- Suporte: **Py** (operador que aplica `hide_select`/`hide` por tipo nos objetos da cena); estado por tipo guardado na cena precisa de **C** se quiser persistir como no B5.

### 3.2 Snap extra (Edge Center, Edge Perpendicular, Exclude Non-Selectable)
- Útil para montar pista/cenário modular. Suporte: **C** (transform_snap). Avaliar custo.

### Pesquisa do Grupo 3 (2026-10-25, sem edição)
- `snap_mode` é valor único (`DNA_scene_types.h` ~1787, valores 0-8). Modos novos: `EDGE_MIDPOINT=9`, `EDGE_PERPENDICULAR=10`, sem do_versions. Multi-seleção estilo B5 = campo novo + do_versions, 2-3 dias → adiar.
- **Exclude Non-Selectable / Backface Culling (0,5-1 dia, risco baixo):** bits livres em `snap_flag` (1<<6, 1<<7); filtro `OB_RESTRICT_SELECT` em `iter_snap_objects` (`transform_snap_object.c` ~158); backface no `raycast_all_cb` (~319) e callbacks de raycast (~353, ~533) com `dot(ray_dir, normal) > 0`; passar via `SnapObjectParams` (`transform_snap.c` ~1224/1315).
- **Edge Center/Perpendicular (1-1,5 dia):** trocar `tmp_co` em `test_projected_edge_dist` (~910) por meio da aresta / `closest_to_line_segment_v3` com ponto de referência (`t->center_global`); trocar `== SCE_SNAP_MODE_EDGE` por `ELEM(...)` (~1259, ~1590, ~1755) e nos `case` de armature/curve/empty/camera. Sem ícone próprio no 2.79 (usar SNAP_EDGE ou desenhar). Risco: valor 9/10 aparece em branco na Range original.
- **Selectability & Visibility:** opção A só Python (0,5 dia, recomendada; objetos novos não herdam); opção B nativa com bitmask por tipo no View3D (2-3 dias; limitar ao editor, não mexer no BGE).
- Ordem proposta: Exclude/Backface → Edge Center/Perp (modo único) → Selectability opção A.

## Fora de escopo (modelagem/animação)
Hair Curves, Point Cloud, Volume, Grease Pencil 3, Viewer Node, Bones overlay, Motion Paths,
Annotations, Render Pass, Compositor, Active Modifier, orientações Cursor/Parent,
Face Project/Face Nearest.

## Ordem
Grupo 1 (1.4 Overlays primeiro, maior ganho) → aceite com janela → Grupo 2 → decidir Grupo 3.

> 2026-10-25: Proportional (toggle + popover VIEW3D_PT_proportional_edit), ícones das Orientations e Snapping reordenado feitos; build OK; aguardando aceite com janela.
