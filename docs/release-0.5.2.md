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

- [ ] About mostra 0.5.2.
- [ ] `ctest` no build Linux passa (inclui `script_load_modules` e `bmesh_bevel`).
- [ ] `2.79/datafiles/sounds/effects/` está no tar; chuva e trovão tocam sozinhos numa cena com Weather Rain.
- [ ] Video Player: vídeo toca em loop, fade e legenda `.srt` aparecem; o actuator Video controla.
- [ ] Logic Bricks 2.0: abrir `docs/logic-bricks-2-tutorial.blend`, rodar, ver Highlight Active e a janela
      no Debug Mode (F4).
- [ ] Text do jogo com atlas bitmap; "Edit Externally" abre o editor do sistema (no Linux usa o fallback).
- [ ] SSGI, CSM com 2/3 cascatas e Directional Blur sem erro de shader no terminal.
- [ ] Baked Lighting (AO e estática) e Material Atlas no editor do pacote.
- [ ] Ragdoll e Game Layers fixadas funcionam.
- [ ] Rodar os `tools/test_*.py` em background com o editor do pacote (mesmos comandos do Windows).

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
