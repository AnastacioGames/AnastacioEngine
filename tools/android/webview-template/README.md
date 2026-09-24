# Template WebView Android (A0b)

APK mínimo que roda o pacote Web (`tools/web/package-web.py`) dentro de um WebView, servido por
`https://appassets.androidplatform.net/assets/www/index.html` (`WebViewAssetLoader`). É a prova A0b de
[docs/android-export-plan.md](../../../docs/android-export-plan.md).

O caminho normal agora é o painel "Android (Range)" do editor ou `tools/web/package-android.py`, que copiam este
template para uma pasta temporária, aplicam `android-export.json` (applicationId, nome, versão, ícone, orientação)
e rodam o Gradle. Ao mudar o template, mantenha os trechos que `range_web/android.py` substitui (`applicationId`,
`versionCode`, `versionName`, `app_name`, `screenOrientation`, `android:label`); os testes em
`tools/tests/web_profile/test_android.py` avisam se sumirem. Os passos abaixo continuam valendo para testar o
template à mão.

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

Release assinado: `range_web/android.py` passa `RANGE_ANDROID_KEYSTORE`, `RANGE_ANDROID_KEY_ALIAS` e
`RANGE_ANDROID_KEYSTORE_PASSWORD` pelo ambiente para `assembleRelease` (e `bundleRelease`, com a opção AAB); sem `RANGE_ANDROID_KEYSTORE` o release
sai sem assinatura. Nenhuma chave ou senha fica neste diretório.

## Diagnóstico (build debug)

- Parâmetros do harness: `adb shell am start -S -n com.anastaciogames.rangewebview/.MainActivity --es query "debug=1&perf=1"`.
- Console JS no logcat: `adb logcat -s RangeWeb`.
- DevTools: `chrome://inspect` no PC, com o aparelho ligado por USB.

## Comportamento

- Gira em paisagem e retrato (`fullUser`, respeita o bloqueio de rotação do sistema); o canvas se ajusta à tela
  mantendo a proporção do jogo. Tela cheia imersiva, tela sempre acesa com o app em primeiro plano.
- Sem permissão `INTERNET`: arquivo ausente no pacote responde 404; links externos abrem no navegador.
- O user agent do WebView ganha `RangeWebView/1`; o `index.html` do pacote usa isso para esconder o botão "Tela cheia".
- Girar ou redimensionar não recria a Activity (`configChanges`), para não recarregar o jogo.
- `launchMode="singleTask"`: tocar no ícone com o jogo aberto não cria uma segunda cópia. Por isso, para mudar a
  `query` de um jogo já aberto, use `am start -S` (reinicia o app).
- O WebView não tem pointer lock; o `index.html` do pacote transforma o pedido em no-op dentro do APK.
- Ainda não há protocolo de pausa com o runtime nem controles por toque (próxima rodada).
