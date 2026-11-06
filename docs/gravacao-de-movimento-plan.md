# Plano — Gravação de movimento (Rec Play)

## Objetivo

Gravar animação controlando o personagem ao vivo, como nos programas de "filme
em tempo real" dos anos 90 (referência de ideia: Microsoft 3D Movie Maker,
1995). O usuário escolhe o personagem, aperta **Rec Play**, joga, e ao parar a
engine guarda o que aconteceu. Gravações se empilham em camadas: grava o
personagem A, depois grava B enquanto A repete a gravação dele.

Implementação própria, do zero, sobre a base Blender 2.79/UPBGE. Nenhum código,
nome, ícone ou conteúdo do 3D Movie Maker entra na engine (o código dele é MIT,
mas a arquitetura não encaixa e as marcas não são licenciadas).

## Decisões confirmadas (usuário, 2026-11-06)

- **Botão próprio**, separado do Play, com ícone novo: bola vermelha de
  gravação junto de uma seta de play/filme. Desenho original (homenagem de
  ideia, sem copiar arte da Microsoft).
- **Saída nos dois formatos**: keyframes editáveis (Action do Blender) e um
  formato próprio de gravação ("take") para reprodução exata.

- **Público**: primeiro o próprio usuário, mas feito para outras pessoas se
  divertirem criando os jogos delas.
- **Destino**: principal é usar dentro do jogo; filme exportado também é desejado.
- **Teste de aceite**: começar por algo simples e ir completando.
- **Experimental**: marcado como "(Experimental)" na engine até ficar bom, porque
  sairá uma versão antes de o recurso estar completo.
- **Liberdade**: o 3D Movie Maker é o conceito; usar o que a engine tem e fazer melhor.

## Regra principal: fácil como brinquedo

O usuário usou o 3D Movie Maker quando criança; o recurso tem de ser usável
por quem nunca abriu o editor:

- Painel em três passos numerados: **1. escolher o personagem**, **2. escolher
  o que ele faz** (uma Action da lista, ou vazio = controles do próprio jogo),
  **3. Rec Play e mexer**. Tudo o mais fica fechado em **Advanced**.
- Padrões que funcionam sem mexer em nada; nenhum termo técnico nos três passos.
- Na gravação: contagem grande na tela, aviso "REC" piscando, e parar com Esc
  já salva. Sem diálogo de confirmação.
- Depois de gravar, botão "Assistir" e "Regravar" no mesmo painel.
- Controle rápido (Fase 4) sobe de prioridade: personagem sem lógica deve
  andar com setas/WASD e tocar a Action escolhida, sem montar Logic Bricks.

## Peças

### 1. Botão, ícone e painel

- Painel **Motion Recording** em Properties > Render (System), depois de
  Player, com as configurações (`Scene.ae_rec_*`, `Object.ae_rec_actor`).
  Feito em 2026-11-06.

- Ícone novo `REC_PLAY` num espaço `DEF_ICON_BLANK` livre de `UI_icons.h`,
  mesmo caminho do ícone `COOK`: `.dat` 16/32 do atlas embutido e PNGs de
  `icons_blender5` e `icons_upbge`. `tools/check_ui_icons.py` tem de passar.
- Em `uiTemplateHeader3D_game_controls` (`view3d_header.c`), botão
  **Rec Play** logo depois de **Play**, chamando um operador novo
  `VIEW3D_OT_game_record` (ao lado de `VIEW3D_OT_game_start` em
  `view3d_view.c`). Também na barra flutuante da 3D View, como o Cook.
- O operador reutiliza o mesmo caminho do Play embutido; só liga a gravação.

### 2. O que é gravado

- **Atores**: objetos marcados com `Record Actor` (propriedade nova do
  objeto, painel próprio). Sem nenhum marcado, grava o objeto ativo.
- Por frame lógico, para cada ator: transformação de mundo (posição, rotação,
  escala) e estado do `BL_ActionManager` de cada camada (action, frame,
  peso, blend). Armatures: as actions tocadas, não pose por osso (fica leve e
  continua editável).
- Câmera ativa também pode ser ator (gravar movimento de câmera).
- Contagem 3-2-1 antes de começar; tecla para parar (padrão `Esc` = parar e
  salvar, como o Play).
- Captura em C++ no fim de cada frame do `KX_Scene` (depois da física), num
  buffer na memória. Nada de Python por frame.

### 3. Formato próprio (take)

- Struct DNA nova na cena: lista de takes (nome, fps, atores, amostras
  compactadas). Persistência no `.range`, igual à decisão do Cutscene: o
  arquivo da cena é a fonte de verdade; export/import de arquivo externo só
  como intercâmbio, depois.
- Reprodução exata no runtime: um ator com take ativo ignora a própria lógica
  e segue o take (interpolando entre amostras).
- Editar DNA exige rebuild limpo (`ninja -t clean`, ver AGENTS.md).

### 4. Keyframes (Action)

- Ao parar, o editor converte o take em uma Action por ator: F-Curves de
  loc/rot/scale com simplificação (remove keyframes redundantes dentro de
  tolerância) e as actions tocadas como strips no NLA.
- Opção "Gerar keyframes" ligada por padrão; o take continua guardado.

### 5. Camadas

- Ao gravar de novo, atores que já têm take tocam a gravação deles; só os
  atores marcados para esta gravação ficam no controle do jogador.
- Por ator: regravar, apagar take, escolher take ativo.

### 6. Integração (depois)

- Evento de Cutscene "Play Take" (ver
  [plano do Cutscene](cutscene-native-integration-plan.md)).
- API Python: `scene.takes`, `obj.play_take(name)`.
- Controle rápido opcional estilo 3DMM (andar com o mouse/WASD e escolher a
  ação numa lista) para quem não tem lógica de personagem pronta.

### 7. Janela Rec Studio (decidido 2026-11-06)

Janela flutuante própria, como no 3D Movie Maker, aberta por
**Window > Rec Studio** ou pelo Rec Play. Montada com peças existentes, pelo
mesmo caminho da janela flutuante do Asset Browser
(`SCREEN_OT_asset_browser_show`, `WM_WINDOW_ASSETS` em `screen_ops.c` e
`wm_window.c`):

- em cima, 3D View grande pela câmera;
- embaixo, miniaturas em abas Cenários / Personagens / Ações (o Asset Browser
  sem menus técnicos);
- na lateral, botões grandes: Gravar, Parar, Assistir, Regravar, Desfazer;
- linha do tempo simples com uma faixa por personagem (camadas).

O editor normal não muda; o painel Motion Recording continua para detalhes.

Feito em 2026-11-06 (`SCREEN_OT_rec_studio_show`, painel `VIEW3D_PT_rec_studio`). Diferenças do desenho:

- Não há botão Parar: o editor fica parado durante o jogo, então F10 para.
- A linha do tempo está no painel lateral: uma faixa por personagem, com o último Take dele.
- A barra de caminho continua visível. O conteúdo inicial vem do kit `rec_kit` (Fase 9).
- Teste: `tools/debug/editor_rec_studio.py` abre por tecla e clica de verdade. Abrir por script com contexto
  falso cria as sub-regiões na janela errada e a área de baixo não desenha.

### 8. Asset Browser (miniaturas)

Base: [Asset Browser](asset-browser.md). Falta:

- incluir Actions no filtro do modo Assets (hoje só OB, GR, MA);
- miniatura de Action (personagem renderizado numa pose do meio);
- soltar uma Action sobre um personagem na 3D View
  (`VIEW3D_OT_asset_drop`, como o material): define `ae_rec_action`;
- soltar um personagem já o marca como `ae_rec_actor`;
- kit inicial de conteúdo (personagens e ações), podendo usar o
  Personagem automático (Fuse → armature).

## Ideias vistas no 3DMMEx (2026-11-06)

Leitura de `src/engine/actor.cpp` e `movie.cpp` do [3DMMEx](https://github.com/benstone/3dmmex).
Só ideias de comportamento, para reimplementar do nosso jeito; nenhum código entra.

- **Gravação começa ao mexer**: o botão arma a gravação, mas ela só inicia quando o
  ator anda um pouco ou passa um tempo curto (~0,75 s). Evita take com início parado.
  Pode substituir a contagem quando ela estiver em 0.
- **Regravar a partir daqui**: regravar apaga só o que vem depois do frame atual e
  emenda no trecho anterior, em vez de refazer o take inteiro.
- **Trechos dentro do take**: cada gravação é um trecho que pode ser movido, adiantado
  ou atrasado no tempo, sem regravar.
- **Eventos além da posição**: troca de ação guardada como evento na linha do tempo, não
  por amostra. Combina com a Fase 3: só gravar quando a action muda.
- **Congelar andando**: tecla que desliza o ator sem avançar a animação (Shift no 3DMM).
- **Suavizar a entrada**: média simples do movimento antes de gravar, útil no mouse.
- **Falha restaura**: guardar o estado anterior antes de gravar e voltar a ele se der erro.
- **Não copiar**: o caminho por distância ("onde", não "quando") do 3DMM. O próprio
  código admite que complicou muito; nosso take continua por tempo.

## Decisões da revisão (2026-11-06)

Plano revisado contra o código; o usuário aceitou as sugestões abaixo.

- **Ator** = objeto marcado mais todos os filhos (cápsula com armature filha).
- **Quem controla o ator gravado**: a lógica do jogo, se houver; se não, controle
  rápido com WASD.
- **O resto do jogo** roda normalmente durante a gravação.
- **Ator repetindo** não colide por padrão (`Collide on Replay`).
- **Só Play embutido**: Standalone fora do escopo por enquanto.

Regras técnicas que saíram da revisão:

- **Flag**: chave `rec_play` por `SYS_WriteCommandLineInt`, escrita em toda execução
  de `game_engine_exec` (0 no Play comum). Sem DNA.
- **Buffer fora da cena**: `StopEngine` destrói as cenas. A gravação fica em C na
  blenkernel, como `BKE_screencast.h`, e vira Action no editor, depois de
  `StartKetsjiShell`. Só gravar quando o Main do jogo é o do editor.
- **Relógio único**: `t` soma o passo do jogo só em passo não suspenso; todos os
  atores usam o mesmo `t`. Sincronia por `t`, não por índice de amostra.
- **Captura** dentro de `KX_SimulationPipeline::Update`, depois de `UpdateParents`,
  com lista própria de atores (sem varrer todos os objetos por frame).
- **Repetição**: marca própria no objeto, respeitada por `UpdateActivity`.
  `SuspendDynamics` não vale para Character: política por tipo de física.
- **Action**: Euler (quaternion não funciona no jogo), curvas lineares, não sobrescrever
  a gravação anterior, `ED_undo_push`, tolerância por canal.
- **Parada**: tecla própria em gravação, porque um sensor na tecla de saída bloqueia o
  Esc. Qualquer saída salva; Esc na contagem cancela.
- **Câmera**: sem câmera real o jogo usa `__default__cam__`, que não tem objeto. Gravar
  câmera exige uma câmera real.
- **Reprodução exata** só vem com o take. Gravar actions é leve e editável, mas não
  cobre IK e scripts; reservar no formato um bloco para pose por osso.
- **Regravar parcial** pula os atores para `t`, mas o mundo volta ao início.
- **Rec Studio** não usa `WM_window_open_temp` (uma só janela temporária). O Play embutido em
  segunda janela foi provado em 2026-11-06 com `tools/debug/editor_rec_janela2.py`.

A testar: ordem do Euler no jogo, Ctrl+Z após gravar, travada ao tocar take longo,
`PointerProperty` com `prop_search` para `ae_rec_action`.

## Fases

A Fase 7 trouxe o DNA do Take (`MotionTake`). O recurso fica marcado como Experimental.

1. Botão, ícone, operador e flag. Instruções em [`HANDOFF-rec-play.md`](../HANDOFF-rec-play.md).
2. Captura de transformação, relógio, parada segura e Action com undo. Teste: cubo
   e personagem físico. Bom ponto para a versão Experimental.
2.5. Organização (decidido 2026-11-06): Take agrupa as Actions de uma gravação, lista no painel, Max
   Duration, contador REC na tela, substituir o Take selecionado. Fluxo: gravar primeiro e depois mandar
   para o Cutscene.
2.6. Evento Play Take no Cutscene e botão Add to Cutscene no Take.
3. Personagem completo: filhos, actions e NLA.
4. Controle rápido (WASD sem Logic Bricks), contagem e aviso REC.
5. Camadas pela Action: repetir A enquanto grava B, Assistir e Regravar.
6. Filme pelo Screencast, ligado no Assistir.
7. Take em DNA versionado, com eventos e reprodução exata.
8. Janela Rec Studio.
9. Asset Browser: Actions, miniaturas, soltar ação/personagem, kit de conteúdo. Feito em 2026-11-06, falta aceite visual.
10. API Python. Feito em 2026-11-06, ver [rec-play-api.md](rec-play-api.md).

Uma fase por vez, com build no Windows e teste do usuário antes da próxima.

## Em aberto

- Frequência de amostragem padrão: todo passo lógico ou taxa fixa.
- Repetição no jogo: no lugar gravado ou relativa ao objeto (NPC).
- Sons do jogo na repetição e narração por microfone.
- Gravação ao trocar de cena: hoje a ideia é fechar o take.
- Quantas gravações guardar.
