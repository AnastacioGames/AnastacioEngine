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

## Peças

### 1. Botão e ícone

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

## Fases

1. Botão + ícone + operador que só inicia o Play com flag de gravação.
2. Captura de transformação em memória + conversão em Action ao parar
   (primeiro resultado visível).
3. Estado de animação (actions/NLA) na captura.
4. Take em DNA + reprodução no runtime + camadas.
5. Painel de takes, contagem, câmera, standalone.
6. Cutscene, API Python e controle rápido.

Uma fase por vez, com build no Windows e teste do usuário antes da próxima.

## Em aberto

- Gravar também no player standalone (precisa devolver o take ao editor por
  arquivo) ou só no Play embutido.
- Frequência de amostragem: todo frame lógico ou taxa fixa (ex. 30 Hz).
- Física de atores em reprodução: viram cinemáticos ou mantêm colisão.
