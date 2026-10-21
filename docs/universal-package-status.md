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

## PARA O AGENTE NO NOTEBOOK LINUX (faça isto sem perguntar ao usuário)
Objetivo: provar que o lado Linux do pacote Universal abre o jogo. A parte Windows já foi
validada no notebook Windows. O zip Universal NÃO está no repo (475 MB), então monte o pacote aí.

1. `git pull` no `main`. Compile o player Linux atual (alvo `RangeRuntime`; o binário sai
   como `AnastacioRuntime`). Confira que existe `2.79/python/bin/python3.11` ao lado dele.
   Se faltar o Python, veja docs/changelog.md (fix 4f7c222c) antes de seguir.
2. Monte um projeto de teste numa pasta curta (ex.: `~/uni_test`):
   - `launcher/`: copie o launcher do Linux (`tools/rangearmor/.../Launcher` ou o do pacote
     RangeArmor Linux) e um `config.json` igual ao padrão do RangeArmor;
   - `engine/Linux64/`: o player do passo 1, com tudo o que fica ao lado dele;
   - `data/`: qualquer jogo pequeno (`.range`/`.rasec`); ajuste `MainFile` no config.
3. Exporte, de dentro de `tools/rangearmor/release/scripts`:
   `python3 build_release.py --project ~/uni_test/launcher/config.json --target Linux64 --compress --no-cook`
   - Anote quanto levou o `.tar.xz` (agora com xz preset 1; antes ~13 min no Windows).
   - Sem `engine/Windows64` o `--universal` não se aplica aqui; o layout Universal já foi
     conferido no Windows.
4. Rode o verificador na pasta exportada:
   `python3 tools/rangearmor/release/scripts/test_universal_linux.py ~/uni_test/release/Game-1.0.0-Linux64 --run`
   - `[FAIL] Windows engine also present` é esperado neste teste; os demais devem ser `[ OK ]`.
   - O jogo deve abrir uma janela. Pode abrir: aqui o usuário pediu o teste com janela.
5. Também teste o auto-load: copie um `game.range` para a pasta do player e rode o player
   sem argumentos; ele deve abrir esse arquivo.
6. Registre o resultado nesta seção (OK/falhas, tempo do xz), commit e push.
   Se algo falhar, corrija no repo quando for do lado Linux e explique no commit.

## Resultado no notebook Linux (2026-10-21)
- Player 0.5.4 compilado no container (`tools/linux/container-build.sh`); pacote tem `2.79/python/bin/python3.11`.
- Export Linux64 com `--compress --no-cook`: 53 s no total, incluindo o `.tar.xz` (335 MB) com xz preset 1.
- `test_universal_linux.py --run`: todos `[ OK ]`, exceto `[FAIL] Windows engine also present` (esperado).
  O jogo abriu janela 640x480 pelo launcher `Game`.
- Auto-load OK: `game.range` ao lado do player, player sem argumentos -> "no game file given, loading .../game.range" e janela.
- Falha encontrada (aberta): o template `Example Game.rasec` do RangeArmor 0.5.4 não carrega no player 0.5.4
  ("loading ... failed:" com mensagem vazia), gzip ou descompactado. `.range` normais carregam.
  No teste usei a demo Destruction como `data/game.rasec`.
  CORRIGIDO no Windows: a chave do .rasec embute a versão (template salvo na 1.5, engine 1.6).
  O leitor (readfile.c) agora aceita 1.6 e 1.5; Example Game.rasec abre no player Windows.
  Linux (2026-10-21, 1a8490da): CONFIRMADO, Example Game.rasec abre janela no player 0.5.4 Linux.
  Novo ponto (aberto): o script do template faz `import range` / `from range.render import ...` (API 1.5);
  a engine só registra `bge` (KX_PythonInit.cpp), então dá "No module named 'range'" e o
  PlayerCollision não roda. Opções: alias `range` -> `bge` no player, ou atualizar o template.
- Obs.: após falha de carga, o player tenta ler o próprio executável (checagem de jogo embutido) e imprime o usage; a mensagem confunde.

## Pendente no Windows
- Apagar `D:\_uni_test` quando o teste Linux passar.

## Cuidados descobertos
- No Git Bash, `cp .../Launcher` pode pegar o `Launcher.exe` (sobrescreveu o do Windows). Copiar com Python.
- O caminho do scratchpad passa de 260 caracteres no stage. Testar em pasta curta.
  - Talvez avisar o usuário quando o projeto estiver em caminho longo.

## Mensagem nova do Kitsuy (a analisar)
- Ele fez arquivos de save "travados" que só o player abre: o editor (menu do Blender) não abre.
- Pede o mesmo na engine: um formato novo que só o player carregue, e não o editor.
- Relacionado: `.cooked` e a proteção do `data.dat` do RangeArmor. Avaliar antes de responder.
