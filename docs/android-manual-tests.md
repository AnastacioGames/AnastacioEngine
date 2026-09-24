# Testes manuais Android

Registro dos testes em aparelho físico da rota APK WebView ([android-export-plan.md](android-export-plan.md)).
Entradas novas no topo. Cada rodada registra aparelho, build, o que foi aprovado e o que ficou pendente.

## 2026-09-23 - A0b: APK WebView mínimo com a cena `motion`

**Aparelho:** OPPO Find X3 Pro (OPG03, variante KDDI/au), Android 13 (API 33), Snapdragon 888 (SM8350),
tela 3216x1440, WebView `com.google.android.webview` 150.0.7871.181.

**Build:** template [tools/android/webview-template](../tools/android/webview-template/) (AGP 9.4.1, Gradle 9.7.1,
compileSdk 37, targetSdk 36, minSdk 24), APK debug de 49,1 MB com `build-web/dist/motion` (runtime Web release do
commit f344f812) em `assets/www/`. Instalado com `adb install -r`, aberto com `--es query "debug=1"`.

**Toolchain:** Android Studio 2026.1.4 em `D:\Program Files\Android\Android Studio` (JDK = `jbr`, OpenJDK 25);
SDK em `%LOCALAPPDATA%\Android\Sdk` (platform 37, build-tools 36, adb 1.0.41). O primeiro `assembleDebug` compilou
sem erro.

Aprovado:

- Carga offline de dentro do APK por `https://appassets.androidplatform.net/assets/www/` (app sem permissão
  `INTERNET`), sem erro no console (logcat `RangeWeb`).
- WebGL 2 (`OpenGL ES 3.0 (WebGL 2.0 (OpenGL ES 3.0 Chromium))`), Python e cena rodando em paisagem.
- `bge.logic.motion` no WebView: `available=True`, gravidade ≈ (0.1, 0.2, 9.8) com o aparelho deitado;
  inclinação e `calibrate()` pelo toque aprovados pelo usuário ("funciona").
- 2026-09-24: APK reinstalado com a marca `RangeWebView/1` (runtime release): botão "Tela cheia" não aparece;
  Home e retorno (via `adb shell input keyevent KEYCODE_HOME` e relançamento) voltam com a cena rodando, sem
  recarregar e sem erro no logcat.
- 2026-09-24: giro de 180° com `sensorLandscape` chega a `ROTATION_270` (visto por `dumpsys window`). Em pé
  (retrato) a imagem não gira: é o esperado. Decisão do usuário: o jogo fica só em paisagem.
  Com o aparelho quase deitado (como se joga a cena `motion`) o Android não detecta o giro, como em qualquer app.

- 2026-09-24: First Person (com `Anastacio_Music.mp3`, `--perf`, runtime release) no APK. Primeira carga mostrava
  "Erro: If you see this error we have a bug. Please report this bug to chromium.": o WebView não tem pointer
  lock e rejeita o pedido do runtime com `UnknownError` (confirmado por CDP chamando `requestPointerLock()`).
  Corrigido no `index.html` (pedido vira no-op no APK). Depois disso: jogo roda, `AudioContext` `running`, sem
  erro; usuário confirmou "está funcionando" e controle por toque "bom".
- Frame time com o jogo parado, 1200 frames medidos por CDP (canvas 640x480, DPR 3,5):
  APK 1ª medida p50 16,7 ms / p95 33,4 ms / 50,3 fps médio (19% dos frames acima de 20 ms);
  APK 2ª medida p50 16,7 / p95 16,7 / 59,9 fps. Chrome 154 do mesmo aparelho, mesmo pacote servido do PC por
  `adb reverse`: p50 33,3 / p95 33,4 / 37,5 fps (uma medida; a segunda falhou por conexão). Variação grande entre
  medidas: ainda não dá para dizer que o APK é mais rápido.
- Tocar no ícone com o jogo aberto por `adb shell am start` abria uma segunda instância da Activity por cima (dois
  jogos rodando). Corrigido com `launchMode="singleTask"`.
- Música: sem som no primeiro pacote porque o `First_Person.range` local (`tools/ADD na engine anastacioEngine/`,
  15/09) é anterior ao script da música. Reempacotado com o `.range` publicado em `gh-pages`
  (`musica/game/First_Person.range`, que chama `aud.Sound(...//Anastacio_Music.mp3)`): log `[music] tocando
  status=True` e pico 0,65 na saída do `ScriptProcessorNode` (antes 0). Usuário confirmou que ouve a música.

- 2026-09-24: save/IDBFS no APK com `web-save.range` (`tools/create_web_save_scene.py`, runtime release):
  sessão 1 `[web-save] SAVED`; `am force-stop` (processo encerrado) e sessão 2 `[web-save] LOADED`. O IndexedDB
  do WebView persiste entre execuções do app. Depois o APK voltou a ter o First Person.

- 2026-09-24: rotação liberada em paisagem e retrato (`fullUser`, respeita o bloqueio de rotação do sistema),
  revertendo a decisão "só paisagem". Três problemas corrigidos, aprovados pelo usuário ("ficou muito bom"):
  imagem achatada ao abrir em pé (a página usava a proporção padrão 960x540 e o First Person roda em 640x480);
  proporção que se deformava a cada giro (o SDL troca `canvas.width/height` pelo tamanho CSS e o `index.html`
  media a proporção por eles); câmera que virava um pouco a cada giro (o cursor virtual do mouse-look ficava no
  centro antigo; agora é reescalado no resize em `GHOST_SystemSDL.cpp`).

- 2026-09-24: A3/A4 aceito. APK debug do First Person (`com.anastaciogames.firstperson`, nome "teste1_fabio")
  gerado pelo painel "Android (Range)" e instalado com "Instalar no celular"; usuário confirmou que funciona.
  Primeiro clique em "Gerar APK" não fazia nada: o arquivo ficava modificado após preencher os campos e o aviso só
  aparecia no topo. Agora o painel salva o arquivo sozinho e mostra erros/resultado abaixo dos botões.
  O teste `engine_android_export.py` instalou sem querer o app de teste "jogo" (`com.anastaciogames.testepainel`)
  com o celular ligado; desinstalado, e o teste só instala com `RANGE_ANDROID_TEST_INSTALL=1`.

Pendente (não confirmado nesta rodada):

- Home/retorno com o processo recriado pelo sistema.
- Repetir a comparação APK x Chrome com mais medidas e jogando (não só parado).
- MIME `application/wasm` pelo `WebViewAssetLoader` (sem aviso de fallback no log, mas não medido).
- O aceite anterior no Chrome foi no OPPO Reno14; este teste usou o Find X3 Pro.
