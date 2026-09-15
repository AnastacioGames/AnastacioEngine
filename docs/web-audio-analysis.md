# Áudio Web: pesquisa e pontos de integração

Auditoria de 2026-09-13 para apoiar Claude. Alvo: navegador comum, WebAssembly + Web Audio.
Revisão de código e fontes oficiais; nenhum build ou teste audível realizado nesta auditoria.

## Conclusão

Preservar Audaspace e avaliar seus backends existentes antes de substituir a biblioteca.
**SDL2 é o primeiro candidato para uma prova de reprodução básica**, porque o backend local
recebe um callback de mixagem e o port já usa SDL2. **OpenAL do Emscripten é o candidato
para reaproveitar a API OpenAL**, mas o backend da engine exige trabalho no streaming.
Essas prioridades são inferências de engenharia, ainda não uma integração comprovada.

## Evidências locais

- `source/CMakePresets.json:147` e `build-web/CMakeCache.txt`: `WITH_OPENAL=OFF` e
  `WITH_AUDASPACE=OFF`; `WITH_SDL=ON`. O build atual não demonstra falha de saída de
  áudio: o sistema está desativado. SDL para janela não implica Audaspace funcionando.
- `source/extern/audaspace/plugins/sdl/SDLDevice.cpp`: `SDL_OpenAudio` instala
  `SDL_mix`, que chama `SoftwareDevice::mix`; `playing()` usa `SDL_PauseAudio`.
  Esse backend não cria a thread de streaming encontrada no backend OpenAL.
  Isso não prova que todo Audaspace dispense threads.
- `source/extern/audaspace/include/devices/SoftwareDevice.h:51`: implementa `I3DDevice`,
  e seu handle implementa `I3DHandle`. Há infraestrutura de áudio espacial reutilizável;
  equivalência de atenuação, posicionamento e efeitos deve ser testada.
- `source/extern/audaspace/plugins/openal/OpenALDevice.cpp:1187`: `start()` cria
  `std::thread` para `updateStreams()`, com `join()` e espera de 20 ms no processamento.
  Não basta ligar uma flag: decidir entre atualização cooperativa pelo loop Web ou
  configuração explícita de threads, após avaliar a implementação OpenAL do SDK.
- `source/extern/audaspace/blender_config.cmake`: integração estática já existe;
  conecta SDL/OpenAL e decodificadores às opções do projeto. O CMake do Audaspace usa
  `OPENAL_LIBRARY`/`OPENAL_INCLUDE_DIR`, que precisam representar o SDK Web, sem bibliotecas nativas.
- `source/source/blender/blenkernel/intern/sound.c:918`: há caminho sem Audaspace.
  Ao religar áudio, revisar também stubs de link, registro de dispositivo e módulo Python `aud`.
- `D:/emsdk/upstream/emscripten/src/lib/libopenal.js:27` (SDK local 6.0.9):
  `ALC_EXT_EFX` aparece como TODO. Reverb/filtros específicos de OpenAL não podem ser
  presumidos disponíveis. O mesmo arquivo usa `autoResumeAudioContext`.
  O SDK local foi inspecionado; sua localização não prova a origem física do build existente.

## O que a pesquisa confirmou

O Emscripten fornece uma implementação própria de OpenAL 1.1 sobre Web Audio, ligada
com **`-lopenal`**. Não se trata de uma porta de OpenAL Soft com `-sUSE_OPENAL=1`;
essa descrição do levantamento anterior estava incorreta. A documentação exige devolver
controle ao loop JavaScript e explica a retomada automática após interação do usuário.
As extensões devem ser consultadas antes do uso.
[Documentação oficial de áudio](https://emscripten.org/docs/porting/Audio.html).

SDL e OpenAL do Emscripten usam Web Audio como saída.
[Documentação do Emscripten](https://emscripten.org/docs/porting/guidelines/browser_limitations.html).
Isso torna viável testar o backend SDL existente, mas não garante que seu CMake,
inicialização, callbacks e dependências já estejam prontos para o navegador.

**miniaudio** é uma alternativa com suporte Web/Emscripten e API de saída PCM.
Poderia sustentar um novo backend de Audaspace, preservando sua interface de alto nível,
mas esse adaptador seria trabalho novo. Não é substituição direta de `AUD_*`.
Seu manual também documenta uma opção AudioWorklet com flags adicionais: não adotar
essa configuração automaticamente no runtime atual.
[Projeto](https://miniaud.io/) e [manual](https://miniaud.io/docs/manual/index.html).

## Sequência sugerida para Claude

### Complemento para implementação — segunda revisão de 2026-09-13

Começar pelo marco **tom em memória → Audaspace → SDL2 → saída do navegador**.
O objetivo desse marco é confirmar o dispositivo e o mixer antes de integrar arquivos de som.

Pontos concretos encontrados na segunda revisão:

| Local | Achado e ação a avaliar |
| --- | --- |
| `source/intern/ghost/intern/GHOST_SystemSDL.cpp:37` | O construtor chama `SDL_Init(SDL_INIT_VIDEO \| SDL_INIT_TIMER)`, sem `SDL_INIT_AUDIO`. Verificar a ordem de inicialização do runtime e inicializar áudio antes de abrir o dispositivo, com tratamento do retorno e ciclo de encerramento correspondente. |
| `source/extern/audaspace/CMakeLists.txt:50` | `OpenALEffect.cpp` e `OpenALReverbEffect.cpp` entram na lista principal de fontes, fora do bloco `WITH_OPENAL`. Portanto, `WITH_OPENAL=OFF` sozinho não isola o backend SDL das dependências OpenAL. |
| `source/extern/audaspace/src/fx/GEEffects/OpenALEffect.cpp:36` | Inclui `al.h`, `alc.h`, `efx.h` e chama `alGenEffects`, `alGenAuxiliaryEffectSlots` e `alGenFilters`. Auditar também headers e bindings C de GEEffects ao isolar esses recursos; remover apenas dois arquivos pode deixar referências indefinidas. São riscos de compilação/link identificados estaticamente, não erros reproduzidos por build nesta revisão. |
| `source/extern/audaspace/CMakeLists.txt:641` | A integração embutida usa `SDL_FOUND`, `SDL_INCLUDE_DIR` e `SDL_LIBRARY`; a busca SDL2 é do modo standalone. Conferir flags da porta Emscripten nos comandos efetivos do alvo `audaspace`, não apenas no executável. |
| `source/source/blender/blenkernel/intern/sound.c:211` | Já existe `BKE_sound_force_device`. Avaliar seu uso antes de `BKE_sound_init` para selecionar `SDL` no teste Web, evitando depender do índice de dispositivo salvo nas preferências desktop. |
| `source/source/blender/blenkernel/intern/sound.c:267` | Se `AUD_init` falha, o código abre `None`. Esse fallback pode dar execução aparentemente normal e completamente silenciosa. Registrar dispositivo solicitado, sucesso de abertura e ocorrência de fallback no teste. |
| `source/source/gameengine/Ketsji/KX_Speaker.cpp:154` | Speaker usa `AUD_Device_getCurrent()`. O teste final deve usar o dispositivo compartilhado da engine, também exposto por `BKE_sound_get_device()`, para exercitar o volume mestre real. |

Configuração candidata do marco: `WITH_AUDASPACE=ON`, `WITH_SDL=ON`,
`WITH_OPENAL=OFF`, mantendo FFmpeg desligado e sem adicionar decodificadores ainda.
**Não é uma receita pronta de build:** primeiro resolver a inclusão incondicional de GEEffects
e verificar dependências transitivas. Preservar o caminho desktop ao delimitar recursos Web.

Diagnóstico mínimo a recolher: dispositivo selecionado, parâmetros obtidos (frequência/canais/formato),
abertura ou fallback `None`, ocorrência do primeiro callback e contagem agregada de frames mixados.
Evitar log por amostra/callback e qualquer espera bloqueante no loop Web.
Um callback executado prova avanço do mixer, não prova que o usuário ouviu o som.

Entrega do primeiro marco: build Web bem-sucedido e página com início por clique,
tom audível e stop/resume funcionando. Depois passar ao WAV e ao Speaker real.
Aplicar as regras de build e anti-loop do `AGENTS.md`; esta revisão não alterou fontes
nem compilou o runtime.

### Marcos seguintes

1. Fazer uma prova pequena com Audaspace + SDL2 e um gerador de tom/PCM em memória,
   para testar saída sem envolver codecs. Verificar inicialização do subsistema de áudio,
   registro/seleção do dispositivo SDL e ligação estática. Não religar todas as dependências.
2. Disponibilizar início por clique e testar pause/resume após alternar a aba.
   Falta de som antes do gesto não deve ser confundida com defeito do mixer.
3. Integrar um asset WAV e validar separadamente o decodificador. O Audaspace configura
   libsndfile/FFmpeg por opções próprias; suporte do navegador a um formato não significa
   que `AUD_Sound` consiga abri-lo no filesystem Wasm. Não presumir WAV funcional sem decoder.
4. Testar Sound Actuator, Speaker, loop, stop, pitch, volume mestre e chamadas Python sobre
   o dispositivo real da engine. Validar duas fontes mono em posições distintas e listener móvel.
5. Se SDL não atender aos requisitos, medir o custo de adaptar `OpenALDevice::updateStreams`
   para trabalho limitado por frame. Não chamar o loop bloqueante existente dentro do frame.
   Se optar por pthreads, analisar também sincronização, execução no browser e deploy antes.
6. Tratar efeitos EFX como capacidade separada: detectar suporte e definir comportamento
   explícito para efeitos ausentes. Não anunciar equivalência ao áudio desktop sem testes.

Aceite: som audível no jogo real, controle pelo usuário e scripts, retomada sem travar,
ausência de erros de carregamento e teste nos navegadores de destino. Logs e build são
necessários, mas não substituem a confirmação audível. A pesquisa está concluída;
o port de áudio continua pendente.
