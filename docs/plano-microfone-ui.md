# Plano: microfone na interface (editor, bricks, nós, Range.audio, Web/Android)

Estado: proposta de design, 2026-11-08. Complementa [plano-microfone.md](plano-microfone.md)
(fases 1 e 2 — núcleo `aud::Microphone` e `aud.Microphone` — feitas e testadas).
Revisado por Claude: receitas de eco/robô corrigidas (`sum()` é soma acumulada, não mistura;
usar `mix()` + `volume()`), normalização na Web sem `Sound.data()`.

## 0. Princípios

1. **Três verbos: Gravar, Ajustar, Usar.** Toda tela segue essa ordem.
2. **Um único "Efeito de voz" (preset) em toda a cadeia.** Editor, brick, nó e Python usam a
   mesma lista com o mesmo nome, montada uma vez só em cima de `aud.Sound`
   (`source/extern/audaspace/bindings/python/PySound.cpp`).
3. **Editar sem destruir.** Corte, aparo e fade são dados; o WAV só é regravado em
   "Aplicar (novo WAV)", e o original nunca é apagado.
4. **Nativo e convertível** ([bricks-2.0-plano.md](bricks-2.0-plano.md)): sensor e atuador em
   C++, rodam na Web/Android e entram no `logic_to_python.py`.
5. **Sem DNA novo quando der.** Só sensor e atuador ganham DNA; o editor reusa `bSound` e
   strips do Sequencer.
6. **Voz leve:** mono 22 050 Hz, como no núcleo.

## 1. Presets de efeito (base comum)

Tabela única exposta como `aud.voice_fx(sound, preset, amount=1.0)` (C++ em
`src/devices/VoiceFX.cpp` ou Python puro sobre `aud.Sound`). Editor (bpy importa `aud`) e
jogo usam o mesmo código.

| Preset | Receita (métodos existentes de `aud.Sound`) |
|---|---|
| `NONE` | — |
| `CHIPMUNK` (esquilo) | `pitch(1.6)` |
| `GIANT` (monstro) | `pitch(0.65).lowpass(2500)` |
| `ROBOT` | `s.modulate(Sound.sine(60))` misturado com o seco: `s.volume(0.3).mix(mod)` + `limit` de amplitude não existe → usar `volume` |
| `RADIO` / telefone | `highpass(400).lowpass(3000).volume(1.4)` |
| `ECHO` | `s.mix(s.delay(0.25).volume(0.5)).mix(s.delay(0.5).volume(0.25))` |
| `CAVE` / `HALL` | No jogo: canal com reverb do `KX_AudioManager` (`apply_reverb_settings`, `KX_AudioManager.cpp:368`). Fora do jogo ou na Web: eco múltiplo + `lowpass` |
| `REVERSE` | `reverse()` — só som gravado, não ao vivo |

- `amount` (0–1) interpola o parâmetro principal (pitch, tempo do eco, corte): **um slider só**.
- Reverb é efeito "de lugar": opção separada "Usar reverb da área/World", não preset.
- Ao vivo (`mic.live`): a UI esconde presets com `reverse`/`loop`.
- `pitch` muda a duração (Audaspace não tem time-stretch); documentar.
- **Edição:** `aud.edit(sound, start, end, fade_in, fade_out, normalize)` com `limit(start,end)`
  (aqui `limit` é corte no tempo), `fadein`, `fadeout` e `volume` pelo pico. Pico: no desktop
  por `Sound.data()`; na Web `data()` não existe (sem numpy) → expor o pico calculado no C++
  (`Microphone` já mede `peak`; para som qualquer, função C++ `aud.peak(sound)`).

## 2. Editor

### 2.1 Onde gravar

`SOUND_OT_record` (plano-microfone fase 6, `source/source/blender/editors/sound/sound_ops.c`)
em três lugares, mesmo operador:
1. Sequencer › Add › **Gravar Som (Microfone)** (`bl_ui/space_sequencer.py`); strip no frame
   atual (`sequencer_add_sound_strip_exec`, `sequencer_add.c:740`).
2. Painel do atuador Sound/Voice e nó Sound/Voice: botão **●** ao lado do campo `sound` —
   grava e preenche ("gravar a fala do NPC direto no brick").
3. Painel Sound do strip: **Regravar**.

Durante a gravação: barra de nível e mm:ss no cabeçalho/status bar; Esc/clique para salvar,
botão direito cancela; `denied/error` vira aviso claro. Dispositivo como propriedade do operador
(`aud.Microphone.devices()`), sem DNA. Contagem 3-2-1 opcional (`countdown`).

### 2.2 Editar: reusar o Sequencer, sem editor de onda próprio

O Sequencer já tem trim, split (K), volume animável, forma de onda e prévia. Falta o caminho de
volta para um `bSound` que o jogo usa:
- **`SOUND_OT_bake_strip`** ("Aplicar edição ao som"): strip ativo (trim, volume/fade, pitch)
  → WAV novo (`rec_001_edit.wav`) com o writer da fase 1 → cria/substitui o `bSound`.
- **Painel "Ajustar Som"** (no painel Sound e como popover do botão de som do atuador):
  Início/Fim, Fade in/out, [Normalizar], Efeito [preset ▼] + Intensidade, [▶ Prévia],
  [Aplicar → novo WAV]. Valores como propriedades do operador (redo/F6), sem DNA.

### 2.3 Prévia

▶ em todo lugar com preset (painel, atuador, nó), parando o handle anterior.
**"Ouvir ao vivo"** com o preset: liga o microfone e toca `voice_fx(mic.live)`; avisa
"use fones (microfonia)".

## 3. Logic Bricks

Padrão do Video/VR Head (`SENS_VR_HEAD = 17` em `DNA_sensor_types.h:327`,
`ACT_VIDEO = 28` em `DNA_actuator_types.h:469`).

### 3.1 Sensor "Microphone" (`SENS_MICROPHONE = 18`, `KX_MicrophoneSensor`)

DNA `bMicrophoneSensor { short mode; short flag; float threshold; float hold; char prop[64]; }`.
- **Falando** (padrão): positivo com `level > threshold`, histerese + `hold` (~0,3 s).
- **Grito/Pico**: pulso com `peak > threshold` (palma, assoprar).
- **Silêncio**: positivo após N s abaixo do limiar.
- Palavra-chave: só valor reservado em `mode`.
- `prop` opcional recebe o `level` a cada tick (medidor, boca abrindo, sem Python).
- Liga o microfone sozinho (`KX_AudioManager::MicrophoneAcquire()`, contagem de uso).
- UI: medidor ao vivo durante o jogo; botão **Calibrar** (2 s silêncio + fala → sugere limiar).

### 3.2 Atuador "Voice" (`ACT_VOICE = 29`, `KX_VoiceActuator`)

Separado do `bSoundActuator` (nada quebra em arquivos antigos).
DNA `bVoiceActuator { short mode, preset; float amount, volume; short flag; char slot[64]; }`.
- **Gravar**: segura = grava (walkie-talkie) ou até `max_seconds`.
- **Tocar gravação**: `slot` com preset/amount; conclui no fim (sensor "Concluído", Bricks 2.0).
- **Ao vivo**: `voice_fx(mic.live)` enquanto positivo.
- **Parar**, **Salvar** (`slot` → `//saves/slot.wav`; Web `/saves`, IDBFS).
- `slot` = nome; gravações num dicionário do `KX_AudioManager`, o mesmo de
  `Range.audio.recordings`.
- Flag "Usar reverb da área" (`UpdateVoiceReverb`, `:395`); 3D opcional "Tocar no objeto".
- Conversão (`BL_ConvertActuators.cpp` perto de `ACT_SOUND`, `BL_ConvertSensors.cpp`), RNA,
  `space_logic.py`, versioning (zero = padrão), `logic_to_python.py`, presets em
  `bl_operators/logic_presets.py`: **"Falar para agir"** e **"Gravador"** (R grava, P toca).

## 4. Logic Tree / UI Tree

A Logic Tree compila para bricks ([logic-tree-plan.md](logic-tree-plan.md) §4): nós quase de
graça em `range_logic_tree.py`, padrão de `RangeLogicSound`:
- `RangeLogicMicrophone` ("Quando falar") e `RangeLogicVoice` (com ● e ▶, desenho compartilhado).

UI Tree (`range_ui_tree.py`): peça **"Medidor de microfone"** e botão **"Ativar microfone"**
(o gesto da Web).

## 5. API `Range.audio`

Fase 3 do plano-microfone mais o necessário para casar com os bricks:

```python
a = Range.audio
a.microphoneStart()                      # idempotente; contagem com os sensores
a.microphoneState()                      # 'granted'|'denied'|'pending'|'error'|'closed'
a.microphoneLevel(), a.microphonePeak()  # 0..1
a.microphoneRecordStart()
snd = a.microphoneRecordStop(slot="fala1")   # também em a.recordings["fala1"]
a.recordings                             # dict nome -> aud.Sound (o mesmo do atuador Voice)
a.voiceFx(snd, "ROBOT", amount=1.0)      # mesma tabela de aud.voice_fx
a.edit(snd, start=0.2, end=None, fade_in=0.05, fade_out=0.1, normalize=True)
a.play(sound, reverb=True, obj=None)     # única porta para o reverb
a.playLive("ROBOT", amount=0.7)
a.microphoneSave("fala1", "fala1.wav")   # /saves na Web
a.voicePresets()
```

camelCase como o resto de `Range.audio`; `aud` fica snake_case. Permissão negada não lança
exceção: `microphoneState()` explica e o nível fica 0.

## 6. Web e Android

- `microphoneStart()` fora de gesto fica `pending`; o runtime Web guarda o pedido e executa no
  próximo `pointerdown`/`keydown` (mesmo destravamento do áudio de saída).
- Overlay padrão: `pending` > 1 s → "🎤 Toque para ativar o microfone"; `denied` → "Microfone
  bloqueado: libere nas configurações". Desligável no export.
- Export: "Usa microfone" marcado sozinho (com aviso) se a cena tiver sensor Microphone,
  atuador Voice ou nó equivalente; senão o APK sai sem `RECORD_AUDIO`.
- Avisos no painel: "Web/Android: começa após o primeiro toque; exige https"; reverb do mundo
  na Web é o aproximado.
- Página oculta/app em segundo plano: captura pausada, `level` 0, sem erro.
- Ao vivo: recomendar fones; no navegador `echoCancellation` já vem ligado.

## 7. Fases

| Fase | Entrega | Depende de |
|---|---|---|
| U1 | `aud.voice_fx`, `aud.edit`, `aud.peak`, lista de presets; testes com o backend Test — **código feito 2026-11-08** (`fx/VoiceFX.{h,cpp}` em C++ para o jogo usar direto, `PyVoiceFX.cpp`; também `aud.duration` e `aud.voice_presets(live)`); libs compilam, falta link do exe + teste | fases 1–2 (feitas) |
| U2 | `Range.audio` (fase 3 + `recordings`, `voiceFx`, `edit`, `play(reverb)`, `playLive`); cena de teste R/P/efeitos — **código feito 2026-11-08 no branch feat/microfone, sem build** (API C `AUD_Microphone.h`; nomes finais: `recordings()`, `recording(slot)`, `setRecording`, `playVoice(som_ou_slot, effect, amount, volume, reverb)`, `playLive`, `stopLive`, `microphoneSave`; `MicrophoneAcquire/Release` para os bricks) | U1 |
| U3 | Sensor Microphone + atuador Voice (DNA/RNA/conversão/UI/versioning/logic_to_python/presets) | U2 |
| U4 | Nós Logic Tree + peças UI Tree | U3 |
| U5 | Web (fase 4) + overlay + auto-marcar no export; Android (fase 5) | U2 (U3 p/ auto-marcar) |
| U6 | Editor: `SOUND_OT_record`, painel "Ajustar Som" com prévia, `SOUND_OT_bake_strip` | U1 |

| U7 | Cutscene e Gravação de Movimento usam as gravações (ver §7.1) | U2 (U6 p/ gravar no editor) |

### 7.1 Cutscene e Gravação de Movimento (pedido 2026-11-08)

- **Cutscene** ([cutscene-native-integration-plan.md](cutscene-native-integration-plan.md),
  [notes-cutscene-events.md](notes-cutscene-events.md)): evento/faixa "Fala" que toca um slot
  de `Range.audio.recordings` ou um `bSound` gravado no editor, com preset + amount e
  `edit` (início/fim/fade). Botão ● no evento grava a fala direto no tempo da cutscene.
- **Gravação de Movimento / Rec Play** ([gravacao-de-movimento-plan.md](gravacao-de-movimento-plan.md),
  [rec-play-api.md](rec-play-api.md)): opção "Gravar voz junto" — `microphoneRecordStart()` no
  mesmo frame do início do Rec, e o WAV salvo ao lado da gravação com o offset de início;
  no Play toca sincronizado (dublagem do personagem, narração de replay).
- Mesma regra do resto: um preset só, sem DNA novo no `bSound`; sincronia pelo tempo de
  início gravado (Audaspace não tem time-stretch, então velocidade ≠ 1 no Play só muda o pitch).

U6 pode andar em paralelo a partir de U1 se o editor for prioridade.

## 8. O que NÃO fazer (por enquanto)

- Editor de onda próprio, multitrilha, edição destrutiva.
- Efeitos ao vivo na timeline do Sequencer ou campos de efeito no DNA do `bSound`.
- Mudar `bSoundActuator`/`KX_SoundActuator` para gravar.
- Usar `Range.logic.getSpectrum()` para microfone.
- Reconhecimento de voz (só `mode` reservado).
- Pedir permissão no carregamento da página/APK; só no primeiro uso.
- Time-stretch (não existe no Audaspace).
