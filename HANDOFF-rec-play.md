# Handoff — Rec Play

Branch: `main`. Plano: [docs/gravacao-de-movimento-plan.md](docs/gravacao-de-movimento-plan.md).
Regras de build: [AGENTS.md](AGENTS.md).

## Estado

- Fase 1 (botão, ícone, operador `VIEW3D_OT_game_record`): enviada.
- Fase 2 (captura e Action `Rec_<objeto>`): feita, ver `docs/changelog.md`.
- Fase 2.5 (Takes, Max Duration, contador): feita, sem aceite visual do painel e do contador.
- Fase 2.6 (evento Play Take e Add to Cutscene): feita, sem aceite visual.
- Fase 3 (filhos e armature por NLA): feita, sem teste com personagem real.
- Próxima: Fase 4.

## Como testar

```
set REC_LOG=caminho\log.json
set REC_RES=caminho\res.txt
set REC_CUT=caminho/copia_cutscene.range
set REC_REPLAY=caminho/replay.json
AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_rec_play.py -- cena.range
AnastacioEngine.exe cena.range --python tools/debug/editor_rec_play.py
```

O script usa a 3D View em tela cheia e desfaz por timer: contexto forçado no redesenho e `ed.undo` dentro de
`scene_update_post` derrubam o editor, mas isso é do script, não do Rec Play.

## Falta conferir à mão

F10 e Esc durante a gravação; personagem físico; objeto parentado a osso (usa o caminho sem a matriz do pai).
