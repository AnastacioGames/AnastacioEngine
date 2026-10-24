# Testes manuais Android

Registro dos testes em aparelho físico da rota APK WebView ([android-export-plan.md](android-export-plan.md)).
Entradas novas no topo. Cada rodada registra aparelho, build, o que foi aprovado e o que ficou pendente.
Todos os testes abaixo são de 2026-09-23 e 2026-09-24; detalhes em [changelog-arquivo.md](changelog-arquivo.md).

## Aparelhos

- **OPPO Find X3 Pro** (OPG03), Android 13 (API 33), Snapdragon 888, tela 3216x1440 a 120 Hz, DPR 3,5,
  WebView 150–153, Chrome 154.
- **Galaxy Tab S6 Lite** (SM-P613), Snapdragon 720G, Android 14, tela 1200x2000, DPR 1,5, WebView e Chrome 153.

Toolchain: Android Studio 2026.1.4 (JDK `jbr`, OpenJDK 25), SDK em `%LOCALAPPDATA%\Android\Sdk`, AGP 9.4.1,
Gradle 9.7.1, compileSdk 37, targetSdk 36, minSdk 24.

## Aprovado

- Carga offline do APK (sem permissão `INTERNET`), WebGL 2, Python, cena `motion`; `bge.logic.motion` com
  inclinação e `calibrate()`.
- Home e retorno sem recarregar; rotação `fullUser` sem deformar imagem nem girar a câmera.
- First Person com música; pointer lock vira no-op no APK (o WebView rejeitava com `UnknownError`).
- Save/IDBFS (`web-save.range`): sobrevive a `am force-stop` e à atualização release sobre release com a mesma chave.
- A3/A4: APK gerado pelo painel e instalado com "Instalar no celular"; release assinado (v1→v2 com `install -r`,
  `firstInstallTime` mantido).
- Controles na tela (cena `pad`, layouts padrão e `wasd`; First Person com `wasd` e `fps`): sem entrada presa em
  arrastar para fora, barra de notificações e Home. Áudio para em segundo plano.
- Tab S6 Lite: `am kill` em segundo plano recria o processo e o jogo carrega de novo; o estado da partida não volta.

## Medidas

Ferramenta: [tools/android/measure-device.py](../tools/android/measure-device.py) (reabre o jogo, clica "Jogar"
por CDP, 5 s de aquecimento e 20 s medidos; `--walk` anda). 3 rodadas, mediana. Chrome pelo `adb reverse`.

| Aparelho / cena | Caso | fps | frames > 20 ms | PSS | Carga até "Jogar" |
|---|---|---|---|---|---|
| Find X3 Pro / First Person | APK parado | 52,4 | 14% | 441 MB | 2,2 s |
| Find X3 Pro / First Person | APK andando | 56,3 | 6% | 446 MB | 2,2 s |
| Find X3 Pro / First Person | Chrome parado | 36,4 | 65% | 610 MB (Chrome inteiro) | 2,0 s |
| Find X3 Pro / First Person | Chrome andando | 44,9 | 34% | 626 MB | 2,0 s |
| Tab S6 Lite / First Person | APK parado | 57,3 | 5% | 379 MB | 4,2 s (1ª 5,7 s) |
| Tab S6 Lite / First Person | Chrome parado | 57,4 | 4% | 432 MB | 3,4 s (1ª 6,2 s) |
| Tab S6 Lite / cena padrão (filtros, 1280x720) | APK parado | 11,5 | todos (83 ms) | 319 MB | 3,2 s |
| Tab S6 Lite / cena padrão | Chrome parado | 12,2 | todos (83 ms) | 439 MB | 2,6 s |

- Sessão de 10 min (Tab S6 Lite, cena padrão parada): 11,53–11,58 fps, sem aquecimento nem vazamento visível.
- Find X3 Pro: o WebView entrega rAF a 60 Hz; o callback do runtime leva p50 20 ms / p99 28 ms com canvas
  640x480. Os quadros perdidos vêm de CPU do runtime por quadro, não de vsync, WebView ou GPU.
- Sensores (Find X3 Pro, 20 s): `devicemotion` ~30 Hz nos dois (APK 28,4 Hz, Chrome 30,8 Hz); idade da leitura
  p50 25 ms no APK e 18 ms no Chrome. Latência até o Python: 1–2 quadros.

## Pendente

- O aceite anterior no Chrome foi no OPPO Reno14; estes testes usaram Find X3 Pro e Tab S6 Lite.
- Layout `race` e botão de alternância de controles em celular real (ver plano de controles).
- Modo avião na primeira abertura, bloqueio de tela, perda de contexto WebGL, sessão longa no jogo real.

Apps que seguiam instalados no Find X3 Pro em 2026-09-24: "Pad teste" (`com.anastaciogames.pad`) e First Person
(`com.anastaciogames.firstperson`).
