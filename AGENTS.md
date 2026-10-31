# Instruções para agentes de código (Codex e outros) neste repo

> **Nomes dos builds:** veja [docs/build-dirs.md](docs/build-dirs.md). "Android" = APK WebView sobre `build-web-release`. O `build-android/` guarda só os APKs gerados por `tools/web/package-android.py`; a rota nativa (NDK) foi abandonada.

## Regra anti-loop: não repita a mesma tentativa que falhou

Antes de rodar QUALQUER comando de build/compilação, confira mentalmente este checklist — a maioria dos
"travamentos" em sessões anteriores foi tentar a mesma coisa repetidamente sem mudar a causa raiz:

1. **O comando está passando pelo `vcvars64.bat`?** Se não, é isso — vá para a seção "Ambiente de build" abaixo, não tente de novo do mesmo jeito.
2. **Se o erro já apareceu 2x seguidas de forma idêntica**, pare de repetir o mesmo comando. Leia a mensagem
   de erro completa, identifique a causa (headers ausentes → ambiente; símbolo indefinido → build incremental
   obsoleto; etc.) e mude de estratégia — não rode o comando pela 3ª vez esperando resultado diferente.
3. **Se depois de aplicar o fix conhecido (vcvars64, `ninja -t clean`) o erro persistir de forma diferente**,
   isso é sinal de um problema novo, não do mesmo problema de ambiente — pare e relate ao usuário o erro exato
   em vez de tentar variações às cegas (mudar flags, tentar outro shell, etc.) por conta própria.
4. **Nunca marque uma tarefa como concluída sem build/execução bem-sucedidos.** Se o ambiente não permitir
   compilar (ex: vcvars64.bat não encontrado nesta máquina), diga isso explicitamente ao usuário como bloqueio
   de ambiente — não como "funcionalidade implementada, só falta compilar".
5. **Limite de tentativas**: depois de 2 tentativas falhas de resolver o mesmo erro de build sozinho, pare e
   peça orientação ao usuário em vez de continuar tentando variações. É preferível parar e perguntar do que
   gastar o orçamento da sessão em tentativa-e-erro.

## Ambiente de build (LEIA ANTES DE COMPILAR)

Um shell puro (cmd, PowerShell comum, git-bash) **não consegue compilar este repo**. `cl.exe` até roda, mas falha com erros como:
```
fatal error C1083: Cannot open include file: 'stdio.h'
fatal error C1083: Cannot open include file: 'string.h'
fatal error C1083: 'vector': No such file or directory
```
Isso não é um erro no código alterado — é porque as variáveis de ambiente `INCLUDE`/`LIB` do MSVC/Windows SDK
não estão carregadas. O build é CMake+Ninja (`build/build.ninja`), não a `.slnx`/MSBuild, então (ao contrário
de abrir a solution no Visual Studio) precisa que o ambiente do "VS Developer Shell" seja configurado
manualmente antes de chamar o Ninja.

**Como compilar corretamente**: rode o `vcvars64.bat` e o `ninja` na MESMA chamada de processo (variáveis de um `.bat` não sobrevivem entre chamadas de shell separadas):
```
cmd /c 'set VSLANG=1033&& "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cd /d D:\AnastacioEngine\build && ninja <target> 2>&1'
```
- A linha `'vswhere.exe' não é reconhecido...` que aparece no começo da saída é ruído inofensivo do próprio `vcvars64.bat`, não é erro.
- Alvos úteis para checagens rápidas (não os produtos completos): `ge_rasterizer`, `ge_rasterizer_opengl`,
  `ge_rasterizer_shaders` (reconstrua este após editar qualquer `.glsl` de filtro — `datatoc` regenera um `.c`
  a partir do texto do shader).
- Alvos completos: `RangeEngine` (editor) e `RangeRuntime` (player standalone, aceita um `.range` como primeiro argumento).
  Saída Windows em `build/bin/`: `AnastacioEngine.exe` e `AnastacioRuntime.exe`.
- Erros de sintaxe GLSL NÃO são pegos por este build em C++ (datatoc só embute o texto cru) — só aparecem em runtime via `glCompileShader`, logado como `CM_Error`/`CM_Warning` no stdout/console.

### Gotcha crítico: mudanças em headers podem exigir rebuild limpo

O build incremental do Ninja aqui às vezes não rastreia corretamente dependências de headers:
- **Editar qualquer `DNA_*.h`** (novo campo de struct etc.) nunca dispara a regeneração de
  `dna.c`/`dna_type_offsets.h` num `ninja <target>` incremental. Sintoma: crash `STATUS_HEAP_CORRUPTION`
  (`0xc0000374`) ao carregar arquivo, ou timing/comportamento não-determinístico, que parece não ter relação
  com a mudança.
- Mesmo headers "normais" (não-DNA) já causaram `EXCEPTION_ACCESS_VIOLATION` no load da cena após rebuild incremental.
- **Causa identificada (2026-09-25):** em `build/CMakeFiles/rules.ninja` o `msvc_deps_prefix` é `Observação: incluindo arquivo:` (MSVC em português). A frase sai do compilador em outra codificação e não bate com o prefixo, então o Ninja **não registra nenhuma dependência de header**: mudar um `.h` só recompila os `.cpp` que você também editou. Ex.: um membro novo em `KX_GameObject.h` deixou `KX_ShadowRenderer.obj` com o layout antigo e o play fechava a engine. Contorno: apagar os `.obj` da área afetada (ex.: `build/source/gameengine/**/*.obj`) ou `ninja -t clean`. **Corrigido em 2026-09-28:** pacote de idioma inglês instalado no Visual Studio e `build/` reconfigurado com `VSLANG=1033` (prefixo agora `Note: including file:`). **Todo build precisa do `set VSLANG=1033&&`** do comando abaixo; sem ele o `cl` volta a responder em português e o Ninja para de registrar dependências de novo.

**Regra**: depois de editar QUALQUER header (`.h`), se aparecer um crash estranho/desproporcional ao diff após
build incremental, não gaste tempo debugando como se fosse bug de código — vá direto para:
```
ninja -t clean
```
seguido de rebuild completo do(s) alvo(s). Um clean rebuild completo de `RangeEngine`+`RangeRuntime` (~2900 passos) leva uns 45-50 minutos.

### Local de instalação real

`build/bin/` é sempre a instalação atualizada (`CMAKE_INSTALL_PREFIX` = `build/bin/${BUILD_TYPE}`,
`ninja install` atualiza). Uma pasta `install/` na raiz do repo pode ser uma cópia manual antiga — não confiar
nela, sempre testar a partir de `build/bin/`.

Para alterações nos scripts Python da UI em `source/release/scripts/`, sincronizar também os arquivos
correspondentes em `build/bin/2.79/scripts/` antes de testar o editor. O executável em uso carrega os scripts
dessa instalação; atualizar somente o código-fonte não altera a UI já instalada.

## Workflow do projeto

Este é um fork em C++ da Range Engine 1.6 Rev1 (derivado de UPBGE 0.2.5b / Blender 2.79), com duas frentes de
trabalho: **Performance** e **Iluminação/Gráficos**. Use `docs/README.md` como índice e confira estas fontes
antes de começar:
- **Nome do projeto:** o nome visível é "Anastacio Engine (fork of Range Engine)". Textos que o usuário vê
  (título, splash, About, instalador, docs) usam "Anastacio Engine"; coisas novas (módulos, addons, classes)
  usam o prefixo `anastacio`/`Anastacio`. Identificadores herdados ficam como estão para não quebrar
  compatibilidade: formato `.range`, `import Range`, `bge`, pasta de config `%APPDATA%\RangeEngine\`, ProgIDs
  `RangeEngine.*` no registro, alvos CMake `RangeEngine`/`RangeRuntime` e o arquivo `RangeEngine.desktop`.
  Migração Windows aprovada em 2026-10-08: os alvos `RangeEngine` e `RangeRuntime` produzem
  `AnastacioEngine.exe` e `AnastacioRuntime.exe`. Linux, Web/Android e identificadores de
  compatibilidade mantêm os nomes anteriores; projetos antigos aceitam os dois nomes do player Windows.
  Não renomeie esses sem plano de migração aprovado. Links da comunidade Range Engine (site, Discord) são
  créditos ao projeto original e ficam.
- `docs/roadmap.md` — somente trabalho aberto e validações pendentes.
- `relatorio-melhorias-anastacioengine.md` — capacidades existentes e decisões técnicas vigentes.
- `docs/changelog.md` — log datado e detalhado do que foi feito em cada sessão (diagnóstico, mudanças de
  código, resultados de benchmark, regressões). Contém o índice e as entradas recentes; o histórico antigo
  está em `docs/changelog-arquivo.md`. Não leia o histórico inteiro: use
  `grep -rn "^## .*termo" docs/changelog.md docs/changelog-arquivo.md`. Novas entradas vão no topo de
  `docs/changelog.md`.
- `docs/code-map-*.md` — mapas de navegação dos arquivos grandes (onde fica cada domínio), para não ler o arquivo inteiro: `code-map-gameengine.md` (KX_Scene, KX_PythonInit, física, conversão, KetsjiEngine, RenderPipeline, BL_Converter), `code-map-view3d-draw.md` (viewport 3D), `code-map-kx-gameobject.md` e `code-map-gpu.md` (gpu_material.c, gpu_shader_material.glsl, receitas de nó de shader, uniform de mundo e sombra), `code-map-logic-window.md` (editor de Logic Bricks) e `code-map-rna-object.md` (RNA do objeto). Antes de abrir um desses arquivos, leia o mapa. Arquivo muito editado com mais de ~3 mil linhas e sem mapa: crie um no mesmo formato e registre em `CODE_MAPS` do `tools/check_docs.py`. Depois de mudar código ou docs, `python tools/check_docs.py` diz se algum link, referência `arquivo:linha` ou linha dos mapas envelheceu (`--fix` corrige os mapas).
- CI no GitHub (`.github/workflows/`): `checks.yml` roda `check_docs`, `check_ui_icons` e o selftest do detector em todo push; `linux-build.yml` compila editor e player no Ubuntu 22.04 e roda `ctest` quando muda `source/`. Depois do push, confira com `gh run list`; não dê a tarefa por concluída com CI vermelho sem avisar o usuário.
- Antes de publicar release no Windows, rode `tools\pre_release.bat` (compila, instala, checks, smoke `--server` do player e `ctest`; para no primeiro erro).
- Onde pôr arquivos novos: cenas de teste em `tools/debug/cenas/`, evidências (prints, logs) em `artifacts/` (ignorado pelo git), documentação em `docs/`.

Antes de propor "vamos implementar X", confira o roadmap e o relatório; consulte no changelog apenas o
histórico relevante. Depois de implementar, atualize o estado vigente e acrescente o registro histórico sem
duplicar textos longos entre os arquivos.

Para mudanças grandes/arriscadas em C++, planeje antes de implementar, e prefira escrever/verificar uma peça
pequena e autocontida por vez, parando para o usuário confirmar antes de escrever a próxima peça — não
empacotar várias peças novas de infraestrutura numa única sequência sem pausa, a menos que o usuário peça
explicitamente para prosseguir autonomamente.

## Modelo de código local (Ollama)

Este repo tem um modelo de código rodando localmente via Ollama (`qwen2.5-coder:14b`), acessível por
`tools/ask_local.sh "prompt" < arquivo`. Use-o para grunt work antes de gastar contexto lendo tudo direto:
resumir arquivo grande, primeira varredura num sistema desconhecido do engine, boilerplate repetitivo. Não use
para mudanças reais de código/arquitetura — isso continua sendo trabalho do agente principal (Claude ou
Codex), não do modelo local.

Antes deles, use `docs/local-knowledge/index-<área>.md`: índice mecânico (arquivo, linhas, classes) gerado por
`python tools/build_code_index.py`, sem LLM e sem alucinação. Para arquivos grandes, veja `docs/code-map-*.md`.

## Outras regras práticas

- **Busque antes de construir**: antes de gastar esforço numa ferramenta externa ou infraestrutura nova para
  resolver um problema (ex: profiling de GPU), procure primeiro no próprio código por algo que já faça isso
  (classes de query, flags de feature, migrações parecidas já registradas no changelog).
- **Trabalho repetido por frame**: toda marca de mudança (`m_modified`, `m_dirty`, `NotifyUpdate`...) só liga
  dentro do ramo que detectou a mudança; laço por frame sobre todos os objetos precisa de uma lista só dos que
  mudam ou de uma checagem barata antes. Depois de mexer em atualização/culling/transform, rodar
  `python tools/check_trabalho_repetido.py` (e `--selftest`) e o detector numa cena parada
  ([docs/auditoria-trabalho-repetido.md](docs/auditoria-trabalho-repetido.md)): parado, os contadores devem ficar ~0.
- **Cascata de propriedade nova**: campo novo de física, logic brick ou atributo Python do jogo precisa
  aparecer em DNA, versioning, painel/FlowMenu, conversor, `logic_to_python.py`, `range_logic_tree.py`,
  traduções, changelog e inventário da API. Antes do commit, rodar `python tools/check_cascata.py`
  (diff desde `HEAD~1` + local; `HEAD~N` para mais; `--prop id` para um só; `--selftest`). FALTA é obrigatório.
  Ele também roda o `check_docs` no final (`--no-docs` pula).
- **Teste visual no jogo real, não em screenshot automatizado**: para bugs de renderização/visuais, captura
  automatizada de tela via câmera scriptada (`RangeRuntime.exe` headless + `--background` + `PrintWindow`) é
  pouco confiável aqui e já produziu resultados enganosos. Prefira pedir para o usuário testar no jogo real
  dele e descrever/enviar print. Testes automatizados sem componente visual (logs de compilação, dumps de
  `-d gpu`, dumps de dados via `bpy`) continuam confiáveis.
- **Antes de empacotar/publicar um release Windows, leia `docs/distribution-0.1.md` inteiro** (não confie em
  resumo de sessão anterior nem em memória compactada para isso). O erro "Falha na inicialização do aplicativo
  devido à configuração lado a lado incorreta" é causado por faltar a **subpasta `blender.crt/`** (com
  `blender.crt.manifest` + DLLs) ao lado do `.exe` — copiar só os DLLs soltos (`concrt140.dll`,
  `msvcp140*.dll`, `vcruntime140*.dll`, `vccorlib140.dll`) sem essa subpasta reproduz o mesmo erro. Sempre
  valide extraindo o ZIP de fato (não rodando de `build/bin/`) e rodando `AnastacioEngine.exe`/`AnastacioRuntime.exe`
  antes de subir para o GitHub; se falhar, o Log de Eventos do Windows
  (`Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='SideBySide'}`) diz exatamente qual
  assembly está faltando — mais rápido e confiável que `sxstrace.exe`, que exige elevação de admin.
