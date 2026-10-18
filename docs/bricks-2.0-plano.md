# Logic Bricks 2.0 — análise e plano

Estado: **plano v2 (2026-10-17)**, revisado após o parecer do Codex. Nada implementado ainda. Branch prevista:
`logic/bricks-2`.

Mudanças da v1 para a v2:
- "Então" deixa de ser um link direto actuator → controller e passa a ser um **sensor de conclusão**.
- Conclusão, cancelamento e falha passam a ser separados.
- O disparo é chamado de **próximo tick de lógica**.
- O Esperar ganha um contrato completo.
- As fases foram divididas em entregas menores e os testes passam a cobrir eventos.

## 1. Por que mexer nos bricks

Os bricks são a porta de entrada da engine para quem não programa. O conversor Logic Bricks → Python (F1–F10)
reproduz o comportamento da engine com CHECK idêntico nos cenários testados (não é uma equivalência geral: o
changelog registra diferenças de ordem entre objetos). Recurso novo precisa continuar convertível.

### O que limita hoje

| Dor | Contorno atual | Custo |
|---|---|---|
| Não existe "depois disso, faça aquilo" | Estados, sensor Actuator, Delay + propriedade como timer | Lógica espalhada, difícil de ler |
| Estados são números 1–30 | Memorizar | Iniciante não entende estados |
| Muitos bricks viram parede de colunas | Rolar, recolher um por um | Projetos grandes ilegíveis (RolimaRacer: 324 controllers em 42 arquivos) |
| Começar do zero | Copiar de outro arquivo | Atrito para o iniciante |
| Não se vê o que dispara | `print` em controller Python | Depuração às cegas |

## 2. Princípios

1. **Nada quebra.** Arquivo antigo (inclusive da Range original 1.6.1002, que pula o nosso versioning) abre e roda
   igual. Campo novo zerado vale o comportamento antigo. Essa regra é necessária, mas não basta: cada campo novo
   também precisa passar por serialização, leitura e remapeamento de ponteiros, cópia, exclusão, undo/redo e
   append/link (ver F0).
2. **Nativo.** O runtime fica em C++, sem custo de Python, e roda em Web/Android sem trabalho extra.
3. **O modelo sensor → controller → actuator é mantido.** Recurso novo entra como sensor, controller ou actuator, e
   não como um caminho paralelo de eventos.
4. **Convertível.** Todo recurso novo entra no `logic_to_python.py`, validado por eventos (seção 5).
5. **Iniciante primeiro.** O recurso precisa ser descobrível olhando para a tela.
6. **Poucos casos bem definidos antes do universal.** Começamos com poucos actuators de semântica clara.

## 3. Ideias, por impacto

### A. Sequência — sensor "Concluído" + atalho "Então" ★★★ (o transformador)

**Por que um sensor e não um link direto.** Em `SCA_ANDController::Trigger` (e no OR), o controller decide lendo
`sensor->GetState()` de cada sensor ligado. `AddTriggeredController()` só agenda a avaliação e não força um
resultado positivo. Um link direto actuator → controller exigiria uma entrada lógica nova em todos os controllers.
Um sensor encaixa no modelo atual sem mudar nenhum controller:

```
[Keyboard Space] → [And] → [Action "pulo"]
[Concluído: Action "pulo"] → [And] → [Sound "aterrissa"]
```

Na interface, o usuário arrasta da saída **"Então"** do actuator para a coluna de controllers. O editor cria o
sensor "Concluído" já apontado para aquele actuator e o liga. Quem conhece bricks vê um sensor normal; o iniciante
vê o fio.

As perguntas do Codex ficam resolvidas pelo próprio modelo:
- **Combinar com outros sensores:** sim. "Concluído + Keyboard" num AND significa "terminou e a tecla está
  apertada".
- **Dois actuators concluindo:** dois sensores. Com OR, qualquer um basta. Com AND, os dois precisam concluir no
  mesmo tick. "Esperar ambos em ticks diferentes" fica para depois e pode ser resolvido com um modo Latch no sensor.
- **Origem num controller Python:** o sensor é acessível por nome, e `sensor.actuator` aponta para o actuator.

**Conclusão ≠ deixou de estar ativo.** Em `SCA_LogicManager::UpdateFrame`, `Update() == false` significa só "não
precisa continuar ativo". Isso também acontece quando a Action não tem animação ou propriedade válida, quando a
Action é interrompida, quando o Sound não tem som ou foi parado e quando o State recebe só um evento negativo.

Contrato:
- O `Update()` booleano continua igual.
- `SCA_IActuator` ganha um **motivo de encerramento**: `NONE`, `COMPLETED`, `CANCELLED` ou `FAILED`, com padrão
  `NONE`. Só os actuators suportados preenchem.
- O sensor "Concluído" dispara somente com `COMPLETED`. Cancelamento e falha não disparam no padrão. Uma opção
  futura pode disparar também em `CANCELLED`.
- Actuators que nunca preenchem o motivo **não aparecem** como alvo do "Então" na interface.

**Actuators da primeira entrega** (F2a): **Esperar** (novo), **Action** (Play: chegou ao fim do intervalo) e
**Sound** (Play End: tocou até o fim). Os outros entram em F2b, um de cada vez, com o contrato escrito (Motion não
termina sozinho, então provavelmente fica de fora).

**Entrega no próximo tick de lógica.** O nome é "tick", e não "quadro", porque com Fixed Timestep vários ticks podem
ocorrer antes de uma imagem ser desenhada. Regras:
- O sensor marca a conclusão quando ela acontece e só fica positivo na avaliação de sensores do **tick seguinte**.
  Isso evita recursão no mesmo tick, e a ordem de avaliação de sensores já é a da engine.
- Várias conclusões do mesmo actuator no mesmo tick contam como **um** pulso, porque o sensor é booleano.
- Um sensor fora do estado ativo **descarta** a conclusão, como acontece hoje com qualquer sensor.
- Ciclos (A → B → A): como cada sensor guarda só um booleano por tick, não há fila crescendo. O custo de um ciclo é
  no máximo um disparo por sensor por tick. Precisa ser confirmado com teste.

**Toca em:** novo `SCA_CompletionSensor` (ou modo novo do `SCA_ActuatorSensor`, a decidir em F0), motivo de
encerramento em `SCA_IActuator` e nos actuators suportados, DNA do sensor (aponta para o actuator por nome, como o
sensor Actuator já faz), conversão Blender → KX, `logic_window.c` (saída "Então" e fio), `logic_ops.c`,
`logic_to_python.py`.

Ponto a medir em F0: reaproveitar o sensor Actuator (que já referencia um actuator por nome e já tem DNA, cópia e
remapeamento) com um modo "Ao concluir" pode eliminar a maior parte do risco de DNA.

### B. Actuator "Esperar" (Wait) ★★★

| Situação | Comportamento |
|---|---|
| Unidade | Segundos de **tempo de simulação** (a escala de tempo afeta). Quadros fica para depois, se pedirem |
| Pulso positivo enquanto conta | **Ignorado** (tecla com pulso contínuo não reinicia o relógio) |
| Opção "Reiniciar" | Desligada por padrão; ligada, cada positivo zera a contagem |
| Pulso negativo | Ignorado: o Esperar começa e vai até o fim |
| Saída do estado do controller | **Cancela** (`CANCELLED`, não dispara "Concluído") |
| Duração zero | Conclui no tick em que foi ativado; o "Concluído" chega no tick seguinte |
| Objeto removido | Cancela |

### C. Estados com nome ★★☆

Um array de 30 nomes no objeto; nome vazio cai no número. Os botões de estado mostram o nome na dica, e o actuator
State oferece a lista. É só DNA + UI, sem runtime. Opcional: helper de nome na API Python.

### D. Grupos de bricks com nome ★★☆

Um rótulo de grupo em cada brick, com cabeçalhos recolhíveis e filtro. Antes de codificar, definir:
- identidade (o nome do grupo é a chave? renomear afeta todos?);
- brick compartilhado entre grupos (controller ligado a sensores de grupos diferentes);
- conexões que apontam para um grupo escondido (o fio precisa indicar que vai para algo oculto);
- **reordenar visualmente por grupo não altera a ordem real de execução**, que continua sendo a da pilha.

### E. Conjuntos prontos (presets) ★★☆

Andar WASD, Pular, Câmera seguindo, Coletar item, Porta com tecla, Vida/dano. Cada preset cria um grupo com os bricks
já ligados. É um operador Python, de risco baixo.

### F. Ver a lógica rodando ★★☆ (investigar)

Um painel ImGui (`KX_Imgui`) mostrando os bricks ativos e as propriedades do objeto selecionado. Precisa de
levantamento.

### Adiados

- **"Ao ativar"** no "Então": ligar o mesmo controller a dois actuators já cobre a execução conjunta.
- **Controller → Controller.**
- **"Esperar todos"** (Latch).

## 4. Fases

| Fase | Conteúdo | Risco | Runtime? |
|---|---|---|---|
| **F0** | Contrato fechado + levantamento: `logic_window.c`, `logic_ops.c`, conversão para KX, versioning, `.cooked`, cópia/exclusão/undo/append de bricks; decidir entre sensor novo e modo do sensor Actuator; mapear onde Action/Sound sabem que concluíram | — | Não |
| **F1a** | Estados com nome | Baixo | Não |
| **F1b** | Grupos (com as definições da seção D) | Médio (UI + persistência) | Não |
| **F2a** | Esperar + motivo de encerramento + sensor Concluído para Esperar, Action e Sound + conversão | **Médio/alto** | Sim |
| **F2b** | Ampliar o "Concluído" para outros actuators, um por vez | Médio | Sim |
| **F3** | Presets | Baixo | Não |
| **F4** | Ver lógica rodando, se o levantamento confirmar | Médio | Sim (só leitura) |

## 5. Validação

- **Compatibilidade:** abrir os arquivos do RolimaRacer e da Range original e conferir comportamento idêntico antes
  e depois.
- **Persistência:** salvar/abrir, copiar bricks entre objetos, append/link, undo/redo, excluir o actuator alvo
  (o sensor fica sem alvo sem crashar) e jogo exportado/`.cooked`.
- **Sequências, comparando por evento e não só pelo estado final:** registrar por tick a origem, o destino e a
  quantidade de disparos. Casos:
  - conclusão normal;
  - cancelamento e falha (Action sem animação, Sound sem arquivo, Esperar cancelado pelo estado), sem disparo;
  - retrigger durante o Esperar;
  - dois actuators concluindo no mesmo tick (AND e OR);
  - ciclo A → B → A, sem crescer por tick;
  - troca de estado com conclusão pendente;
  - objeto removido com conclusão pendente;
  - réplicas (Add Object) com sensores próprios;
  - "Concluído" apontando para actuator de outro objeto;
  - Fixed Timestep com vários ticks por quadro.
- **Conversão:** os mesmos casos em bricks × Component × Module, comparando o registro de eventos.
  Diferenças de ordem conhecidas entre objetos ficam documentadas.
- **Teste à mão** do usuário em F1a, F1b e F2a, antes do merge.

## 6. Riscos

- **Motivo de encerramento** espalhado pelos actuators: limitar aos suportados e manter `NONE` como padrão.
- **Ordem entre objetos:** o conversor já tem diferença conhecida aqui. Sequências entre objetos podem divergir;
  documentar e testar.
- **Réplicas e LibFree:** o sensor aponta para o actuator da réplica (`ProcessReplica`/relink, como o sensor Actuator
  já faz); limpar a conclusão pendente em `ClearAllEvents`, ao remover o sensor e ao remover o actuator alvo.
- **Grupos:** o risco é de interface e persistência, não de runtime.
- **UI do fio "Então":** um fio da 3ª coluna até a 1ª pode poluir; alternativa é mostrar só o nome do actuator no
  sensor.

## 7. Decisões em aberto (para o usuário)

1. Sensor "Concluído" com atalho "Então" na interface, em vez de link direto? (proposta: sim)
2. Primeira entrega só com Esperar, Action e Sound? (proposta: sim)
3. Esperar ignora novos positivos por padrão e cancela ao sair do estado? (proposta: sim)
4. Nomes: "Concluído"/"Então"/"Esperar" em pt-BR, "Finished"/"Then"/"Wait" em inglês?
5. Começar por F0 + F1a (estados com nome)?

## 8. Resultado da F0 (2026-10-18)

**Decisão: modo "Ao concluir" no sensor Actuator, não um sensor novo.**

- `bActuatorSensor` (`DNA_sensor_types.h`) já tem `int type`, que nenhum código lê ou grava. Ele vira o modo:
  `0` = comportamento atual (ativo/inativo), `1` = Concluído. Não muda o DNA, e arquivos antigos e da Range
  original chegam com `0`, ou seja, idênticos ao de hoje.
- Cópia (`copy_sensor`: `MEM_dupallocN` de `data`), escrita (`writefile.c`), leitura, undo e append já tratam o
  struct inteiro. O alvo é por nome, como hoje: renomear o actuator (`rna_Actuator_name_set`) não atualiza o
  sensor, e excluir o alvo deixa `m_actuator` nulo (`Evaluate` devolve falso). Esse comportamento já existe e é
  seguro; atualizar o nome ao renomear fica como melhoria opcional.
- `.cooked` guarda só hull e shaders; a lógica vem do `.range`. Sem impacto.
- Conversão: `BL_ConvertSensors.cpp` (case `SENS_ACTUATOR`) passa a ler `type` e repassa ao `SCA_ActuatorSensor`.
- RNA: nova enum `mode` em `rna_def_actuator_sensor`. UI: `draw_sensor_actuator` em `logic_window.c`.

**Motivo de encerramento** (`SCA_IActuator`: `FINISHED`/`CANCELLED`/`FAILED`, gravado quando `Update()` devolve
falso e o `SCA_LogicManager` tira o actuator da lista ativa):

| Actuator | FINISHED | CANCELLED | FAILED |
|---|---|---|---|
| Action (`BL_ActionActuator::Update`) | ramo "Handle a finished animation" (`ACT_FLAG_PLAY_END` + `IsActionDone`): Play, Ping Pong, Flipper | sobreposto por outra action na camada; pulso negativo em Loop Stop | `m_actionName` vazio; Property sem a propriedade |
| Sound (`KX_SoundActuator::Update`) | `isplaying` cai sem pulso negativo | pulso negativo com modo *Stop* | `m_sound` nulo |
| Esperar (novo) | tempo esgotado | saída do estado, objeto removido | — |

Loops sem fim (Loop Stop segurado, Sound em loop) nunca disparam o Concluído, como esperado. Desativação por
troca de estado passa por `SCA_LogicManager` linha ~150 (`Deactivate()` + `SetActive(false)`) e deve gravar
`CANCELLED`.

**Detecção no sensor:** o modo Concluído dá pulso positivo de um tick quando o actuator sai da lista ativa com
`FINISHED`; um contador de conclusões no actuator evita perder conclusões que ocorrem no mesmo tick do
reinício.

## 9. F1a já existia (2026-10-18)

O commit `6d1596fa` ("Nomes para layers da cena e states do Logic Editor") já entrega a F1a:
`Object.state_names[30][32]` no DNA (vazio = número), `sca_state_name_get` (`sca.c`), RNA
`game.state_names`, painel "States" na barra lateral do Logic Editor (visível, nome, inicial) e o nome na dica
dos botões de estado do controller, do actuator State e de `uiTemplateGameStates`.
Faltam só os extras opcionais: escolher o estado pelo nome numa lista no actuator State e um helper de nome
na API Python. Próximo passo: F1b (grupos).

## 10. F1b grupos (2026-10-18)

Feita. Cada brick (sensor, controller, actuator) ganhou `char group[32]` no DNA e `group` no RNA; vazio = sem grupo,
então arquivos antigos e da Range original continuam iguais.
Definições da seção D tomadas:
- **Identidade:** o nome é a chave, por coluna e por objeto. Bricks com o mesmo texto formam o mesmo grupo.
- **Brick compartilhado:** cada brick está em um só grupo; os fios entre grupos diferentes são desenhados normalmente.
- **Grupo escondido:** o cabeçalho recolhido mostra `Nome (n)` e recebe os fios dos bricks ocultos (botões de
  link/inlink no próprio cabeçalho), então dá para ver para onde vai cada fio e até ligar novos.
- **Ordem:** os sem grupo vêm primeiro, depois cada grupo na ordem em que aparece. É só desenho; a execução segue a
  ordem das listas.
- Recolher fica em um bit de flag de cada brick (`SENS/CONT/ACT_GROUP_HIDE`).
- O campo de grupo aparece no topo do brick expandido.
Falta o teste à mão do usuário. Renomear um grupo inteiro de uma vez ficou para depois.

## 11. F2a Esperar + Concluído (2026-10-18)

Implementada, com o teste de runtime pendente (precisa abrir o jogo).
- **Motivo de encerramento:** `SCA_IActuator::SetEndReason` (`END_NONE`/`FINISHED`/`CANCELLED`/`FAILED`) e um
  contador de conclusões (`GetFinishCount`), zerado nas réplicas.
  - Action: `FINISHED` no ramo "Handle a finished animation"; `CANCELLED` ao ser sobreposta ou parada (Loop Stop,
    Property); `FAILED` sem action ou sem a propriedade.
  - Sound: `FINISHED` quando o som que o actuator tocou chega ao fim; `CANCELLED` ao parar por pulso negativo;
    `FAILED` sem som ou quando o play não começa. `stopSound()`/`pauseSound()` do Python não contam como concluído.
- **Sensor Actuator, modo Concluído:** `bActuatorSensor.type` = `SENS_ACTUATOR_FINISHED` (1); RNA `mode`
  (`ACTIVE`/`FINISHED`). Dispara quando o contador do actuator mudou desde a última avaliação: o pulso chega no tick
  seguinte e vários no mesmo intervalo viram um. `Init()` (chamado ao voltar ao estado ativo) e o relink sincronizam o
  contador, então conclusões de quando o sensor estava fora do estado são descartadas. Python: `sensor.mode`.
- **Actuator Esperar** (`ACT_WAIT` = 27, `bWaitActuator {duration, flag}`, `SCA_WaitActuator`): tempo de lógica,
  positivos ignorados enquanto conta (opção Restart), negativos ignorados, cancela quando os controllers saem do
  estado (`IsNoLink`) ou o objeto é removido (`Deactivate`), duração zero conclui no mesmo tick. Python: `duration`,
  `useRestart`, `waiting`, `elapsed`.
- **pt-BR:** "Esperar", "Concluído" e as dicas no `pt_BR.po`.
- **logic_to_python:** Esperar e sensor no modo Concluído ficam como TODO (controller continua em brick).
- **Atalho "Então":** botão no cabeçalho dos actuators que concluem (Esperar, Action, Sound), operador
  `LOGIC_OT_actuator_then`. Cria o sensor Actuator em Concluído apontado para o actuator e um And ligado a ele, no
  estado do controller que já move o actuator. O usuário liga o And aos próximos actuators. No lugar do arrasto de
  uma saída: na UI atual um fio da 3ª coluna até a 1ª exigiria um tipo novo de link.
- Alvo sem suporte: no modo Concluído, o sensor mostra um aviso quando o actuator escolhido nunca conclui. A lista
  continua com todos os actuators (filtrar a busca exigiria um callback próprio no uiItemPointerR).
- Teste no jogo: PASS em 2026-10-18 (o runtime não imprime no stdout redirecionado; gravar o resultado em arquivo).
- Cena de teste: casos W1 (0,5 s, 1 conclusão), W0 (zero), W2 (cancelado pelo estado), W3 (Restart com pulso
  contínuo, nunca conclui), W4 (sem Restart, várias conclusões), A1 (Action sem action, falha) — imprime
  `BRICKS2 result ... PASS/FAIL`.

### F2b — Steering

- Contrato: com **Self Terminated** ligado, Concluído quando chega ao alvo (Seek e Path Following: dentro da
  distância ou no fim do caminho; Flee: longe o bastante). Pulso negativo = cancelado; sem alvo = falha. Sem Self
  Terminated ele nunca conclui, e o botão "Então" e o aviso do sensor tratam esse caso.
- Teste no jogo: PASS em 2026-10-18. Seek de x=0 até o alvo em x=10, com distância 1 e velocidade 5: concluiu uma
  vez em 1,874 s, em x=9,00. Sem alvo: nenhuma conclusão. Sem Self Terminated: nenhuma conclusão.
- ShapeAction não tem conversão no runtime (o Action cobre shape keys), então não entra. Os outros actuators
  (Motion, Camera, Scene, Property, Message...) não têm um fim natural e ficam de fora até alguém pedir um caso.

## F3 — Presets (feito)

Menu **Add › Preset** da Logic Editor (`logic.preset_add`, em `bl_operators/logic_presets.py`). Cada preset cria os
bricks já ligados num grupo com o nome do preset, traduzido:

| Preset | Bricks |
|---|---|
| Andar (WASD) | W/S movem ±0,1 em Y local; A/D giram ±0,05 rad |
| Saltar | Espaço + Ray −Z (1,1) → velocidade Z 6 (precisa de física Dynamic) |
| Câmera Seguindo | na câmera da cena: Always → Camera atrás do objeto ativo (−Y, altura 3, 5–8) |
| Coletar Item | Collision com prop `player` → End Object + Message `collected` |
| Porta com Tecla | E + Near `player` (3) → alterna `open`; `open` = True → Action em Flipper (o usuário escolhe a Action) |
| Vida e Dano | prop `health` = 100; Collision `damage` → −10; `health` < 1 → End Object |

As propriedades só são criadas quando ainda não existem. Aplicar o mesmo preset duas vezes gera nomes com `.001`.
Teste em background: os 6 presets criam os bricks, ligações e grupos esperados, e tudo sobrevive a salvar/reabrir.

## F4 — Ver a lógica rodando (feito)

Janela **Logic Bricks** no Debug Mode (`-g show_debug_mode = 1` ou opção da cena), aberta ao selecionar um objeto. Só leitura:

- estados 1-30, ativos acesos;
- sensores: positivo agora (apagado quando sem ligação no estado ativo);
- controllers: no estado ativo ou não;
- actuators: rodando, quantas vezes concluíram e o último encerramento (finished/cancelled/failed);
- a linha que acabou de ligar pisca em amarelo e some em 1 s.

Os grupos ficam só no editor; os nomes de estado chegam ao jogo (ficam no Object) e aparecem na janela.

## F5 — Histórico, pausa no disparo e nomes de estado (feito)

Na janela Logic Bricks:

- **History**: as últimas 50 ocorrências *diferentes* do objeto (sensor ficou positivo, controller disparou,
  actuator começou, actuator concluiu/foi cancelado/falhou), a mais nova em cima. Repetir uma ocorrência a sobe
  para o topo e soma na coluna "x". Botão Clear; troca de objeto limpa.
- **Pausar no disparo**: clicar no nome de um brick o marca (vermelho, `*`). Quando ele disparar, todas as cenas
  são suspensas; o botão de pausa da barra continua.
- Sensores e actuators contam as próprias subidas (`SCA_ISensor::GetRiseCount`, `SCA_IActuator::GetStartCount`),
  então pulsos de um tick entre dois quadros (State, Property, Message) também entram no histórico e pausam.
- **Nomes de estado**: "Active: Normal" em verde, nome na dica dos quadradinhos e na coluna dos controllers
  ("off (Hurt)").

## F6 — Mais presets e cena tutorial (feito)

| Preset | Bricks |
|---|---|
| Inimigo que Persegue | Near `player` (10, solta em 12) → Steering Seek no objeto com `player` (3 u/s, para a 1) |
| Checkpoint e Renascer | Python `logic_checkpoint.py`: guarda o início; Collision `checkpoint` salva o lugar; Collision `kill` volta |
| Botão de Menu | Mouse Over + Left Click → Scene Set (o usuário escolhe a cena); liga o cursor do mouse |
| Plataforma que Vai e Volta | estados Going/Returning; em cada um Motion por tick + Wait 2 s; "Então" troca o estado |

O inimigo precisa de física Dynamic: Steering num objeto Static anda só um passo.

Cena tutorial: `docs/logic-bricks-2-tutorial.blend`, gerada por `tools/debug/cenas/criar_cena_bricks2_tutorial.py`
(com um segundo argumento cria o Checker do teste automático). Tem jogador (Walk, Jump, Checkpoint, estados
Normal/Hurt com Wait + "Então"), câmera, moeda, porta com Action, checkpoint, inimigo, plataforma e o texto
"LEIA-ME". Teste: a plataforma faz os estados 1,2,1 e anda 3,6; o inimigo alcança o jogador, que fica em Hurt
1,5 s e volta ao Normal; marcar "To Returning" pausa o jogo aos 2 s.

## F7 — Actuator Vídeo (feito)

Novo `ACT_VIDEO` (28, `bVideoActuator`: objeto, segundos, modo, flag) que comanda o componente Video Player
(`anastacio_video.VideoPlayer`) do objeto escolhido, ou do próprio objeto se o campo ficar vazio. No jogo é
`KX_VideoActuator`, que procura o componente com o atributo `anastacio_video` e chama os métodos dele.

| Modo | Faz | Concluído |
|---|---|---|
| Play / Restart | toca (Restart volta ao 0 antes) | quando o vídeo acaba; em loop nunca. Pausar, parar ou sair do estado: cancelado |
| Play/Pause | pausa se está tocando, senão toca | como Play quando toca; na hora quando pausa |
| Pause / Stop / Seek | na hora | no mesmo tick |

Seek usa Segundos; com Relativo soma ao tempo atual. O tempo fica entre 0 e a duração. Se o comando chega
antes do `start()` do componente (Always no primeiro tick), ele espera um tick. Sem Video Player no objeto:
falhou, com um aviso no console.

Teste headless (`--server`): Seek concluído no mesmo tick; Play depois do Seek para 3 s concluiu; o "Então" do
Play deu Restart; o Pause cancelou o Restart sem concluir.
