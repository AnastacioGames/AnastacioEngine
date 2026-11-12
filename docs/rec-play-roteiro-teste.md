# Rec Play: roteiro de teste com janela

Anote em cada passo: OK, ou o que aconteceu de diferente. Cada bloco leva poucos minutos.

## 1. Gravar e assistir (Rec Studio)

1. Abra **Window > Rec Studio**.
2. Em **Scenery**, arraste o Park para a cena. Esperado: o cenário aparece.
3. Em **Characters**, arraste o Hero. Esperado: ele vira ator sozinho.
4. Em **Actions**, arraste Run sobre o Hero. Esperado: a ação aparece no painel do ator.
5. Clique em **Record**, mova o ator com WASD e pare com **F10**. Esperado: contagem nítida, `REC` com o tempo, e o Take na lista.
6. Clique em **Watch**. Esperado: o movimento é igual ao que você gravou.
7. Clique em **Rerecord** e grave outro movimento. Esperado: continua um Take só, com o movimento novo.
8. Clique em **Undo**. Esperado: desfaz a última gravação.

## 2. Levar o Take para a cutscene

A gravação não cria evento sozinha; o evento nasce do botão **Add to Cutscene**.

1. Na janela principal, abra a aba **Render** e o painel **Motion Recording (Experimental)**.
2. Selecione o Take na lista e clique em **Add to Cutscene**.
3. Abra **Cutscene Sequences**. Esperado: existe uma sequência, e nela um evento Play Take com o nome do Take.
4. Clique duas vezes no Take e renomeie para `Intro`. Esperado: o evento passa a usar `Intro`.
5. Grave um segundo Take e use **Add to Cutscene** de novo. Esperado: o evento entra depois do primeiro.
6. Aperte `P`. Esperado: os atores repetem a gravação (Add to Cutscene liga **Play on Start** na sequência).

## 3. Pular e parar a cutscene

Com um script que chame `scene.skip_cutscene()` ou `scene.stop_cutscene()`:

1. Pule no meio do Take. Esperado: o ator vai para a pose final e a física e a lógica voltam.
2. Pare no meio do Take. Esperado: o ator fica onde está e volta a responder.

## 4. Generate Keyframes desligado

1. Em **Motion Recording**, abra as opções avançadas e desligue **Generate Keyframes**.
2. Use um personagem com armature e ação. Grave e clique em **Watch**.
3. Esperado: o corpo se move e a animação toca junto.
4. Religue a opção. Esperado: a Action `Rec_...` aparece na timeline, como no seu print.

## 5. Use Take e objeto em osso

1. Selecione o Take e clique em **Use Take**. Esperado: a timeline toca o movimento no editor.
2. Prenda um objeto a um osso de um ator, grave e clique em **Use Take**. Esperado: o objeto acompanha a mão e não sai voando.

## 6. Durante o jogo

1. Dê Play com a UI ao vivo, toque um Take e tente clicar em `-` na lista de Takes. Esperado: a remoção é recusada e a engine não trava.
2. Grave com **Sample Rate** fixo em 1 ou 2 num personagem com ação. Esperado: a animação toca no Watch.

## 7. Painel fora do Rec Studio

1. Abra a barra **N** numa 3D View comum. Esperado: o bloco Rec Studio não aparece.
2. Abra a barra N no Rec Studio. Esperado: Record, Watch, Rerecord e Undo aparecem.

## Sabidamente limitado

- Cada cenário solto cria uma cópia (`Park`, `Park.001`).
- O Rec Studio não mostra mensagens de erro na tela.
- `ae_rec_takes.remove()` por script durante o jogo ainda pode travar a engine.
