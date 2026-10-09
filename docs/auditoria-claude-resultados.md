# Auditoria: resultados do Claude (GL5, GL6, GL10)

Lote delegado por `docs/auditoria-handoff-claude.md`. Branch `claude/auditoria-gl`
(worktree separada). Codex integra estados em roadmap/changelog/suspeitos.

## Teste comum

Cena gerada por `criar_cena_gl.py` (pasta temporaria da sessao): 300 empties, cada
um com Always em pulso ligado a seis atuadores de propriedade (Add "1", Assign
"m + 2", Assign "5" em propriedade inexistente seguido de Add "1", Assign `"ok"`,
Toggle), sensor Property Changed, teclado (todas as teclas, toggle vazio) e mouse.
Um Probe roda 1200 frames sem vsync e grava somas das propriedades e ms por frame
dos frames 200-1200.

Base e nova compiladas da mesma worktree (5a7c6709 com e sem o diff), rodadas
alternadas, mesma cena:

| Rodada | Base (ms/frame) | Nova (ms/frame) |
| --- | --- | --- |
| 1 | 1,833 | 1,295 |
| 2 | 1,812 | 1,240 |
| 3 | 1,825 | 1,250 |

Media: 1,82 → 1,26 ms por frame (-31%) com 1800 atuadores de propriedade, 300
sensores Changed, 300 de teclado e 300 de mouse. Resultado funcional identico nas
seis rodadas: `soma_n 359700`, `soma_m 719400`, `a = 6`, `s = "ok"`. O contador
do sensor Changed nao e deterministico entre execucoes (depende do ritmo de frames)
e nao foi usado como criterio.

## GL5 — SCA_PropertyActuator

**Diagnostico: confirmado.** Cada ativacao positiva criava um `EXP_Parser`, mesmo em
Toggle/Level, e reinterpretava `m_exprtxt` (alocacao da arvore e dos valores).
Identificadores sao resolvidos no `Calculate` via contexto do parser, entao arvores
com nomes de propriedade nao podem ser guardadas (prenderiam o dono por referencia).

**Mudanca:** `GetExpression` so e chamado em Assign/Add/Copy. Quando `m_exprtxt` e um
literal (numero com sinal opcional, ou string entre aspas), a arvore e guardada e
reaproveitada enquanto o texto for igual (`value` via Python invalida). Literais
nao tem identificador, entao a arvore nao referencia o objeto. `EXP_ConstExpr`
devolve o proprio valor; por isso, ao criar propriedade nova com Assign a partir
da arvore guardada, grava-se uma replica, para um Add posterior nao alterar a
constante (coberto pelo teste `a_valores`). Replicas zeram o cache no
`ProcessReplica`. Expressoes com nomes, erros de parse e o ramo runtime property
seguem o caminho anterior.

**Pendencia:** a conversao do ramo runtime property (`CM_StringTo`/`sscanf` por
ativacao) nao foi cacheada: custo pequeno e recurso pouco usado.

## GL6 — SCA_PropertySensor

**Diagnostico: majoritariamente falso positivo.** As conversoes de constante sao um
`CM_StringTo` de texto curto por frame; um cache precisaria comparar a string
(`value`/`min`/`max` sao gravaveis por Python), custo equivalente. Sem ganho real,
nao foi alterado. Unico desperdicio concreto: no modo Changed, `GetText()` (retorna
por valor) era chamado duas vezes quando o valor mudava.

**Mudanca:** Changed chama `GetText()` uma vez e move o texto para `m_previoustext`.

## GL10 — SCA_KeyboardSensor e SCA_MouseManager

**Diagnostico: confirmado, custo pequeno.**
- Teclado: `GetProperty("")` por frame em todo sensor sem toggle configurado; com
  "All keys", dois lacos completos sobre as teclas; com log ativo, a propriedade de
  texto era reconstruida (conversao UTF-8 + nova `EXP_StringValue`) todo frame
  mesmo sem digitacao.
- Mouse: posicao (`GetInput` MOUSEX/MOUSEY) relida por sensor dentro do laco.

**Mudancas:** pula a busca com toggle vazio; um laco unico com saida antecipada;
`LogKeystrokes` retorna cedo sem texto digitado quando a propriedade alvo ja e
string (se nao for string, segue convertendo como antes); posicao do mouse lida uma
vez, no primeiro sensor nao suspenso.

## GL9 — SCA_TimeEventManager (extra, fora do handoff)

**Diagnostico: falso positivo na pratica.** O `new EXP_FloatValue` e um por frame
(nao por propriedade), e so ocorre com propriedades Timer ou `fixedtime > 0`. Uma
alocacao pequena por frame nao aparece em medicao.

**Mudanca minima:** retorna cedo sempre que nao ha propriedades Timer (antes
alocava e liberava o valor sem uso quando `fixedtime > 0`). Sem efeito funcional.
GL7 e GL8 (Ketsji) ficaram de fora por estarem fora do escopo GameLogic do handoff.

## RA4 — cache do stream VBO de instancing

**Diagnostico: confirmado.** O VBO de instancing era reenviado a cada passe mesmo
com todas as instancias paradas.

**Mudanca:** o buffer guarda slots, revisoes e pass index do ultimo stream e pula
`GPU_buffer_lock_stream` quando nada mudou (so `RAS_NORMAL` sem sort). A revisao
de `RAS_MeshUser` vem de um contador atomico global `uint64_t`. Uma revisao local
iniciada em 1 permitia ABA: um objeto novo no endereco de um removido podia
casar ponteiro e revisao e herdar a matriz/cor antigas.

**Teste:** `criar_cena_ra4_instancing.py`, 100 cubos com instancing. drawCalls = 1
em todos os frames; instancingUploads = 1 inicial, 0 em repouso, 1 em cada mudanca
(posicao f60, cor f100, ocultar f140, mostrar f180). Build editor/player ok.
Sem benchmark de FPS. Pendencia a parte: o player nao fecha apos `endGame()`
nessa cena.
