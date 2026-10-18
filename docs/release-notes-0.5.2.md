# AnastacioEngine 0.5.2

Versão com Logic Bricks 2.0, Video Player nativo, texto do jogo com atlas bitmap, sons de efeito automáticos
e um SSGI e um CSM mais fáceis de usar, além de várias correções de vídeo, sombras e interface.

## Novidades

### Logic Bricks 2.0

- **Grupos de bricks** com cabeçalho recolhível, lista de grupos na barra lateral e botões para mover grupos
  para cima e para baixo nas colunas.
- **Actuator Wait** e modo **Finished** no sensor Actuator: dá para encadear ações ("quando terminar, faça").
- Botão **Then** no actuator: cria o sensor Finished e o controller And já ligados.
- O Steering com Self Terminated avisa o sensor Actuator quando chega; o editor avisa quando um Finished
  aponta para um actuator que nunca termina.
- **Actuator Video**, que controla o Video Player.
- **Presets** de lógica em Add > Preset, **histórico** da lógica, **pausar ao disparar** e uma cena tutorial
  (`docs/logic-bricks-2-tutorial.blend`).
- Janela **Logic Bricks no Debug Mode** mostrando a lógica rodando e **Highlight Active**: os bricks acendem
  ao vivo quando disparam.
- Colunas mais largas e cabeçalho do objeto alinhado com os bricks.
- **Logic Bricks → Python** converte também Wait, Video e Finished.

### Video Player

- Componente **Video Player** com painel na aba Object, controlado por Python ou pelos Logic Bricks.
- **Fade** para cutscenes em tela cheia e **legendas `.srt`** (com botão de legenda de exemplo).
- Texturas de vídeo mais nítidas e mais rápidas.
- O export do jogo copia os vídeos usados pelo Video Player.

### Texto

- **Atlas bitmap** para o Text do jogo: gerado a partir da fonte, com estilos e suporte a cirílico e kana.
- **Preview do Game Text** na viewport, com opção de esconder o texto original e limites de Text-Res.
- Edit Externally abre o editor do sistema quando não há outro configurado.
- Text Editor com barras de ferramentas flutuantes, painel de legendas, barra lateral em caixas e fechar abas
  pelo botão direito.

### Render, sombras e efeitos

- **SSGI nativo** mais fácil: o painel mostra só o que impede o efeito, com o conserto ao lado, e o
  **Check Scene** gera um relatório da cena. Suporte a Mix/Add Shader, closures aproximadas, Alpha Clip e a
  opção Approximate Unsupported.
- **SSGI mais suave**: amostragem intercalada, upsampling bilateral e opção **Denoise**.
- **CSM** (sombras em cascata): referência pela câmera ou pela luz Sun, 2 ou 3 cascatas, **Auto Bias**
  (também em Variance/VSM) e custo bem menor no modo Camera com Static Shadow.
- **Camera FX**: Directional Blur por reprojeção de profundidade, com o rastro só atrás do movimento.
- **Baked Lighting** moderno: interface por modo, Oclusão de Ambiente e Iluminação Estática + Sombras,
  bake da cena inteira, escolha explícita de CPU/GPU.

### Som

- Sons de efeito incluídos na engine: explosão, destruição, chuva e trovão.
- Chuva e raios ligados já tocam som sozinhos: o módulo Effects é criado e preenchido ao salvar ou rodar,
  e os arquivos vão para a pasta `sounds/` do projeto.
- Volume e atraso do trovão pela distância do raio.
- Liga/desliga o som de cada efeito (chuva, raio, Empty Lightning, Explosive/Destruction).
- Trovões, explosões e quebras saem com tom e volume levemente variados a cada vez.

### Interface

- Aba Object dividida em **Object / Game / Transform**; novas abas **Physics/Damage** e
  **Sky/Atmosphere/Properties**.
- Abas nos painéis de Export/Render, receitas de material e novo layout do preview de textura.
- Painel Use Shadow reorganizado em seções com ícones; CSM com painel próprio na luz Sun.
- Weather Rain em seções expansíveis (Ripples e Splash lado a lado) e campos do Weather em botões
  arredondados como no Material.
- Partículas GPU com campos XYZ em 3 colunas.
- **Game Layers fixadas**, escolhidas pelo popover do cabeçalho ou pelo painel N.
- **Ragdoll**: preview de autoria, componente comum para personagens e NPCs, presets de física e painel
  mais compacto.
- Splash com os links do Patreon da Anastacio Engine e da Range Engine.
- Traduções que faltavam em português, espanhol e russo.

## Correções

### Vídeo

- Vídeos com keyframes distantes (gravações de tela) não derrubam mais o jogo para ~1 FPS.
- Loop sem engasgo (antes travava 8-17 ms a cada volta).
- Quadros na ordem e no tempo certos em arquivos com B-frames, decodificação em várias threads e timebase
  fina (AVI deixava pular trechos inteiros).
- Imagens estáticas voltaram a carregar como textura de vídeo.
- `VideoPlayer.dispose()` não falha mais se o jogo acabar antes do `start()`.

### Sombras e efeitos

- CSM com referência pela luz: o Shadow Fade não clareia mais as cascatas Medium e Low.
- Camera FX: a passada da lente é pulada quando o Directional Blur não tem giro de câmera (mais FPS).

### Interface

- Um nome de ícone inválido não faz mais o painel inteiro sumir (vira ícone de erro com aviso no console);
  20 ícones inválidos corrigidos em add-ons e no flowmenu.
- Add Sounds copia os sons da engine para o projeto, então eles não somem no jogo exportado.
- Curvas não mostram mais Render U/V e propriedades que não valem na game engine.
- Requisitos do SSGI e notas do Fast Shader Loading em blocos recolhíveis.
- Outliner sem o rótulo `<unsaved>` no cabeçalho.

### Web e Android

- Botão para alternar os controles de toque e chegar aos menus do jogo.
- Texturas PNG carregam no runtime Web (wasm32).

### Ferramentas

- Detector de trabalho repetido por frame e log opcional de transform por objeto (`RANGE_AUDIT_TRANSFORMS`).
- Testes automáticos novos para bake, Material Atlas, conversão de Logic Bricks e sons do Weather;
  suíte `ctest` 100%.

## Pendências conhecidas

- Web: o feixe do Spot na Volumetric Fog não aparece no navegador (no desktop aparece).
- Sombra colorida: a cor no Sun com cascatas (CSM) ainda está em ajuste.
- Linux: o bake de lightmap usa box blur no lugar do OIDN.

## Downloads

- `AnastacioEngine-0.5.2-windows-x64.zip`: engine portátil para Windows x64 (editor + runtime).
- `AnastacioEngine-0.5.2-linux-x86_64.tar.xz`: engine portátil para Linux x86_64.
- `RangeArmor-0.5.2-windows-x64.zip`: painel RangeArmor (asset separado da engine).
- `SHA256SUMS.txt`: hashes SHA-256 de todos os arquivos acima.

**Como usar:** extraia o pacote numa pasta própria e abra `AnastacioEngine.exe` (Windows) ou
`AnastacioEngine` (Linux). Para rodar um jogo exportado, use `AnastacioRuntime.exe` (Windows) ou
`AnastacioRuntime` (Linux). No Linux não é preciso instalar bibliotecas: o pacote já traz as que usa em
`lib/`. Para pôr o ícone no menu e na dock, rode `./install-desktop.sh` dentro da pasta.
