# Logic Bricks 2.0 — plano e referência

Estado: **mesclado no main em 2026-10-18 (`4b97ddea`)**. F0 a F7 feitas. Falta o teste à mão do usuário
(seção "Pendências"). Este arquivo guarda o contrato técnico (seções 8 e 11), citado por
[logic-tree-plan.md](logic-tree-plan.md).

## Princípios (valem para mudanças futuras)

1. **Nada quebra.** Arquivo antigo (inclusive da Range original 1.6.1002, que pula o nosso versioning) abre e roda
   igual. Campo novo zerado vale o comportamento antigo. Cada campo novo também passa por serialização, leitura,
   remapeamento de ponteiros, cópia, exclusão, undo/redo e append/link.
2. **Nativo.** Runtime em C++, sem custo de Python; roda em Web/Android.
3. **Modelo sensor → controller → actuator mantido.** Recurso novo entra como sensor, controller ou actuator.
4. **Convertível.** Recurso novo entra no `logic_to_python.py`, validado por eventos.
5. **Iniciante primeiro.** O recurso é descobrível olhando para a tela.

## Fases (resumo)

| Fase | Entrega |
|---|---|
| F0 | Contrato e levantamento (seção 8) |
| F1a | Estados com nome: já existia no commit `6d1596fa` (`Object.state_names`, painel States) |
| F1b | Grupos de bricks com nome (`group[32]` no DNA/RNA; cabeçalho recolhível `Nome (n)` recebe os fios dos ocultos; reordenar é só desenho) |
| F2a | Esperar + motivo de encerramento + sensor Actuator em modo Concluído + atalho "Então" (seção 11) |
| F2b | Steering com Self Terminated conclui ao chegar ao alvo; PASS no jogo em 2026-10-18 |
| F3 | Presets no menu Add › Preset (`bl_operators/logic_presets.py`): Andar, Saltar, Câmera Seguindo, Coletar Item, Porta com Tecla, Vida e Dano |
| F4 | Janela Logic Bricks no Debug Mode: estados, sensores, controllers e actuators ao vivo (só leitura) |
| F5 | Histórico das últimas 50 ocorrências, pausar no disparo de um brick, nomes de estado no jogo |
| F6 | Presets Inimigo que Persegue, Checkpoint e Renascer, Botão de Menu, Plataforma que Vai e Volta; cena tutorial `docs/logic-bricks-2-tutorial.blend` (gerada por `tools/debug/cenas/criar_cena_bricks2_tutorial.py`) |
| F7 | Actuator Vídeo (`ACT_VIDEO` = 28, `KX_VideoActuator`) comanda o componente Video Player; Play conclui no fim do vídeo, Pause/Stop/Seek no mesmo tick |

## 8. Resultado da F0 (2026-10-18)

**Decisão: modo "Ao concluir" no sensor Actuator, não um sensor novo.**

- `bActuatorSensor` (`DNA_sensor_types.h`) já tinha `int type`, que nenhum código lia. Ele vira o modo:
  `0` = ativo/inativo (antigo), `1` = Concluído. Não muda o DNA; arquivos antigos chegam com `0`.
- Cópia, escrita, leitura, undo e append já tratam o struct inteiro. O alvo é por nome: renomear o actuator
  não atualiza o sensor, e excluir o alvo deixa `m_actuator` nulo (`Evaluate` devolve falso). É seguro.
- `.cooked` guarda só hull e shaders; a lógica vem do `.range`.
- Conversão: `BL_ConvertSensors.cpp` (case `SENS_ACTUATOR`) lê `type`. RNA: enum `mode` em
  `rna_def_actuator_sensor`. UI: `draw_sensor_actuator` em `logic_window.c`.

**Motivo de encerramento** (`SCA_IActuator`: `FINISHED`/`CANCELLED`/`FAILED`, gravado quando `Update()` devolve
falso e o `SCA_LogicManager` tira o actuator da lista ativa):

| Actuator | FINISHED | CANCELLED | FAILED |
|---|---|---|---|
| Action (`BL_ActionActuator::Update`) | ramo "Handle a finished animation": Play, Ping Pong, Flipper | sobreposto por outra action; pulso negativo em Loop Stop | `m_actionName` vazio; Property sem a propriedade |
| Sound (`KX_SoundActuator::Update`) | `isplaying` cai sem pulso negativo | pulso negativo com modo *Stop* | `m_sound` nulo |
| Esperar | tempo esgotado | saída do estado, objeto removido | — |

Loops sem fim nunca disparam o Concluído. Desativação por troca de estado passa por `SCA_LogicManager`
(`Deactivate()` + `SetActive(false)`) e grava `CANCELLED`.

**Detecção no sensor:** pulso positivo de um tick quando o actuator sai da lista ativa com `FINISHED`; um contador
de conclusões no actuator evita perder conclusões no mesmo tick do reinício.

## 11. F2a Esperar + Concluído (2026-10-18)

- **Motivo de encerramento:** `SCA_IActuator::SetEndReason` (`END_NONE`/`FINISHED`/`CANCELLED`/`FAILED`) e contador
  `GetFinishCount`, zerado nas réplicas. Sound: `stopSound()`/`pauseSound()` do Python não contam como concluído.
- **Sensor Actuator, modo Concluído:** `SENS_ACTUATOR_FINISHED` (1); RNA `mode` (`ACTIVE`/`FINISHED`). Dispara
  quando o contador mudou desde a última avaliação: o pulso chega no tick seguinte e vários viram um. `Init()` e o
  relink sincronizam o contador, então conclusões de fora do estado são descartadas. Python: `sensor.mode`.
- **Actuator Esperar** (`ACT_WAIT` = 27, `bWaitActuator {duration, flag}`, `SCA_WaitActuator`): tempo de lógica,
  positivos ignorados enquanto conta (opção Restart), negativos ignorados, cancela quando os controllers saem do
  estado (`IsNoLink`) ou o objeto é removido, duração zero conclui no mesmo tick. Python: `duration`,
  `useRestart`, `waiting`, `elapsed`.
- **Atalho "Então":** botão no cabeçalho dos actuators que concluem; operador `LOGIC_OT_actuator_then`. Cria o
  sensor Actuator em Concluído e um And ligado a ele, no estado do controller que move o actuator.
- Alvo sem suporte: o sensor mostra aviso quando o actuator nunca conclui (a lista não é filtrada).
- Teste no jogo: PASS em 2026-10-18 (casos W0–W4 e A1, imprime `BRICKS2 result ... PASS/FAIL`; o runtime não
  imprime no stdout redirecionado, gravar em arquivo).

## Pendências

- **Teste à mão do usuário** de F1b (grupos), F2a (Esperar, Concluído, "Então") e da cena tutorial no editor.
- `logic_to_python`: Esperar e sensor em modo Concluído ainda são TODO (o controller fica em brick).
- Opcionais: escolher o estado pelo nome no actuator State; helper de nome de estado na API Python; renomear um
  grupo inteiro de uma vez; atualizar o sensor ao renomear o actuator alvo.
- Adiados: "Ao ativar" no "Então", Controller → Controller, "Esperar todos" (Latch), unidade em quadros no Esperar.
- Outros actuators (Motion, Camera, Scene, Property, Message...) não têm fim natural e ficam sem Concluído até haver
  caso de uso. ShapeAction não tem conversão no runtime.
- Limite conhecido: sequências entre objetos podem divergir na conversão para Python (diferença de ordem já
  registrada no conversor).
