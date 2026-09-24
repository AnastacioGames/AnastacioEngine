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

Pendente (não confirmado nesta rodada):

- Home e retorno (sem recarregar; o processo não foi recriado durante a sessão), giro de 180° em paisagem.
- `?perf=1` com o jogo real (First Person), áudio, save/IDBFS e comparação com o Chrome do mesmo aparelho.
- MIME `application/wasm` pelo `WebViewAssetLoader` (sem aviso de fallback no log, mas não medido).
- Esconder o botão "Tela cheia" do harness dentro do APK (a Activity já é imersiva).
- O aceite anterior no Chrome foi no OPPO Reno14; este teste usou o Find X3 Pro.
