# AnastacioEngine 0.7.0

A engine agora ouve: microfone no jogo e no editor. Esta versão também traz o Rec Play para gravar cenas jogando,
luz indireta por volumes de sondas, texturas KTX2 e FSR 1, além de muitas correções vindas de testes automáticos.

## Novidades

### Microfone e gravação de voz

- **Botão Record na barra superior do editor:** um clique grava direto para o Sequencer. Ao lado ficam as opções:
  gravar um som novo, escolher o microfone, ajustar o som e abrir o Video Sequencer numa janela separada. Enquanto
  grava, o botão fica vermelho com o tempo e o volume.
- **Gravar onde o som é usado:** botão de gravar na fala da cutscene, no nó Sound da Logic Tree e nos strips de
  som do Sequencer.
- **Ajustar Som:** corte, fades, normalizar e efeitos de voz, salvos num WAV novo.
- **Microfone no jogo:** `Range.audio.microphone*`, `playVoice` e `playLive`, com efeitos de voz e reverb. Sensor
  Microphone, atuador Voice, nós When Talking e Voice na Logic Tree, e peças de UI (Microphone Meter e Enable
  Microphone).
- **Web e Android:** microfone por `getUserMedia`, com opção no export. O APK só pede `RECORD_AUDIO` se o jogo usar.

### Criação e animação

- **Rec Play:** grave o que acontece jogando em Takes, com camadas, regravação, janela Rec Studio e botão Movie.
  Os Takes podem entrar numa Cutscene.
- **Personagem automático:** do Fuse ao personagem riggado, sem Mixamo, por File > Import > Fuse Character.
- **Posturas do Character:** abaixar, rastejar e encolher no pulo, com velocidade por postura, auto crouch e
  configuração na aba de física e na Logic Tree.
- **Track Tool:** gerador de pistas com faixas, inclinação, cenário e terreno.
- **Minimap na UI Tree:** Add, Bake, mapa inteiro, marcador e Show on Minimap com cor por objeto.

## Melhorias

### Gráficos e desempenho

- **Light Probe Volumes:** luz indireta por grade de sondas numa caixa Empty, com ajuste automático pelo Quality
  Preset.
- **Automatic Occluders:** escolhe os occluders ao carregar e liga ou desliga a oclusão sozinho. Vem desligado por
  padrão.
- **KTX2 / Basis Universal:** um arquivo de textura que vira BC, ETC2 ou ASTC ao carregar. DDS BC5 para normal maps
  e upload comprimido de DDS na Web.
- **FSR 1** como upscale padrão da resolução dinâmica.
- **Chuva com superfícies molhadas:** escurece e dá brilho enquanto chove, e seca depois.
- **Game Trace e Trace Doctor:** relatório que explica como corrigir o problema encontrado.

### Editor

- Video Sequencer agora aparece direto no menu de editores, na coluna Animation.
- Botões de Play e voltar ao início no cabeçalho do Sequencer.
- Listas longas de nós abrem em duas colunas, para caber na tela.
- Textura de fundo no tema e opções novas na 3D View.
- Addon Sprytile 0.4.6 incluído, desativado por padrão.

## Correções

### Crashes

- Redo depois de um passo em Edit Mode.
- `G` no Node Editor quando a área muda no meio da operação.
- Criação de links de nós com a prévia rodando.
- `joint_rotation` em animação.
- Vários outros, achados por varredura automática de operadores.

### Colisão do Character

- A cápsula acompanha a malha, inclusive em personagens fora do centro e com escala.
- Mudança de escala em tempo de jogo enquanto abaixado.
- Pares de colisão são limpos quando a forma muda.

### Editor e nós

- Mudar cores e valores do céu não trava mais a 3D View.
- UI Tree com fake user ao salvar, e diálogos reabrem com a mesma fala.
- Logic Tree: valores iniciais em Add to Property e Wait; Go To State lista só Frames de Estado.
- Collada exporta textura DDS/KTX2 empacotada como PNG.
- Correções em Dope Sheet, `curve.draw`, UV Follow Active Quads e painéis.

### Jogo e Python

- `end()` + `addScene` no mesmo frame.
- Mensagens de erro mais claras no LibLoad e no VideoTexture.
- `KX_MeshBuilder` não perde vértices.
- `setActionFrame` com speed 0.
- Fonte padrão registrada no player.
- Teclas sem mapeamento (como Print Screen) não disparam controles vazios.

### Gráficos

- Normal maps não ficam mais pretas no Adreno.
- Static Batch não perde mais o sol e as sombras.
- Geometry Instancing fica fora do Static Batch.
- Nuvens sem quadriculado na viewport.
- Interpolação do Fixed Timestep sem erro de culling.

### Export e Web

- Export standalone leva módulos de runtime, arquivos do projeto e `.cooked` com os assets.
- Export Web leva os `.range` usados por LibLoad, as falas de cutscene e as vozes de Take.
- Static Batch na Web sem `glMultiDrawElements`.
- A Web não prende mais a CPU para limitar o FPS.

### Arquivos antigos

- Valores certos de sombra em cascata, Light LOD e resolução dinâmica.

## Downloads

- `AnastacioEngine-0.7.0-windows-x64.zip`: editor e runtime para Windows, portátil (extraia e rode).
- `RangeArmor-0.7.0-windows-x64.zip`: ferramenta para criar e empacotar projetos (Windows).
- `AnastacioEngine-0.7.0-linux-x86_64.tar.xz`: editor e runtime, portátil, com as bibliotecas incluídas.
- `RangeArmor-0.7.0-linux-x86_64.tar.xz`: ferramenta para criar e empacotar projetos (Linux).
- `SHA256SUMS.txt`: hashes para conferir o download.

No Windows: extraia e abra `AnastacioEngine.exe`.

No Linux: extraia, abra `AnastacioEngine` e, se quiser o ícone no menu, rode `./install-desktop.sh`.
