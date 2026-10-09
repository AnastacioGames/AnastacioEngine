# Auditoria: tarefas para o Claude

## Passagem vigente — RA4 (2026-10-09)

O lote GL5/GL6/GL9/GL10 abaixo ja foi integrado. RA3 foi validado no jogo e
integrado em `12741810`; RA5 esta concluido por aceite do usuario. A proxima
tarefa autorizada para o Claude e concluir **RA4 — cache do stream VBO de
instancing**. Nao descarte nem reformate alteracoes preexistentes do worktree.

### Estado entregue

- Ha um diff local, ainda sem commit, nos arquivos
  `Common/CM_WorkCounters.h`, `Ketsji/KX_PythonInit.cpp`,
  `Rasterizer/RAS_MeshUser.{h,cpp}`, `RAS_InstancingBuffer.{h,cpp}` e
  `RAS_DisplayArrayBucket.cpp`.
- O desenho: `RAS_MeshUser` incrementa `m_instancingVersion` se matriz, cor,
  layer ou pass index mudam. O buffer guarda slots/revisoes/pass index do ultimo
  stream e so chama `GPU_buffer_lock_stream` de novo se a lista/ordem ou alguma
  revisao mudou. `Realloc` invalida os dados. O cache esta propositalmente
  restrito a `RAS_NORMAL` sem `m_sort`: billboards e halos dependem da camera;
  transparencia ordenada precisa ordenar e reenviar pelo caminho atual.
- Novo contador por frame: `instancingUploads` em
  `bge.logic.getRenderStats()`, incrementado em `RAS_InstancingBuffer::Update`.
- Gerador de teste criado: `tools/debug/cenas/criar_cena_ra4_instancing.py`.
  Ele monta 100 cubos que compartilham malha/material Principled com
  `use_instancing=True`; altera posicao no frame 60, cor no 100, visibilidade
  no 140/180 e grava `drawCalls`/`instancingUploads` em `RA4_RESULT`.
- Build `RangeEngine RangeRuntime` passou com `vcvars64.bat` e `VSLANG=1033`
  (log `%TEMP%/anastacio-ra4/build.log`). Depois gere/reabra a cena e execute
  o player. Esperado:
  upload inicial, zero no repouso, um upload ao mover/mudar cor e upload quando
  a lista de visiveis muda, sem alterar os draws esperados.

### Limites

- Nao declare RA4 concluido sem build e execucao bem-sucedidos.
- Avalie overflow de `unsigned int` da revisao: wraparound e aceitavel apenas se
  a igualdade continuar segura no ciclo de vida do buffer; se nao, corrija de
  modo local. Confirme tambem a comparacao de `mt::vec4` no build atual.
- Preserve os contadores existentes e nao use o cache em caminhos dependentes
  da camera. Medir uploads comprova trabalho removido; nao alegar ganho de FPS
  sem benchmark separado.

Divisao proposta em 2026-10-09, autorizada pelo usuario. Codex permanece com RA3
e seu plano de transparencia. Este documento pode ser passado diretamente ao Claude.

## Escopo do Claude

Retome a auditoria geral em `docs/auditoria-suspeitos.md`, nesta ordem:

1. **GL5 — SCA_PropertyActuator**: verificar o custo de criar parser e reavaliar
   expressao constante a cada ativacao. Distinguir constantes de expressoes que
   dependem de propriedades mutaveis. Nao congelar valores dinamicos nem mudar
   semantica de erro, conversao, replica ou modos do atuador.
2. **GL6 — SCA_PropertySensor**: verificar lookup/conversao repetidos de constantes.
   Preservar alteracoes de propriedades, configuracao via Python, replicas,
   comparacoes de texto/numeros, intervalos e pulsos positivos/negativos.
3. **GL10 — SCA_KeyboardSensor e SCA_MouseManager**: verificar lookup de toggle
   vazio e consultas invariantes dentro do laco. Preservar captura de texto,
   toggle configurado, transicoes de teclas/botoes e eventos de mouse.

Os itens ainda sao suspeitos: primeiro confirme no codigo atual e no historico
relevante. Se ja estiverem resolvidos ou forem falsos positivos, registre a evidencia;
nao invente uma correcao para justificar o item.

## Modo de trabalho e verificacao

- Leia `AGENTS.md`, `docs/README.md`, roadmap e relatorio vigente. Consulte apenas
  o changelog pertinente e os indices locais de logic-scripting.
- Trabalhe uma peca por vez. Para mudanca grande/arriscada, apresente diagnostico
  e plano antes de implementar, conforme AGENTS.md.
- Prefira mudancas locais aos arquivos de GameLogic. Nao altere renderizacao,
  shaders, transparencia, matrizes, RA2/RA3 ou infraestrutura geral do profiler.
- Use contadores/testes existentes quando possivel. Compare resultados funcionais
  antes/depois e meca o trabalho eliminado; nao deduza ganho de FPS de uma leitura.
- Para cenas `.range`, use `.claude/skills/cena-de-teste/SKILL.md` e salve em pasta
  temporaria exclusiva. Nao altere o jogo original do usuario.
- Compile editor/player e execute testes relevantes com `vcvars64.bat` e
  `VSLANG=1033` na mesma chamada. Siga a regra anti-loop do AGENTS.md.
- Entregue por item: diagnostico, arquivos alterados, teste/reproducao, resultado,
  medida se houver e pendencias. Nao marque concluido sem build/execucao exitosos.

## Coordenacao para evitar conflitos

- Preferencia: worktree/branch propria para o Claude; confira previamente o estado
  do repositorio e preserve todas as alteracoes existentes.
- Se trabalhar na mesma pasta, mantenha o escopo de arquivos acima e coordene
  builds: ambos compartilham `build/` e `build/bin/`; nao execute Ninja nem substitua
  binarios enquanto Codex estiver construindo ou usando a referencia visual.
- Nao edite diretamente os documentos compartilhados `docs/roadmap.md`,
  `docs/changelog.md` e `docs/auditoria-suspeitos.md` durante o trabalho paralelo.
  Registre resultados em `docs/auditoria-claude-resultados.md`; Codex integra os
  estados e historico ao final. Rode `python tools/check_docs.py`.
- Nao inclua alteracoes preexistentes em commits. A skill Claude atualizada e os
  documentos do RA3 estao sem commit e pertencem ao trabalho anterior do Codex.
- Commit/publicacao ficam para uma solicitacao do usuario; entregue o diff revisavel.

## Fora deste lote

RA3 e validacoes de transparencia ficam com Codex. Fisica, rede, spawn/LibLoad,
animacao e demais itens da lista nao fazem parte desta delegacao inicial.
