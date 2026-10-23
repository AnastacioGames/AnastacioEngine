# UI Tree — menus 2D no Node Editor

Branch: `feat/ui-tree-proto` (2026-10-23).

## Ideia

- Árvore de nós própria: **UI Tree**.
- **Frame = tela do jogo.** Os botões dentro dele aparecem no jogo na mesma posição e no mesmo tamanho relativos.
- **Nó Button = botão.** As saídas são eventos: On Enter, On Exit, On Over, On Press, On Release e On Click.
- **Nós de ação** ligados nos eventos: Print, Send Message, Go To Screen, Change Scene e Quit Game.
- No jogo, a tela ativa é desenhada em overlay, por cima do render.

## Etapa 0 — protótipo (Python + um ajuste em C no desenho do Frame)

| Peça | Arquivo |
|---|---|
| Árvore, nós, Bake UI (painel N do Node Editor) | `source/release/scripts/startup/range_ui_tree.py` |
| Runtime: lê `ui_tree_data.py`, desenha em `post_draw` (bgl/blf), mouse, som | `source/release/scripts/modules/range_ui_runtime.py` |
| Desenho do botão, comum ao editor e ao jogo | `source/release/scripts/modules/range_ui_draw.py` |
| Screen: Frame só com borda, sem crescer, proporção do jogo | `source/source/blender/editors/space_node/drawnode.c` |
| Gera a cena de teste | `tools/debug/cenas/criar_cena_ui_tree.py` → `ui_tree_proto.range` |

No jogo: um sensor Always (pulso ligado) + um controlador Python Module `range_ui_runtime.main`.
A tela ativa é a propriedade de jogo `ui_screen` do dono do script ("" esconde o menu): liga/desliga por
Logic Bricks (atuador Property) ou Python. Na cena de teste, M mostra e H esconde.

Screen (Add → Widgets → Screen) é um Frame marcado com `ui_screen`; Frames comuns seguem organizando.
Ações: Print, Send Message, Go To Screen, Change Scene, Quit Game, Play Sound (uma entrada aceita vários botões).

O que o teste precisa mostrar:
1. O menu "Jogar / Opções / Sair" aparece centralizado.
2. O hover muda a cor.
3. Entrar em Jogar e clicar em Jogar imprimem no console.
4. Opções leva para a tela "Opcoes"; Voltar retorna para "Menu".
5. Sair fecha o jogo.

Limites conhecidos do protótipo:
- ~~Precisa apertar Bake UI depois de cada mudança.~~ Resolvido: Bake automático ao apertar P e ao salvar.
- O tamanho do botão vem do nó desenhado; em `-b` usa 30 de altura.
- Só retângulo arredondado com cor e texto.

## Feito no protótipo (Python), 2026-10-23

- **Barra flutuante:** painel UI Tree também na prateleira T (ícone na barra de abas).
- **Animações nativas do botão:** Hover Scale, Press Scale, Anim Time (cor e escala suaves).
- **Widgets:** Panel, Image (lida com `Range.texture` no jogo; Fit Image Aspect), Toggle e Slider
  (gravam numa propriedade, saída On Change). Opção **Audio**: Toggle = Sound On/Off e
  Slider = Master Volume mandam no volume geral do jogo (`aud.Device().volume`).
- **HUD:** Progress Bar, Label, Gauge (velocímetro circular com ponteiro).
- **Screen:** Fade (s) ao mostrar/esconder; sons padrão de Hover/Click sem ligar nós.
- **Ações:** Set Property, Add Property, Toggle Property, Run Python (`modulo.funcao(ui)`).
- **Navegação:** setas/analógico mudam o foco, Enter/Espaço/botão A apertam, esquerda/direita
  mexem o Slider; o mouse mexendo devolve o controle ao hover.
- **Escala e âncora:** cada Screen escolhe Stretch ou Keep Aspect; em Keep cada widget segue uma
  das 9 âncoras (cantos, bordas, centro), editadas no painel UI Tree.
- **Estados:** botão com Enabled If (cinza, sem eventos e fora do foco) e Selected If (destacado).
- **API Python:** `range_ui_runtime.show(nome)`, `hide()`, `set_hud(bool)`, `get()`.
- Integração com Logic Bricks: propriedades `ui_screen`/`ui_hud` e a ação Send Message
  (sensor Message).

- **Bake automático:** ao apertar P e ao salvar (o export salva), a UI Tree do último Bake
  (ou a única do arquivo) é gravada de novo; o botão Bake UI continua para conferir.
- **HUD por viewport (split screen):** campo Camera na Screen de HUD; o HUD é desenhado dentro
  do viewport daquela câmera (`setViewport`), lido pelo novo `KX_Camera.viewport` (C++).
  Um HUD por jogador: cada widget pode ler as propriedades de um Object diferente.

Ainda falta:
- ~~**Web/Android:**~~ Resolvido (2026-10-23) sem desenho novo: a emulação de GL legado do
  Emscripten já faz `glBegin`/`glOrtho`, mas o `bgl` recebia ponteiros GLEW nulos (só linka o que
  o C chama pelo nome) — `bgl.c` chama a emulação direto. `GL_POLYGON` virou `GL_TRIANGLE_FAN`
  (a emulação não aceita POLYGON) e `blf.draw` do Python passa a usar as matrizes/cor do `bgl`.
  Testado no Chrome headless: menu, hover, Opções com toggle/slider e texto. O Android usa o
  mesmo pacote Web. Obs.: o runtime Web embute `release/scripts` no `.data`; mudou um módulo,
  refaça o link.
- **Runtime em C++** lendo a árvore direto do DNA: com o Bake automático deixou de ser urgente;
  passa a fazer sentido junto com o desenho novo da Web.

## Etapas do projeto de verdade (se o protótipo for aprovado)

1. **Runtime em C++**: ler a árvore direto do DNA (sem Bake) e desenhar no rasterizer, depois dos filtros 2D.
2. **Mais widgets**: Label, Image, Panel, Slider, Toggle; estados disabled e selected; entradas Enabled, Visible e Text.
3. **Editor**: prévia real do botão dentro do Frame; ancoragem e modo de escala (esticar ou manter proporção).
4. **Animações nativas do botão** (sem ligar nós): escala no hover, clique "afundando", fade de entrada/saída da tela, transição de cor suave.
5. **Ações**: Tween, Set Property, Run Python, Show/Hide; sons padrão de hover/clique na própria Screen.
6. **Integração**: sensor "UI Event" nos Logic Bricks, API `Range.ui`, navegação por gamepad e teclado.
7. ~~Export Web/Android, docs e template.~~ Feito (2026-10-23): guia em `ui-tree.md`, botões + Menu / + HUD / Setup Game Logic.
