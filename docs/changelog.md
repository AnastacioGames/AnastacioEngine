# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, como sempre). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-09-24 a 2026-09-23 | 19 | 34 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |

## 2026-09-24 - Tradução dos textos fixos dos layouts Python (scan estático)

- Novo `tools/tests/web_profile/i18n_scan_labels.py` (roda no motor): lê com `ast` os `.py` de
  `release/scripts/startup` e lista os textos literais passados a `label`, `operator`, `prop`, `menu` etc.
  (`text=` ou `label("...")`, respeitando `text_ctxt` e `translate=False`) que `pgettext_iface` não traduz. Cobre o que
  o `i18n_audit.py` (só RNA) não via. 2 378 textos distintos; antes, 895 sem tradução em pt_BR e 898 em es (ru não medido antes).
- Novo `range_web/translations_labels.py` (pt_BR/es/ru, 997 textos), registrado depois dos outros dicionários
  (`setdefault`: tradução já existente vence). Cobre sobretudo os painéis do game engine (Game, Física, Mundo,
  Input System, cutscene, componentes, menus da Range) e menus do Blender que o catálogo 2.79 não traduz. Textos
  que o catálogo traduz num idioma e não em outro ficam nas três línguas, para as tabelas manterem as mesmas chaves.
- Depois: pt_BR 72, es 74 e ru 30 sem tradução no scan, todos nomes próprios (Range Engine - Discord), códigos
  (X/Y/Z, FXAA, ORM, AWD/FWD/RWD) ou palavras iguais nas duas línguas (Sensor, Material). A auditoria RNA também
  cai um pouco (pt_BR 1 286 → 1 279, ru 1 958 → 1 940).
- `engine_i18n.py` confere um rótulo fixo em pt/es/ru; `engine_web_ui.py` e os 124 testes puros seguem OK.
  es/ru pedem revisão nativa. Não conferido na janela real do editor. Textos em C fora do RNA seguem sem scan.

## 2026-09-24 - Controle na tela: checklist do celular no navegador e no Find X3 Pro (A1, etapa T4)

- `tools/web/verify-touch.cjs` passou de 19 para 25 conferências, cobrindo no Edge headless os critérios do plano
  que antes só estavam na lista do celular: dois botões juntos (A+B, engine vê `buttons=[0, 1]`), dedo do stick
  arrastado até em cima do botão A (continua no stick e não aperta A), soltar fora do controle, `touchcancel` com
  stick e botão apertados, e página escondida (`visibilitychange`, troca de app) com o stick apertado. Tudo solta
  sem entrada presa.
- Mudança do plano: a cena de teste da T4 é a do pad (`make_pad_project.py`), que já registra eixos, botões,
  teclas e a ação do Input System, e sai no logcat `RangeWeb` no APK; o multitoque fica no `verify-touch.cjs`,
  sem modo novo no `verify-capabilities.cjs`.
- Roteiro do aparelho escrito no plano (T4). Itens 1 a 4 aprovados no Find X3 Pro pelo usuário: APK
  `com.anastaciogames.pad` da cena `pad`, layouts stick e `wasd`, logcat sem entrada presa (detalhes em
  `android-manual-tests.md`). Falta o First Person com `wasd` no aparelho.

## 2026-09-24 - Controle na tela: layout no painel Web e aviso de entrada sem toque (A1, etapa T3)

- Properties > Scene > Web (Range) ganhou **Controle na tela** (nenhum, stick + 2 botões, d-pad + 4 botões, dois
  sticks, stick como WASD + espaço, d-pad como setas + espaço/Enter) e **Modo do stick** (onde o dedo toca ou no
  canto). O Exportar Web passa `--touch-layout/--touch-stick` ao empacotador, que grava `touch_controls` no
  `manifest.json`. O painel Android mostra o mesmo campo: o APK embute o pacote Web, então a config não foi para o
  `android-export.json` (decisão registrada no plano).
- Nova regra WEB-INPUT-001 (`range_web/touch.py`, aviso, evidência potencial): sensor Keyboard com tecla que o
  layout não aperta, sensor Joystick com botão/stick que o layout não tem, ação do Input System sem nenhum binding
  alcançado (todas as entradas do binding precisam estar no layout; clique esquerdo e movimento do mouse contam,
  porque o toque fora dos controles vira mouse). Com controle desligado, um só aviso informativo. Não vê
  `logic.keyboard` lido em Python.
- Correção: os mapas do Input System (`KeyMapping/*.json`, lidos pelo motor ao lado do `.range`) não entravam no
  pacote Web; o export do editor agora os inclui. `make_pad_project.py` gera `KeyMapping/Pad.json` com a ação
  "Pular" (espaço ou botão A) e `verify-touch.cjs` confere as duas vias no navegador (19/19). Isso também fecha a
  pendência da T0 de conferir um binding `JOYSTICK` com o pad virtual.
- Traduções pt/es/ru do painel e das mensagens. "Stick", "Dynamic" e "Fixed" viraram "Stick mode", "Where the
  finger touches" e "In the corner": o catálogo do Blender traduz os primeiros ("Bastão", "Фикс") e vence o nosso.
- Testes: `test_range_web.py` +5 (teclas dos layouts conferidas contra o template, sensores, mapas, layout
  desligado), 124 puros OK; `engine_collect_bpy.py` (JSON no pacote, aviso com stick e sem aviso com wasd) e
  `engine_web_export.py` (layout do painel no manifest e na página) sem falhas; `engine_i18n`, `engine_web_ui` e
  `engine_android_export` sem falhas. Não testado: celular.

## 2026-09-24 - Controle na tela: alvo tecla para jogos que leem teclado (A1, etapa T2)

- O controle na tela também aperta teclas. Na página, stick e d-pad aceitam `keys` (cima, baixo, esquerda, direita;
  o stick vira tecla depois de meio curso, diagonal aperta duas) e o botão aceita `key`, com os nomes de
  `bge.events` (`WKEY`, `SPACEKEY`, …). O controle com alvo tecla não mexe no gamepad. Novos layouts: `wasd`
  (stick = W/A/S/D, botão = espaço) e `arrows` (d-pad = setas, espaço e Enter).
- `Module.rangePad.keys` leva os códigos de `bge.events` (tabela na página na ordem de `SCA_EnumInputs`, conferida
  contra o `bge.events` no teste). `DEV_InputDevice::PollVirtualKeys` lê por `EM_JS` a cada quadro, chamado em
  `LA_Launcher::EngineNextFrame` logo depois dos eventos do sistema. Teclado físico e toque ficam em estados
  separados e o evento só muda com o estado combinado: soltar o toque não solta W que o teclado segura, e vice-versa.
  No build nativo o poll não faz nada. Chega ao sensor Keyboard, a `logic.keyboard` e aos bindings `KEYBOARD` do
  Input System (mesma tabela de entradas).
- Removido o `printf("[web-input] ...")` de depuração que sobrou em `DEV_EventConsumer::HandleKeyEvent`.
- `TOUCH.layout` aceita também a lista de controles (para a config do projeto na T3).
- `verify-touch.cjs` 16/16 no Edge headless: as 10 de gamepad e, no `wasd`, códigos W=45/SPACE=8/UPARROW=72 iguais
  aos do `bge.events`, stick para cima + botão dão `keys [45,8]` sem eixo nem botão de gamepad, o jogo vê W e espaço
  apertados e soltos, W segurado no teclado (CDP) continua quando o toque solta e sobe quando o teclado solta. Cada
  layout abre numa aba nova: recarregar na mesma aba deixava o toque do CDP sem chegar à página. D-pad do `arrows`
  conferido à parte (diagonal = ↑ e →). Build Web e nativo sem erro. Aceite do usuário no Edge do PC (`wasd` com
  mouse e teclado físico). Não testado: celular, First Person com `wasd`.

## 2026-09-24 - Controle na tela: overlay com stick, d-pad e botões (A1, etapa T1)

- `package-web.py` desenha o controle na página (HTML/CSS, sem custo na cena) e escreve `Module.rangePad`, que a T0
  já entrega como gamepad 0. Cada controle segue um dedo (`pointerId` + pointer capture): mover e apertar ao mesmo
  tempo funciona, e arrastar para fora do controle não solta nem aciona outro. Toques fora dos controles seguem para
  o canvas (arrastar para olhar continua). Tudo solta em `blur`, `visibilitychange`, `pagehide`, giro da tela e
  `pointercancel`.
- Layouts: `stick` (stick esquerdo + A/B, padrão), `dpad` (d-pad de 8 direções nos botões DPAD do SDL + A/B/X/Y),
  `twin` (dois sticks, eixos 0-1 e 2-3). Stick dinâmico (nasce onde o dedo toca, na zona inferior da metade da
  tela) ou fixo; zona morta radial de 10 %. Tamanho por `vmin` e margens por `env(safe-area-inset-*)`
  (`viewport-fit=cover`).
- Aparece só em `pointer: coarse` (celular, WebView do APK) ou com `?touch=1`; `?touch=0`, `?touchlayout=` e
  `?touchstick=` para testar. Padrão do pacote por `--touch-layout` (`none` desliga) e `--touch-stick`; o editor ainda
  usa o padrão (seletor na T3). Com `?debug=1` o log mostra `[touch] axes ... | buttons ...`.
- `tools/web/verify-touch.cjs`: 10/10 no Edge headless com toque emulado pelo CDP — stick até a borda dá LX 1,
  botão A junto, engine vê os dois (`axes=[1.0, 0.0, …] buttons=[0]`) e o sensor A dispara; soltar só o A mantém o
  stick; soltar tudo zera; diagonal solta ao perder o foco; toque fora dos controles não mexe no pad. D-pad
  conferido à parte (diagonal cima-direita aperta UP+RIGHT, baixo só DOWN, soltar zera).
- Com o controle USB ligado no PC, `verify-pad.cjs` falha nas 3 checagens que esperam "sem gamepad" (o índice 0 é o
  físico); anotado no cabeçalho dele. Conferido pelo usuário no Edge do PC com `?touch=1`, usando o mouse como
  dedo: funciona. Não testado: celular (toque real, entalhe, WebView do APK).

## 2026-09-24 - Controle na tela: ponte do gamepad virtual (A1, etapa T0)

- Levantamento e caminho do A1 completo em [android-touch-controls-plan.md](android-touch-controls-plan.md): overlay
  HTML (Pointer Events) alimentando o input existente, com alvo gamepad ou tecla; estende o Range Input System em
  vez de criar sistema paralelo. O joystick virtual do SDL não está habilitado na porta Emscripten
  (`SDL_config_emscripten.h` sem `SDL_JOYSTICK_VIRTUAL`), por isso a ponte é da engine.
- `DEV_Joystick` lê `Module.rangePad` (`active`, `axes[6]` em -1..1 na ordem do SDL GameController, `buttons` em
  máscara de bits) a cada quadro, por `EM_JS` no molde do `logic.motion`. Com o pad ativo, o índice 0 existe mesmo
  sem controle físico (nome "Range Virtual Pad"); com controle físico no 0, os dois se somam (eixo: o mais empurrado
  vence; botão: qualquer um). Controle físico que chega com o pad sozinho abre na mesma instância. Pad desligado
  remove o índice 0 virtual. `SyncLiveState` usa o estado somado, então o sensor Joystick também dispara.
- Corrigido de passagem: `GetName()` com controle ausente construía `std::string` de ponteiro nulo;
  leitores de eixo/botão não chamam mais o SDL com controle nulo.
- `package-web.py` expõe `Module.rangePad` (inativo; o overlay vem na T1).
- Cena `tools/tests/web_profile/make_pad_project.py` e `tools/web/verify-pad.cjs` (escreve `Module.rangePad` pelo
  CDP): 7/7 no Edge headless com `build-web-release` — sem pad `joysticks[0]` vazio; pad ativo vira
  `joysticks[0]` com eixos (1, -0.5, …, 0.25) no Python; botão A em `activeButtons` e sensor Joystick down/up;
  pad desligado remove o gamepad.
- Controle USB real ("Standard Gamepad") no Edge do PC, com o usuário: sozinho, eixos/botões/sensor A funcionam;
  com o pad ligado (LX 0.5 + B), o eixo fica 0.5 com o físico solto e vira -1.0 quando empurrado ao fim, e os botões
  se somam (`[0, 1]`, `[1, 9]`); ao desligar o pad o eixo volta a 0 e o B solta na hora, e o físico segue
  funcionando sozinho (stick ±1, botões, sensor A). Aba minimizada pausa o jogo (sem leitura). Não testado:
  Input System (mesmo `DEV_Joystick`, sem teste próprio), celular.

## 2026-09-24 - Export Android: release assinado

- Build type Release liberado. Chave PKCS12 (RSA 4096, ~27 anos) criada pelo keytool do JDK: botão "Criar chave"
  no painel (padrão `~/RangeAndroidKeys/<applicationId>.jks`) ou `package-android.py --create-keystore`. Recusa
  caminho dentro de repositório git e nunca sobrescreve uma chave existente.
- `android-export.json` ganha `keystore` e `keyAlias`; a senha nunca é gravada. Vem de
  `RANGE_ANDROID_KEYSTORE_PASSWORD` (terminal, ou pedida por `getpass`) ou do campo "Senha da chave"
  (`WindowManager.range_android_password`, `SKIP_SAVE`, fora do `.blend`). O template lê chave, alias e senha
  do ambiente (`signingConfigs` só existe com `RANGE_ANDROID_KEYSTORE`), então nada fica no projeto temporário.
- Antes do Gradle, `keytool -list` confere senha e alias (erros claros em vez da exceção do Gradle). Depois,
  `apksigner verify --print-certs`; o relatório ganha `signing` com o SHA-256 do certificado.
- Catálogos es/ru do Android completados: `engine_i18n.py` falhava em "es/ru cobrem as mesmas chaves do pt_BR"
  desde o commit do A3/A4.
- Verificado: `test_android.py` (20 testes, com criação real de chave, senha errada, alias inexistente e recusa
  dentro do git), `engine_android_export.py` e `engine_i18n.py` sem falhas; release do First Person pelo terminal
  com chave temporária (APK assinado, senha ausente de `gradle.log`, JSON e relatório); debug continua igual.
  No aparelho (app de teste separado): release v1 instalado e v2 atualizado por cima com a mesma chave,
  `firstInstallTime` mantido; com a cena `web-save`, v3 `SAVED` e v4 por cima `LOADED` (save preservado).

## 2026-09-24 - Export Android pelo editor e pelo terminal (A3/A4, APK debug)

- Novo `range_web/android.py` (sem bpy): confere o pacote do export Web por `SHA256SUMS.txt`, copia
  `tools/android/webview-template` para `%TEMP%/range-android-build/` (sem `build/`, `.gradle/` nem o `www/` de teste),
  põe o jogo em `assets/www` (sem `serve.py`/`HOSTING.md`), aplica `applicationId`, nome, `versionName`/`versionCode`,
  ícone PNG (`mipmap-xxxhdpi`) e orientação (`fullUser`/`sensorLandscape`/`sensorPortrait`) e roda `assembleDebug`.
  Saída: APK, `android-export.json` usado, `android-report.json` (hashes, template, JDK/SDK) e `gradle.log`.
  O namespace Kotlin continua `com.anastaciogames.rangewebview`; só o `applicationId` muda.
- JDK/SDK: `JAVA_HOME`/`ANDROID_HOME`, depois Android Studio (registro do Windows e `%LOCALAPPDATA%\Android\Sdk`),
  depois as pastas do painel. Sem JDK, SDK, platform 37 ou build-tools: erro com o que instalar; nada é instalado.
- `adb`: instala por cima com `install -r` e abre o jogo; erros claros para aparelho ausente, não autorizado,
  assinatura diferente (não desinstala, para não apagar o save) e versão mais nova no aparelho.
- Painel "Android (Range)" (`bl_ui/properties_android.py`, `Scene.range_android`), abaixo do painel Web: campos,
  "Gerar APK" (exporta o Web antes se o pacote estiver ausente ou mais velho que o `.range`) e "Instalar no celular".
  Gradle e adb rodam numa thread com operador modal; em modo background, direto. Traduções em
  `range_web/translations_android.py`.
- `tools/web/package-android.py`: mesma lógica pelo terminal (`--web`, `--config` ou `--app-id/--name`, `--install`).
- Release assinado ainda bloqueado com mensagem ("use debug").
- Verificado: `test_android.py` (15 testes), `engine_android_export.py` no editor em background (APK gerado de uma cena
  vazia, sem celular "Instalar" cancela com mensagem) e APK do First Person pelo terminal (`aapt`: id
  `com.anastaciogames.firstperson`, nome e versão certos). Primeiro `assembleDebug` em ~8 s com o cache do Gradle.
- Aceite: APK do First Person gerado pelo painel e instalado no Find X3 Pro com "Instalar no celular"; aprovado
  pelo usuário. Correções do aceite: "Gerar APK" salva o arquivo modificado antes de exportar (antes recusava e o
  aviso sumia no topo) e o painel mostra o último erro/resultado abaixo dos botões. `engine_android_export.py` só
  chama "Instalar" com `RANGE_ANDROID_TEST_INSTALL=1` (tinha instalado o app de teste no celular ligado).

## 2026-09-24 - APK e Web: rotação em paisagem e retrato

- APK: `screenOrientation` passa de `sensorLandscape` para `fullUser` (as quatro direções, respeitando o bloqueio
  de rotação do sistema). No APK o `index.html` sempre ajusta o canvas à tela.
- `package-web.py`: `fitCanvas` usa uma proporção fixa do jogo, adotada quando o runtime cria a janela com a
  resolução do `.range` (MutationObserver em `width/height`). Antes media por `canvas.width/height`, que o SDL
  troca pelo tamanho CSS a cada resize: a imagem abria achatada em pé (960x540 x 640x480) e se deformava a cada giro.
  Vale também para a tela cheia no navegador.
- `GHOST_SystemSDL.cpp` (Web): no resize da janela o cursor virtual do mouse-look é reescalado para a nova
  janela. Ficava no centro antigo e a câmera do First Person virava um pouco a cada giro.
- Aprovado pelo usuário no Find X3 Pro com o First Person ("ficou muito bom").

## 2026-09-24 - APK: botão "Tela cheia" escondido dentro do app

- `MainActivity` acrescenta `RangeWebView/1` ao user agent do WebView. O `index.html` de `package-web.py` procura
  essa marca e não mostra o botão "Tela cheia" dentro do APK, que já abre imersivo. No navegador nada muda.
- Verificado no Edge headless com o user agent sobrescrito pelo CDP (botão visível sem a marca, oculto com ela).
  APK debug recompilado com o pacote `motion` e o runtime release (`build-web-release/bin`), instalado no
  Find X3 Pro: botão ausente e Home/retorno com a cena seguindo sem recarregar.
- Orientação: o giro de 180° em paisagem funciona com o `sensorLandscape` atual. Em pé a imagem não vira retrato,
  e o jogo continua só em paisagem por decisão do usuário. Um `OrientationEventListener` próprio foi testado e
  descartado: não era necessário.
- First Person no APK: o WebView do Android não tem pointer lock e rejeita o pedido do runtime (cursor oculto)
  com `UnknownError: If you see this error we have a bug...`, que a página mostrava como erro fatal. O
  `index.html` de `package-web.py` troca `Element.prototype.requestPointerLock` por um no-op só dentro do APK
  (marca `RangeWebView/`); no navegador nada muda. Jogo roda, áudio `running`, usuário confirmou.
- `AndroidManifest.xml`: `launchMode="singleTask"`. Tocar no ícone com o jogo aberto por `adb shell am start`
  criava uma segunda Activity por cima, com dois jogos rodando.
- Medida por CDP, jogo parado, 1200 frames: APK 50,3 e 59,9 fps médios em duas rodadas (p50 16,7 ms); Chrome do
  aparelho com o mesmo pacote 37,5 fps (p50 33,3 ms, uma rodada). Números preliminares
  ([android-manual-tests.md](android-manual-tests.md)).
- Música ausente no APK não era do WebView: o `First_Person.range` local é uma versão antiga sem o script da
  música. Com o `.range` publicado em `gh-pages` a saída de áudio mede pico 0,65 (antes 0); usuário ouviu.
- Save no APK: `web-save.range` grava (`SAVED`), o app é encerrado por `am force-stop` e a sessão seguinte lê
  (`LOADED`). O IndexedDB do WebView persiste entre execuções.
- Cuidado ao reempacotar para o APK: `build-web/bin` pode estar com runtime de depuração (SAFE_HEAP); usar
  `--runtime-dir build-web-release/bin`.

## 2026-09-23 - APK WebView mínimo (A0b) rodando no aparelho

- Novo template `tools/android/webview-template/` (Kotlin, uma Activity, AGP 9.4.1 com Kotlin embutido, Gradle
  9.7.1 pelo wrapper com `distributionSha256Sum`, compileSdk 37/targetSdk 36/minSdk 24, `androidx.webkit` 1.17.1,
  `androidx.core` 1.19.1). `WebViewAssetLoader` serve `assets/www/` em `https://appassets.androidplatform.net`;
  arquivo ausente responde 404 explícito e o app não pede `INTERNET`. Links externos abrem no navegador.
- Paisagem (`sensorLandscape`), imersivo, tela acesa, `configChanges` para girar sem recarregar o jogo. Console JS
  vai para o logcat (`RangeWeb`); depuração remota e o extra `query` (ex.: `debug=1`) só no build debug.
- Testado no OPPO Find X3 Pro (Android 13, WebView 150) com a cena `motion`: carga offline, WebGL 2, Python e
  `bge.logic.motion` com sensores reais; inclinação e `calibrate()` aprovados pelo usuário. Pendências em
  `docs/android-manual-tests.md` (novo).

## 2026-09-23 - Sensores de movimento: `bge.logic.motion` (giroscópio, acelerômetro, inclinação)

- Por decisão do usuário, os sensores vieram antes do APK Android: testáveis já no celular pelo navegador, e o APK
  (WebView) herda sem mudança. Não há biblioteca externa: `DeviceMotionEvent`/`DeviceOrientationEvent` são padrão.
- Nova classe `KX_PythonMotion` (`Ketsji/KX_PythonMotion.{h,cpp}`, no padrão de `KX_PythonMouse`), registrada como
  `bge.logic.motion`: `available`, `gyroscope` (rad/s), `accelerometer` e `gravity` (m/s², apontando para cima como
  no W3C), `orientation` (alpha/beta/gamma do navegador), `tilt` (x, y de -1 a 1: para onde uma bola rolaria na
  tela) e `calibrate()`. No Web lê `Module.rangeMotion` por `EM_JS`; nas outras plataformas `available = False` e
  zeros. Documentada em `bge.types.KX_PythonMotion.rst`.
- Página do `package-web.py`: ouve os dois eventos, gira os eixos para os da tela (`screen.orientation.angle`),
  calcula a gravidade (ou passa-baixa, sem aceleração linear), pede permissão no clique em Jogar (só iOS exige) e,
  com `?debug=1`, loga os valores uma vez por segundo. `available` cai depois de 1 s sem leitura.
- Achado: Chrome/WebView preenchem `rotationRate` como alpha=x, beta=y, gamma=z, não na ordem do texto do W3C.
  O mapeamento segue o Chrome; iOS usa a ordem da especificação (não testado).
- Cena de teste gerada por `tools/tests/web_profile/make_motion_project.py` (`projects-teste/motion/motion.range`):
  tabuleiro que inclina, bola que rola, verde/vermelho para sensor ligado/desligado, toque calibra.
- Validação: `RangeRuntime` nativo (MSVC) e runtime Web release compilados; sonda nativa com todos os atributos
  (`available=False`, `Vector` zerado, `calibrate()` = `False`); `tools/web/verify-motion.cjs` com sensores emulados
  pelo CDP no Edge headless: `MOTION: PASS` (retrato, paisagem a 90°, giro nos três eixos, calibração pelo toque).
  `orientation` não foi emulada. 99 testes de `tools/tests/web_profile` OK. Falta o teste no celular real.

## 2026-09-23 - Web: mensagens das regras traduzidas (English, Português, Español, Русский)

- As mensagens e dicas de correção das regras Web (`rules_files.py`, `rules_python.py`, `runtime.py`,
  `manifest.py`, `collect.py`, `collect_bpy.py`, `preflight.py`, `export.py`) passam a ser escritas em inglês,
  como o resto do painel. Os detalhes internos de manifesto inválido também, mas sem tradução (só quem monta runtime vê).
- `i18n.Msg` guarda o texto em inglês (JSON e testes) junto do molde e dos argumentos; `i18n.tr` traduz na exibição
  (o catálogo casa o molde, não o texto já formatado). Argumentos que também são `Msg` são traduzidos; nomes de
  arquivo, não. O painel e o aviso de export bloqueado usam `tr`.
- Catálogo novo `translations_rules.py` (112 moldes, pt_BR/es/ru) somado aos catálogos do perfil Web. O russo
  e o espanhol precisam de revisão nativa, como os de `translations_ui.py`.
- Validação: 99 testes unitários de `tools/tests/web_profile`; no editor, `engine_i18n.py` (com checagens novas de
  `tr`), `engine_web_ui.py`, `engine_collect_bpy.py`, `engine_web_export.py` e `engine_web_cli.py`, todos aprovados.

## 2026-09-23 - Web: mouse com cursor oculto deixa de girar a câmera sem parar

- Usuário relatou mouse "muito sensível" no First Person (GitHub Pages). Causa: no port SDL2/Emscripten o
  `WarpMouse` não funciona, então `reCenter()` não recentralizava e `deltaPosition` repetia o deslocamento a cada
  frame (câmera girando como joystick). Não era sensibilidade do jogo.
- `GHOST_SystemSDL.cpp` (só `__EMSCRIPTEN__`): com cursor oculto, cursor virtual acumulado de `xrel/yrel`;
  `setCursorPosition` move o cursor virtual. Clique de mouse real pede pointer lock no `#canvas`.
  `GHOST_WindowSDL.cpp`: mostrar cursor sai do pointer lock; ocultar pede. `package-web.py`: rejeição de pointer
  lock não vira erro na página.
- Validação no Edge headless (sonda `mprobe`): movimento de 80 px gera um único delta, com e sem pointer lock;
  toque/arrasto gera delta proporcional, sem salto no toque novo; cursor visível inalterado. Publicado no
  `gh-pages` (0.1.2). Usuário confirmou no teste real: sensibilidade do mouse e jogo OK.

## 2026-09-23 - Web: botão de tela cheia na página do jogo

- Usuário confirmou que o First Person roda no celular pelo GitHub Pages e pediu tela cheia.
- `index.html` gerado por `package-web.py`: botão "Tela cheia"/"Sair da tela cheia" no canto superior esquerdo,
  visível depois de "Jogar". Coloca a página inteira em tela cheia (overlay `?perf=1`/`?debug=1` continuam
  visíveis), escala o canvas por CSS mantendo a proporção (resolução de desenho inalterada, sem custo extra) e,
  no Android, tenta travar em paisagem. Oculto sem Fullscreen API (iPhone só tem para `<video>`).
- Validação no Edge headless com viewport de celular (800x360, DPR 2): botão oculto antes de jogar, entra e sai
  da tela cheia por clique, frames continuam contando, nenhum erro/exceção. Publicado no `gh-pages` (0.1.1).
  No celular do usuário o botão só girou a imagem para paisagem, sem tela cheia de fato (limite do
  navegador); usuário aceitou assim.

## 2026-09-23 - Web: nome do jogo com espaço ajustado no export; build de teste no GitHub Pages

- `tools/web/package-web.py`: nome do `.range` com espaço/acento/caractere inválido deixa de ser recusado ("nome do
  arquivo do jogo invalido para o FS virtual", achado em `melhores graficos .range`). `safe_name()` tira acentos e
  troca o resto por `_` (`Meu Jogo Ação.range` → `Meu_Jogo_Acao.range`; só não ASCII → `game.range`); o nome
  padrão do pacote segue a mesma regra. Vale também para o export do editor, que chama o empacotador. Extras
  (`--extra`) continuam recusados com nome inválido, porque scripts os importam pelo nome.
- Validação: pacotes gerados com `Meu Jogo Ação.range` e `日本 jogo.range`, `index.html`/`manifest.json` apontam
  para o nome ajustado e `perf-run.cjs` recebeu frames no Edge headless.
- Build de teste para celular: First Person (`tools/ADD na engine anastacioEngine/First_Person.range`, renomeado
  pelo usuário) empacotado com `--perf` e publicado na branch órfã `gh-pages` (GitHub Pages:
  <https://anastaciogames.github.io/AnastacioEngine/?perf=1>). Link público testado no Edge headless: carrega,
  WebGL2/Core, sem erro. Medição p50/p95 em celular físico pendente com o usuário.

## 2026-09-23 - Web: `aud` METH_NOARGS validado no navegador

- A correção de aridade de `ea2cfd04` (18 métodos `METH_NOARGS` de `PySound`/`PyDevice`/`PyHandle`/
  `PyDynamicMusic`/`PyPlaybackManager`) foi conferida com o runtime `build-web-release` de 2026-09-23:
  `claude_aud_noargs_probe.py` empacotada e rodada por `claude_r3_run.cjs` no Edge headless. `cache()`,
  `reverse()`, `handle.pause()` e `handle.stop()` com som válido terminam sem `function signature mismatch`
  (`[r3] TODOS`).
- **Regressões repetidas depois da mudança de áudio** (runtime `build-web-release` de 2026-09-23, Edge headless
  isolado): áudio `web-audio` (`verify-capabilities.cjs audio`) 8/8 OK (AudioContext rodando, pico 0,35); módulo
  `aud` (`create_web_aud_module_scene.py`) até `[aud] aud OK`; bloom + resize (`claude_m3_resize.*`) com offscreens
  canvas/2, /4, /8 em 640x360, 1024x600, 400x300 e 960x540 e `glError=0x0` em todas as fases; resolução dinâmica
  sem timer com aviso único; R1 `CONSTRAINT_ABI_TEST: PASS` no Web e guard estático `PASS (31 methods)`.
- Aceite visual do Principled/PBR Web (luzes de cena e sombra) dado pelo usuário no navegador com GPU real.

## 2026-09-23 - Web: luzes de cena e sombra do Principled/PBR no perfil CORE (WebGL2)

- **Problema**: o `web-runtime` compila com `WITH_GL_PROFILE_CORE_RANGERUNTIME` (`USE_CORE_PROFILE` nos shaders).
  O loop de luzes de `node_bsdf_principled()`/`node_bsdf_diffuse()`/`node_bsdf_glossy()` e a sombra do Principled
  estavam em `#ifndef USE_CORE_PROFILE` (`gl_LightSource` não existe em GLES3, e `RAS_OpenGLLight` não chama
  `glLight*` em CORE): no navegador esses materiais só recebiam ambiente/IBL, sem Sun/Point/Spot nem sombra.
- **Correção**:
  - `RAS_OpenGLLight::ApplyFixedFunctionLighting()` preenche também um `GPUSceneLight` (`GPU_material.h`) com os
    mesmos valores do `glLight*`, em espaço de visão (posição/direção multiplicadas pela view, `halfVector`
    derivado para o Sun, `spotCosCutoff`). `RAS_Rasterizer` guarda os 8 slots (`GetSceneLights()`), porque
    uniform é estado do programa e `ProcessLighting()` não recalcula quando a camada de luz se repete.
  - `GPU_material_bind_scene_lights()` envia `unflightsource[i].*` por objeto, junto do bind de sombra em
    `BL_BlenderShader::BindShadowLamps()`; no COMPAT as localizações são -1 e nada é enviado.
  - GLSL: em CORE, `uniform SceneLightSource unflightsource[8]` com os campos de `gl_LightSource`; os três BSDFs
    leem `SCENE_LIGHT(i)` (em COMPAT continua `gl_LightSource[i]`). A amostragem de sombra passou para
    `scene_light_shadow()`, com índices constantes em `unfshadowmap[]` (GLSL ES 3.00 proíbe indexar array de
    samplers com a variável do loop).
  - `gpu_extensions.c`: no Emscripten `GPU_max_textures()` fica limitado a 28, o máximo de units que o
    `LEGACY_GL_EMULATION` rastreia. Com WebGL informando 32 (SwiftShader), o bind da sombra em
    `max - 3 + i` fazia `glEnable` estourar em `hook_enable` (`enabled_tex2D` de undefined) ao carregar a cena.
- **Validação**: `build` nativo (`RangeRuntime`/`RangeEngine`) e `build-web-release` compilaram com código 0.
  `shadow_ibl_test.range` empacotado e rodado no Edge headless (SwiftShader): sem exceção, sem erro de shader no
  pré-voo, `glError=0`; a captura mostra os brilhos das várias luzes, o cone do Spot e as sombras no chão.
  **Pendente**: aceite visual do usuário no navegador com GPU real e conferência do desktop (o GLSL do caminho
  COMPAT mudou: macro `SCENE_LIGHT` e helper de sombra).

## 2026-09-23 - Sombra em Principled/PBR: correções que faltavam para funcionar no jogo real

A entrada de 2026-09-21 compilava mas não sombreava nada no jogo (validado no `shadow_ibl_test.range`). Causas
encontradas (todas confirmadas por diagnóstico em runtime, não só leitura de código):

- **Bind fora de hora**: `GPU_material_bind_shadow_lamps()` rodava em `KX_BlenderMaterial::Prepare()`, antes de
  `BindProg()`, então o `glUniform*` ia para o programa errado. Agora é `BL_BlenderShader::BindShadowLamps()`,
  chamado por objeto em `KX_BlenderMaterial::ActivateMeshUser()` depois de `Update()`.
- **`ProcessLighting()` nunca era chamado para materiais com nodes** (só o caminho `m_shader` chamava), então
  `m_shadowLamps` ficava vazio. Agora `ActivateMeshUser()` chama `ProcessLighting(true, ...)` também para
  `m_blenderShader`. Efeito colateral a observar: todo material com nodes passa a receber o estado de luz
  fixed-function por objeto.
- **Vazamento**: `GPU_material_bind_shadow_lamps()` chamava `add_user_list()` (sem dedupe) por objeto e por frame;
  agora registra lamp/material uma vez.
- **Point/Spot tratados como direcionais** em `node_bsdf_principled()`: agora `position.w == 1` usa
  direção `luz - fragmento`, atenuação `constant/linear/quadratic` e cone do Spot (`spotCutoff`,
  `spotExponent`). Diffuse/Glossy BSDF (`node_bsdf_diffuse`/`node_bsdf_glossy`) **não** foram tocados.
- **`GL_SPOT_CUTOFF` em radianos**: `RAS_OpenGLLight::ApplyFixedFunctionLighting()` passava `m_spotsize / 2`
  (radianos) onde o GL espera graus [0, 90]; agora converte. Sem isso o cone valia ~0,4° e o Spot não iluminava.
- **Loop limitado a 3 luzes**: numa cena com 4 luzes o Sun (slot 3) nunca entrava. `NUM_LIGHTS` passou a 8
  (slots desligados são pulados) e `NUM_SHADOW_LIGHTS = 3` mantém o limite de shadow maps.
- **Luz desligada mantinha a cor antiga**: `RAS_OpenGLRasterizer::DisableLight()` agora zera `diffuse`/`specular`
  do slot, já que o shader não olha `GL_LIGHTi`.
- **Sampler de sombra sem textura**: slots sem sombra apontam `unfshadowmap[i]` para a própria unit em vez da
  unit 0 (evita `sampler2DShadow` e `sampler2D` na mesma unit).
- **Validação**: `RangeRuntime` com `projects-teste/pbr-baseline/shadow_ibl_test.range`, sombras do Spot no
  chão visíveis (usuário: "parece bom, sombra um pouco fraca, deve ser regulagem" — o chão satura com 4 luzes
  somando energia 5,6). Ainda sem comparação lado a lado com material legado.
- **Ainda sem sombra no Principled**: Point/Local, CSM e VSM (limite de engine, inalterado).
