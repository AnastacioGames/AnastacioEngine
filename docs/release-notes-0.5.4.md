# AnastacioEngine 0.5.4

Versão grande: Smart Components com assistente, Logic Bricks que avisam o que está errado, idiomas no jogo,
gravação de tela com som, novas opções de material no modo Game e várias correções (crash em placas de vídeo
antigas, Export Web e Export 1 Click no Linux). Toda a interface nova vem traduzida para português, espanhol e
russo.

## Novidades

### Smart Components

- **Campos tipados com `Range.args`:** `Float` e `Int` (com mínimo, máximo e dica no tooltip), `Bool`, `Text`,
  `Choice`, `Color`, `Object`, `ObjectList`, `Point`, `Scene` e `Header` (título que abre e fecha os campos
  abaixo). O jogo recebe os mesmos valores de antes: components antigos continuam iguais.
  - `Object` mostra um seletor de objeto e chega no jogo como `KX_GameObject` (ou `None` se foi apagado).
  - `ObjectList` guarda vários objetos, com botões Add Selected, New, subir e remover.
  - `Point` guarda uma posição, com botões 3D Cursor e Selected.
  - `Scene` escolhe uma cena e chega como nome, pronto para `logic.addScene`.
  - Os campos Object e Scene seguem o objeto ou a cena quando são renomeados.
- **Opções de editor:** `show_if` (só mostra o campo quando outro tem certo valor), `required`, `filter`
  (MESH, LAMP…), `warn_above`, e desenhos na viewport (`line`, `circle`, `create`).
- **Classe `Editor` opcional** dentro do component (só no editor; o jogo ignora): avisos por campo
  (`on_change`), botões (`buttons`), `on_attach`, `draw_ui` e gizmos na viewport. Avisos automáticos para campo
  vazio, objeto que não existe, objeto em camada escondida e valor acima do limite.
- **Smart Component Wizard** (Properties ▸ Game ▸ Component Manager e Text ▸ New Smart Component): cria um
  component a partir de uma receita, com lista de campos, prévia ao vivo da caixa e o código gerado. Receitas:
  Vazio, Perseguidor, Patrulha (lista de pontos), Coletável, Spawner (sorteia modelos, pode nascer num ponto),
  Porta, Zona de gatilho, Vida, Câmera seguidora, Luz piscando e Girador.
- Botão **Add Field** no fim da caixa do component: põe um campo novo direto no código e recarrega.
- **Python:** `obj.game.components.new("modulo.Classe")` e `.remove(comp)` no editor.
- Template **"04 Smart Component"** em Text Editor ▸ Templates ▸ Components. O Video Player e o Rigid Body Joint
  passaram a usar a API nova.

### Logic Bricks espertos

- **Brick Inspector** (painel N do Logic Editor): lista os problemas do objeto ativo e dos outros objetos;
  clicar abre o brick com problema.
- **Avisos** para: Steering sem alvo, Path Following sem navmesh, Track To/Camera/Parent sem objeto, Add Object
  sem objeto ou com objeto em camada visível, Action/Sound/Scene não escolhidos, propriedade que não existe,
  Near/Radar/Collision sem objeto com a propriedade, Ray/Near com distância 0, Message sem quem envie ou receba,
  Motion com força em objeto não dinâmico, Python controller sem módulo, Keyboard sem tecla e bricks sem
  ligação.
- **Desenho na viewport:** esfera do Near, cone do Radar, linha do Ray e seta do Steering/Track To/Camera até o
  alvo, com o nome do brick.
- **Presets novos:** Mouse Look, Shoot, Spawn Every 2 Seconds, Turret e Pause Key. O preset Door teve o Reset
  Distance corrigido.

### Idiomas do jogo (`Range.locale`)

- Tabela de traduções em CSV (`//locale/translations.csv`) com uma coluna por idioma, mais fonte e atlas por
  idioma. O jogo abre no idioma do sistema e lembra a escolha do jogador.
- Painel **Scene ▸ Game Languages** em passos: ativar, adicionar idioma, traduzir todos os textos de uma vez e
  ver a prévia de cada idioma na viewport (a prévia nunca é salva no arquivo).
- Componente **Language Button** (clique ou tecla troca o idioma e mostra o nome nativo) e funções
  `Range.locale.tr`, `next`, `previous`, `native_name`.
- Bitmap Atlas: Generate from Font guarda os dados no `.range`; botões Show JSON, Open Folder e Copy Atlas to
  Selected; Generate Language Atlases cria um atlas por idioma só com as letras usadas.
- Guia completo em `docs/idiomas.md`.

### Gravação de tela

- **Window ▸ Record Screen** (Ctrl+Alt+F3) e botão **Rec** no cabeçalho Info: grava o editor e o jogo rodando em
  MP4 H.264, com qualidade (Low a Very High), FPS, cursor e janela inteira ou só a 3D View. Botões Open Folder e
  Play Last.
- **Grava o som** do editor e do jogo (Windows 10 versão 2004 ou mais nova), sem pegar o som de outros
  programas. Opção Audio no popover do Rec.
- Com o editor gravando, o jogo aberto no **Standalone** também é gravado automaticamente, num vídeo próprio.
- A gravação não trava a interface: a captura e o encoder rodam fora da thread principal. O render de animação
  em vídeo também ficou mais rápido (encoder usa várias threads).

### Materiais no modo Game

- **Shadows Only** (shadow catcher): o material mostra só a sombra que recebe, ótimo para chão invisível que
  recebe sombra. Precisa de Alpha Blend; o painel avisa se não estiver.
- **Fresnel** na transparência, igual ao Blender Internal.
- **Z Offset** funciona de verdade no jogo e na viewport (bom para decals). Materiais antigos com Z Offset
  diferente de zero podem mudar de aparência.
- **Shadow Casting Alpha:** a sombra respeita a transparência do material (sombra parcial).

### Outros

- **GPU Particle System:** botão para copiar as configurações (principais e Mix) do objeto ativo para os outros
  selecionados.
- **Python:** `KX_GameObject.getCurvePoints()` devolve os pontos da curva de um objeto.
- **Text Editor:** opção Show Floating Menus e opções de contexto no cabeçalho.

## Correções

- **Crash em placas de vídeo antigas (Intel HD e outras):** se o driver de vídeo travar durante a preparação
  de shaders da primeira abertura de um jogo exportado, a próxima abertura pula essa etapa em vez de travar
  sempre no mesmo lugar.
- **Janela de crash mais útil:** mostra o caminho exato dos arquivos de log e de backtrace (antes dizia
  `<file>.crash.txt` e era difícil achar). Quando o crash é dentro do driver de vídeo, a janela avisa e sugere
  atualizar o driver ou baixar Anti-Aliasing, Dynamic Resolution e filtros 2D.
- **Export Web no Linux:** o pacote 0.5.3 saiu com o manifesto do runtime Web desatualizado e o Export Web
  parava com `WEB-PKG-001`. Corrigido, e o empacotamento agora confere o manifesto antes de gerar o pacote.
- **Export Game (1 Click) no Linux:** o pacote leva o `python3.11`; antes o export parava com
  "Could not find a Python interpreter".
- **Logic Editor:** crash ao iniciar o jogo com uma área Logic aberta e um script mudando o contexto.
- **Windows:** timer com resolução de 1 ms, para frames mais regulares (antes uma espera de 1 ms podia durar
  ~16 ms).
- **Travadas no começo do jogo:** imagens de materiais usados dentro de nós Material agora carregam junto com a
  cena, e não no primeiro desenho (tirava ~40 ms de travada no RolimaRacer).
- **Painel Components:** mostra os Smart Components; os avisos do `on_change` aparecem na janela do editor.
- **Templates de Components:** o menu não mostra mais a pasta `__pycache__` como "Pycache".
- **Traduções:** os textos novos desta versão foram traduzidos para português, espanhol e russo.

## Downloads

- `AnastacioEngine-0.5.4-windows-x64.zip`: editor e runtime para Windows.
- `RangeArmor-0.5.4-windows-x64.zip`: painel de exportação (Windows); exporta jogos para Windows e Linux.
- `AnastacioEngine-0.5.4-linux-x86_64.tar.xz`: editor e runtime para Linux, com as bibliotecas incluídas.
- `RangeArmor-0.5.4-linux-x86_64.tar.xz`: painel de exportação para Linux; exporta jogos para Linux e Windows.
