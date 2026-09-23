# Build no Windows

O projeto usa CMake + Ninja e gera a instalação atual em `build/bin/`. As regras anti-loop e de preservação
do workspace estão em [`../AGENTS.md`](../AGENTS.md) e prevalecem sobre notas históricas do changelog.

## Dependência externa: pasta `lib/`

A pasta `lib/` (bibliotecas pré-compiladas de terceiros — Python, OpenEXR, FFmpeg etc.) **não fica no Git**
(está no `.gitignore`, é grande demais para o repositório) e precisa ser baixada à parte via SVN antes de
configurar o CMake:

```bat
svn checkout https://svn.blender.org/svnroot/bf-blender/trunk/lib/win64_vc15 lib/win64_vc15
```

Rode esse comando na raiz do projeto (`D:\AnastacioEngine`), criando `lib/win64_vc15/`. Sem essa pasta, a
configuração do CMake falha por não encontrar as dependências.

Para build Linux, a pasta equivalente **não** é necessária — o preset Linux usa as bibliotecas da própria
distro via apt (ver [`docs/linux-build.md`](linux-build.md)).

## Ambiente obrigatório

Uma chamada direta de `ninja` em PowerShell ou `cmd` comum não herda `INCLUDE` e `LIB` do MSVC. Para
compilar um diretório já configurado, carregue `vcvars64.bat` e execute Ninja no mesmo processo:

```bat
cmd /c '"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cd /d D:\AnastacioEngine\build && ninja <target> 2>&1'
```

A mensagem de que `vswhere.exe` não foi reconhecido, quando emitida pelo próprio `vcvars64.bat`, é ruído
conhecido se o restante do ambiente for carregado corretamente.

`source/CMakePresets.json` também declara o toolset, SDK e variáveis de ambiente usados na configuração.
Isso não torna uma chamada posterior e isolada de `ninja` independente do Developer Shell.

## Configuração vigente

- CMake raiz: `source/CMakeLists.txt`.
- Preset: `v142-ninja`, build `Release`, Ninja e MSVC v142.
- `build/`: build principal/compatibility e instalação corrente em `build/bin/`.
- `build_core/`: build usado para validar o caminho core do runtime.
- `install/`: cópia manual potencialmente antiga; não usar para validação.

Opções relevantes incluem `WITH_PYTHON`, `WITH_BULLET` e `WITH_PLAYER`. O editor permanece em OpenGL
compatibility; `WITH_GL_PROFILE_CORE_RANGERUNTIME` cobre o caminho core específico do player.

## Alvos

- `ge_rasterizer`, `ge_rasterizer_opengl`: verificações rápidas do rasterizador.
- `ge_rasterizer_shaders`: reconstruir após editar `.glsl`; o alvo apenas incorpora o texto.
- `RangeEngine`: editor completo.
- `RangeRuntime`: player standalone, executado como `RangeRuntime.exe <arquivo.range>`.

Erros de sintaxe GLSL aparecem somente em runtime, via `glCompileShader`, normalmente como `CM_Error` ou
`CM_Warning` no console.

## Clean rebuild

Após editar `DNA_*.h`, execute `ninja -t clean` e reconstrua os executáveis completos. O build incremental
pode manter `dna.c` ou `dna_type_offsets.h` obsoletos e causar corrupção de heap ao carregar arquivos.

Se uma mudança em outro header provocar crash desproporcional ao diff após build incremental, faça um clean
rebuild antes de investigar o crash como defeito funcional. Não repita a mesma tentativa de build mais de
duas vezes sem mudar a causa identificada.

## Validação mínima

- Compile o menor alvo afetado e depois os executáveis que distribuem a mudança.
- Para rasterizador/shader, valide compatibility e core quando aplicável.
- Execute `RangeEngine.exe` e `RangeRuntime.exe` no fluxo afetado.
- Para comportamento visual, use o jogo real; screenshots automatizados não são evidência confiável neste
  projeto.
- Nunca declare uma mudança de código concluída apenas porque compilou.
