# Build no Linux

## TL;DR — comece por aqui

**Se voce baixou o release 0.4.1 e so tem o editor (sem `RangeRuntime`)**: e um bug de empacotamento
conhecido (o `.tar.xz` saiu com um preset so). Ate sair uma release corrigida, compile a partir do
codigo-fonte pelos passos abaixo — voce vai ter os dois executaveis.

Nao tente compilar Blender/UPBGE 2.79 "cru" a partir do codigo original: em distros Linux recentes
(GCC/glibc novos demais pra um codigo de 2014-2015) isso trava com erros de toolchain. Este repo ja tem
um preset Linux com todos os fixes de compatibilidade aplicados (FFmpeg, OpenColorIO, RPATH do Python
etc.) — use ele em vez de tentar compilar do zero.

**Importante**: esses scripts e presets so existem na branch `linux-sync`, nao na `main` nem nos
releases publicados. Confirme que esta nela antes de tudo:

```bash
git clone https://github.com/AnastacioGames/AnastacioEngine.git
cd AnastacioEngine
git checkout linux-sync
```

Depois, um unico comando cobre dependencias (via apt), Python 3.11 isolado, configuracao e build:

```bash
bash tools/linux/quickstart-editor.sh      # editor completo (RangeEngine)
bash tools/linux/quickstart.sh             # so o player/runtime (RangeRuntime), pra rodar um .range
```

Executaveis ficam em `build-linux-editor/bin/RangeEngine` e `build-linux/bin/RangeRuntime`. **Nao e
necessario** baixar `lib/linux_x64` via svn — isso e so para o build Windows (`lib/win64_vc15`); o preset
Linux usa as bibliotecas da propria distro instaladas via apt.

Se travar em algum passo, rode `bash tools/linux/preflight.sh` para checar o ambiente, e guarde a saida
completa do erro (nao so a ultima linha) antes de pedir ajuda.

## PENDENTE NA MAQUINA LINUX (handoff de 2026-09-21) - LEIA PRIMEIRO

Relatado por Kitsuy (tester Linux) sobre o pacote 0.4.0.

### 1. `libpython3.11.so.1.0: cannot open shared object file` — VALIDADO EM LINUX (2026-09-21)

Build, empacotamento e execucao em diretorio limpo confirmados nesta maquina (ver `docs/changelog.md`
2026-09-21). Resumo: `readelf -d` mostra RUNPATH `$ORIGIN/lib:/opt/anastacio-python311/lib:`;
`LD_DEBUG=libs` confirma resolucao via `$ORIGIN/lib` do pacote (nunca tenta o `/opt` absoluto);
`./RangeEngine -b` roda e sai limpo. Precisou de um fix extra nao relacionado ao RUNPATH: faltava
`#include <iostream>` em `source/intern/locale/boost_locale_wrapper.cpp` (usava `std::cout`; so
compilava no MSVC por inclusao transitiva). Falta so publicar 0.4.1 (depois de decidir sobre o item 2).

### 2. Crash de tooltip — fix aplicado e VALIDADO em sessao grafica real (2026-09-21)

Investigacao estatica (2 rodadas) descartou a hipotese original de "checkbox invertida" (comportamento
padrao do Blender upstream, nao bug) e a hipotese de uso-apos-liberacao de ID dentro do `PointerRNA` do
`uiBut` (esse caminho revalida o `but` a cada disparo do timer). Encontrada uma falha estrutural mais
generica em `source/source/blender/windowmanager/intern/wm_tooltip.c`: o timer do tooltip guarda um
`ARegion *region_from` bruto por ate `UI_TOOLTIP_DELAY` (~0.5s); operacoes de layout nesse intervalo
(maximizar/restaurar area, trocar tipo de editor, split/join, fullscreen) liberam `ARegion`s sem passar
por nenhuma limpeza do estado de tooltip pendente — use-after-free plausivel ao disparar o timer.
Corrigido com `wm_tooltip_region_is_valid()`: antes de usar `region_from` em `WM_tooltip_init()`,
confirma que a regiao ainda esta na lista viva de `screen->areabase`/`regionbase`; se nao estiver, limpa
o estado e sai sem dereferenciar. Build (`linux-editor`/`RangeEngine`) limpo apos o fix.

**Validado em sessao grafica real** (DISPLAY local, nao `--background`): "Python Tooltips" foi ligado
(esse e o caminho de codigo mais exposto, ver H1 acima) e o fix foi promovido a padrao de fabrica (ver
abaixo). Hover em botoes seguido de Ctrl+Espaco (maximizar/restaurar area) repetido em varios paineis,
antes do disparo do timer (~0.5s): sem crash, saida limpa do processo. Testado tambem com `HOME` limpo
simulando primeira execucao (sem config previa): preferencias carregam corretamente, sem crash.

**Padrao de fabrica atualizado**: `versioning_defaults.c` deixava `USER_TOOLTIPS_PYTHON` ligado por
padrao, o que (por usar `RNA_def_property_boolean_negative_sdna`) fazia a checkbox "Python Tooltips"
aparecer **desmarcada** e o caminho de codigo mais exposto ao bug nunca rodar em instalacao limpa.
Corrigido para deixar a checkbox marcada por padrao (bit desligado), testando o caminho de codigo real
em vez de mascarar o problema por omissao. `source/release/datafiles/startup.blend` tambem foi
atualizado com as demais preferencias de interface confirmadas pelo usuario.

### (texto original abaixo, preservado como historico da preparacao no Windows)

Causa: o pacote 0.4.0 saiu com RUNPATH absoluto `/opt/anastacio-python311/lib` (so existe na maquina de build).
Alteracoes ja no repo (nao commitadas ate este handoff):

- `source/source/blenderplayer/CMakeLists.txt` e `source/source/creator/CMakeLists.txt`: `BUILD_RPATH`/`INSTALL_RPATH`
  = `$ORIGIN/lib`, e o `libpython3.11.so.1.0` real (SONAME) e copiado para `bin/lib/` (POST_BUILD) e instalado em `lib/`.
- `tools/linux/package-runtime.sh`: aceita `BIN_DIR` (para empacotar o editor), embute `python311/lib`, faz patch do
  RUNPATH antigo (so em builds velhos) e falha se o libpython nao estiver no pacote.

Passos:

1. `bash tools/linux/install-python311.sh` (se `/opt/anastacio-python311` nao existir).
2. `cmake --preset linux-editor -S source && cmake --build build-linux-editor --target RangeEngine -j"$(nproc)" && cmake --install build-linux-editor`
   (idem `linux-runtime`/`build-linux` para o `RangeRuntime`).
3. `readelf -d build-linux-editor/bin/RangeEngine | grep -E 'RPATH|RUNPATH'` -> deve ser `$ORIGIN/lib`; `ls build-linux-editor/bin/lib`
   -> `libpython3.11.so.1.0`; `ldd build-linux-editor/bin/RangeEngine | grep "not found"` -> vazio.
4. `BIN_DIR=build-linux-editor/bin bash tools/linux/package-runtime.sh 0.4.1` (o `.tar.xz` sai em `build-linux/dist/`).
5. Extrair o tar num diretorio limpo, renomear `/opt/anastacio-python311` temporariamente e rodar `./RangeEngine` (janela) e `-b`.
   Se o Python reclamar de `encodings`/stdlib, o problema e a stdlib (ver `python311/lib/python3.11`), nao o libpython.
6. Corrigir se algo falhar, atualizar changelog/este doc e so entao publicar 0.4.1 (seguir `docs/distribution-*.md`/AGENTS.md).

### 2. Crash ao passar o mouse sobre tooltips (causa NAO identificada)

Relato: tooltips crasham o editor; so nao crasha com a opcao de "profile" ligada (provavelmente Show Profile em
Info > Header, `show_framerate_profile`; confirmar com o Kitsuy). Ele viu o mesmo bug no fork dele.
Codigo: `source/source/blender/editors/interface/interface_region_tooltip.c` (ramos de `USER_TOOLTIPS_PYTHON`;
default em `versioning_defaults.c:86`; checkbox "Python Tooltips" e invertido, `rna_userdef.c:3587`).

Passos: compilar o editor com simbolos, rodar `gdb --args build-linux-editor/bin/RangeEngine`, passar o mouse nos
tooltips do painel de profile / botoes que crasham, `bt`. Testar alternando Show Profile e Python Tooltips. Corrigir a
causa (ponteiro invalido, `strinfo`/RNA nulo, etc.), nao so o default. Registrar no changelog.

### 3. Ao terminar

Atualizar `docs/changelog.md` e `docs/roadmap.md` (secao Linux) e commitar com push para a branch `linux-sync`.

## Estado em 15 de setembro de 2026 — validacao em Linux nativo (Ubuntu 24.04, GPU NVIDIA real)

Primeira validacao fora do WSLg, num notebook com grafica hibrida Intel+NVIDIA (Optimus/PRIME):
`RangeRuntime` compila, instala e roda o jogo `RolimaRacer.range` do usuario com audio audivel e GPU NVIDIA
dedicada em uso — **confirmado diretamente pelo usuario** (nao so por log), depois de tres bugs reais
encontrados e corrigidos nesta rodada:

1. **Binario instalado nao abria fora do ambiente de build**
   (`libpython3.11.so.1.0: cannot open shared object file`) — RPATH ausente para o Python isolado. Corrigido
   em `source/source/blenderplayer/CMakeLists.txt`. Ver `docs/changelog.md` (2026-09-15) para o bug
   secundario de RPATH_CHECK que isso revelou.
2. **Audio nao tocava** (assets `.ogg`/`.mp3` do jogo) — `WITH_CODEC_SNDFILE` era sempre revertido para
   `OFF` por um bug de nome de variavel em `build_files/cmake/Modules/FindSndFile.cmake`
   (`SndFile_FOUND` vs `LIBSNDFILE_FOUND`). Corrigido nesse modulo.
3. **Jogo lento, rodando na iGPU Intel em vez da NVIDIA dedicada** — notebooks Optimus/PRIME usam a iGPU por
   padrao. Precisa de `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` (o
   `tools/linux/quickstart.sh` agora detecta isso sozinho via `xrandr --listproviders` e injeta as variaveis
   automaticamente).
4. **Bug visual so na NVIDIA**: arvores/grama (materiais "Alpha Blend Hashed") apareciam com ruido tipo
   "chiado de TV analogica". Causa: fallback de dither por shader que so fica correto com MSAA real, e a
   NVIDIA (ao contrario do Mesa/Intel) honra literalmente "0 amostras pedidas". Corrigido forcando um minimo
   de amostras em `LA_Launcher.cpp` e `BL_Converter.cpp::ConvertScene` (por cena, ja que a pista do jogo e
   carregada como uma cena separada em runtime). Ver `docs/changelog.md` (2026-09-15) para os detalhes.

Se voce tem um notebook com GPU NVIDIA hibrida (Optimus/PRIME) e vai rodar o jogo manualmente sem passar
pelo `quickstart.sh`, lembre de exportar as duas variaveis do item 3 antes de `./RangeRuntime jogo.range`.

Nessa mesma maquina, no mesmo dia, o editor completo (`RangeEngine`, preset `linux-editor`) tambem foi
validado pela primeira vez em Linux real: compila, linka e roda (`--background` + `import bpy`) depois de
mais seis bugs corrigidos. Ver secao "Editor (RangeEngine)" abaixo para os detalhes.

O pacote portatil 0.3.0 tambem foi validado em maquina limpa em 2026-09-15, com Python 3.11 embutido em
`python311/`, `RUNPATH` relativo a `$ORIGIN/python311/lib`, assinatura SHA-256 e inclusao do codigo-fonte
correspondente. O estado publico atual e **Linux x86_64 validado para runtime portatil**; o editor Linux ainda
precisa de validacao de janela real antes de ser tratado como distribuicao final do editor.

## Atalho automatico (recomendado)

Para quem nao tem experiencia com Linux: um unico script cobre instalacao de dependencias
(via `apt`), checagem de ambiente, configuracao, compilacao e instalacao:

```bash
bash tools/linux/quickstart.sh
```

Para compilar e ja rodar um jogo `.range` ao final:

```bash
bash tools/linux/quickstart.sh /caminho/para/seu_jogo.range
```

O script assume Debian/Ubuntu (`apt`). Para outra distro, siga os passos manuais abaixo trocando
os comandos de instalacao de pacotes pelo gerenciador correspondente. Em caso de erro, cole a saida
completa do script para um assistente (Claude/ChatGPT) rodando na propria maquina Linux investigar.

## Estado em 8 de setembro de 2026

O `RangeRuntime` agora liga e roda no ambiente de referencia Debian 13 via WSL. Duas causas de link
quebrado sob `WITH_BLENDER=OFF` foram corrigidas:

1. Stubs de bad-level-call para simbolos exclusivos do editor estavam desabilitados (`#if 0`) sob a
   suposicao de que `WITH_BLENDER` sempre estaria ligado junto de `WITH_PLAYER`. Passaram a ser
   compilados condicionalmente com `#ifndef WITH_BLENDER`, e o alvo `bad_level_call_stubs` passou a
   receber a definicao `-DWITH_BLENDER` quando aplicavel
   (`source/blenderplayer/bad_level_call_stubs/CMakeLists.txt`).
2. O GNU ld resolve simbolos de bibliotecas estaticas em uma unica passada ordenada; a lista
   `BLENDER_SORTED_LIBS`, ajustada historicamente para o build completo (editor+player), deixava
   referencias nao resolvidas quando as bibliotecas de editor saem do grafo. A ligacao do
   `RangeRuntime` em Unix/nao-Apple agora usa `-Wl,--start-group ... --end-group`
   (`source/blenderplayer/CMakeLists.txt`).

Com essas correcoes, `RangeRuntime` compila, linka (exit 0) e roda: abre janela real via X11/WSLg, cria
contexto OpenGL 4.5 (Mesa/llvmpipe) e carrega um `.range` real, permanecendo em loop de jogo estavel por
varios minutos sem crash. Teste feito via WSLg, que usa renderizacao por software (llvmpipe) — ainda falta
validar em Linux nativo com GPU real, e testar audio/input a fundo. Portanto o binario existe e roda, mas
essa observacao ficou superada pela validacao nativa e pelo pacote 0.3.0 de 2026-09-15 descritos acima.

Teste com um jogo real (`RolimaRacer.range`) via WSLg apontou dois pontos:

- **Desempenho baixo**: esperado, ja que o WSLg usa renderizacao por software (Mesa/llvmpipe) em vez de
  um driver de GPU real. Nao e evidencia de regressao do engine; precisa ser reavaliado em Linux nativo
  com GPU.
- **Sem audio audivel**: o log do OpenAL (`ALSOFT_LOGLEVEL=3`) mostra inicializacao completa e saudavel —
  backend `pulse` conectado ao dispositivo virtual `RDP Sink` do WSLg, contexto e canais criados sem erro.
  Ou seja, a inicializacao de audio do engine no Linux esta correta; a ausencia de som ouvido e mais
  provavel de ser roteamento/mixer do WSLg (RDP Sink -> Windows) ou a cena testada nao disparando som
  naquele trecho, e nao uma falha do engine. Confirmado em um segundo teste (`ImGui_example.range`, sem
  audio) que o restante do runtime (janela, OpenGL, componentes Python/ImGui) funciona normalmente e so o
  audio fica mudo — reforca a hipotese de limitacao do WSLg, nao bug do engine. Precisa confirmacao em
  Linux nativo com saida de audio real.
- Tambem foi relatado um problema visual de alpha (nao investigado ainda; baixa prioridade frente aos
  itens acima).

Este roteiro prepara o **RangeRuntime** para Linux x86_64. A base CMake do projeto possui caminhos Unix/X11,
e a variante ja foi compilada, executada e empacotada em Linux real. As notas historicas abaixo permanecem
para explicar a evolucao do port.

## Escopo inicial

O preset `linux-runtime` compila somente o player, com OpenGL/X11, Python, SDL e OpenAL. FFmpeg, OpenImageIO,
OpenColorIO, Cycles, compositor e outros recursos ficam desligados nesta primeira etapa (o player nao precisa
deles). Isso preserva o Windows e reduz o primeiro problema de portabilidade a um alvo verificavel.

## Editor (RangeEngine) — preset `linux-editor`, validado em Linux real em 15 de setembro de 2026

O preset `linux-editor` (mesmo `source/CMakePresets.json`) builda o alvo `RangeEngine` com `WITH_BLENDER=ON`.
Primeira compilacao completa do editor fora do Windows, no mesmo notebook Ubuntu 24.04/NVIDIA Optimus usado na
validacao do `RangeRuntime`: **compila, linka e roda (`RangeEngine --background --python-expr "import bpy"`
confirma Python/bpy operacionais)** depois de seis bugs reais encontrados e corrigidos:

1. **FFmpeg: ponteiros `const` na API nova** — `avcodec_find_decoder`/`avcodec_find_encoder` e
   `AVFormatContext::oformat` passaram a devolver ponteiros `const` a partir do FFmpeg 5.0 (aqui:
   libavcodec60/FFmpeg 6.1 do Ubuntu 24.04); o wrapper `audaspace` ainda atribuia a ponteiros nao-`const`.
   Corrigido em `extern/audaspace/plugins/ffmpeg/FFMPEGReader.cpp` e `FFMPEGWriter.cpp` (o segundo tambem
   precisou de uma variavel local `AVCodecID` em vez de escrever direto em `outputFmt->audio_codec`, que
   agora e `const`).
2. **OpenColorIO: API v1 incompativel com OCIO 2.1+** — `intern/opencolorio/ocio_impl.cc`/`ocio_impl_glsl.cc`
   usam a API antiga da OpenColorIO (`getDisplayColorSpaceName`, `Processor::apply`/`applyRGB`/`applyRGBA`,
   `DisplayTransformRcPtr`), removida na 2.x; o Ubuntu 24.04 só tem `libopencolorio-dev` 2.1+. Portar
   exigiria reescrever dezenas de chamadas — fora do escopo desta validacao de build. **`WITH_OPENCOLORIO`
   desligado** para o preset `linux-editor` (`source/CMakePresets.json`).
3. **FFmpeg (export de video): API pre-3.1 removida** — `source/blender/blenkernel/intern/writeffmpeg.c` usa
   `AVStream::codec`, `avcodec_encode_video2`/`avcodec_encode_audio2`, `av_free_packet`, `avpicture_fill`,
   `AVFormatContext::filename`, todos removidos do FFmpeg ha varios anos. Mesmo caso do item 2 em escopo:
   **`WITH_CODEC_FFMPEG` desligado** para o preset `linux-editor`. Sem isso, o RangeEngine linux nao exporta
   video nem tem os codecs FFmpeg da libavformat/libavcodec do sistema; import/export de imagem estatica via
   OpenImageIO continua ligado normalmente.
4. **`strcmp` sem declaracao implicita** — `source/blender/editors/interface/interface_context_menu.c` usava
   `strcmp` (via `BLI_string.h`) sem incluir `<string.h>` diretamente; o gcc do Ubuntu 24.04 trata declaracao
   implicita de funcao como erro (`-Werror=implicit-function-declaration`). Corrigido com
   `#include <string.h>` no topo do arquivo.
5. **Link falhava por `-lge_player` ausente** — `source/gameengine/Launcher/CMakeLists.txt` linkava a
   biblioteca `ge_player` incondicionalmente, mas `source/gameengine/CMakeLists.txt` só adiciona o
   subdiretorio `GamePlayer` (que a gera) quando `WITH_PLAYER=ON`; o preset `linux-editor` usa
   `WITH_PLAYER=OFF` (é o editor, não o player). Corrigido guardando essa dependencia com
   `if(WITH_PLAYER)`.
6. **Link falhava por simbolos OpenImageIO indefinidos** (`TypeDesc::basesize()`, `ParamValue::clear_value()`)
   — o Ubuntu 24.04 divide a OpenImageIO em duas bibliotecas (`libOpenImageIO.so` e
   `libOpenImageIO_Util.so`), e esses simbolos vivem só na segunda; `FindOpenImageIO.cmake` so procurava e
   linkava a primeira. Corrigido adicionando a busca por `OpenImageIO_Util` e anexando-a a
   `OPENIMAGEIO_LIBRARIES` (`build_files/cmake/Modules/FindOpenImageIO.cmake`).
7. **Mesmo bug de RPATH do `RangeRuntime`** (`libpython3.11.so.1.0: cannot open shared object file`) —
   faltava no alvo `RangeEngine` a mesma correcao ja aplicada ao `RangeRuntime`
   (`source/blenderplayer/CMakeLists.txt`). Aplicada agora tambem em `source/creator/CMakeLists.txt`
   (`BUILD_RPATH`/`INSTALL_RPATH` = `${PYTHON_ROOT_DIR}/lib`, guardado por `UNIX AND NOT APPLE AND NOT
   EMSCRIPTEN AND PYTHON_ROOT_DIR`, mesmo racional documentado la).

Bug menor adicional, sem relacao com portabilidade Linux especificamente: o `install()` de
`release/datafiles/debugmode_configfile/imgui.ini` em `source/creator/CMakeLists.txt` era incondicional, mas
esse arquivo nunca existiu no repositorio (nao ha historico git dele). Guardado com `if(EXISTS ...)`, igual ao
padrao ja usado para outros datafiles opcionais nesse mesmo arquivo.

`WITH_*` do preset apos essa rodada:

- **Ligados**: `WITH_COMPOSITOR`, `WITH_OPENIMAGEIO` (import/export de imagem parada em nodes de
  material/textura e no editor de imagem).
- **Desligados**: `WITH_CYCLES`, `WITH_ALEMBIC`, `WITH_OPENVDB` (nao usados pelo RangeEngine, mesmo no
  Windows), `WITH_OPENCOLORIO` e `WITH_CODEC_FFMPEG` (API antiga incompativel com as versoes do Ubuntu
  24.04 — ver itens 2 e 3 acima; portar fica para uma rodada futura dedicada, nao bloqueia o editor abrir
  e rodar).

Atalho automatico (mesmo padrao do runtime, mas instala tambem as libs de FFmpeg/OIIO/OCIO — usadas so na
etapa de configuracao/preflight; as flags acima decidem o que de fato entra no binario):

```bash
bash tools/linux/quickstart-editor.sh
```

Manual:

```bash
cmake --preset linux-editor -S source
cmake --build build-linux-editor --target RangeEngine -j"$(nproc)"
cmake --install build-linux-editor
```

O executavel fica em `build-linux-editor/bin/RangeEngine`. Testado ate agora: compilacao completa, instalacao
portable e `RangeEngine --background --factory-startup --python-expr "import bpy; print(bpy.app.version_string)"`
(confirma Python/bpy operacionais e RPATH do Python isolado correto). **Ainda falta**: abrir a janela do
editor de verdade (interface grafica, icones, i18n, addons Python) numa sessao com display — o teste acima
rodou so em modo `--background`, sem GHOST/X11 nem contexto OpenGL da UI.

**i18n (2026-09-20, so validado no Windows)**: o preset agora liga `WITH_INTERNATIONAL` (locale vendorizado em
`source/release/datafiles/locale`, com pt_BR, pt, es e ru). Requer `libboost-locale-dev` (ja em `libboost-all-dev`). O
`msgfmt` e compilado junto, nao usa o gettext do sistema. Ao recompilar, conferir que
`build-linux-editor/bin/*/datafiles/locale/pt_BR/LC_MESSAGES/blender.mo` existe e rodar
`RangeEngine -b --python tools/tests/web_profile/engine_i18n.py`. O seletor na janela ainda precisa de teste.

O checkout atual contem apenas `lib/win64_vc15`; estas bibliotecas nao funcionam no Linux. O preset usa
as bibliotecas da distribuicao, sem alterar `build/` nem o preset Windows.

## Ambiente de referencia

Use uma instalacao Linux x86_64 com sessao grafica. A referencia inicial e Debian 13 x86_64 com o CPython 3.11
isolado em `/opt/anastacio-python311`, selecionado explicitamente pelo preset. WSLg pode ajudar a descobrir erros de configuracao, mas nao substitui
o teste de janela, audio, driver OpenGL e distribuicao em Linux nativo.

Instale as ferramentas e dependencias iniciais:

```bash
sudo apt update
sudo apt install build-essential cmake ninja-build git pkg-config \\
  libx11-dev libxi-dev libxinerama-dev libxxf86vm-dev libxfixes-dev \\
  libgl1-mesa-dev libglu1-mesa-dev libglew-dev \\
  libsdl2-dev libopenal-dev libsndfile1-dev \\
  libfreetype6-dev libpng-dev libjpeg-dev zlib1g-dev libtbb-dev \\
  libboost-all-dev libfftw3-dev
```

Se o CMake acusar outra biblioteca ausente, instale o pacote `-dev` correspondente e registre o nome e o
erro no changelog; nao habilite recursos extras antes de o runtime basico iniciar.

**Python 3.11 nao vem mais pelo apt em distros recentes** (confirmado em Ubuntu 24.04: so ha
`python3.12` nos repositorios). Como o preset exige o ABI 3.11 especificamente, compile-o isolado com:

```bash
bash tools/linux/install-python311.sh
```

O script instala as dependencias de build do CPython, baixa o codigo-fonte oficial e instala via
`make altinstall` em `/opt/anastacio-python311` (nao mexe no Python do sistema). E idempotente — rodar
de novo so reinstala se `FORCE=1` for passado. Se sua distro ja tiver `python3.11`/`python3.11-dev` pelo
apt (ex: Debian 13), o script continua funcionando do mesmo jeito, so que compilando a partir do fonte
em vez de usar o pacote do sistema, para garantir o mesmo layout em `/opt/anastacio-python311` esperado
pelo preset.

Antes de configurar, rode a verificacao sem alterar o sistema:

```bash
bash tools/linux/preflight.sh
```

O preset seleciona Python 3.11. Para a referencia desta maquina, execute a verificacao com
`PYTHON_EXECUTABLE=/opt/anastacio-python311/bin/python3.11 bash tools/linux/preflight.sh`.
O suporte a essa versao so sera considerado
real depois da configuracao, compilacao e execucao do runtime.

## WSL nesta maquina

O WSL2 e util para configurar e compilar, mas nao substitui a validacao final em Linux nativo. Nesta maquina,
o Ubuntu 26.04 oferece Python 3.14 e o Ubuntu 24.04 oferece Python 3.12. A distribuicao `Debian` instalada
via WSL e a referencia desta primeira compilacao, com Python 3.11 compilado separadamente para manter a ABI esperada pela engine.

## Configurar, compilar e instalar

No clone do repositorio:

```bash
cmake --preset linux-runtime -S source
cmake --build build-linux --target RangeRuntime -j"$(nproc)"
cmake --install build-linux
```

O pacote portatil e criado em `build-linux/bin/`. Nao compartilhe essa pasta com `build/` do Windows.
Para testar um jogo:

```bash
cd build-linux/bin
./RangeRuntime /caminho/para/jogo.range
```

Antes de reportar sucesso, confirme ao menos: abertura de janela, carregamento de um `.range`, renderizacao
OpenGL, entrada, audio, execucao de scripts Python e encerramento normal. Logs de CMake e do runtime devem
ser preservados para corrigir o primeiro erro real, em vez de adivinhar no Windows.

## Empacotamento futuro

**Importante — pacote completo precisa dos DOIS presets.** `linux-runtime` (WITH_PLAYER=ON,
WITH_BLENDER=OFF) so gera `RangeRuntime`; `linux-editor` (WITH_BLENDER=ON, WITH_PLAYER=OFF) so gera
`RangeEngine`. Empacotar so um dos dois `bin/` produz um `.tar.xz` faltando o outro executavel — foi
o que aconteceu no release 0.4.1 (Kitsuy reportou "no RangeRuntime, just the menu": o pacote saiu so
de `build-linux-editor/bin`). Compile e instale os dois antes de empacotar:

```bash
cmake --preset linux-runtime -S source && cmake --build build-linux --target RangeRuntime -j"$(nproc)" && cmake --install build-linux
cmake --preset linux-editor -S source && cmake --build build-linux-editor --target RangeEngine -j"$(nproc)" && cmake --install build-linux-editor
```

Depois de validar os dois runtimes, gere o arquivo distribuivel unico com ambos (`BIN_DIR` e o
principal, `EXTRA_BIN_DIR` completa o que faltar sem sobrescrever nada):

```bash
BIN_DIR=build-linux/bin EXTRA_BIN_DIR=build-linux-editor/bin bash tools/linux/package-runtime.sh <versao>
```

Ele cria `build-linux/dist/AnastacioEngine-<versao>-linux-x86_64.tar.xz`, o arquivo
`.tar.xz.sha256` e inclui `COPYING`. O script recusa empacotar se nenhum dos dois binarios tiver sido
instalado, e agora avisa (sem falhar) se o pacote final sair sem `RangeRuntime` ou sem `RangeEngine` —
confira que o aviso NAO aparece antes de publicar.

Distribua esse arquivo, seu checksum e o codigo-fonte correspondente. Antes de anunciar a release,
extraia o `.tar.xz` num diretorio limpo e confirme que **os dois** `./RangeEngine` e `./RangeRuntime`
existem e abrem — o pacote 0.3.0 e o 0.4.1 (so RangeEngine) ja mostraram que pular essa checagem deixa
bug passar.
