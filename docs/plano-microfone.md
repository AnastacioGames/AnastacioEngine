# Plano: microfone na engine (jogo, editor, Web e Android)

Estado: aprovado em 2026-11-08 após revisão (/code-review: 9 pontos aceitos, 1 recusado — conversão s16→float in-place já é correta). Implementação começando pela fase 1.

## Contexto

Nem a engine, nem o Blender 2.79 dela, nem o Blender 5 gravam áudio. O usuário quer:
- no jogo: interagir com o microfone (volume da voz, gravar e tocar de volta, efeitos);
- no editor: gravar áudio e usar como Sound/strip;
- o mesmo no runtime Web e no APK Android (WebView sobre o build Web).

Não precisa de biblioteca nova. A captura no desktop já existe e está compilada:
`OpenALReader` (`source/extern/audaspace/plugins/openal/OpenALReader.cpp`), mas nada a usa.
Na Web, o navegador dá `getUserMedia`; o runtime já tem um AudioWorklet de saída
(`plugins/webaudio/WebAudioDevice.cpp`) cujo esquema dá para espelhar na entrada.

## Decisões

1. **Um núcleo C++ só, com backends.** Classe `aud::Microphone` no Audaspace com fila
   circular própria. Backends: OpenAL (desktop) e WebAudio (Web/Android). Python e jogo
   não sabem qual backend está ativo.
2. **Captura por sondagem, não pelo mixer.** `poll()` puxa as amostras do backend para a
   fila, mede nível e acumula gravação. Motivo: o `OpenALReader` devolve menos amostras
   que o pedido quando não chegou som, e o mixer do Audaspace não foi feito para isso.
   Quem toca o som ao vivo lê da fila e completa com silêncio.
3. **WAV próprio (PCM 16 bits).** A Web não tem writer (sem libsndfile/ffmpeg) e
   `Sound.write` falha lá. Um writer WAV mínimo resolve em todas as plataformas.
4. **Microfone é opt-in no export.** Android só pede `RECORD_AUDIO` se o jogo marcar
   "Microphone"; nada muda para jogos que não usam.

## Qualidade: voz leve

Padrão mono, 22 050 Hz, WAV PCM 16 bits (~43 KB/s, ~2,6 MB/min). Basta para voz e
deixa fila, gravação e arquivos pequenos. Estéreo/44,1 kHz só se o jogo pedir. Na Web o
`AudioContext` roda a 48 kHz: o worklet de entrada reduz para 22 050 Hz (média simples
+ decimação) antes de mandar ao WASM, para mandar menos dados pela porta.

## Fase 1: núcleo no Audaspace (desktop)

Arquivos novos em `source/extern/audaspace/`:
- `include/devices/IMicrophoneBackend.h`: `open(device, rate, channels)`, `close()`,
  `available()` (amostras prontas), `read(buffer, n)`, `devices()`, `state()`
  (`granted / denied / pending / error`).
- `plugins/openal/OpenALMicrophone.{h,cpp}`: backend sobre `alcCaptureOpenDevice /
  alcCaptureSamples / ALC_CAPTURE_SAMPLES`, aproveitando o código de `OpenALReader.cpp`.
  Lista dispositivos com `ALC_CAPTURE_DEVICE_SPECIFIER`. Sob `WITH_OPENAL`.
- `include/devices/Microphone.h` + `src/devices/Microphone.cpp`:
  - fila circular float (~2 s) protegida por mutex; `poll()` (main thread) é o único
    escritor. Cada consumidor tem seu próprio cursor de leitura: nível, gravação e cada
    reader ao vivo (thread do mixer). Ninguém "rouba" amostra de outro;
  - `level()` (RMS do último bloco), `peak()` com queda suave,
    `startRecording()/stopRecording()` → `std::shared_ptr<Buffer>` (a gravação copia
    no `poll()`, não depende do cursor do ao vivo);
  - `specs()` devolve a taxa **real** do backend (na Web é a do `AudioContext`, em geral
    48000). O pedido de `rate` é só sugestão; quem precisar converte com `resample`;
  - `createLiveSound()`: `ISound` cujo reader lê da fila e completa com zero (para
    tocar ao vivo e aplicar efeitos já existentes: pitch, eco, filtros);
  - `recordingSound()`: devolve a gravação como `StreamBuffer` (`include/util/StreamBuffer.h`).
- `src/file/WAVWriterSimple.cpp` (ou função `writeWav(path, buffer, specs)`): grava PCM16.
- Registro do backend: o plugin registra uma fábrica de backend (mesmo padrão de
  `registerPlugin()` dos devices); `Microphone` escolhe a de maior prioridade.
- `CMakeLists.txt` do audaspace: adicionar os fontes no ramo `NOT PLUGIN_OPENAL`
  (linhas ~590-611) e o núcleo no `SRC` geral.

Ajustes sobre o `OpenALReader` atual:
- buffer do dispositivo de captura OpenAL do tamanho da fila (~2 s), não `buffersize`,
  para aguentar travadas e carregamentos (LibLoad, load assíncrono) sem estouro; se
  `available()` chegar ao limite, contar perda (`dropped`) em vez de falhar calado;
- chamar `alcCaptureStop` antes de fechar;
- `convert_s16_float` in-place está correta (percorre de trás para frente,
  `src/respec/ConverterFunctions.cpp:122`); pode ser reaproveitada.

## Fase 2: Python `aud` (editor e jogo)

Novo `bindings/python/PyMicrophone.{h,cpp}`, registrado em `PyAPI.cpp` como `aud.Microphone`
(seguir o padrão de `PySound.cpp`: `tp_alloc`, `shared_ptr`, `AUDError`).

```python
mic = aud.Microphone(device=None, rate=22050, channels=1)
aud.Microphone.devices()          # lista de nomes
mic.start(); mic.stop(); mic.poll()
mic.level, mic.peak, mic.active, mic.state   # state: 'granted'|'denied'|'pending'|'error'
mic.record_start(); snd = mic.record_stop()  # aud.Sound (StreamBuffer)
mic.live                          # aud.Sound ao vivo, para device.play(mic.live.pitch(1.5))
mic.save_wav(path)                # usa o writer WAV da fase 1
```

O módulo `aud` já é importável no jogo (`KX_PythonInit.cpp:2998-3006`, importado em `:3150`)
e no editor (`bpy_interface.c:226`).

## Fase 3: jogo (`Range.audio.microphone`)

- `KX_AudioManager` (`source/source/gameengine/Ketsji/KX_AudioManager.cpp`) guarda um
  `aud::Microphone` criado sob demanda e chama `poll()` em `KX_AudioManager::Update()`
  (`:502`), uma vez por frame.
- Python em `py_audio_methods` (`:1206`): `Range.audio.microphoneStart(device=None)`,
  `microphoneStop()`, `microphoneLevel()`, `microphonePeak()`, `microphoneState()`,
  `microphoneRecordStart()`, `microphoneRecordStop()` → `aud.Sound`,
  `microphoneSave(path)` (no Web vai para `/saves`, IDBFS), `microphoneLive()` → `aud.Sound`.
- Só o fim do jogo (e `microphoneStop()`) fecha o microfone. `StopAll()` (`:937`) não
  mexe nele: trocar de música ou de cena não pode cortar uma gravação nem, na Web,
  pedir permissão de novo.
- Opcional: `Range.audio.microphoneSpectrum(bands)` com nível por bandas (FFTW está
  desligado: filtros passa-banda simples ou FFT pequena embutida). Não usar
  `Range.logic.getSpectrum()`: no BGE antigo ele é o espectro da saída.
- Depois (fase 6): sensor de Logic Brick/Logic Tree "Microphone" (nível acima de X).

## Fase 4: Web

- `plugins/webaudio/WebMicrophone.{h,cpp}` (só `EMSCRIPTEN`), backend da fase 1:
  - `EM_JS`: `navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,
    noiseSuppression:true, autoGainControl:true}})` → `ctx.createMediaStreamSource` →
    `AudioWorkletNode('range-input')`, no mesmo `AudioContext` de
    `Module.rangeAudio.ctx` (`WebAudioDevice.cpp:97-137`). O nó tem 1 saída ligada a um
    `GainNode` com ganho 0 até o `destination`, senão alguns navegadores não chamam
    `process()`. `start()` chama `ctx.resume()`.
  - O worklet manda blocos `Float32Array` pela porta (transferível); o main thread
    copia para um buffer alocado uma vez com `_malloc` e chama `_aud_webmic_push(ptr, n)`,
    que escreve na fila C++. Exportar a função (`EMSCRIPTEN_KEEPALIVE` ou
    `EXPORTED_FUNCTIONS` em `source/source/blenderplayer/CMakeLists.txt`, como o
    `_aud_webaudio_mix` já existente). Sem SharedArrayBuffer (build Web sem pthreads).
  - Taxa real = `ctx.sampleRate`, informada ao C++ na abertura.
  - `state()` vem da promessa do `getUserMedia` (pendente/negado/liberado).
- `tools/web/package-web.py`: em `syncAudio()` (`:785-809`) desligar as trilhas do
  microfone quando a página fica oculta; flag `--microphone` no manifest.json
  (mesmo padrão de `--cardboard`, `:1199`).
- Salvar: `microphoneSave` grava em `/saves` e chama `FS.syncfs(false)` (padrão de
  `saveGamePythonConfig`, `KX_PythonInit.cpp:3764`). Opcional: `download(path)` via
  `Blob` + `a.download`.
- Exige contexto seguro (https ou localhost). O pedido de permissão aparece no primeiro
  `start()`; o jogo deve chamar `start()` após um clique/toque.

## Fase 5: Android (WebView)

- `source/release/scripts/modules/range_web/android.py`: `"microphone": False` em
  `DEFAULTS` (`:36-50`); em `apply_config` (`:365`) inserir antes de `<application`
  `RECORD_AUDIO` e `MODIFY_AUDIO_SETTINGS` com `_replace_once`. Ler `microphone` do
  manifest.json do pacote Web (como `cardboard`, `:585`). CLI em
  `tools/web/package-android.py` e campo na UI de export.
- `tools/android/webview-template/.../MainActivity.kt` (`WebChromeClient` em `:82`):
  `onPermissionRequest` → se pedir `RESOURCE_AUDIO_CAPTURE`:
  - sem `RECORD_AUDIO` no manifesto: `deny()` na hora;
  - já concedida (`checkSelfPermission`): `grant()` na hora;
  - senão guardar o `PermissionRequest` num campo, `requestPermissions(RECORD_AUDIO)`,
    e em `onRequestPermissionsResult` chamar `grant()` ou `deny()` e limpar o campo;
  - negado com "não perguntar de novo" também responde `deny()` (o callback vem
    negado na hora). Toda rota termina em `grant` ou `deny`, nunca fica pendente.
- A página já é servida em `https://appassets.androidplatform.net` (contexto seguro).

## Fase 6: editor

- `source/source/blender/editors/sound/sound_ops.c`: operador modal `SOUND_OT_record`
  com timer: `start()`, `poll()` a cada tique, nível no cabeçalho/status bar, Esc/clique
  para parar. Ao parar: grava `//sounds/rec_###.wav`; se o .range ainda não foi salvo,
  grava num temporário e empacota no arquivo (packedfile, como `SOUND_OT_pack`,
  `sound_ops.c:733`) para não depender do temporário. Cria o datablock Sound e, se
  aberto no Sequencer, adiciona o strip no
  frame atual (reusar `sequencer_add_sound_strip_exec`, `sequencer_add.c:740`).
- Botão "Record" no menu Add do Sequencer e no painel de Sound; dispositivo de entrada
  como propriedade do operador (lista de `aud.Microphone.devices()`), sem mudar DNA.
- Gravar junto com o Play da timeline (sincronizado) fica para depois.

## Fora do plano (por enquanto)

Reconhecimento de voz (Vosk/whisper.cpp), chat de voz multiplayer (Opus), cancelamento de
eco no desktop (Voice Capture DSP do Windows, WebRTC APM, SpeexDSP), Kinect.

## Verificação

- Build: skill `build-anastacio` (desktop) e build Web (`build-web-release`).
- Teste automático desktop sem microfone físico: OpenAL Soft tem dispositivo de captura
  falso? Se não, testar `Microphone` com um backend de teste (seno) via Python:
  `aud.Microphone(...)` com backend `"test"` → `level` > 0, `save_wav` gera WAV válido
  (ler de volta com `aud.Sound.file`).
- Cena de teste em `tools/debug/cenas/` (skill `cena-de-teste`): texto na tela com o nível,
  tecla R grava, P toca de volta com pitch. Aceite com janela pelo usuário (fala no mic).
- Web: abrir em localhost no Chrome, conferir pedido de permissão, nível e gravação em
  `/saves`; WAV salvo com a taxa do `AudioContext` e tocando na velocidade certa;
  negar permissão → `state == 'denied'` sem travar.
- Desktop: travada artificial de 3 s durante gravação → contador `dropped` e áudio sem
  lixo depois.
- Android: APK com `microphone` ligado no celular (Adreno 660): pedido do sistema, nível
  reage. APK sem a opção: manifesto sem `RECORD_AUDIO`.
- Editor: `SOUND_OT_record` via `tools/testes_engine/controle.py`; strip aparece no
  Sequencer e toca.
- `python tools/check_docs.py`, entrada no `docs/changelog.md` e item no `docs/roadmap.md`.

## Ordem sugerida

1 → 2 → 3 (com cena de teste e aceite) → 4 → 5 → 6.
