# Revisão para o Codex: controle de testes + correções dos lotes 1 e 2

Você é revisor. Não implemente nada; entregue um relatório. Para cada ponto diga
**aceito / parcial / recusado** com arquivo:linha e o motivo, conferido no código.

## 1. Ferramenta de controle (sem commit ainda)

Arquivos: `tools/testes_engine/servidor.py`, `controle.py`, `varrer.py`,
`source/source/blender/makesrna/intern/rna_wm_api.c` (`Window.event_simulate`),
linha nova no `AGENTS.md`.

Como funciona: o editor abre numa área de trabalho Windows invisível
(`CreateDesktopW`), com config isolada (`BLENDER_USER_*`). Um operador modal com
timer atende um pedido TCP por tique em 127.0.0.1 com token (`sessao.json`).
Comandos: listar, descrever, op, ler, definir, py, desenhar, tela, evento, fechar.
`event_simulate` só funciona com `ANASTACIO_EVENT_SIMULATE=1`.

Revise:
- Segurança: dá para outro processo usar o servidor (token, bind, arquivo de
  sessão)? `event_simulate` vaza para builds de usuário? Recusa sem a variável?
- Robustez: override de contexto (`contexto()`, `so_janela()`), troca de tipo de
  área (`TrocouEditor`), socket não bloqueante, pedidos parciais/grandes, timeout,
  editor travado ou morto.
- `rna_wm_api.c`: validação de `type`/`value`, coordenadas, `text` (UTF-8,
  tamanho), memória do evento, uso com janela sem foco.
- `varrer.py`: reset da cena entre operadores, classificação dos estados
  (ok, sem_contexto, recusou, falha, crash, travou, pulado), lista `PERIGOSOS`
  (falta algum operador que mexe em disco, rede, janelas ou abre o runtime?).
- Portabilidade: o que quebra no Linux (sugestão com Xvfb).

## 2. Correções já enviadas ao main

Commits `ea3c3f1f` e `a419e5ed` (`git show` em cada). Confira se cada guarda
cobre a causa e não só o sintoma, e se não muda comportamento válido:
- `outliner_edit.c` `parent_drop_exec`, `node_select.c` (`select_grouped`,
  `select_same_type_step`), `object_modifier.c` `skin_armature_create_exec`.
- `sculpt_undo.c` `sculpt_undosys_step_decode`: sair cedo deixa o undo
  consistente?
- `object_vgroup.c`: troca de `CTX_data_active_object` por `ED_object_context`
  nos execs de fix/lock — bate com o poll em todos os contextos (pin de
  propriedades)?
- `object.c` `BKE_object_animation_event_remove`: decremento do índice dos
  sensores; e o sensor que apontava exatamente para o removido?
- `bpy_internal_import.c`: `ImportError` quando não há exceção pendente; o
  ramo de reload precisa do mesmo?
- `clip.py` (`int()`), `anastacio_track.py` (ícones).

## 3. Fila ainda não aplicada (dê opinião antes de eu aplicar)

- Logic Tree: `plan()` com regra morta (`range_logic_tree.py:583`),
  `logic_tree_record` sem try/finally, Convert to Nodes renumera estados e
  perde valores iguais ao padrão (`:1453`).
- UI Tree: Bake quebra com nó que não é widget dentro de Screen (`range_ui_tree.py:881`),
  evento via Reroute some (`_actions_for` `:849`), Setup Game Logic sem objeto (`:1490`).
- Material from Texture Set: classificação de mapas (`anastacio_material_recipes.py:64-107`),
  `alpha_blend` herdado (`:811`).
- Dope Sheet modo Cache File lê tipo errado (`anim_filter.c:202`); índice ativo
  de cutscene fica -1 (`object_cutscene.c:153,186,291`).
- `KX_BatchGroup` x Auto Static Batch (`KX_BatchGroup.cpp:118-121`).

Formato de saída: lista por seção, mais grave primeiro, curta.
