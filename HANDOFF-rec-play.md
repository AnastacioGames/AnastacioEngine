# Handoff — Rec Play

Branch: `main`. Plano: [docs/gravacao-de-movimento-plan.md](docs/gravacao-de-movimento-plan.md).
Regras de build: [AGENTS.md](AGENTS.md).

## Estado

- Fase 1 (botão, ícone, operador `VIEW3D_OT_game_record`): enviada.
- Fase 2 (captura e Action `Rec_<objeto>`): feita, ver `docs/changelog.md`.
- Próxima: Fase 3. Antes de começar, ouvir as observações do usuário sobre o teste da Fase 2.

## Como testar

```
set REC_LOG=caminho\log.json
set REC_RES=caminho\res.txt
AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_rec_play.py -- cena.range
AnastacioEngine.exe cena.range --python tools/debug/editor_rec_play.py
```

O script usa a 3D View em tela cheia e desfaz por timer: contexto forçado no redesenho e `ed.undo` dentro de
`scene_update_post` derrubam o editor, mas isso é do script, não do Rec Play.

## Falta conferir à mão

F10 e Esc durante a gravação; personagem físico; objeto parentado a osso (usa o caminho sem a matriz do pai).
