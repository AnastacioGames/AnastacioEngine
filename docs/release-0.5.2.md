# Release 0.5.2 — novidades e passos no Linux

Estado em 2026-10-18: versão subida para 0.5.2 (`ANASTACIO_VERSION_STRING`, About em `wm.py`,
`stage_release_windows.py`, `container-build-22.04.sh`). **Ainda não publicada**: falta o teste no Linux e
depois montar os pacotes. Regras gerais em [AGENTS.md](../AGENTS.md); empacotamento Windows em
[distribution-0.1.md](distribution-0.1.md) (ler inteiro antes); passos do container em
[release-0.5.0-linux.md](release-0.5.0-linux.md) (trocar 0.5.0 por 0.5.2).

## Testes já feitos no Windows (2026-10-18, sem abrir janela de jogo)

- Build `RangeEngine` + `RangeRuntime` OK.
- `ctest`: 15/15 (o `script_load_modules` falhava por `anastacio_video`, módulo só do jogo; entrou na
  BLACKLIST como o `anastacio_ragdoll_runtime`).
- `tools/test_*.py` em background: baked AO/static, logic_to_python (bricks2, F5, F6, F7, código gerado
  compila), Material Atlas (normal, integração e modal ok/error/cancel/cancel-late), Material Classic,
  PBR UV, categorias da aba Object, layout do preview de textura, sons automáticos do Weather — todos OK.
- `check_trabalho_repetido.py --selftest` OK; os 4 suspeitos do modo normal já existiam na 0.5.1.
- `check_docs.py`: 0 erros. `check_ui_icons.py`: 0 ícones inválidos.

## Linux (2026-10-18, container Ubuntu 22.04)

- Pacote `AnastacioEngine-0.5.2-linux-x86_64.tar.xz` gerado; `ctest` 10/10.
- `tools/test_*.py` com o editor do pacote extraído: baked AO/static, logic F5/F6, Material Atlas
  (normal, integração, undo, restore), Material Classic, PBR UV, categorias do Object, preview de textura OK.
- **Bug achado:** `datafiles/sounds/` não tinha regra de `install` no `creator/CMakeLists.txt`, então os
  sons de efeito (chuva, trovão, explosão, destruição) ficavam fora do pacote e
  `test_weather_sounds_auto.py` falhava. Corrigido; `container-build-22.04.sh` agora confere
  `sounds/effects/trovao1.wav` no tar.
- Reteste depois da correção (com `c1d0c692` do Windows incluído): `test_weather_sounds_auto.py` OK,
  logic F7/bricks2 OK, Material Atlas modal ok/error/cancel/cancel-late OK (com janela, Xvfb), undo/redo OK.
  Falta só o checklist visual abaixo (usuário).
- SHA-256 do pacote Linux:
  `53ba78349b30cf0f55c9136307a1562d4a4bc4b7bb998dc9eaaa3468d663e0a4  AnastacioEngine-0.5.2-linux-x86_64.tar.xz`
- Como rodar certo: `test_logic_convert_f7/bricks2_codegen.py` precisam de `GEN_OUT=<prefixo>`;
  `test_material_atlas_modal.py` e `test_material_atlas_integration.py -- --undo` precisam de janela
  (sem `-b`; no Linux headless use Xvfb). Com `-b` o atlas roda síncrono (`G.background`) e o modal falha.

## Avisos para o Windows (antes de gerar o zip)

1. `git pull` e recompilar `RangeEngine RangeRuntime` + `ninja install` (a regra nova copia os sons).
2. Conferir que existe `build/bin/2.79/datafiles/sounds/effects/` com `chuva.wav`, `trovao1-3.wav`,
   `explosao_*.wav`, `quebra_*.wav`. O teste de sons passou no Windows provavelmente porque o
   `build/bin` local já tinha os arquivos copiados à mão; um zip feito sem o `install` sairia sem som.
3. `python tools/stage_release_windows.py 0.5.2` e conferir a mesma pasta no zip extraído
   (junto com `blender.crt/`, ver [distribution-0.1.md](distribution-0.1.md)).
4. Rodar de novo `test_weather_sounds_auto.py` com o editor do zip extraído.

## Windows refeito com o install novo (2026-10-18)

- `git pull` (21d7c503), `ninja RangeEngine RangeRuntime install`: 14 sons em `build/bin/2.79/datafiles/sounds/effects/`.
- Zip `AnastacioEngine-0.5.2-windows-x64.zip` (SHA256 `fa01903f6d9abfb1a8822742b23d5899a625f79ce5549e827e81a6e5e64a665b`)
  extraído e conferido: `blender.crt/`, `ucrtbase.dll`, `web/` com android-template, 14 sons, sem
  `AnastacioEngine_BakeTest.exe`, nenhum caminho com `\`; About 0.5.2; `test_weather_sounds_auto.py` com
  o editor do zip OK (copia `chuva.wav` e `trovao1-3.wav` para `sounds/` do projeto).
- Falta: refazer o zip da RangeArmor (launcher mudou desde a 0.5.1) e montar o `SHA256SUMS.txt` final.

## Novidades desde a 0.5.1

### Logic Bricks 2.0
- Grupos de bricks recolhíveis, lista de grupos na barra lateral, mover grupos para cima/baixo.
- Actuator **Wait**, modo **Finished** no sensor Actuator e botão **Then** (cria Finished + And).
- Actuator **Video** que controla o Video Player.
- Presets em Add > Preset, histórico da lógica, pausa ao disparar e cena tutorial
  (`docs/logic-bricks-2-tutorial.blend`).
- Janela Logic Bricks no Debug Mode e **Highlight Active** (realce ao vivo dos bricks que disparam).
- `logic_to_python` converte Wait, Video e Finished.

### Vídeo
- Componente **Video Player** (painel na aba Object), loop sem engasgo, B-frames e timebase fina,
  texturas de vídeo mais nítidas, fade em cutscene de tela cheia e legendas `.srt`.
- O export copia os vídeos do Video Player.

### Texto
- Atlas bitmap para Text do jogo (gerado da fonte, estilos, cirílico/kana), preview na viewport.
- Text Editor: barras flutuantes, painel de legendas, fechar abas pelo botão direito.

### Render, sombras e efeitos
- SSGI nativo mais fácil (Check Scene, só problemas que bloqueiam) e mais suave (Denoise, upsampling bilateral).
- CSM: referência pela luz Sun, 2 ou 3 cascatas, Auto Bias (também em VSM), custo menor no modo Camera.
- Camera FX: Directional Blur por reprojeção de profundidade.
- Baked Lighting moderno (AO e iluminação estática; correção do kernel OpenCL).

### Som
- Sons de efeito incluídos na engine (explosão, destruição, chuva, trovão) e preenchimento automático do
  Effects ao salvar/rodar; volume e atraso do trovão pela distância.
- Liga/desliga som por efeito; one-shots com pitch e volume variados.

### Interface e outros
- Aba Object dividida em Object/Game/Transform; abas Physics/Damage e Sky/Atmosphere/Properties.
- Painéis de Use Shadow, Weather Rain e Weather reorganizados; partículas GPU com campos XYZ em 3 colunas.
- Game Layers fixadas pelo popover do cabeçalho e painel N.
- Ragdoll: preview de autoria, componente comum e presets de física.
- Web/Android: botão para alternar os controles de toque e acessar os menus.
- i18n: textos que faltavam em pt_BR, es e ru.

## Checklist no Linux (usuário confirma o que é visual)

Gerar o pacote no container (ver [release-0.5.0-linux.md](release-0.5.0-linux.md), o padrão agora é 0.5.2),
extrair numa pasta limpa e conferir:

- [x] About mostra 0.5.2.
- [x] `ctest` no build Linux passa (inclui `script_load_modules` e `bmesh_bevel`).
- [x] `2.79/datafiles/sounds/effects/` está no tar; chuva e trovão tocam sozinhos numa cena com Weather Rain.
- [x] Video Player: vídeo toca em loop, fade e legenda `.srt` aparecem; o actuator Video controla.
- [x] Logic Bricks 2.0: abrir `docs/logic-bricks-2-tutorial.blend`, rodar, ver Highlight Active e a janela
      no Debug Mode (F4).
- [x] Text do jogo com atlas bitmap; "Edit Externally" abre o editor do sistema (no Linux usa o fallback).
- [x] SSGI, CSM com 2/3 cascatas e Directional Blur sem erro de shader no terminal.
- [x] Baked Lighting (AO e estática) e Material Atlas no editor do pacote.
- [x] Ragdoll e Game Layers fixadas funcionam.
- [x] Rodar os `tools/test_*.py` em background com o editor do pacote (mesmos comandos do Windows).

## Depois do teste: lançar

1. Corrigir o que o Linux apontar e commitar.
2. Windows: `python tools/stage_release_windows.py 0.5.2` + `python tools/stage_release_web.py <pasta>`;
   validar extraindo o zip (pasta `blender.crt/`).
3. Linux: tar.xz do container + `sha256sum`; juntar no `SHA256SUMS.txt` com Windows e RangeArmor.
4. README: trocar os links de download para 0.5.2 e tirar o "(em teste...)" da seção Novidades; corpo da release = `docs/release-notes-0.5.2.md`. Atualizar o README (downloads), criar a tag `v0.5.2` e a release no GitHub.

## Pendências conhecidas (não bloqueiam)

- Web: feixe do Spot na Volumetric Fog não aparece no navegador.
- Sombra colorida: cor no Sun com CSM ainda pendente.
- OIDN no Linux (bake usa box blur).

## Publicação (rascunho criado no Linux, 2026-10-18)

Release **v0.5.2 em rascunho** no GitHub com `AnastacioEngine-0.5.2-linux-x86_64.tar.xz` e um
`SHA256SUMS.txt` com as linhas do Linux e do Windows. README já aponta para os links da 0.5.2.
No PC com Windows, para terminar:

1. Refazer o zip da RangeArmor 0.5.2 e calcular o SHA-256.
2. Acrescentar a linha da RangeArmor ao `SHA256SUMS.txt` (baixe o do rascunho com
   `gh release download v0.5.2 -p SHA256SUMS.txt`).
3. `gh release upload v0.5.2 AnastacioEngine-0.5.2-windows-x64.zip RangeArmor-0.5.2-windows-x64.zip SHA256SUMS.txt --clobber`
4. Conferir os 4 arquivos no rascunho e publicar: `gh release edit v0.5.2 --draft=false --latest`
   (cria a tag `v0.5.2` no `main`).

## RangeArmor 0.5.2 (Windows, 2026-10-18)

- Pasta `build/release-staging/RangeArmor-0.5.2-windows-x64/` montada a partir do zip da 0.5.1, com os
  scripts atuais (`common.py`, `get_rangeengine_currentplatform.py`, `prepare_cooked.py`: nome
  `AnastacioRuntime` também no Linux) e `Launcher.exe` recompilado (`cargo +1.95.0 test` 4/4).
- `legacy-template-sha256.json` ganhou `Linux64` com o hash do `Launcher` Linux da 0.5.0/0.5.1
  (`c4f0f3e4…`): projetos antigos passam a usar o launcher novo ao exportar.
- **Falta (PC Linux):** compilar o `Launcher` Linux, que procura `AnastacioRuntime` com fallback para
  `RangeRuntime` (o da 0.5.1 não acha o runtime do pacote 0.5.2):

  ```bash
  cd tools/rangearmor/source/launcher   # Cargo.lock versão 3: serve o cargo 1.75 do apt; se reclamar de versão, use o rustup
  cargo test --locked && cargo build --release --locked --target-dir /tmp/ra-launcher
  strip /tmp/ra-launcher/release/rangearmor   # opcional; upx -5 se tiver
  sha256sum /tmp/ra-launcher/release/rangearmor
  cp /tmp/ra-launcher/release/rangearmor /tmp/Launcher-linux && gh release upload v0.5.2 /tmp/Launcher-linux --clobber
  ```

  O hash novo não pode ser `c4f0f3e4…`. Depois o Windows baixa esse asset para
  `release/launcher/Launcher`, apaga o asset temporário do rascunho, gera o zip da RangeArmor, sobe com
  o zip do Windows e o `SHA256SUMS.txt`, e publica.

## Retorno do PC Linux (2026-10-18, 15:40)

### Launcher Linux da RangeArmor: feito

- Compilado em container `rust:1.95-bullseye` (glibc máx. 2.30; no host 24.04 ficava exigindo 2.39),
  `cargo test --locked` 4/4, `strip`. SHA-256 `3cb1ade91d3440c300328adfcb13a7aaf166b77f84f8f262d30293ec25dcb678`
  (diferente do legado `c4f0f3e4…`). Já está no rascunho como asset **`Launcher-linux`**.

### BLOQUEIA A PUBLICAÇÃO: `.cooked` de outro compilador quebra a colisão

- Sintoma (teste visual no Linux): no `docs/logic-bricks-2-tutorial.blend`, Player e Enemy atravessam o chão
  ao dar Play. Causa: o `.cooked` commitado (gerado no Windows) foi carregado. O BVH de malha estática é
  gravado com `btOptimizedBvh::serializeInPlace` (layout de memória do compilador): BVH do MSVC é lixo no
  GCC e vice-versa, e o cabeçalho só conferia hash/vértices/`version == 1`. Reproduzido: com o cache do
  Windows o Player cai até z=-18; com cache gerado no Linux para em z=0,5.
- Também vale ao contrário (cache do Linux no Windows) e para jogo exportado **do Windows para Linux**
  com `.cooked` pronto.
- Correção (commitada e validada no container Linux): `CcdPhysicsController.cpp` grava a versão do BVH
  com compilador + `sizeof(btOptimizedBvh)` e recusa BVH de outro compilador (reconstrói);
  `CcdCookedData::AddBvh` substitui a entrada recusada para o `.cooked` ser regravado certo.
  `docs/logic-bricks-2-tutorial.cooked` e `.blend1` saíram do git; `*.cooked` no `.gitignore`.
- **Windows, depois desse commit:** `git pull`, recompilar `RangeEngine RangeRuntime` + `ninja install`
  (só `.cpp` mudou), refazer o zip da engine e o da RangeArmor, atualizar o `SHA256SUMS.txt` e só então
  publicar. Conferir: um `.cooked` velho do Windows deve mostrar `bvh 1 loaded, … 1 new` no primeiro Play
  (recusado e refeito) e física normal.

- Validado: cache do Windows → 1ª execução recusa e refaz o BVH (`1 new`), Player/Enemy param em z=0,5;
  2ª execução usa o cache regravado. Pacote Linux refeito com a correção e trocado no rascunho:
  `73a960e4a0b43225017a863bd541c40944447f125d8e5c7fe37b5563cce833fa  AnastacioEngine-0.5.2-linux-x86_64.tar.xz` (o `SHA256SUMS.txt` do rascunho já tem esta linha).

### Play Standalone não abria no Linux (corrigido)

- `anastacio_cook._runtime_path()` só procurava `RangeRuntime` fora do Windows; o pacote Linux tem
  `AnastacioRuntime` desde a 0.5.1, então Standalone dava "Player path not found" (o Play embutido
  funcionava). Agora procura `AnastacioRuntime` e cai para `RangeRuntime`. Mesma função alimenta o Cook
  da exportação (`RANGEARMOR_COOK_RUNTIME`). Padrão `EngineLinux64` da exportação e a checagem do runtime
  no projeto também passaram a `AnastacioRuntime` (o `common.py` da RangeArmor já aceita os dois).
- Validado: `wm.blenderplayer_start` com o editor do pacote abre o runtime e a cena roda (Player em z=0,5).
- **Windows:** não muda nada no comportamento (lá já era `AnastacioRuntime.exe`); só entra no `git pull`.
  O pacote Linux será refeito com isso e trocado no rascunho junto com o `SHA256SUMS.txt`.
- Pacote Linux refeito com as duas correções (física do `.cooked` e Standalone) e trocado no rascunho:
  `1a4f7f00ab82466658aac096528200748d9e5833312ccc4b048ed29b5fa3c0e7  AnastacioEngine-0.5.2-linux-x86_64.tar.xz` (linha já no `SHA256SUMS.txt` do rascunho;
  falta trocar a do zip Windows e acrescentar a da RangeArmor).

### Linux: checklist visual aprovado (2026-10-18)

- Usuário testou o pacote final (`1a4f7f00…`) extraído: visual OK (Play e Standalone, tutorial Logic Bricks 2.0,
  som, vídeo, render). Log do terminal sem erro de shader, traceback ou crash. **Linux liberado.**
- **Falta só o Windows:** `git pull`, recompilar + `ninja install`, refazer zip da engine e da RangeArmor
  (com o `Launcher-linux` do rascunho), corrigir o `SHA256SUMS.txt` (linha Windows nova + RangeArmor),
  `gh release upload v0.5.2 ... --clobber`, apagar o asset `Launcher-linux` do rascunho e publicar com
  `gh release edit v0.5.2 --draft=false --latest`.

## Pacotes finais (Windows, 2026-10-18, depois de f4f1181b)

- Windows recompilado com as correções do Linux (física do `.cooked`, Standalone): ctest 15/15,
  `tools/test_*.py` sem erro, zip extraído conferido (About 0.5.2, `blender.crt/`, sons, `web/`).
- RangeArmor 0.5.2: scripts novos, `Launcher.exe` recompilado, `Launcher` Linux do rascunho
  (`3cb1ade9…`, bate com o registrado), raiz `RangeArmor-0.5.2-windows-x64/`.
- `SHA256SUMS.txt` final (em `build/release-staging/SHA256SUMS.txt`):

  ```
  1a4f7f00ab82466658aac096528200748d9e5833312ccc4b048ed29b5fa3c0e7  AnastacioEngine-0.5.2-linux-x86_64.tar.xz
  5a6d7756ae99bfec4582cae6bb6b91f08224afce53c36f83a199f25f8d24b3c0  AnastacioEngine-0.5.2-windows-x64.zip
  4e04cf1518ad321a7678221d5a3fb310e6fe5a6b26011d23707ba98750a97a8d  RangeArmor-0.5.2-windows-x64.zip
  ```

- Falta: subir para o rascunho e publicar (precisa da autorização do usuário):

  ```bash
  gh release upload v0.5.2 build/dist/AnastacioEngine-0.5.2-windows-x64.zip build/dist/RangeArmor-0.5.2-windows-x64.zip build/release-staging/SHA256SUMS.txt --clobber
  gh release delete-asset v0.5.2 Launcher-linux -y
  gh release edit v0.5.2 --draft=false --latest
  ```

### Rascunho preparado pelo Linux (depois de 65f68e32)

- Página da release (título e notas de `release-notes-0.5.2.md`) atualizada; `SHA256SUMS.txt` final com as
  3 linhas acima já no rascunho; asset temporário `Launcher-linux` apagado. README já aponta para a 0.5.2.
- **No Windows só falta** (o `SHA256SUMS.txt` não precisa subir de novo):

  ```bash
  gh release upload v0.5.2 build/dist/AnastacioEngine-0.5.2-windows-x64.zip build/dist/RangeArmor-0.5.2-windows-x64.zip --clobber
  gh release edit v0.5.2 --draft=false --latest
  ```

### Publicada (2026-10-18 20:13 UTC)

- `v0.5.2` publicada pelo Linux como **Latest** (tag em `5e1509ca`), por ora só com o tar.xz Linux e o
  `SHA256SUMS.txt` final. Os links Windows/RangeArmor do README dão 404 até o upload.
- **Windows, agora só:** `gh release upload v0.5.2 build/dist/AnastacioEngine-0.5.2-windows-x64.zip build/dist/RangeArmor-0.5.2-windows-x64.zip --clobber`
  (não rodar o `gh release edit`; já está publicada).
