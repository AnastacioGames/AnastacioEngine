# Notas — Cutscene: export/import de todos os eventos e Wait Trigger (branch `cutscene/events`)

Dúvidas, decisões tomadas sem perguntar e bloqueios desta sessão (2026-10-04, rotina agendada).

## Decisões

- **Wait Trigger — como é liberado.** O plano não define o mecanismo. Implementados dois caminhos:
  1. **Mensagem**: uma mensagem com *subject* igual ao nome do Trigger (Send Message actuator ou
     `bge.logic.sendMessage("nome")`, sem destinatário) libera a espera. `KX_Scene::UpdateCutscene` consulta o
     `KX_NetworkMessageScene` a cada tick enquanto o manager está em `WAIT_TRIGGER`.
  2. **Chamada Python**: `scene.release_cutscene_trigger(name)` (retorna `True` se encerrou a espera agora).
  - **Propriedade (game property): não implementada.** `KX_Scene` não tem propriedades de jogo próprias; ligar
    uma propriedade de objeto exigiria escolher qual objeto (decisão de design em aberto). Mensagem + Python cobrem
    o mesmo uso. Reavaliar se o usuário quiser.
- **Latch de trigger.** Se o trigger é liberado *antes* da espera começar (mesmo tick ou antes), fica retido e
  é consumido pelo próximo Wait Trigger com o mesmo nome, para não perder a liberação por ordem de tick. `Start()`
  e `Stop()` limpam os latches. Risco: um release "sobrando" faz o próximo Wait Trigger com o mesmo nome passar
  direto; está documentado no `.h`.
- **Bug corrigido de passagem:** `Start()`/`Stop()` não limpavam o estado de espera, então um `restart`/novo
  `play` durante um Wait herdava a espera anterior.
- **Schema JSON v2.** O v1 (`{cena: {nome_da_sequência: [passos]}}`) perdia `cutscene_id` e o nome da sequência
  (o importador prefixava `"Cena / "`). O exportador agora grava `schema_version: 2`
  (`{cena: {"sequences": [{name, cutscene_id, events}]}}`) e o importador aceita legado, v1 e v2. Todos os 18 tipos
  de evento têm ação JSON (`cutscene_native_events.py`, verificada contra o enum RNA no teste).
- Campos DNA sem propriedade RNA (`param_str_b`, `flag`, `param_int` em Lock Player etc.) não são exportados:
  só o que a UI edita.

## Bloqueios de ambiente

- `python.org` bloqueado pelo proxy (403): `tools/linux/install-python311.sh` não consegue baixar o CPython 3.11.9.
  Contorno: Python 3.11 do apt (`/usr`) com `-DPYTHON_ROOT_DIR=/usr`. O build resultante não é o pacote portátil de
  distribuição, só serve para testes.
- Build de teste: preset `linux-editor` com Cycles, Compositor, OpenColorIO, OpenImageIO e International desligados
  para encurtar (nenhum afeta o Cutscene). Diretório `build-linux-editor/` (não versionado).
