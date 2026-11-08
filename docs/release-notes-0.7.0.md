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
- **Track Tool:** gerador de pistas com faixas, inclinação, cenário e terreno.
- **Minimap na UI Tree:** Add, Bake, mapa inteiro, marcador e Show on Minimap com cor por objeto.

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

- Vários crashes corrigidos, achados por varredura automática de operadores: redo depois de passo em Edit Mode,
  `G` no Node Editor quando a área muda, criação de links com prévia rodando e `joint_rotation`, entre outros.
- Normal maps não ficam mais pretas no Adreno, e o Static Batch funciona na Web sem `glMultiDrawElements`.
- Export standalone leva módulos de runtime, arquivos do projeto e `.cooked` com os assets; o Export Web leva os
  `.range` usados por LibLoad, as falas de cutscene e as vozes de Take.
- Runtime: `end()` + `addScene` no mesmo frame, mensagens de erro do LibLoad e fonte padrão no player.
- Arquivos antigos recebem os valores certos de sombra em cascata, Light LOD e resolução dinâmica.
- Mudar cores e valores do céu não trava mais a 3D View.
- Teclas sem mapeamento (como Print Screen) não disparam mais controles vazios.

## Downloads

- `AnastacioEngine-0.7.0-windows-x64.zip`: editor e runtime para Windows, portátil (extraia e rode).
- `RangeArmor-0.7.0-windows-x64.zip`: ferramenta para criar e empacotar projetos (Windows).
- `SHA256SUMS.txt`: hashes para conferir o download.

No Windows: extraia e abra `AnastacioEngine.exe`.
