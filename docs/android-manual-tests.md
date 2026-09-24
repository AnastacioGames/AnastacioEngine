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

- 2026-09-24: release assinado no Find X3 Pro (feito pelo agente via adb, chave de teste temporária, app separado
  `com.anastaciogames.testerelease` para não tocar no debug instalado). v1 (versionCode 1) instalada, abriu até
  "Pronto./Jogar" e entrou no jogo; v2 (versionCode 2, versionName 1.1, mesma chave) instalada por cima com
  `install -r`: `Success`, `firstInstallTime` mantido (atualização, não reinstalação, dados do app preservados) e o
  jogo abre de novo. Senha ausente de APK, JSON, relatório e `gradle.log`. Save na atualização: `web-save`
  como release v3 (sessão 1 `[web-save] SAVED`), v4 instalada por cima com a mesma chave e aberta de novo:
  `[web-save] LOADED`. O save sobrevive à atualização release sobre release (o First Person não salva nada). Título da tela inicial aparece como
  "pkg" (nome do pacote Web de teste, não o `appName`).

- 2026-09-24: controle na tela (A1, T4) no Find X3 Pro, aprovado pelo usuário ("funciona, perfeito"). APK debug
  `com.anastaciogames.pad` ("Pad teste") da cena `pad` (`make_pad_project.py`, runtime release), gerado por
  `tools/web/package-android.py --install`. Layout padrão (stick dinâmico + A/B): o logcat `RangeWeb` mostra o
  stick analógico chegando a ±1 e em diagonais (`axes=[0.84, 0.24, ...]`), stick e B juntos
  (`axes=[-0.99, 0.11, ...] buttons=[1]`), A 5 vezes no sensor Joystick e na ação `Pular` do Input System, com
  soltura em todas; usuário fez arrastar para fora, barra de notificações e Home sem entrada presa. Layout `wasd`
  (reaberto com `--es query "touchlayout=wasd"`, sem reinstalar): W/A/S/D e espaço com um `up` para cada `down`
  (W 4, A 6, S 7, D 6, espaço 4) e `map Pular down` pelo espaço. O app segue instalado.

- 2026-09-24: apps de teste desinstalados do Find X3 Pro a pedido do usuário: `com.anastaciogames.testerelease`,
  `com.anastaciogames.rangewebview` (template) e `com.anastaciogames.firstperson` ("teste1_fabio").

- 2026-09-24: controle na tela (A1, item 5 da T4) no jogo real, aprovado pelo usuário ("funciona bem"). APK debug
  `com.anastaciogames.firstperson` 0.1.6 (versionCode 2), mesmo `.range` e música do teste anterior, empacotado
  com o runtime release e `--touch-layout wasd`. O layout mostra um direcional que aperta W/A/S/D (diagonal = duas
  teclas) e o botão Espaço; o jogo, que só lê teclado, anda e pula sem mudança. O log de toque só sai com
  depuração ligada, então a aprovação é visual. O app segue instalado, junto com o "Pad teste".

- 2026-09-24: relato do usuário no 0.1.6: ao ir para segundo plano o jogo pausa e volta de onde estava (mesmo
  depois de muito tempo), mas a música continuava tocando. Corrigido na página (áudio suspenso com a página
  escondida). Pedido no mesmo relato: segundo direcional à direita para olhar e botão de tiro. APK 0.1.7
  (versionCode 3) com `--touch-layout fps` instalado no Find X3 Pro e aprovado pelo usuário: música para em
  segundo plano e volta ao reabrir, stick direito gira a câmera e o botão de tiro atira o disco.

- 2026-09-24: comparação APK x Chrome no Find X3 Pro com medida automática
  ([tools/android/measure-device.py](../tools/android/measure-device.py): reabre o jogo, clica "Jogar" por CDP, 5 s
  de aquecimento e 20 s medidos; `--walk` segura W e alterna A/D). First Person, APK 0.1.7 debug (WebView 153) e
  mesmo pacote no Chrome 154 por `adb reverse`; 3 rodadas por caso, mediana:

  | Caso | fps | frames > 20 ms | Memória (PSS) | Carga até "Jogar" |
  |---|---|---|---|---|
  | APK parado | 52,4 | 14% | 441 MB (app + renderer) | 2,2 s |
  | APK andando | 56,3 | 6% | 446 MB | 2,2 s |
  | Chrome parado | 36,4 | 65% | 610 MB (Chrome inteiro) | 2,0 s |
  | Chrome andando | 44,9 | 34% | 626 MB | 2,0 s |

  Nenhum frame acima de 34 ms nos dois (máximo 50 ms uma vez no Chrome): os frames lentos são de 33 ms, ou seja,
  frames de 60 Hz perdidos, e não travadas. O APK foi melhor que o Chrome em todas as rodadas; com 3 rodadas cada
  e resultados estáveis, a diferença agora é consistente. Heap JS ~45 MB nos dois; a bateria ficou entre 37 e 38 °C,
  sem subir durante a medida. A memória do Chrome inclui o navegador, então não é comparável diretamente.

- 2026-09-24: mesma comparação num aparelho mais fraco: Galaxy Tab S6 Lite (SM-P613, Snapdragon 720G), Android 14,
  tela 1200x2000 (DPR 1,5), WebView e Chrome 153. First Person 0.1.7 debug, jogo parado, 3 rodadas cada, mediana:

  | Caso | fps | frames > 20 ms | Memória (PSS) | Carga até "Jogar" |
  |---|---|---|---|---|
  | APK parado | 57,3 | 5% | 379 MB (app + renderer) | 4,2 s (1ª 5,7 s) |
  | Chrome parado | 57,4 | 4% | 432 MB (Chrome inteiro) | 3,4 s (1ª 6,2 s) |

  Empate: os dois ficam perto de 60 fps, com um frame de 50 ms em uma rodada de cada. O canvas é 640x480 nos dois;
  a área menor no Chrome (barra de endereço) só muda a escala na tela, não o custo de desenhar. Bateria em 28 °C,
  sem subir. Neste aparelho, o Chrome não fica atrás como no Find X3 Pro; a diferença lá pode vir do DPR 3,5 ou da
  tela de 120 Hz, ainda não investigado.

- 2026-09-24: no Tab S6 Lite, com o First Person no APK: o `RangeRuntime.wasm` chega como `application/wasm` e
  `WebAssembly.instantiateStreaming` existe. Home, `am kill` com o app em segundo plano e reabrir: o sistema
  recria o processo, o jogo carrega de novo até "Pronto./Jogar" sem erro no log. O estado da partida não volta.

- 2026-09-24: cena padrão do `RangeEngine.exe` (`source/release/datafiles/startup.blend`, com filtros) como
  cena mais pesada, pacote `Cena_Padrao` (runtime release), APK debug `com.anastaciogames.cenapadrao`.
  Tab S6 Lite, jogo parado, 3 rodadas cada, mediana:

  | Caso | fps | frame típico | Memória (PSS) | Carga até "Jogar" |
  |---|---|---|---|---|
  | APK parado | 11,5 | 83 ms | 319 MB (app + renderer) | 3,2 s (1ª 3,8 s) |
  | Chrome parado | 12,2 | 83 ms | 439 MB (Chrome inteiro) | 2,6 s (1ª 3,8 s) |

  Empate de novo, os dois no limite da GPU: todos os frames acima de 34 ms (83 a 100 ms, cinco vsyncs). O canvas é
  1280x720 (3x os pixels do First Person) e os filtros rodam por pixel. Bateria em 29 °C, sem subir.

- 2026-09-24: sessão longa no Tab S6 Lite, cena padrão no APK, jogo parado, 10 min com leitura por minuto:
  11,53 a 11,58 fps em todos os minutos, p50 83,5 ms sem mudar, bateria de 29,4 para 29,9 °C (nível 89% do
  início ao fim), PSS 325 MB no fim (319 MB nas medidas curtas). Sem queda de fps, aquecimento ou vazamento de
  memória visível. A primeira tentativa, com o First Person andando, foi cancelada: a câmera fica olhando para o
  vazio e não representa carga de jogo.

- 2026-09-24: causa dos frames de 60 Hz perdidos no Find X3 Pro (APK do First Person, parado). A tela está em
  120 Hz (LTPO), mas o WebView entrega o rAF a 60 Hz: os intervalos são só 16,7 ms (~72%) e 33,3 ms (~28%),
  46–49 fps. O tempo gasto dentro do callback de rAF (o frame do runtime no main thread) é p50 20 ms, p90 25 ms,
  p99 28 ms, acima dos 16,7 ms de um vsync, com canvas de 640x480. Não é vsync, WebView nem GPU: é custo de
  CPU do runtime por frame (lógica/Python/física/envio GL). Melhorar exige otimizar o frame do runtime (M4).
- 2026-09-24: sensores no Find X3 Pro, First Person, APK contra Chrome do mesmo aparelho, 20 s cada:

  | Alvo | `devicemotion` | Intervalo p50/p95 | Idade da leitura no frame p50/p95 |
  |---|---|---|---|
  | APK | 28,4 Hz | 33,5 / 53,9 ms | 25 / 50 ms |
  | Chrome | 30,8 Hz | 33,4 / 44,2 ms | 18 / 35 ms |

  `orientation` chega nos dois (alpha/beta/gamma iguais ao evento `deviceorientation`, ex. 90/4/-1 com o
  aparelho deitado). A taxa é a mesma (~30 Hz, limite do navegador); a idade maior no APK acompanha o frame mais
  lento, não o sensor. Latência total até o Python fica em 1–2 frames.

Pendente (não confirmado nesta rodada):

- O aceite anterior no Chrome foi no OPPO Reno14; este teste usou o Find X3 Pro.
