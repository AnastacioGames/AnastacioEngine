# Template WebView Android (A0b)

APK mínimo que roda o pacote Web (`tools/web/package-web.py`) dentro de um WebView, servido por
`https://appassets.androidplatform.net/assets/www/index.html` (`WebViewAssetLoader`). É a prova A0b de
[docs/android-export-plan.md](../../../docs/android-export-plan.md); o exportador `package-android.py` (A3) vem depois.

Toolchain: Android Studio (JDK = `jbr` dele, SDK com platform 37), AGP 9.4.1, Gradle 9.7.1 pelo wrapper.

## Gerar e instalar

1. Gerar o pacote Web: `python tools/web/package-web.py --game <jogo>.range --name <nome> --version <versao>
   --runtime-dir build-web-release/bin` (sem `--runtime-dir` ele usa `build-web/bin`, que pode ser um build de depuração).
2. Copiar o conteúdo de `build-web/dist/<nome>/` (sem `serve.py` e `HOSTING.md`) para `app/src/main/assets/www/`
   (pasta ignorada pelo git).
3. Compilar (PowerShell, nesta pasta):

   ```
   $env:JAVA_HOME = 'D:\Program Files\Android\Android Studio\jbr'
   $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
   .\gradlew.bat assembleDebug
   ```

4. Instalar no aparelho com depuração USB: `adb install -r app\build\outputs\apk\debug\app-debug.apk`.

## Diagnóstico (build debug)

- Parâmetros do harness: `adb shell am start -n com.anastaciogames.rangewebview/.MainActivity --es query "debug=1&perf=1"`.
- Console JS no logcat: `adb logcat -s RangeWeb`.
- DevTools: `chrome://inspect` no PC, com o aparelho ligado por USB.

## Comportamento

- Paisagem (`sensorLandscape`), tela cheia imersiva, tela sempre acesa com o app em primeiro plano.
- Sem permissão `INTERNET`: arquivo ausente no pacote responde 404; links externos abrem no navegador.
- O user agent do WebView ganha `RangeWebView/1`; o `index.html` do pacote usa isso para esconder o botão "Tela cheia".
- Girar ou redimensionar não recria a Activity (`configChanges`), para não recarregar o jogo.
- Ainda não há protocolo de pausa com o runtime nem controles por toque (próxima rodada).
