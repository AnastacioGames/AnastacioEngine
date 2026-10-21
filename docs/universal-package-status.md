# Pacote Universal (Win + Linux) — onde parou (2026-10-20)

## Feito e enviado (d82d2b0f)
- Player abre `<nome do player>.range` ou `game.range` da própria pasta.
- `build_release.py --universal`, botão "Universal (Win + Linux)" no Panel, Export 1 Click com `--universal`.
- 12 testes do exportador OK; Panel compilado e instalado em `build/bin/rangearmor`.

## Teste real em andamento
- Projeto de teste montado em `D:\_uni_test`:
  - `engine/Windows64`: runtime do `build/bin`.
  - `engine/Linux64`: RangeRuntime do pacote 0.5.1 (`build/release-linux-inspect`).
  - `data/Example Game.rasec` vem de `D:\tutorial`.
- Próximo comando (rodar dentro de `build/bin/rangearmor/release/scripts`):
  `..\..\..\2.79\python\bin\python.exe build_release.py --project D:/_uni_test/launcher/config.json --target All --compress --universal --no-cook`
- Depois:
  1. conferir a pasta e o zip `Game-1.0.0-Universal`;
  2. no WSL (Ubuntu), extrair o zip e conferir os bits de execução do `launcher/Launcher` e do `engine/Linux64/RangeRuntime`;
  3. rodar o launcher.
- Ao terminar, apagar `D:\_uni_test`.

## Cuidados descobertos
- No Git Bash, `cp .../Launcher` pode pegar o `Launcher.exe` (sobrescreveu o do Windows). Copiar com Python.
- O caminho do scratchpad passa de 260 caracteres no stage. Testar em pasta curta.
  - Talvez avisar o usuário quando o projeto estiver em caminho longo.

## Mensagem nova do Kitsuy (a analisar)
- Ele fez arquivos de save "travados" que só o player abre: o editor (menu do Blender) não abre.
- Pede o mesmo na engine: um formato novo que só o player carregue, e não o editor.
- Relacionado: `.cooked` e a proteção do `data.dat` do RangeArmor. Avaliar antes de responder.
