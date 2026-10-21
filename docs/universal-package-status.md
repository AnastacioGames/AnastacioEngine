# Pacote Universal (Win + Linux) — onde parou (2026-10-20)

## Feito e enviado (d82d2b0f)
- Player abre `<nome do player>.range` ou `game.range` da própria pasta.
- `build_release.py --universal`, botão "Universal (Win + Linux)" no Panel, Export 1 Click com `--universal`.
- 12 testes do exportador OK; Panel compilado e instalado em `build/bin/rangearmor`.

## Teste real (2026-10-21)
- Exportação Universal OK em `D:\_uni_test` (pasta + zip, `Game.exe` e `Game` lado a lado).
- WSL: bits de execução preservados no zip (launcher e runtime).
- Não abriu no Linux porque o runtime de teste (0.5.1) não tem `2.79/python/bin/python3.11`.
  Falha do projeto de teste, não do pacote.
- Linux tar.xz levava ~13 min (xz preset 6). Agora usa preset 1; falta medir.

## Próximo: testar no notebook Linux
1. Compilar o player Linux atual (`AnastacioRuntime` + `2.79/python/bin/python3.11`).
2. Colocar em `engine/Linux64/` do projeto (ou do pacote Universal).
3. Rodar `python3 tools/rangearmor/release/scripts/test_universal_linux.py <Game-1.0.0-Universal.zip> --run`
   - Extrai o zip mantendo os bits de execução.
   - Confere o launcher, o runtime, as libs (`ldd`) e o Python.
   - Abre o jogo.
- Ao terminar, apagar `D:\_uni_test`.

## Cuidados descobertos
- No Git Bash, `cp .../Launcher` pode pegar o `Launcher.exe` (sobrescreveu o do Windows). Copiar com Python.
- O caminho do scratchpad passa de 260 caracteres no stage. Testar em pasta curta.
  - Talvez avisar o usuário quando o projeto estiver em caminho longo.

## Mensagem nova do Kitsuy (a analisar)
- Ele fez arquivos de save "travados" que só o player abre: o editor (menu do Blender) não abre.
- Pede o mesmo na engine: um formato novo que só o player carregue, e não o editor.
- Relacionado: `.cooked` e a proteção do `data.dat` do RangeArmor. Avaliar antes de responder.
