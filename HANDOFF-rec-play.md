# Handoff — Rec Play, Fase 1 (botão, ícone e operador)

Para continuar no PC (Windows), com Claude ou Codex. Branch: `ccr-f8a165aa-ikjsis`.
Plano completo: [docs/gravacao-de-movimento-plan.md](docs/gravacao-de-movimento-plan.md).
Regras de build: [AGENTS.md](AGENTS.md) (sempre `vcvars64.bat` + `set VSLANG=1033&&`).

## O que já está pronto (só Python, ainda não visto no editor)

- Painel **Motion Recording** em Properties > Render > System, depois de Player:
  `RENDER_PT_game_motion_record` em `source/release/scripts/startup/bl_ui/properties_game_render.py`,
  registrado em `bl_ui/properties_game.py`.
- Propriedades `Scene.ae_rec_*`, `Object.ae_rec_actor`, `Object.ae_rec_action` em
  `source/release/scripts/startup/bl_operators/anastacio_motion_record.py` (na lista `_modules` de
  `bl_operators/__init__.py`).

**Primeiro passo no PC:** `git pull`, copiar `source/release/scripts/` para `build/bin/2.79/scripts/`, abrir o
editor e conferir o painel (três passos, Advanced fechado). Só depois começar o C++.

## Fase 1 — o que fazer

Objetivo: botão **Rec Play** que inicia o Play embutido igual ao Play, mas com uma flag de "gravando". Ainda
não grava nada (isso é a Fase 2). Teste de aceite: o botão aparece com ícone próprio no cabeçalho e na barra
flutuante, o jogo inicia, Esc volta ao editor, e o console mostra uma linha confirmando que a flag chegou ao
runtime.

1. **Ícone `REC_PLAY`** (mesmo caminho do `COOK`, ver changelog "Ícone novo `COOK`"):
   - trocar um `DEF_ICON_BLANK(n)` livre por `DEF_ICON(REC_PLAY)` em
     `source/source/blender/editors/include/UI_icons.h` (não renumerar; usar um BLANK);
   - criar `release/datafiles/blender_icons16/icon16_rec_play.dat` e `blender_icons32/icon32_rec_play.dat`
     (copiar o formato de `icon16_cook.dat`/`icon32_cook.dat`) e PNGs em `icons_blender5` e `icons_upbge`;
   - acrescentar `rec_play` na lista de ícones de `source/source/blender/editors/datafiles/CMakeLists.txt`
     (ao lado de `cook`);
   - desenho original: bola vermelha + seta de play/filme. Não copiar arte do 3D Movie Maker.
   - `python tools/check_ui_icons.py` tem de continuar sem erro novo.
2. **Operador `VIEW3D_OT_game_record`** em `source/source/blender/editors/space_view3d/view3d_view.c`, ao lado de
   `VIEW3D_OT_game_start`: mesmo `game_engine_exec`/`game_engine_poll`; liga a flag antes e desliga depois.
   Declarar em `view3d_intern.h` e registrar em `view3d_ops.c` (perto de `WM_operatortype_append(VIEW3D_OT_game_start)`).
   - Flag: um campo de runtime que o Ketsji consiga ler (ex. global/argumento passado ao iniciar o jogo
     embutido). **Não** criar campo DNA nesta fase.
3. **Botões**: depois de "Play" em `uiTemplateHeader3D_game_controls` (`view3d_header.c`) e na barra flutuante
   (`view3d_draw.c`, bloco `view3d_floating_game_controls`): `uiItemO(row, "Rec Play", ICON_REC_PLAY, "VIEW3D_OT_game_record")`.
4. **Painel**: trocar a linha "Rec Play button: coming in phase 1" do passo 3 por
   `row.operator("view3d.game_record", text="Rec Play", icon='REC_PLAY')` com `row.scale_y = 1.6`.
5. **Docs**: entrada no topo de `docs/changelog.md`, atualizar "Gravação de movimento" em `docs/roadmap.md`,
   `python tools/check_docs.py`.

## Cuidados

- `UI_icons.h` é header: depois de editar, se aparecer crash estranho, `ninja -t clean` (AGENTS.md).
- Alvo para testar: `RangeEngine` (editor). Não marcar como feito sem build e teste na janela.
- Parar para o usuário testar antes da Fase 2.
