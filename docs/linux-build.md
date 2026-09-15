# Build no Linux (em preparacao)

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
o pacote/distribuicao ainda nao foram validados.

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
mas esta variante ainda nao foi compilada nem executada em Linux real. Portanto, o resultado e uma build
experimental, nao uma versao oficial distribuivel.

## Escopo inicial

O preset `linux-runtime` compila somente o player, com OpenGL/X11, Python, SDL e OpenAL. O codec FFmpeg fica
desligado temporariamente: a base atual usa APIs removidas no FFmpeg 7 e precisa de uma migracao propria antes
de habilitar video. Editor, Cycles, compositor e outros recursos que trazem dependencias pesadas tambem ficam
desligados nesta primeira etapa. Isso
preserva o Windows e reduz o primeiro problema de portabilidade a um alvo verificavel.

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

Depois de validar o runtime, gere o arquivo distribuivel com:

```bash
bash tools/linux/package-runtime.sh <versao>
```

Ele cria `build-linux/dist/AnastacioEngine-<versao>-linux-x86_64.tar.xz`, o arquivo
`.tar.xz.sha256` e inclui `COPYING`. O script recusa empacotar se `RangeRuntime` ainda nao tiver sido
instalado em `build-linux/bin/`.

Distribua esse arquivo, seu checksum e o codigo-fonte correspondente.
Somente anuncie suporte oficial apos validar o pacote extraido em uma maquina Linux limpa. O estado publico
ate la e **"Linux x86_64: experimental, sem build oficial"**.
