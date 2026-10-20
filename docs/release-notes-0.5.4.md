# AnastacioEngine 0.5.4

Corrige o Export Web do pacote Linux e traz os Smart Components, idiomas no jogo, gravação de tela e
novas opções de material no modo Game.

## Correções

- **Export Web no Linux:** o pacote 0.5.3 saiu com o manifesto do runtime Web desatualizado e o Export Web
  parava com `WEB-PKG-001`. O runtime foi refeito e o empacotamento agora para se o manifesto não bater com
  os arquivos.
- **Export Game (1 Click) no Linux:** o pacote passa a levar o `python3.11`; antes o export parava com
  "Could not find a Python interpreter".
- **Painel Components:** o painel do objeto agora mostra os Smart Components; avisos do `on_change`
  aparecem na janela do editor.
- **Windows:** timer com resolução de 1 ms (frames mais regulares).

## Novidades

- **Smart Components:** components com campos tipados (`Range.args`: `Float`/`Int` com mínimo, máximo e
  dica, `Bool`, `Text`, `Choice`, `Color`, `Object`, `Scene`, `Header`), uma classe `Editor` opcional
  (avisos por campo, botões, `on_attach`, `draw_ui`, gizmos na viewport) e `components.new()`/`remove()`
  pelo Python. Os campos Object/Scene seguem o objeto ou a cena quando são renomeados. Template
  "04 Smart Component" em Text Editor ▸ Templates ▸ Components.
- **Idiomas do jogo (`Range.locale`):** tabela de traduções em CSV, painel Scene ▸ Game Languages em passos
  (ativar, adicionar idioma, traduzir todos os textos, prévia na viewport), fonte e atlas por idioma e o
  componente Language Button. Guia em `docs/idiomas.md`.
- **Gravação de tela:** Window ▸ Record Screen (Ctrl+Alt+F3) grava o editor e o jogo rodando em MP4 H.264,
  com qualidade, FPS e cursor configuráveis.
- **Materiais no modo Game:** Shadows Only (shadow catcher), Fresnel na transparência, Z Offset e Shadow
  Casting Alpha.
- **Python:** `KX_GameObject.getCurvePoints` amostra a curva de um objeto.
- **Texto:** opção Show Floating Menus e opções de contexto no cabeçalho do Text Editor.

## Downloads

- `AnastacioEngine-0.5.4-linux-x86_64.tar.xz`: editor e runtime para Linux, com as bibliotecas incluídas.
- `RangeArmor-0.5.4-linux-x86_64.tar.xz`: painel de exportação para Linux; exporta jogos para Linux e Windows.
