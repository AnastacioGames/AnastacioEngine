# Plano: nó Minimap na UI Tree

Status: implementado em 2026-11-03 (falta aceite visual com janela e uso no RolimaRacer).

## Objetivo

Nó HUD **Minimap** no UI Tree, sem código: imagem do mapa visto de cima e
marcadores (jogador, rivais) que andam com a posição dos objetos. Não
redesenha a cena (leve na iGPU), ao contrário de uma segunda câmera.

## Onde mexer

1. `source/release/scripts/startup/range_ui_tree.py`
   - Classe `UIMinimapNode(UIHudNode, Node)`, `bl_idname = "RangeUIMinimap"`,
     ao lado de `UIImageNode`/`UIGaugeNode`.
   - Propriedades:
     - `image_name` (prop_search em `bpy.data.images`), `tint`;
     - `world_min` / `world_max` (X/Y do mundo cobertos pela imagem);
     - botão "Fit to Scene" que mede os limites pelos objetos de uma
       Collection/Group ou pela seleção;
     - `rotate` (mapa gira com o jogador) e `zoom` (raio visível em metros;
       0 = mapa inteiro);
     - formato: `shape` quadrado/redondo, `radius`, borda e cor da borda
       (reaproveitar o estilo do Panel);
     - marcadores: Object = jogador (`object_name` herdado), cor e tamanho.
       Rivais: prefixo de nome (ex.: `carro_`) **ou** propriedade de jogo
       (ex.: `minimap`), com cor e tamanho próprios. O jogador desenha como
       seta (direção pela rotação Z), os outros como ponto.
   - `widget()` devolve `{"kind": "MINIMAP", "path", "tint", "world_min",
     "world_max", "rotate", "zoom", "shape", ..., "markers": {...}}`.
   - `preview_values()`: marcador de exemplo no centro.
   - Registrar em `HUD_NODES` e em `CATEGORIES` (categoria HUD).
   - Prévia no editor: em `_draw_previews`, o mesmo bindcode que o
     `UIImageNode` usa (`image.gl_load()`).

2. `source/release/scripts/modules/range_ui_draw.py`
   - `draw_minimap(bgl, data, bindcode, markers, x, y, w, h)`:
     - mundo -> UV: `u = (px - min_x) / (max_x - min_x)`, idem v;
     - zoom/rotate: recorte de UV centrado no jogador e girado por -yaw
       (rodar as coordenadas de textura do quad, não a tela);
     - formato redondo: triangle fan com UVs por vértice (sem stencil);
     - marcadores fora do recorte: grudar na borda (clamp) ou esconder;
     - borda com `_rounded_polygon`.
   - Ramo `elif kind == "MINIMAP"` em `draw_widget`. Os marcadores chegam
     por parâmetro, então a função continua sem depender de bpy/Range.

3. `source/release/scripts/modules/range_ui_runtime.py`
   - `_DRAW_ORDER`: MINIMAP com o mesmo nível do IMAGE.
   - Em `draw_widgets`: para MINIMAP, carregar a textura com
     `self.texture(path)` e montar a lista de marcadores:
     `(x, y, yaw, cor, tamanho, é_jogador)`, vinda de `self.obj_for(data)` e
     da varredura de `self.scene.objects` pelo prefixo/propriedade.
     **Guardar em cache** a lista de objetos rivais (refazer só quando a
     contagem de objetos da cena mudar), para não varrer tudo a cada quadro.
   - Yaw: `obj.worldOrientation.to_euler().z`.

4. Depois de editar: copiar os 3 arquivos para `build/bin/2.79/scripts/...`
   (regra de sincronizar os scripts).

## Teste

- Cena de teste (skill cena-de-teste): plano com textura, um cubo jogador
  andando e 3 rivais com a propriedade `minimap`; Bake UI; rodar em
  background e conferir sem erro no log (`%TEMP%/range_runtime.log.txt`).
- Aceite visual com janela só quando o usuário pedir.
- Web: só bgl, sem API de SO, então não precisa de ramo `__EMSCRIPTEN__`.
- Depois: RolimaRacer (imagem da pista + 20 pilotos) e entrada em
  docs/changelog.md e na documentação do UI Tree.

## Fora do escopo (talvez depois)

- Gerar a imagem do mapa automaticamente (render ortográfico de cima por
  um operador "Bake Minimap Image").
- Desenhar o traçado da pista a partir de uma curva Bézier.
