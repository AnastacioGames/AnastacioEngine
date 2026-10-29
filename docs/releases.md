# Histórico de releases

Uma seção por versão: notas para o usuário, como foi montada e o que ficou aberto. O procedimento vigente
(Windows com `blender.crt/`, Web, container Linux, `SHA256SUMS.txt`) está em
[distribution-0.1.md](distribution-0.1.md). Regras gerais em [AGENTS.md](../AGENTS.md).

## Pendências abertas

- Web: o feixe do Spot na Volumetric Fog não aparece no navegador (no desktop aparece).
- Linux: o OIDN não está no apt do container; o bake de lightmap usa box blur. Não é bug.
- Testes que precisam de janela (`test_material_atlas_modal.py`, `test_material_atlas_integration.py -- --undo`)
  não rodaram no Linux da 0.5.3 (PC sem `xvfb-run`).

## Dicas comuns de montagem

- Use um clone separado para o container Linux: `build-linux*/` não serve para o host.
- A imagem `localhost/anastacio-linux-builder:ubuntu22.04` traz `VERSION` e `WEB_RUNTIME_DIR` antigos no
  ambiente. Passe os dois:
  `podman run --rm -e VERSION=<versao> -e WEB_RUNTIME_DIR=/work/build-web-release/bin -v $PWD:/work:Z localhost/anastacio-linux-builder:ubuntu22.04`.
- Teste sempre o pacote extraído numa pasta limpa, nunca a pasta de build.
- `test_logic_convert_f7.py` e `test_bricks2_codegen.py` precisam de `GEN_OUT=<prefixo>`. Os testes de
  Material Atlas com modal precisam de janela (sem `-b`; no Linux headless use Xvfb).
- Depois de mudar regra de `install`, rode `ninja install` antes de montar o zip. Na 0.5.2 os sons de efeito
  só passaram no Windows porque `build/bin` tinha cópia manual.
- Launcher Linux da RangeArmor: compile em `rust:1.95-bullseye` (glibc máx. 2.30). O registrado é
  `3cb1ade9…`; o legado `c4f0f3e4…` não acha o `AnastacioRuntime`. Os launchers não ficam no git: vêm do
  zip Windows publicado da RangeArmor.
- Abra janelas do jogo/editor só quando o usuário pedir; o resto valide em background.

## 0.6.1

Estado: **em preparo** (versão `0.6.1` no executável, About e scripts de release). Pacotes Linux montados e
testados em 2026-10-28 (seção "Linux" abaixo); Windows e Wine pendentes.

Notas para o usuário:

- **Tempo de jogo:** espera entre quadros no estilo spin/sleep (sugestão do Kitsuy), com a precisão do sleep
  medida ao abrir; no Wine e com timer de 15 ms o jogo não fica mais lento.
- **Fixed Timestep suave:** o desenho é interpolado entre os passos de lógica, então a imagem fica lisa mesmo
  quando o PC desenha num ritmo diferente do jogo (`RANGE_NO_INTERP=1` desliga, para comparar).
- **Fixed Timestep ligado por padrão nas cenas novas.** Jogos existentes mantêm a opção como estava; no modo
  legado, um PC que desenha abaixo da taxa de lógica deixa o jogo em câmera lenta.
- **Desempenho em iGPU:** céu e lens flare mais leves, qualidade de lens flare e estrelas.
- **Performance Report:** simulador de PC fraco, tempo de GPU por etapa, céu como etapa própria e selo de PC antigo.
- **Correções:** troca de cena online desenha o World da cena nova; recarga de shaders após o clarão de explosão;
  UI Tree mantém o layout ao organizar; botões de toque e tela de carregamento na Web; gravação de tela mais rápida.

Texto da página do GitHub: [release-notes-0.6.1.md](release-notes-0.6.1.md). Divisão Windows/Linux: [release-0.6.1-plano.md](release-0.6.1-plano.md).

### Linux (2026-10-28, notebook Linux, clone `~/AnastacioEngine-build050` em `034f480a`)

Pacotes em `~/AnastacioEngine-build050/build-linux/dist/` (enviados em 2026-10-28 ao rascunho `v0.6.1` junto com `SHA256SUMS-linux.txt`; o Windows publica):

- `AnastacioEngine-0.6.1-linux-x86_64.tar.xz` (264 MB) sha256 `71494a7f5179d2f6eb8d41d29e00f827d8dcd1db08810b939d3b71fd00f0264b`
- `RangeArmor-0.6.1-linux-x86_64.tar.xz` (7,1 MB) sha256 `bfa3cf146bd72801fb842c258cefca19d12e1ff4e177fdfdefbc1836cf23eefc`

Resultados:

1. Timing nativo (Intel RPL-P, 60/120 fps, [timing_linux_result.txt](../timing_linux_result.txt)): sem câmera
   lenta nem diferença de física; o modo legado ficou liso (`step_cv` 4,2 → 0,1). Com a interpolação ligada o
   `fixed` fica um pouco menos liso quando a tela e a lógica têm o mesmo ritmo (`step_cv` 0,3–0,5 contra
   0,0–0,1 com `RANGE_NO_INTERP=1`). Wine não testado: não há build Windows atual nesta máquina.
2. Runtime Web recompilado (`web-runtime-release-linux`, manifesto com 242 módulos) e incluído no pacote.
3. Container (`VERSION=0.6.1`): build e pacote OK. `ctest` 10/10.
4. `testar-release.sh 0.6.1`: tudo OK (ldd, arquivos, Python 3.11.9, versão 0.6.1 no binário, os 13
   `tools/test_*.py`, runtime `--server` 60 frames e `test_material_atlas_modal` com janela).
5. Export Web pelo editor do pacote com a cena de Compositing: preflight sem problemas; pacote rodou no Chrome
   headless (`verify-package.cjs`, rc 0) e o filtro do Compositing foi criado. Sem GPU no headless, precisa de
   `--use-angle=swiftshader --enable-unsafe-swiftshader`; sem isso o runtime não cria a janela.
6. RangeArmor: painel recompilado em `rust:1.95-bullseye`; launchers do pacote 0.6.0 (não mudaram,
   `3cb1ade9…`). Export **Universal com Compile Scripts** de um projeto de teste: `data/` só com `.rasec`,
   `.cooked` e `.pyc`; `test_universal_linux.py --run` OK e o jogo rodou o módulo a partir do `.pyc`
   (`MARKER_PYC frames=60`). Lado Windows do Universal foi um `.exe` falso.
7. Com janela (Wayland): editor do pacote abre (binário `AnastacioEngine 0.6.1`); jogo de teste no modo Fixed
   rodou 8 s sem câmera lenta (`real=8.004`, `step_cv=0.3`).

Pendente: Wine, pacotes Windows (o runtime Web pode ser copiado de `build-web-release/bin` do Linux),
`SHA256SUMS.txt` com os quatro arquivos, README/site e publicação.

## 0.6.0

Estado: **publicada completa em 2026-10-27** (tag `v0.6.0`, splash novo `47b71d9e`). Linux primeiro; Windows
anexado no mesmo dia (ver "Windows final").

### Notas para o usuário (rascunho)

Primeira versão grande depois da 0.5.4. Novidades:

- **Logic Tree:** lógica por nós no Node Editor (árvore, Then, Frames de Estado, todos os bricks, Run Python,
  receitas, depuração e destaque ao vivo dos nós que dispararam).
- **UI Tree:** menus e HUD 2D por nós, também na Web/Android; nó **Dialogue Box** e Setup Dialogue no objeto
  Text. **Text Boxes** no jogo (quebra de linha, páginas, máquina de escrever).
- **Compositing no jogo:** Blur, Glare, Directional Blur, Color Correction, Tonemap, Dilate/Erode, Z Combine,
  Crop e Bilateral Blur. Node Editor com faixa de efeitos e presets (Shader, Logic, UI) no estilo Blender 5.
- **Render:** sombra de sol em cascatas (CSM) no Principled, PCSS (sombra suave por distância), SH9 em sondas,
  partículas flipbook, Sky Quality (céu leve no celular), HLOD com troca por célula, Auto Static Batch.
- **Ferramentas:** Scene Doctor (colisão simplificada, DDS, Prepare Audio), Performance Report
  (Game ▸ Performance), FPS Counter, Range Trace por módulos, barra e menus da 3D View no estilo Blender 5.
- **Smart 2D Filter:** uniforms Bool, Choice e Object; Custom Filter com Smart Filter.
- **Python:** `Range.types.TrackLine` para IA de corrida, `setBoneRotationOffset`, World Sound por mensagem,
  Start Asleep na física, escala de tempo que vale para animação, cutscene e física juntas.
- **Export:** Compile Scripts entrega os scripts de `data/` só como `.pyc`; o `.range` aberto sai do pacote
  quando há `.rasec`; pacote Universal (Windows + Linux numa pasta); player acha o jogo na própria pasta.

Correções: revisão ampla do núcleo (KX_GameObject, KX_Scene, SceneGraph, relógio, joystick no catch-up,
LibLoad/LibFree, callbacks de colisão, mensagens de bricks), crash do Logic Editor com armaduras, cutscene
com espera, relatório de crash sem PDB, menos CPU na leitura de arquivos e nos passes de sombra.

Downloads: `AnastacioEngine-0.6.0-windows-x64.zip`, `AnastacioEngine-0.6.0-linux-x86_64.tar.xz`,
`RangeArmor-0.6.0-windows-x64.zip`, `RangeArmor-0.6.0-linux-x86_64.tar.xz` e `SHA256SUMS.txt`.

### Montagem

Feito (2026-10-27): `ANASTACIO_VERSION_STRING`, About (`wm.py`) e exemplos/padrões dos scripts de release em
0.6.0. Novo `tools/linux/testar-release.sh` (pacote extraído: `ldd`, arquivos, Python 3.11, os 14
`tools/test_*.py`, e `AnastacioRuntime --server` numa cena que roda 60 frames, de
`tools/linux/release_smoke_scene.py`; a cena foi conferida no build Windows). O script foi conferido no WSL com
o pacote antigo 0.5.1: acusou o que de fato falta nele (nomes `RangeEngine`, sem `python3.11`, sem sons). As
bibliotecas de som/OpenGL/X11 do sistema ausentes na máquina viram aviso, não falha.

Pré-conferência no Windows (2026-10-27), antes do Linux:

- Build incremental com a 0.6.0 + `ninja install`; `ctest` 15/15; os 13 `tools/test_*.py` headless OK.
  `test_baked_static_smoke.py` estava velho (procurava o texto em português trocado na 0.5.4) e foi corrigido.
- Traduções: 80 textos novos desde a 0.5.4 em `translations_more.py` (pt_BR, es, ru), achados pelas auditorias
  `tools/tests/web_profile/i18n_*.py` cruzadas com o diff `v0.5.4..HEAD`. pt_BR sem tradução: RNA 1166 → 1110,
  layouts 121 → 100. O que sobra são nomes próprios, códigos e enums antigos. es/ru pedem revisão nativa.
- Runtime `--server` com marcador de 120 frames: Compositing (sem o fim no frame 5 da própria cena), Bricks 2.0
  (tutorial), Flipbook, HLOD (616 objetos), PCSS e UI Tree. Todas chegaram aos 120 frames.
- Não feito aqui: export Universal com Compile Scripts (precisa do player Linux na RangeArmor, que não existe
  neste PC; o Compile Scripts já foi validado no Windows) e runtime Web (o build é feito em container).

Na máquina Linux, num clone separado com o main atualizado:

1. Runtime Web: recompilar o preset `web-runtime-release` com o main atual (o de `build-web-release/` é de
   2026-10-25, antes do Compositing e das revisões de relógio/KX). Conferir o manifesto regenerado.
2. `VERSION=0.6.0 WEB_RUNTIME_DIR=/work/build-web-release/bin bash tools/linux/container-build.sh`.
3. `bash tools/linux/testar-release.sh 0.6.0` (com `xvfb-run` instalado roda também o runtime e o teste modal).
4. Export Web pelo editor do pacote (`tools/web/validate-web.py --export`).
5. RangeArmor Linux: painel em `rust:1.95-bullseye` e `tools/linux/stage_rangearmor_linux.sh 0.6.0`
   (launchers do `RangeArmor-0.5.4-windows-x64.zip`; o launcher não mudou). Rodar
   `tools/rangearmor/release/scripts/test_universal_linux.py` e exportar um jogo com **Compile Scripts**
   ligado: o player Linux tem de rodar só com `.rasec` e `.pyc` (só foi testado no Windows).
6. Com janela: editor abre, jogo exportado roda pelo launcher.

Pacotes Windows montados (2026-10-27), ainda sem zip final da engine:

- `build/release-staging/AnastacioEngine-0.6.0-windows-x64/` com `tools/stage_release_windows.py 0.6.0 --no-zip`
  + `stage_release_web.py`. Lista igual à do zip 0.5.4 mais 56 arquivos novos de `2.79/scripts` e
  `rgbcx-license.txt`; nada sumiu. Logs de depuração (`_props.log` etc.) entravam: o script agora exclui `.log`.
  Pasta conferida: `blender.crt/`, `0.6.0` no executável e runtime rodando a cena de teste com Python 3.11.
  O `web/runtime` dela ainda é o de 2026-10-25.
- RangeArmor: novo `tools/stage_rangearmor_windows.py` monta o zip a partir do da versão anterior (launchers,
  Godot de backup) com painel recompilado e `release/` do git.

### Teste Linux (2026-10-27, notebook Linux, clone `~/AnastacioEngine-build050`)

Pacotes em `~/AnastacioEngine-build050/build-linux/dist/` (engine em `0079d62f`; a RangeArmor com `9d966d1e`):

- `AnastacioEngine-0.6.0-linux-x86_64.tar.xz` (281 MB) sha256 `43cdca3eb355834ea3a8eee2ecbcb6fecd05f4f7abefa3787fc0853a2b05a826` (rebuild com o splash novo, 23/23)
- `RangeArmor-0.6.0-linux-x86_64.tar.xz` (7,4 MB) sha256 `282b9dc5331568056136ec1aac944d785cedda7667148e217a0d8bb5d33bf123`

Resultados:

1. Runtime Web (`web-runtime-release-linux`, com `PYTHON_WASM_ROOT_DIR=~/web-python-poc/python-wasm-web`)
   **não linkava**: a faixa de presets chama UI em `rna_ui_api.c` (`UI_but_operator_ptr_get`, `uiLayoutGetBlock`,
   `UI_block_layout_set_current`, `uiDefIconButO_ptr`, `UI_but_flag_enable`). Stubs em
   `bad_level_call_stubs/stubs.c` (`ef7ba789`). O Windows vai bater no mesmo erro se ainda não tiver
   recompilado o runtime Web.
2. Build do container **falhou** em `KX_CompositorFilter.cpp` (`strcmp` sem `<cstring>`; o MSVC aceita).
   Corrigido em `6e82c8ab`. Depois disso, build e pacote OK.
3. `testar-release.sh 0.6.0`: **23/23 OK** (ldd, arquivos, Python 3.11.9, os 14 `tools/test_*.py`, runtime
   `--server` 60 frames e `test_material_atlas_modal` com janela, via `DISPLAY`).
4. Export Web pelo editor do pacote (`validate-web.py --export`) com a cena de Compositing: preflight sem
   problemas; pacote rodou no Chrome headless (`verify-package.cjs`, rc 0), filtro do Compositing criado.
5. RangeArmor Linux: painel recompilado em `rust:1.95-bullseye` (GLIBC máx. 2.30), launcher `3cb1ade9…`
   conferido. Export **Universal com Compile Scripts**: `data/` só com `.rasec`, `.cooked` e `.pyc`;
   `test_universal_linux.py --run` 7/7 OK e o jogo rodou o módulo a partir do `.pyc` (marcador
   `MARKER_PYC frames=60`). O lado Windows do Universal foi um `.exe` falso (não há runtime Windows aqui).
   Bug achado e corrigido (`9d966d1e`): o cook rodava com `cwd=data/` e o `imgui.ini` criado ia no pacote.
6. Com janela (pedido do usuário): editor abre; jogo de Compositing roda com o efeito visível; Node Editor
   troca de área para Shader/Compositing/Logic Tree/UI Tree sem crash.
7. **Rec fechava o editor no Linux** (achado pelo usuário): sem FFmpeg e sem AVI, `BKE_movie_handle_get`
   devolvia NULL e `BKE_screencast_begin` o copiava. Correções (`f2638a71` e `0079d62f`): checagem de
   NULL, `WITH_CODEC_AVI` ligado nos presets Linux (grava `.avi` MJPEG; MP4 H.264 segue só no Windows),
   índice AVI sem buracos, nome `.avi` (antes `.mp40001-0001.avi`, e o Play Last do Standalone não achava),
   parada em 1,9 GB, buffer `FILE_MAX` no `start_avi`. **Vale também no Windows:** a captura agora arredonda
   o tamanho para baixo (arredondar para cima perdia todos os quadros com janela de largura/altura ímpar).
   Conferido: gravação de 3,8 s → 114 quadros a 30 fps, índice sem entradas vazias, janela 1854x1131.
   `testar-release.sh` de novo 23/23.

Depois do Linux, no Windows: `git pull` (traz `ef7ba789`, `6e82c8ab`, `9d966d1e` e as correções do Rec), `ninja install`, recompilar o runtime Web (ou copiar o do Linux) para `build-web-release/bin`, rodar de novo
`stage_release_web.py` na pasta e `stage_release_windows.py 0.6.0 --zip-only`; refazer o zip da RangeArmor (`prepare_cooked.py` mudou em `9d966d1e`) e o que mais
mudar; extrair os zips numa pasta limpa e testar; `SHA256SUMS.txt`, README e site.

### Windows final (2026-10-27)

`git pull` até `458c5a95`; `ninja RangeEngine RangeRuntime install`; runtime Web recompilado em
`build-web-release` (vcvars64 + `emsdk_env.bat`, manifesto regenerado); `stage_release_windows.py 0.6.0 --no-zip`,
`stage_release_web.py` e `--zip-only`; RangeArmor refeita com `stage_rangearmor_windows.py` (19 arquivos, como a
0.5.4). Zips sem `\` nem `.log`/`imgui.ini`. Extraídos em pasta limpa: editor `-b` abre (0.6.0 no binário) e
`AnastacioRuntime --server` na `release_smoke_scene.py` grava `ok 60 3.11.7`.

- `AnastacioEngine-0.6.0-windows-x64.zip` (203 MiB) sha256 `d15f8e5d1626c117d2d0ba6dc537dc166ad732a38b1c39a379b84afa17cea9b4`
- `RangeArmor-0.6.0-windows-x64.zip` sha256 `3f061d39bb6c7c149fee3747b620eec0b2be77db2ab2bb865702ab3fdcfa8251`

`SHA256SUMS.txt` da release ganhou as duas linhas (mantidas as do Linux); notas e README sem o "Windows em breve".

## 0.5.4

Estado: **Windows publicada em 2026-10-20. Linux pendente** (ver acima).

### Notas para o usuário

Versão grande. Novidades:

- **Smart Components:** campos tipados com `Range.args` (`Float`, `Int`, `Bool`, `Text`, `Choice`, `Color`,
  `Object`, `ObjectList`, `Point`, `Scene`, `Header`), opções `show_if`, `required`, `filter`, `warn_above`
  e desenhos na viewport. Classe `Editor` opcional (avisos, botões, gizmos). **Smart Component Wizard** com
  receitas, botão **Add Field**, `obj.game.components.new()`/`.remove()` e template "04 Smart Component".
- **Logic Bricks espertos:** Brick Inspector no painel N, avisos de brick mal configurado, desenho de
  Near/Radar/Ray/Steering na viewport e presets novos (Mouse Look, Shoot, Spawn Every 2 Seconds, Turret,
  Pause Key).
- **Idiomas do jogo (`Range.locale`):** CSV de traduções, painel Scene ▸ Game Languages, componente Language
  Button e atlas por idioma. Guia em `docs/idiomas.md`.
- **Gravação de tela:** Window ▸ Record Screen (Ctrl+Alt+F3) e botão Rec; MP4 H.264 com som (Windows 10
  2004+); grava também o Standalone.
- **Materiais no modo Game:** Shadows Only, Fresnel na transparência, Z Offset real e Shadow Casting Alpha.
- Outros: copiar configurações do GPU Particle System, `KX_GameObject.getCurvePoints()`, Show Floating Menus.

Correções: crash em placas antigas na preparação de shaders (pula na próxima abertura); janela de crash com
caminho real dos logs; Export Web no Linux (`WEB-PKG-001`); Export 1 Click no Linux (pacote leva
`python3.11`); crash do Logic Editor ao iniciar o jogo; timer de 1 ms no Windows; imagens de nós Material
carregam com a cena; painel Components; `__pycache__` fora do menu de templates; traduções pt_BR/es/ru.

Downloads: `AnastacioEngine-0.5.4-windows-x64.zip` e `RangeArmor-0.5.4-windows-x64.zip`. Linux "em breve
nesta mesma página".

### Montagem

- Textos novos traduzidos em `translations_more.py`. Receitas do Wizard ficaram em português (são código gerado).
- `ctest` 15/15 (`range_language` entrou na lista de módulos só do jogo em `bl_load_py_modules.py`).
- Runtime Web recompilado (manifesto regenerado, 242 módulos); `web/` com `stage_release_web.py`.
- Lista de arquivos igual à da 0.5.3. Zip extraído: editor `-b` abre, runtime roda `base6 anastacio.range`
  (relato do Discord), sem erro SideBySide.
- RangeArmor: painel recompilado (testes 26/26) pelo padrão `./engine/Linux64/AnastacioRuntime`.
- Na mesma noite o zip da engine foi refeito e trocado com `--clobber`: textos em português no código
  (`63a1157e`) e addon Ragdoll ativo por padrão (`66268bb6`).

```text
78cf434ddbea8fad2d0a91b183f1c237d373927bc543186b2b98ef2ec89166d0  AnastacioEngine-0.5.4-windows-x64.zip
5515dfa1e4099057a6c9d2cee3a737f44da518583232bef9e73b49ec7efb2235  RangeArmor-0.5.4-windows-x64.zip
```

## 0.5.3

Estado: **completa em 2026-10-18** (Windows, Linux e RangeArmor Linux).

### Notas para o usuário

Correções sobre a 0.5.2, com foco no export Web/Android, e a primeira RangeArmor para Linux.

- Sons de efeito: o módulo Effects criado pela chuva já vem com os sons da engine (`79556dad`).
- Export Web/Android (WebGL2): partículas de fumaça, fogo e light flicker; chuva com aura, raios e superfície
  molhada; shaders convertidos para WebGL2; cópia da tela sem tela preta (`4d81b518`).
- Downloads: engine Windows e Linux, `RangeArmor-0.5.3-windows-x64.zip` e o novo
  `RangeArmor-0.5.3-linux-x86_64.tar.xz` (usa o `python3` do sistema; Set Icons precisa do `wine`).

### Montagem

- Windows: `ctest` 15/15; runtime Web recompilado depois de `4d81b518`; lista de arquivos igual à 0.5.2.
  RangeArmor sem mudança, zip refeito com raiz `RangeArmor-0.5.3-windows-x64/`.
- Linux: container com `-e VERSION=0.5.3 -e WEB_RUNTIME_DIR=...` (ver dicas acima); `ctest` 10/10;
  `tools/test_*.py` OK com o pacote extraído. `test_weather_sounds_auto.py` atualizado para os 14 sons.
- RangeArmor Linux (primeira vez): `tools/linux/stage_rangearmor_linux.sh`. Painel em `rust:1.95-bullseye`;
  `release/launcher/` inteiro do zip Windows (`Launcher` `3cb1ade9…`, `Launcher.exe` `40aecdf5…`); sem
  ResourceHacker nem `godot_backup`. Testes do painel que chamam `python` falham no container (só tem
  `python3`); não é bug.
- Teste com janela no Linux: painel abre; jogo exportado (Linux64, tutorial Logic Bricks 2.0) roda pelo
  launcher fora do projeto. O `Example Game.rasec` do modelo não abre no runtime atual.
- Site de docs (`AnastacioDocs`, `d54716b`): RangeArmor no Linux nas páginas de export.

```text
e90d6f46ba3ae7b18df111d3ddebca1a6ba9d6527d20a2015e9fa67b620a5a58  AnastacioEngine-0.5.3-windows-x64.zip
58049cf7ac1ceb4396cc4801d97c95445d9f807d9960b225c3696e0bac8f6c9f  RangeArmor-0.5.3-windows-x64.zip
5d271afc846cc52073a2d8b830ba68603e31be40369d33eb5698a6a15e442f43  AnastacioEngine-0.5.3-linux-x86_64.tar.xz
cef2d3c228aa7e7167ea27cf2718f4d2bced3662638021996808834f6e85b504  RangeArmor-0.5.3-linux-x86_64.tar.xz
```

## 0.5.2

Estado: **completa em 2026-10-18** (publicada 20:13 UTC, tag em `5e1509ca`).

### Notas para o usuário

- **Logic Bricks 2.0:** grupos recolhíveis, actuator Wait, modo Finished e botão Then, actuator Video,
  presets, histórico, pausa ao disparar, janela no Debug Mode e Highlight Active; cena
  `docs/logic-bricks-2-tutorial.blend`; `logic_to_python` converte Wait, Video e Finished.
- **Video Player:** componente nativo, fade em tela cheia, legendas `.srt`, export copia os vídeos.
- **Texto:** atlas bitmap para o Text do jogo, preview na viewport, Text Editor com barras flutuantes.
- **Render:** SSGI mais fácil (Check Scene) e mais suave (Denoise); CSM com 2/3 cascatas e Auto Bias;
  Directional Blur por reprojeção; Baked Lighting moderno.
- **Som:** sons de efeito na engine (explosão, destruição, chuva, trovão), Effects preenchido sozinho,
  trovão pela distância, liga/desliga por efeito, pitch variado.
- **Web/Android:** botão Controles ligados/desligados para usar os menus do jogo.
- **Interface:** abas Object/Game/Transform, Physics/Damage, Sky/Atmosphere/Properties; Game Layers
  fixadas; Ragdoll com preview e presets; traduções pt_BR/es/ru.
- Correções: vídeo (keyframes distantes, loop, B-frames), ícone inválido não some com o painel, sons no
  pacote instalado, Play Standalone no Linux, `.cooked` entre Windows e Linux, PNG no runtime Web.

### Montagem

- Windows: `ctest` 15/15 (`anastacio_video` entrou na BLACKLIST de `script_load_modules`); `tools/test_*.py`
  em background OK; `check_docs.py` e `check_ui_icons.py` sem erro.
- **Bug do Linux:** `datafiles/sounds/` não tinha regra de `install` no `creator/CMakeLists.txt`.
  Corrigido; `container-build-22.04.sh` passou a conferir `sounds/effects/trovao1.wav` no tar.
- **Bloqueio corrigido:** `.cooked` de outro compilador quebrava a colisão (BVH gravado com
  `serializeInPlace` depende do layout do compilador). `CcdPhysicsController.cpp` agora grava compilador +
  `sizeof(btOptimizedBvh)` e refaz o BVH recusado. `*.cooked` saiu do git. Um `.cooked` velho mostra
  `bvh 1 loaded, … 1 new` no 1º Play.
- **Play Standalone no Linux:** `anastacio_cook._runtime_path()` procura `AnastacioRuntime` e cai para
  `RangeRuntime`.
- RangeArmor: scripts atuais, `Launcher.exe` recompilado, `Launcher` Linux novo (`3cb1ade9…`) e
  `legacy-template-sha256.json` com `Linux64` do launcher legado.
- Checklist visual no Linux aprovado pelo usuário com o pacote `1a4f7f00…`.

```text
1a4f7f00ab82466658aac096528200748d9e5833312ccc4b048ed29b5fa3c0e7  AnastacioEngine-0.5.2-linux-x86_64.tar.xz
5a6d7756ae99bfec4582cae6bb6b91f08224afce53c36f83a199f25f8d24b3c0  AnastacioEngine-0.5.2-windows-x64.zip
4e04cf1518ad321a7678221d5a3fb310e6fe5a6b26011d23707ba98750a97a8d  RangeArmor-0.5.2-windows-x64.zip
```

O pedido de RangeArmor para Linux (musikai, Discord, 2026-10-18) foi atendido na [0.5.3](#053).

## 0.5.0

Estado: Windows e Web gerados e testados em 2026-10-12 (`ed2fe7fc`, `a8f045cc`, `ce19b151`, `c08a54e7`).
Release completa (Win+Linux+RangeArmor) em 2026-10-13.

### Montagem do Linux

- Container Ubuntu 22.04 com `tools/linux/container-build-22.04.sh` (ver
  [distribution-0.1.md](distribution-0.1.md#linux-x86_64)). O script falha se faltar `libae_uvatlas.so`,
  `icons_upbge/`, `icons_blender5/`, `anastacio_network/`, ou se entrar `Range_Components_Label.rar`.
- Checklist do pacote extraído: `startup.blend` novo, About com a versão, runtime roda um `.range`, cenas
  de `tools/debug/cenas/` (`criar_cena_ssgi.py`, `criar_cena_vfog.py`, `criar_cena_vitral.py`,
  `criar_cena_world_sound.py`) sem crash nem erro de shader, som, bake e UV atlas.

```text
34bd79db594cf5167f323739a1d43d611edfadd210fd88c911f2cf956b360c4e  AnastacioEngine-0.5.0-windows-x64.zip
e7b5045901d571d6b34f2ef6c443dc462c97af86644bde337630a50438311068  RangeArmor-0.5.0-windows-x64.zip
```
