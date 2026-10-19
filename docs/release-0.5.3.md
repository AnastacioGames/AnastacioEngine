# Release 0.5.3 — Windows agora, Linux depois

Estado em 2026-10-18: versão subida para 0.5.3 (`ANASTACIO_VERSION_STRING`, About em `wm.py`,
`stage_release_windows.py`, `container-build-22.04.sh`). Mudanças desde a 0.5.2: `79556dad` (módulo Effects
criado pela chuva recebe os sons) e `4d81b518` (partículas e chuva no WebGL2). Notas em
[release-notes-0.5.3.md](release-notes-0.5.3.md).

## Windows (pronto, 2026-10-18)

- `RangeEngine` + `RangeRuntime` + `ninja install` OK; `ctest` 15/15.
- Runtime web de `build-web-release/bin` compilado depois de `4d81b518`; `web/` montado com `stage_release_web.py`.
- Lista de arquivos do pacote idêntica à da 0.5.2 (`blender.crt/` com manifesto, `ucrtbase.dll` solto,
  `sounds/effects/` presente). Zips sem `\` nos nomes. Editor abre a partir da cópia extraída (`-b`).
- RangeArmor sem mudanças desde a 0.5.2 (scripts e `legacy-template-sha256.json` iguais); zip refeito da
  pasta da 0.5.2 com raiz `RangeArmor-0.5.3-windows-x64/`.

```text
e90d6f46ba3ae7b18df111d3ddebca1a6ba9d6527d20a2015e9fa67b620a5a58  AnastacioEngine-0.5.3-windows-x64.zip
58049cf7ac1ceb4396cc4801d97c95445d9f807d9960b225c3696e0bac8f6c9f  RangeArmor-0.5.3-windows-x64.zip
```

## Linux (pendente, PC Linux)

1. Pacote da engine: `VERSION=0.5.3` no `container-build-22.04.sh` (já é o padrão), ver
   [release-0.5.0-linux.md](release-0.5.0-linux.md).
2. RangeArmor Linux: passos em [release-0.5.2.md](release-0.5.2.md#rangearmor-para-linux-pendente-pc-linux),
   trocando 0.5.2 por 0.5.3 (os launchers vêm de `RangeArmor-0.5.3-windows-x64.zip`).
3. Baixar o `SHA256SUMS.txt` da release, acrescentar as duas linhas Linux e subir com `--clobber`;
   atualizar README (linha Linux) e as notas.

## Linux (feito no PC Linux, 2026-10-18)

- Engine: container `localhost/anastacio-linux-builder:ubuntu22.04` + runtime web de `build-web-release/bin`
  recompilado depois de `4d81b518`. **Atenção:** essa imagem tem `VERSION=0.5.1` e `WEB_RUNTIME_DIR=/web-build/bin`
  no ambiente e roda o script do repo como CMD; passe os dois:
  `podman run --rm -e VERSION=0.5.3 -e WEB_RUNTIME_DIR=/work/build-web-release/bin -v $PWD:/work:Z localhost/anastacio-linux-builder:ubuntu22.04`.
  Todas as conferências do `container-build-22.04.sh` OK; `ctest` 10/10.
- `tools/test_*.py` com o editor do pacote extraído (`-b`): todos OK. `test_weather_sounds_auto.py` foi
  atualizado: desde `79556dad` o módulo Effects criado pelo raio/chuva vem com os 14 sons da engine, e o
  teste ainda esperava só os 3 trovões. Os dois que precisam de janela (`test_material_atlas_modal.py`,
  `test_material_atlas_integration.py -- --undo`) não rodaram: este PC está sem `xvfb-run` (código sem
  mudança desde a 0.5.2, onde passaram).
- RangeArmor Linux (primeira vez): `tools/linux/stage_rangearmor_linux.sh` monta o pacote. Painel compilado
  em `rust:1.95-bullseye` (glibc máx. 2.30); `release/data`, `icons`, `scripts` do git; `release/launcher/`
  inteiro do `RangeArmor-0.5.3-windows-x64.zip` (`Launcher` `3cb1ade9…`, `Launcher.exe` `40aecdf5…`);
  sem `ResourceHacker` e sem `godot_backup`. Testes do launcher 4/4. Os testes do painel que chamam
  `python` falham no container (só tem `python3`), não é bug do painel.
- Export Linux64 sem janela: `build_release.py` (com `python3` do sistema, como o painel faz quando o
  pacote não tem `python/bin`) gerou o jogo; o executável copiado para outra pasta abriu o `AnastacioRuntime`
  (parou em "Unable to open a display", esperado sem tela).

```text
5d271afc846cc52073a2d8b830ba68603e31be40369d33eb5698a6a15e442f43  AnastacioEngine-0.5.3-linux-x86_64.tar.xz
cef2d3c228aa7e7167ea27cf2718f4d2bced3662638021996808834f6e85b504  RangeArmor-0.5.3-linux-x86_64.tar.xz
```

- Teste com janela (PC Linux): `RangeArmor Panel` abre sem erro nem biblioteca faltando. Jogo exportado
  (Linux64, `docs/logic-bricks-2-tutorial.blend` como Main File, pasta copiada para fora do projeto) roda pelo
  launcher: shaders compilados no 1º Play, Player/Enemy em z=0,5, screenshot com cena e sombra certas.
  O `Example Game.rasec` do modelo não abre no runtime atual; num projeto real o Main File é o `.range` do jogo.
- Publicada: os dois tar.xz Linux e o `SHA256SUMS.txt` com 4 linhas subiram para a `v0.5.3` (já publicada pelo Windows).
