# Anastacio Engine
> Game engine para criação de jogos 3D. Fork da Range Engine 1.6 Rev1, na linhagem UPBGE / Blender 2.79.

**De Range Engine a Anastacio Engine.** O que começou como uma versão personalizada da Range Engine cresceu
com cada atualização: renderização, física, ferramentas de editor, Linux nativo, Web e Android. Hoje boa
parte do código foi reescrita ou revisada, e a engine segue caminho próprio como um fork. Projetos continuam
compatíveis: o formato `.range` e os módulos `Range` e `bge` permanecem os mesmos.

> [!IMPORTANT]
> **Para baixar a engine, use a seção [Download](#download) ou a página de [Releases](https://github.com/AnastacioGames/AnastacioEngine/releases).**
> O botão verde **Code → Download ZIP** baixa só o código-fonte, sem os executáveis.

![Splash Screen da AnastacioEngine](https://raw.githubusercontent.com/AnastacioGames/AnastacioEngine/main/release-images/v0.6.0/splash.png)

## Download

Versão atual: **[AnastacioEngine 0.6.1](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.6.1)** (Windows e Linux)

| Pacote | Conteúdo |
|---|---|
| [Windows x64 (0.6.1)](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.6.1/AnastacioEngine-0.6.1-windows-x64.zip) | Editor e runtime, portátil (extraia e rode). |
| [Linux x86_64 (0.6.1)](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.6.1/AnastacioEngine-0.6.1-linux-x86_64.tar.xz) | Editor e runtime, portátil (extraia e rode), com as bibliotecas incluídas. |
| [RangeArmor 0.6.1 Windows](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.6.1/RangeArmor-0.6.1-windows-x64.zip) · [Linux](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.6.1/RangeArmor-0.6.1-linux-x86_64.tar.xz) | Ferramenta separada para criar e empacotar projetos. O painel roda no Windows e no Linux e exporta jogos para Windows e Linux. |
| [SHA-256 dos pacotes 0.6.1](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.6.1/SHA256SUMS.txt) | Hashes para conferir o download. |

**Como usar:** extraia o pacote numa pasta própria e abra `AnastacioEngine.exe` (Windows) ou `AnastacioEngine` (Linux).
Para rodar um jogo exportado, use `AnastacioRuntime.exe` (Windows) ou `AnastacioRuntime` (Linux). Os alvos de build continuam `RangeEngine`/`RangeRuntime`.
No Linux não é preciso instalar bibliotecas: o pacote já traz
as que usa em `lib/` e depende só do que qualquer desktop tem (driver de vídeo, X11/Wayland, som). Para pôr o
ícone no menu e na dock, rode `./install-desktop.sh` dentro da pasta.

## Novidades da 0.6.1

Tempo de jogo mais estável (Windows, Linux e Wine), Fixed Timestep suave e ligado por padrão nas cenas novas,
céu e lens flare mais leves em iGPU e simulador de PC fraco no Performance Report. Detalhes nas
[notas do release](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.6.1).

## Novidades da 0.6.0

- **Logic Tree:** lógica por nós no Node Editor (todos os bricks, Run Python, receitas, Frames de Estado e
  destaque ao vivo dos nós que dispararam).
- **UI Tree:** menus e HUD 2D por nós, também na Web/Android; Dialogue Box e Text Boxes no jogo.
- **Compositing no jogo:** Blur, Glare, Directional Blur, Color Correction, Tonemap, Dilate/Erode, Z Combine,
  Crop e Bilateral Blur; Node Editor com faixa de efeitos e presets no estilo Blender 5.
- **Render:** sombra de sol em cascatas (CSM), PCSS, SH9 em sondas, partículas flipbook, Sky Quality, HLOD e
  Auto Static Batch.
- **Ferramentas:** Scene Doctor, Performance Report, FPS Counter, Range Trace e barra/menus no estilo Blender 5.
- **Export:** Compile Scripts entrega só `.pyc`; pacote Universal (Windows + Linux numa pasta).
- **Gravação de tela no Linux:** grava em AVI (o MP4 com som segue no Windows).
- Revisão ampla do núcleo e muitas correções.

Lista completa em [docs/releases.md](docs/releases.md#060).

## Novidades da 0.5.4

- **Smart Components:** campos tipados com `Range.args` (Float/Int com limites e dica, Bool, Text, Choice,
  Color, Object, ObjectList, Point, Scene, Header), avisos e desenhos na viewport, classe `Editor` opcional e o
  **Smart Component Wizard**, que cria components prontos a partir de receitas (Perseguidor, Patrulha,
  Coletável, Spawner, Porta, Vida, Câmera seguidora e outras).
- **Logic Bricks espertos:** painel **Brick Inspector** lista o que está errado (alvo faltando, propriedade que
  não existe, brick sem ligação…), desenho do Near/Radar/Ray na viewport e presets novos (Mouse Look, Shoot,
  Turret, Pause Key…).
- **Idiomas no jogo (`Range.locale`):** tabela de traduções, painel Game Languages em passos, prévia na viewport
  e componente Language Button. Guia em [docs/idiomas.md](docs/idiomas.md).
- **Gravação de tela com som:** Window ▸ Record Screen (Ctrl+Alt+F3) ou botão Rec grava o editor e o jogo em
  MP4, inclusive o Standalone.
- **Materiais no modo Game:** Shadows Only (shadow catcher), Fresnel na transparência, Z Offset e Shadow Casting
  Alpha.
- **Correções:** crash em placas de vídeo antigas na primeira abertura do jogo, janela de crash com o caminho
  certo dos arquivos, Export Web e Export 1 Click no Linux, timer de 1 ms no Windows e menos travadas no começo
  do jogo.
- **Traduções:** toda a interface nova em português, espanhol e russo.

Lista completa em [docs/releases.md](docs/releases.md#054).

## Novidades da 0.5.3

- **RangeArmor no Linux:** o painel da RangeArmor agora também roda no Linux
  ([download](https://github.com/AnastacioGames/AnastacioEngine/releases/download/v0.5.3/RangeArmor-0.5.3-linux-x86_64.tar.xz))
  e exporta jogos para Linux e Windows. Extraia, renomeie a pasta para `rangearmor` e coloque dentro da pasta
  da engine. Usa o `python3` do sistema; o Set Icons (ícone do `.exe`) precisa do `wine`.
- **Efeitos na Web e no Android (WebGL2):** os efeitos que antes não apareciam no navegador agora rodam:
  - partículas de fumaça, fogo e light flicker;
  - chuva com aura em volta da câmera, raios/relâmpagos e máscara de superfície molhada;
  - shaders dos efeitos convertidos para WebGL2, partículas animadas na GPU e saída de cor em float
    conferida antes de usar;
  - cópia da tela sem erro de buffers de desenho, que deixava a imagem preta ou faltando efeito.
- **Sons de efeito:** o módulo Effects criado pela chuva já vem com os sons da engine, então explosão e
  destruição não ficam mais mudas.

Lista completa em [docs/releases.md](docs/releases.md#053).

## Novidades da 0.5.2

- **Logic Bricks 2.0:** grupos recolhíveis, actuator Wait e modo Finished para encadear ações, botão Then,
  actuator Video, presets, histórico, janela de lógica no Debug Mode e **Highlight Active** (os bricks
  acendem quando disparam). O conversor para Python entende os bricks novos.
- **Video Player:** componente nativo com fade para cutscenes, legendas `.srt` e controle por Logic Bricks;
  o export copia os vídeos.
- **Texto do jogo:** atlas bitmap gerado da fonte (cirílico e kana), preview na viewport.
- **SSGI e CSM:** SSGI com Check Scene, Denoise e resultado mais suave; CSM com 2 ou 3 cascatas,
  referência pela luz Sun e Auto Bias.
- **Som:** chuva, trovão, explosão e destruição já vêm na engine e tocam sozinhos; liga/desliga por efeito.
- **Controles de toque na Web e no Android:** botão **Controles: ligados/desligados** no canto da tela para
  esconder os controles virtuais e tocar nos menus do jogo (Start, opções) sem que o stick pegue o toque.
  Ao religar, volta o mesmo tipo de controle que o jogador escolheu (stick, setas ou inclinar o celular no
  layout de corrida), e essa escolha fica guardada para a próxima vez que ele abrir o jogo.
- **Interface:** aba Object em Object/Game/Transform, painéis de sombra e clima reorganizados, Game Layers
  fixadas, Ragdoll com presets.
- **Correções:** vídeos não caem mais para ~1 FPS nem engasgam no loop, CSM sem cascatas clareadas, ícone
  inválido não some com o painel, sons da engine vão junto no jogo exportado, PNG no runtime Web.

Lista completa em [docs/releases.md](docs/releases.md#052).

## Novidades da 0.5.1

Versão de correções sobre a 0.5.0, com foco em estabilidade no Linux, export Web/Android e no shading PBR.

- **Export Web/Android:** o template Android e a pasta `web/` completa agora vão para o pacote (zip Windows
  e tar Linux); faltando isso, o Build APK falhava com "Android template not found" na 0.5.0.
- **Linux:** OpenColorIO 2.x (Ubuntu 24.04+, mantendo 1.x), Cycles com OpenColorIO 2.x, FFmpeg 5+/6.x,
  correções de link que impediam a build em alguns ambientes, `SIGTERM`/`SIGINT` encerrando o jogo
  corretamente, probe de SSGI sem depender de `ctypes.WinDLL`.
- **ORM:** dá para escolher quais das três influências (Diffuse Ref, Specular Intensity, Ambient) recebem a
  Occlusion do "RGB to ORM", em vez de sobrescrever as três sempre; arquivos antigos continuam iguais.
- **Sombra colorida (Sun com CSM):** a mancha colorida no chão sob vitrais aparece corretamente com cascatas.
- **SSGI:** não corta mais vidros em Alpha Blend pela metade.
- Destruição treme a câmera ativa; personagem acompanha plataformas móveis; `MeshBuilder.addSlot` sem
  `primitive` usa triângulos; validação de componentes não trava mais em projetos sem `Range.network`/`audio`/`texture`.

Lista completa na [página da release](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.5.1).

## Novidades da 0.5.0

- **Clima e névoa:** Volumetric Fog (lâmpadas coloridas, raios de sol e de spot, Fog Volumes de fumaça e fogo,
  neblina nos vales, poeira no feixe), Volumetric Clouds com raymarch e Céu em Camadas junto com as nuvens.
- **Sombra colorida (vitral):** vidro com Alpha Blend projeta luz colorida, também no feixe da névoa, com Glow.
- **Partículas e explosões:** modo Burst, Particle Explosion (Fire/Electric/Concrete/Water), marca no chão,
  fumaça e fogo de partículas e luz que tremula.
- **World Sound:** música, ambiente e efeitos (explosão, destruição, chuva, trovão) no World, com eco opcional.
- **Shader Nodes:** Planar Reflection, Fur Shells, Billboard, Strands, Explode, World Bloom e SSR como nós.
- **SSGI** experimental nativo, com emissivos.
- **Logic Bricks → Python:** conversor que gera componentes equivalentes aos bricks.
- **Web:** áudio por AudioWorklet, controle de toque para corrida (stick, setas ou inclinar), pré-voo de shaders,
  rede por WebSocket no navegador e VR no celular.
- **Rede:** servidor WebSocket com transporte múltiplo e predição de corpos dinâmicos.
- **Decimate High Quality**, constraints de física prontas, splash novo com arquivos fixados (Pin).
- Executáveis Windows renomeados para `AnastacioEngine.exe` e `AnastacioRuntime.exe`.

**Correções:** crash do SSGI com o nó Diffuse, crash do Planar Reflection, crash no setFullScreen, crash no
aquecimento de shaders, sombra com GPU Skinning em pose T, pose na troca de LOD, sons com a cena suspensa,
emissor Empty de partículas, chuva na 3D View, filtros 2D no 1º quadro, texto do jogo parando de renderizar,
culling de atividade, batch ao mover objeto, parallax e triplanar, travadas na pintura de textura, SIGTERM no
runtime. Lista completa na [página da release](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.5.0).

**Efeitos ainda em ajuste.** Os efeitos novos desta versão funcionam, mas ainda vão receber ajustes visuais e
correções nas próximas versões. Pontos já conhecidos:

- Sombra colorida (vitral): alguns pontinhos coloridos soltos no próprio vidro; no Sun com cascatas (CSM) a
  mancha colorida no chão ainda não aparece.
- Volumetric Fog na Web: a névoa funciona no navegador, mas o feixe de luz do Spot ainda não aparece.
- SSGI é experimental: vidro transparente (Alpha Blend) pode sair cortado em degraus.
- Linux: o bake de lightmap usa um filtro mais simples (sem o denoiser OIDN).

Galeria de imagens por versão: [release-images/](release-images/README.md), com os [prints das novidades da 0.5.0](release-images/v0.5.0/README.md).

## Novidades da 0.4.6

- **Câmera do jogo:** foco, rastreio de alvo, Camera FX (profundidade de campo, speed blur, blur direcional,
  olho de gato) e tremor de câmera, nos painéis da câmera (só Range Game).
- **Chuva do World:** respingo nas superfícies, aura nos objetos, raios com clarão e riscos finos; iguais no jogo
  e na 3D View. Controle por Python com `setWeather()` e `strikeLightning()`.
- **Destruição e explosões nativas:** painéis Destruction/Explosive, Generate Fragments (pedaços num collection)
  e API Python.
- **Reverb Area:** Empty com reverb OpenAL por área (esfera ou caixa), com presets e transição pela câmera.
- **Soft body no jogo:** escala, transformação, velocidade, suspend e deformer corrigidos.
- **Outliner:** arrastar um objeto selecionado para uma coleção move toda a seleção.
- MSAA mínimo do jogo passa de 4x para 2x (cenas novas vêm com 2x).

## Novidades da 0.4.5

- **Abre em mais distros:** o pacote agora é compilado no Ubuntu 22.04 (exige glibc 2.35) e leva as bibliotecas
  junto. Corrige `libOpenImageIO.so.2.4: cannot open shared object file` no Ubuntu 26.04 e o erro de glibc em
  distros mais antigas que o Ubuntu 24.04. Testado em Ubuntu 22.04, Debian 12, Ubuntu 26.04 e Fedora limpos.
- **Ícone da Range** na janela e atalho `.desktop` para o menu de aplicativos.
- **Windows 0.4.5:** mesma engine da 0.4.4, publicada para igualar a numeração. O número da versão no splash e
  no About passa a ser 0.4.5.
- Se ainda der erro, rode `ldd ./RangeEngine | grep "not found"` e mande a saída numa
  [issue](https://github.com/AnastacioGames/AnastacioEngine/issues).

## Novidades da 0.4.4

Correções dos bugs reportados pelo Kitsuy (crash com `setHalfAnimations`, folhagem Hashed sem MSAA, rodas do
carro, runtime sem GPU), navmesh dinâmica, Link de objeto e previews automáticas no Asset Browser, espelho e água
com corte oblíquo e correções de lâmpadas e sombras. **Mudança de API:** `setAntiAliasing(0)` e `(1)` usam 4
amostras. O pacote Windows já traz as correções de previews do Asset Browser (`.range`, grupos vazios).
Detalhes nas [notas do release](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.4).

## Novidades da 0.4.3

Addons sem avisos do Python 3.11 e correção do loop de tempo (Fixed Timestep fora da interface, v-sync sem
atraso falso). O resto é igual à 0.4.2.

## Novidades da 0.4.2

### Destaque: render Cycles na placa de vídeo
- **NVIDIA (CUDA):** placas RTX 20, 30, 40 e 50 já vêm suportadas no pacote do Windows, sem instalar o CUDA Toolkit.
- **AMD (OpenCL):** render e bake na GPU AMD, testados numa RX 6800M.
- **Embree:** render na CPU mais rápido, no Windows e no Linux.
- Bake de iluminação na GPU dá o mesmo resultado que na CPU.

### Correções importantes
- **Linux:** o pacote 0.4.1 não abria fora da máquina de build (`No module named 'encodings'`). Corrigido e
  testado num Ubuntu 24.04 limpo. **Quem baixou o 0.4.1 deve atualizar.**
- **Arquivos UPBGE:** abrir um projeto UPBGE com sensores escrevia fora da memória; corrigido. Save/Load do
  `globalDict` agora também lê os arquivos `.bgeconf` do UPBGE.
- **Material com shader GLSL próprio:** apagar o texto do shader deixava o material apontando para memória
  liberada (crash). Corrigido, junto com vazamentos de memória.
- **Subsurface Scattering:** Scale 0 gerava pixels pretos; corrigido.
- **Custom Viewport da câmera:** ficava errado ao redimensionar a janela ou usar resolução dinâmica; agora
  se ajusta a cada frame.
- **Foliage (vento):** grama instanciada não balançava e a base das plantas se mexia; corrigido. O vento
  também não perde precisão em sessões longas.
- **Screens:** Ctrl+Seta deixava de trocar de screen depois de apagar uma; corrigido.
- **Theme:** Copy Global Theme agora atualiza toda a interface de uma vez.
- Diversas correções de segurança e estabilidade no Cycles (leitura de arquivos, luzes IES, buffers grandes).

### Novidades e aprimoramentos
- **Asset Browser:** novo modo do File Browser para navegar por bibliotecas de `.blend` e arrastar objetos,
  grupos e materiais direto para a Vista 3D.
- **Outliner com coleções:** pastas para organizar a cena. Uma pasta pode ficar "fora do jogo" (objetos
  começam inativos, prontos para o Add Object) e virar um Group com um clique.
- **Painéis reorganizados:** abas Camera, Material, Render, Physics, Vehicle, Game Settings e Text Editor em
  painéis nativos, com opções que o jogo não usa escondidas e avisos quando uma combinação não tem efeito.
- **Custom Viewport:** presets prontos (tela cheia, picture-in-picture, tela dividida, quadrantes) e prévia do
  tamanho em pixels.
- **Aba Input** nas Propriedades e **aba Export Game** (RangeArmor, Web e Android) no editor.
- **Veículos:** motor em Nm, pedais, joystick, moto e telemetria de marcha/RPM no HUD e no Vehicle Lab.
- **Idiomas:** interface em English, Português, Español e Русский.
- **Windows:** arquivos `.blend` e `.range` associados à engine.

## Ferramentas para criar jogos
- **World, clima e iluminação:** clima direto na cena e sombras CSM ajustáveis pelo editor.
- **Veículos:** transforme um Rigid Body em veículo e ajuste a física em tempo real pelo Vehicle Lab.
- **GPU Skinning:** escolha **RanGE GPU Skinning** no painel da Armature e ligue **GPU Skinning** no material.
- **RangeArmor:** crie projetos e prepare distribuições pelo RangeArmor Panel.
- **Render Cycles:** CPU, NVIDIA (CUDA) e AMD (OpenCL).

## Plataformas
| Plataforma | Estado |
|---|---|
| Windows x64 | Suportada. |
| Linux x86_64 | Suportada (nativo). |
| Web (navegador) | Em testes; ainda não usar em produção. Detalhes no [roadmap](docs/roadmap.md). |
| Android | Experimental: APK/AAB gerado pelo editor a partir do pacote Web. |
| 32-bit | Não suportado. |

## Sobre

AnastacioEngine é um projeto da Anastacio Games. A engine parte da Range Engine 1.6 Rev1, derivada da
UPBGE 0.2.5b / Blender 2.79, e foca em performance, renderização, ferramentas de runtime e fluxo de produção
para jogos.

## Desenvolvimento (código-fonte)

- [Diagramas da arquitetura](docs/diagramas-arquitetura.md) · [Índice da documentação](docs/README.md) · [Roadmap](docs/roadmap.md) · [Histórico técnico](docs/changelog.md)
- [Build no Windows](docs/build-notes.md) · [Build no Linux](docs/linux-build.md) · [Arquitetura](docs/architecture.md)
- [Como contribuir](CONTRIBUTING.md) · [Licença](docs/licenca.md) · [Relatório de melhorias](relatorio-melhorias-anastacioengine.md)

Para agentes de código, as regras operacionais estão em [AGENTS.md](AGENTS.md).
