# UI Tree — guia de uso

Menus e HUD 2D do jogo montados no Node Editor. Funciona no desktop, na Web e no Android.
Plano e histórico técnico: [ui-tree-plan.md](ui-tree-plan.md).

## Começo rápido (template)

1. Node Editor → tipo **UI Tree** → **New**.
2. Painel **UI Tree** (N ou aba na prateleira T): **+ Menu** e/ou **+ HUD**.
   - Menu: telas `Menu` (Jogar, Opções, Sair) e `Opcoes` (Som, Volume, Voltar).
   - HUD: barra e texto de vida (canto de cima) e velocímetro (canto de baixo).
3. **Setup Game Logic**: liga na câmera da cena o Always (pulso) + Python Module
   `range_ui_runtime.main` e cria as propriedades `ui_screen`, `ui_hud`, `som`, `volume`,
   `vida` e `velocidade`. Rodar de novo não duplica nada.
4. Aperte **P**. O Bake é automático ao jogar e ao salvar.

Jogar esconde o menu e liga o HUD; Som e Volume mandam no volume geral do jogo.

## Peças

- **Screen**: Frame marcado como tela (Add → Widgets → Screen). Tem Fade, sons padrão de
  hover/clique, Scale Mode (Stretch ou Keep Aspect) e imagem de fundo só para o editor
  (Capture Camera). **HUD Screen** fica sempre por baixo do menu; com **Camera** preenchida,
  desenha só no viewport daquela câmera (split screen).
- **Widgets**: Button, Toggle, Slider, Panel, Image; HUD: Progress Bar, Label (`{vida:.0f}`),
  Gauge. Cada widget pode ler as propriedades de outro objeto (campo Object).
- **Eventos do Button**: On Enter, On Exit, On Over, On Press, On Release, On Click.
  Toggle e Slider têm On Change.
- **Ações**: Print, Send Message, Go To Screen, Change Scene, Quit Game, Play Sound,
  Set/Add/Toggle Property, Run Python (`modulo.funcao(ui)`).
- **Estados**: Enabled If / Selected If (propriedade bool).
- **Âncora**: em Keep Aspect, cada widget segue um dos 9 pontos (painel UI Tree).

## Controle pelo jogo

- Propriedade `ui_screen` do dono do script: nome da tela; `""` esconde o menu.
- Propriedade `ui_hud` (bool): mostra/esconde o HUD.
- Python: `range_ui_runtime.show("Menu")`, `hide()`, `set_hud(True)`, `get()`.
- Teclado/controle: setas ou analógico mudam o foco, Enter/Espaço/A apertam,
  esquerda/direita mexem o Slider.
- Logic Bricks: atuador Property em `ui_screen`; Send Message + sensor Message.
