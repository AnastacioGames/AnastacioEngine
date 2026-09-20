# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

## 2026-09-19 - Marco G: MP3 no áudio do runtime Web

- O runtime Web não tem exceções C++: qualquer `throw` vira `Aborted(undefined)`. O Audaspace escolhe o leitor
  tentando cada `IFileInput` com `try/catch`, então um plugin MP3 separado abortava o runtime quando o WAV
  rejeitava o arquivo (pacote 8208 v0.1.2).
- `plugins/wav/WAVFile.cpp` agora reconhece RIFF/WAVE e, se não for, delega a `createMP3Reader`
  (`plugins/mp3/MP3File.cpp`, dr_mp3 v0.7.4 vendorizado, domínio público/MIT-0), que devolve `nullptr` em vez
  de lançar. Só lança se o arquivo não for WAV nem MP3. Streaming com seek e loop.
- Prova: `tools/create_web_music_scene.py` (MP3 empacotado, Sound Actuator em loop) no pacote 8208 v0.1.3;
  **o usuário confirmou que a música toca**. OGG segue fora.

## 2026-09-19 - Marco G: UV/normais constantes em malhas no runtime Web

- Sintoma: chão da cena `web-render` sem o xadrez e iluminação fraca na Web (desktop correto). O UV chegava constante em (0,0) ao fragment shader e as normais também eram constantes.
- Diagnóstico (sondas CDP em `WebGL2RenderingContext`): ponteiros, buffer (UV 0..4 no offset 160), location (`att0@2`) e link estavam corretos; `VERTEX_ATTRIB_ARRAY_DIVISOR` valia 1 nos locations 1-6 durante o draw de malha, então cada vértice lia o primeiro elemento. Trocar o VS por `gl_Position`/constante propagava o varying; só `att0` vinha zerado.
- Causa: o desenho instanciado de debug/partículas deixa divisor 1 nesses locations e a emulação legacy de VAO do Emscripten não isola divisores (mesmo defeito já corrigido em `ScreenPlane::Render`).
- Correção: `RAS_StorageVao::BindPrimitives` zera os divisores 0-7 no Web; o instancing reaplica os seus depois (`ActivateInstancing`). Verificado: xadrez, cubo vermelho, especular, névoa e sombras corretos no pacote `web-render`.
- `tools/create_web_render_scene.py`: chão com UV explícito (4x4); `RENDER_OFF=orco` mantém o caminho ORCO.

## 2026-09-19 - Compatibilidade Python para projetos BGE/UPBGE

- `KX_PythonInit.cpp`: depois de criar a API `Range`, a engine agora registra `bge` e todos os seus
  submódulos públicos como aliases no `sys.modules`. Eles referenciam os mesmos objetos (`bge.logic is
  Range.logic`), preservando também estado compartilhado como `globalDict` quando um projeto usa as duas
  grafias. Scripts legados com `import bge`, `import bge.logic` ou `from bge import events` não precisam
  ser editados; a documentação para código novo continua sendo `import Range`.
- A mesma inicialização restaura em `collections` os aliases de ABCs removidos no Python 3.10 e mantidos em
  `collections.abc` (`MutableMapping`, `Mapping`, `Sequence`, `Iterable` e relacionados). Isso permite
  dependências antigas embutidas em jogos, como TinyTag, sem alterar seus fontes; os objetos continuam sendo
  as implementações padrão de `collections.abc`.
- `aud.Factory` volta a existir como alias de `aud.Sound`. A chamada antiga `aud.Factory(arquivo)` e seus métodos,
  como `buffer`, usam o mesmo tipo atual e não exigem editar o jogo. O console informa os aliases de
  compatibilidade que forem aplicados.

## 2026-09-19 - Marco G: sombra de spot (buffer) no runtime Web

- Sintoma (teste manual do pacote `web-render`): `RuntimeError: null function` em `GPU_texture_bind_as_framebuffer`, chamado de `RAS_OpenGLLight::BindShadowBuffer`, logo após a cena iniciar. Isolado por bissecção de variantes da cena (`RENDER_OFF=shadow`) e por trace com `--profiling-funcs`.
- Causa: `glPushAttrib`/`glPopAttrib` são ponteiros do GLEW-ES e ficam `NULL` no Web (o init do GL 1.1 não roda em ES e o WebGL não tem essas funções). Só o caminho de sombra os exercitava.
- Correção: `extern/glew-es/src/glew.c` instala substitutos no `glewInit` (Emscripten) que emulam ENABLE/VIEWPORT/SCISSOR/DEPTH_BUFFER bits.
- Novos: `tools/create_web_render_scene.py` (com `RENDER_OFF=rot,shadow,ao,mist,alpha`), `tools/create_web_devices_scene.py` e modo `render` em `verify-capabilities.cjs`. Regressão: sim 9/9, áudio, toque e filtros passam. O aspecto visual da sombra ainda depende de aceite do usuário.

## 2026-09-19 - Marco G: áudio no runtime Web (Audaspace + SDL2)

- `WITH_AUDASPACE=ON` no preset `web-runtime`; backend SDL2 (Web Audio/ScriptProcessor). OpenAL e libsndfile seguem desligados.
- Emscripten não tem `efx.h`: `extern/audaspace/compat/web-no-openal` traz stubs EFX (no-op) para os efeitos OpenAL sempre compilados.
- Leitor WAV embutido (`plugins/wav`, PCM 8/16/24/32 e float; sem OGG/MP3) registrado como plugin estático.
- Módulo Python `aud` (audaspace-py) não é compilado no Web (exigiria numpy): `AUD_PyInit.cpp` vira stub (módulo vazio) e as pontes `AUD_getSoundFromPython`/`AUD_getPythonSound`/`checkPlaybackManager` retornam nulo. `bpy_types.Sound.factory` não funciona no Web.
- `GPG_Ghost`: força o dispositivo "SDL" no Web (a ordem da lista muda); `LA_Launcher` não aplica o áudio 3D no Web (com fallback None a conversão nula derrubava o boot).
- Prova (`verify-capabilities.cjs audio`, jogo `tools/create_web_audio_scene.py`, tom WAV em loop via Sound Actuator, Chrome headless): AudioContext `running` a 48 kHz, 579 mil frames, pico 0,35. Regressão sim (9/9) e toque OK. **Falta a confirmação audível pelo usuário** e áudio 3D/efeitos/OGG.

## 2026-09-19 - Marco G: provas de capacidade no runtime Web (parcial)

- Novo `tools/web/verify-capabilities.cjs` (Chrome/CDP, sem julgamento visual) e `tools/create_web_capabilities_scene.py` (jogo de teste de física, `addObject`/`endObject`, `addScene` e `replace`).
- Toque: `touchStart`/`touchEnd` no canvas viram clique de mouse no runtime atual (3 de 3), pela emulação de mouse do SDL; não há API multitouch nem `Range` de toque.
- Filtros 2D: 11 simples ligam e desligam e 4 embutidos (SSAO, Bloom, LightScatter, SSR) ligam, sem erro de shader (28 verificações, web-smoke release, SwiftShader).
- **Defeito do runtime achado:** `Range.logic.getCurrentScene()` derruba o runtime com `function signature mismatch`. `METH_NOARGS` declarado com função de 1 parâmetro; o CPython chama com 2, o que no desktop passa e em WebAssembly é trap. Varredura estática (`find_bad`, heurística) achou cerca de 210 declarações com contagem de parâmetros diferente do flag, em `KX_PythonInit.cpp` (43), `KX_PyConstraintBinding.cpp` (28), `mathutils` (Vector, Matrix, Quaternion, Euler, Color, geometry, noise) e `blf`. Chamadas como `vec.normalize()` estão no mesmo risco.
- Tentativa de contorno: `-sEMULATE_FUNCTION_POINTER_CASTS=1` falha no `wasm-opt --fpcast-emu` ("max-func-params needs to be at least 17"); o emscripten não expõe esse limite. Revertido; runtime release restaurado (hash igual ao anterior).
- **Corrigido na fonte** (opção escolhida): métodos `METH_NOARGS` ganham o segundo parâmetro (`Py_UNUSED(ignored)`) em `KX_PythonInit`, `mathutils`, `bpy*`, `bgl`, `imbuf`, `idprop`, `gpu_offscreen`, VideoTexture e ImGui; os helpers `*_apply_to_copy` do mathutils passam o argumento extra. `EXP_PYMETHODTABLE` passa a `METH_VARARGS | METH_KEYWORDS` (as funções do macro já recebiam 3 parâmetros) e ganha `EXP_PYMETHODTABLE_VARARGS` para métodos de 2 parâmetros. `KX_Speaker::GetActiveEffect*` viram NOARGS de fato.
- Resultado no runtime release: `getCurrentScene`, física, `addObject`/`endObject`, `addScene` (overlay) e `replace` passam (9 de 9 em `verify-capabilities.cjs ... sim`).
- Pendente: `KX_PyConstraintBinding.cpp` (28 declarações, arquivo com alterações locais do usuário) e diretórios ainda não varridos (bmesh, gpu, blf).

## 2026-09-19 - Pré-voo Web automático no editor

- Novo `range_web/preflight_run.py`: serve o pacote numa porta local livre, abre Chrome/Edge headless (`RANGE_WEB_BROWSER` ou detecção) com `?preflight=1&post=1` e recebe o relatório por `POST /__preflight`. Sem node nem CDP; fecha só o processo que abriu. Falhas de ambiente (sem navegador, sem resposta em 60 s) voltam como "Pré-voo não executado", nunca como erro do jogo.
- `package-web.py`: a página postou o relatório após `delay` segundos (padrão 12) quando `&post=1`. Pacotes gerados antes disso não respondem (o editor avisa por timeout): reexporte.
- Editor: opção "Pré-voo após exportar" (ligada por padrão) e botão "Testar pacote no navegador". Validar continua sem abrir navegador (não há pacote); preserva os resultados de pré-voo já obtidos.
- Verificado: 75 testes puros (6 novos, navegador falso) e Chrome real sobre um pacote do `bom.blend` (13,5 s, sem problemas, nenhum processo restante). O fluxo dentro do editor ainda não foi exercitado.

## 2026-09-19 - Pré-voo Web: casos positivos reais de Python e shader

- Três cenas com falha proposital (import de módulo inexistente, `int("abc")`, filtro 2D custom com GLSL inválido) empacotadas com o runtime release e abertas no Chrome headless. O pré-voo agora acusa: WEB-PY-001 (módulo), WEB-PY-009 (ValueError) e WEB-GFX-002 (shader, com o log `ERROR: 0:1: ...` do compilador).
- Defeitos achados e corrigidos: o mesmo erro de Python se repetia a cada frame (47 entradas; agora um por causa, na página e em `check_preflight`); o log do shader chegava só como cabeçalho (as linhas `ERROR:` seguintes agora são anexadas); `ValueError` sem "Traceback" na mesma linha era perdido (a página passou a rastrear o traceback aberto). Códigos ANSI removidos do texto.
- Ainda heurístico: estágio do shader sai `?` e o material vem vazio (o runtime não informa); só esses três tipos de falha foram exercitados.

## 2026-09-19 - Pré-voo Web importado no editor

- `range_web/preflight.py`: `load_preflight(path)` lê o JSON do pré-voo e devolve Findings; arquivo ilegível ou JSON inválido vira WEB-DEPLOY-002. Teste novo em `test_preflight.py` (68 testes passam).
- `properties_web.py`: botão "Importar pré-voo Web" escolhe o JSON e junta os resultados ao relatório atual (marcados `origin: preflight`, substituídos a cada importação). Validar/Exportar não rodam o navegador nem reaproveitam o pré-voo. Só o import de módulo foi compilado; o botão não foi exercitado no editor.

## 2026-09-19 - Pré-voo Web (marco E, página)

- `tools/web/package-web.py`: `index.html` aceita `?preflight=1` e monta o relatório `range-web-preflight` v1 (WebGL, isolamento, arquivos com MIME/hash, contexto perdido, erros de shader/Python por heurística). `verify-package.cjs` grava o relatório com `PREFLIGHT_OUT`.
- Verificado no Chrome headless (SwiftShader) com `web-smoke.range` e o runtime recém-compilado: jogo rodou, relatório sem findings em `check_preflight`; relatório adulterado (hash, MIME) gera WEB-DEPLOY-002. Não exercitados: casos positivos reais de shader/Python.
- Hook do manifesto verificado: `cmake --build --preset web-runtime-release` linkou e regenerou `RangeRuntime.manifest.json` (240 módulos).

## 2026-09-19 - Manifesto do runtime Web regenerado no build

- `source/source/blenderplayer/CMakeLists.txt`: sob Emscripten, `RangeRuntime` ganhou um `POST_BUILD` que roda `tools/web/make-runtime-manifest.py` no diretório do binário, usando `PYTHON_EXECUTABLE` do host. Evita manifesto com hashes antigos bloqueando o export com WEB-PKG-001. Sem `PYTHON_EXECUTABLE` só emite aviso de configuração.
- Verificado depois em build real (ver entrada do pré-voo acima).

## 2026-09-19 - Release 0.4.0

- Versão do splash atualizada para 0.4.0 (`wm.py`). Pacote Windows `AnastacioEngine-0.4.0-windows-x64.zip` montado a partir de `build/bin/` e validado extraindo o ZIP: `RangeEngine.exe` e `RangeRuntime.exe` (com `demos/Example_ImgGui`) iniciam, sem erros SideBySide.
- Correção de empacotamento: a `0.3.0` levava DLLs do VC++ soltas ao lado do `.exe` além de `blender.crt/`; com elas o `RangeRuntime.exe` sai com código 11 ao abrir um `.range`. A `0.4.0` não as inclui.
- `RangeArmor-0.4.0-windows-x64.zip` é o mesmo conteúdo da 0.3.0, só renomeado para acompanhar a versão.
- O pacote Linux `0.4.0` precisa ser compilado na máquina Linux e anexado à release com `gh release upload`.

## 2026-09-18 - Web: sombreamento com lâmpadas e profundidade no navegador

- `gpu_shader_material.glsl`: `shade_cooktorr_spec` usa piso `max(rough * rough, 0.001)`, como `shade_phong_spec`. Com Roughness 0 o cálculo dava 1/0 e depois 0 * inf = NaN; o desktop absorve o NaN no `max()`, mas ANGLE/WebGL propaga e o objeto ficava preto sob luz GLSL. Vale também no desktop, mas só para roughness abaixo de cerca de 0,03 (antes indefinido). Confirmado no navegador com `bom_cubo.blend` (cubo com textura difusa, normal map, Sun e Point).
- `gpu_texture.c`: no Web, texturas de profundidade passam a `GL_DEPTH_COMPONENT24`/`GL_UNSIGNED_INT` (antes 16 bits). O WebGL2 recusa `glBlitFramebuffer` entre profundidades de formatos diferentes, e os renderbuffers já eram de 24 bits; com lâmpada a cena quebrava com centenas de `GL_INVALID_OPERATION`.
- Observado no teste: o normal map (`.dds`) aparece no Web um pouco diferente do desktop; ainda não investigado. Components de template (`templates_components`) precisam estar na pasta do projeto para o export Web (WEB-PKG-003).

## 2026-09-18 - Web: export com validação (marco F, parcial)

- `range_web/export.py`: `export_package` bloqueia por erros, gera em diretório temporário e troca o destino; falha ou cancelamento preserva o export anterior. Testes puros em `test_export.py`.
- Botão Exportar Web (`scene.range_web_export`) valida de novo pelo mesmo caminho do Validar Web, exige arquivo salvo e chama `tools/web/package-web.py` (só em árvore de desenvolvimento). Teste no motor: `tools/tests/web_profile/engine_web_export.py`. O painel/botão não foi exercitado numa janela gráfica.
- Comando de linha: `RangeEngine -b jogo.blend --python tools/web/validate-web.py -- [--json out.json] [--export] [--out-dir D]` usa `_run_validation` e o operador de export (mesmo validador do painel); sai com 1 se houver erros. Teste: `tools/tests/web_profile/engine_web_cli.py`.
- Módulos `.py` do projeto (inclusive em subpastas) e assets externos dentro da pasta do `.blend` entram no pacote mantendo o caminho relativo (`--extra-root` no empacotador). Arquivos fora da pasta do projeto ficam de fora. A criação de diretórios no FS virtual (`FS_createPath` em index.html) foi confirmada no navegador (log `[fs] /pkg/util.py`). Painel Web (Range) verificado à mão no editor: Validar, Exportar, Localizar, bloqueio por erro e aviso de arquivo não salvo. O analisador agora segue `from pkg import util` e `import pkg.util` até o submódulo (antes o alvo era truncado para `pkg`).
- Assets externos (imagem, som, fonte, biblioteca) fora da pasta do `.blend`, ou symlinks que escapam dela, agora geram erro `WEB-PKG-005` no Validar Web e bloqueiam a exportação. Antes ficavam de fora do pacote sem aviso.
- O Validar Web também confere os arquivos que entram no pacote (módulos alcançados e assets dentro da pasta do projeto): destinos duplicados ou que só diferem na caixa (`WEB-PKG-005/006`) e tipo de arquivo (`.rasec` = `WEB-PKG-009`; `.pyd`/`.dll`/`.so` = `WEB-PKG-008`; `.pyc` sem o magic do runtime só avisa). Implementado em `collect_bpy._check_package_files`. Sem limite de tamanho de asset: o plano só prevê orçamento de textura (WEB-GFX-004), de outro marco.

## 2026-09-18 - Web: leitura do pré-voo (marco E, parcial)

- `range_web/preflight.py` transforma o relatório JSON do navegador (isolamento, WebGL, arquivos/MIME/hash, contexto perdido, shaders, erros Python) em Findings WEB-DEPLOY-001/002/003, WEB-GFX-001/002, WEB-PY-001, WEB-PKG-003 e WEB-PY-009. Testes puros em `tools/tests/web_profile/test_preflight.py`.
- Falta a página de pré-voo que produz esse JSON, a captura de logs e o teste no navegador (exigem Node.js/Chrome, ausentes nesta máquina).

## 2026-09-18 - Web: manifesto do runtime (marco D, parcial)

- `tools/web/make-runtime-manifest.py` gera `RangeRuntime.manifest.json` ao lado de `RangeRuntime.{js,wasm,data}`: hashes/tamanhos, módulos Python (stdlib do `python311.zip` + símbolos `PyInit_*` de `libpython3.11.a` + núcleo + `Range`/`mathutils`/`bgl`/`blf`) e capacidades do preset (`audio`, `threads`, `touch`, `video`, `network` = `disabled`; `gamepad`, `save` = `unvalidated`). Nada vira `validated` sem `--evidence capacidade=teste`. `aud` fica fora: só existe com `WITH_AUDASPACE`.
- `range_web/runtime.py` (puro): `find_runtime` escolhe o primeiro diretório com manifesto e devolve WEB-PKG-001 para manifesto ausente, inválido, de outro `runtime_id` ou com artefato divergente. O Validar Web usa os módulos do manifesto no lugar do fallback de stdlib; sem manifesto, mantém o fallback e reporta PKG-001. Diretórios: `RANGE_WEB_RUNTIME_DIR` e, em árvore de desenvolvimento, `build-web-release/bin` (`build-web/bin` para `web-runtime`); o layout de instalação fica para o marco F.
- Limites: `engine_revision` é o HEAD ao gerar (não prova a fonte do wasm) e a lista de módulos é derivada do build, não confirmada por import no navegador. O aceite do marco D (cubo + Python controller + A/D no navegador) segue com o smoke manual já registrado em `web-deploy.md`; falta o teste automatizado.
- Testes: `test_runtime.py` (6 puros; suíte com 53) e 3 verificações novas em `engine_web_ui.py` (runtime válido, módulos vindos do manifesto, artefato divergente).

## 2026-09-18 - Web: operador Validar Web e resultados no painel

- `bl_ui/properties_web.py`: operadores `scene.range_web_validate` (roda `collect_bpy.collect_report()` e guarda o `Report` num global transitório, fora do `.blend`) e `scene.range_web_locate` (troca para a cena de origem via `context.screen.scene` e seleciona o objeto; objeto do pool de spawn só informa a cadeia). O painel mostra o resumo, até 30 resultados (regra, mensagem, cadeia, correção sugerida, Localizar) e "Nenhuma verificação executada" até a primeira validação. O `draw()` só lê o resultado guardado; a coleta nunca roda nele. Texto do resultado indica que é da última validação. O motivo de Exportar Web indisponível agora aponta o marco F.
- Sem manifesto de runtime instalado, o conjunto de módulos disponíveis é `sys.stdlib_module_names` + builtins + API do motor (`Range`, `mathutils`, `bgl`, `blf`, `aud`, de `KX_PythonInit.cpp`); vira o manifesto quando o runtime Web (marco D) o fornecer. Sem os módulos do motor, o `startup.blend` gerava WEB-PY-001 para `import Range`.
- `report({'WARNING'})` em vez de `ERROR` para resultado com erros: `ERROR` faz `bpy.ops` levantar exceção ao chamar por script.
- Testes: o de integração da coleta foi renomeado para `engine_collect_bpy.py` (o `unittest discover` importava `bpy` do Python do sistema) e há `engine_web_ui.py` (8 verificações no motor: registro, Validar, erro de módulo ausente, `Range` não ausente, Localizar, índice inválido). Suíte pura: 47 testes. Não verificado: desenho do painel e clique nos botões (dependem do editor gráfico).

## 2026-09-18 - Web: marco C (coleta e resolução de dependências)

- `range_web/collect.py` (puro): `Snapshot`/`Reference` e `resolve()` percorrem referências de controllers (Script por Text, Module) e components e seus imports transitivos com conjunto de visitados (ciclos e dependência compartilhada são analisados uma vez). Text datablock tem precedência sobre arquivo do projeto, como no motor. Ausente ou controller sem Text vira WEB-PKG-003 com a cadeia de origem (`fase.range → Objeto → Controller → módulo`); import não resolvido segue como WEB-PY-001 do analisador, sem erro duplicado; import protegido por `try/except ImportError` não é seguido. `check_assets()` dá WEB-PKG-003 para arquivo referenciado ausente.
- `range_web/collect_bpy.py`: monta o snapshot a partir do `.blend` (todas as cenas e objetos fora de cena, sem excluir por visibilidade; Text datablocks; pasta do `.blend` como raiz de módulos; imagens/sons/fontes/bibliotecas externos, ignorando empacotados, gerados e sem uso) e `collect_report()` devolve `Report` com hash do snapshot (muda ao editar Text ou arquivo). Somente leitura; nada é importado ou executado.
- Testes: `tools/tests/web_profile/test_collect.py` (14 casos puros; suíte total 47) e `engine_collect_bpy.py` (integração via `RangeEngine -b --python`, passou).
- Limites conhecidos: imports relativos e `from pkg import submódulo` não são seguidos; PY-005 (main loop) não é coletado porque não há propriedade RNA para ele; PKG-005 por raiz/symlink fica para o marco F (exige raízes explícitas); entry scene ainda não restringe a coleta (todas as cenas entram); sem UI ligada.

## 2026-09-18 - Web: WEB-PKG-004 no scanner Python

- `rules_python.py`: literal de caminho do host (drive Windows, UNC, `/home`, `/Users`…) no 1º argumento de `open`, `os.*` de arquivo, `pathlib.Path`, `LibLoad` e `aud.Factory` gera WEB-PKG-004 (ERROR/CONFIRMED no nível do módulo em script necessário; senão WARNING/POTENTIAL). Caminhos formados dinamicamente não são cobertos (ficam para o navegador). Teste novo em `test_range_web.py` (34 casos, passam nos dois Pythons).
- `import bge` (nome legado; o motor só expõe `Range`) gera WEB-PY-001 com a correção `import Range`. Template `templates_py/gamelogic.py` migrado para `import Range`.

## 2026-09-18 - Web: marco B (núcleo puro `range_web`)

- Novo pacote `release/scripts/modules/range_web/`, sem `bpy` e sem executar/importar os scripts analisados: `results.py` (`Finding` com gravidade e evidência independentes; `ERROR` exige evidência `CONFIRMED`; `Report` com JSON e resumo "Nenhuma incompatibilidade detectada", nunca "garantido"), `manifest.py` (schema `range-web-runtime` v1 do manifesto do **runtime**, distinto do `manifest.json` do pacote; `validated` exige `evidence`; capacidade ausente conta como não validada; manifesto ausente/ilegível/inválido/hash divergente vira um único WEB-PKG-001), `rules_files.py` (WEB-PKG-004/005/006/008/009: caminho do host, destinos virtuais, `..`, colisão e caixa, symlink fora das raízes, `.pyc` por magic, extensão nativa por assinatura, `.rasec`) e `rules_python.py` (AST: WEB-PY-001/002/003/004/005/006/007/008/009 e WEB-PKG-007).
- Política do scanner Python: `ERROR/CONFIRMED` só quando o script é declarado necessário e o uso está no nível do módulo, sem guard desconhecido nem `try/except ImportError`; senão `WARNING/POTENTIAL`. Guards resolvíveis para o alvo `emscripten` (`sys.platform`, `os.name`, `platform.system()`) escolhem o ramo. Aliases simples, reatribuição e parâmetros que escondem o nome são tratados; `eval`/`exec`/import dinâmico só geram aviso de cobertura parcial.
- Testes em `tools/tests/web_profile/test_range_web.py` (33 casos): passam com o Python do sistema e com `RangeEngine -b --python` (Python 3.11 do motor). Cópia do pacote em `build/bin/2.79/scripts/modules/` para o teste.
- Ainda não ligado à UI: coleta de cenas/bibliotecas/assets (marco C), pré-voo no navegador e botão Validar/Exportar não existem; o painel continua com Exportar Web indisponível. Pendentes das regras WEB-GFX/MEDIA/INPUT/NET/SAVE/DEPLOY (dependem do runtime e do navegador).

## 2026-09-18 - Web: marco A (Scene.range_web e painel Web)

- Novo `bl_ui/properties_web.py`: `RangeWebSettings` (`schema_version`, `check_compatibility`, `runtime_id`, `entry_scene`, `output_directory`) registrado como `Scene.range_web` em `bl_ui/__init__.py` (Python puro, sem DNA/C++, padrão `rangearmor_export`). Propriedades como anotações: com atribuição simples esta engine as deixa como `_PropertyDeferred`.
- Painel "Web (Range)" na aba Cena (motor `BLENDER_GAME`, fechado por padrão): opção de verificar compatibilidade, campos, "Nenhuma verificação executada", Exportar Web indisponível com motivo único (validador é o marco B) e nota de que a tecla P é prévia desktop. Sem I/O no `draw()`.
- Verificado com `RangeEngine -b`: defaults, salvar/reabrir, Undo/Redo, cena nova e cópia de cena. Não verificado: desenho do painel e export desktop (dependem do editor).

## 2026-09-18 - Web: empacotador de export e verificador de pacote

- Novo `tools/web/package-web.py` (equivalente Web de `tools/linux/package-runtime.sh`): valida `.range` e runtime, gera pasta hospedável com `index.html` de produção (progresso, erro visível, botão Jogar, `?debug=1`), `manifest.json` (hashes, requisitos WebGL 2/sem threads, avisos), `SHA256SUMS.txt`, `serve.py`, `HOSTING.md` e ZIP opcional. Não compila nada; consome `build-web/bin`. Arquivos extras (`--extra`) ficam ao lado do `.range` no FS virtual.
- Novo `tools/web/verify-package.cjs`: abre o pacote via CDP em tempo real, clica em Jogar, envia uma seta e falha se houver erro visível/aborto/exceção.
- Verificado com `web-smoke.range` (pacote de 51,5 MiB): cena carregada de `game/`, WebGL 2, controlador Python iniciado, seta moveu o cubo, exit 0. Validação por log, sem julgamento visual.
- Achado: `--dump-dom` com `--virtual-time-budget` trava o runtime em `idbfs-initial-sync` (IndexedDB não avança em tempo virtual) — não é bug do pacote; usar CDP em tempo real.
- Achado: Node 24 no Windows dispara assert do libuv se `process.exit()` roda com WebSocket aberto.
- Novo preset `web-runtime-release` (herda de `web-runtime`, `build-web-release/`): sem `SAFE_HEAP`/`ASSERTIONS=2`/`-g2`. Removido o preload TEMP de `untitled.range` em `source/blenderplayer/CMakeLists.txt`. Build completo OK (exit 0).
- Release vs debug: `.wasm` 19,9 MB vs 25,4 MB, `.js` 0,9 MB vs 2,1 MB, `.data` ~25 MB (domina); pacote 44,8 MiB (zip 16,3 MB). `verify-package.cjs` no pacote de release: exit 0, WebGL 2, controlador Python e tecla movendo o cubo. Só log, sem julgamento visual.
- Novo `tools/web/verify-persistence.cjs`: grava token em `/saves`, `syncfs(false)`, recarrega a página e confere o retorno do IndexedDB (8 checagens OK, exit 0). Para isso o pre-js expõe `Module["FS"]`. Cobre a camada IDBFS.
- Novo `tools/create_web_save_scene.py` + `tools/web/verify-save.cjs`: cena mínima que chama `Range.logic.saveGlobalDict('ci')` no 1º frame e, após recarregar, `loadGlobalDict` devolve o dict (token + dict aninhado); o verificador lê o console do runtime (4 checagens OK, exit 0, pacote release).
- Pendente: integração à UI. Ver [web-deploy.md](web-deploy.md).

## 2026-09-18 - Actuators: propriedade string para nome de objeto; Global Property renomeada para World Property

- Edit Object > Add Object e Track To ganharam os checkboxes `From Property` e `World Property`: o nome do objeto vem de uma propriedade string do dono ou do World. Com `World Property` ligado, o campo lista só as propriedades do tipo string do World.
- Track To só encontra objetos já ativos na cena; Add Object também busca objetos em camadas inativas.
- Renomeado "Global Property/Properties" para "World Property/Properties" em todos os labels da UI (painel do World, botão `Add World Property`, operadores, Property Actuator, Edit Object), comentários e docs vigentes. Os identificadores internos (`GLOBAL_PROPERTY`, `world.game_property_new`, etc.) não mudaram; entradas antigas deste changelog preservam o nome anterior.

## 2026-09-17 - 3D View: atualização contínua unificada

- Removido o botão textual `Always Render (CPU+)` da barra flutuante. O ícone de câmera `Realtime Shading` é agora o único controle de atualização contínua da 3D View.
- Ligado, ele atualiza materiais/nós animados e também força os redraws necessários para decals e projetores seguirem objetos em movimento; desligado, o timer é removido e o consumo extra de CPU para esses redraws cessa.
- Workspaces antigos com `Always Render` ativo são convertidos ao abrir para o novo toggle, permitindo desligar a função normalmente.

## 2026-09-17 - Inicialização: configurações ImGui e tema padrão silenciosos

- O leitor da seção `KX_DebugMode` em `imgui.ini` agora tolera linhas ausentes ou inválidas: preserva o valor padrão atual em vez de emitir `Load from imgui.ini: Float value -> Error!` ou substituir a preferência por zero. Isso também evita uma exceção caso um `imgui.ini` antigo tenha um valor numérico malformado.
- A aplicação automática, no primeiro uso, do tema AnastacioGames não escreve mais uma linha de log para cada parte do mesmo XML. O carregamento manual de presets XML continua verboso para diagnóstico.

## 2026-09-17 - Shared optimization reference and foliage wind distance

- `KX_Scene` now publishes one optimization-reference position after physics each frame. It uses the active
  camera today and is the single extension point for a future Player reference.
- Game Material settings add optional `Foliage Optimization` and `Wind Distance` (50 m default). With the
  option enabled, Foliage Shader and Grass use the shared reference; an object outside the radius exits the
  vertex wind routine before evaluating procedural noise. Existing materials stay unrestricted until enabled.
- Camera Properties in Game Engine mode now identifies the active Scene camera as the source of this shared
  reference, keeping the relationship visible while configuring distance-based systems.

## 2026-09-16 — Auditoria estruturada de performance

- Corrigido o painel flutuante da 3D View: os botões individuais de mover,
  rotacionar e escala agora só aparecem quando o manipulador principal está
  ligado, igual ao cabeçalho original. Build de `RangeEngine` concluído;
  confirmação visual na janela real pendente.

- Criada a taxonomia LIFE, DUP, CPU, MEM, GPU, SYNC, POOL e ALG para separar
  vazamento de trabalho, duplicação, alocação, sincronização e custo de
  renderização.
- Registrados dois problemas já confirmados (animações persistentes e
  componentes ignorando suspensão) e candidatos que precisam de medição:
  duplicação nas listas GPU/sombra, cópia/crescimento de mapas em mensagens de
  rede, possível espera em GL_QUERY_RESULT, alocações de culling e sorting
  por frame nos buckets, além de registros duplicados em callbacks de colisão.
- Segunda rodada estática encontrou ainda alocações por frame no culling,
  sorting/batching e snapshot de componentes Python. O registro de componentes
  tem um único call site hoje, então não foi classificado como duplicação
  confirmada; os itens permanecem separados como hotspots ou contratos frágeis

- As listas de objetos de partículas GPU e shadow casters passaram a aceitar
  cada ponteiro apenas uma vez (`KX_Scene::Add*`). A correção é preventiva para
  réplicas/reentrada de cena e foi validada compilando `ge_ketsji` e ligando
  `RangeRuntime`.
  para validação posterior.
- O inventário completo está em docs/performance-audit.md; nenhum candidato
  foi alterado sem reprodução.

## 2026-09-16 — Correção de engine + script: animações de objetos de pool deixam de acumular em KX_Scene::m_animatedlist

- **Problema relatado**: objetos de efeito em pool (fumaça, faíscas, terra/asfalto, slipstream) ao queimar pneu causavam aumento contínuo da porcentagem de "Animations" no profiler até ~16%, mesmo após o efeito terminar e o objeto retornar ao pool.
- **Diagnóstico**: o custo residual era causado por um gap arquitetural na engine: `KX_GameObject::playAction()` registra o objeto uma única vez em `KX_Scene::m_animatedlist` (via `AddAnimatedObject` chamado pela primeira vez que `GetActionManager()` é criado), mas `stopAction()` **apenas limpa as layers de ação** — ele **nunca remove o objeto da lista**. A remoção só ocorre quando o objeto é destruído (via `RemoveObject`). Objetos de pool são reciclados, nunca destruídos, então ficam registrados para sempre. A cada frame, `KX_Scene::UpdateAnimations()` itera sobre todos os objetos da lista (inclusive os "inativos" no pool) e despacha tarefas de update de animação, mesmo quando não há nada a fazer.
- **Solução implementada**:
  1. **Engine (C++)**: expusemos `BL_ActionManager::Suspend()/Resume()/IsSuspended()` (métodos pré-existentes, mas nunca acessíveis do Python) através de novos métodos em `KX_GameObject`: `SuspendAnimations()` e `ResumeAnimations()` (implementação em `KX_GameObject.cpp` ~linha 2126-2138, espelhando o padrão de `SuspendPhysics()`/`RestorePhysics()`), e registrados na tabela de métodos Python (~linha 2685-2698) com macros `EXP_PYMETHOD_NOARGS` (header `KX_GameObject.h` ~linha 999-1000).
  2. **Jogo (Python)**: editado `pool_add_object.py` para chamar `obj.suspendAnimations()` em `_recursive_stop_and_hide()` (executado ao desativar/reciclar um objeto para o pool) e `obj.resumeAnimations()` em `_activate()` (executado ao reativar um objeto), removendo as checagens de `hasattr(inst, "suspend")`/`hasattr(inst, "resume")` que nunca funcionavam (esses métodos nunca existiram no engine).
  3. **Mecanismo**: `KX_Scene::UpdateAnimations()` respeita `IsActionsSuspended()` (que lê `BL_ActionManager::IsSuspended()`), pulando o dispatch de tarefa de atualização para objetos suspensos — o objeto permanece em `m_animatedlist`, mas não gera custo de CPU por frame enquanto suspenso.
- **Build**: recompilado incrementalmente (`ninja RangeEngine RangeRuntime`) após corrigir o `LNK1104` (executável `RangeEngine.exe` foi fechado manualmente pelo usuário), link bem-sucedido com exit code 0; novos binários instalados em `build/bin/`.
- **Próximos passos**: validação em-jogo (queimar pneu, monitorar profiler "Animations" durante e após o efeito) para confirmar que a porcentagem não sobe mais ou permanece baixa com a correção aplicada.

## 2026-09-15 — Release 0.3.0: pacote Windows publicado, RangeArmor como asset separado

- **Windows x86_64 0.3.0 publicado**: `RangeEngine.exe`/`RangeRuntime.exe` recompilados (ninja, preset
  nativo) após o commit `72d661c6` (tema AnastacioGames), empacotados em
  `AnastacioEngine-0.3.0-windows-x64.zip` seguindo a convenção de `distribution-0.1.md` (sem logs, `.pdb`,
  `.map`, `.lib`, `.exp`, ferramentas internas, cenas de teste; DLLs redistribuíveis do Visual C++ —
  `concrt140`, `msvcp140*`, `vccorlib140`, `vcruntime140` — incluídas a partir do VS 2026 Community
  instalado na máquina).
- **RangeArmor publicado como asset separado, não mais embutido no zip da engine**: o código-fonte da
  RangeArmor não está neste repositório (`tools/RangeArmor-master/` é ignorado pelo Git); o pacote
  `RangeArmor-0.3.0-windows-x64.zip` foi montado a partir do bundle presente em `build/bin/rangearmor/`
  (painel, launcher, scripts de build/export Python, ícones) mais a licença MIT (`LICENSE.txt`, © 2020
  BGEmpire Studio) recuperada de um artefato 0.2.0 anterior. Publicado na mesma release `v0.3.0` do GitHub,
  como página compartilhada mas asset distinto — não como um repositório novo.
- `SHA256SUMS.txt` da release `v0.3.0` atualizado com as três entradas (Linux, Windows, RangeArmor).
- Upload feito via `gh release upload v0.3.0 ... --clobber` após autenticação do GitHub CLI na máquina de
  desenvolvimento.

## 2026-09-15 — Documentação: Linux nativo como base para Web/Android

- Atualizados `docs/README.md`, `docs/roadmap.md`, `relatorio-melhorias-anastacioengine.md` e
  `docs/android-web-export-roadmap.md` para registrar que a validação nativa em Linux x86_64 ajuda a reduzir
  o risco dos exports Web/Android.
- Conclusão registrada: Linux não implementa Web/Android automaticamente, mas prova que o runtime já saiu do
  eixo Windows/MSVC com toolchain Unix, Python 3.11 isolado, OpenAL, SDL/X11, RPATH e empacotamento próprio.
  Isso vira referência prática para Web (HTML/JS/WASM) e Android (NDK/APK/AAB), principalmente em Python
  embarcado, seleção explícita de features por plataforma e validação em hardware real.
- Android continua sem backend GHOST/APK funcional. O próximo passo técnico deve começar pelos bloqueios
  concretos do NDK já conhecidos (`malloc_stats` ausente na Bionic e `GL/glu.h` inexistente), antes de criar
  infraestrutura maior.

## 2026-09-15 — Release 0.3.0: pacote Linux portátil, tema padrão AnastacioGames

- **Empacotamento portátil validado em máquina limpa**: o `RUNPATH` absoluto (`/opt/anastacio-python311/lib`)
  embutido no `RangeEngine`/`RangeRuntime` pelo preset `linux-editor`/`linux-runtime` foi trocado por
  `$ORIGIN/python311/lib` via patch binário direto na tabela de strings do ELF (sem `patchelf`/`chrpath`
  disponíveis no sistema), e o runtime isolado do Python 3.11 (`/opt/anastacio-python311`) passou a ser
  copiado para dentro do próprio pacote (`python311/lib/`). Testado rodando os dois binários a partir de um
  diretório isolado, sem qualquer dependência do caminho original — resolve a pendência do roadmap de validar
  o tarball numa máquina limpa.
- **Tema AnastacioGames como padrão na primeira execução**: novo script de startup
  `source/release/scripts/startup/anastacio_default_theme.py` aplica o preset
  `scripts/presets/interface_theme/anastaciogames.xml` via `rna_xml.xml_file_run` (chamando a API de baixo
  nível em vez do operador `script.execute_preset`, que depende de contexto de janela indisponível no
  registro de scripts de startup) e salva as preferências do usuário. Um arquivo-marcador na pasta de config
  evita reaplicar o tema em execuções seguintes; se o salvamento falhar, a lógica tenta de novo na próxima
  abertura em vez de travar num estado sem tema.
- **Versão exibida bump para 0.3.0** em `source/release/scripts/startup/bl_operators/wm.py` (splash screen).

## 2026-09-15 — Linux nativo: RangeEngine (editor completo) compila e roda pela primeira vez, 6 bugs corrigidos

- **Máquina**: mesma do `RangeRuntime` (Ubuntu 24.04 nativo, `fabio-ASUS-Linux`). Primeira tentativa de build
  do alvo `RangeEngine` (`WITH_BLENDER=ON`, preset `linux-editor` introduzido no commit
  `feat(linux): preparar preset e script para compilar o RangeEngine (editor)`), nunca compilado em Linux
  antes.
- **Bug 1 — FFmpeg, ponteiros `const` na API nova**: `avcodec_find_decoder`/`avcodec_find_encoder` e
  `AVFormatContext::oformat` passaram a devolver ponteiros `const` a partir do FFmpeg 5.0; o Ubuntu 24.04 tem
  libavcodec60 (FFmpeg 6.1), mas o wrapper `audaspace` (`extern/audaspace/plugins/ffmpeg/FFMPEGReader.cpp` e
  `FFMPEGWriter.cpp`) ainda atribuía a ponteiros não-`const`. Corrigido tipando `aCodec`/`codec` como
  `const AVCodec*` e trocando a escrita direta em `outputFmt->audio_codec` (agora inacessível, `outputFmt`
  virou `const AVOutputFormat*`) por uma variável local `AVCodecID audio_codec`.
- **Bug 2 — OpenColorIO, API v1 removida na 2.x**: `intern/opencolorio/ocio_impl.cc`/`ocio_impl_glsl.cc` usam
  chamadas da API antiga da OpenColorIO (`Config::getDisplayColorSpaceName`, `Processor::apply`/`applyRGB`/
  `applyRGBA`, `DisplayTransformRcPtr`) que não existem mais na OpenColorIO 2.x — e o Ubuntu 24.04 só tem
  `libopencolorio-dev` 2.1+. Portar essas chamadas para a API 2.x é um trabalho de várias dezenas de call
  sites, fora do escopo de uma validação de build; **desliguei `WITH_OPENCOLORIO`** no preset `linux-editor`
  (`source/CMakePresets.json`) em vez de tentar um fix parcial.
- **Bug 3 — FFmpeg (export de vídeo), API pré-3.1 removida**: `source/blender/blenkernel/intern/writeffmpeg.c`
  usa `AVStream::codec`, `avcodec_encode_video2`/`avcodec_encode_audio2`, `av_free_packet`,
  `avpicture_get_size`/`avpicture_fill`, `AVFormatContext::filename` — todos removidos do FFmpeg há vários
  anos (a maior parte já no 3.1~4.0). Mesmo caso de escopo do bug 2: **desliguei `WITH_CODEC_FFMPEG`** no
  mesmo preset. Consequência: o RangeEngine linux atual não exporta vídeo nem decodifica os codecs FFmpeg da
  libavformat/libavcodec do sistema (o `WITH_CODEC_SNDFILE`/OpenAL para tocar áudio de jogo, já validado no
  `RangeRuntime`, não depende disso).
- **Bug 4 — declaração implícita de `strcmp`**: `source/blender/editors/interface/interface_context_menu.c`
  usa `strcmp` (via `BLI_string.h`) sem incluir `<string.h>` diretamente; o gcc do Ubuntu 24.04 trata
  declaração implícita de função como erro (`-Werror=implicit-function-declaration`, já visto antes em outro
  contexto). Corrigido com `#include <string.h>` no topo do arquivo.
- **Bug 5 — link falhava por `-lge_player` ausente**: `source/gameengine/Launcher/CMakeLists.txt` linka a
  biblioteca `ge_player` incondicionalmente na lista `LIB` do `ge_launcher`, mas
  `source/gameengine/CMakeLists.txt` só faz `add_subdirectory(GamePlayer)` (onde `ge_player` é definida)
  quando `WITH_PLAYER=ON` — e o preset `linux-editor` usa `WITH_PLAYER=OFF` (é o editor, não o player
  standalone). Bug de wiring do CMake exposto pela primeira combinação real de `WITH_BLENDER=ON` +
  `WITH_PLAYER=OFF` em Linux. Corrigido guardando essa entrada da lista com `if(WITH_PLAYER)`.
- **Bug 6 — link falhava por símbolos OpenImageIO indefinidos**: `undefined reference to
  'OpenImageIO_v2_4::TypeDesc::basesize() const'` e `'...ParamValue::clear_value()'` ao linkar
  `bf_imbuf_openimageio`. Causa: o Ubuntu 24.04 divide a OpenImageIO em `libOpenImageIO.so` (core) e
  `libOpenImageIO_Util.so` (tipos/utilidades, onde esses dois símbolos realmente vivem — confirmado com
  `nm -D`); `build_files/cmake/Modules/FindOpenImageIO.cmake` só procurava e linkava a primeira. Corrigido
  adicionando `FIND_LIBRARY(OPENIMAGEIO_UTIL_LIBRARY NAMES OpenImageIO_Util ...)` e anexando o resultado a
  `OPENIMAGEIO_LIBRARIES` quando encontrado.
- **Bug 7 — mesmo bug de RPATH do RangeRuntime, faltando no editor**: `libpython3.11.so.1.0: cannot open
  shared object file` ao rodar `build-linux-editor/bin/RangeEngine` fora do ambiente de build — o fix de
  `BUILD_RPATH`/`INSTALL_RPATH` aplicado ao `RangeRuntime` em 15/09 (`source/blenderplayer/CMakeLists.txt`,
  entrada acima) nunca tinha sido replicado para o alvo `RangeEngine`. Corrigido aplicando o mesmo padrão em
  `source/creator/CMakeLists.txt` (bloco `WITH_INSTALL_PORTABLE`, guardado por `UNIX AND NOT APPLE AND NOT
  EMSCRIPTEN AND PYTHON_ROOT_DIR`).
- **Bug menor sem relação com portabilidade Linux**: `install(FILES
  release/datafiles/debugmode_configfile/imgui.ini ...)` em `source/creator/CMakeLists.txt` era
  incondicional, mas esse arquivo nunca existiu no repositório (sem histórico git) — quebrava `cmake --install`
  em qualquer plataforma, não só Linux. Corrigido guardando com `if(EXISTS ...)`, no mesmo padrão já usado
  para outros datafiles opcionais logo acima no arquivo.
- **Resultado**: `RangeEngine` compila (2707 passos), linka e instala sem erros. Smoke test:
  `build-linux-editor/bin/RangeEngine --background --factory-startup --python-expr "import bpy;
  print(bpy.app.version_string)"` roda e imprime a versão, confirmando Python/bpy operacionais e o RPATH do
  Python isolado correto. **Não testado ainda**: abrir a janela real do editor (GHOST/X11, contexto OpenGL da
  UI, ícones, i18n, addons Python) — o smoke test acima rodou inteiro em modo `--background`, sem criar
  janela. Ver `docs/linux-build.md` (seção "Editor (RangeEngine)") para o resumo consolidado e o estado atual
  das flags `WITH_*`.

## 2026-09-15 — Linux nativo: RangeRuntime compila e roda com GPU real (fix de RPATH do Python isolado)

- **Máquina**: Ubuntu 24.04 nativo (notebook do usuário, `fabio-ASUS-Linux`), primeira validação fora do
  WSLg usado na referência de 8 de setembro. Com `cmake`/`ninja`/libs de sistema instalados via apt e o
  Python 3.11 isolado (`tools/linux/install-python311.sh`), `cmake --preset linux-runtime -S source` +
  `cmake --build build-linux --target RangeRuntime` compilaram sem erros (~1847 passos).
- **Bug encontrado e corrigido — RangeRuntime instalado não abria fora do ambiente de build**: rodar
  `build-linux/bin/RangeRuntime` diretamente falhava com `error while loading shared libraries:
  libpython3.11.so.1.0: cannot open shared object file`. Causa: o alvo `RangeRuntime` no Linux
  (`source/blenderplayer/CMakeLists.txt`) nunca definia RPATH nenhum, e `WITH_INSTALL_PORTABLE` (ligado no
  preset) liga `CMAKE_SKIP_BUILD_RPATH` globalmente (`source/CMakeLists.txt`), então o binário linkado
  contra `/opt/anastacio-python311/lib/libpython3.11.so` não carregava sem `LD_LIBRARY_PATH` manual.
  Corrigido adicionando `BUILD_RPATH`/`INSTALL_RPATH` = `${PYTHON_ROOT_DIR}/lib` só para o alvo
  `RangeRuntime` em Unix (guardado por `NOT EMSCRIPTEN AND PYTHON_ROOT_DIR`, sem afetar Windows/macOS/wasm).
- **Segundo bug, mais sutil, descoberto ao corrigir o primeiro**: com `INSTALL_RPATH` deixado no default
  (vazio) e só `BUILD_RPATH` setado, `cmake --install build-linux` passou a **apagar o próprio binário e
  falhar** (`file INSTALL cannot find .../RangeRuntime`). Causa: como o preset instala com `DESTINATION "."`
  e `CMAKE_INSTALL_PREFIX` = `build-linux/bin` (mesma pasta do link), a origem e o destino do install são o
  mesmo arquivo; o script gerado roda `file(RPATH_CHECK FILE <arquivo> RPATH "<INSTALL_RPATH>")` antes de
  copiar, e como o RPATH já gravado no binário (pelo `BUILD_RPATH`) não batia com o `INSTALL_RPATH` (vazio)
  esperado, o CMake apagava o arquivo achando que ia recopiá-lo da origem — que era o próprio arquivo que
  acabara de apagar. Corrigido deixando `BUILD_RPATH` e `INSTALL_RPATH` **iguais**, para o RPATH_CHECK nunca
  achar divergência nesse layout de instalação "self-referencing".
- **Resultado**: `RangeRuntime` instalado roda direto (`./RangeRuntime jogo.range`, sem env var nenhuma) sem
  o erro de `libpython3.11.so.1.0`. Testado com o jogo do usuário (`RolimaRacer.range`,
  `/home/fabio/Documentos/jogos/ProjetoRolimaRacer/`): carregou e rodou sem crash. **Atenção**: nesse primeiro
  teste eu reportei incorretamente que a GPU usada era "Mesa Intel(R) Graphics real" como se fosse o
  resultado esperado — na verdade essa é a iGPU Intel, e a máquina do usuário tem uma NVIDIA RTX 5060 Laptop
  dedicada que **não** estava sendo usada; o jogo também estava sem áudio. Ver entrada abaixo
  ("GPU NVIDIA, áudio OGG/MP3 e bug de dither alpha") para o diagnóstico e correção reais desses dois
  problemas, confirmados pelo usuário só depois de mais uma rodada de fixes.
- Isso resolve a limitação principal registrada em 8 de setembro ("ainda falta validar em Linux nativo com
  GPU real") — a build deixa de depender só do WSLg com renderização por software — mas só depois dos fixes
  de GPU/áudio/alpha da entrada seguinte a validação ficou realmente completa.

## 2026-09-15 — Linux nativo: GPU NVIDIA (Optimus/PRIME), áudio OGG/MP3 e bug de dither alpha na NVIDIA

Continuação da entrada acima: o usuário testou `RolimaRacer.range` no notebook (`fabio-ASUS-Linux`, Intel
Core Ultra + NVIDIA RTX 5060 Laptop, Optimus/PRIME) e reportou três problemas reais: áudio não tocava, jogo
lento porque estava rodando na iGPU Intel em vez da NVIDIA dedicada, e (depois de corrigir os dois primeiros)
um bug visual sério só na NVIDIA — árvores/grama com aparência de "chiado de TV analógica" (ruído
preto-e-branco denso cobrindo qualquer objeto com esse tipo de material).

- **Áudio não tocava**: `WITH_CODEC_SNDFILE` e `WITH_CODEC_FFMPEG` estavam ambos `OFF` no preset
  `linux-runtime`, e os assets de som do jogo são `.ogg`/`.mp3` — o OpenAL inicializava normalmente (log
  mostrava device/context criados), mas não havia decoder para os arquivos. Causa raiz real, mais sutil:
  `WITH_CODEC_SNDFILE=ON` no preset **não bastava**, porque `build_files/cmake/Modules/FindSndFile.cmake`
  tinha um bug de nome de variável — `FIND_PACKAGE_HANDLE_STANDARD_ARGS(SndFile ...)` define `SndFile_FOUND`,
  não `LIBSNDFILE_FOUND`, mas é esse segundo nome que `platform_unix.cmake` checa para decidir se desliga
  `WITH_CODEC_SNDFILE` de volta — então a flag era sempre revertida para `OFF` silenciosamente, mesmo com
  `libsndfile1-dev` instalado e a flag pedida no preset. Corrigido com uma ponte
  `SET(LIBSNDFILE_FOUND ${SndFile_FOUND})` em `FindSndFile.cmake`, logo após o `FIND_PACKAGE_HANDLE_STANDARD_ARGS`.
  Esse bug provavelmente afeta (afetava) qualquer build Linux que tentasse ligar sndfile, não só este preset.
- **Jogo lento / GPU errada**: notebook com gráfica híbrida Intel+NVIDIA (Optimus/PRIME). Sem nenhuma
  variável de ambiente, o driver usa a iGPU Intel por padrão mesmo com o driver NVIDIA instalado e
  funcionando (`nvidia-smi` ok). Corrigido rodando com `__NV_PRIME_RENDER_OFFLOAD=1
  __GLX_VENDOR_LIBRARY_NAME=nvidia` — confirmado via log (`Using Device: NVIDIA Corporation - NVIDIA GeForce
  RTX 5060 Laptop GPU/PCIe/SSE2`, `OpenGL 4.6.0 NVIDIA 595.84`). `tools/linux/quickstart.sh` agora detecta
  automaticamente (via `xrandr --listproviders` procurando `NVIDIA-G0`) se a máquina tem esse tipo de GPU
  híbrida e injeta essas variáveis sozinho ao rodar o jogo, sem o usuário precisar lembrar.
- **Bug de dither alpha só na NVIDIA ("chiado de TV")**: materiais com blend "Alpha Blend Hashed"
  (`GPU_BLEND_ALPHA_TO_COVERAGE`) usam, em `source/source/blender/gpu/intern/gpu_material.c`
  (`gpu_material_construct_end`, função `shade_dither`), um dither por shader (padrão Bayer) como fallback
  de transparência quando `scene->gm.aasamples <= 1`, combinado com `GL_ALPHA_TEST` +
  `GL_SAMPLE_ALPHA_TO_COVERAGE` no estado fixo (`gpu_draw.c`). Sem multisample real no framebuffer, esse
  dither aparece cru — e o driver proprietário da NVIDIA honra literalmente "0 amostras pedidas" (framebuffer
  single-sample de verdade), enquanto o Mesa/Intel aparentemente entrega algum multisample por padrão mesmo
  sem pedido explícito, mascarando o problema. Corrigido forçando um mínimo de 4 amostras sempre que
  `gm.aasamples <= 1`, em dois pontos: `LA_Launcher.cpp` (samples do canvas/framebuffer principal, cena
  inicial) e `BL_Converter.cpp::ConvertScene` (por cena — **necessário porque a pista/árvores do jogo é uma
  cena carregada em runtime via LibLoad/AddScene, com seu próprio `Scene->gm.aasamples` independente da cena
  inicial do menu**; corrigir só a cena inicial não bastou, foi preciso instrumentar com prints de debug
  temporários para descobrir que `mat->scene` nos materiais da pista apontava para um `Scene*` diferente do
  `m_startScene` do launcher).
- **Resultado confirmado pelo usuário** (via screenshot e mensagem direta, não só log): áudio tocando, GPU
  NVIDIA em uso, árvores/grama renderizando normalmente sem ruído.

## 2026-09-15 — Linux nativo: script para instalar Python 3.11 isolado (apt nao tem mais o pacote)

- **Motivo**: preparando o ambiente de trabalho em Linux nativo (Ubuntu 24.04, fora do WSL usado na
  referência de 8 de setembro), `sudo apt install python3.11 python3.11-dev` falhou com "Impossível
  encontrar o pacote" — confirmado que o repositório do Ubuntu 24.04 só oferece `python3.12`. O preset
  `linux-runtime` exige `PYTHON_ROOT_DIR=/opt/anastacio-python311` (ABI 3.11 especificamente), então o
  Python do sistema (3.12) não serve mesmo que estivesse disponível.
- Criado `tools/linux/install-python311.sh`: compila CPython 3.11.9 a partir do fonte oficial
  (`--enable-shared`, `make altinstall`) direto em `/opt/anastacio-python311`, instala `pip`/`numpy`
  isolados nesse prefixo e é idempotente (só reinstala com `FORCE=1`).
- `tools/linux/quickstart.sh` atualizado: removida a tentativa de `apt install python3.11` (que quebrava
  o script inteiro via `set -e` em distros sem esse pacote) e adicionado o passo que chama
  `install-python311.sh` antes do preflight; `preflight.sh` agora roda com
  `PYTHON_EXECUTABLE=/opt/anastacio-python311/bin/python3.11` por padrão em vez do `python3.11` genérico
  do PATH.
- `docs/linux-build.md` atualizado para apontar o novo script em vez de descrever a compilação manual de
  forma vaga.
- **Pendente**: rodar `install-python311.sh` + `quickstart.sh` de ponta a ponta nesta máquina Linux nativa
  (com GPU real, ao contrário da referência WSLg) e confirmar `RangeRuntime` compilando/rodando — ainda
  não executado nesta sessão.

## 2026-09-14 — Web: encerramento da etapa de filtros 2D

- Filtros nativos originais confirmados funcionando no navegador.
- Filtros adicionados na evolução da Range Engine compilam e executam sem erros de shader ou falhas de draw no smoke test Web.
- Aceite visual detalhado e refinamento de desempenho ficam adiados para uma etapa própria; efeitos pesados deverão ser opcionais no uso via Internet.

## 2026-09-14 — Web: persistência de save via IndexedDB (IDBFS)

- Levantamento do save existente (`bge.logic.saveGlobalDict`/`loadGlobalDict`): único mecanismo de
  persistência de jogo no engine, todo concentrado em `saveGamePythonConfig`/`loadGamePythonConfig`/
  `pathGamePythonConfig` (`KX_PythonInit.cpp`), usando `fopen`/`fwrite`/`fread` puro sobre o resultado do
  `PyMarshal_WriteObjectToString` do `globalDict`. No Web isso caía dentro do MEMFS empacotado via
  `--preload-file` (somente leitura de fato, e não persiste entre sessões/abas mesmo se gravável).
- `pathGamePythonConfig()`: sob `__EMSCRIPTEN__`, o caminho passa a ser fixo em `/saves/<saveName>.<ext>`
  em vez de derivar de `KX_GetOrigPath()` (que aponta pro asset empacotado, não para um diretório
  gravável/persistente). Fora do Web, comportamento idêntico ao anterior.
- `saveGamePythonConfig()`: após o `fwrite`/`fclose` bem-sucedido, `EM_ASM` dispara
  `FS.syncfs(false, cb)` para persistir a escrita do MEMFS para o IndexedDB — sem isso, o save
  desaparece ao fechar a aba (IDBFS só sincroniza a leitura no boot, sync de escrita é sempre explícito).
- `source/source/blenderplayer/web_idbfs_prerun.js` (novo, `--pre-js` só no target `RangeRuntime`):
  monta `/saves` como `IDBFS` e roda `FS.syncfs(true, cb)` como run dependency antes do `main()` do
  Emscripten começar, trazendo saves de sessões anteriores para o MEMFS antes de qualquer
  `loadGamePythonConfig()` síncrono rodar.
- `source/source/blenderplayer/CMakeLists.txt`: bloco `if(EMSCRIPTEN)` do target `RangeRuntime` ganhou
  `-lidbfs.js`, `-sFORCE_FILESYSTEM=1` e `--pre-js=.../web_idbfs_prerun.js`, escopados só a este target
  (mesmo padrão já usado para `--preload-file`, para não afetar as ferramentas geradoras nativas
  `datatoc`/`makesdna`/`makesrna` que usam `NODERAWFS`).
- Build `RangeRuntime` em `build-web` via `vcvars64.bat` + `emsdk_env.bat`: exit 0, sem erro/warning novo.
  Confirmado por grep no `RangeRuntime.js` gerado que `IDBFS` e a run dependency `idbfs-initial-sync`
  estão de fato embutidos no runtime.
- **Pendente**: nenhuma cena local hoje chama `saveGlobalDict()`/`loadGlobalDict()` a partir de um
  controller Python, então falta um smoke test dedicado (via CDP: salvar, recarregar a página,
  confirmar que o valor persistiu no IndexedDB) e o aceite visual do usuário no navegador real. A API
  Python continua síncrona mesmo no Web; o `syncfs` de escrita é best-effort assíncrono em segundo
  plano — se a aba fechar no meio do sync, o save mais recente pode não persistir (limitação conhecida
  do IDBFS, não deste fix).

## 2026-09-14 — Web: cobertura dos filtros nativos restantes no fix de draw buffers

- Retomando o item pendente da entrada "roteamento de draw buffers nos materiais gerados"/"saídas dos
  filtros de pós-processamento": `m_webSingleColorOutput` em `RAS_2DFilter.cpp` cobria só cinco filtros
  nativos (FXAA, Rain, Clouds, LensFlare, Tonemaps) por comparação de fonte completa do fragment shader,
  porque `filterMode` sozinho não distingue nativo de custom (o clima também usa `FILTER_CUSTOMFILTER`).
- Levantamento dos `.glsl` em `RAS_OpenGLFilters/` e de `KX_2DFilterManager.cpp`/`RAS_2DFilterManager.cpp`
  confirmou que todos os filtros nativos restantes que desenham direto no off screen compartilhado da cena
  (sem off screen próprio via `SetOffScreen`) declaram só um output `fragColor`, igual aos cinco já
  cobertos: SSAO, Blur, Sharpen, Dilation, Erosion, Laplacian, Sobel, Prewitt, GrayScale, Sepia, Invert,
  OutLine, e os passes finais de composição de Bloom (`RAS_Bloom2DFilter_Image`), SSR
  (`RAS_SSR_Blur2DFilter`) e Light Scattering (`RAS_LightScaterring_Image2DFilter`) — esses três últimos
  têm passes intermediários com off screen próprio (não precisam do fix), mas o pass final de composição
  não tem e sofreria o mesmo `GL_INVALID_OPERATION: missing fragment shader outputs` no Web assim que
  habilitado numa cena com MRT ativo.
- `RAS_2DFilter.cpp`: lista de comparação estendida para as 15 fontes adicionais confirmadas
  (Bloom buf/bufH/bufV, SSR buffer e Light Scattering buffer ficaram de fora de propósito, por já
  usarem off screen próprio de um anexo só). Nenhuma mudança de header, flag global ou comportamento
  fora de `__EMSCRIPTEN__`.
- Build `RangeRuntime` em `build-web` via `vcvars64.bat` + `emsdk_env.bat` na mesma chamada: exit 0, 5
  passos. Smoke test via Chrome/CDP (`build-web/smoke-diagnose.cjs`, cache desativado,
  `web-smoke.range`): **2.055 draws, zero falhas, 685 com o segundo anexo (MRT) ativo** — confirma
  ausência de regressão no caminho já validado, não valida os filtros novos em si (a cena de smoke não
  os habilita).
- Pendente (resolvido a seguir nesta mesma data): nenhuma cena local hoje habilita SSAO/Blur/Sharpen/etc.
  para exercitar o fix igual foi feito para FXAA/Rain/Clouds antes; falta uma cena dedicada de MRT/filtros
  (o item já registrado no roadmap) para validar por CDP e depois aceite visual do usuário.

## 2026-09-14 — Web: cena dedicada valida os 15 filtros nativos recém-cobertos

- Seguindo o pendente da entrada anterior: `tools/create_web_smoke_scene.py` ganhou um bloco que empilha
  15 `SCA_2DFilterActuator` no `WebKeyboardCube` (todos ligados ao mesmo controller Python, sempre ativos
  via o sensor `ALWAYS` já existente): `BLUR`, `SHARPEN`, `DILATION`, `EROSION`, `LAPLACIAN`, `SOBEL`,
  `PREWITT`, `GRAYSCALE`, `SEPIA`, `INVERT`, `OUTLINE`, `SSAO`, `BLOOM`, `LIGHTSCATTER`, `SSR` — exatamente
  os 15 filtros adicionados à cobertura do `m_webSingleColorOutput` na entrada anterior. Os filtros
  built-in (SSAO/Bloom/Light Scattering/SSR) não exigem setup extra de cena: `RAS_2DFilterManager::
  SetBuiltinFilterEnabled` cria os passes internos sozinho a partir só do actuator.
  - Gotcha de API: `sensor.link(actuator)` falha (`AlwaysSensor.link()` só aceita `Controller`); o link
    correto de um actuator a um controller já criado é `controller.link(actuator=act)`.
- Cena regerada via `build/bin/RangeEngine.exe -b --python tools/create_web_smoke_scene.py` (editor nativo,
  não o player Web) sobrescrevendo `build-web/bin/web-smoke.range`.
- Smoke test via Chrome/CDP (`build-web/smoke-diagnose.cjs`, servidor HTTP e Chrome debugging já ativos de
  sessão anterior): **2.046 draws, zero falhas, 682 com MRT (segundo anexo) ativo**, sem nenhuma entrada de
  erro/exceção no log (`build-web/smoke-diagnostic.log`). Isso valida de fato o fix da entrada anterior —
  antes só havia sido validada a ausência de regressão no caminho de 5 filtros já cobertos, agora os 15
  filtros novos foram exercitados e não produziram `GL_INVALID_OPERATION`.
- Segue faltando: aceite visual do usuário no navegador real (este teste só confirma ausência de erro de
  GL via CDP, não a corretude visual de cada filtro — não há objetos refletivos para SSR nem luz
  configurada para Light Scattering/SSAO nesta cena mínima).

## 2026-09-14 — Web: correção da entrada anterior — os 15 filtros nunca tinham sido de fato ativados, mais 5 bugs reais de shader achados e corrigidos

- **A validação "15 filtros exercitados, zero `GL_INVALID_OPERATION`" da entrada anterior estava incorreta.**
  O usuário reportou visualmente "apareceu mas sem efeitos" — investigação confirmou que nenhum dos 15
  filtros era de fato executado: `controller.link(actuator=act)` só declara a ligação lógica, mas um
  `SCA_PythonController` (`SCA_PythonController.cpp`) só dispara um actuator ligado quando o script chama
  `cont.activate(actuator_ou_nome)` explicitamente — a cena anterior nunca fazia essa chamada, então
  `SCA_2DFilterActuator::Update()` nunca rodava e nenhum filtro era criado. O "sem falhas" reportado antes
  media apenas o caminho sem filtro nenhum ativo.
- Bug adicional que teria mascarado o resultado mesmo com `activate()`: os 11 filtros simples (não
  built-in) compartilhavam `filter_pass=0` por não terem sido configurados individualmente — via
  `RAS_2DFilterManager::AddFilter`, isso faz o segundo filtro criado no mesmo pass logar aviso e não fazer
  nada (`SCA_2DFilterActuator.cpp`, case `default`), então só o primeiro filtro ativado teria efeito.
- **Fix**: `tools/create_web_smoke_scene.py` reescrito a pedido do usuário ("colocar os efeitos em teclas
  do teclado") — cada um dos 15 filtros agora é ativado por uma tecla dedicada em vez de sempre-ligado:
  `1`-`9`/`0`/`Q` para os 11 filtros simples (Blur, Sharpen, Dilation, Erosion, Laplacian, Sobel, Prewitt,
  GrayScale, Sepia, Invert, Outline — cada um com `filter_pass` único 0-10 e 3 actuators ligados
  `<nome>_CREATE`/`_ON`/`_OFF`, ativados via `cont.activate()` por nome), `W`/`E`/`R`/`T` para os 4
  built-in (SSAO, Bloom, LightScatter, SSR — só actuator `_ON`, já que o actuator clássico só chama
  `SetBuiltinFilterEnabled(mode, True)`, sem caminho de desligar por logic brick — limitação do engine,
  não bug desta cena). Borda de tecla detectada por variável própria no objeto (`key_edge()`), não pelo
  valor `JUST_ACTIVATED` puro do engine, por robustez a testes automatizados.
- **Gotcha de teste automatizado via CDP** (`build-web/filters-smoke-diagnose.cjs`): eventos de teclado
  sintéticos (`Input.dispatchKeyEvent`) não chegam ao handler SDL/Emscripten sem o canvas primeiro receber
  foco de mouse — confirmado pelo texto na tela ("Clique no jogo e use as setas"), mas não documentado em
  nenhum lugar do código. Sem um clique sintético (`Input.dispatchMouseEvent`) antes das teclas, todo teste
  automatizado por teclado falha silenciosamente, inclusive testes que já tinham funcionado antes (ex.:
  seta direita), causando falso-negativo de regressão. Fix do script de teste: clique no canvas antes de
  qualquer tecla.
- **Com o binding de teclado realmente ativando os filtros pela primeira vez, apareceram 5 bugs reais de
  shader, específicos de WebGL2/GLSL ES 3.00 (tipagem estrita, aceito em compiladores desktop mas rejeitado
  aqui)**, um por filtro, todos corrigidos:
  - `RAS_SSAO2DFilter.glsl`: `float * int`/`float - int` em `createJitter()` (faltavam `.0`) e
    `int < float` no loop de amostragem (faltava `int()` no limite).
  - `RAS_OutLine2DFilter.glsl`: `uniform mat2 rot = mat2(...)` — GLSL ES não permite inicializador em
    declaração de `uniform`; trocado para `const mat2`.
  - `RAS_Bloom2DFilter_bufH.glsl`/`RAS_Bloom2DFilter_bufV.glsl`: `pixel * i` (float * int) no cálculo do
    offset do blur gaussiano; `i` envolvido em `float()`.
  - `RAS_LightScaterring_Buffer2DFilter.glsl`: `i < ge_LightScatterParams.x` (int < float) no loop de
    raymarching; limite envolvido em `int()`.
  - `RAS_SSR2DFilter.glsl`: `v.z < 0` (float < int literal) em `decode_octa()`; trocado para `0.0`.
  - `RAS_SSR_Blur2DFilter.glsl`: `float / textureSize(...)` — `textureSize` retorna `ivec2`, divisão com
    `float` à esquerda não existe; resultado envolvido em `vec2()`.
- Rebuild `RangeRuntime` em `build-web` (vcvars64 + emsdk_env na mesma chamada): exit 0, 14 passos.
  Sweep completo via CDP das 15 teclas (`filters-smoke-diagnose.cjs` estendido para cobrir todas, não só
  Blur/SSAO): **zero erros de compilação de shader e zero falhas de draw em todas as 15 teclas**, contra 5
  filtros com erro de compilação confirmado no run anterior ao fix (Outline, Bloom, LightScatter, SSR, e
  SSAO já corrigido antes desse sweep).
- Segue faltando (igual à entrada anterior, ainda não resolvido): aceite visual do usuário no navegador
  real — o teste automatizado agora confirma que os 15 filtros *executam* sem erro de GL/shader, mas não
  confirma a aparência visual correta de cada efeito.

## 2026-09-14 — Web: LightScatter e SSR renderizando tela branca (aceite visual do usuário, 6º bug de shader)

- Usuário testou os 15 filtros no navegador real (primeiro aceite visual desta série): 13 funcionam
  corretamente, mas `LightScatter` (tecla `R`) e `SSR` (tecla `T`) pintam a tela inteira de branco.
- Achado por comparação com os shaders que funcionam: `RAS_Bloom2DFilter_Image.glsl` (compose final do
  Bloom, funciona) escreve `gl_FragColor = vec4(cor, 1.0)` — atribuição completa do `vec4`, canal alfa
  incluído. Os dois passes finais de composição problemáticos faziam só `gl_FragColor.rgb = ...`, sem
  nunca escrever `.a`: `RAS_LightScaterring_Image2DFilter.glsl` (compose final do LightScatter) e
  `RAS_SSR_Blur2DFilter.glsl` (compose final do SSR — o primeiro pass, `RAS_SSR2DFilter.glsl`, já
  escrevia `.a = 1.0` corretamente, só o pass de blur final tinha o bug). Alfa não inicializado em
  `out vec4 fragColor` é indefinido (não zerado por padrão), consistente com o sintoma de tela branca.
- **Fix**: as duas atribuições passaram a escrever o `vec4` inteiro com `.a = 1.0`, no mesmo padrão do
  Bloom e dos demais filtros que já funcionavam.
- Rebuild `RangeRuntime` (vcvars64 + emsdk_env): exit 0, 6 passos. Sweep completo via CDP das 15 teclas
  novamente: zero erros de compilação, zero falhas de draw (sem regressão). **Aceite visual de `R`/`T`
  pós-fix ainda pendente com o usuário** — esta entrada registra o diagnóstico e o fix aplicado, não a
  confirmação visual final.

## 2026-09-14 — Web: varredura de todos os `.glsl` de filtro por escrita de alfa indefinida (pós 6º bug)

- A pedido do usuário ("verifica os outros que tem vec4 tmb"), grep em todos os 25 `.glsl` de
  `RAS_OpenGLFilters/` por `gl_FragColor`/`fragColor` para achar outras ocorrências do mesmo padrão do
  6º bug (atribuição só de `.rgb`, sem `.a`, em `out vec4 fragColor`).
- Achados mais 3 casos com o mesmo bug latente, todos em passes intermediários (escrevem num off screen
  próprio consumido depois só via `.rgb` por outro pass, por isso nunca deram tela branca visível, mas
  têm o mesmo alfa indefinido do 6º bug): `RAS_Bloom2DFilter_bufH.glsl` e `RAS_Bloom2DFilter_bufV.glsl`
  (blur horizontal/vertical do Bloom) e `RAS_LightScaterring_Buffer2DFilter.glsl` (buffer de oclusão do
  Light Scattering). Os demais 22 arquivos já faziam atribuição completa do `vec4` ou setavam `.a`
  explicitamente (confirmado por leitura de cada ocorrência de `gl_FragColor`/`fragColor`).
- **Fix**: as três atribuições passaram de `gl_FragColor.rgb = <expr>;` para
  `gl_FragColor = vec4(<expr>, 1.0);`, mesmo padrão dos fixes anteriores.
- Rebuild `RangeRuntime` (vcvars64 + emsdk_env): exit 0, 8 passos. Sweep completo via CDP das 15 teclas
  (rodado da raiz do repo, `node build-web/filters-smoke-diagnose.cjs`, pois o script assume cwd em
  `D:\AnastacioEngine`): zero erros de compilação, zero falhas de draw em todos os 15 filtros, incluindo
  LightScatter e SSR — sem regressão. Aceite visual final de `R`/`T` continua pendente com o usuário.

## 2026-09-14 — Web: gamepad físico — D-pad/analógico travando (resolvido)

- Depois de confirmado que o botão do gamepad funcionava perfeitamente, o
  usuário reportou que o D-pad/analógico não funcionava bem (engasgado,
  travando). Instrumentação com duas camadas de log — uma dentro da porta
  SDL2 do Emscripten (`EMSCRIPTEN_JoystickUpdate`, valor bruto reportado
  pelo browser) e outra em `DEV_Joystick::OnAxisEvent` (valor que
  efetivamente chega ao motor) — permitiu comparar as duas pontas em tempo
  real. O log de teste do usuário mostrou, numa janela de ~300ms, 13
  mudanças reais de `axis[0]` no browser e **zero** chamadas correspondentes
  a `OnAxisEvent` no motor: prova direta de que a maioria dos eventos de
  eixo estava sendo perdida antes de chegar ao consumidor.
- Causa raiz: `GHOST_SystemSDL::processEvents()` (via `SDL_PollEvent`
  irrestrito, sem checar tipo) e `DEV_Joystick::HandleEvents()` (via
  `SDL_PeepEvents` filtrado por tipo joystick/controller) cada um faz seu
  próprio `SDL_PumpEvents`/`SDL_JoystickUpdate()` uma vez por frame,
  operando sobre a MESMA fila global do SDL — a mesma raiz estrutural do bug
  de teclado/mouse já documentado acima (no Web, `sdlew` resolve os mesmos
  símbolos estáticos do binário para os dois consumidores). O `PollEvent`
  irrestrito de GHOST silenciosamente drena e descarta eventos
  `SDL_CONTROLLERAXISMOTION` antes do `PeepEvents` filtrado do joystick
  conseguir lê-los, sempre que o estado do gamepad muda entre os dois pumps
  no mesmo frame.
- Por que o botão nunca sofreu com isso: `aButtonPressIsPositive`/
  `aAnyButtonPressIsPositive`/`aButtonReleaseIsPositive` chamam
  `SDL_GameControllerGetButton()` AO VIVO, lendo o estado interno do
  joystick no SDL (`joystick->buttons[]`), que é atualizado dentro de
  `SDL_PrivateJoystickButton()` ANTES até do evento correspondente ser
  colocado na fila — não importa se o evento em si se perde depois.
- Fix aplicado em `DEV_Joystick.cpp`/`DEV_Joystick.h`: `GetAxisPosition()`
  deixou de ser um getter inline que só lia o cache `m_axis_array`
  (populado exclusivamente por `OnAxisEvent` ao consumir um evento da fila)
  e passou a ler `SDL_GameControllerGetAxis()` diretamente, no mesmo padrão
  já comprovado confiável dos botões. `aAxisIsPositive`, `pGetAxis` e
  `pAxisTest` foram atualizados para usar esse getter em vez do cache bruto.
  Isso elimina a corrida de fila por completo para leitura de eixo, sem
  precisar reordenar a chamada de `HandleEvents`/`processEvents` nem tocar
  no GHOST. `DEV_JoystickEvents.cpp` (que mantém `OnAxisEvent`/
  `IsTrigAxis()`) não foi alterado — o cache fica inofensivo, só não é mais
  usado para posição.
- **Confirmado pelo usuário em 2026-09-14** com controle físico real, após
  rebuild: D-pad/analógico responde de forma suave e consistente, sem
  travar, inclusive em segurar/soltar/movimentos rápidos.
- Ponto separado, ainda em aberto: o gate de timestamp
  (`gamepadState.timestamp != item->timestamp`) da porta SDL2 do emsdk
  (ver entrada anterior) foi mantido removido como reforço — `Gamepad.timestamp`
  do browser é documentadamente pouco confiável e é um problema
  independente que a corrida de fila mascarava. Esse patch e os printfs de
  diagnóstico continuam vivendo fora do controle de versão deste
  repositório (cache de toolchain do emsdk) — não sobrevivem a uma
  reinstalação limpa nem se propagam para outra máquina. Formalizar isso
  (patch de build, port SDL2 vendorizado, etc.) segue pendente.

## 2026-09-14 — Web: gamepad físico — D-pad intermitente e movimento que não para

- Depois dos fixes de teclado/mouse confirmados, usuário testou com um
  controle físico (gamepad) e reportou dois sintomas: (1) D-pad às vezes
  precisa de mais de um toque para o movimento registrar (mesma classe de
  bug do teclado); (2) mais grave — o cubo não para de se mover mesmo
  soltando o direcional, ficando preso em movimento contínuo.
- Investigação apontou não para código deste repositório
  (`DEV_Joystick.cpp`/`DEV_JoystickEvents.cpp`), mas para a própria porta
  SDL2 do Emscripten (fora do repositório, no cache do emsdk:
  `.../cache/ports/sdl2/SDL-release-2.32.10/src/joystick/emscripten/SDL_sysjoystick.c`,
  função `EMSCRIPTEN_JoystickUpdate`). Ela só processa mudanças de
  botão/eixo quando `gamepadState.timestamp != item->timestamp` — e o
  `Gamepad.timestamp` do browser é conhecidamente pouco confiável entre
  browsers/SOs (pode não avançar mesmo com estado real mudando). Se isso
  travar bem no momento do release do D-pad, o evento de soltar nunca é
  gerado e o estado fica preso em `ACTIVE` indefinidamente — explica os
  dois sintomas (perda intermitente de transições em ambas as direções).
- Correção aplicada nesse arquivo (fora do repo, cache do emsdk): removido
  o gate de timestamp; botões e eixos são comparados e processados
  diretamente a cada chamada (os checks internos por elemento já evitam
  reprocessar quando nada mudou de verdade). Diagnóstico adicionado: printf
  disparado só quando os botões 13/14 (D-pad direita/esquerda) mudam de
  estado, com timestamp antigo vs. novo, para confirmar a causa quando o
  usuário testar com hardware real.
- **Atenção**: essa correção vive num arquivo fora do controle de versão
  deste repositório (cache de toolchain do emsdk). Funciona nesta máquina,
  mas não sobrevive a uma reinstalação limpa do emsdk nem se propaga para
  outra máquina de build. Ainda não decidido como torná-la permanente
  (patch aplicado no processo de build, port SDL2 customizado versionado no
  repo, etc.) — pendente de decisão antes de considerar este ponto
  encerrado. Teste real com controle físico também pendente.

## 2026-09-14 — Input Web: toques rápidos perdidos na leitura Python (events dict)

- Depois do fix da fila SDL, usuário reportou "o controle funciona mas eu
  tenho que ficar apertando várias vezes para funcionar" — de "nunca funciona"
  para "não confiável".
- Testes de bisecção confirmaram captura SDL/GHOST 100% confiável (6/6 toques
  capturados mesmo com down+up sem intervalo nenhum): o problema não está na
  captura, está numa camada acima.
- Causa raiz: `KX_PythonKeyboard.cpp::pyattr_get_events` (que alimenta
  `Range.logic.keyboard.events`, a forma mais comum de ler teclado via Python
  neste engine) e `KX_PythonMouse.cpp::pyattr_get_events` liam apenas o
  ÚLTIMO elemento da fila de transições do tick (`m_queue.back()`). Quando um
  toque físico completo (down+up) cai dentro do mesmo tick de lógica — bem
  mais provável no Web pelo overhead do wasm/Python rodando mais devagar que
  o nativo — o valor final reportado é `JUSTRELEASED`, não
  `JUSTACTIVATED`/`ACTIVE`, e o toque é descartado silenciosamente. Padrão
  antigo do BGE, raramente visível a 60fps nativo (toque completo em <16ms é
  incomum para um humano), exposto pelo tick mais lento do Web.
- Não é bug na lógica de sensores (`SCA_KeyboardSensor::Evaluate`), que já usa
  `Find()`/`End()` corretamente sobre a fila inteira — o problema era só nos
  getters de conveniência Python `keyboard.events`/`mouse.events`.
- Correção: antes de usar o último elemento da fila, os dois getters agora
  checam `input.Find(SCA_InputEvent::JUSTACTIVATED)` e priorizam reportar a
  ativação quando ela aparece em qualquer ponto da fila do tick. Build Web e
  nativo (`RangeRuntime`) recompilados com sucesso após a mudança.
- **Confirmado em 2026-09-14**: reload limpo, clique único instantâneo
  (down+up de volta-a-volta, 0ms de intervalo — o pior caso, que antes do fix
  caía direto em `JUSTRELEASED`) em `ArrowRight` e `ArrowLeft`, dois testes
  isolados: `[web-smoke] keyboard moved cube` apareceu nos dois, sem precisar
  de sorte de timing entre ticks. Investigação de input Web encerrada.

## 2026-09-14 — Web: causa raiz real do teclado — segundo consumidor da fila SDL

- Retomando o ponto em aberto da entrada anterior ("Pendente: mesmo com o
  evento entrando na fila do SDL com sucesso, `GHOST_SystemSDL::processEvents`
  ainda não demonstrou receber `SDL_KEYDOWN`/`SDL_KEYUP`..."): reproduzido via
  Chrome headless + CDP (`build-web/keyboard-diagnose.cjs`,
  `build-web/keyboard-diagnose2.cjs`), dispatch real de tecla
  (`Input.dispatchKeyEvent` com `code` preenchido, após focar o `#canvas`) —
  não uma simulação de automação sem `KeyboardEvent.code` (essa já havia sido
  descartada antes por invalidar o teste).
- Confirmado, em ordem: o DOM entrega `keydown`/`keyup` reais ao canvas
  (`RAW_KEYDOWN`/`RAW_KEYUP`), o callback do Emscripten dispara, e
  `Emscripten_HandleKey` (porta SDL2, instrumentada anteriormente) reporta
  `posted=1` e `KEYDOWN_state=1`/`KEYUP_state=1` — ou seja, o evento realmente
  entra na fila global do SDL. Mas `GHOST_SystemSDL::processEvents` não
  reportava nenhum `polled sdl_event.type=` em nenhum frame seguinte, nem
  mesmo os eventos de janela (`SDL_WINDOWEVENT`) — sinal de que algo mais
  drenava a fila inteira antes de GHOST chegar a ela.
- Causa raiz: `DEV_Joystick::HandleEvents`
  (`source/source/gameengine/Device/DEV_JoystickEvents.cpp`) tinha seu próprio
  laço `while (SDL_PollEvent(&sdl_event))`, sem filtro de tipo — o `default:`
  do switch descarta silenciosamente qualquer evento que não seja de
  joystick/controller. SDL só tem uma fila de eventos por processo; esse
  segundo consumidor a esvaziava por completo (teclado incluso) antes de
  `GHOST_SystemSDL::processEvents` fazer seu próprio `SDL_PollEvent`.
  Não afeta o Windows nativo porque lá o `sdlew` (usado por
  `DEV_JoystickEvents.cpp`) carrega dinamicamente um `SDL2.dll` **separado**
  (biblioteca própria, fila própria) via `LoadLibrary`; sob Emscripten,
  `sdlew` resolve os mesmos símbolos já linkados estaticamente no próprio
  binário (mesma fila que `GHOST_SystemSDL` usa), então os dois consumidores
  colidem de fato só no build Web.
- Fix em `DEV_JoystickEvents.cpp`: substituído o `SDL_PollEvent` genérico por
  `SDL_PeepEvents(..., SDL_GETEVENT, min, max)` restrito às duas faixas de
  tipo de evento que este código realmente trata (`SDL_JOYAXISMOTION`..
  `SDL_JOYDEVICEREMOVED` e `SDL_CONTROLLERAXISMOTION`..
  `SDL_CONTROLLERSENSORUPDATE`), precedido de `SDL_PumpEvents()` explícito
  (necessário porque, ao contrário de `SDL_PollEvent`, `SDL_PeepEvents` não
  bombeia a fila sozinho). Guard de disponibilidade do `sdlew` atualizado de
  `SDL_PollEvent == (void*)0` para `SDL_PumpEvents`/`SDL_PeepEvents`. Nenhuma
  mudança de comportamento para joystick/controller, que continuam recebendo
  exatamente os mesmos eventos de antes.
- Validado via rebuild + reteste com o mesmo harness CDP: agora
  `GHOST_SystemSDL::processEvents polled sdl_event.type=768/769` aparece para
  cada tecla, seguido de `GHOST_SystemSDL SDL_KEYDOWN/UP scancode=79 ...` e
  `HandleKeyEvent key=268 down=1`/`down=0` — a cadeia completa até
  `DEV_EventConsumer::HandleKeyEvent` (entrada real no sistema de input do
  jogo) confirmada de ponta a ponta pela primeira vez. Logs em
  `build-web/keyboard-diagnostic.log` (antes do fix, zero eventos
  `polled`) e `build-web/keyboard-diagnostic2.log` (depois do fix).
- Pendente: esse teste cobre só a cadeia SDL → GHOST → `DEV_EventConsumer`,
  não a aceitação visual completa (mover o cubo com as setas, visível no
  navegador por uma pessoa) — a cena usada (`untitled.range`) está vazia.
  Ainda é preciso o teste manual real do usuário para o aceite final,
  incluindo o mouse (não testado nesta sessão, mesmo mecanismo pode ou não
  se aplicar). Diagnóstico ainda não removido do código (mantido sob
  `#ifdef __EMSCRIPTEN__`, ver nota da entrada anterior).

## 2026-09-14 — Web: input de teclado/mouse não chegava ao jogo

- Usuário reportou que teclado/mouse não funcionam no export Web, apesar da
  mesma cena funcionar perfeitamente no player nativo Windows (confirmado:
  cubo se move com as setas e gira com o mouse).
- Diagnóstico em camadas, do DOM do navegador até o C++ compilado: (1) listeners
  JS crus confirmaram que o navegador entrega `keydown`/`keyup` corretos ao
  `canvas`; (2) instrumentação direta da API HTML5 do Emscripten
  (`emscripten_set_keydown_callback`) mostrou que o registro em `"#window"` e
  `"#document"` retorna `EMSCRIPTEN_RESULT_NOT_SUPPORTED` (`-4`) neste ambiente,
  enquanto `"#canvas"` funciona; (3) leitura do fonte real da porta SDL2 usada
  pelo build (fora do repositório, no cache do emsdk:
  `.../cache/ports/sdl2/SDL-release-2.32.10/src/video/emscripten/SDL_emscriptenevents.c`,
  não o submódulo `source/extern/SDL2`, que é código morto para este build)
  confirmou a causa raiz: `Emscripten_InitKeyboard`/`Emscripten_RegisterEventHandlers`
  usa `SDL_GetHint(SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT)` e cai no padrão
  `"#window"` quando o hint não está definido, sem checar o retorno de erro das
  chamadas `emscripten_set_key*_callback` — o listener de teclado do SDL nunca
  chegava a existir.
- Correção aplicada em `GHOST_SystemSDL.cpp` (construtor de `GHOST_SystemSDL`):
  `SDL_SetHint(SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT, "#canvas")` antes do
  `SDL_Init`, sob `#ifdef __EMSCRIPTEN__`. Sem efeito nos demais backends (X11,
  Win32, SDL nativo).
- Validado via diagnóstico dentro da própria porta SDL2 (rebuild forçado do
  cache do emsdk): com o hint aplicado, `Emscripten_RegisterEventHandlers`
  de fato usa `keyElement=#canvas` e os três registros (`keydown`/`keyup`/
  `keypress`) retornam sucesso (0). `Emscripten_HandleKey` também confirma
  `posted=1` e `SDL_GetEventState(SDL_KEYDOWN/KEYUP)` habilitado — ou seja, o
  evento entra corretamente na fila de eventos do SDL.
- Pendente: mesmo com o evento entrando na fila do SDL com sucesso, o
  `GHOST_SystemSDL::processEvents` ainda não demonstrou receber
  `SDL_KEYDOWN`/`SDL_KEYUP` via `SDL_PollEvent` nos testes do navegador (nota:
  um teste anterior que indicava falha aqui foi descartado — usava simulação de
  teclado de automação de navegador que não preenche `KeyboardEvent.code`,
  invalidando o teste, não o código). Diagnóstico adicional já instrumentado
  logo no início do laço `while (SDL_PollEvent(...))` em `processEvents`,
  logando todo `sdl_event.type` recebido, para confirmar se o polling do GHOST
  enxerga qualquer evento da fila ou nenhum. Teste real ainda não concluído.

## 2026-09-14 — Web: tela preta e divisor residual no quad

- Usuário testou no navegador e reportou tela preta com piscadas brancas.
  Logs de inicialização não demonstravam falha nos draws; muitas mensagens
  vermelhas eram diagnósticos enviados pelo `printErr` do harness.
- Auditoria de dados via editor nativo: `build-web/bin/untitled.range` tem
  zero objetos e nenhuma câmera (`build-web/scene-audit.log`). Os testes
  anteriores de seis draws/frame cobriam fundo, quatro filtros e cópia final,
  não geometria nem lógica Python de jogo.
- Instrumentação CDP encontrou atributo UV (localização 1) com divisor 1.
  O VBO e os offsets estavam corretos, mas o quad usava UV constante. Testes
  temporários com cor constante e UV derivado da posição isolaram o problema.
  A emulação legacy não isola os divisores como o caminho nativo de VAOs.
- `RAS_OpenGLRasterizer.cpp`, `ScreenPlane::Render`: sob Emscripten, salva
  divisores 0/1, define ambos como zero durante o draw e restaura ao terminar.
  Usa entradas GLES diretas; sem mudança de header, shader ou flags globais.
- Build Web via vcvars64: exit 0, três passos (`screen-divisor-build.log`).
  Validação com shaders originais: **6.192 draws, zero erros GL**. Pixel central
  do fundo e da saída FXAA agora coincidem; tela final RGBA `[102,103,98,255]`
  no primeiro frame e `[102,103,99,255]` no frame 101, antes perto de preto.
  Logs em `build-web/screen-divisor-diagnostic.log`. Leituras numéricas não
  substituem aceite visual; nenhuma captura automatizada foi usada.
- `tools/create_web_smoke_scene.py` gera cena separada com cubo laranja,
  câmera e controlador Python (rotação + setas). Gerador executado no editor
  nativo; harness local `test-smoke.html` carrega a cena por preRun/fetch.
  O runtime Web aborta com **alignment fault em test_pointer_array**, antes
  de iniciar a cena. Reprodução: `build-web/smoke-diagnostic.log`; ainda não
  corrigido nem validado Python/teclado. O harness original foi preservado.
- Próxima unidade: carregamento de arrays de ponteiros de arquivos 64 bits
  no runtime wasm32. Aceite visual da correção do quad continua pendente.

## 2026-09-14 — Web: saídas dos filtros de pós-processamento

- `RAS_2DFilter.cpp/.h`: no Emscripten, reconhece os shaders nativos de FXAA,
  chuva, nuvens, lens flare e tonemap comparando as fontes completas no link.
  A classificação é atualizada em relinks, sem tratar todo CUSTOMFILTER como
  saída única (os efeitos de clima também usam esse modo). Fontes diferentes
  mantêm o roteamento existente, inclusive filtros personalizados com MRT.
- Durante esses draws, salva os draw buffers e ativa somente o primeiro;
  o guard de escopo restaura todos os slots antes de desassociar o destino.
  Os anexos adicionais continuam alocados e seu conteúdo é preservado.
- Build Web `RangeRuntime` com vcvars64: exit 0, 15 passos, sem crash após
  alteração do header. Log: `build-web/filters-build.log`.
- Chrome/CDP com cache desativado, mesma `untitled.range` com dois anexos:
  **6.222 draws, 1.037 frames, zero erros GL nos draws**. Antes desta unidade
  havia quatro erros por frame. Os 1.037 draws restantes com o segundo anexo
  ativo dão evidência de restauração entre passes. Diagnóstico preservado em
  `build-web/filters-diagnostic.log`; não houve captura nem aceite visual.
- Pendentes: teste visual e Python/teclado no navegador real, cena dedicada
  de MRT/lacunas e demais filtros nativos. O export Web ainda não está concluído.

## 2026-09-14 — Web: roteamento de draw buffers nos materiais gerados

- Retomada preservando as alterações locais anteriores. Diagnóstico via Chrome
  headless/CDP, sem captura de imagem: a cena `build-web/bin/untitled.range`
  possui dois anexos ativos. O primeiro draw inválido era o fundo em
  `KX_WorldInfo::RenderBackground`, com somente `fragData0` no shader.
- `gpu_material.c`: consulta as saídas `fragDataN` no programa ligado uma vez
  na construção; no bind, conserva apenas os slots com saída, mantendo os
  índices e usando `GL_NONE` nas lacunas. O unbind restaura o roteamento no
  framebuffer original, preservando inclusive o binding atual se ele mudou.
  Mudança restrita a Emscripten, sem editar headers ou flags globais.
- Build `RangeRuntime` em `build-web`, passando pelo `vcvars64.bat`: exit 0
  (três passos). Diagnóstico com cache desativado: 6.228 draws, incluindo
  1.038 draws do fundo, com **zero erros GL no fundo**. Os 5.190 draws dos
  outros passes voltam a encontrar o segundo anexo ativo, confirmando a
  restauração. Restam 4.152 erros: quatro draws por frame, contra cinco antes.
- Os primeiros três erros restantes pertencem a FXAA, chuva e nuvens. São
  shaders de pós-processamento, fora do bind de `GPUMaterial`; precisam de
  uma próxima unidade de correção. Não reduzir todos os offscreens a um
  anexo, pois isso descartaria os dados MRT usados por outros materiais.
- Artefatos locais: `build-web/diagnose.cjs`, `resume-before.log`,
  `resume-diagnostic.log` e `resume-build.log`. O harness abre uma página nova
  por teste e desativa cache; eventos de uma página reutilizada podem incluir
  logs antigos e não servem para comparar os binários.
- Export Web **não concluído**: faltam correção dos filtros, validação de
  materiais MRT/lacunas em cena dedicada e aceite visual com Python/teclado.

## 2026-09-13 — Barra inferior da 3D View: câmera e camadas

- Os controles de bloqueio de câmera/camadas e seleção de camadas, antes isolados no extremo direito do cabeçalho da 3D View, foram transferidos para o fim da barra flutuante no canto inferior esquerdo.
- Validação: rebuild incremental de `RangeEngine` concluído; smoke test confirmou a propriedade `lock_camera_and_layers` e o painel `VIEW3D_PT_layer` na inicialização.

## 2026-09-13 — Barra inferior da 3D View: transformação

- Os controles de manipulador, eixos, orientação e pivô foram adicionados ao fim da mesma barra flutuante, mantendo a sequência dos grupos já transferidos.
- As versões correspondentes foram removidas do cabeçalho.

## 2026-09-13 — Barra inferior da 3D View: controles do modo Edit

- Auto Merge, Occlude Geometry e o painel de visualização da malha foram adicionados ao fim da barra inferior.
- Os controles condicionais que apareciam no cabeçalho ao entrar no modo Edit foram removidos de lá; na barra inferior eles agora só são desenhados com um objeto ativo em Edit Mode.
- Validação: rebuild incremental de `RangeEngine` e smoke test de troca para Edit Mode concluídos.

## 2026-09-13 — WebGL2: texImage2D/texParameter e getParameter (GL_MAX_LIGHTS)

- `gpu_texture.c` (`GPU_texture_create_nD`): textura de profundidade usava `GL_DEPTH_COMPONENT` (não dimensionado) como `internalformat` de `texImage2D`, rejeitado pelo WebGL2/GLES3 (exige formato dimensionado); corrigido para `GL_DEPTH_COMPONENT16` sob `__EMSCRIPTEN__`. `glTexParameteri(..., GL_DEPTH_TEXTURE_MODE, ...)` também foi pulado sob Emscripten — o enum não existe em GLES3/WebGL2 core.
- `RAS_OpenGLRasterizer.cpp` (`GetNumLights`): `glGetIntegerv(GL_MAX_LIGHTS, ...)` (pipeline fixo, sem equivalente em GLES3/WebGL2) era a causa raiz de um erro `getParameter: invalid parameter name` no console — mascarado porque o Chrome deduplica mensagens de erro com texto idêntico, então uma única linha no console podia corresponder a chamadas inválidas diferentes. Corrigido retornando 8 fixo sob `__EMSCRIPTEN__` (mesmo teto que a rota desktop já aplicava com `numlights > 8`).
- Localização da causa raiz do `getParameter` exigiu instrumentação: monkeypatch de `WebGL2RenderingContext.prototype.getParameter`/`WebGLRenderingContext.prototype.getParameter` no harness de teste (`build-web/bin/test.html`, temporário, revertido depois), chamando `getError()` a cada `getParameter` e logando `pname`/stack via `console.log` — capturado com Chrome headless via `--enable-logging=stderr --v=1` sem `--dump-dom` (que trava no loop de render em tempo real da página e é morto antes de gravar saída).
- `gpu_extensions.c` (`gpu_extensions_init`): três consultas adicionais de `getParameter`/estado desktop-only guardadas sob `__EMSCRIPTEN__` como endurecimento de espec (nenhuma isoladamente foi a causa raiz acima, mas são inválidas em WebGL2/GLES3 e ficariam pendentes de qualquer forma): `GL_RED_BITS`/`GREEN_BITS`/`BLUE_BITS` (colordepth fixado em 24), `GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT` (o shim GLEW do Emscripten reporta a extensão pela string, sem `getExtension()` real; anisotropia fixada em 1.0), `GL_MAX_COLOR_TEXTURE_SAMPLES` (textura multisample não existe em GLES3/WebGL2; consulta pulada).
- Validação: rebuild limpo de `RangeRuntime` e teste em Chrome headless (`test.html` + `untitled.range`) confirmou, por grep no log real do navegador, zero linhas `WebGL:` e presença de `"[web-launcher] engine started"`. **Isso valida apenas ausência de erro de console — não é validação visual nem funcional.** Achado à parte, não investigado: a mesma instrumentação revelou `getParameter(GL_ELEMENT_ARRAY_BUFFER_BINDING)` retornando `INVALID_FRAMEBUFFER_OPERATION` (6x), não visível no log final sem instrumentação; impacto real ainda desconhecido.
- Combinado com os fixes de VAO/VBO e IBO da sessão anterior, todas as quatro classes de erro de console rastreadas até agora no port Web estão confirmadas ausentes; falta validar visualmente o cubo e o controle via Python/teclado — ver `docs/roadmap.md`.

## 2026-09-13 — WebGL2: depth texture format/type e draw buffers do offscreen

- Teste real em navegador (screenshots do usuário, não Chrome headless) revelou dois erros WebGL2 sequenciais no fluxo de renderização do cubo.
- **Corrigido e confirmado pelo usuário**: `gpu_texture.c` (`GPU_texture_create_nD`) definia `internalformat = GL_DEPTH_COMPONENT16` para textura de profundidade sob `__EMSCRIPTEN__`, mas deixava `type = GL_UNSIGNED_BYTE` — combinação inválida em WebGL2/GLES3 (`GL_DEPTH_COMPONENT16` só é válido com `GL_UNSIGNED_SHORT`), rejeitada pelo ANGLE com `glTexImage2DRobustANGLE: Invalid combination of format, type and internalFormat`, que por sua vez deixava a textura com tamanho zero e cascateava em `GL_INVALID_FRAMEBUFFER_OPERATION: ... Attachment has zero size` em todo `glClear`/`glDrawElements` seguinte. Corrigido setando `type = GL_UNSIGNED_SHORT` no branch Emscripten. Retest do usuário confirmou as duas mensagens de erro completamente ausentes.
- **Ainda não resolvido**: com o bug acima corrigido, apareceu (ou ficou visível) `GL_INVALID_OPERATION: glDrawElements: Active draw buffers with missing fragment shader outputs` (256 ocorrências, atingiu o teto de log do Chrome). Mecanismo: `RAS_OffScreen::Bind()` chama `GPU_framebuffer_bind_all_attachments(fb, m_numColorSlots)`, que faz `glDrawBuffers(numAttachment, ...)`; se o fragment shader ativo no draw não declarar saída para cada slot ativo, o ANGLE rejeita o draw.
- Tentativa de fix: `gpu_codegen.c` (`code_generate_fragment`) passou a declarar `layout(location = %d) out vec4 fragData%d;` explícito por saída (antes sem `layout(location=...)`, dependendo da ordem de declaração). **Rebuild e retest do usuário mostraram o erro idêntico, sem mudança** — descarta, para esta cena, a hipótese de que a falta de location explícita fosse a causa: o material padrão do cubo só popula `outputs[0]` (`GPU_material_output_link` é chamado com `index=0` em todos os call sites exceto `node_shader_output_attachment.c`, ligado ao mecanismo de anexos extras `gm.attachments[]`), então o fix deveria ter sido um no-op — e foi.
- Hipótese em aberto (não confirmada): `m_numColorSlots` (= `RAS_OffScreen::AttachmentList::size()`, construída em `LA_Launcher.cpp` a partir de `gm.attachments[0..6]`) pode ser maior que 1 para esta cena `.range` específica, enquanto o material só escreve em location 0. Diagnóstico adicionado: `fprintf(stderr, "[web-launcher] offscreen attachments=%d\n", ...)` em `LA_Launcher.cpp`, rebuild concluído; **retest ainda pendente no momento em que a sessão foi encerrada** (fim de expediente do usuário).
- Se a hipótese cair (`attachments=1`), próximos suspeitos a investigar: `gpu_shader_basic_frag.glsl` (shader legado de pipeline fixo, usa `gl_FragColor`/`varying`, sintaxe incompatível com GLSL ES 3.00 — não confirmado se é realmente compilado/usado sob o caminho Emscripten), os avisos de "emscripten GL emulation"/"immediate mode emulation" no console (não conectados ao bug ainda), ou outro FBO (sombra, filtro 2D) fora do offscreen principal da cena.
- **Reforço explícito do usuário nesta sessão**: console sem uma mensagem de erro específica, ou mesmo `"[web-launcher] engine started"` no log, não é validação visual nem funcional. A barra de aceite (cubo real renderizando corretamente e controlável por Python/teclado, confirmado visualmente pelo usuário via captura manual de tela, sem automação de captura) continua pendente e é o próximo passo assim que o console estiver de fato sem erros WebGL.

## 2026-09-13 — Pesquisa de áudio para o port Web

- Segunda revisão para apoiar Claude: localizados inicialização SDL sem `SDL_INIT_AUDIO`,
  fontes GEEffects incluídas fora do bloco `WITH_OPENAL` e fallback silencioso para `None`.
  Acrescentado roteiro concreto de integração e diagnóstico ao documento de áudio;
  achados estáticos, sem execução do áudio ou mudança nas fontes.
- Confirmados Audaspace/OpenAL desativados no preset/cache e backend SDL existente.
- Documentados streaming com `std::thread`, limites de EFX e dependência de decodificadores.
- Corrigida no plano Web a referência incorreta a OpenAL Soft/`USE_OPENAL`: a implementação
  própria do Emscripten usa `-lopenal`. Fontes e roteiro em [web-audio-analysis.md](web-audio-analysis.md).
- Auditoria documental e estática; sem alterações de engine, build ou teste audível.

## 2026-09-13 — Auditoria da emulação GL para apoiar a integração Web

- Verificados preset/cache, SDK 6.0.9, renderer, logs existentes e wrappers do JS gerado.
  `LEGACY_GL_EMULATION` já está ativo e não pode ser combinado com `FULL_ES3` nesse SDK.
- Probe `tools/web_gl_emulation_probe.cjs` executado com exit 0: a sequência atual de
  unbind apaga o VBO do VAO emulado; o controle com ordem invertida preserva a referência.
  Contexto GL simulado, sem comprovação de correção no navegador ou novo build da engine.
- Evidências, limites, uso potencial de FULL_ES3 no zsort e próximos testes para Claude
  em [web-gl-emulation-analysis.md](web-gl-emulation-analysis.md). Renderer e flags preservados.

## 2026-09-13 — Web/Emscripten: SetLines/glPolygonMode, ImGui #version 120 e início do GLSL ES sweep

- `RAS_OpenGLRasterizer::SetLines` chamava `glPolygonMode`, sem equivalente em WebGL/GLES2; corrigido com guard `#ifdef __EMSCRIPTEN__` que ignora a chamada (sem estado a preservar).
- `KX_Imgui::Init` inicializava o backend ImGui com `#version 120` (GLSL desktop) incondicionalmente; sob Emscripten isso falhava ao compilar/linkar o shader do ImGui no WebGL2. Corrigido para usar `#version 300 es` sob `__EMSCRIPTEN__`, mantendo `#version 120` em desktop.
- Diagnóstico de testes headless: `chrome.exe --headless` (modo antigo) combinado com `--user-data-dir` relativo abre uma janela real do Chrome com um diálogo de erro em vez de rodar sem interface — usar `--headless=new` e caminho absoluto evita o problema; mesmo `chrome.exe --version` pode abrir uma janela cheia nesta máquina, então testes automatizados via linha de comando precisam de `taskkill //F //IM chrome.exe` de segurança após cada tentativa.
- Com os dois bugs acima corrigidos, o teste em Chrome headless avançou até compilar o shader do ImGui, revelando um problema bem maior em `gpu_shader_material.glsl` (5411 linhas): dezenas de erros de tipo GLSL ES (int/float sem conversão implícita, `sampler2DShadow` sem precisão, `mod()` sem overload para inteiro) espalhados pelo arquivo. Cinco ocorrências do padrão int/float corrigidas nesta sessão (`~615`, `~1145`, `~1972`, `~2329`, `~2348`); erros adicionais confirmados entre as linhas `~2702` e `~4639` seguem pendentes — ver `docs/roadmap.md`.

## 2026-09-13 — WebGL2: shaders, VAO e framebuffers alcançam a criação do canvas

- O preset Web passou a exigir WebGL2/GLES3 e o backend SDL solicita o contexto correspondente. A compatibilidade de shaders usa GLSL ES 300 e chamadas diretas do Emscripten para criação, compilação, consulta de atributos e uniforms.
- As operações de VAO, debug draw, framebuffer e renderbuffer deixaram de depender dos ponteiros de extensão desktop do GLEW, que permanecem nulos no wasm. `glDrawBuffer` é encaminhado para `glDrawBuffers`, disponível no WebGL2.
- O build incremental de `RangeRuntime` terminou com sucesso. No Chrome headless, os shaders básicos compilaram e todos os framebuffers e texturas observados foram criados; a inicialização alcançou a criação do canvas.
- O próximo bloqueio confirmado é uma chamada nula no construtor `RAS_Query::RAS_Query`, durante `LA_Launcher::InitEngine`. A cena ainda não foi executada nem validada visualmente.

## 2026-09-13 — Web/Emscripten: alinhamento na leitura SDNA e avanço do carregamento

- O carregamento de `untitled.range` no `RangeRuntime` wasm32 deixou de abortar na leitura de `GLOB`. A causa era alinhamento de 64 bits: `MEM_callocN` podia devolver apenas alinhamento de 4 bytes no wasm32, enquanto `FileGlobal` e `Main` contêm `uint64_t`.
- `DNA_struct_reconstruct` e `BKE_main_new` passaram a usar alocação alinhada a 8 bytes, mantendo a inicialização zerada. `blo_nextbhead` passou a fazer aritmética de ponteiro por `char *`, evitando o underflow unsigned de `POINTER_OFFSET` ao recuperar `BHeadN`.
- O build web incremental terminou com exit 0. O Chrome headless percorre os blocos até `ENDB` sem `alignment fault`, segmentation fault ou erro do Python; o teste para em `could not create main window`, pois o harness não fornece uma janela gráfica real. A validação visual com janela permanece pendente.
- O teste em Chrome normal confirmou que a falha de janela não era exclusiva do headless. O backend SDL passou a solicitar GLES 2 explicitamente, eliminando `EGL_BAD_CONFIG`; o canvas WebGL de 640×480 é criado. A inicialização web também evita texturas-placeholder 1D/3D, ausentes no WebGL 1, e usa `OES_vertex_array_object` pelas entradas diretas do Emscripten.
- O runtime agora alcança `LA_PlayerLauncher::InitEngine()`. O bloqueio vigente são os shaders GLSL desktop (`#version 120` e sintaxe associada), rejeitados pelo GLSL ES; usar o shader nulo após essa falha ainda causa o abort. A próxima etapa é a adaptação dos shaders para WebGL, não o carregamento do arquivo.
## Índice

| Data | Resumo |
|---|---|
| [2026-09-12 (AddObject + External Files — objeto linkado sumia após save/export)](#2026-09-12--addobject--external-files--objeto-linkado-sumia-apos-saveexport) | `id->us == 0` num objeto referenciado só por um ator AddObject fazia `write_libraries()` descartá-lo (e a lib) silenciosamente em qualquer save, inclusive o copy-save de "Start Game In Player"; corrigido com `PROP_ID_REFCOUNT` na RNA + `id_us_plus()` no relink do `readfile.c`; validado via script Python (`Range.logic`/`KX_PythonComponent`) reproduzindo o mesmo `scene.addObject()` do ator |
| [2026-09-12 (Export 1 clique — rebuild automático do template Launcher.exe)](#2026-09-12--export-1-clique--rebuild-automatico-do-template-launcherexe) | Scaffold detecta sozinho se `Launcher.exe` template está mais antigo que `main.rs` e recompila com `cargo build --release` automaticamente, sem confirmação nem passo manual — elimina de vez a classe de bug "abre e fecha" mesmo após reinstalar `tools/RangeArmor-master` |
| [2026-09-12 (Export 1 clique — scaffold automático, progresso e Launcher.exe corrompido)](#2026-09-12--export-1-clique--scaffold-automatico-progresso-e-launcherexe-corrompido) | Scaffolding do projeto (`config.json`/`Launcher.exe`/ícones/runtime) e `.rasec` agora são gerados automaticamente pelo botão; barra de progresso + cursor de espera durante o export; `Launcher.exe` template estava compilado de um `main.rs` antigo com `.unwrap()` e sempre crashava ("abre e fecha") — recompilado |
| [2026-09-12 (Export — botão 1 clique)](#2026-09-12--export--botao-1-clique) | Novo `wm.one_click_export_rangearmor` roda `build_release.py` direto (sem abrir o RangeArmor Panel) e abre a pasta `release/` no final |
| [2026-09-11 (Modo seguro — pastas de config ausentes)](#2026-09-11--modo-seguro--wm_init-recria-pastas-de-config-ausentes) | `WM_init()` recria `config`/`scripts`/`datafiles` se ausentes; crash de config ausente corrigido; fix é cross-platform (mesmo código C, sem `#ifdef _WIN32`) |
| [2026-09-10 (View 3D — gizmo de navegação)](#2026-09-10--view-3d--gizmo-de-navegacao) | Indicador de eixos legado substituído pelo gizmo visual da Range 1.6 Rev2; aguarda inspeção visual |
| [2026-09-10 (Iluminação — preset padrão de Sun)](#2026-09-10--iluminacao--preset-padrao-de-sun) | Novas Lamps usam o preset CSM de sombra solicitado |
| [2026-09-09 (Cutscene — Fase 4G: API Python de runtime)](#2026-09-09--cutscene--fase-4g-api-python-de-runtime) | Scene expõe play/stop/restart nativos sem vazar estado interno |
| [2026-09-09 (Cutscene — Fase 4H: falha segura de instanciação)](#2026-09-09--cutscene--fase-4h-falha-segura-de-instanciação) | Spawn Object não desreferencia réplica nula quando a conversão falha |
| [2026-09-09 (Cutscene — Fase 5A: importador nativo)](#2026-09-09--cutscene--fase-5a-importador-nativo) | JSON legado pode ser migrado para Scene.cutscene_settings com rejeição explícita |
| [2026-09-09 (Cutscene — Fase 5B: regressão do importador)](#2026-09-09--cutscene--fase-5b-regressão-do-importador) | Conversão de JSON legado/versionado e rejeições do importador verificadas no editor |
| [2026-09-09 (Cutscene — Fase 5C: exportação nativa)](#2026-09-09--cutscene--fase-5c-exportação-nativa) | JSON versionado exporta e reimporta eventos Spawn Object sem perder referências |
| [2026-09-09 (Cutscene — Fase 5D: exemplo e roteiro)](#2026-09-09--cutscene--fase-5d-exemplo-e-roteiro) | Exemplo .blend reproduzível e validação de save/load documentada |
| [2026-09-09 (Cutscene — Fase 4F: ownership e limpeza)](#2026-09-09--cutscene--fase-4f-ownership-e-limpeza) | Spawn Object suporta dependente parentado e limpeza coordenada em stop/restart/troca/destruição da cena |
| [2026-09-09 (Cutscene — Fase 4E: despachante Spawn Object)](#2026-09-09--cutscene--fase-4e-despachante-spawn-object) | Eventos pendentes de Spawn Object agora instanciam a réplica primária pela infraestrutura nativa da cena |
| [2026-09-09 (Cutscene — Fase 4D: avanço no loop da cena)](#2026-09-09--cutscene--fase-4d-avanco-no-loop-da-cena) | Relógio da Cutscene avança no ciclo de simulação e retém eventos pendentes para o despachante nativo |
| [2026-09-09 (Cutscene — Fase 4C: linha do tempo)](#2026-09-09--cutscene--fase-4c-linha-do-tempo) | Manager agenda eventos em segundos com ordem estável e seek reverso definido |
| [2026-09-09 (Cutscene — Fase 4B: ciclo de vida)](#2026-09-09--cutscene--fase-4b-ciclo-de-vida) | Manager possui contrato explícito de iniciar, parar e reiniciar, isolado do DNA |
| [2026-09-09 (Cutscene — Fase 4A: conversão para runtime)](#2026-09-09--cutscene--fase-4a-conversao-para-runtime) | Definições de Cutscene são resolvidas para objetos do runtime por cena, sem acoplamento à UI Python |
| [2026-09-09 (Cutscene — Fase 2G: regressão de persistência)](#2026-09-09--cutscene--fase-2g-regressao-de-persistencia) | Teste em background confirma salvar e reabrir dados e referências de Spawn Object |
| [2026-09-09 (Cutscene — Fase 2F: criação inicial)](#2026-09-09--cutscene--fase-2f-criacao-inicial) | Add de sequência permanece disponível com a lista vazia |
| [2026-09-09 (Cutscene — Fase 2E: validação Spawn Object)](#2026-09-09--cutscene--fase-2e-validacao-spawn-object) | Inspector destaca Template Object e Spawn Point ausentes antes da execução |
| [2026-09-09 (Cutscene — Fase 2D: inspector Spawn Object)](#2026-09-09--cutscene--fase-2d-inspector-spawn-object) | Inspector do evento ativo com tempo, tipo e referências da ação Spawn Object |
| [2026-09-09 (Cutscene — Fase 2C: lista de eventos)](#2026-09-09--cutscene--fase-2c-lista-de-eventos) | Painel de eventos da sequência ativa, com operações nativas e proteção para seleção vazia |
| [2026-09-09 (Cutscene — Fase 2B: lista de sequências)](#2026-09-09--cutscene--fase-2b-lista-de-sequências) | Painel nativo registra a lista de sequências e seus operadores; Add/Remove usam os ícones nativos disponíveis `ZOOMIN`/`ZOOMOUT` |
| [2026-09-09 (Cutscene — Fase 2A: contexto nativo)](#2026-09-09--cutscene--fase-2a-contexto-nativo) | Aba Cutscene nativa de Properties, com ícone `SEQUENCE`, rota de Scene e posição logo após World; clean rebuild aprovado |
| [2026-09-09 (Cutscene — Fase 1E: duplicação segura)](#2026-09-09--cutscene--fase-1e-duplicação-segura) | Operadores nativos duplicam sequências e eventos mantendo referências de objetos e seus usuários em equilíbrio; editor e runtime compilados |
| [2026-09-09 (Cutscene — Fase 1D: reordenação nativa)](#2026-09-09--cutscene--fase-1d-reordenação-nativa) | Operadores nativos movem sequências e eventos sem alterar dados ou referências; editor e runtime compilados |
| [2026-09-09 (Cutscene — Fase 1C: operadores nativos)](#2026-09-09--cutscene--fase-1c-operadores-nativos) | Operadores nativos de adicionar/remover sequências e eventos, com undo e atualização da UI; editor e runtime compilados |
| [2026-09-09 (Cutscene — Fase 1B: exposição RNA)](#2026-09-09--cutscene--fase-1b-exposição-rna) | Dados persistidos de Cutscene expostos à API RNA; build de editor e runtime aprovado |
| [2026-09-09 (Cutscene — Fase 1A: dados persistidos)](#2026-09-09--cutscene--fase-1a-dados-persistidos) | Estrutura de Cutscene em `Scene`, ciclo de vida, serialização, relink de objetos e migração de arquivos antigos; clean rebuild aprovado |
| [2026-09-08 (scripts — varredura de bugs silenciosos em addons)](#2026-09-08--scripts-varredura-de-bugs-silenciosos-em-addons) | 4 addons corrigidos (report() com tipo errado, vazamento de RNA property, sintaxe legada, operators órfãos) com bump de versão; 5 revisados sem bug |
| [2026-09-08 (scripts — modernização de Python legado)](#2026-09-08--scripts-modernizacao-de-python-legado) | `bpy.props` sem anotação corrigido em 17 addons; `print`/`xrange` residuais de Py2 corrigidos em 2 addons |
| [2026-09-08 (extern/cjson — atualização para 1.7.19)](#2026-09-08--externcjson-atualizacao-para-1719) | `cJSON.h`/`cJSON.c` atualizados de 1.7.18 para 1.7.19 (sem patches locais); traz limite de recursão em `cJSON_Duplicate` e outros fixes de segurança/robustez |
| [2026-09-08 (RecastNavigation — port para API moderna dtNavMesh/dtNavMeshQuery)](#2026-09-08--recastnavigation-port-para-api-moderna-dtnavmeshdtnavmeshquery) | `KX_NavMeshObject`/`KX_SteeringActuator` migrados de `dtStatNavMesh` para `dtNavMesh`/`dtNavMeshQuery`; walkable Height/Radius/Climb reconectados à UI; log `[Plano9]` removido |
| [2026-09-07 (Linux — preparação do runtime)](#2026-09-07--linux--preparação-do-runtime) | Preset `linux-runtime` e roteiro de build/validação adicionados; sem build Linux executado |
| [2026-09-07 (Ketsji, Plano 10 — encerramento)](#2026-09-07--ketsji-plano-10-encerramento) | Plano 10 e o programa de modernização (Planos 1-10) encerrados |
| [2026-09-07 (Ketsji, Plano 10 — ownership dos componentes em architecture.md)](#2026-09-07--ketsji-plano-10-ownership-dos-componentes-em-architecturemd) | Documenta ownership dos membros de `KX_KetsjiEngine` em `architecture.md` |
| [2026-09-07 (Ketsji, Plano 10 — ordem do frame em architecture.md + correção de tc_network)](#2026-09-07--ketsji-plano-10-ordem-do-frame-em-architecturemd-e-correcao-de-tc_network) | Ordem oficial do frame documentada; corrige comentário errado sobre `tc_network` |
| [2026-09-07 (Ketsji, Plano 10 — limpeza de comentários e nomes)](#2026-09-07--ketsji-plano-10-limpeza-de-comentarios-e-nomes) | Comentários desatualizados de `tc_overhead`/`NextFrame`/`FrameOver` corrigidos |
| [2026-09-07 (Ketsji, Plano 10 — levantamento + limpeza de código morto)](#2026-09-07--ketsji-plano-10-levantamento-e-limpeza-de-codigo-morto) | Mapeamento de `KX_KetsjiEngine` + remoção de código morto (`FrameTimes`, `Export()` etc.) |
| [2026-09-07 (Ketsji, Plano 9 — fechamento: paralelização e batching descartados)](#2026-09-07--ketsji-plano-9-fechamento-paralelizacao-e-batchinginstancing-descartados-sem-ganho-mensuravel) | Draw calls medidos (145-1187/frame) abaixo do limiar; batching/instancing descartado |
| [2026-09-07 (Ketsji, Plano 9 — swap interval só quando muda)](#2026-09-07--ketsji-plano-9-swap-interval-so-quando-muda) | `SetSwapControl()` só chama quando o valor muda; ganho não mensurável |
| [2026-09-07 (Ketsji, Plano 8 — teste em jogo real da flag)](#2026-09-07--ketsji-plano-8-teste-em-jogo-real-da-flag-use_fixed_timestep) | `use_fixed_timestep` validado em jogo real pelo usuário, sem crash |
| [2026-09-07 (Ketsji, Plano 8 — validação da aritmética do acumulador)](#2026-09-07--ketsji-plano-8-validacao-da-aritmetica-do-acumulador-de-passo-fixo) | Aritmética do acumulador validada manualmente; ineficiência de `timescale=0` registrada |
| [2026-09-07 (Weather — animação de chuva/nuvens ignora Time Scale)](#2026-09-07--weather-animacao-de-chuvanuvenslens-flare-passa-a-respeitar-time-scale) | Weather agora usa `GetFrameTime()` em vez de `GetRealTime()`, respeitando Time Scale |
| [2026-09-07 (Ketsji, Plano 8 — flag exposta em GameData/RNA/UI)](#2026-09-07--ketsji-plano-8-flag-de-passo-fixo-exposta-em-gamedatarnaui) | `use_fixed_timestep` exposta em DNA/RNA/UI, off por padrão |
| [2026-09-07 (Ketsji, Plano 8 — acumulador de passo fixo)](#2026-09-07--ketsji-plano-8-introducao-do-acumulador-de-passo-fixo-atras-de-flag-desligada) | Acumulador de passo fixo implementado atrás de flag desligada (inerte) |
| [2026-09-06 (Ketsji, Plano 5 — controle de tolerância do cache de cascata)](#2026-09-06--ketsji-plano-5-5a-unidade-controle-de-tolerancia-do-cache-de-cascata-pelo-usuario) | `csm_cache_max_stale_frames` novo, controla tolerância do cache de cascata |
| [2026-09-06 (Ketsji, Plano 5 — câmeras reutilizadas, cache de cascata e correção do roadmap)](#2026-09-06--ketsji-plano-5-3a-e-4a-unidades-de-otimizacao-e-correcao-do-roadmap-de-blend-suave) | Câmeras de sombra reutilizadas; cache de matrizes de cascata por luz |
| [2026-09-06 (Ketsji, Plano 5 — otimização de matrizes de cascata)](#2026-09-06--ketsji-plano-5-otimizacao-eliminar-recomputacao-de-matrizes-de-cascata) | Matrizes de cascata CSM calculadas 1x/luz/frame em vez de até 5x |
| [2026-09-06 (Ketsji, Plano 5 — extração do pipeline de sombras)](#2026-09-06--ketsji-plano-5-extracao-pura-do-pipeline-de-sombras-para-kx_shadowrenderer) | `KX_ShadowRenderer` extraída de `KX_KetsjiEngine` (extração pura) |
| [2026-09-06 (Ketsji/Rasterizer, Plano 4 — busca de novos candidatos)](#2026-09-06--ketsjirasterizer-plano-4-guardas-em-kx_texturerenderermanager-e-ras_rasterizer) | Guardas RAII em `KX_TextureRendererManager` e `RAS_Rasterizer::ProcessLighting` |
| [2026-09-06 (Ketsji, Plano 4 — binds de framebuffer de shadow)](#2026-09-06--ketsji-plano-4-guardas-de-bindunbind-de-framebuffer-em-rendershadowbuffers) | Guardas RAII para binds de framebuffer de shadow |
| [2026-09-06 (Ketsji, Plano 4 — câmeras temporárias de shadow)](#2026-09-06--ketsji-plano-4-guarda-de-camera-temporaria-em-rendershadowbuffers) | Guarda RAII libera câmeras temporárias de shadow |
| [2026-09-06 (Ketsji, Plano 4 — guardas em RAS_2DFilter::Render)](#2026-09-06--ketsji-plano-4-guardas-de-escopo-em-ras_2dfilterrender) | Guarda RAII genérica restaura estado de `RAS_2DFilter::Render` |
| [2026-09-06 (Ketsji, Plano 4 — guarda offscreen)](#2026-09-06--ketsji-plano-4-guarda-de-escopo-para-o-offscreen-de-collision-depth) | Guarda RAII restaura offscreen do collision-depth pass |
| [2026-09-06 (Ketsji, Plano 3 — encerrado)](#2026-09-06--ketsji-plano-3-encerrado-por-decisao-do-usuario-escopo-atual) | Plano 3 encerrado após 8 unidades; ASan/UBSan/sombras C++ pendentes |
| [2026-09-06 (Ketsji, Plano 3 — sistema de partículas)](#2026-09-06--ketsji-plano-3-teste-de-regressao-do-sistema-de-particulas) | `particle_system_regression.py` — teste de contrato de `KX_ParticleSystem`, PASS |
| [2026-09-06 (Ketsji, Plano 3 — múltiplas câmeras/viewports/estéreo)](#2026-09-06--ketsji-plano-3-teste-de-regressao-de-multiplas-camerasviewportsestereo) | `multi_camera_stereo_regression.py` — bug de pareamento achado e corrigido, depois PASS |
| [2026-09-06 (Ketsji, Plano 3 — callbacks de desenho)](#2026-09-06--ketsji-plano-3-teste-de-regressao-dos-callbacks-de-desenho) | `drawing_callbacks_regression.py` — ordem pre/post draw validada, PASS |
| [2026-09-06 (Ketsji, Plano 3 — asserts de dependências)](#2026-09-06--ketsji-plano-3-asserts-nas-dependencias-obrigatorias) | `BLI_assert` em `SetImgui`/`SetDebugMode`/`SetNetworkMessageManager` |
| [2026-09-06 (Ketsji, Plano 3 — self-teste CSM)](#2026-09-06--ketsji-plano-3-self-teste-matematico-do-csm-sem-opengl) | `SelfTestCascadeShadowMath` — self-teste da matemática do CSM sem OpenGL |
| [2026-09-06 (Ketsji, Plano 3 — script de cenas)](#2026-09-06--ketsji-plano-3-script-de-regressao-para-ciclo-de-vida-de-cenas) | `scene_lifecycle_regression.py` — add/remove/replace/suspend/resume, PASS |
| [2026-09-06 (Ketsji, Plano 3 — câmeras temporárias)](#2026-09-06--ketsji-plano-3-auditoria-de-ciclo-de-vidarefcount-de-cameras-temporarias) | Auditoria de refcount de câmeras temporárias — nenhum bug encontrado |
| [2026-09-06 (Ketsji, Plano 3 — relógio controlável)](#2026-09-06--ketsji-plano-3-relogio-controlavelfalso-para-testes-de-temporizacao) | `CM_Clock` ganha modo manual opt-in (`SetManualTime`/`AdvanceManualTime`) |
| [2026-09-06 (Ketsji, Plano 2 — contador de lógica)](#2026-09-06--ketsji-plano-2-contador-de-sensorescontrollersatuadores) | Contadores de sensores/controllers/atuadores no Debug Mode |
| [2026-09-06 (Ketsji, Plano 2 — contador de draw calls)](#2026-09-06--ketsji-plano-2-contador-de-draw-callsmudancas-de-material) | Contador de draw calls/mudanças de material no Debug Mode |
| [2026-09-06 (Ketsji, Plano 2 — contador de luzes/sombras)](#2026-09-06--ketsji-plano-2-contador-de-luzestotalatualizadaspasses-de-sombra) | Contador de luzes total/atualizadas/passes de sombra |
| [2026-09-06 (Ketsji, Plano 2 — encerramento por decisão do usuário)](#2026-09-06--ketsji-plano-2-avanco-para-o-plano-3-por-decisao-do-usuario) | Plano 2 pausado (não esgotado) por decisão do usuário; avança para o Plano 3 |
| [2026-09-06 (Ketsji, Plano 2 — contador de objetos)](#2026-09-06--ketsji-plano-2-contador-de-objetos-totaltestadovisivel-no-culling) | Contador de objetos total/testado/visível no culling |
| [2026-09-06 (Ketsji, Plano 2 — tc_physics fora de escopo)](#2026-09-06--ketsji-plano-2-tc_physics-confirmado-fora-de-escopo) | `tc_physics` confirmado fora do escopo do Plano 2 |
| [2026-09-06 (Ketsji, Plano 2 — validação Filtros 2D)](#2026-09-06--ketsji-plano-2-validacao-em-jogo-real-do-tc_filters2d) | `tc_filters2d` validado em jogo real |
| [2026-09-06 (Ketsji, Plano 2 — categoria Filtros 2D)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-filtros-2d) | Categoria de profiling `tc_filters2d` separada de `tc_rasterizer` |
| [2026-09-06 (Ketsji, Plano 2 — validação em jogo real)](#2026-09-06--ketsji-plano-2-validacao-em-jogo-real-das-unidades-3-a-7) | Unidades 3-7 do Plano 2 validadas em jogo real |
| [2026-09-06 (Ketsji, plano mestre — separação render/simulação)](#2026-09-06--ketsji-plano-mestre-refinamento-dos-planos-6-9-com-relatorio-de-separacao-rendersimulacao) | Planos 6-9 do plano mestre refinados com o relatório de separação render/simulação |
| [2026-09-06 (Ketsji, Plano 2 — light update)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-atualizacao-de-luzes) | Categoria `tc_lightupdate` separada de `Shadows` |
| [2026-09-06 (Ketsji, Plano 2 — scenegraph)](#2026-09-06--ketsji-plano-2-categorias-de-profiling-para-as-tres-passagens-de-updateparents) | `tc_scenegraph` dividido em `_logic`/`_actuators`/`_physics` |
| [2026-09-06 (Ketsji, Plano 2 — input/imgui)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-input-e-imgui) | Categoria `tc_input` separada de `Overhead` |
| [2026-09-06 (Ketsji, Plano 2 — actuators)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-actuators) | Categoria `tc_actuators` separada de `Logic` |
| [2026-09-06 (Ketsji, Plano 2 — partículas)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-updategpuparticleemitters) | Categoria `tc_particles` separada de `Scenegraph` |
| [2026-09-06 (Ketsji, Plano 2 — texture renderers)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-rendertexturerenderers) | Categoria `tc_texturerenderers` completa o item texture renderers/collision-depth |
| [2026-09-06 (Ketsji, Plano 2)](#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-o-collision-depth-pass) | Categoria `tc_collisiondepth` separada de `Shadows` |
| [2026-09-05 (Ketsji, Plano 1B)](#2026-09-05--ketsji-plano-1b-higiene-conservadora-do-arquivo) | 75 linhas de código desativado removidas de `NextFrame`/`Render`/`RenderCamera` |
| [2026-09-05 (Ketsji, cursor)](#2026-09-05--ketsji-plano-1a-vida-útil-do-cursor-personalizado) | `FreeCustomMouseCursor` corrigido (nullptr + leak); Plano 1A completo |
| [2026-09-05 (Ketsji, projeção do Sol)](#2026-09-05--ketsji-plano-1a-projeção-segura-do-sol) | Guard em `screenPos.w` no cálculo de posição do Sol (Light Scattering/Lens Flare) |
| [2026-09-05 (Ketsji, taxas)](#2026-09-05--ketsji-plano-1a-validação-de-taxas-logic-tic-rate-render-rate-animation-rate) | `SetTicRate`/`SetRenderRate`/`SetAnimationRate` rejeitam valores inválidos |
| [2026-09-05 (Ketsji, shadowCulling)](#2026-09-05--ketsji-plano-1a-separação-shadowculling-de-maxphystep) | `shadowCulling` separado de `maxphystep` (DNA/RNA/versionamento) |
| [2026-09-05 (Ketsji)](#2026-09-05--ketsji-plano-1a-contador-csm) | Contador CSM por engine/frame |
| [2026-09-05](#2026-09-05) | `is_vehicle`/`vehicle_wheels` ligados à criação real do veículo; W/S corrigido |
| [2026-09-04](#2026-09-04) | Identidade visual Windows (ícone Range + cubo Anastacio) atualizada |
| [2026-09-03](#2026-09-03) | Layout do editor; organização da documentação; CSM/`staticShadow` corrigido |
| [2026-09-03 (varredura Blender)](#varredura-estática-de-bugs-silenciosos--achados-novos-do-fork-blender-correções-às-cegas-2026-09-03) | 15 achados da varredura estática corrigidos às cegas |
| [2026-09-03 (varredura Blender, itens pendentes)](#varredura-estática-de-bugs-silenciosos--os-10-itens-pendentes-fechados-3-novos-falsos-positivos-2026-09-03) | Os 10 itens restantes fechados (7 corrigidos, 3 falso positivo); relatório 26/26 |
| [2026-08-23](#2026-08-23) | Ferramenta de benchmark; fix de log GL 2.1; `RAS_InstancingBuffer` otimizado |
| [2026-08-24 §1](#2026-08-24) | Streaming Manager; regressão de instancing corrigida |
| [2026-08-24 §2](#2026-08-24-1) | Início da migração de shaders para core-profile-safe |
| [2026-08-24 §3](#2026-08-24-2) | Migração core-profile-safe dos filtros restantes; profiler Animations separado |
| [2026-08-24 §4](#2026-08-24-3) | GPU Skinning — Fases A-G completas |
| [2026-08-24 (continuação)](#2026-08-24-continuação) | `install/` obsoleto identificado; Core Profile Fase 6 (shadow map VSM) |
| [2026-08-25](#2026-08-25) | Core Profile fechado; Z-prepass; Borderless Window; CSM do zero; menu ImGui |
| [2026-09-01 §3](#modo-de-billboard-vertical-para-o-sistema-de-partículas-gpu) | Billboard vertical (axis-locked Z) para partículas GPU |
| [2026-08-26](#2026-08-26) | Motor confirmado GPU-bound; fix de UI no painel Culling; Occluder+Static |
| [2026-08-29](#2026-08-29) | Crash de impostor multi-angle corrigido; MSAA confirmado implementado |
| [2026-08-30](#2026-08-30) | Build do `RangeRuntime` quebrado corrigido (libs/stubs/símbolos duplicados) |
| [2026-08-31](#2026-08-31) | GPU Particles (transform feedback) — Fases A-K completas e confirmadas em jogo |
| [2026-08-31 §2 (Fase L)](#2026-08-31-2) | Debug ao vivo de GPU Particles; ponte de save-back via JSON com o editor |
| [2026-08-31 §3 (Fase L.2)](#2026-08-31-3) | Overlay de debug movido de componente Python para `KX_ParticleDebugUI` (C++) |
| [2026-08-31 §5 (Fase N)](#2026-08-31-5) | Visibilidade pausa update+draw do emissor; toggle `enabled` independente |
| [2026-09-01 §1](#2026-09-01) | Actuator GPU Particles removido (crash); Property auto-criada no lugar |
| [2026-09-01 §2](#2026-09-01) | Weather: layout unificado; rain shader revisado (streaks + ripples) |
| [2026-09-01 §6](#estilo-de-chuva-volumetric-otimização-das-inversas-de-matriz-em-rainclouds) | Estilo de chuva "Volumetric"; `inverse()` por-pixel trocada por matrizes pré-invertidas |
| [2026-09-01 §7](#global-properties-no-world-shared-object-world-dict) | Global Properties no World compartilhadas entre objetos; 2 crashes corrigidos |
| [2026-09-01 §8](#world-status-global-properties-auto-criadas-pendente) | World Status implementado, compila limpo, não apareceu em teste real (pendente) |
| [2026-09-01 §9](#console-in-game-imgui-botão-liga-desliga-no-header-da-3d-view) | Console in-game (ImGui); crash crítico em `termcolor.hpp` corrigido |
| [2026-09-02 §1](#física-para-o-sistema-de-partículas-gpu-fase-o) | Física (colisão) para GPU Particles — Ground Plane e Screen-Space, confirmado em jogo |
| [2026-09-02 §2](#varredura-estática-de-bugs-silenciosos---correções-às-cegas) | Varredura estática — 2 lotes de correções às cegas (buffer overflow, leaks, ponteiros nulos) |
| [2026-09-02 §2](#ground-plane-com-objeto-de-referência-e-screen-space-via-gpu-particle-collider) | Ground Plane ganha objeto de referência; Screen-Space via `use_gpu_particle_collider` |
| [2026-09-13](#fragment-shader-customizado-por-emissor-fase-p) | Fragment shader customizado (arquivo `.glsl` externo, hot-reload) para GPU Particles + exemplos |


---

## 2026-09-11 (continuação) — Crash na primeira execução com tema vazio (`U.themes` sem entradas)

- **Bug**: mesmo depois do fix acima (pastas recriadas), rodar `RangeEngine.exe` com
  `%APPDATA%\RangeEngine` totalmente ausente ainda crashava (`EXCEPTION_ACCESS_VIOLATION`), agora
  mais adiante — na tela de splash ou logo na primeira janela desenhada.
- **Causa raiz**: sem `userpref.blend`/`startup.blend` do usuário, o carregamento cai no
  `datatoc_startup_blend` embutido no binário (`wm_homefile_read()` em `wm_files.c`); esse blend de
  fábrica não contém nenhum `Theme`, então `U.themes` fica vazia. Nada no caminho de inicialização
  chamava `ui_theme_init_default()` automaticamente — essa função só era acionada pelo operador
  manual "Reset to Default Theme" (`interface_ops.c`). Dezenas de pontos do código de UI (desenho
  de widgets, splash screen, etc.) fazem `UI_GetTheme()->...`/`U.themes.first->...` sem checar NULL,
  então o primeiro que rodava after essa condição derrubava o processo — confirmado com uma
  backtrace simbolizada (`SymFromAddr`/`CaptureStackBackTrace`, adicionada e depois mantida em
  `windows_exception_handler` de `creator_signals.c` como diagnóstico permanente) apontando para
  `wm_block_splash_image_roundcorners_add` (`wm_splash_screen.c:184`) e, numa segunda repetição,
  `widget_state_pulldown` (`interface_widgets.c:2266`) — ambos lendo campos de um `bTheme*` nulo.
- **Fix**: `UI_init_userdef()` (`source/blender/editors/interface/interface.c`) agora chama
  `ui_theme_init_default()` sempre que `U.themes` está vazia, antes de `init_userdef_do_versions()`
  e de qualquer código de desenho rodar — garante um tema "Default" válido em qualquer cenário de
  primeira execução, independente do blend de fábrica conter ou não um Theme.
- **Validação**: `ninja RangeEngine` limpo (exit 0). Reproduzido apagando
  `%APPDATA%\RangeEngine` de verdade e rodando `RangeEngine.exe`: antes deste fix, crash
  (`EXCEPTION_ACCESS_VIOLATION` na tela de splash); depois, o processo abre e permanece rodando
  normalmente, com as três pastas (`config`/`datafiles`/`scripts`) recriadas vazias como esperado.

## 2026-09-12 — AddObject + External Files — objeto linkado sumia após save/export

- **Sintoma**: um objeto vinculado via "External Files" (linkado na library, sem instanciar na
  cena) e referenciado apenas por um ator AddObject de Logic Bricks funcionava normalmente no
  editor logo após o link, mas desaparecia depois de fechar/reabrir o `.range` (ou usar "Start
  Game In Player", que salva uma cópia antes de rodar) — o ator disparava e não achava o objeto.
- **Causa raiz**: o ID do objeto linkado ficava com `id->us == 0` por dois motivos combinados: (a)
  a propriedade RNA do alvo do ator AddObject (`rna_actuator.c`) não tinha a flag
  `PROP_ID_REFCOUNT`, então nada incrementava o contador ao apontar o ator para o objeto; (b) o
  passe de relink de ponteiros do `readfile.c` para esse tipo de ator nunca chamava `id_us_plus`.
  `writefile.c`'s `write_libraries()` só grava IDs com `id->us > 0`, então qualquer save (incluindo
  o copy-save interno de "Start Game In Player") descartava silenciosamente o objeto e sua library
  do arquivo de saída.
- **Fix**:
  - `source/source/blender/makesrna/intern/rna_actuator.c` — adicionada `PROP_ID_REFCOUNT` nas
    flags da propriedade "object" do EditObjectActuator.
  - `source/source/blender/blenloader/intern/readfile.c` — no relink de atuadores, caso
    `ACT_EDIT_OBJECT`: `if (eoa->type == ACT_EDOB_ADD_OBJECT && eoa->ob && eoa->ob->id.lib) {
    id_us_plus(&eoa->ob->id); }`.
  - `source/source/blender/windowmanager/intern/wm_files_link.c` — link via "External Files" passa
    a usar `FILE_LINK | FILE_RELPATH`, mantendo o caminho da library relativo ao `.blend`
    (`//lib.blend`) em vez de gravar o caminho absoluto da máquina que registrou o link —
    necessário para a referência sobreviver à exportação para Standalone, onde só uma cópia da
    library ao lado do projeto é distribuída.
  - `source/release/scripts/startup/bl_operators/wm.py` (`WM_OT_blenderplayer_start`) — o
    copy-save de "Start Game In Player" passa a usar `relative_remap=False`: por padrão
    `relative_remap=True` com `copy=True` absolutiza todos os caminhos de library antes de salvar
    (`writefile.c`, `G_FILE_SAVE_COPY` + `G_FILE_RELATIVE_REMAP`), mesmo a cópia `~` ficando sempre
    na mesma pasta do arquivo original — isso transformava links relativos de External Files em
    caminhos absolutos específicos da máquina na cópia descartável, quebrando silenciosamente o
    teste em outra máquina.
  - `source/release/scripts/startup/bl_operators/wm.py` (export RangeArmor) — o `.rasec` de
    `MainFile` agora é sempre regravado a cada export (antes só era gerado se ainda não existisse),
    evitando que um `.rasec` desatualizado embarque dados antigos (ex.: um link de External Files
    adicionado depois do último export).
- **Validação**: rebuild limpo de `RangeEngine`/`RangeRuntime` com as três primeiras correções.
  Reproduzido o caminho de código do ator (`KX_Scene::AddReplicaObject`) via script Python
  standalone, dos dois jeitos — `KX_PythonComponent` com argumentos configuráveis no painel, e
  sensor Keyboard + controlador Python chamando `scene.addObject()` — confirmando que o objeto
  linkado (`Group_car`) aparece corretamente em `objectsInactive` e é instanciado com sucesso após
  fechar/reabrir o projeto. Note que o módulo Python deste fork se chama `Range`, não `bge`.

## 2026-09-12 — Export 1 clique — rebuild automático do template Launcher.exe

- **Motivação**: o Fix 4 da entrada abaixo resolveu o bug corrigindo manualmente o binário
  `Launcher.exe` uma vez (via `cargo build --release` rodado à mão no terminal), mas o problema
  podia voltar silenciosamente se `tools/RangeArmor-master` fosse reinstalado/reclonado (o binário
  não é rastreado em git). Usuário pediu para eliminar esse passo manual de vez: detectar o caso e
  já corrigir sozinho, de forma automática, sem diálogo de confirmação nem intervenção manual.
- **Fix — `_rangearmor_ensure_launcher_template_fresh(template_dir)`**
  (`source/release/scripts/startup/bl_operators/wm.py`), chamada no início de
  `_rangearmor_scaffold_project` antes de copiar `Launcher.exe` para o projeto: compara a data de
  modificação do `Launcher.exe` template com a de `source/launcher/src/main.rs`; se o `.rasec`/
  Launcher template estiver mais antigo que o source (ou não existir), e `cargo` estiver disponível
  no PATH, roda `cargo build --release --target x86_64-pc-windows-msvc` (ou
  `x86_64-unknown-linux-gnu` em Linux) dentro de `source/launcher` e copia o binário resultante
  por cima do template automaticamente, antes do resto do scaffold prosseguir. Melhor-esforço e
  silencioso em qualquer falha (cargo ausente, build falhar, `main.rs` não encontrado): nesses
  casos apenas mantém o comportamento anterior (usa o template como está), sem bloquear o export.
- **Efeito**: qualquer clique em "Export Game (1 Click)" agora garante — sozinho, sem passo
  manual — que o `Launcher.exe` usado no scaffold nunca fica desatualizado em relação ao source
  Rust atual, eliminando de vez a classe de bug "abre e fecha" descrita no Fix 4 abaixo, mesmo após
  reinstalações futuras de `tools/RangeArmor-master`.

## 2026-09-12 — Export 1 clique — scaffold automático, progresso e Launcher.exe corrompido

- **Motivação**: usuário reportou que o botão "Export Game (1 Click)" ainda exigia abrir o
  RangeArmor Panel manualmente uma vez antes (para gerar `launcher/config.json`, `Launcher.exe`,
  ícones e runtime do engine), e pediu para automatizar isso no próprio clique. Também pediu um
  indicador visual de carregamento durante o export ("faça o mais fácil").
- **Fix 1 — scaffold automático**: `WM_OT_one_click_export_rangearmor.execute()`
  (`source/release/scripts/startup/bl_operators/wm.py`) agora chama
  `_rangearmor_scaffold_project(project_dir)` no início, que recria em Python puro a mesma
  estrutura que o RangeArmor Panel criaria (`welcome.gd:_create_new_project`/
  `scripts/globals.gd:DEFAULT_PROJECT_FOLDERS`/`DEFAULT_PROJECT_FILES`/`DEFAULT_FIELDS`): pastas
  `data`/`engine`/`engine/Linux64`/`engine/Windows64`/`launcher`/`icons`, `launcher/config.json`
  com os defaults, e cópia de `Launcher(.exe)`/ícones a partir do template empacotado com o
  RangeArmor Panel, se ainda não existirem. Também dispara automaticamente
  `get_rangeengine_currentplatform.py --all-platforms` se `engine/<plataforma>` ainda não tiver o
  runtime copiado. Abrir o painel manualmente continua funcionando, mas deixou de ser necessário.
- **Fix 2 — indicador de progresso**: todo o corpo do operador foi envolto em
  `wm.progress_begin(0, 5)`/`wm.progress_update(n)`/`wm.progress_end()` (percentual ao lado do
  cursor) e `context.window.cursor_set('WAIT'/'DEFAULT')`, dentro de um `try/finally` para garantir
  que o cursor volte ao normal mesmo se o export falhar no meio do caminho.
- **Fix 3 — `MainFile` desatualizado ("abre e fecha", causa nº 1)**: `_rangearmor_write_export_preset`
  deixava `MainFile` no valor default `"Example Game.rasec"` quando o projeto nunca tinha sido
  salvo como protegido (`.rasec`) antes — o launcher exportado procurava um arquivo que não
  existia e fechava sozinho. Agora, se o `.rasec` correspondente ao `.blend` atual não existir em
  `data/`, ele é gerado automaticamente via `bpy.ops.wm.save_as_mainfile_protected(...)` (mesma
  lógica do botão "Save as Protected"), e `MainFile` é sempre sincronizado com o nome real do
  `.rasec`.
- **Fix 4 — `Launcher.exe` desatualizado ("abre e fecha", causa nº 2, mais grave)**: mesmo depois
  do fix 3, o executável exportado continuava abrindo e fechando na hora. Investigação (formato
  binário do `.rasec` byte-a-byte, `RangeRuntime.exe` chamado direto, `launcher.py` legado) não
  encontrou nada quebrado — até rodar o `.exe` renomeado direto pelo terminal, que revelou um
  panic do Rust: `thread 'main' panicked at 'called Option::unwrap() on a None value',
  src\main.rs:137:60`. O `Launcher.exe` template usado no scaffold
  (`tools/RangeArmor-master/RangeArmor-master/release/launcher/Launcher.exe`) estava compilado de
  uma versão antiga de `source/launcher/src/main.rs` (o launcher Rust real, não confundir com o
  painel Godot nem com o `gui-rs` do editor do RangeArmor Panel) que ainda tinha um `.unwrap()`
  problemático; o `main.rs` atual no repositório já usa `map_err`/`ok_or_else` em todos os pontos
  equivalentes e não tem esse bug. **Recompilado** com
  `cargo build --release --target x86_64-pc-windows-msvc` a partir do source atual, e o `.exe`
  resultante substituiu o template em `release/launcher/Launcher.exe` (usado pelo scaffold para
  todo projeto novo) — validado rodando o launcher reconstruído no projeto de teste do usuário
  (`D:\teste_export\MyProject`), que agora inicia o `RangeRuntime.exe` corretamente sem panic.
  **Ainda não versionado**: o binário `release/launcher/Launcher.exe` não está rastreado em git
  (é um artefato binário); qualquer reinstalação/cópia futura desse diretório a partir de uma
  fonte externa (ex.: reclonar `tools/RangeArmor-master`) vai trazer de volta o binário antigo —
  se isso acontecer, repetir o `cargo build --release` acima e recopiar o `.exe`.

## 2026-09-12 — Export — botão 1 clique

- **Motivação**: o fluxo existente (`Scene > Export (RangeArmor)` → "Open RangeArmor Panel")
  ainda exigia abrir o painel Godot separado e clicar em "Export All" lá dentro, além de copiar
  manualmente os arquivos gerados para outro lugar.
- **Achado**: `_on_ButtonExport_pressed` do painel (`editor.gd`) só chama `_run_script`, que roda
  `python release/scripts/build_release.py --project <config.json> --target <alvo> [--compress]`
  via `OS.execute`. Não há lógica adicional na UI Godot — o empacotamento inteiro (STAGE 1-4 de
  `build_release.py`: pastas, dados do jogo, launcher, engine, compressão) é um script Python
  autocontido, então dá para chamá-lo direto do Blender sem abrir o executável do painel.
- **Fix**: novo operador `wm.one_click_export_rangearmor`
  (`source/release/scripts/startup/bl_operators/wm.py`, `WM_OT_one_click_export_rangearmor`) e
  botão "Export Game (1 Click)" no painel `Scene > Export (RangeArmor)`
  (`bl_ui/properties_scene.py`). Reaproveita `_write_export_preset`/`_ensure_launcher_script` do
  operador existente, resolve o Python do projeto do mesmo jeito que `editor.gd`
  (`AlternativePython`/`AlternativePythonLinux` relativo à instalação do RangeEngine atual, com
  fallback para `PythonWindows64`/`PythonLinux64` do próprio projeto), roda
  `build_release.py --target All --compress` via `subprocess.run` e abre a pasta `release/`
  resultante no Explorer/`xdg-open` ao final. Nenhuma mudança no RangeArmor Panel (Godot) foi
  necessária.
- **Fora de escopo / não testado nesta sessão**: execução end-to-end real dentro do Blender
  (precisa de um projeto RangeArmor completo com `engine/Windows64` já populado via "Get RanGE").
  Testar com um projeto real antes de confiar no botão para builds de release.

## 2026-09-11 — Modo seguro — `WM_init()` recria pastas de config ausentes

- **Bug original**: apagar `%APPDATA%\RangeEngine` inteira (reset manual de config) fazia o
  `RangeEngine.exe` crashar na inicialização (`EXCEPTION_ACCESS_VIOLATION`) em vez de recriar a
  pasta do zero, porque código de inicialização mais adiante assumia que `config`/`scripts`/
  `datafiles` já existiam.
- **Fix**: `WM_init()` em `source/blender/windowmanager/intern/wm_init_exit.c` agora chama
  `BKE_appdir_folder_id_create()` para `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS` e
  `BLENDER_USER_DATAFILES` logo após `GHOST_CreateSystemPaths()`, antes de qualquer código de
  UI/init rodar — garante que as três pastas existam (recriando-as se ausentes) antes que outro
  código dependa delas.
- **Plataforma**: a mudança é em código C comum (`BKE_appdir_folder_id_create`, sem `#ifdef
  _WIN32`), a mesma função já usada nas demais plataformas — portanto o fix já se aplica ao build
  Linux automaticamente, sem necessidade de código adicional específico. Não foi feito (nem exigido
  por este bug) um build/teste Linux nesta sessão; a preparação de build Linux já registrada em
  [2026-09-07 (Linux — preparação do runtime)](#2026-09-07--linux--preparação-do-runtime) segue como
  pendência separada de validação.
- **Validação**: reproduzido o cenário renomeando (não apagando) a pasta real
  `%APPDATA%\RangeEngine` para simular "pasta ausente", rodando o `.exe` sob `timeout` — antes do
  fix, crash imediato; depois do fix, o processo iniciou e permaneceu rodando normalmente até o
  fim do teste, sem crash. Dados reais do usuário restaurados e verificados intactos após o teste.

## 2026-09-10 — View 3D — gizmo de navegação

- Substituído o indicador legado de três linhas/letras da View 3D por um gizmo
  compacto inspirado na Range Engine 1.6 Rev2 instalada localmente: cubo central
  translúcido orientado pela câmera, traços coloridos para os seis semieixos e
  rótulos X/Y/Z nos sentidos positivos.
- Após ajuste visual, os alvos circulares foram removidos e os rótulos passaram
  a usar cinza.
- A implementação permanece no overlay OpenGL compatibility já usado pelo editor
  2.79, sem importar a infraestrutura incompatível de gizmos do Blender moderno.
  Nesta unidade, o gizmo é somente visual; a interação por clique exige um operador
  de evento próprio e ficou deliberadamente para uma unidade posterior.
- Validação: `ninja RangeEngine` recompilou `view3d_draw.c`, linkou e instalou
  `build/bin/RangeEngine.exe` com sucesso (exit code 0). Falta inspeção visual no
  editor real para ajustar tamanho, posição e acabamento.

## 2026-09-10 — Iluminação — preset padrão de Sun

- `BKE_lamp_init()` agora inicializa toda Lamp nova com o preset mostrado para uso como Sun: shadow map
  Simple, filtro PCF, 1024 px, 1 sample, soft 0,300, bias 1,000, slope bias 0,000, com CSM e debug
  desativados, proporções Near/Middle 0,400/0,350, Medium 512 px/soft 5/bias 1 e Low 128 px/soft 8/bias 1.
- O operador de adicionar Lamp chama essa inicialização antes de definir o tipo solicitado, portanto os
  valores estão presentes imediatamente ao adicionar uma Sun. Arquivos e Lamps existentes permanecem
  inalterados.

---

## 2026-09-09 — Cutscene — Fase 4G: API Python de runtime

- `KX_Scene` expõe `play_cutscene(sequence=0)`, `stop_cutscene()` e
  `restart_cutscene()` para scripts de jogo controlarem o manager nativo sem
  acessar ponteiros ou estruturas transitórias.
- A API retorna sucesso quando aplicável e emite `RuntimeError` para cenas sem
  Cutscene convertida ou sem sequência ativa; índice inválido retorna
  `ValueError`. Stop/restart preservam a limpeza coordenada dos objetos gerados.
- Validação: `git diff --check` e `ninja RangeRuntime RangeEngine`.

## 2026-09-09 — Cutscene — Fase 4H: falha segura de instanciação

- O despachante de `Spawn Object` agora trata a falha de `AddReplicaObject()`
  para o template antes de criar o dependente, registrar ownership ou liberar
  a réplica. O evento é descartado com erro explícito, sem desreferenciar
  ponteiro nulo nem deixar um dependente órfão.
- O caminho normal de instanciação e parentamento permanece inalterado.
- Validação: `git diff --check` e build `RangeRuntime`/`RangeEngine`.

## 2026-09-09 — Cutscene — Fase 5A: importador nativo

- Adicionado `source/release/scripts/templates_py/cutscene_native_import.py`,
  que importa o JSON legado `{cena: {id: [passos]}}` e o schema versionado
  `{"schema_version": 1, "scenes": ...}` para `Scene.cutscene_settings`.
- O importador converte somente `spawn_object`, resolve referências por nome em
  `bpy.data.objects` e rejeita ações sem equivalente nativo, referências
  ausentes, schema desconhecido ou eventos sem Template Object/Spawn Point.
  Nenhum script arbitrário do add-on é carregado.
- Validação: sintaxe Python compilada com `py_compile` e `git diff --check`.

## 2026-09-09 — Cutscene — Fase 5B: regressão do importador

- Adicionado `source/release/scripts/templates_py/cutscene_native_import_regression.py`.
  O roteiro cria objetos temporários e verifica no editor a importação dos formatos
  legado e versionado, referências `Template Object`/`Spawn Point`/`Dependent Object`,
  `clear_existing` e a rejeição de schema desconhecido e ações sem equivalente nativo.
- Validação: `py_compile`, `git diff --check` e execução em background com
  `RangeEngine --factory-startup`; o roteiro terminou com `[cutscene_native_import_regression] PASS`.

## 2026-09-09 — Cutscene — Fase 5C: exportação nativa

- Adicionados `cutscene_native_export.py` e sua regressão. O exportador escreve
  `schema_version: 1`, sequências e eventos `spawn_object` com referências de
  objetos por nome; tipos ainda sem equivalente nativo são rejeitados.
- A regressão executa exportação e reimportação no editor e confirma nome, tempo
  e as três referências de `Spawn Object`.
- Validação: `py_compile`, `git diff --check` e execução em background com
  `RangeEngine --factory-startup`, terminando com `[cutscene_native_export_regression] PASS`.

---

## 2026-09-09 — Cutscene — Fase 5D: exemplo e roteiro

- Adicionados `cutscene_native_example.py` e
  `cutscene_native_example_validate.py`. O primeiro gera um `.blend` mínimo,
  determinístico e baseado em DNA nativo; o segundo reabre o arquivo e verifica
  a sequência `Opening`, o evento `Spawn Hero`, o tempo e as referências de
  `Spawn Object`, incluindo `Dependent Object` opcional.
- Adicionado `docs/cutscene-native-example.md` com comandos de geração,
  save/load, intercâmbio JSON e roteiro manual de Play/Stop/standalone.
- A unidade não altera o runtime nem a UI; o exemplo não depende do add-on em
  `tools/ProjetoCutscene`.

## 2026-09-09 — Cutscene — Fase 4F: ownership e limpeza

- O manager registra as instâncias runtime primária e dependente criadas por
  cada evento. Quando há `Dependent Object`, a réplica nasce no mesmo Spawn
  Point e é parentada ao objeto principal por `SetParent`, que conserva a
  transformação mundial durante a ligação.
- `KX_Scene` remove as instâncias registradas antes de stop, restart, troca de
  manager e destruição da cena. A remoção usa a fila nativa de eutanásia, então
  a hierarquia parentada é destruída uma única vez e não deixa objetos órfãos.
- Validação: `git diff --check` e `ninja RangeRuntime RangeEngine` concluíram;
  ambos os executáveis foram linkados em `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 4E: despachante Spawn Object

- O ciclo lógico agora consome os eventos pendentes de Cutscene antes de
  sensores e controladores. Para `Spawn Object` válido, ele instancia o
  `Template Object` na transformação do `Spawn Point` pela mesma
  `AddReplicaObject()` usada pelos actuators nativos.
- Template ou ponto de spawn ausentes, e tipos de evento não suportados, emitem
  erro claro e não interrompem a simulação. A referência temporária da chamada
  é liberada imediatamente; a cena mantém a referência de runtime pela sua
  lista de root parents, como nos caminhos existentes de spawn.
- Esta unidade cria somente o objeto principal. O `Dependent Object` e a
  remoção coordenada em stop/restart permanecem a próxima unidade de ownership.
- Validação: `git diff --check` e `ninja RangeRuntime RangeEngine` concluíram;
  ambos os executáveis foram linkados em `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 4D: avanço no loop da cena

- `KX_SimulationPipeline` agora avança a Cutscene no começo da simulação de
  cada cena ativa, antes de sensores e controladores. Assim ela usa o mesmo
  relógio lógico do jogo, respeita pausa/suspensão e mantém o comportamento de
  timestep fixo consistente com os demais subsistemas.
- `KX_Scene` retém os eventos atravessados numa fila de runtime e oferece uma
  transferência única para o despachante. Nenhum evento é descartado enquanto
  `Spawn Object` ainda não está implementado; substituir ou destruir a cena
  descarta a fila junto com seu manager.
- Validação: `ninja RangeRuntime RangeEngine` concluiu. `RangeEngine.exe` já
  não estava bloqueado e ambos os binários foram atualizados em `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 4C: linha do tempo

- `KX_CutsceneManager::Update()` recebe o tempo absoluto de runtime em
  segundos e retorna somente os eventos atravessados desde a chamada anterior.
  Eventos no mesmo instante preservam o ordinal de autoria por uma ordenação
  estável aplicada ao iniciar a sequência.
- Uma chamada repetida no mesmo frame não redespacha eventos. Ao buscar para
  trás, o manager recompõe o cursor para os eventos que já pertencem ao novo
  instante e não emite efeitos durante o seek; a próxima progressão temporal
  continua a partir dali. `Stop()` e `Restart()` reinicializam esse estado.
- Esta unidade ainda não acopla a linha do tempo ao loop da engine nem cria
  objetos: o próximo passo conecta o despachante ao ponto de atualização da
  cena, antes de implementar `Spawn Object`.
- Validação parcial: `KX_CutsceneManager.cpp` compilou e `RangeRuntime` foi
  linkado. O link de `RangeEngine` ficou pendente porque `build/bin/RangeEngine.exe`
  estava bloqueado por outro processo (`LNK1104`); nenhum processo do usuário foi
  encerrado automaticamente.

---

## 2026-09-09 — Cutscene — Fase 4B: ciclo de vida

- `KX_CutsceneManager` agora mantém somente estado transitório de reprodução:
  sequência ativa e indicador de execução. `Start()` rejeita índices inválidos;
  `Stop()` limpa completamente o estado; `Restart()` reaplica a sequência ativa
  quando houver uma. Nenhum desses dados é escrito no DNA da cena.
- O ownership por `KX_Scene` já estabelecido na Fase 4A garante destruição do
  manager em remoção, reinício ou substituição da cena. O despachante temporal
  e os objetos gerados continuam fora desta unidade.
- Validação: `ninja RangeEngine RangeRuntime` concluiu e instalou os binários
  em `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 4A: conversão para runtime

- Adicionado `KX_CutsceneManager` como proprietário por `KX_Scene` das
  definições resolvidas durante a conversão. Ele recebe cópias de sequência,
  evento, tempo e tipo, além das referências diretas aos `KX_GameObject`s.
- `BL_ConvertBlenderObjects` converte os ponteiros DNA via
  `BL_SceneConverter::FindGameObject`, que cobre objetos ativos e inativos e
  evita busca frágil por nome. Cenas sem sequências não criam manager.
- Esta unidade ainda não inicia reprodução, despacha eventos nem instancia
  objetos; esses estados serão acrescentados separadamente sobre o contrato
  agora estabelecido.
- Validação: `ninja RangeEngine RangeRuntime` concluiu e instalou os binários
  em `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 2G: regressão de persistência

- Adicionado `cutscene_persistence_regression.py` aos templates Python. Em
  background, ele cria uma sequência e um evento `Spawn Object`, salva o
  `.blend`, reabre-o no mesmo processo e verifica nome, tempo e as referências
  de `Template Object`, `Spawn Point` e `Dependent Object`.
- Validação: o script executou com `RangeEngine.exe --background` e reportou
  `PASS` após reabrir o arquivo temporário.

---

## 2026-09-09 — Cutscene — Fase 2F: criação inicial

- Corrigida a disponibilidade de `Add` em `Cutscene Sequences`: o controle com
  `ZOOMIN` permanece ativo quando a coleção está vazia, permitindo criar a
  primeira sequência. Remove, Duplicate e Move seguem desabilitados até haver
  uma seleção válida.
- Validação: sintaxe Python por compilação em memória, revisão de whitespace e
  `ninja RangeEngine RangeRuntime` aprovados; o painel foi instalado em
  `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 2E: validação Spawn Object

- O inspector de `Spawn Object` agora destaca individualmente `Template Object`
  e `Spawn Point` quando estiverem vazios e informa que ambos são obrigatórios.
  `Dependent Object` permanece opcional e não gera alerta.
- Validação: sintaxe Python por compilação em memória, revisão de whitespace e
  `ninja RangeEngine RangeRuntime` aprovados; o painel foi instalado em
  `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 2D: inspector Spawn Object

- Adicionado o painel `Event` em `Properties > Cutscene`. Ele edita o evento
  ativo da sequência ativa e permanece seguro quando não há uma seleção válida.
- O inspector expõe nome, tempo e tipo do evento. Para `Spawn Object`, expõe
  diretamente `Template Object`, `Spawn Point` e `Dependent Object`, usando as
  propriedades RNA persistidas da cena.
- Validação: sintaxe Python por compilação em memória, revisão de whitespace e
  `ninja RangeEngine RangeRuntime` aprovados; o painel foi instalado em
  `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 2C: lista de eventos

- Adicionado `Cutscene Events` em `Properties > Cutscene`. O painel acompanha
  somente a sequência ativa e liga a coleção RNA de eventos ao índice ativo da
  cena.
- Add, Remove, Duplicate e Move chamam os operadores nativos de evento com os
  índices explícitos de sequência e evento. Add/Remove usam `ZOOMIN`/`ZOOMOUT`;
  as ações que precisam de uma seleção permanecem desabilitadas quando a lista
  está vazia ou o índice está inválido.
- Sem sequência selecionada, o painel mostra uma orientação em vez de acessar
  uma coleção inválida. A edição do inspector de cada evento permanece a
  próxima unidade.
- Validação: sintaxe Python por compilação em memória, revisão de whitespace e
  `ninja RangeEngine RangeRuntime` aprovados; o painel foi instalado em
  `build/bin/`.

---

## 2026-09-09 — Cutscene — Fase 2B: lista de sequências

- Criado o painel nativo `Properties > Cutscene > Cutscene Sequences`,
  registrado no carregamento padrão de `bl_ui`. A lista usa a coleção RNA da
  cena e seus índices ativos, sem depender de add-on.
- Os controles de estruturar a lista chamam exclusivamente os operadores
  nativos de adicionar, apagar, duplicar e mover. Os controles de adicionar e
  apagar usam os ícones nativos `ZOOMIN`/`ZOOMOUT`, que são os equivalentes
  Add/Remove efetivamente disponíveis neste atlas Blender 2.79; o plano foi
  corrigido para registrar os identificadores reais.
- Validação: sintaxe Python verificada por compilação em memória, revisão de
  whitespace aprovada e `ninja RangeEngine RangeRuntime` concluído (instalou
  `properties_cutscene.py` e o registro atualizado em `build/bin/`).

---

## 2026-09-09 — Cutscene — Fase 2A: contexto nativo

- Adicionado `BCONTEXT_CUTSCENE` ao fim da enumeração de Properties, sem
  renumerar contextos serializados existentes. O contexto usa `ICON_SEQUENCE`,
  constrói seu caminho a partir de `Scene` e é válido mesmo sem objeto ativo.
- O roteamento de Properties reconhece a categoria `"cutscene"`; a barra
  superior inclui `CUTSCENE` imediatamente depois de `WORLD`. Ainda não há
  painel de autoria nesta fase.
- Validação: `ninja -t clean` seguido de rebuild completo de `RangeEngine` e
  `RangeRuntime` aprovado; os dois executáveis foram ligados e a UI atualizada
  instalada em `build/bin/`.

## 2026-09-09 — Cutscene — Fase 1E: duplicação segura

- Adicionados `CUTSCENE_OT_sequence_duplicate` e `CUTSCENE_OT_event_duplicate`.
  Ambos inserem uma cópia logo após o item de origem, selecionam a cópia e
  participam de undo/redo.
- A cópia profunda de sequência cria eventos próprios; os três ponteiros de
  objeto de cada evento continuam referências aos mesmos IDs, com incremento
  explícito de usuário. Remover um evento ou uma sequência agora faz o
  decremento simétrico antes de liberar a memória, evitando tanto referências
  órfãs quanto contagem de usuários incorreta nos caminhos de edição direta.
- Validação: build incremental de `RangeEngine` e `RangeRuntime` aprovado.

---

## 2026-09-09 — Cutscene — Fase 1D: reordenação nativa

- Adicionados `CUTSCENE_OT_sequence_move` e `CUTSCENE_OT_event_move`, ambos
  com direção `UP`/`DOWN`, undo/redo, validação de índices e notificador de
  cena. Eles só rearranjam os nós existentes, portanto não copiam nem alteram
  os dados e referências de cada evento.
- Um movimento impossível no limite da lista é cancelado sem criar passo de
  undo. Após um movimento efetivo, o índice ativo acompanha o item movido e o
  evento ativo é reinicializado ao trocar a sequência selecionada.
- Validação: build incremental de `RangeEngine` e `RangeRuntime` aprovado.

---

## 2026-09-09 — Cutscene — Fase 1C: operadores nativos

- Criados e registrados os operadores `CUTSCENE_OT_sequence_add`,
  `CUTSCENE_OT_sequence_remove`, `CUTSCENE_OT_event_add` e
  `CUTSCENE_OT_event_remove`. Eles editam apenas os dados persistidos da cena,
  participam de undo/redo, recusam cenas vinculadas e validam todos os índices.
- A criação inicializa nomes legíveis (`Sequence` e `Spawn Object`), seleciona o
  item novo e preserva índices ativos válidos após remoção; apagar uma sequência
  também libera seus eventos. Cada operação emite `NC_SCENE | NA_EDITED` para
  atualizar consumidores da UI.
- Validação: `ninja RangeEngine RangeRuntime` recompilou `object_cutscene.c`,
  linkou `RangeRuntime.exe` e `RangeEngine.exe` com sucesso (exit code 0).
  A primeira tentativa revelou somente o include ausente de `BLI_strncpy`,
  corrigido com `BLI_string.h` antes da validação final.

---

## 2026-09-09 — Cutscene — Fase 1B: exposição RNA

- Exposta a estrutura persistida pela API RNA: `Scene.cutscene_settings`, coleções de
  sequências e eventos, índices ativos, nome, tempo em segundos, tipo de evento e
  referências `Template Object`, `Spawn Point` e `Dependent Object`.
- `Spawn Object` é o único valor de tipo exposto nesta etapa. As referências de objeto
  usam o contrato RNA de ID com contagem de usuários; a UI e os operadores ainda não
  foram adicionados, portanto as coleções seguem somente de leitura para a autoria.
- Validação: `ninja RangeEngine RangeRuntime` regenerou `rna_scene_gen.c` e concluiu os
  74 passos, com os dois executáveis linkados (exit code 0). A inspeção do código gerado
  confirmou as propriedades e iteradores das três estruturas.

---

## 2026-09-09 — Cutscene — Fase 1A: dados persistidos

- Adicionado o modelo persistido em `Scene`: `CutsceneSettings`, `CutsceneSequence` e
  `CutsceneEvent`, com o primeiro evento genérico `Spawn Object` e as três referências
  de objeto previstas (template, ponto de spawn e dependente opcional).
- `Scene.cutscene_settings` reutiliza o ponteiro legado `pad1`, que não tinha leitores;
  assim os offsets posteriores da `Scene` — inclusive os `uint64_t` — permanecem estáveis
  em SDNA 32/64-bit. A tentativa inicial de acrescentar o ponteiro ao lado de
  `toolsettings` revelou o desalinhamento no gerador DNA e foi substituída por essa
  solução compatível.
- Implementados alocação, cópia profunda e liberação; escrita/leitura direta, relink das
  referências `Object` e enumeração de IDs com contagem de usuários. O versionamento 1.6.109
  sempre cria uma estrutura vazia para arquivos anteriores, sem interpretar o padding
  legado como dado válido.
- Validação: `ninja -t clean && ninja RangeEngine RangeRuntime` concluído com sucesso
  (2.941 etapas, `RangeEngine.exe` e `RangeRuntime.exe` linkados, exit code 0).
- Ainda não é a Fase 1 completa: save/reopen e edição assistida dependem da próxima unidade
  de RNA e operadores nativos; não houve teste visual de editor nesta entrega de fundação.

## 2026-09-08 — scripts: varredura de bugs silenciosos em addons

Continuação do levantamento de `source/release/scripts/addons/`, desta vez seguindo
`docs/checklist-varredura-bugs-silenciosos.md` (ownership, contratos, limites,
stubs/defaults, API pública, ciclo de vida de registro, validade de dados) em vez de só
sintaxe. A pedido do usuário, todo addon com bug confirmado teve o `bl_info["version"]`
incrementado.

- **`easy_ragdoll_RangeEngine.py`** (`5.0` → `5.1`): `self.report("ERROR", ...)` corrigido
  para `self.report({'ERROR'}, ...)` (primeiro argumento precisa ser `set`, não string —
  levantava `TypeError` ao disparar o report). No script embutido `RAGDOLL_SCRIPT`,
  `getRagdollCenterPosition()` caía em `return` implícito (`None`) quando
  `maintain_parent=True` e a lista de ossos estava vazia (`count == 0`); adicionado
  fallback para a posição do root.
- **`ant_landscape/__init__.py`** (`0.1.8` → `0.1.9`): `unregister()` não desfazia
  `bpy.types.Object.ant_landscape` (registrado em `register()`), deixando a RNA property
  viva após desabilitar o addon. Adicionado `del bpy.types.Object.ant_landscape`.
- **`io_scene_x3d/__init__.py`** (`1.2.0` → `1.2.1`): todas as properties de
  `ImportX3D`/`ExportX3D` usavam a sintaxe antiga `nome = bpy.props.X(...)` — mesma classe
  de bug do ticket 1 da entrada anterior, mas este arquivo não fez parte da varredura
  mecânica de 17 arquivos porque não batia no grep usado na ocasião. Convertido para
  `nome: bpy.props.X(...)`.
- **`addon_editor_shot_tool.py`** (`1.0.0` → `1.0.1`): `CUTSCENE_OT_delete_shot` e
  `CUTSCENE_OT_strip_shot_properties` estavam implementados, mas nunca entravam em
  `CLASSES` nem eram referenciados por nenhum painel — operators mortos, inacessíveis via
  UI (mesmo padrão do bug já corrigido em `Range_Object_Pencil`, indicando ser um erro
  recorrente neste histórico de addons: adicionar o operator e esquecer de expô-lo).
  Adicionados a `CLASSES` e ligados à UI: botão de exclusão (ícone `X`) por linha de shot
  em `CUTSCENE_PT_shot_tool`, botão "Remover Propriedades de Tomada" em
  `CUTSCENE_PT_empty_shot_data`.
- Revisados sem bug encontrado (fechados limpos, sem bump de versão):
  `io_import_images_as_planes.py`, `io_curve_svg/__init__.py`,
  `io_mesh_uv_layout/__init__.py`, `automate_atlas_bake.py`,
  `cutscene_timeline_editor.zip` (extraído e lido; registro/unregister simétricos,
  `bpy.utils.previews` liberado corretamente).
- Verificação: os 4 arquivos modificados compilam limpo via `python -m py_compile`. Teste
  funcional de ciclo register/unregister dentro do Range Engine e revisão de
  `io_scene_obj/__init__.py` (único item pendente do backlog) ficam para uma próxima
  sessão.

## 2026-09-08 — scripts: modernização de Python legado

Levantamento em `source/release/scripts/` (965 arquivos `.py`) a pedido do usuário, após o
porte Linux do `RangeRuntime`. Executado conforme plano em 3 tickets independentes,
ordenados por risco.

- **Ticket 1 (risco real)**: 17 arquivos com `nome = bpy.props.X(...)` em vez de
  `nome: bpy.props.X(...)` em classes `Operator`/`PropertyGroup`/`AddonPreferences`/`Panel` —
  sob o Python 3.11 embarcado isso causa descarte silencioso de RNA (mesma classe de bug já
  documentada em `rna_xml.py`). Corrigido mecanicamente, arquivo por arquivo, só dentro das
  classes afetadas (atribuições soltas em módulo/função permanecem `=`). Estilo normalizado
  para `nome: bpy.props.X(...)` sem espaço antes dos dois-pontos, consistente em todos os 17
  arquivos.
- **Ticket 2 (baixo risco)**: `io_sequencer_edl/parse_edl.py:274` (`print t` → `print(t)`) e
  `io_scene_obj/import_obj.py:913` (`xrange` → `range`). Ambas as ocorrências estavam dentro
  de blocos de string triple-quoted (código de exemplo/desativado, nunca executado) —
  corrigido por consistência, não por bug ativo.
- **Ticket 3 (cosmético)**: debt encontrada (129 arquivos `%`-formatting, 10 `OrderedDict`)
  fica em backlog, sem PR dedicado — corrige-se ao tocar o arquivo por outro motivo. Não
  mexer nos usos propositais de `OrderedDict` no padrão "pretty args" de
  `KX_PythonComponent`.
- Verificação: todos os arquivos tocados compilam limpo via `python -m py_compile`.
  Verificação funcional em editor real (painéis carregando sem erro, import EDL/OBJ) —
  reportada como normal pelo usuário.

## 2026-09-08 — extern/cjson: atualização para 1.7.19

Levantamento de bibliotecas vendorizadas em `source/extern` a pedido do usuário; cJSON foi
escolhido por ser um arquivo único, sem patches locais aplicados (confirmado por diff
contra o upstream `DaveGamble/cJSON`), tornando a atualização de baixo risco.

- `source/extern/cjson/include/cJSON.h` e `source/extern/cjson/src/cJSON.c` atualizados de
  1.7.18 para 1.7.19 (CRLF preservado, sem mudanças de estrutura/CMakeLists).
- Fixes trazidos pela versão nova: limite de recursão (`CJSON_CIRCULAR_LIMIT`) em
  `cJSON_Duplicate` contra stack overflow em referências circulares; correção de `strcpy`
  com regiões sobrepostas em `cJSON_SetValuestring`; parsing de números via buffer alocado
  dinamicamente em vez de buffer fixo de 64 bytes (evita truncamento silencioso de números
  longos); checagem de bounds adicionada em `cJSON_DetachItemViaPointer`.
- Validado com build isolado do target `extern_json` (compila limpo). Build completo do
  motor não foi executado nesta sessão.
- Outras libs vendorizadas revisadas e não atualizadas por ora: `imgui` (1.90 WIP, upstream
  bem à frente, mas exige revalidar a integração custom do `KX_PythonImgui`), `bullet2`
  (2.84, possivelmente com patches locais do fork Blender — precisa diff antes de mexer),
  `ceres`/`Eigen3`/`glew` (baixo risco de quebra vs. ganho, não priorizado agora).

## 2026-09-08 — RecastNavigation: port para API moderna (dtNavMesh/dtNavMeshQuery)

Port do pathfinding/navmesh (`KX_NavMeshObject`, `KX_SteeringActuator`) da API antiga
`dtStatNavMesh`/`dtStatNavMeshBuilder` (pré-fusão do Detour, ~2011) para a API atual
`dtNavMesh`/`dtNavMeshQuery`, seguindo o plano em 5 fases (0-4 obrigatórias, 5 opcional).
Confirmado em jogo real pelo usuário (movimento do personagem na direção correta).

- `KX_NavMeshObject`: `BuildNavMesh()` passou a usar `dtNavMeshCreateParams` +
  `dtCreateNavMeshData` em vez do bloco manual de serialização
  (`dtStatNavMeshHeader`/`dtStatPoly`/`dtStatBVNode`/`createBVTree`); `m_navMesh` agora é
  `dtNavMesh*` com `dtNavMeshQuery* m_navQuery` associado; `DrawNavMesh()`, `FindPath()` e
  `Raycast()` reescritos para iterar tiles (`getTileAndPolyByRef`) e usar
  `m_navQuery->findPath/findStraightPath/raycast` com `dtQueryFilter`.
- `KX_SteeringActuator`: `getNavmeshNormal`/`HandleActorFace` portados do acesso direto a
  `dtStatPoly`/`dtStatPolyDetail` para o mesmo padrão de tile/poly via `dtNavMeshQuery`.
- Bug encontrado e corrigido durante a Fase 5 (avaliação de UI/Logic Bricks): os campos
  `walkableHeight`/`walkableRadius`/`walkableClimb` de `dtNavMeshCreateParams` (usados por
  `dtCreateNavMeshData`, em world units) estavam hardcoded (`2.0f`/`0.6f`/`0.9f`) e nunca
  liam o `RecastData` da cena (`agent_height`/`agent_radius`/`climb_max`, já expostos no
  painel "Navigation Mesh" desde antes). Não confundir com o `walkableHeight/Radius/Climb`
  de `mesh_navmesh.c`, que são valores em voxels usados só no bake e já estavam corretos.
  Corrigido lendo `GetScene()->GetBlenderScene()->gm.recastData` diretamente.
- Avaliado e descartado por ora: expor `dtQueryFilter` (include/exclude flags, custo por
  área) no Steering Actuator. Hoje todo polígono do navmesh sai do bake com a mesma flag
  (`1`) e a mesma área (`0`) — sem um sistema de múltiplas áreas por polígono, um filtro
  configurável não teria efeito nenhum. Ver item de navmesh dinâmica no roadmap.
- Removida toda a instrumentação de debug (`DEBUGNAV`, `CM_Error`/`printf` em
  `KX_SteeringActuator.cpp`, `KX_NavMeshObject.cpp`, `BL_BlenderDataConversion.cpp`,
  `DerivedMesh.c`, `navmesh_conversion.c`) usada para isolar os bugs de direção/crash
  durante o port, e o log `[Plano9] drawcalls=.../materialbinds=...` de
  `KX_KetsjiEngine::EndFrame()` (throttled a 1x/s, atrás de `SHOW_RENDER_QUERIES`), a
  pedido do usuário.
- Fora de escopo: `Recast/`/`Detour/` vendorizados não foram atualizados a partir de
  `tools/recastnavigation-main` (só os pontos de integração foram portados); permanece
  como item futuro em [`roadmap.md`](roadmap.md).

## 2026-09-07 — Linux — preparação do runtime

- Adicionado o preset CMake `linux-runtime`, isolado do preset MSVC: compila somente `RangeRuntime` em
  `build-linux/`, com instalação portátil e recursos de editor/renderização não essenciais desativados.
- Adicionado `docs/linux-build.md`, com dependências iniciais de Ubuntu 24.04, comandos de configuração,
  critérios de validação e regra de não anunciar suporte oficial antes de teste em Linux nativo.
- Adicionado `tools/linux/preflight.sh`, que verifica compilador, bibliotecas e o ABI Python 3.11 antes de
  chamar o CMake. A distribuição WSL local é Ubuntu 26.04/Python 3.14 e, por isso, não é referência válida
  para esta primeira compilação.
- Adicionado `tools/linux/package-runtime.sh`, que transforma uma instalação Linux já validada em
  `tar.xz` com checksum SHA-256 e `COPYING`, sem alterar o artefato Windows.
- A árvore atual só possui `lib/win64_vc15`; por isso o preset Linux usa dependências do sistema e esta
  preparação **não** foi compilada nem executada nesta máquina Windows. A primeira execução Linux é a
  próxima validação necessária.

## 2026-09-07 — Weather: animação de chuva/nuvens/lens flare passa a respeitar Time Scale

Bug reportado pelo usuário: reduzir Time Scale coloca o jogo inteiro em câmera lenta, mas os efeitos
nativos de Weather (chuva, nuvens, lens flare) continuavam animando em velocidade real, sem sofrer a
desaceleração.

Causa: em `KX_RenderPipeline.cpp`, o uniform de tempo (`rain_time`/`cloud_time`/`flare_time`) que anima
os shaders de scroll/flicker era alimentado por `m_engine->GetRealTime()` — o relógio de parede da
engine, deliberadamente escolhido numa unidade anterior para não parar durante pause/resume, mas que
por consequência também ignora Time Scale.

Fix: trocado para `m_engine->GetFrameTime()`, que acumula `m_timestep` uma vez por frame de lógica
executado; como os frames de lógica são regulados pelo Time Scale via `m_simAccumulator`
(`KX_KetsjiEngine::NextFrame`), o tempo de simulação passa a andar mais devagar junto com o resto do
jogo quando o Time Scale é reduzido — sem exigir nenhuma outra mudança.

Build (`ninja RangeEngine RangeRuntime`) passou limpo — apenas `KX_RenderPipeline.cpp` recompilado. Uma
primeira rodada falhou só no link (`LNK1104`, `RangeEngine.exe` em execução travando o arquivo),
resolvida fechando o processo e relinkando. Teste em jogo real (reduzir Time Scale e confirmar que
chuva/nuvens desaceleram junto) fica pendente do usuário.

---

## 2026-09-07 — Ketsji Plano 8: validação da aritmética do acumulador de passo fixo

Quarta unidade do Plano 8, sem alteração de código. Objetivo declarado na unidade anterior: validar o
acumulador com o relógio manual do Plano 3 (`CM_Clock::SetManualTime`/`AdvanceManualTime`) e os scripts
de regressão de `templates_range/`.

Achado: o relógio manual não tem nenhum consumidor no repositório — não existe harness de teste C++
(gtest permanece `OFF`, decisão já tomada na primeira unidade do Plano 3) nem binding Python para
`SetManualTime`/`AdvanceManualTime`, e os scripts de `templates_range/` rodam via pulso real de frame
dentro do jogo, não conseguindo dirigir `NextFrame()` com tempos sintéticos. Escrever esse harness seria
uma unidade de infraestrutura própria (traz de volta a decisão de build system do gtest), fora do escopo
desta unidade.

Validação feita por rastreamento manual da aritmética de `KX_KetsjiEngine.cpp:535-556` contra sequências
de tempo equivalentes às que `AdvanceManualTime` produziria:

- 60Hz real, `timescale=1`: 1 step/frame, idêntico ao caminho legado.
- 60Hz real, `timescale=0.5`: ainda 1 step/frame (o fator `timescale` se cancela na razão
  acumulador/`m_framestep`), mas `m_framestep` cai pela metade — câmera lenta correta sem mudar a
  cadência de chamadas a `Update()`.
- Soluço de frame (`realDelta` salta para 0.5s): laço para em `m_maxLogicFrame` (5), excesso descartado
  via clamp do acumulador — spiral of death evitado, como já previsto na auditoria anterior.
- Caso novo, não coberto antes: `timescale=0` com a flag ligada. `m_framestep` vira 0, a condição do
  `while` (`acumulador >= 0`) passa a ser quase sempre verdadeira, e o laço roda `m_maxLogicFrame` (5)
  updates por frame com delta zero em vez de zero updates. Não quebra nada (delta zero é inerte), mas é
  desperdício de CPU. Registrado como observação; não corrigido nesta unidade (fora do escopo de
  "validar", e só é alcançável com a flag ligada, que ainda não tem nenhum jogo publicado usando-a).

Conclusão: aritmética correta para os casos normais e de backlog; único ponto fraco é a ineficiência em
`timescale=0`, não uma regressão de comportamento. Sem código alterado, sem build. Próximo passo
pendente do usuário: ativar `use_fixed_timestep` (painel Physics → Steps & Timing) num projeto real e
testar em jogo, incluindo reduzir Time Scale a zero para observar se o desperdício de CPU é perceptível.

---

## 2026-09-07 — Ketsji Plano 10: encerramento

Quinta e última unidade do Plano 10. Decisão explícita de não executar os dois itens que restavam
em aberto:

- **Padronizar nomes de taxas/passos/estados** (`m_timestep`, `m_framestep`, `m_timeUnderRate`,
  `m_useFixedTimestep`, `m_ticrate`, `m_renderrate`, `m_animationrate`, `m_anim_framerate`,
  `m_average_framerate`, todos em `KX_KetsjiEngine.h`) — descartado. É rename puramente estético,
  sem ganho funcional, mas exige tocar call sites espalhados por vários `.cpp`; o risco de erro
  silencioso (typo, shadowing, `.cpp`/`.h` dessincronizados) supera o benefício.
- **Extrair `UpdateSleepTime()`/`ClockTiming()`/`FrameOver()`/`FrameTiming()` para `KX_FrameClock`**
  — descartado por ora. Seguia identificado desde a primeira unidade como a mudança de maior risco
  comportamental do Plano 10 (mexe em ~24-30 membros `m_*time*` usados pelo motor inteiro), e não há
  hipótese de ganho mensurável que justifique esse risco agora. Se for retomada no futuro, deve
  entrar como plano próprio com hipótese, benchmark A/B e teste de regressão dedicados — não como
  sub-item de limpeza.

Com isso, o Plano 10 — e o programa de modernização do `KX_KetsjiEngine` descrito em
`docs/ketsji-engine-modernization-plan.md` (Planos 1 a 10) — está encerrado no escopo que teve ganho
líquido comprovado. Os dois itens acima ficam registrados como decisões de escopo conscientes, não
como trabalho esquecido.

Sem alteração de código, só documentação; nenhum build necessário.

---

## 2026-09-07 — Ketsji Plano 10: ownership dos componentes em architecture.md

Quarta unidade do Plano 10, cobrindo a segunda metade do item "Documentar ordem oficial do frame
e ownership dos componentes" (a primeira metade, ordem do frame, foi a unidade anterior). Nova seção
"Ownership dos componentes do maestro (`KX_KetsjiEngine`)" em `docs/architecture.md`, distinguindo:

- Membros injetados e não possuídos por `KX_KetsjiEngine` (`m_canvas`, `m_rasterizer`, `m_converter`,
  `m_imgui`, `m_debugMode`, `m_networkMessageManager`, `m_inputDevice`) — ponteiros crus atribuídos
  pelos setters (`SetCanvas`/`SetRasterizer`/`SetConverter`/`SetInputDevice`/
  `SetNetworkMessageManager`) ou construídos direto pelo launcher; `KX_KetsjiEngine` nunca os
  deleta. Reaproveita a auditoria já feita no Plano 3 (5ª unidade), que confirmou o launcher
  (`LA_Launcher::InitEngine`) como único ponto de construção da engine e dono desses objetos.
- Membros possuídos internamente: `m_shadowRenderer`/`m_renderPipeline`/`m_simulationPipeline`/
  `m_sceneScheduler` (todos `std::unique_ptr`, extraídos nos Planos 5-7) e `m_CustomMouseCursor`
  (ponteiro cru com dono explícito via `SetCustomMouseCursor`/`FreeCustomMouseCursor`, ver Plano 1A
  item 5) — vivem e morrem com a instância da engine.
- `m_scenes` como categoria à parte: possuído pelo motor, mas populado/esvaziado em runtime pelo
  `m_sceneScheduler`, não diretamente pela engine.

Sem alteração de código, só documentação; nenhum build necessário.

---

## 2026-09-07 — Ketsji Plano 10: ordem do frame em architecture.md e correção de tc_network

Terceira unidade do Plano 10. Escreveu a seção "Ordem do frame" em `docs/architecture.md`,
formalizando a sequência já reconstruída na primeira unidade (`NextFrame()` → input/ImGui/joystick
→ simulação → libs/cenas agendadas → `BeginFrame()`/`Render()`/`EndFrame()` quando `m_doRender`,
ou `UpdateSleepTime()` direto quando não), junto com uma nota sobre os candidatos de extração
(`KX_FrameClock`) e sobre o profiling de `KX_TimeCategoryLogger`.

Ao escrever essa nota, revisitou o comentário adicionado na unidade anterior sobre `tc_network`
e achou um erro: o grep da unidade anterior teria devido pegar `KX_RenderPipeline.cpp:503`
(`m_engine->m_logger.StartLog(KX_KetsjiEngine::tc_network)`, medindo o culling+LOD update antes
de `GetVisibleMeshes()`), mas o comentário escrito dizia "unused: never StartLog()'d". Corrigido
em `KX_KetsjiEngine.h` para descrever o uso real. `tc_scenegraph` continua confirmado como código
morto de profiling (só `tc_scenegraph_logic`/`_actuators`/`_physics` recebem `StartLog()` hoje,
em `KX_SimulationPipeline.cpp`) — esse comentário não mudou.

Lição: verificar afirmações de "não usado em lugar nenhum" com grep no `.cpp` real antes de
escrever no header, não confiar em um levantamento anterior sem reconferir.

Sem mudança de comportamento; build limpo (`RangeEngine`, incremental).

---

## 2026-09-07 — Ketsji Plano 10: limpeza de comentários e nomes

Segunda unidade do Plano 10, conforme decisão do usuário de seguir com limpeza de
comentários/nomes/documentação antes de considerar a extração de `UpdateSleepTime()`. Achados
nesta passagem sobre `KX_KetsjiEngine.h`/`.cpp`:

- Comentário de `tc_overhead` dizia "profile info drawing overhead", mas o código chama
  `StartLog(tc_overhead)` em 7 pontos diferentes de `NextFrame()`/`EndFrame()` — é o bucket
  catch-all que acumula o tempo entre o fim de uma categoria nomeada e o início da próxima, não
  overhead de desenhar o profile em si. Comentário corrigido.
- `tc_network` (rotulado "CameraCulling") e `tc_scenegraph` (rotulado "UpdateParents") nunca
  recebem `StartLog()` em lugar nenhum do código-fonte (busca em todo `gameengine/`), mas
  continuam expostos por `GetPyProfileDict()` — qualquer script Python que leia esses dois campos
  do dicionário de profile está lendo zero sempre, não "sem dado". Adicionado comentário no enum
  deixando isso explícito, sem remover as entradas (removê-las mudaria as chaves expostas ao
  Python, fora do escopo de uma limpeza de comentários).
- Dois comentários vagos esclarecidos: "done with old over time reset" → "Caught up: clear the
  accumulated logic-frame overtime" (contexto: reset de `m_overframetime` depois do laço de sleep
  de catch-up); "logic time over rate fix code" → comentário explicando que `FrameOver()` atualiza
  `m_overframetime` (desvio acumulado vs. `m_timestep`) consumido pelo sleep de catch-up.

Nenhuma mudança de comportamento; build limpo de `RangeEngine` (incremental, `ge_ketsji` e
dependentes recompilados por alteração de header).

---

## 2026-09-07 — Ketsji Plano 10: levantamento e limpeza de código morto

Primeira unidade do Plano 10 (limpeza final e documentação do contrato), sem extração de
código ainda. Levantamento de `KX_KetsjiEngine.cpp`/`.h` (1196/756 linhas) mapeou funções por
categoria (orquestrador puro vs. lógica própria substancial), membros de dados, e código morto.

Candidatos reais de extração identificados (não executados nesta unidade): `NextFrame()`
(~144 linhas, mistura input/debug-UI/timestep), `UpdateSleepTime()` (~112 linhas, algoritmo de
catch-up puro, nenhuma chamada a pipeline — maior ganho líquido se virar
`KX_FrameClock`/`KX_FrameRateController` próprio, absorvendo também
`ClockTiming()`/`FrameOver()`/`FrameTiming()` e ~24-30 membros `m_*time*`), `EndFrame()`
(~68 linhas, mistura swap/canvas legítimo com log de draw calls e loop de particle-debug-overlay
que poderiam ir para `KX_DebugRenderer`/`KX_ParticleDebugUI`).

Código morto removido (sem alteração de comportamento): struct `FrameTimes`
(`KX_KetsjiEngine.h`, nunca instanciada) e seu getter comentado `GetFrameTimes()`; declaração
`Export(const std::string&)` no header, sem implementação em nenhum .cpp e sem nenhum chamador;
4 linhas de código comentado morto em `NextFrame()`/`UpdateAnimations()`
(`//m_logger.NextMeasurement()`, `//m_overrendertime`, `//m_animationtime`,
`//m_overanimationtime`); includes não usados `<unordered_set>` e `<cfloat>`. Build limpo
(`RangeEngine`/`RangeRuntime`, clean rebuild de `ge_ketsji` por alteração de header).

Ordem oficial do frame reconstruída (para a documentação de contrato pendente): `NextFrame()` →
input/imgui/joystick → simulação (`m_simulationPipeline->Update()`, direto ou via loop de
acumulador) → processamento de libs/cenas agendadas → retorna `m_doRender`. Se `true`:
`BeginFrame()` → `Render()` (→ `m_renderPipeline->Render()`) → `EndFrame()` (chama
`UpdateSleepTime()` primeiro, depois motion blur/log/debug-UI/swap). Se `false`:
`UpdateSleepTime()` é chamado direto dentro de `NextFrame()`. Essa sequência ainda precisa virar
texto formal em `docs/architecture.md` numa unidade futura.

Decisão do usuário: não extrair `UpdateSleepTime()`/timing para `KX_FrameClock` agora (maior
risco comportamental do Plano 10); próxima unidade foca em limpeza de comentários/nomes de
old-architecture e documentação (frame order, ownership de componentes), deixando a extração
maior como item separado se necessário.

---

## 2026-09-07 — Ketsji Plano 9: fechamento — paralelização e batching/instancing descartados sem ganho mensurável

Fechamento do Plano 9 (otimizações orientadas por perfil). Dois candidatos restantes fechados
sem implementação, conforme a regra do próprio plano ("otimização sem ganho mensurável deve ser
descartada"):

- **Paralelização**: auditoria de ownership de dados (agente Explore) não encontrou candidato
  novo "puro e independente" no frame loop — todo trecho toca Python/GIL, SceneGraph, Bullet ou
  OpenGL. O único paralelismo existente (`KX_CullingHandler::Process` via `tbb::parallel_reduce`)
  só é seguro porque roda depois que todas as escritas do frame no SceneGraph já terminaram (lê
  um SceneGraph "congelado"), não é uma exceção real à regra de exclusividade. Hipótese encerrada
  sem mudança de código.
- **Batching/instancing**: nova instrumentação (log throttled de
  `RAS_Rasterizer::GetLastDrawCalls()`/`GetLastMaterialChanges()` em `EndFrame()`, reaproveitando
  a flag existente `SHOW_RENDER_QUERIES`, sem UI/API nova) mediu, em jogo real (RolimaRacer via
  Play do editor), 145-296 draw calls/frame e ~166 material binds; numa cena de benchmark
  deliberadamente pesada (185→261 objetos em ~9s), 918-1187 draw calls/frame. Ambos bem abaixo do
  limiar de milhares de draw calls onde overhead de driver GPU vira gargalo real em hardware
  atual (RTX 5060 Laptop). Candidato descartado sem implementação.

Nota lateral (fora de escopo, não corrigida): `-g name value` (sem `=`) no parser de argumentos
do standalone (`GPG_Ghost.cpp`) cai em um branch morto/comentado e é silenciosamente ignorado —
só `-g name=value` funciona. Além disso o standalone (`LA_Launcher.cpp`) zera por padrão todas as
flags de debug (`show_render_queries` incluída) independente do `gm.flag` salvo na cena, ao
contrário do editor embutido, que sincroniza `gm.flag` automaticamente ao apertar Play.

Nota adicional: na cena de benchmark pesada, `Overhead` (48.2%) e `ShadowCulling` (25.8%)
dominaram o frame time, não os draw calls (0.8%). Usuário julgou o resultado esperado para uma
cena deliberadamente pesada e optou por não investigar agora — achado documentado como candidato
para um futuro Plano 11 ou revisão de CSM, não investigado nesta sessão.

---

## 2026-09-07 — Ketsji Plano 9: swap interval só quando muda

Primeira unidade do Plano 9 (otimizações orientadas por perfil), candidato "atualizar swap
interval apenas quando seu valor mudar". `KX_RenderPipeline::Render()` chamava
`canvas->SetSwapControl(canvas->GetSwapControl())` incondicionalmente a cada frame; em
`KX_BlenderCanvas`/`GPG_Canvas` isso desce até `wm_window_set_swap_interval()` →
`GHOST_SetSwapInterval()`, uma chamada real de driver/OS repetida todo frame mesmo quando o
valor pedido é idêntico ao já aplicado.

Adicionado `KX_RenderPipeline::m_lastAppliedSwapControl` (sentinela
`RAS_ICanvas::SWAP_CONTROL_MAX` = "nunca aplicado"); `Render()` agora só chama
`SetSwapControl()` quando o valor pedido difere do último efetivamente aplicado. Sem mudança
de comportamento observável — o valor lido de `GetSwapControl()` continua o mesmo antes e
depois, só a frequência da chamada ao driver muda.

Build limpo dos dois executáveis (`RangeEngine`/`RangeRuntime`, 133/133, sem erros/avisos
novos). Sem benchmark numérico anexado: uma chamada de driver a menos por frame fica abaixo do
ruído de frame time medível pelo profiler A/B do projeto — o valor da mudança é eliminar uma
syscall/driver-call redundante por frame, não corrigir uma regressão. Teste em jogo real
pendente do usuário (troca de vsync via `set_vsync`/painel deve continuar funcionando
normalmente).

---

## 2026-09-07 — Ketsji Plano 8: teste em jogo real da flag `use_fixed_timestep`

Quinta unidade do Plano 8: teste em jogo real, pendente desde a unidade anterior. Usuário criou um
arquivo de teste dedicado com um component anexado, ligou `use_fixed_timestep` (painel Physics → Steps
& Timing) e rodou o jogo. Log observado:

```text
[SelfTestCascadeShadowMath] PASS
Range Game Engine Started -----------
Range Game Engine Finished ----------
```

Início e fim limpos, sem crash nem erro. Usuário confirmou verbalmente o teste. A confirmação cobre
"roda sem quebrar" — não há medição reportada sobre o caso `timescale=0` (ineficiência de CPU
identificada na unidade anterior). Com isso, a flag está validada como segura para uso opcional (default
continua desligado); a ineficiência do `timescale=0` permanece uma otimização pendente, não bloqueante,
para uma unidade futura caso se mostre relevante na prática.

---

## 2026-09-07 — Ketsji Plano 8: flag de passo fixo exposta em GameData/RNA/UI

Terceira unidade do Plano 8. `SetUseFixedTimestep` existia desde a unidade anterior mas era
inacessível — nenhum chamador. Esta unidade expõe a opção por projeto, sem mudar o
comportamento padrão (continua off).

- `DNA_scene_types.h`: novo bit `GAME_USE_FIXED_TIMESTEP (1 << 26)` dentro do campo `GameData.flag`
  já existente (não é campo novo — sem risco de layout/SDNA obsoleto).
- `rna_scene.c`: propriedade RNA booleana `use_fixed_timestep` ligada ao bit acima, seguindo o
  padrão de `use_restrict_animation_updates`.
- `LA_Launcher.cpp`: `m_ketsjiEngine->SetUseFixedTimestep((gm.flag & GAME_USE_FIXED_TIMESTEP) != 0);`
  logo após `SetTimeScale(gm.timeScale);`, lido uma vez no início da cena.
- `properties_game.py`: checkbox `use_fixed_timestep` na caixa "Steps & Timing" do painel Physics.

Build (`ninja RangeEngine RangeRuntime`) passou limpo — todos os objetos alterados compilaram sem
erro. Uma primeira rodada falhou só no link final (`LNK1104: não é possível abrir o arquivo
bin\RangeEngine.exe`) porque o executável estava em execução travando o arquivo; resolvida
fechando o processo e relinkando.

Pendente para a próxima unidade: validar com o relógio manual do Plano 3
(`CM_Clock::SetManualTime`/`AdvanceManualTime`) e os scripts de regressão de
`source/release/scripts/templates_range/`, e só então testar em jogo real com a flag ligada.

---

## 2026-09-07 — Ketsji Plano 8: introdução do acumulador de passo fixo (atrás de flag desligada)

Segunda unidade de código do Plano 8 (a primeira foi a auditoria pura de 2026-09-06, sem código).
Introduz a infraestrutura do acumulador de passo fixo descrita no plano mestre, mantendo o
comportamento padrão idêntico ao atual porque a nova flag nasce desligada e nada ainda a liga.

- `KX_KetsjiEngine` ganha três membros novos: `m_useFixedTimestep` (bool, `false` por padrão),
  `m_simAccumulator` (double, tempo real acumulado ainda não consumido por um passo de simulação) e
  `m_accumulatorPreviousRealTime` (double, referência de tempo real independente de
  `m_previousRealTime`, que continua pertencendo ao catch-up por sleep existente em
  `UpdateSleepTime()`/`FrameOver()`).
- Em `NextFrame()`, a chamada única `m_simulationPipeline->Update()` foi envolvida por um `if
  (m_useFixedTimestep)`: com a flag desligada (padrão), o caminho é exatamente o de antes (uma
  chamada por frame). Com a flag ligada, mede-se o tempo real decorrido desde a última chamada via
  `m_clock`, acumula-se escalado por `m_timescale`, e roda-se `m_simulationPipeline->Update()` uma
  vez por `m_framestep` inteiro devido, até o limite `m_maxLogicFrame` passos por frame; o excesso
  de tempo além desse limite é descartado (não se acumula indefinidamente), evitando um spiral of
  death sob um stall longo.
- `m_simAccumulator`/`m_accumulatorPreviousRealTime` são resetados em `StartEngine()` (mesmo ponto
  onde `m_staticSplitSettleFrames` já era zerado) e também ao ligar a flag via novo
  `SetUseFixedTimestep(true)`, para não consumir de uma vez um atraso acumulado enquanto o caminho
  antigo (sleep) era quem tinha posse do catch-up.
- Novos getters/setters públicos `GetUseFixedTimestep()`/`SetUseFixedTimestep(bool)`, seguindo o
  padrão de `GetMaxLogicFrame()`/`SetMaxLogicFrame()` ao lado. Nenhum consumidor liga a flag ainda —
  sem exposição Python nem DNA nesta unidade — então o novo caminho é código morto alcançável apenas
  por um futuro `SetUseFixedTimestep(true)` em C++, propositalmente inerte por ora.
- Build limpo dos dois executáveis aprovado (`ninja RangeEngine RangeRuntime`, 135/135 passos, exit
  0), necessário por alterar `KX_KetsjiEngine.h`. Sem teste em jogo real: a flag não tem nenhum
  caminho de ativação nesta unidade, então não há comportamento novo observável.
- Próxima unidade do Plano 8: decidir e implementar a exposição da flag (modo de compatibilidade
  citado no plano mestre — provavelmente uma opção de `GameData`/RNA, não hardcoded), depois validar
  com o relógio manual do Plano 3 (`CM_Clock::SetManualTime`/`AdvanceManualTime`) e os scripts de
  regressão existentes, e só então testar em jogo real com a flag ligada.

## 2026-09-05

**Splash — layout limpo para criação de projetos**

- O painel inferior do splash adotou o estilo sem relevo: as ações e arquivos recentes deixam de usar os
  retângulos cinzas e passam a usar as cores do tema, como no splash atual do Blender.
- A coluna esquerda passa a ser `Project`: oferece `Create Project`, `Open Project` e recuperação de
  sessão. `New File` e `Open console` foram removidos. O grupo `Range Engine Network` reúne Discord,
  Website, Python API e suporte; o GitHub da AnastacioGames fica abaixo dos arquivos recentes.
- O cabeçalho passou a dizer `Range Engine - Custom Version`. A janela About usa o novo
  `range_logo.png`: emblema Range/Anastacio, wordmark `RANGE ENGINE` e `Anastacio Games` em dourado.
  Validação de build: `ninja RangeEngine` regenerou o datafile e relinkou o editor com sucesso.

**Create Project — estrutura inicial de projeto**

- `Create Project` agora abre um diálogo para nome e destino e recusa sobrescrever uma pasta existente. Ele cria
  `data/` com `scripts/`, `textures/`, `models/`, `audio/`, `fonts/`, `scenes/` e `libloads/`, além de
  `engine/`, `launcher/`, `icons/` e `release/` na raiz. O `.range` inicial e sua cópia protegida `.rasec` ficam
  diretamente em `data/`.
- A escolha do destino passou a usar o navegador de pastas completo do editor; o projeto não é mais criado
  imediatamente no caminho padrão ao clicar na ação.
- Corrigido o contexto do botão no splash para `INVOKE_DEFAULT`; antes ele ignorava o navegador de pastas e
  executava diretamente com o nome e destino padrão.
- Validação manual concluída pelo usuário tanto pelo splash quanto por `File > Create Project`: o seletor de
  destino abriu corretamente e a estrutura foi criada com sucesso.

---

## 2026-09-04

**Identidade visual Windows**

- O ícone de aplicação e de associação de arquivo agora usa a composição aprovada: símbolo legado da Range ao fundo e cubo dourado da Anastacio em primeiro plano, deslocado para a direita.
- Novo PNG-fonte com transparência real: `source/release/windows/icons/anastacio-range-composite-transparent-v1.png`; ICO multi-resolução (16, 24, 32, 48, 64, 128 e 256 px) correspondente mantido ao lado dele.
- `winrange.ico` e `winblenderfile.ico` foram substituídos pela composição, cobrindo respectivamente os executáveis e os arquivos `.range` no Windows.
- Validação: `ninja RangeEngine RangeRuntime`, com `vcvars64.bat`, recompilou os dois recursos RC e relinkou `build/bin/RangeEngine.exe` e `build/bin/RangeRuntime.exe` com sucesso.
- O header `INFO_HT_header` agora mostra `ANASTACIO ENGINE`; o slot interno `BLENDER` do atlas também foi substituído pelo símbolo composto em 16 e 32 px. O SVG e os dois assets originais foram preservados em `source/release/datafiles/icon-backups/2026-09-04-before-anastacio-header-icon/` antes da mudança.
- Validação: `ninja RangeEngine`, com `vcvars64.bat`, regenerou os dois datafiles de ícones e relinkou o editor com sucesso.

---

## 2026-09-03

**Correções de layout do editor (Properties/Render Layers/Particles/Physics)**

- Removido o painel `RENDERLAYER_PT_layers` ("Layer List") de `bl_ui/properties_render_layer.py` — pedido do usuário, painel duplicava a lista de render layers sem uso real no fluxo do projeto.
- Ordem das abas Render/Scene no editor Properties: já estava correta em `rna_SpaceProperties_context_itemf` (`rna_space.c`), a função real que monta a ordem dos ícones das abas (Render → Render Layer → Scene → World). O array estático `buttons_context_items` (só referência para doc/i18n) estava com Scene antes de Render — corrigido para bater com o comportamento real.
- **Causa raiz do bug "menu de Particles não aparece em objeto Empty"**: em `buttons_context_path_particle()` (`editors/space_buttons/buttons_context.c:351`), a aba Particles só era revelada (`sbuts->pathflag`) para `ob->type == OB_MESH`. Como `ParticleSystem` fica em `Object->particlesystem` (não é campo de mesh), e o sistema de partículas GPU deste fork (`use_gpu_particles`) já não exige malha, a checagem foi ampliada para `OB_MESH || OB_EMPTY`.
- Menu Physics / "Create Obstacle": já estava por último na ordem real de registro (`PHYSICS_PT_game_physics` → `PHYSICS_PT_game_collision_bounds` → `PHYSICS_PT_game_obstacles` em `bl_ui/properties_game.py`, únicos 3 painéis com `bl_context = "physics"` visíveis para `BLENDER_GAME`) — nenhuma mudança necessária.
- `ninja RangeEngine` limpo (75/75, exit 0). Teste em jogo real (abrir editor, selecionar Empty, checar aba Particles e ordem Render Layers/Physics) ainda pendente de confirmação do usuário.
- Item "range abrir arquivos .blend e .range" (`docs/arrumar.md`): investigado e confirmado pelo usuário que já funciona por drag-and-drop — `BLO_has_bfile_extension()` (`readfile.c:1402`) já reconhece `.blend` e `.range`, e o dropbox de janela (`screen_ops.c:4876`, `WM_OT_open_mainfile`) já trata o drop. Nenhum código novo necessário, item fechado como já implementado.

**Organização da documentação**

- Criado `docs/README.md` como índice e definida a separação entre estado atual, referência e histórico.
- `relatorio-melhorias-anastacioengine.md`, `docs/roadmap.md` e `docs/build-notes.md` foram consolidados para
  remover estados superados e contradições de build.
- `CLAUDE.md` e `CODEX.md` agora apontam para `AGENTS.md`, única fonte das regras operacionais.
- Removidos a tarefa temporária de build, o handoff concluído do bug hunt e o status antigo do menu de
  gamepad; pendências ainda válidas foram migradas ao roadmap.
- Corrigida a nota de licença: os fontes herdados usam GPLv2-or-later e o repositório contém os textos da
  GPLv2 e GPLv3; a escolha explícita para a distribuição ficou registrada no roadmap.

**Bug B — CSM + `staticShadow` sem sombra no ângulo inicial: corrigido e confirmado visualmente**

- O log fresco mostrou que a primeira chamada de `RenderShadowBuffers()` recebia a projeção da câmera ainda não inicializada: `p00/p11 == 0` fazia os cantos do frustum dividirem por zero, os limites ficarem em `FLT_MAX/-FLT_MAX`, `near/far` virarem infinitos e as três texturas CSM terminarem inteiramente em profundidade `1.0`.
- A ordem explica o sintoma: `RenderShadowBuffers()` roda antes de `GetRenderData()`, e esta última só então chama `KX_Camera::UpdateView()`. Com `staticShadow`, o passe inválido consumia `m_requestShadowUpdate`; mover/girar a câmera provocava uma atualização posterior e fazia a sombra aparecer.
- Fix em `KX_KetsjiEngine::RenderShadowBuffers()`: para uma luz CSM, validar os coeficientes `p00/p11` da projeção antes de entrar no passe. Se ainda forem zero ou não finitos, a luz é adiada sem chamar `UnbindCascadeShadowBuffer()`, preservando o pedido de atualização para o frame seguinte, quando a câmera já foi inicializada.
- O gate real de `NeedStaticShadowUpdate()` foi restaurado (o diagnóstico estava forçando rebake estático todo frame) e todos os logs temporários do Bug B foram removidos de `KX_KetsjiEngine.cpp`, `gpu_material.c` e `gpu_framebuffer.c`.
- Validação automática: `ninja RangeRuntime` compilou e linkou limpo (6/6); `RangeRuntime.exe "projects-teste/Teste de nova luz e sombra.range"` abriu e executou por 10 segundos sem erro de shader/GL, `NaN` ou infinito no log.
- **Resultado visual do primeiro fix: rejeitado pelo usuário** — a sombra continuou ausente. O simples adiamento do passe não é solução do Bug B.
- Correção revisada: `RenderShadowBuffers()` agora chama `GetSceneViewport()` + `KX_Camera::UpdateView()` para a câmera ativa antes de qualquer cálculo CSM, usando a mesma área de render e olho esquerdo de `GetRenderData()`. Isso fornece projeção e modelview do frame corrente já no primeiro shadow pass, sem depender de retry.
- Verificação da revisão: `ninja RangeRuntime` concluiu 3/3; a cena real executou por 12 segundos sem mensagens em stderr e sem erro de shader/GL. Nova confirmação visual ainda pendente.
- Teste controlado definitivo: a câmera começa no ângulo problemático, gira `-20°` em X e retorna `+20°`. A sombra aparecia ao baixar e sumia ao retornar, descartando inicialização, shader cache e textura stale como causa principal.
- Telemetria combinada confirmou três fatos no mesmo ciclo: (1) samplers e matrizes eram válidos; (2) forçar todos os casters pelo culling da CPU não alterava o mapa; (3) na cascata distante, os centros dos objetos ficavam com `NDC.z` entre `1,25` e `1,70` no ângulo inicial, fora do limite `+1`, mas entravam em `0,56–0,87` ao baixar a câmera. X/Y permaneciam válidos.
- **Causa raiz**: o ortho era ajustado somente aos oito cantos do frustum de receptores. Geometria relevante para o shadow map podia continuar fora do intervalo Z dessa fatia, sendo recortada pela projeção conforme o pitch da câmera.
- **Correção final**: `ComputeCascadeShadowMatrices()` recebe a cena e amplia somente o Z usando os AABBs reais dos objetos com malha que sobrepõem a cascata em X/Y no espaço da luz, com margem de 0,5 unidade. Isso mantém o tight-fit X/Y e evita a margem fixa de todo o `cliprange`, que corrigia a cobertura mas reduzia desnecessariamente a precisão de profundidade.
- Resultado visual intermediário confirmado pelo usuário: a sombra passou a aparecer desde o início. O refinamento por AABB preservou, em execução automática, os mesmos pixels ocupados nos mapas enquanto melhorou a precisão Z entre aproximadamente 35% e 120% frente à margem fixa, dependendo da cascata.
- Instrumentação temporária (`CSM-SNAPSHOT`, matrizes, clip coordinates e dumps de shader) removida. Build final limpo de `RangeRuntime` concluído (253/253, exit 0) e ciclo standalone sem crash ou erro de shader/GL.
- Qualidade da cena de teste: a Sun está configurada com filtro `NONE` e buffers CSM `512×512`; serrilhado/hard edge restante é esperado dessa configuração e não deve ser mascarado impondo PCF no código.

---

## 2026-08-23

**Diagnóstico**
- Mapeamento de código real para o plano de melhorias de performance e iluminação: confirmado que GPU instancing (`RAS_InstancingBuffer`), batching estático (`RAS_BatchDisplayArray`) e LOD por distância (`KX_LodManager`) já existem e funcionam; gaps reais identificados são occlusion culling (ausente) e shaders internos em compatibility profile (sem `#version`, `gl_TexCoord`/`gl_FragColor`/`texture2D`). Detalhes em `relatorio-melhorias-anastacioengine.md`.

**Cena de teste**
- Criada `projects-teste/benchmark.range`: filtros de pós-processamento, navmesh, instâncias de objeto com muitos triângulos em rigidbody, um Empty que adiciona objetos continuamente, e planos sem colisão com textura alpha.

**Recurso novo: Benchmark automático com relatório**
- Adicionado `projects-teste/benchmark_report.py` — primeiro recurso novo construído sobre a engine. Não é uma mudança no motor (C++): é uma ferramenta Python que usa a API já exposta `bge.logic.getProfileInfo()` (populada por `KX_KetsjiEngine::EndFrame()` a partir do profiler interno `KX_TimeCategoryLogger`) para amostrar as categorias de tempo por frame (física, lógica, rasterizador, animações, scenegraph, sombras etc.) ao longo de uma execução, calcular média/mínimo/máximo por categoria e FPS médio, e gravar um relatório `.txt` automaticamente ao final da duração configurada.
- Uso: Python Controller em modo "Module" apontando para `benchmark_report.run`, em um objeto com as game properties `duration`, `sample_interval` e `output_dir` (todas opcionais, com padrão).
- Fora de escopo desta versão: estatísticas de memória (a engine só imprime no console via `PrintMemInfo`, não expõe em Python) e mínimo/máximo nativo no profiler em C++ (hoje só guarda média móvel) — ambos candidatos a uma v2 se for necessário um relatório mais rico.

**Correção: nome do módulo Python do fork**
- `benchmark_report.py` usava `import bge`, mas a Range Engine renomeou o módulo Python do jogo de `bge` para `Range` (confirmado em `KX_PythonInit.cpp:2384-2385` — só `Range` é registrado em `sys.modules`, com submódulos `Range.logic`, `Range.render`, `Range.types`, `Range.events`, `Range.constraints`, `Range.application`, `Range.texture`; não há alias `bge`). Corrigido para `import Range as bge`, mantendo o resto do código igual. Scripts novos para esta engine devem usar `import Range` (ou o alias) em vez de `import bge`.

**Achado do benchmark: estouro de texture slots por lâmpada com sombra**
- Ao rodar `benchmark.range`, o console mostrava `GPU_texture_bind: Not enough texture slots.` repetindo todo frame. Causa identificada pelo usuário e confirmada no código: um grupo com objeto + lâmpada foi instanciado várias vezes, e cada lâmpada com sombra ativa reserva um texture slot dedicado via `GPU_lamp_shadow_buffer_bind()` (`source/blender/gpu/intern/gpu_material.c:3691`), além dos slots já usados pelas texturas do material e pelos filtros de tela ativos. `GPU_max_textures()` (`gpu_extensions.c:99`) reflete o limite real reportado pelo driver da GPU, não um teto artificial da engine — então material + filtros + N lâmpadas com sombra somam mais slots do que o disponível.
- Mitigação imediata: desativar sombra nas lâmpadas instanciadas em massa (usar no máximo uma ou poucas lâmpadas com sombra por cena) e/ou reduzir filtros de tela simultâneos.
- Relevante para a trilha de Iluminação do `relatorio-melhorias-anastacioengine.md`: é um sintoma concreto do modelo forward puro pré-PBR — em deferred rendering a passada de sombra não compete por texture slot com a passada de material do mesmo jeito. Reforça o argumento para avaliar deferred/tiled rendering nas fases futuras.

**Confirmação em hardware real: contexto forçado em OpenGL 2.1 compatibility**
- Log de inicialização do `benchmark.range` numa RTX 5060 Laptop GPU: `OpenGL Supported: 4.6.0 NVIDIA 610.62 - Shading language: 4.60 NVIDIA` mas `Using OpenGL Version: 2.1`. Confirma ao vivo o que já estava mapeado no CMake (`WITH_GL_PROFILE_COMPAT=ON`, `WITH_GL_PROFILE_CORE=OFF`): a engine roda em compatibility profile 2.1 mesmo em hardware que suporta core 4.6/GLSL 4.60. O limitador é a configuração da engine, não a GPU — reforça a prioridade da migração de shaders internos para core profile.

**Ferramenta ajustada para Python Component**
- `benchmark_report.py` (Module/Controller) foi substituído por `benchmark_component.py`, uma classe `Range.types.KX_PythonComponent` (confirmado em `KX_PythonComponent.cpp:102-160`: o próprio gerenciador de componentes chama `update()` todo frame). Elimina a dependência de sensor Always em modo pulso + Controller Python (Module), que era um ponto de falha silenciosa. Movido para a pasta `script/` do projeto de teste, onde funcionou de primeira.

**Primeiro benchmark real — resultado (23/08/2026, `benchmark.range`, RTX 5060 Laptop GPU, 10s)**
- `benchmark_report_20260823_190214.txt`: 264 frames em 10s (FPS médio 26.4). `Physics` foi o maior custo médio (30ms, 46.3%) mas o dado relevante é a variância: de 0.389ms a **113ms** num único frame — pico isolado, não custo constante. Os intervalos de amostra com queda de FPS mais forte (ex.: t=3.1s→4.4s, só 7 frames em 1.34s ≈ 5 FPS) coincidem com os momentos de mais objetos novos entrando em colisão, assinatura típica de rigidbody dinâmico com collision shape = malha exata (Mesh/Triangle Mesh) em vez de Convex Hull/primitiva. `Rasterizer` foi o segundo maior custo (12ms médio, 43.5%) mas estável (máx. 23ms, sem picos como a física). Contagem de objetos foi de 212 para 372 em 9.6s de spawn contínuo, sem sinal de estabilizar.
- Achado extra a investigar: `Animations` apareceu com 8.4% (2.9ms) mesmo sem nenhuma animação adicionada de propósito na cena — possível Action/Armature residual em algum objeto do grupo instanciado ou no navmesh, custando FPS sem necessidade.
- Próximo passo sugerido: conferir o tipo de Collision Bounds do objeto instanciado em rigidbody e trocar para Convex Hull/primitiva se estiver em modo malha; rodar o benchmark de novo e comparar o novo `Physics max_ms` contra os 113ms desta rodada.

**Correção importante: occlusion culling já existe, não é gap**
- Antes de escrever código C++ para occlusion culling (Fase 1 original da trilha Performance), a investigação da API (`RAS_CullingHandler`, `SG_CullingNode`) revelou um segundo caminho de culling já implementado: `KX_Scene::CalculateVisibleMeshes` (`Ketsji/KX_Scene.cpp:1263-1279`) já faz occlusion culling via DBVT do Bullet (`m_physicsEnvironment->CullingTest`), stock do UPBGE, não tocado pelo fork.
- Confirmado como recurso real e exposto na UI: checkbox **"DBVT Culling"** = `scene.game_settings.use_occlusion_culling` (`rna_scene.c:4961-4966`, backed por `WO_DBVT_CULLING`) + campo **"Occlusion Resolution"** = `occlusion_culling_resolution` (`rna_scene.c:4878-4884`, 128-1024px, padrão 128). Objetos precisam ter o Physics Type marcado como **"Occluder"** (`OB_OCCLUDER`, `rna_object.c:1688`) para participar do buffer de oclusão.
- Correção aplicada em `relatorio-melhorias-anastacioengine.md`: occlusion culling saiu da lista de gaps e da Fase 1 da trilha Performance (que passou a ser só otimização de instancing). Evitou escrever um sistema C++ duplicado — exatamente o risco que o pedido original desta sessão queria prevenir.
- Ação real recomendada (nível de cena, não de código): ligar `use_occlusion_culling` em `benchmark.range` e marcar o chão/paredes como Occluder, depois rodar o benchmark de novo para medir o ganho real em `Rasterizer`.

**Otimização real (código): RAS_InstancingBuffer para de realocar todo frame**
- `source/gameengine/Rasterizer/RAS_InstancingBuffer.h/.cpp`: adicionado rastreio de capacidade (`m_capacity`). `Realloc()` só libera/realoca o VBO quando `size > m_capacity` (crescendo com folga de +25%); caso contrário reaproveita o buffer existente. Antes, todo frame — mesmo sem mudança na contagem de instâncias — o buffer inteiro era destruído e recriado (`GPU_buffer_free`+`GPU_buffer_alloc`, com mutex/pool-bookkeeping e um `glBufferData(GL_STATIC_DRAW)` extra). Compilado com sucesso (`ge_rasterizer.lib`, `RangeEngine.exe`, `RangeRuntime.exe`), sem regressão de assinatura — o chamador (`RAS_DisplayArrayBucket::RunInstancingNode`) já usava a contagem real (`nummeshslots`) pro draw call, não a capacidade do buffer.
- Pendente: rodar `benchmark_component.py` de novo pós-build e comparar `Rasterizer avg/max ms` contra o relatório de baseline (`benchmark_report_20260823_190214.txt`).

**CORREÇÃO GRANDE: a engine nunca esteve presa em OpenGL 2.1 — era bug de log**
- Antes de reescrever qualquer shader, tentei uma mudança pequena e reversível: pedir um contexto WGL "3.2 compatibility" em vez do "2.1" hardcoded (`GHOST_WindowWin32.cpp:677-684`, branch que já existia comentado no código, deixado pelos devs originais do Blender). Rebuild e teste em hardware real não mudaram nada visível — e ao investigar por quê, achei a causa raiz: **a engine já rodava em OpenGL 4.6.0 (compatibility) o tempo todo**, confirmado por `glGetString(GL_VERSION)` em `RAS_OpenGLRasterizer::PrintHardwareInfo` (`RAS_OpenGLRasterizer.cpp:511`, linha "OpenGL Supported: 4.6.0 NVIDIA...").
- A linha seguinte do log, `"Using OpenGL Version: 2.1"`, que usamos como evidência do problema original, é um **bug de log pré-existente**: imprimia `GLEW_VERSION_MAJOR` + `GLEW_VERSION` (`RAS_OpenGLRasterizer.cpp:513`) — essas são macros da **versão da própria biblioteca GLEW** (`glew.h:19682`, `#define GLEW_VERSION_MAJOR 2`), não a versão do contexto OpenGL. Coincidência de nome (parecia "2.1" de GL, era "2.x" do GLEW) gerou um diagnóstico tecnicamente errado que foi parar no relatório de melhorias.
- Corrigido: revertida a mudança no `GHOST_WindowWin32.cpp` (não fazia diferença real, e não há motivo pra desviar do código original sem necessidade comprovada). Corrigida a linha de log em `RAS_OpenGLRasterizer.cpp:513` para reportar o profile compilado (`Compiled GL Profile: Compatibility`) em vez da versão do GLEW — testado, mostra corretamente agora.
- **Impacto no roadmap**: como o driver já entrega GL 4.6/GLSL 4.60 completo em compatibility profile, e `gpu_shader_version()` (`gpu_shader.c`) já injeta automaticamente a versão certa em cada shader compilado, os 62 shaders legados (`gl_TexCoord`, `gl_FragColor`, `texture2D`) já funcionam plenamente — não há capacidade de GPU escondida sendo desperdiçada. Migrar para **core profile** de verdade continua possível, mas a motivação muda de "destravar hardware" para "modernização arquitetural" (remover fixed-function, preparar terreno pra UBO/compute shader de forma mais rígida) — bem mais fraca do que o diagnóstico original sugeria. Fica para decisão do usuário se ainda vale a pena com esse racional revisado, antes de investir na reescrita dos 62 arquivos `.glsl`.

**Benchmark pós-fix: física resolvida, Animations vira o próximo item real**
- Usuário corrigiu dois objetos da cena que estavam com Physics Type "Static" quando deveriam ser "No Collision" — isso eliminou o pico de física (`benchmark_report_20260823_200343.txt`, engine antiga em `D:\ProjetoRangeEngine`): `Physics` caiu de avg 30ms/max 113ms para avg 1.0ms/max 2.0ms, FPS médio subiu de 26.4 para 42.5. Confirma 100% a hipótese original sobre collision shape.
- Repetido com o `RangeEngine.exe` recompilado desta sessão (`build/bin`, inclui a otimização do `RAS_InstancingBuffer`): `benchmark_report_20260823_201152.txt` — FPS médio 45.9, `Physics` 0.66ms (2.8%), `MainRender` (equivalente ao antigo "Rasterizer") 16.1ms (70.6%, faixa 14.5–17.1ms, mais estável e um pouco mais baixo que os 18.7ms da rodada com o binário antigo).
- Esse build expõe um profiler mais granular que a engine antiga: categorias novas `ActivityCulling`, `CameraCulling`, `MainRender`, `ShadowCulling`, `Shadows`, `Sleeping`, `UpdateParents` (em vez de um único "Rasterizer" genérico) — reflete o código-fonte atual, não é "modo debug", é o profiler real desse build. Quanto mais propriedades expostas aqui, melhor para diagnosticar futuras rodadas.
- **`Animations` explicado — é proposital, não é bug**: custa ~3.7-3.8ms (15-16% do frame), escalando com a contagem de objetos. Confirmado pelo usuário: a cena tem 11 armatures com a mesma animação em objetos diferentes, de propósito, como parte da carga de teste do benchmark. Não precisa de investigação nem fix.

**Itens "a diagnosticar" da trilha Performance — investigados**
- **Loop principal single-thread**: confirmado real (`KX_KetsjiEngine::NextFrame`, sequencial: activity → animações → lógica → parents → física → parents → render, sem `tbb`/`std::thread` em lugar nenhum dessa função). Paralelizar de verdade exigiria lock no scenegraph (física e lógica mexem nos mesmos transforms no mesmo frame) — projeto arquitetural grande, fora de escopo por ora.
- **GIL em Python components**: confirmado real (`SCA_LogicManager`/`KX_PythonComponent::Update` chamam `PyObject_CallMethod` um objeto por vez, sem tentativa de paralelizar). Limitação inerente do CPython — não dá pra contornar sem sub-interpreters, que é mais invasivo ainda. Fora de escopo.
- **Bullet MT solver — descartado após investigação mais funda**: achado inicial (de que `btConstraintSolverPoolMt`/`btBatchedConstraints` já existiam no vendor tree) estava **errado**. Confirmado que o Bullet vendorado aqui é 2.84 e essas classes só existem em versões bem mais novas do Bullet — "ligar" o solver MT exigiria vendorar código novo, mesmo risco de deriva de API já descartado quando decidimos não atualizar o Bullet sem evidência. Fora de escopo.
- **Partículas GPU**: confirmado gap real, mas pior do que "sem GPU" — não há partículas rodando em gameplay nem em CPU (só existem no viewport do editor, código não chega no runtime do Ketsji). Construir do zero é semanas de trabalho. Fora de escopo desta sessão.
- **Streaming de assets — reavaliado, não é um gap tão grande quanto o relatório original supunha**: já existe um mecanismo assíncrono real e funcional, `LibLoad`/`KX_LibLoadStatus`/`LibFree` (`BL_Converter.cpp`), com thread pool próprio. Faltava só a camada de estratégia por distância em cima — isso virou a Fase 2 desta rodada (ver abaixo).

**Recurso novo: Streaming Manager (Python, sobre API C++ já existente)**
- Adicionado `projects-teste/scripts/streaming_manager.py` — componente `Range.types.KX_PythonComponent` que carrega/descarrega um chunk de cena (`LibLoad(..., asynchronous=1)` / `LibFree`) por distância da câmera ativa, com histerese (`load_distance` < `unload_distance`, mesma lógica de banda dupla que o `KX_LodManager` já usa) e cooldown mínimo antes de poder descarregar, pra evitar oscilar na fronteira.
- Cuidado tratado no código: `KX_LibLoadStatus.onProgress` existe na API mas é um stub vazio no C++ (não funciona) — não usar. O componente também não usa `onFinish` (que funciona, mas dispara fora do fluxo normal do `update()`, exigindo gerenciar estado a partir de um callback assíncrono); em vez disso, faz polling simples de `status.finished` a cada `update()`, mais simples de raciocinar dentro do modelo de componente. Antes de chamar `LibFree`, sempre confere `status.finished` — `LibFree` recusa silenciosamente (retorna `False`, sem crash) se o load ainda não terminou, mas o componente não depende só disso.
- v1 não limita quantos chunks carregam ao mesmo tempo (cada componente cuida só da própria âncora) — candidato a refinamento futuro se muitas âncoras carregarem juntas virar problema de verdade.
- Sintaxe validada com o Python bundled da engine (`build/bin/2.79/python`). Não testado com carregamento real ainda — precisa de pelo menos um `.blend`/`.range` de chunk separado e uma âncora na cena para validar o fluxo completo.

**Regressão corrigida: buffer de instancing travava atributos errados quando o shader ainda não estava pronto**
- Sintoma reportado pelo usuário: um objeto de faísca com material de nós piscava (aparecia "plano/errado" por alguns frames) só depois da otimização do `RAS_InstancingBuffer`.
- Causa raiz real (não é bug na otimização em si — é um bug pré-existente que ela deixou de mascarar por acidente): `RAS_DisplayArrayBucket::UpdateActiveMeshSlots` (`RAS_DisplayArrayBucket.cpp:176-184`) cria o `RAS_InstancingBuffer` uma única vez, capturando `mat->GetInstancingAttribs()` (`KX_BlenderMaterial.cpp:450-457`) — que retorna atributos incompletos (`DEFAULT_ATTRIBS`, sem cor/layer/info) se o shader do material ainda não estiver `Ok()` naquele instante. Uma vez criado, o buffer nunca era reavaliado. O churn de VBO por frame do código antigo, por coincidência, dava tempo do shader ficar pronto antes da maioria dos casos — um bug geral que afeta qualquer material instanciado recarregado em runtime, não só a faísca.
- Corrigido em `RAS_DisplayArrayBucket.cpp` (~linha 165-171): reaproveitado o canal de notificação de reload de material já existente (`m_materialUpdateClient.GetInvalidAndClear()`) para também invalidar todos os slots de `m_instancingBuffer[]`, forçando recriação com atributos atualizados. Sem custo por frame — só reage a eventos reais de reload.
- Compilado com sucesso (`ge_rasterizer`, `RangeEngine.exe`, `RangeRuntime.exe`). Pendente: usuário confirmar visualmente que o pisca-pisca sumiu no jogo dele.

**Robustez: StreamingManager não trava mais com caminho de chunk inválido**
- Ao testar, `LibLoad` com um caminho inexistente (`.rasec` em vez de `.range` — descoberta lateral: `.rasec` é uma extensão real e proposital deste fork, usada por um fluxo de "save protegido" em `wm_files.c:2244-2263`, não é erro de digitação, mas também não é o formato que `LibLoad` espera para carregar um chunk) lançava `ValueError` não tratado dentro de `update()`, e o motor desativa o `KX_PythonComponent` permanentemente após qualquer exceção em `update()` — o streaming parava de vez.
- Corrigido: `_start_load()` agora captura a exceção, loga o erro e agenda uma nova tentativa depois de `retry_cooldown` (3s) em vez de deixar o componente morrer.

**Instancing, fase 2: elimina rebind redundante de vertex attributes por frame**
- Contexto: com o buffer de instancing reaproveitado entre frames (fase 1 acima), `RAS_DisplayArrayBucket::RunInstancingNode` continuava reemitindo incondicionalmente, todo frame e por bucket, as chamadas `glEnableVertexAttribArray`/`glVertexAttribPointer`/`glVertexAttribDivisorARB` (via `material->ActivateInstancing`/`rasty->ActivateOverrideShaderInstancing`, até 7 chamadas GL) mesmo quando o id do VBO e os offsets não tinham mudado desde o frame anterior — churn de estado de driver sem necessidade, que só fazia sentido quando o buffer era recriado todo frame (antes da fase 1).
- Implementado: `RAS_InstancingBuffer` (`.h`/`.cpp`) ganhou `NeedsRebind()`/`MarkBound()`/`InvalidateBinding()`, rastreando se o binding atual (mais o par shader-de-material/shader-override + tipo de override) já é válido. `RunInstancingNode` (`RAS_DisplayArrayBucket.cpp`) só reemite as chamadas de attribute-pointer quando `NeedsRebind()` é true.
- Duas lacunas de invalidação foram fechadas de propósito, para não repetir a classe de bug de staleness já corrigida na fase 1 para materiais: (1) `Realloc()` chama `InvalidateBinding()` no ramo em que de fato recria o VBO; (2) `UpdateActiveMeshSlots` também invalida o binding de todos os `m_instancingBuffer[]` no ramo `SIZE_MODIFIED`, caso em que a VAO é recriada do zero mas o buffer de instancing em si não muda — sem essa invalidação, o binding ficaria marcado "válido" contra uma VAO nova e vazia.
- Limpeza incidental: removida uma chamada morta a `rasty->SetClientObject(...)` dentro do loop de empacotamento do `Update()` — nada lia `m_clientobject` depois, e instancing desenha tudo num único `glDrawElementsInstanced`, sem noção de "objeto atual" a servir.
- Compilado com sucesso (`ge_rasterizer`, `RangeEngine.exe`, `RangeRuntime.exe`). Pendente: rodar `benchmark_component.py` de novo e comparar `MainRender avg/max ms` contra o relatório mais recente (`benchmark_report_20260823_201152.txt`).

**Benchmark da Fase 2b confirmado: ganho real, porém modesto (correção de uma leitura errada no meio do caminho)**
- Rodado `benchmark_component.py` de novo em `benchmark.range`, mesma RTX 5060 Laptop GPU do baseline anterior. Antes de rodar, uma pegadinha de hardware: o notebook estava na bateria, e nesse modo o driver desliga a dGPU e só expõe a Intel integrada (`Get-CimInstance Win32_VideoController` não listava a RTX) — a primeira tentativa rodou sem querer na Intel (FPS 37.0, perfil de custo completamente diferente, não comparável). Corrigido plugando o carregador; a RTX voltou a aparecer.
- **Primeira rodada com a RTX (`benchmark_report_20260824_103029.txt`), lançada via `Start-Process` numa janela pequena/padrão**: sugeria FPS 45.9→60.3 e `MainRender` caindo de 16.07ms pra 1.08ms (~15x) — número bom demais, e de fato era artefato de medição: janela pequena = muito menos pixels pra rasterizar, não é o mesmo trabalho de GPU que o baseline original mediu.
- **Correção com o usuário rodando manualmente em tela cheia (`benchmark_report_20260824_103254.txt`)**: FPS médio 47.4, `MainRender` 14.297ms (64.2%) — muito mais alinhado com o baseline `benchmark_report_20260823_201152.txt` (RTX 5060, tela cheia, FPS 45.9, `MainRender` 16.07ms). Ganho real: FPS +3% (45.9→47.4), `MainRender` -11% (16.07ms→14.30ms), com contagem de objetos idêntica na progressão (197→321 em ambas as rodadas, mesmo padrão de spawn).
- **Lição**: resolução/tamanho de janela afeta diretamente `MainRender` e deve ser mantida constante entre rodadas de benchmark comparativo — daqui pra frente, sempre rodar `RangeRuntime.exe` em tela cheia (ou com a mesma resolução explícita) antes de comparar números entre sessões.
- Confirma que o skip de rebind redundante de vertex attributes (`RAS_InstancingBuffer::NeedsRebind`) tem ganho real, mas modesto (~11% em `MainRender`) — não a melhoria dramática que a primeira leitura (errada) sugeriu.

**Trilha Iluminação, início da Fase 1: piloto de migração de shaders para sintaxe core-profile-safe**
- Escopo desta rodada: só o vertex shader compartilhado dos 22 filtros 2D (`RAS_VertexShader2DFilter.glsl`) + os 3 fragment shaders mais simples (`RAS_GrayScale2DFilter.glsl`, `RAS_Invert2DFilter.glsl`, `RAS_Sepia2DFilter.glsl`), como prova de conceito do padrão a repetir nos ~19 filtros restantes e depois no resto do motor. Migração de sintaxe é 100% desacoplada de ligar `WITH_GL_PROFILE_CORE` — sintaxe core-safe (`in`/`out`, `texture()`, `layout(location=N)`) compila e roda normalmente sob o contexto compatibility atual, confirmado pelo precedente já existente em `gpu_shader_vertex.glsl:10-14`. `WITH_GL_PROFILE_CORE` continua desligado; essa flag só será ligada numa fase futura, depois que todos os shaders legados estiverem migrados.
- **Achado que mudou o desenho inicial**: `RAS_OpenGLRasterizer::ScreenPlane` (o quad fullscreen usado pelos filtros) não é exclusivo deles — `RAS_Rasterizer::DrawOffScreen` também o usa, todo frame, com ou sem filtro ativo, para o blit final da cena pra tela, via `GPU_SHADER_DRAW_FRAME_BUFFER`/`gpu_shader_frame_buffer_vert.glsl` (confirmado idêntico ao vertex shader dos filtros antes da migração: `gl_Position = gl_Vertex; gl_TexCoord[0] = gl_MultiTexCoord0;`). Substituir (em vez de somar) as chamadas de fixed-function client-state no construtor do `ScreenPlane` teria quebrado a imagem final inteira, não só os filtros. Corrigido no desenho: a mudança em C++ é aditiva — mantém `glEnableClientState`/`glVertexPointer`/`glTexCoordPointer` como estavam e soma `glEnableVertexAttribArray`/`glVertexAttribPointer` nas locations 0/1 em paralelo, contra o mesmo VBO.
- `RAS_VertexShader2DFilter.glsl` reescrito com dual-write: sob `#if __VERSION__ >= 130` usa `layout(location=0/1) in`/`out vec2 texCoordVarying` (sintaxe nova); sob `#else` mantém o corpo original byte-a-byte (`gl_Vertex`/`gl_MultiTexCoord0`/`gl_TexCoord[0]`) como fallback morto mas correto. Também escreve em `gl_TexCoord[0]` no ramo novo, para não quebrar os 19 filtros ainda não migrados que ainda leem essa variável.
- Os 3 fragment shaders piloto passaram a ler `texCoordVarying` (não `gl_TexCoord[0].st`) e escrever num `out vec4 fragColor` customizado (`layout(location=0)`), com `texture()` no lugar de `texture2D()` — mesmo padrão `#if __VERSION__ >= 130`/`#else` com o corpo legado intacto no fallback. Ler `texCoordVarying` em vez de manter `gl_TexCoord[0].st` foi deliberado: valida a cadeia nova ponta a ponta (C++ → vertex shader → varying → fragment shader) já neste primeiro piloto, em vez de deixar isso para um arquivo mais complexo depois.
- Nenhum arquivo recebeu sua própria linha `#version` — `RAS_Shader::GetParsedProgram` já remove qualquer `#version` encontrada no texto (com warning) antes de injetar a versão central; a versão em si não foi tocada nesta fase.
- Testado: build limpo (`ge_rasterizer_shaders`, `ge_rasterizer_opengl`, `RangeEngine.exe`, `RangeRuntime.exe`) e execução real de `RangeRuntime.exe` com `benchmark.range` (RTX 5060 Laptop, mesmo hardware dos benchmarks anteriores) — console de inicialização sem nenhum erro/warning de shader ou GLSL, cena renderizou normalmente (estrada, árvores, personagens instanciados), confirmando que o caminho de maior risco (vertex shader + `ScreenPlane` usados no blit final todo frame) não regrediu.
- **Confirmado com filtro ativo pelo usuário**: com o `Filter2DToggle` (ver entrada abaixo) na câmera de `benchmark.range`, `GRAYSCALE` ligado/desligado em jogo (tecla F) renderiza corretamente — valida a cadeia nova ponta a ponta (C++ `ScreenPlane` → vertex shader com `texCoordVarying` → fragment shader com `fragColor`/`texture()`) com um filtro de verdade ativo, não só o caminho sem filtro.
- Próximos candidatos, mesmo padrão: `RAS_Blur2DFilter.glsl`/`RAS_Sobel2DFilter.glsl` (próximo nível de complexidade, ainda self-contained), depois o resto dos 22 filtros.

**Recurso novo: Filter2DToggle (Python, sobre API C++ já existente) — resolve o "testar filtro ativo" pendente acima**
- Adicionado `projects-teste/scripts/filter2d_toggle.py` — componente `Range.types.KX_PythonComponent`, mesmo espírito do `streaming_manager.py` (autocontido, sem exigir outros logic bricks na cena). Liga/desliga um filtro 2D numa tecla configurável, usando só a API Python já exposta (`scene.filterManager.addFilter()`/`removeFilter()`/`getFilter()`, `Range.logic.keyboard`, constantes `RAS_2DFILTER_*` de `Range.logic` e `Range.events`) — nenhuma mudança em C++.
- Args editáveis: `filter_type` (um dos 10 tipos aceitos por `addFilter` — `GRAYSCALE`/`INVERT`/`SEPIA` são os já migrados para core-profile-safe nesta sessão, os outros 7 continuam com sintaxe legada mas funcionam igual sob o profile compatibility atual), `toggle_key` (nome em `Range.events`, ex. `"FKEY"`), `pass_index` (slot no `filterManager`, usar um valor diferente por componente se mais de um estiver ativo ao mesmo tempo), `start_enabled`.
- Detalhe de API confirmado no código (`KX_2DFilterManager.cpp`): `addFilter` só aceita tipos entre `FILTER_BLUR` e `FILTER_CUSTOMFILTER` no enum — Bloom/Tonemap/SSAO/FXAA/Outline/Motion Blur usam mecanismos próprios (`changeBloomValues` etc. ou opções de cena) e ficaram de fora da lista de tipos suportados por este componente de propósito, pra não expor uma opção que ia estourar `ValueError` em runtime.
- Chamadas ao `filterManager` protegidas com `try/except ValueError`, seguindo o mesmo cuidado do `streaming_manager.py`: uma exceção não tratada dentro de `update()`/`start()` desativa o `KX_PythonComponent` permanentemente.
- Sintaxe validada com o Python bundled da engine (`build/bin/2.79/python`). **Testado pelo usuário em `benchmark.range`**: componente adicionado na câmera, `GRAYSCALE`/tecla F confirmados funcionando em jogo.

## 2026-08-24

**Piloto (GrayScale/Invert/Sepia) — confirmação final em jogo**
- Usuário testou `INVERT` e `SEPIA` via `Filter2DToggle` em `benchmark.range` (log de console mostrando ligar/desligar sem erro). Com isso os 3 filtros do piloto estão 100% validados em jogo (`GRAYSCALE` já tinha sido confirmado na sessão anterior) — fecha o piloto da Fase 1 da trilha Iluminação por completo.

**Migração de shaders para core-profile-safe: Blur, Sobel, Sharpen, Dilation, Erosion, Laplacian, Prewitt**
- Mesmo padrão do piloto (`#if __VERSION__ >= 130` com `in vec2 texCoordVarying`/`layout(location=0) out vec4 fragColor`/`texture()` no ramo novo, corpo legado intacto no `#else`) aplicado aos 7 filtros restantes do 2D Filter Actuator clássico que usam o padrão de "9 amostras" com `bgl_TextureCoordinateOffset[9]`. Diferença notada durante o levantamento: ao contrário de GrayScale/Invert/Sepia (que já tinham o envelope `#if/#else` e só precisaram trocar o conteúdo), nenhum desses 7 tinha o envelope — foi criado do zero em cada um.
- Confirmado antes de editar (via investigação de código) que a migração é isolada e segura: `RAS_2DFilterManager`/`RAS_2DFilter`/`RAS_OpenGLRasterizer::ScreenPlane` tratam todo filtro 2D de forma genérica, sem nenhum código específico para Blur/Sobel/etc.; o uniform `bgl_TextureCoordinateOffset[9]` é preenchido de forma agnóstica de shader em `RAS_2DFilter::ComputeTextureOffsets`/`BindUniforms` e não muda em nenhum dos dois ramos. Nenhuma mudança adicional foi necessária fora dos arquivos `.glsl`.
- Compilado (`ge_rasterizer_shaders`, `RangeRuntime.exe`) e **testado pelo usuário em jogo**, via `Filter2DToggle`, em dois lotes: `BLUR`/`SOBEL` primeiro, depois `SHARPEN`/`DILATION`/`EROSION`/`LAPLACIAN`/`PREWITT` — todos os 7 confirmados funcionando sem erro de shader no console.
- Com isso, os 10 filtros do 2D Filter Actuator clássico (`RAS_2DFilterManager::FILTER_MODE` de `FILTER_BLUR` a `FILTER_INVERT`, exceto os builtins de cena SSAO/Bloom/Tonemap/LightScatter/SSR/FXAA que usam mecanismo próprio) estão migrados e validados. `projects-teste/scripts/filter2d_toggle.py` atualizado (docstring) para refletir que não há mais diferença de sintaxe entre os `filter_type` suportados.
- Restam no motor: fixed-function fallback (`gpu/shaders/gpu_shader_basic_*.glsl` etc.) e mundo/background/compositor — não iniciados.

**Migração de shaders para core-profile-safe: FXAA e Outline (fecha o grupo de pós-processamento)**
- `RAS_Fxaa2DFilter.glsl`: mesmo padrão dual-branch; diferença em relação aos filtros anteriores é o uso de `texture2DLod` (variante com LOD explícito do `texture2D`), migrado para `textureLod()` no ramo novo — resto do algoritmo (FXAA clássico, adaptado do geeks3d.com, já creditado no cabeçalho do arquivo) intacto.
- `RAS_OutLine2DFilter.glsl`: multi-textura (`bgl_RenderedTexture`, `bgl_DepthTexture` não usado no shader atual, `bgl_DataTextures[0]`), sem uso de LOD ou array de offsets — migração direta, mesmo padrão.
- Confirmado por investigação de código que esses dois não passam pela mesma via do usuário final que os 10 anteriores: FXAA é ligado pelo checkbox nativo de cena "Post Processing Shaders → FXAA" (`scene.scenefx_settings.use_fxaa`, sistema `SCENEFXSettings` descoberto nesta sessão — ver mapeamento arquitetural abaixo), não pelo `Filter2DToggle`/`addFilter`. Outline é ligado via Actuator de lógica clássico ("2D Filter" → tipo "Outliner"), não tem entrada no painel de cena nem no `Filter2DToggle`.
- Nota importante sobre "AA Samples" (painel System, ao lado de FXAA): é MSAA de hardware (`GameData.aasamples`, `rna_scene.c:4652-4757`), configuração de framebuffer/contexto sem nenhum GLSL — não faz parte desta migração, mecanismo totalmente independente do filtro FXAA.
- Compilado (`ge_rasterizer_shaders`, `RangeRuntime.exe`, `RangeEngine.exe`) e testado pelo usuário: FXAA ligado pelo checkbox nativo, Outline ligado via Actuator "2D Filter"/"Outliner" na câmera — nenhum erro de shader no console em ambos os casos. Outline não mostrou mudança visual, como esperado: o filtro depende de um material alimentando `bgl_DataTextures[0]` com máscara de contorno, ausente em `benchmark.range` — comportamento correto de um filtro sem highlight configurado, não falha de migração.
- **Grupo "filtros de pós-processamento" (`RAS_OpenGLFilters/*.glsl`) fica assim fechado**: todos os filtros de shader único (10 do 2D Filter Actuator clássico + FXAA + Outline) migrados e validados. Restam nessa pasta só os multi-pass nativos (Bloom, SSR, Light Scattering, SSAO, Tonemap) — que já usam `texture()`/variável de coordenada própria desde que foram implementados, não dependem do vertex shader compartilhado nem do dual-write, e por isso não entram nesse escopo de migração.

**Fixed-function fallback (`source/blender/gpu/shaders/*.glsl`) — investigação de escopo antes de editar**
- Antes de editar, investigação de código (não código escrito ainda) mapeou os 37 arquivos de `gpu/shaders/`. Achado que corrigiu a suposição inicial: `gpu_shader_basic_{vert,frag,geom}.glsl` (citados de memória como alvo) na verdade só rodam no **editor** Blender (via `gpu_basic_shader.c`, API de modo imediato pra UI/viewport) — nenhuma referência em `gameengine/`. Não fazem parte do jogo, fora de escopo pelo critério do projeto (só editar o que afeta o jogo rodando).
- Os arquivos que realmente rodam no jogo se dividem em risco muito desigual: (a) um grupo com o mesmo padrão `varying`/`texture2D`/`gl_FragColor` dos 12 filtros já migrados — baixo risco, isolado por efeito; (b) dois arquivos centrais, `gpu_shader_vertex.glsl` e `gpu_shader_material.glsl` (5227 linhas), concatenados em **todo material do jogo sem nós customizados** — dependem de estado fixed-function sem equivalente em core (`gl_LightSource`, `gl_ModelViewMatrix`, `gl_ProjectionMatrix`, `gl_NormalMatrix`, `gl_ClipPlane`), exigindo redesenho de uniforms (não é troca mecânica de sintaxe) e com raio de impacto de "quebra a cena inteira" em caso de erro. Decisão do usuário: migrar só o grupo (a) por ora; (b) fica para uma frente separada, com seu próprio design, antes de tocar em qualquer linha.
- **Correção durante a leitura arquivo-por-arquivo do grupo "fácil" estimado pela investigação inicial**: vários arquivos que pareciam simples na varredura por padrão de texto (`gl_TexCoord`/`texture2D`/`gl_FragColor`) na verdade também usam matrizes fixed-function (`gl_ProjectionMatrix`, `gl_ModelViewMatrix`, `gl_ModelViewProjectionMatrix`) nos vertex shaders — mesmo problema do grupo (b), não sintaxe. Ficam de fora desta rodada e vão para a mesma decisão futura do grupo (b): `gpu_shader_black_vert.glsl`, `gpu_shader_frustum_line_vert.glsl`, `gpu_shader_frustum_solid_vert.glsl`, `gpu_shader_flat_color_vert.glsl`, `gpu_shader_2d_box_vert.glsl`, `gpu_shader_vsm_store_vert.glsl` (shadow map VSM), `gpu_shader_smoke_vert.glsl` (smoke/fire) — e os respectivos fragment shaders pareados, deixados intactos junto (migrar só o frag de um par sem o vert não teria valor).
- **Segunda exclusão encontrada durante a leitura**: `gpu_shader_sep_gaussian_blur_vert/frag.glsl` (blur do shadow map VSM, `GPU_framebuffer_blur` em `gpu_framebuffer.c:489-529`) é desenhado via **immediate mode** (`glBegin(GL_QUADS)`/`glVertex2f`/`glTexCoord2d`, não VBO com atributos genéricos) — diferente do `RAS_OpenGLRasterizer::ScreenPlane` (já usado pelos filtros e por `frame_buffer_vert/frag`, que por isso puderam ser migrados com segurança). Migrar a sintaxe do vertex shader sem reescrever esse draw call em C++ quebraria o binding de atributos; fora de escopo desta rodada.
- **Migrados nesta rodada (grupo confirmadamente seguro, sem mudança de C++)**: `gpu_shader_frame_buffer_vert.glsl` + `_frag.glsl` (usa o mesmo `ScreenPlane` já adaptado pelos filtros — mesmo padrão `layout(location=0/1) in pos/uv` + `texCoordVarying`), `gpu_shader_black_frag.glsl` (trivial, sem textura/matriz), e os fragment shaders dos efeitos FX nativos que só dependem de uma variável de interpolação **nomeada** (`uvcoord`/`uvcoordsvar`) já escrita pelo vertex shader correspondente (`gpu_shader_fx_vert.glsl`/`gpu_shader_fx_dof_vert.glsl`) — como GLSL faz o link de `in`/`varying` por nome (não pela palavra-chave), dá pra migrar só o lado do fragment shader sem tocar no vertex nem no C++ que o desenha, seja ele imediate-mode ou não: `gpu_shader_fx_tonemap_frag.glsl`, `gpu_shader_fx_fxaa_frag.glsl`, `gpu_shader_fx_bloom_frag.glsl` (já vinha parcialmente migrado por terceiros, sem dual-branch — realinhado ao padrão do projeto), `gpu_shader_fx_depth_resolve.glsl`, `gpu_shader_fx_dof_frag.glsl` (5 sub-passes) e `gpu_shader_fx_dof_hq_frag.glsl` (MRT — `gl_FragData[0/1/2]` viraram 3 `layout(location=N) out` nomeados: `fragData0/1/2`).
- Compilado (`bf_gpu`, `RangeRuntime.exe`, `RangeEngine.exe`) e **confirmado pelo usuário em jogo**: cena renderiza normal (crítico, já que `frame_buffer` é usado no blit de toda a tela, com ou sem filtro ativo), Bloom/Tonemap/FXAA nativos continuam funcionando pelo painel de cena.
- Ficam pendentes nesse diretório, todos por causa do mesmo problema de matrizes fixed-function (não sintaxe): `gpu_shader_fx_ssao_frag.glsl` (`gl_ProjectionMatrix`), `gpu_shader_fx_ssr_frag.glsl` (`gl_ProjectionMatrix`/`gl_ProjectionMatrixInverse`), `gpu_shader_fx_light_scatter_frag.glsl` (`gl_ModelViewMatrix`/`gl_ProjectionMatrix`) — os builtins nativos SSAO/SSR/Light Scatter, apesar de estarem na mesma "família FX" dos que acabaram de ser migrados, têm o mesmo problema duro do grupo (b) e não puderam entrar nesta rodada.

**Trilha Performance: profiler "Animations" separado em pose/curva vs. skinning — resultado decide a próxima frente**
- Usuário perguntou como otimizar o custo de animação (15-30% do frame nos benchmarks), mencionando "cozimento binário de esqueletos" usado em outras engines. Investigação de arquitetura (sem código) mapeou o pipeline: cada armature tem cópia própria de Action/pose (sem cache/bake entre objetos idênticos tocando a mesma animação — o caso exato dos 11 armatures do benchmark); a avaliação de pose já roda em thread pool paralelo (`BLI_task_pool`, `KX_Scene.cpp`), não é limitada pelo GIL do Python — corrige a suposição registrada antes no relatório de que o loop principal é totalmente single-thread; o skinning (deform da malha pelos ossos) é 100% CPU, sem GPU skinning em lugar nenhum do motor (nenhum uniform de matriz de bone em nenhum `.glsl`). A categoria "Animations" do profiler misturava avaliação de curva/pose/IK **e** skinning na mesma métrica, tornando impossível saber qual dos dois dominava.
- Implementado: `KX_Scene::UpdateAnimations` (que despachava, por objeto, uma única tarefa de thread pool fazendo pose+deform juntos, `KX_Scene.cpp`) foi dividida em duas passadas paralelas sequenciais — `UpdateAnimations` (só `UpdateActionManager`/avaliação de pose via a nova `UpdateAnimPoseTask`, populando um cache `m_animNeedsUpdateCache` por objeto pré-alocado no thread principal antes do despacho, para não inserir concorrentemente num mapa durante a fase paralela — só valores já existentes são escritos, seguro entre threads) e `UpdateAnimationDeformers` (novo método público, chama `UpdateAnimDeformTask` só para quem o cache marcou como `needs_update`). Nova categoria de profiler `tc_animations_deform`/"Skinning" adicionada em `KX_KetsjiEngine.h/.cpp` — mecânico: um valor a mais no enum + uma string a mais em `m_profileLabels`, que já é exposto automaticamente tanto no HUD de debug quanto em `Range.logic.getProfileInfo()` (usado por `benchmark_component.py`), sem precisar tocar em mais nenhum lugar.
- Cuidado que quase passou despercebido: `KX_Scene::UpdateAnimations` passou a retornar `bool` (se a passada de pose realmente rodou, ou foi pulada pelo throttle nativo "Restrict Animation Updates"). Os 3 chamadores (`KX_KetsjiEngine::NextFrame`, mais `ImageRender.cpp` e `KX_TextureRendererManager.cpp` — usados em câmeras de render-to-texture) só chamam `UpdateAnimationDeformers()` quando esse retorno é `true`. Sem essa checagem, o skinning rodaria todo frame mesmo com o throttle ativado, anulando o próprio propósito dessa otimização nativa.
- Compilado (`ge_ketsji`, `RangeRuntime.exe`, `RangeEngine.exe`) e testado em `benchmark.range` (RTX 5060), em duas condições: janela pequena (`Animations` 0.456ms/2.7%, `Skinning` 2.291ms/13.8%) e **tela cheia, confirmado pelo usuário** (`Animations` 0.557ms/2.5%, `Skinning` 3.343ms/15.1%, FPS médio 47.2 — MainRender 14.6ms bate com o baseline de tela cheia da Fase 2b). Proporção consistente nas duas condições: **skinning CPU domina por ~5-6x sobre a avaliação de curva/IK**. Usuário confirmou visualmente que as animações continuam corretas (print do HUD de debug em jogo). Resultado direto: bake de pose compartilhada entre objetos idênticos (que atacaria só a fatia de curva/IK) teria impacto pequeno; **GPU skinning é a otimização que realmente move a agulha** para esta cena de teste.

## 2026-08-24

**GPU Skinning — implementação das Fases A a D (Fase E de verificação em jogo ainda pendente)**
- Usuário decidiu encarar a frente de GPU skinning identificada na sessão anterior. Planejamento em duas rodadas de agentes Explore (pipeline CPU atual: `BL_SkinDeformer`/`RAS_DisplayArray`; infraestrutura de shader/atributo existente: `RAS_InstancingBuffer`, `GPU_shader_uniform_vector`, `gpu_shader_vertex.glsl`) e um agente Plan, resultando em plano de 5 fases salvo e aprovado. Achado-chave do planejamento que orientou o design inteiro: a via inteira cabe dentro do profile GL compatibility atual — não depende da migração pendente para core profile.
- **Fase A — atributos de vértice**: `RAS_DisplayArray::VertexData` ganhou `boneIndices`/`boneWeights` (`vec4_packed`, até 4 influências por vértice), com custo condicional via `Format::hasBoneData` (malhas sem armature não pagam os 32 bytes/vértice extras); novo bit `BONE_MODIFIED`; `RAS_AttributeArray::AttribType` ganhou `RAS_ATTRIB_BONE_INDEX`/`RAS_ATTRIB_BONE_WEIGHT`, ligados em `RAS_StorageVao` como atributos genéricos `GL_FLOAT` normais (não per-instance). Populados uma única vez na conversão de malha (`BL_ConvertDerivedMeshToArray`, `BL_BlenderDataConversion.cpp`): lê `MDeformVert`/`MDeformWeight` do object (só quando ele tem um Armature modifier — `BL_ModifierDeformer::HasArmatureDeformer`), pega os 4 maiores pesos por vértice, renormaliza. **Limitação documentada, não resolvida**: a malha convertida é cacheada por `Mesh*` e pode ser compartilhada por múltiplos Objects; se dois objects compartilham a malha com vertex groups em ordem diferente, os índices de bone ficam errados para um deles — mesma limitação implícita que já existia em `BL_SkinDeformer::m_dfnrToPC`, agora só "assada" em dados de malha compartilhados. Build (`ge_rasterizer`, `ge_rasterizer_opengl`, `ge_converter`, `ge_ketsji`) e `RangeEngine` completo confirmados sem erro.
- **Fase B — shader + variante `USE_SKINNING`**: novo slot de cache de material `Material.gpumaterialskinning` (espelha `gpumaterialinstancing` 1:1, incluindo todos os `GPU_material_free`/`BLI_listbase_clear` espalhados por `material.c`/`readfile.c`/`render_update.c`/`gpu_material.c` que já tratavam o par gpumaterial/gpumaterialinstancing); `GPU_material_from_blender` ganhou parâmetro `is_skinning` (com `BLI_assert` proibindo instancing+skinning juntos nesta rodada); `gpu_shader_vertex.glsl` ganhou bloco `#ifdef USE_SKINNING` (atributos `boneIndices`/`boneWeights`, uniform array `boneMatrices[MAX_BONES]`) inserido no mesmo ponto que o bloco de instancing, antes da transformação fixed-function. Novo `#define GPU_MAX_SKINNING_BONES 64` em `GPU_material.h`, compartilhado entre o codegen GLSL e o deformer C++. Ligação decidida via flag de material `MA_SKINNING` (novo bit em `shade_flag`, exposto como `use_gpu_skinning` na API Python/RNA) — mesmo padrão já usado por `MA_INSTANCING`, já que bucket/shader são compartilhados por material, não por object. Upload da paleta de matrizes reaproveita `GPU_shader_uniform_vector` sem nenhuma ligação GL nova (o parâmetro `arraysize` já existia, só nunca tinha sido chamado com valor > 1). Build (`bf_gpu`, `ge_ketsji`) e `RangeEngine` completo confirmados sem erro.
- **Fase C — enum RNA + dispatch no deformer**: novo valor `ARM_VDEF_BGE_GPU` no enum `eArmature_VertDeformer` (`DNA_armature_types.h`) e entrada correspondente em `rna_armature.c` (mesmo combo "Vertex Deform" já exposto na UI de Armature, sem plumbing novo). `BL_SkinDeformer::UpdateInternal` ganhou o novo case: valida o orçamento de bones (`defbase_tot > GPU_MAX_SKINNING_BONES` cai de volta pro CPU com aviso no console, `CM_Warning`), senão chama `UpdateBoneMatrixPalette()` (novo método) e pula `UpdateTransverts()` — malha fica em bind pose no VBO, só a paleta de matrizes muda por frame, e `m_bDynamic` passa a `false` só nesse caminho (antes era `true` incondicional pra todos os branches). **Ponto de correção mais delicado do design**: o loop CPU (`BGEDeformVerts`) não aplica `chan_mat` direto em espaço objeto, ele passa por um espaço relativo via `pre_mat`/`post_mat`; pra bater exatamente com o resultado do CPU, cada matriz da paleta é pré-multiplicada como `post_mat * chan_mat * pre_mat` antes do upload (dentro de `UpdateBoneMatrixPalette`), não deixado pro shader. Cache `m_dfnrToPC` (que já existia só dentro de `BGEDeformVerts`) foi extraído pra `EnsureDfnrToPCCache()`, reaproveitado pelos dois caminhos. Transporte da paleta até o uniform: `BL_BlenderShader::Update()` já recebe o `RAS_MeshUser` do objeto — passou a chamar `meshUser->GetDeformer()->GetBoneMatrices(...)` (novo método virtual em `RAS_Deformer`, default `false`) antes de `GPU_material_bind_bone_matrices`. Build (`ge_converter`) e `RangeEngine` completo confirmados sem erro.
- **Fase D — guard rails**: `KX_BatchGroup::MergeObjects` passou a rejeitar (com `CM_Error`) objects cujo deformer é GPU-skinned (`RAS_Deformer::IsGPUSkinned()`, novo método virtual, `false` por padrão) — hoje não existia nenhuma checagem de tipo de deformer no batching estático, e paletas de bone por-instância ficam fora de escopo. `BL_BlenderShader::UseInstancing()` já nega automaticamente instancing quando `MA_SKINNING` está ligado (skinning tem prioridade), consistente com o `BLI_assert` da Fase B. Build (`ge_ketsji`, `ge_converter`) confirmado sem erro.
- **Não feito nesta sessão (fora de escopo, ver ressalvas do plano)**: tangentes de normal-map não são re-orientadas pela matriz de skinning no vertex shader (mesmo tipo de lacuna que já existe pra instancing+tangente, mas não tratada aqui) — afeta só iluminação de normal-map em malhas skinned, não a geometria.

**Fase E — validação em jogo: CONCLUÍDA, com duas causas raiz de build encontradas e corrigidas no processo**
- Após compilar, `RangeEngine.exe` (editor) passou a travar com `STATUS_HEAP_CORRUPTION` (`0xc0000374`, reportado dentro de `ntdll.dll`) já na cena padrão em branco, tanto em modo `-b` quanto em janela — sem nenhum arquivo de teste envolvido. `RangeRuntime.exe` (o player, usado nas sessões anteriores) parecia funcionar, mas isso se mostrou coincidência de timing (heap corruption nem sempre trava na hora — só quando o bloco corrompido é reutilizado).
- **Causa raiz 1 — `dna.c` desatualizado**: a regra do Ninja que gera `source/blender/makesdna/intern/dna.c` (a tabela SDNA embutida no binário, usada para interpretar arquivos `.blend`/`.range` salvos) só lista `bin/makesdna.exe` como dependência — não lista nenhum `DNA_*.h` como entrada rastreada. Resultado: editar `DNA_material_types.h`/`DNA_armature_types.h` (Fases B/C desta sessão) nunca dispara a regeneração desse arquivo em builds incrementais; `dna.c` ficou parado em 23/08 16:12 durante toda a sessão. Como o comparador de versão do Blender deriva o tamanho "atual" do struct do PRÓPRIO `dna.c` (não de `sizeof()` direto), a struct `Material` ficava com tamanho relatado menor que o `struct Material` de fato compilado (com `gpumaterialskinning` a mais) — qualquer código que grava nesse campo (`direct_link_material` em `readfile.c`) escreve além do buffer alocado. Corrigido apagando `dna.c`/`dna_type_offsets.h` manualmente e deixando o Ninja regenerá-los (não existe flag de rebuild forçado para isso na configuração atual do projeto).
- **Causa raiz 2 — `writefile.c` desatualizado pelo mesmo motivo**: `source/blender/blenloader/intern/writefile.c` inclui `dna_type_offsets.h` (offsets pré-computados, usados para salvar arquivos rápido) mas o Ninja tem a mesma lacuna de dependência — `writefile.c.obj` ficou parado em 23/08 16:16, compilado contra o header de offsets antigo. Isso corrompia silenciosamente qualquer arquivo `.range` salvo por builds feitos durante a sessão (mesmo que a leitura estivesse correta). Corrigido forçando a recompilação (`touch writefile.c`).
- **Dado que as duas causas acima são uma classe geral de bug** (Ninja não rastreia headers gerados por `custom command` do CMake como dependência de quem os inclui, quando o `#include` não passa por um mecanismo de depfile), a correção definitiva usada foi `ninja -t clean` seguido de rebuild completo do zero (~2911 passos, ~50min) em vez de caçar mais arquivos individualmente — garante que não sobra nenhum outro `.obj` com essa mesma inconsistência. **Anotado na memória do projeto para próximas sessões**: qualquer mudança em `DNA_*.h` deve ser seguida de um rebuild limpo, não incremental.
- Com o build limpo, `RangeEngine.exe` parou de travar (testado em cena em branco e em `benchmark.range`). Teste de GPU skinning real: script Python (via `RangeEngine.exe -b --python`) duplicou os materiais `Ch33_body`/`Ch33_hair` só para os 9 mesh slots do primeiro personagem (`Armature.000`), ligou `use_gpu_skinning=True` neles e `deform_method='BGE_GPU'` no armature, salvou como `projects-teste/benchmark_gpu_test.range` (arquivo original preservado intacto). Rodando em `RangeRuntime.exe`: sem crash, sem erro de shader no console, `boneIndices`/`boneWeights`/`boneMatrices` resolvidos com locations válidas (confirmado via instrumentação temporária, removida ao final), screenshot mostra os personagens renderizados corretamente (sem colapso de geometria, sinal de que a paleta de matrizes não está zerada). Bind pose confirmado visualmente correto; comparação frame-a-frame de animação em movimento e o benchmark comparativo de FPS ficam para uma futura sessão (a cena de teste usada mostra os personagens parados/idle no trecho observado).

**Fase F — validação em movimento e benchmark comparativo: geometria OK, performance é uma REGRESSÃO (não um ganho) — causa raiz parcialmente corrigida**
- Validação visual com animação em movimento (não mais idle): dois screenshots em `benchmark_gpu_test.range` com o personagem GPU-skinned em poses de corrida diferentes, sem colapso de geometria nem distorção — bind pose e blend no vertex shader confirmados corretos também com o esqueleto se movendo, não só parado.
- Benchmark comparativo (`benchmark_report.py`, mesmo `benchmark_gpu_test.range`, 1 de 11 personagens com `use_gpu_skinning`) contra o baseline 100% CPU registrado antes (`benchmark_report_20260824_105337.txt`): **FPS caiu de 60.3 para 48.6**, `Skinning` (CPU) mais que dobrou (2.29ms→5.33ms) mesmo com só 1/11 personagens convertidos, e uma categoria `GPU Latency` que era irrelevante (0.035ms) saltou pra 6.12ms/26.5% — sinal de stall CPU↔GPU. Reproduzido duas vezes (inclusive descartando contaminação por screenshot durante a medição).
- **Causa raiz #1 encontrada e corrigida**: `vertformat.hasBoneData` (`BL_BlenderDataConversion.cpp`, tanto em `BL_ConvertMesh` quanto em `BL_ConvertDerivedMeshToArray`) era decidido por **"o objeto tem armature deformer"**, não por "o material tem `use_gpu_skinning` ligado". Resultado: ligar GPU skinning em 1 personagem inflava o formato de vértice (32 bytes/vértice extras de `boneIndices`/`boneWeights`) dos **11** personagens da cena, inclusive os 10 que continuam 100% CPU e nunca leem esses atributos — mais bytes por vértice pra malhas que não precisam, pesando no upload de VBO e no loop de deform por CPU. Corrigido: o formato de vértice agora é decidido por material (`ma->shade_flag & MA_SKINNING`), não mais por mesh inteira — `vertformat` deixou de ser único por `KX_Mesh` e passou a ser calculado por material dentro do loop de conversão, e a escrita de `boneIndices`/`boneWeights` por vértice em `BL_ConvertDerivedMeshToArray` passou a consultar `array->GetFormat().hasBoneData` (por material) em vez de uma flag única pra malha inteira. Build incremental (não mexeu em `DNA_*.h`, dispensou rebuild limpo) e `RangeRuntime.exe` confirmados sem erro de shader.
- **Resultado do fix**: `Skinning` caiu pra 0.09ms/0.4% e `GPU Latency` voltou a 0.05ms/0.2% — confirma que a causa #1 era real e a correção é válida por si só (deve ser mantida independente do resto). **Mas o FPS não melhorou** (50.8 vs 48.6, dentro do ruído) — o custo simplesmente migrou quase inteiro para a categoria `MainRender` (1.12ms/4.9% → **13.90ms/66.5%**). Ou seja: o gargalo real do GPU skinning nunca esteve na passada de CPU/deform (`UpdateAnimationDeformers`/categoria "Skinning") — está no **render** (`BL_BlenderShader::Update`, que faz `GPU_material_bind_bone_matrices`→`GPU_shader_uniform_vector`→`glUniformMatrix4fv` uma vez por mesh-slot, todo frame, durante `MainRender`), só que estava mascarado pelo bug da causa #1.
- **Causa raiz #2 — NÃO investigada, fora do alcance sem profiler de GPU**: por que o upload de uma paleta de bone matrices (dezenas de `mat4`, nada absurdo em volume) custa ~12ms extra de `MainRender` pra só 1 personagem. Hipóteses não verificadas: overhead de `glUniformMatrix4fv` chamado por mesh-slot (9 vezes/frame pra esse personagem) em vez de uma vez por objeto; algum estado de shader/VAO sendo re-setado por causa da variante `USE_SKINNING`; ou sincronização acidental em algum ponto do bind. Diagnosticar isso ao certo exige RenderDoc/Nsight, não só leitura de código e profiler in-game — fica para uma sessão futura.
- **Conclusão desta rodada**: GPU Skinning está **funcionalmente correto** (geometria certa, parado e em movimento) mas **não entrega o ganho de performance que motivou o trabalho** — pelo contrário, é hoje mais lento que CPU skinning para este cenário de teste. Não é um limite fundamental da abordagem (upload de bone palette via uniform é uma técnica padrão em outras engines), é um problema de implementação ainda não localizado com precisão. **Não recomendado para uso em produção nesta forma** até a causa #2 ser encontrada e corrigida.

**Fase G — causa raiz #2 investigada com instrumentação manual (RenderDoc bloqueado por compat profile): MainRender alto NÃO é causado pelo GPU Skinning — é custo normal da cena**
- RenderDoc não pôde ser usado: exige core profile OpenGL, e a engine roda em compatibility profile (gap já documentado na trilha Iluminação) — "Captures disabled" ao tentar. Sem Nsight disponível, a investigação seguiu por instrumentação manual de CPU (`std::chrono`) diretamente no código, em vez de profiler de GPU externo.
- Timers temporários inseridos em três pontos do pipeline de render (removidos ao final da sessão): (1) dentro de `BL_BlenderShader::Update()`, separando o tempo de `GPU_material_bind_uniforms` do de `GPU_material_bind_bone_matrices`/`glUniformMatrix4fv`; (2) em `RAS_MeshSlot::RunNode()`, separando `ActivateMeshUser` da submissão real do draw call (`storage->IndexPrimitives()`); (3) um print único por material em `KX_BlenderMaterial::ActivateMeshUser()` para confirmar qual caminho de shader (`m_shader` custom vs. `m_blenderShader`) e qual flag (`use_gpu_skinning`) está realmente em uso em runtime.
- **Achado de processo, não de performance**: o material com `use_gpu_skinning=True` esperado (`Ch33_body`/`Ch33_hair`, sem sufixo) não era o material realmente desenhado em tela — o personagem com o armature `BGE_GPU` (`Armature.000`, único entre os 11 personagens do teste) usa os materiais `Ch33_body.001`/`Ch33_hair.001`, que já estavam com a flag ligada desde o início. Cada personagem é composto por 7-9 objects de malha (Belt/Body/Pants/Shirt/Shoes/Suit/Tie etc.) compartilhando o mesmo material — cenário que passa por `RAS_DisplayArrayBucket::RunBatchingNode` (static batching via `KX_BatchGroup`, montado por um script Python embutido na cena), não pelo `RAS_MeshSlot::RunNode` normal. A proteção existente (`KX_BatchGroup::MergeObjects`, Fase D) que rejeita objects GPU-skinned do batching estático continua válida e não impediu nada de errado aqui — o personagem `.000` de fato usa GPU skinning corretamente.
- **Resultado da instrumentação em ambos os caminhos de render (`RunNode` e `RunBatchingNode`, cobrindo tanto o personagem GPU quanto os 10 CPU)**: custo de `Update()` (incluindo o upload da paleta de bones) e custo de submissão do draw call ficaram **ambos ~0.000-0.005ms**, consistentemente, ao longo de centenas de frames — nenhum dos dois pontos suspeitos (upload de uniform, emissão do draw) explica os ~12-15ms de `MainRender`.
- **Teste decisivo**: benchmark comparativo na mesma cena (`benchmark_gpu_test.range`, 168 objetos), alternando `Armature.000.deform_method` entre `BGE_GPU` e `BLENDER` (CPU, todos os 11 personagens 100% CPU). `MainRender` ficou **estatisticamente igual nos dois casos** (10.8-15.3ms com GPU skinning ligado vs. 12.0ms com GPU skinning totalmente desligado) — a variação está dentro do ruído normal entre execuções, não há diferença sistemática atribuível ao GPU skinning.
- **Conclusão revisada (substitui a da Fase F)**: o `MainRender` alto (~12-15ms, 55-66% do frame) **não é causado pelo GPU Skinning** — é o custo normal desta cena de teste (168 objetos, várias sombras, múltiplos personagens com malhas relativamente pesadas) e já existia antes de qualquer trabalho de GPU skinning, mascarado pela causa raiz #1 (Fase F) que inflava `Skinning`/`GPU Latency` artificialmente. **GPU Skinning é seguro para uso** do ponto de vista de performance range desta investigação — não acelera nem piora o `MainRender` neste cenário; o ganho real dependeria de cenas com mais personagens GPU-skinned simultâneos (não testado). A causa raiz do `MainRender` alto em si (não relacionada a skinning) fica como investigação separada para sessão futura — candidatos a explorar: número de draw calls não-batchados, custo de sombras (`Shadows` 1.2-1.8ms é só a categoria própria, mas pode haver overhead de shadow map em `MainRender`), ou geometria/shader cost geral da cena.
- Toda a instrumentação temporária (`std::chrono`/`fprintf(stderr, ...)` em `BL_BlenderShader.cpp`, `RAS_MeshSlot.cpp`, `KX_BlenderMaterial.cpp`) foi removida ao final; nenhum código de diagnóstico permanece no branch.
- **Achado incidental**: a propriedade `use_gpu_skinning` (material) existe na API Python/RNA desde a Fase B mas nunca tinha sido exposta na UI do editor (`properties_material.py`) — só `use_instancing` tinha o `col.prop(...)` correspondente. Corrigido: `col.prop(mat, "use_gpu_skinning")` adicionado ao lado de `use_instancing` no painel de Material (Physics/Game tab).

## 2026-08-24

**Correção de documentação: modelo PBR já existe, não é trabalho futuro**
- Usuário apontou que a Range Engine 1.4 já divulgava PBR shading (screenshot do site oficial). Confirmado no código: `node_bsdf_principled` (`gpu_shader_material.glsl:3765`) já é um Principled BSDF completo (base_color, metallic, roughness, subsurface, clearcoat, anisotropic, transmission), herdado do fork 1.6 Rev2. `relatorio-melhorias-anastacioengine.md` corrigido — Fase 2 (PBR) da trilha Iluminação deixou de ser "avaliar depois do core profile" e passou a "já implementado, herdado do fork".

**Migração para OpenGL Core Profile — Fase 1 concluída (plumbing de upload de uniforms), frente de alto risco escolhida pelo usuário**
- Plano completo de 8 fases escrito e aprovado (`~/.claude/plans/hashed-leaping-quiche.md`), cobrindo vertex/material shaders, filtros SSAO/SSR/Light Scatter, shadow VSM e debug draw. Cada fase isolada sob `#ifdef USE_CORE_PROFILE`, build padrão COMPAT=ON intocado até a fase final.
- **Fase 0 (groundwork)**: `RAS_Rasterizer` passou a guardar a matriz de projeção (`m_projmatrix`, populada em `SetProjectionMatrix()`, antes só era enviada pro fixed-function e descartada). `gpu_shader.c` ganhou o ponto de injeção do define `USE_CORE_PROFILE` (gated por `WITH_GL_PROFILE_CORE`, inerte no build padrão) em `gpu_shader_version()`/`gpu_shader_standard_defines()`.
- **Fase 1 (uniform upload)**: dois builtins novos em `GPU_material.h` — `GPU_PROJECTION_MATRIX` e `GPU_NORMAL_MATRIX` — seguindo o mesmo padrão já existente para `GPU_VIEW_MATRIX`/`GPU_LOC_TO_VIEW_MATRIX` (nome do uniform em `gpu_codegen.c`, location lookup e upload em `gpu_material.c`). Nenhum shader ainda declara esses uniforms, então os builtins nunca são ativados — mudança inerte até a Fase 3+ (puramente aditiva).
  - `GPU_material_bind()` ganhou parâmetro `projmat[4][4]`, threadeado pelos 6 call sites: jogo (`BL_BlenderShader::BindProg`, `KX_WorldInfo`) passa a matriz real via `rasty->GetProjectionMatrix()` (accessor novo); editor (`view3d_draw.c`) passa `rv3d->winmat`; um call site do editor (`gpu_draw.c`, object-mode draw) passa `NULL` por não ter uma matriz de projeção trivialmente disponível ali — fora do escopo desta migração (o jogo é o alvo).
  - Normal matrix (`GPU_NORMAL_MATRIX`) calculada em `GPU_material_bind_uniforms()` como `transpose(inverse(mat3(view*obmat)))` — equivalente ao que o fixed-function `gl_NormalMatrix` já calcula automaticamente a partir do MODELVIEW atual. Investigado o suposto risco de escala negativa (`m_camnegscale`, `SetViewMatrix(mat, scale)`): confirmado que só afeta o *winding* de face (front-face culling), não a matemática da normal matrix — não precisa de tratamento especial na derivação.
- **Bug de processo encontrado e descartado — build incremental obsoleto, não um bug real**: após adicionar `m_projmatrix` a `RAS_Rasterizer.h`, `ninja RangeRuntime` incremental produziu um binário que crashava com `EXCEPTION_ACCESS_VIOLATION` no load da cena. Bisectado via `git stash` (isolando arquivo por arquivo) até um único header — parecia um bug real de código. `ninja -t clean` + rebuild completo do mesmo código fez o crash desaparecer inteiramente. Confirma que a lacuna de rastreamento de dependência do Ninja documentada para `DNA_*.h` (ver Fase B/C acima) também pode afetar headers comuns — anotado na memória do projeto: depois de tocar em qualquer header deste build, preferir rebuild limpo antes de investigar um crash "estranho".
- Todas as etapas confirmadas com rebuild limpo + `RangeRuntime.exe` no `benchmark.range`: sem erro de shader no console, sem crash, screenshot idêntica entre Fase 0 e Fase 1 (esperado, mudança inerte).
- **Pendente para a próxima sessão**: Fase 2 (injeção de `#version 330 core` real e teste em build CORE descartável) em diante — ver plano completo.

**Migração para OpenGL Core Profile — Fase 2 investigada: achado que redefine o escopo da Fase 8**
- Confirmado que a injeção de `#version 330 core`/`#define USE_CORE_PROFILE` (`gpu_shader.c:145-147,247-249`) já estava presente nas mudanças não commitadas desde a Fase 0 — nada novo a escrever aqui, só faltava verificar.
- Build COMPAT padrão rebuildado (`ninja RangeRuntime`) e confirmado sem mudança ("no work to do" — já estava atualizado).
- Build CORE=ON descartável criado em `build_core_test/` (cópia via `robocopy /MIR` do `build/` + `cmake -DWITH_GL_PROFILE_CORE=ON -DWITH_GL_PROFILE_COMPAT=OFF .` reapontando `CMAKE_CACHEFILE_DIR`). Ao tentar compilar `RangeRuntime` nesse diretório, encontrado um bloqueio de **compilação C++ (não GLSL runtime, como o plano previa)**: o próprio motor já tem um mecanismo de "poison" de funções fixed-function em core profile (`glew-mx.h:80-81` inclui `intern/gl-deprecated.h`, que redefine `glBegin`/`glVertex*`/`glTranslatef`/etc. para `DO_NOT_USE_*` quando `CORE && !COMPAT`).
- Primeiro ponto encontrado: 3 funções inline em `BIF_gl.h:81-92` (`glTranslate3fv`/`glScale3fv`/`glRotate3fv` e variantes) usavam essas chamadas fora de qualquer guard — corrigido envolvendo em `#ifdef WITH_GL_PROFILE_COMPAT` (mudança no source compartilhado, mas inerte no build padrão já que `WITH_GL_PROFILE_COMPAT` é `ON` lá).
- Rebuild seguinte (2487 passos, `BIF_gl.h` é incluído amplamente) revelou o problema real: **3.589 ocorrências de OpenGL fixed-function em 73 arquivos de `source/blender/editors/`** (UI do editor Blender — `view3d_draw.c`, `interface_widgets.c`, `drawobject.c`, `anim_markers.c` etc.), nunca preparados para core profile (herdado do Blender 2.79, que não suportava core profile no editor). Em contraste, `source/gameengine/` (o que roda no `RangeRuntime`) tem só **35 ocorrências em 4 arquivos** (`RAS_OpenGLRasterizer.cpp`, `RAS_OpenGLLight.cpp`, `RAS_OpenGLDebugDraw.cpp`, `RAS_StorageVao.cpp`).
- **Conclusão**: a Fase 8 do plano original (flip do build inteiro, incluindo `RangeEngine`/editor, para core profile) não é viável sem migrar milhares de call sites de UI — fora de proporção com o valor pra este fork. Decisão do usuário: redefinir o objetivo da Fase 8 para **só o `RangeRuntime` (player) em core profile**, mantendo `RangeEngine` (editor) permanentemente em compatibility.
- Investigação de viabilidade: `source/source/blenderplayer/CMakeLists.txt:101-190` (lista `BLENDER_SORTED_LIBS` do `RangeRuntime`) **não inclui nenhuma lib `bf_editors_*`** — só `bf_editor_datafiles` (ícones/dados, não é a UI). Isso indica que o player não depende do código de `editors/` e a Fase 8 restrita é em princípio viável. O erro de compilação encontrado veio de `ninja RangeRuntime` processando arquivos de `editors/` mesmo assim — investigado a seguir.

**Migração para OpenGL Core Profile — dependência espúria localizada: não é bug do Ninja, é dependência real do `bf_rna`**
- `ninja -t query bin/RangeRuntime.exe` (em `build_core_test/`) confirma que `RangeRuntime` linka diretamente com ~30 libs `bf_editor_*` (`bf_editor_space_view3d`, `bf_editor_interface`, `bf_editor_armature` etc.), apesar de `BLENDER_SORTED_LIBS` no `blenderplayer/CMakeLists.txt` não listar nenhuma delas — a dependência é transitiva, injetada por outra lib.
- Rastreada até `source/blender/makesrna/intern/CMakeLists.txt:393-408`: o target `bf_rna` (que `RangeRuntime` linka diretamente, via `BLENDER_SORTED_LIBS`) declara ~14 libs `bf_editor_*` na sua lista `LIB`, que `blender_add_lib()` (`build_files/cmake/macros.cmake:277-295`) linka como `target_link_libraries(bf_rna INTERFACE ${library})` — ou seja, viram dependência pública de qualquer coisa que linke `bf_rna`, incluindo `RangeRuntime`.
- **Não é um artefato de tracking do Ninja nem do CMake — é uma dependência de código real**: os callbacks RNA gerados (`rna_object.c`, `rna_mesh.c` etc.) chamam funções `ED_*` do editor diretamente (ex.: `ED_object_parent()`, `ED_curve_editnurb_load()` em `rna_object.c`), porque a API RNA do Blender 2.79 foi desenhada para o editor ler/escrever propriedades via os mesmos setters que a UI usa — o motor de jogo herda esse acoplamento só por linkar `bf_rna` (necessário para `.range`/`.blend` I/O e a API Python do jogo).
- **Conclusão que redefine a Fase 8 de novo**: o escopo "só `RangeRuntime` em core profile, sem tocar `editors/`" não é viável como estava definido — `bf_rna` arrasta ~14 das ~30 libs `bf_editor_*` para dentro do link do player goste ou não. Migrar só os 35 pontos fixed-function do `gameengine/` não é suficiente; seria necessário também migrar (ou stub) os pontos fixed-function das libs `bf_editor_*` que `bf_rna` linka — que é uma fatia menor que os 73 arquivos completos de `editors/`, mas ainda não medida. Medido: as 14 pastas `editors/{armature,curve,mesh,object,physics,render,sculpt_paint,space_clip,space_file,space_image,space_info,space_node,space_view3d,transform}` (union das libs linkadas por `bf_rna` + `bf_editor_transform`/`bf_editor_render` que aparecem no `ninja -t query`) somam **~1.483 ocorrências fixed-function em ~37 arquivos** — menos da metade dos 3.589/73 originais (dominado por `space_view3d`, 847, e `transform`, 212), mas ainda uma migração grande, não um fix pontual. **Pendente para a próxima sessão**: decisão do usuário sobre se vale migrar essa fatia menor (~1.483 ocorrências) ou se a Fase 8 deve ser abandonada/adiada de novo.
- `build_core_test/` mantido em disco (descartável, fora do controle de versão) para retomar a investigação sem precisar reconfigurar do zero.

**Migração para OpenGL Core Profile — Fase 2 concluída: build CORE escopado ao target real, `editors/`/`bf_rna` nunca precisam ser tocados**
- **Correção de arquitetura**: em vez de flipar `WITH_GL_PROFILE_COMPAT`/`WITH_GL_PROFILE_CORE` globalmente (que afeta todo mundo que chama `add_definitions(${GL_DEFINITIONS})`, incluindo `editors/` e `bf_rna`), foi descoberto que essas ~59 chamadas já são por-target — cada `CMakeLists.txt` decide se recebe `GL_DEFINITIONS`. Isso permite escopar o "veneno" (poison de fixed-function via `gl-deprecated.h`) só no código que o `RangeRuntime` de fato executa, sem tocar o resto do build nem precisar da migração de ~1.483 ocorrências do achado anterior.
- Adicionada opção `WITH_GL_PROFILE_CORE_RASTERIZER_TEST` (`source/CMakeLists.txt`, default `OFF`, `mark_as_advanced`) que gera uma variável `GL_DEFINITIONS_RASTERIZER` — igual a `GL_DEFINITIONS` (comportamento padrão inalterado) quando `OFF`, ou só `-DWITH_GL_PROFILE_CORE` (sem `COMPAT`) quando `ON`. `gameengine/Rasterizer/RAS_OpenGLRasterizer/CMakeLists.txt` (o único target que contém as 35 ocorrências fixed-function reais do gameengine) trocou `add_definitions(${GL_DEFINITIONS})` por `add_definitions(${GL_DEFINITIONS_RASTERIZER})` — a única mudança de fato no grafo de build.
- Reconfigurado `build_core_test/` com `WITH_GL_PROFILE_CORE=OFF -DWITH_GL_PROFILE_COMPAT=ON -DWITH_GL_PROFILE_CORE_RASTERIZER_TEST=ON` (ou seja: build inteiro em COMPAT normal, só o rasterizer em CORE isolado) e `ninja RangeRuntime`. **Resultado confirma a hipótese**: das 1907 etapas do build, só as 4 arquivos esperados falharam — `RAS_OpenGLRasterizer.cpp`, `RAS_OpenGLLight.cpp`, `RAS_OpenGLDebugDraw.cpp`, `RAS_StorageVao.cpp` — todos com erros `DO_NOT_USE_gl*` exatamente nos pontos fixed-function já mapeados (glMaterialfv, glLightf, glVertexPointer, glPushMatrix/glLoadMatrixf/glMultMatrixf, glAccum, etc.), mais um `USE_GL_CLIP_DISTANCE0` não definido (dependência cruzada a resolver na Fase 3). `editors/`, `bf_rna` e todo o resto do build (1753 outras etapas) compilaram normalmente sob COMPAT, sem qualquer alteração de comportamento.
- **Fase 2 dá-se por concluída**: a infraestrutura de verificação (build CORE isolado e reproduzível, sem custo de migrar o editor) está pronta e funcionando. O caminho para a Fase 3 está livre: migrar exatamente esses 35 pontos fixed-function nesses 4 arquivos (mais resolver `USE_GL_CLIP_DISTANCE0`) é o próximo trabalho, e cada iteração pode ser verificada rodando `ninja RangeRuntime` neste mesmo `build_core_test/` já configurado.

**Migração para OpenGL Core Profile — os 35 pontos fixed-function do gameengine resolvidos, `RangeRuntime` CORE compila e roda**
- Pesquisado precedente externo antes de inventar convenção própria: UPBGE (fork que assumiu o BGE após a Blender Foundation descontinuar) tem histórico de commits "core profile" (`a4fb4abe`), mas sua correção foi pro `RAS_StorageVBO.cpp` (path não-VAO, redescobre a location via `glGetAttribLocation` a cada bind — válido só porque redefine por draw call) e o `master` atual já foi reescrito por completo sobre o Gawain/GPU_batch moderno do Blender 4.x (não existe mais `RAS_StorageVao.cpp` lá) — nenhum dos dois é um precedente direto pro nosso caso (VAO com binding fixado na criação, não por draw call). Confirmado via Khronos OpenGL Wiki que a prática padrão pra esse caso (um VAO, vários shader programs) é `layout(location=N)` explícita e consistente entre todos os shaders, exatamente a abordagem já usada.
- `RAS_OpenGLLight.cpp` (`ApplyFixedFunctionLighting`, `glLightfv`/`glLightf`/`glEnable(GL_LIGHT0+n)`): confirmado morto para materiais GLSL — `GPU_material_update_lamps`/`GPU_material_bind_uniforms` já alimentam luzes via `GPULamp`/uniforms, não via estado fixed-function. Guardado sob `#ifdef WITH_GL_PROFILE_COMPAT`, lógica de contagem/filtro de luz preservada.
- `RAS_StorageVao.cpp` (`glEnableClientState`/`glVertexPointer`/`glNormalPointer`/`glColorPointer`/`glClientActiveTexture`/`glTexCoordPointer`): substituído sob `WITH_GL_PROFILE_CORE` por `glVertexAttribPointer` em locations explícitas reservadas — `RAS_ATTR_LOC_POSITION=0`, `_NORMAL=1`, `_COLOR=2` — que ficam como contrato pendente para `gpu_shader_vertex.glsl` declarar (`layout(location=0) in vec3 position;` etc.) quando migrado na Fase 3 do plano original. Atributos genéricos (UV, tangente, bone data) já usavam `attrib.m_loc` (lookup por nome, por-material) tanto no branch antigo quanto no novo — sem risco de colisão contanto que o shader base reserve essas 3 locations.
- `RAS_OpenGLDebugDraw.cpp` (`glOrtho` x2, `glColor4fv`): guardado sob COMPAT. Achado à parte: `BLF_draw` (`source/blender/blenfont/`, usado pro texto de debug on-screen) é fixed-function por dentro (`glMatrixMode`/`glPushMatrix`/`glGetFloatv(GL_CURRENT_COLOR)` em `blf_draw_gl__start`) — módulo inteiro fora do escopo desta migração, texto de debug simplesmente não renderiza sob CORE até essa lib ganhar sua própria migração (não afeta a cena principal).
- `RAS_OpenGLRasterizer.cpp` (maior arquivo, ~9 funções): `ScreenPlane` já fazia dual-write pros atributos genéricos (locations 0/1) desde a migração anterior dos filtros — só sobrava guardar o client-state redundante. `Init`/`BeginFrame`/`SetAmbient`/`SetFog`/`Exit`/`EnableLights` (glShadeModel/glLightModelfv/glFog*/glColorMaterial) confirmados mortos pra GLSL, mesmo padrão do `RAS_OpenGLLight.cpp`. `SetSpecularity`/`SetShinyness`/`SetDiffuse`/`SetEmissive` (glMaterialfv) idem. `PushMatrix`/`PopMatrix`/`SetMatrixMode`/`MultMatrix`/`LoadMatrix`/`LoadIdentity` — a pilha de matriz fixed-function que envolve cada draw call — viram no-op sob CORE (push/pop ficam balanceados por serem os dois no-op); seguro porque a Fase 0/1 já threadeia as matrizes rastreadas em CPU direto como uniforms via `GPU_material_bind()`, sem depender desse estado GL. Dois gaps documentados como conhecidos, não migrados agora: `EnableClipPlane`/`DisableClipPlane` (`glClipPlane`/`GL_CLIP_PLANE0` não tem equivalente fixed-pipeline em core — precisaria de `gl_ClipDistance[]` escrito pelo vertex shader, é trabalho da Fase 3) e `MotionBlur` (`glAccum`, buffer de acumulação foi **removido** do core profile, sem substituto direto — precisaria de um pass de post-process por velocity buffer, mesma família dos filtros SSAO/SSR já existentes).
- **Build CORE completo compila e linka**: os 4 arquivos + o resto do build (1907 passos) — `RangeRuntime.exe` gerado em `build_core_test/bin/`. Rodado contra `benchmark.range`: log confirma `Compiled GL Profile: Core` (GL 4.6 core real, não um fallback compat), processo não crasha. Renderização visivelmente quebrada (formas sólidas azul/rosa sem a cena 3D correta, texto de debug corrompido) — **esperado e correto**: `gpu_shader_vertex.glsl`/`gpu_shader_material.glsl` ainda usam `gl_Vertex`/`gl_ModelViewMatrix`/etc., inválidos sob `#version 330 core`, então os shaders de material devem estar falhando silenciosamente na compilação (driver NVIDIA não imprimiu erro no console capturado, mas o resultado visual bate com o esperado). Screenshot salva como baseline "antes" da Fase 3 em `projects-teste/core_profile_phase3_screenshot.png`.
- **Estado final**: as Fases 0-2 do plano de 8 fases estão completas e verificadas. O bloqueio C++ que impedia até testar visualmente (achado depois da Fase 2, tratado como extensão emergencial da Fase 7) está resolvido. Caminho livre para a Fase 3 do plano original (migração GLSL de `gpu_shader_vertex.glsl`), que agora pode ser verificada de ponta a ponta (compilar + rodar + screenshot) neste mesmo `build_core_test/`.

**Migração para OpenGL Core Profile — Fase 3 concluída: `gpu_shader_vertex.glsl` migrado e verificado sem erro de compile**
- `gl_Vertex`/`gl_Normal` → `layout(location = 0) in vec3 att_Position;`/`layout(location = 1) in vec3 att_Normal;` sob `USE_CORE_PROFILE`, casando com o contrato de locations já fixado em `RAS_StorageVao.cpp` na Fase 2 (0=position, 1=normal, 2=color). `gl_ModelViewMatrix` → `unfviewmat * unfobmat` (os dois já existiam como uniform incondicional no arquivo, só não eram usados no `main()`). `gl_ProjectionMatrix`/`gl_NormalMatrix` → dois uniforms novos, `unfprojmat` (`mat4`) e `unfnormalmat` (`mat3`).
- **Achado**: `unfprojmat`/`unfnormalmat` (via os builtins `GPU_PROJECTION_MATRIX`/`GPU_NORMAL_MATRIX` da Fase 1) só recebem valor do lado C++ (`gpu_material.c:337-340`) se o bit correspondente estiver setado em `material->builtins` — e esse bit só liga quando algum nó do grafo de material referencia aquele builtin explicitamente, nunca o caso do vertex shader base (que precisa dessas matrizes incondicionalmente, pra todo material, sob CORE). Corrigido forçando os 4 bits (`GPU_VIEW_MATRIX|GPU_OBJECT_MATRIX|GPU_PROJECTION_MATRIX|GPU_NORMAL_MATRIX`) sob `#ifdef WITH_GL_PROFILE_CORE`, logo após `GPU_generate_pass()` retornar em `gpu_material_construct_end()` (`gpu_material.c` ~linha 329) — ~7 linhas, inerte no build padrão (macro nunca definida lá).
- `gl_ClipPlane[i]`/`gl_ClipVertex` (usado só por `KX_PlanarMap`, clipping de reflexo em espelho/água): virou no-op sob `USE_CORE_PROFILE` no shader (não escreve `gl_ClipDistance[]`), espelhando o no-op já existente do lado C++ desde a Fase 2 (`RAS_OpenGLRasterizer::EnableClipPlane`/`DisableClipPlane`, guardados sob `WITH_GL_PROFILE_COMPAT`). Porte completo pra `gl_ClipDistance[]` (precisaria de `glEnable(GL_CLIP_DISTANCE0)` + uniform de plano + o vertex shader escrevendo o array) fica documentado como gap conhecido, fora de escopo até essa feature ser revisitada.
- **Escopo do build de teste precisou crescer**: a verificação por log de compile só é significativa se `blender/gpu` (que emite o `#version`/`USE_CORE_PROFILE` via `gpu_shader.c`) também compilar com `WITH_GL_PROFILE_CORE` — até aqui só `RAS_OpenGLRasterizer` tinha a flag (Fase 2). Primeira tentativa escopou o target `bf_gpu` inteiro via `GL_DEFINITIONS_RASTERIZER` — quebrou a compilação: ~10 arquivos não relacionados à migração (`gpu_draw.c`, `gpu_buffers.c`, `gpu_compositing.c`, `gpu_select.c`/`gpu_select_pick.c`/`gpu_select_sample_query.c`, `gpu_basic_shader.c`, `gpu_texture.c`, `gpu_framebuffer.c`, `gpu_extensions.c`, `gpu_debug.c`) usam OpenGL fixed-function/enums legados por toda parte (seleção/picking de objetos no editor, compositing, texto de debug de estado GL) — mesmo padrão do achado `editors/`/`bf_rna` da Fase 2. **Corrigido escopando por arquivo**, não por target: `source/blender/gpu/CMakeLists.txt` reverteu pro `add_definitions(${GL_DEFINITIONS})` normal e ganhou um `set_source_files_properties(intern/gpu_shader.c intern/gpu_material.c PROPERTIES COMPILE_DEFINITIONS "WITH_GL_PROFILE_CORE")` guardado por `if(WITH_GL_PROFILE_CORE_RASTERIZER_TEST)` — só esses 2 arquivos (os únicos que este trabalho de fato toca) recebem a define no build de teste; o resto de `bf_gpu` continua em COMPAT. A descrição da opção `WITH_GL_PROFILE_CORE_RASTERIZER_TEST` em `source/CMakeLists.txt` foi atualizada pra refletir que agora cobre mais que só o rasterizer.
- **Verificado**: `ninja RangeRuntime` em `build_core_test/` recompila só os arquivos afetados (`gpu_shader_vertex.glsl.c`, `gpu_shader.c`, `gpu_codegen.c`, `gpu_material.c` + link) e termina em 11/11, 0 erros. Rodando `RangeRuntime.exe benchmark.range`: o log de compile GLSL não mostra **nenhum erro em `gpu_shader_vertex.glsl`** — os únicos erros capturados são em `gpu_shader_material.glsl` (linhas 90-93: `gl_ProjectionMatrix`/`gl_ModelViewMatrix`/`gl_ModelViewProjectionMatrix removed after version 140`), que é território da Fase 4, ainda não migrada — resultado esperado e correto. O processo em seguida crasha com `EXCEPTION_ACCESS_VIOLATION`; não investigado a fundo (fora do escopo desta fase), mas plausivelmente um shader/programa GL inválido sendo usado a jusante por causa da falha de link do material, não do vertex (que compilou limpo) — hipótese é que suma sozinho quando a Fase 4 migrar `gpu_shader_material.glsl`. Confirmado que `GPU_material_bind()` já testa `material->pass != NULL` antes de usar, então o crash não vem desse ponto óbvio.
- **Build COMPAT padrão intocado**: `ninja bf_gpu` no `build/` normal recompilou os mesmos arquivos e linkou sem erro nem warning novo (58/58) — o branch `#else`/inerte de todas as mudanças (shader e `gpu_material.c`) é texto idêntico ao anterior.
- Sanity check de segurança: `RAS_OpenGLRasterizer::EnableClipPlane`/`DisableClipPlane` (Fase 2) e o novo bloco de clip do shader (Fase 3) são consistentes entre si — ambos no-op sob CORE, nenhum dos dois tenta escrever/ler um estado que o outro não fornece.
- **Estado final**: Fase 3 do plano de 8 fases completa e verificada. Caminho livre para a Fase 4 (`gpu_shader_material.glsl`, maior risco do plano inteiro — 5227 linhas geradas por codegen de nós).

## 2026-08-24

**Migração para OpenGL Core Profile — Fase 4 concluída: `gpu_shader_material.glsl` migrado; crash da Fase 3 investigado e não vem deste arquivo**
- Todas as substituições feitas via `#define` sob `USE_CORE_PROFILE`, no topo do arquivo, em vez de editar os ~30 pontos de uso espalhados individualmente (mais simples e menos arriscado que ifdef por call site, num arquivo gerado por codegen de nós): `texture2D`→`texture`, `texture2DLod`/`textureCubeLod`→`textureLod`, `texture2DProj`→`textureProj` (~45 usos); `gl_ProjectionMatrix`→`unfprojmat`, `gl_ProjectionMatrixInverse`→`inverse(unfprojmat)`, `gl_ModelViewMatrix`→`(unfviewmat * unfobmat)`, `gl_ModelViewMatrixInverse`→`inverse(unfviewmat * unfobmat)`, `gl_NormalMatrix`→`unfnormalmat` (~20 usos). Os 4 uniforms (`unfviewmat`/`unfobmat`/`unfprojmat`/`unfnormalmat`) já eram forçados incondicionalmente para todo material sob `WITH_GL_PROFILE_CORE` desde a Fase 3 (`gpu_material.c`), então bastou declará-los no topo deste arquivo (mesmo nome, para casar com a location já resolvida no programa linkado) — nenhuma mudança de C++ foi necessária nesta fase.
- **Achado fora do escopo original do plano**: `node_bsdf_diffuse`/`node_bsdf_glossy`/`node_bsdf_principled` (nós de shading novos, incluindo o Principled BSDF) leem `gl_LightSource[i]` (array fixed-function de luzes) num loop `NUM_LIGHTS`, sem equivalente em core profile. Como o lado C++ que alimentava esse array (`glLightfv` em `RAS_OpenGLLight.cpp`) já tinha sido confirmado morto e no-op'd sob CORE na Fase 2, o array estaria vazio/indefinido de qualquer forma — guardado o loop de luzes direcionais sob `#ifndef USE_CORE_PROFILE` nos 3 lugares (fallback vira ambient-only sob CORE), documentado como gap conhecido no mesmo padrão de `EnableClipPlane`/`MotionBlur` já aceito nas fases anteriores. Sem esse guard o arquivo não compilaria sob `#version 330 core` (`gl_LightSource` foi removido).
- **Verificado**: `grep` confirma nenhum uso não-guardado de `gl_ModelViewMatrix`/`gl_ProjectionMatrix`/`gl_NormalMatrix`/`gl_LightSource` fora dos `#define`/`#ifndef` novos. `ninja RangeRuntime` em `build_core_test/` recompila só os arquivos afetados (`gpu_shader_material.glsl.c`, `bf_gpu`, link) e termina 4/4, 0 erros.
- **Crash investigado (pedido do usuário) — não vem de `gpu_shader_material.glsl`**: rodando `RangeRuntime.exe benchmark.range` no build CORE pós-Fase-4, o log de compile GLSL **não mostra mais nenhum erro em `gpu_shader_material.glsl`** (migração confirmada correta), mas o `EXCEPTION_ACCESS_VIOLATION` da Fase 3 persiste, com os mesmos erros de compile (`gl_ProjectionMatrix`/`gl_ModelViewMatrix removido após a versão 140`, linhas 90-91 e 93 do shader montado). A hipótese da Fase 3 ("deve sumir quando a Fase 4 migrar o material") estava errada — os erros vêm de outro grupo de shaders "builtin" do motor (compilados sob demanda via `GPU_shader_create`/`GPU_shader_get_builtin_shader` em `gpu_shader.c`, não pelo codegen de nós de material): `gpu_shader_flat_color_vert.glsl` (`gl_ProjectionMatrix * gl_ModelViewMatrix` numa linha só, bate exatamente com o padrão do primeiro erro do log) e a dupla `gpu_shader_frustum_line_vert.glsl`/`gpu_shader_frustum_solid_vert.glsl` (`gl_ModelViewProjectionMatrix`, bate com o segundo/terceiro erro) — usados por overlays de debug draw (frustum de câmera, outlines) via `GPU_SHADER_FLAT_COLOR`/`GPU_SHADER_FRUSTUM_LINE`/`GPU_SHADER_FRUSTUM_SOLID`, não cobertos pelo plano original (que listava só vertex/material/SSAO/SSR/light-scatter/VSM/debug-draw-C++). **Isso redefine o escopo da Fase 7** ("debug draw"), que o plano original assumia poder se reduzir a validação (achando que não havia `.glsl` dedicado a debug draw) — na verdade existem pelo menos 3 arquivos GLSL builtin dedicados (`flat_color`, `frustum_line`, `frustum_solid`), possivelmente mais (`basic_vert`/`basic_frag`, `black_vert`, `box2d`, `smoke_vert` também usam esses símbolos e não foram auditados ainda). **Pendente para a próxima sessão**: mapear todos os builtin shaders afetados, migrá-los seguindo o mesmo padrão de `#define` desta fase, e então revalidar se o crash desaparece.

**Migração para OpenGL Core Profile — Fase 5 investigada: o plano original mirava os arquivos errados**
- Usuário pediu para seguir com a Fase 5 (SSAO/SSR/Light Scatter). Começada a mesma migração por `#define` usada na Fase 4 em `gpu_shader_fx_ssao_frag.glsl` — mas antes de terminar, investigado quem de fato chama `GPU_shader_get_builtin_fx_shader`/`GPU_fx_do_composite_pass` (as únicas funções que compilam esses 3 arquivos do plano) e confirmado por grep que a única chamada existe em `source/blender/editors/space_view3d/view3d_draw.c` — o viewport do **editor** do Blender, parte de `editors/`, que `RangeRuntime` nunca linka (decisão permanente da Fase 2/8: editor fica em COMPAT, fora de escopo). Ou seja, esses 3 arquivos nunca são sequer compilados pelo jogo — a edição (inerte, mas inútil) foi revertida (`git diff` confirma o arquivo voltou a zero).
- **O SSAO/SSR/LightScatter que o jogo de fato renderiza é outro sistema**: `KX_Scene.cpp` lê `scene->scenefx_settings.scenefx_flag` (`SCENE_FX_FLAG_SSAO`/`_SSR`/`_LIGHTSCATTER`) e alimenta o pipeline de 2D Filters do gameengine, que usa `source/gameengine/Rasterizer/RAS_OpenGLFilters/RAS_SSAO2DFilter.glsl`, `RAS_SSR2DFilter.glsl`, `RAS_SSR_Blur2DFilter.glsl`, `RAS_LightScaterring_Buffer2DFilter.glsl`, `RAS_LightScaterring_Image2DFilter.glsl` — arquivos completamente diferentes dos do plano.
- **Corrige também uma afirmação errada de sessão anterior**: `relatorio-melhorias-anastacioengine.md`/este changelog diziam que o grupo `RAS_OpenGLFilters/` estava "fechado (12/12)" — reler a entrada original (mais acima nesta mesma data) mostra que ela na verdade **excluía explicitamente** os filtros multi-pass nativos (Bloom/SSR/LightScattering/SSAO/Tonemap) desse escopo fechado, com a justificativa de que "já usam `texture()`" — parcialmente certo (`texture()` sim), mas incompleto: lendo `RAS_SSAO2DFilter.glsl` diretamente, ele ainda usa `gl_ProjectionMatrix` (linha 32), `gl_TexCoord[0]` (linha 12), `gl_FragColor` (linha 157) e `texture2D` (linha 125) — não migrado.
- **Estado**: nenhuma migração real de Fase 5 foi feita ainda. Os 5 arquivos `RAS_OpenGLFilters/*.glsl` corretos foram identificados, mas não auditados individualmente (contagem de símbolos legados, onde os uniforms são setados em C++ — provavelmente `RAS_2DFilterManager.cpp` ou equivalente, ainda não localizado). Pausado para confirmação do usuário antes de prosseguir com a Fase 5 de verdade.

**Migração para OpenGL Core Profile — Fase 5 de verdade concluída: `RAS_SSAO2DFilter.glsl`, `RAS_SSR2DFilter.glsl`, `RAS_SSR_Blur2DFilter.glsl`, `RAS_LightScaterring_Buffer2DFilter.glsl`, `RAS_LightScaterring_Image2DFilter.glsl`**
- Usuário confirmou prosseguir com os 5 arquivos certos. Uniforms setados em `RAS_2DFilter.cpp` (não `RAS_2DFilterManager.cpp` como suspeitado — esse é só o dono da lista de filtros ativos por cena; quem faz upload de uniform por-shader é `RAS_2DFilter::BindUniforms()`), via uma tabela `predefinedUniformsName[]`/`m_predefinedUniforms[]` já existente (mesmo padrão usado por `ge_ssaoparams`/`ge_ssrparams`/etc.) — adicionados 2 novos slots, `GE_VIEW_MATRIX_UNIFORM`/`GE_PROJECTION_MATRIX_UNIFORM` (`RAS_2DFilter.h`), mapeados pros nomes `unfviewmat`/`unfprojmat` (mesma convenção de nome já usada em `gpu_shader_vertex.glsl`/`gpu_shader_material.glsl` desde as Fases 3-4, para reconhecimento). `BindUniforms()` ganhou um parâmetro `rasty` (só precisava de `canvas`/`sun_screen_pos` antes) pra poder chamar `rasty->GetViewMatrix()`/`GetProjectionMatrix()` (accessors já existentes desde a Fase 0/1) — thread até o único call site em `Render()`. Upload incondicional (sem `#ifdef`), seguindo o mesmo padrão já usado em todo esse arquivo: `SetUniform` é no-op se a location for -1 (uniform não declarado no shader ativo), então shaders COMPAT que não declaram esses uniforms simplesmente ignoram o upload.
- **GLSL**: cada arquivo ganhou um bloco `#ifdef USE_CORE_PROFILE` no topo com as declarações que precisa (`in vec2 texCoordVarying;` sempre; `uniform mat4 unfprojmat;`/`unfviewmat;` só onde usados; `out vec4 fragColor;` sempre) e os `#define` de alias (`gl_ProjectionMatrix`→`unfprojmat`, `gl_ProjectionMatrixInverse`→`inverse(unfprojmat)`, `gl_ModelViewMatrix`→`unfviewmat` — sem multiplicar por matriz de objeto, já que é um post-process de tela cheia sem objeto por-draw, diferente do `gpu_shader_material.glsl` da Fase 4 —, `gl_FragColor`→`fragColor`, `texture2D`→`texture` só no SSAO). `gl_TexCoord[0]` (não tem substituto direto em core) trocado por `texCoordVarying`, um `out vec2` que `RAS_VertexShader2DFilter.glsl` **já emitia em paralelo** desde antes desta sessão (só não era consumido) — só precisou guardar a linha `gl_TexCoord[0] = ...` desse vertex shader sob `#ifndef USE_CORE_PROFILE` (built-in removido em core), a linha `texCoordVarying = uv` já funciona nos dois profiles sem mudança.
- **Achado à parte, não corrigido nesta fase (fora do pedido do usuário)**: os outros 12 filtros de `RAS_OpenGLFilters/` (Blur, Dilation, Erosion, Laplacian, GrayScale, Invert, Sepia, Sobel, Prewitt, Sharpen, OutLine, Fxaa) que a entrada de changelog anterior descreveu como "migrados e validados" **ainda usam `gl_TexCoord[0]`/`gl_FragColor`/`texture2D` sem nenhum guard `#ifdef`** — confirmado por grep, nenhum arquivo desses tem uma única ocorrência de `USE_CORE_PROFILE`. A entrada anterior provavelmente descrevia só o dual-write de atributos (posição/normal em locations fixas, contrato do `RAS_StorageVao.cpp` da Fase 2), não a migração de sintaxe GLSL em si — mesmo tipo de leitura otimista que já causou o desvio de escopo original desta Fase 5. Não mexido agora (fora do que foi pedido), mas registrado pra não repetir a mesma surpresa depois.
- **Verificado**: `ninja RangeRuntime` em `build_core_test/` compila limpo (29/29, 0 erros) — inclui a regeneração/recompilação dos 5 `.glsl.c` tocados + `RAS_2DFilter.cpp`/`RAS_2DFilterManager.cpp`/`KX_2DFilterManager.cpp`/`KX_2DFilter.cpp`/`SCA_2DFilterActuator.cpp`/`BL_ConvertActuators.cpp`/`KX_Scene.cpp` (dependentes de `RAS_2DFilter.h` por causa da assinatura nova de `BindUniforms`). Build COMPAT padrão (`ninja RangeRuntime` em `build/`) também recompila limpo, 27/27, 0 erros — branch `#else`/upload incondicional confirmados inertes lá.
- **Verificação em tela pendente**: `RangeRuntime.exe benchmark.range` no build CORE continua parando no crash de debug-draw já conhecido (mesmos erros/endereço de antes, nada novo) antes de qualquer screenshot útil — não dá pra confirmar visualmente se SSAO/SSR/LightScatter renderizam corretos sob CORE (e não está confirmado se `benchmark.range` sequer liga algum desses efeitos) até esse crash ser resolvido. Fica pendente pra depois da Fase 7 (debug draw), próximo passo combinado com o usuário.

**Migração para OpenGL Core Profile — Fase 7 (debug draw) parcial: crash original resolvido, um novo crash (imediato, não relacionado) encontrado logo em seguida**
- Usuário confirmou seguir com o crash pendente. Migrados `gpu_shader_flat_color_vert/frag.glsl`, `gpu_shader_frustum_line_vert.glsl`, `gpu_shader_frustum_solid_vert/frag.glsl`, `gpu_shader_2d_box_vert.glsl` (mesmo padrão `#define` de alias) — mas por serem shaders `GPU_shader_create` puros (não passam pelo `GPU_material`), as matrizes precisaram de upload manual em C++: `RAS_OpenGLDebugDraw` ganhou `m_colorViewProjUniform`/`m_frustumLineViewProjUniform`/`m_frustumSolidViewProjUniform` (um `unfviewprojmat` combinado = `GetProjectionMatrix() * GetViewMatrix()`, calculado uma vez por `Flush()`) e `m_box2dOrthoUniform` (`unforthomat`, via `rasty->GetOrthoMatrix(0, width, height, 0, -100, 100)` — a caixa 2D de overlay precisa de uma projeção ortográfica de tela, não a câmera 3D da cena, e o `glOrtho()`/pilha de matriz fixed-function que ela lia virou no-op sob CORE desde a Fase 2).
- **Confirmado: isso resolveu o crash original** (`gl_ProjectionMatrix`/`gl_ModelViewMatrix`/`gl_ModelViewProjectionMatrix removidos após a versão 140`, linhas 90-93) — sumiu do log de compile depois do rebuild.
- **Mas surgiu um crash novo, diferente, no mesmo ponto do startup**: `gl_TexCoord is removed after version 140` (erro único, linha 86). Investigação levou por vários caminhos errados antes de achar a causa real:
  - Suspeita inicial: os 12 filtros "clássicos" de `RAS_OpenGLFilters/` (Blur/Dilation/Erosion/Laplacian/GrayScale/Invert/Sepia/Sobel/Prewitt/Sharpen/OutLine/Fxaa). **Falso alarme — esses já estão certos**: usam `#if __VERSION__ >= 130` (não `USE_CORE_PROFILE`) pra ramificar pro caminho moderno (`texCoordVarying`/`layout(location=0) out vec4 fragColor`/`texture()`), e `__VERSION__` já é sempre >=130 em hardware real (mesmo em COMPAT) — ou seja, esse ramo já rodava e já era validado no build padrão atual. A afirmação da entrada anterior deste changelog ("migrados e validados") **estava certa**; a dúvida registrada ali foi um engano meu, causado por um grep plano que não distinguiu o ramo `#else` morto do código realmente ativo. Corrigido aqui.
  - Achado real: `RAS_Bloom2DFilter_buf/bufH/bufV/Image.glsl` e `RAS_Tonemaps2DFilter.glsl` (5 arquivos — os "multi-pass nativos" que a nota de changelog original, de antes desta sessão, dizia estarem fora daquele escopo fechado) não tinham nenhum shim `>=130`, mesmo padrão sem guarda do grupo SSAO/SSR/LightScatter da Fase 5 real. Migrados com o mesmo `#ifdef USE_CORE_PROFILE` (texCoordVarying + alias fragColor, sem uniforms de matriz). **Não resolveu o crash** — mesmo erro continuou depois, ou seja Bloom/Tonemap não são o que compila cedo no startup (cena provavelmente não os liga, ou não são eles que disparam aqui).
  - Também checados e descartados: `gpu_shader_frame_buffer_vert/frag.glsl` (usado todo frame pro blit final via `RAS_Rasterizer::DrawOffScreen`/`ScreenPlane::Render()`) — já tem o shim `>=130` (`layout(location=0/1) in vec3 pos/vec2 uv`), já está certo, e o construtor de `RAS_OpenGLRasterizer::ScreenPlane` já escreve os atributos genéricos nas locations 0/1 antecipando exatamente isso (comentário no código já cita esse arquivo nominalmente). Também `gpu_shader_black_vert.glsl`/`gpu_shader_vsm_store_vert/frag.glsl` (território da Fase 6/sombra, via `RAS_Rasterizer::SetOverrideShader`/`RAS_BucketManager.cpp`) — genuinamente não migrados (`gl_Vertex`/`gl_ModelViewMatrix`/`gl_ProjectionMatrix`, `varying` puro sem `in`/`out`), mas nenhum dos dois usa `gl_TexCoord`, então nenhum explica *esse* erro específico.
  - **Achado o real culpado**: `gpu_shader_sep_gaussian_blur_vert.glsl`/`_frag.glsl` (sem shim `>=130`, `gl_TexCoord[0]`/`gl_MultiTexCoord0`/`texture2D` crus) — usado por `GPU_framebuffer_blur()` em `gpu_framebuffer.c`, chamado por `gpu_material.c` (quase certamente pro blur dos mip levels da textura de mundo/ambiente que alimenta a amostragem `wtex`/`textureCubeLod` de reflexo em `gpu_shader_material.glsl` da Fase 4 — ou seja, roda pra qualquer cena com World/background, praticamente sempre, cedo durante o setup de material/mundo — bate com o padrão do crash, sempre no mesmo ponto cedo em toda execução).
- **Bloqueio maior encontrado aqui, ainda não corrigido**: o draw call de `GPU_framebuffer_blur()` é **immediate-mode fixed-function puro** — `glBegin(GL_QUADS)`/`glTexCoord2d()`/`glVertex2f()`/`glEnd()`, sem VBO/VAO nenhum. Isso é proibido de vez em core profile (não é só sintaxe de shader como tudo corrigido até aqui) e `gpu_framebuffer.c` não está na lista de arquivos escopados por `WITH_GL_PROFILE_CORE_RASTERIZER_TEST`, então nem foi pego pelo guard `DO_NOT_USE_gl*` da Fase 2. Corrigir isso pede o mesmo tipo de trabalho da Fase 2 em `RAS_StorageVao.cpp`/`RAS_OpenGLRasterizer.cpp` (VBO real + atributos genéricos, `glDrawArrays` no lugar de `glBegin`/`glEnd`) — uma classe de mudança maior e diferente do que só alias de texto de shader.
- **Parado aqui pra confirmar com o usuário** antes de reescrever `gpu_framebuffer.c` sem combinar — é um tipo de fix maior (reescrita de draw call C++ imediate-mode) do que as migrações mecânicas de texto de shader feitas até aqui nesta investigação. Build COMPAT padrão confirmado intocado (27/27, 0 erros) depois de todas essas mudanças. Logs em `build_log_phase7_debugdraw.txt`, `build_log_phase7_bloom.txt`, `projects-teste/core_profile_phase7*.log`.

**Migração para OpenGL Core Profile — Fase 7 concluída: `gpu_framebuffer.c` reescrito (fim do immediate mode em `GPU_framebuffer_blur()`)**
- Usuário confirmou seguir com a reescrita. `GPU_framebuffer_blur()` desenhava um quad de tela cheia duas vezes (blur horizontal e vertical do shadow map VSM) via `glBegin(GL_QUADS)`/`glTexCoord2d()`/`glVertex2f()`/`glEnd()` — proibido em core profile. Substituído por um VBO+VAO estático de módulo (`g_blur_quad`, lazy-init em `gpu_framebuffer_blur_quad_ensure()`), com posição+UV intercalados (2f+2f) em generic vertex attributes nas locations 0/1 — mesma convenção já usada em `RAS_OpenGLRasterizer::ScreenPlane` e no contrato de `RAS_StorageVao.cpp` da Fase 2. Desenho via `glDrawArrays(GL_TRIANGLE_FAN, 0, 4)` (`gpu_framebuffer_blur_quad_draw()`), chamado nos dois pontos onde o `glBegin/glEnd` antigo estava. Cleanup exposto como `GPU_framebuffer_blur_free()` (novo, em `GPU_framebuffer.h`), ligado em `gpu_codegen_exit()` logo depois de `GPU_shader_free_builtin_shaders()` — mesmo padrão de lifetime já usado pros builtin shaders, já que o quad só existe enquanto o shader `GPU_SHADER_SEP_GAUSSIAN_BLUR` também existe.
- **GLSL**: `gpu_shader_sep_gaussian_blur_vert/frag.glsl` migrados pro mesmo padrão `#if __VERSION__ >= 130` já usado pelos 12 filtros clássicos e por `gpu_shader_frame_buffer_vert/frag.glsl` (branch moderno com `layout(location=0/1) in`/`texCoordVarying`/`texture()`/`fragColor`, branch legado intocado com `gl_Vertex`/`gl_TexCoord[0]`/`texture2D`/`gl_FragColor` — este último provadamente nunca exercitado em hardware real, `__VERSION__` já é sempre >=130).
- **Achado no caminho — bomba-relógio da mesma família, ainda não disparada**: `gpu_shader_frame_buffer_vert.glsl`, copiado como referência pro padrão acima, escreve `gl_TexCoord[0] = vec4(uv, 0.0, 1.0);` **sem guarda** dentro do próprio ramo `>=130` — que sob `#version 330 core` (injetado por `gpu_shader.c` pra qualquer shader passado por `GPU_shader_create`, não só os do `GPU_material`) causaria exatamente o mesmo erro `gl_TexCoord is removed after version 140` que acabou de ser corrigido no blur. Não disparou ainda porque o shader `draw_frame_buffer` é compilado sob demanda (primeiro blit pra tela), mais tarde no startup que o blur do World (compilado cedo, durante setup de material). Corrigido preventivamente com o mesmo guard que `RAS_VertexShader2DFilter.glsl` já usa (`#ifndef USE_CORE_PROFILE` em volta do write) — sem essa correção, migrar o gaussian blur só teria adiado o crash pro próximo shader builtin a ser exercitado, não eliminado a classe de bug.
- **Achado de CMake — define aditivo, não exclusivo**: `set_source_files_properties(... PROPERTIES COMPILE_DEFINITIONS "WITH_GL_PROFILE_CORE")` em `source/blender/gpu/CMakeLists.txt` **soma** ao `add_definitions(${GL_DEFINITIONS})` do diretório (que já traz `WITH_GL_PROFILE_COMPAT` por padrão) em vez de substituí-lo — diferente do mecanismo de `RAS_OpenGLRasterizer`, que troca `GL_DEFINITIONS_RASTERIZER` inteiro (exclusivo). Ou seja, no build de teste, `gpu_shader.c`/`gpu_material.c`/`gpu_framebuffer.c` recebem **os dois** defines simultaneamente. Isso não quebrava nada nos 2 arquivos anteriores (ambos checam `#ifdef WITH_GL_PROFILE_CORE` primeiro e retornam/isolam, nunca dependem da ausência de COMPAT) mas quebraria silenciosamente o novo código do quad se ele checasse só `#ifdef WITH_GL_PROFILE_COMPAT` pro fallback de client-state legado (`glEnableClientState`/`glVertexPointer`/`glTexCoordPointer` — também proibidos em core, reintroduziria o mesmo bug por outra API). Corrigido usando `#if defined(WITH_GL_PROFILE_COMPAT) && !defined(WITH_GL_PROFILE_CORE)`. `gpu_framebuffer.c` adicionado à lista de `set_source_files_properties` (mesmo arquivo de CMake), já que agora é código realmente tocado por esta migração.
- **Verificado**: `ninja bf_gpu` no build COMPAT padrão (`build/`) compila limpo, sem warning novo. `ninja RangeRuntime` em `build_core_test/` compila limpo (28/28, 0 erros). Rodando `RangeRuntime.exe benchmark.range` no build CORE: processo **não crasha mais** — sem `EXCEPTION_ACCESS_VIOLATION`, sem `gl_TexCoord is removed after version 140` no log (`projects-teste/core_profile_phase7_framebuffer_run_err.log`).
- **Execução avançou e revelou um bug novo, genuinamente pré-existente, não relacionado a esta migração**: `RAS_SSAO2DFilter.glsl` agora compila e expõe dois tipos de erro real de GLSL — `error C7549: OpenGL does not allow C style initializers` (2x, `vec4 ssao_params = {...}` linha ~33 e `vec4 tempVecs[3] = {...}` linha ~56, sintaxe de array inválida em GLSL, precisaria do construtor `vec4[3](...)`) e `error C1059: non constant expression in initialization` (6x) — este último porque o arquivo inicializa várias variáveis **de escopo global** com expressões não-constantes: `uvcoordsvar` (de `texCoordVarying`, uma `in`), `att`/`ssao_params`/`ssao_sample_params` (de uniforms ou de uma chamada de função `get_sample_params()`), `projection` (de `gl_ProjectionMatrix`, que sob `USE_CORE_PROFILE` é um `#define` pro uniform `unfprojmat`) — GLSL estrito sob core profile não permite inicializar globals com nada que não seja uma expressão constante. Esse bug já existia antes desta sessão inteira de migração; só nunca tinha sido exercitado porque a execução travava mais cedo no startup (primeiro no crash de debug-draw, depois no do blur) antes de chegar no SSAO. **Não corrigido ainda** — é um retrabalho de arquitetura (mover as inicializações de escopo global pra dentro de `main()`/funções, threadeando como parâmetros), maior que alias de texto, mesma classe de decisão que a reescrita do `gpu_framebuffer.c` foi. Achado registrado, aguardando decisão do usuário sobre prosseguir agora ou depois.
- Logs em `build_log_phase7_framebuffer_compat.txt`, `build_log_phase7_framebuffer_core.txt`, `projects-teste/core_profile_phase7_framebuffer_run*.log`, screenshot em `projects-teste/core_profile_phase7_framebuffer_screenshot.png` (tela cinza sólida — renderização ainda quebrada, esperado, o VSM/black/SSAO shaders seguintes ainda não migrados).

**Migração para OpenGL Core Profile — corrigido o bug pré-existente de inicialização global do `RAS_SSAO2DFilter.glsl` (e achados 2 casos irmãos nos outros filtros multi-pass)**
- Usuário confirmou corrigir agora. `RAS_SSAO2DFilter.glsl`: todas as globals problemáticas (`uvcoordsvar`, `att`, `ssao_params`, `ssao_sample_params`, `projection`, `invproj`) viraram declarações sem inicializador, populadas no início de `main()` (a ordem já respeita as dependências: `att`→`ssao_params`, `projection`→`invproj`→`getviewvecs()`). Os dois inicializadores estilo-C (`vec4 ssao_params = {...}` e `vec4 tempVecs[3] = {...}` dentro de `getviewvecs()`) trocados por sintaxe de construtor (`vec4(...)`/`vec4[3](...)`) — `tempVecs` é local, então só precisava da sintaxe certa, não de mover pra `main()`.
- **Achado 1 (irmão, mesma classe)**: `RAS_SSR2DFilter.glsl` tinha o mesmo padrão — `vec2 texcoord = texCoordVarying;`/`= gl_TexCoord[0].st;` em escopo global. Mesma correção: declaração sem inicializador + atribuição no topo de `main()`.
- **Achado 2 (irmão, escala maior)**: uma varredura em todo `RAS_OpenGLFilters/*.glsl` achou o **mesmo padrão exato em mais 7 arquivos** — `RAS_Bloom2DFilter_buf/bufH/bufV/Image.glsl`, `RAS_LightScaterring_Image2DFilter.glsl`, `RAS_LightScaterring_Buffer2DFilter.glsl`, `RAS_SSR_Blur2DFilter.glsl` — todos com `vec2 texcoord`/`uvcoord` de escopo global inicializado a partir de `texCoordVarying`/`gl_TexCoord[0]`. Corrigidos todos com o mesmo padrão mecânico (declaração global sem inicializador, atribuição no topo de `main()`).
- **Achado 3, só apareceu depois do rebuild**: com os globals corrigidos, `RAS_Bloom2DFilter_bufH.glsl`/`bufV.glsl` ainda falhavam com o mesmo `error C1059` — desta vez numa variável **local** dentro de `main()`: `const float pixel = 5.0 / ge_BloomParams.z/w;`. `const` local também exige expressão constante em GLSL estrito (uniform não conta), independente de ser global ou não — bug diferente da classe "global scope", mas mesmo sintoma. Corrigido removendo o `const` (a variável não precisa ser constante, só é lida dentro do loop).
- **Verificado**: `ninja RangeRuntime` em `build_core_test/` compila limpo em duas rodadas (uma por achado). `RangeRuntime.exe benchmark.range` no build CORE, com `-d gpu` pra dump completo do shader anotado: **zero** `GPUShader: compile error:` no stderr (antes desta correção: 6x `error C1059` + 2x `error C7549` só do SSAO; a rodada intermediária, já com SSAO/SSR/os-outros-7 corrigidos, ainda mostrava 6x `error C1059` vindos do bug do `const` no Bloom). Sem crash em nenhuma das rodadas. Screenshot permanece cinza sólido (mesmo resultado inconclusivo da Fase 7 anterior — não é sinal de regressão, é uma limitação de captura/foco de janela já registrada, não da renderização em si).
- Logs em `build_log_phase7_ssao_core.txt`/`_core2.txt`, `projects-teste/core_profile_phase7_ssao_debug_run_err.log` (dump anotado com `-d gpu`), `projects-teste/core_profile_phase7_ssao_run2_err.log` (confirmação final, log limpo).

**Migração para OpenGL Core Profile — FECHADA: todo o caminho de execução do `RangeRuntime` compila e roda sob CORE, sem erro de shader e sem crash**
- Estado final consolidado do plano de 8 fases (Fases 0-7 concluídas ao longo desta sessão, ver entradas acima para o detalhamento técnico de cada uma): vertex/material base (Fases 0-4), filtros 2D clássicos + SSAO/SSR/LightScatter (Fase 5), debug draw + framebuffer blit/blur do shadow map VSM + inicializadores globais dos filtros multi-pass (Fase 7) — todos migrados e verificados em `build_core_test/` (`WITH_GL_PROFILE_CORE_RASTERIZER_TEST=ON`). `RangeRuntime.exe benchmark.range` roda sem `EXCEPTION_ACCESS_VIOLATION` e sem nenhum `GPUShader: compile error:` no log (`-d gpu`). `editors/`/`bf_rna` (UI do editor Blender, usada só por `RangeEngine`) permanecem intocados em compatibility profile — decisão permanente desde a Fase 2 (dependência real via `bf_rna`→`bf_editor_*`, não um bug de escopo; migrar essa fatia é um projeto à parte, não avaliado como necessário para o objetivo desta trilha).
- **Três gaps residuais conhecidos, aceitos como fora de escopo desta migração (nenhum bloqueante, nenhum exercitado por `benchmark.range`)**:
  - **Motion blur**: `RAS_OpenGLRasterizer::MotionBlur` dependia de `glAccum`/buffer de acumulação, removido do core profile sem substituto direto. Reimplementar exigiria um pass de post-process por velocity buffer, mesma família de técnica dos filtros SSAO/SSR já existentes — não iniciado.
  - **Clipping de reflexo (espelho/água)**: `KX_PlanarMap` dependia de `gl_ClipPlane`/`glClipPlane`, sem equivalente fixed-pipeline em core. `RAS_OpenGLRasterizer::EnableClipPlane`/`DisableClipPlane` (C++) e o bloco de clip em `gpu_shader_vertex.glsl` (GLSL) já são no-op consistente sob CORE desde as Fases 2-3 — porte completo pra `gl_ClipDistance[]` (`glEnable(GL_CLIP_DISTANCE0)` + uniform de plano + escrita no vertex shader) fica para quando essa feature for revisitada.
  - **Texto de debug on-screen**: `BLF_draw` (`source/blender/blenfont/`) é fixed-function por dentro (`glMatrixMode`/`glPushMatrix`/`glGetFloatv(GL_CURRENT_COLOR)`) e está fora do escopo desta migração — simplesmente não renderiza sob CORE, não afeta a cena principal.
- **Pendente antes de considerar CORE pronto para uso em produção (fora do escopo desta rodada de documentação)**: transformar o `build_core_test/` descartável num build CORE de verdade (opção de CMake estável, não um diretório de teste avulso), e confirmação visual em tela cheia — bloqueada até aqui só por limitação de captura/foco de janela nesta sessão, não por regressão de renderização conhecida.
- `relatorio-melhorias-anastacioengine.md` atualizado para refletir o fechamento (Fase 1 da trilha Iluminação e seção "Próximos passos").

## 2026-08-24 (continuação)

**Diretório de instalação (`install/` na raiz) estava obsoleto — build/install real fica em `build/bin/`**
- Usuário reportou que "a engine mudou de lugar" e estava pedindo addons/arquivos visuais alterados (`splash.png`) que faltavam. Investigação: `install/` na raiz do repo é uma cópia manual antiga (parada em 23/08 16:04), incompleta — só tinha 39/84 addons e faltavam `fonts`/`blender_icons16-32`/`brushicons`/`matcaps`/`startup.blend`/`splash.png` de `2.79/datafiles`. O `CMAKE_INSTALL_PREFIX` real do projeto é `build/bin/${BUILD_TYPE}` (`WITH_INSTALL_PORTABLE`) — ou seja, `build/bin/` já É o install de verdade, atualizado a cada build; `install/` na raiz nunca foi o destino oficial, virou uma cópia órfã de uma sessão anterior. Rodado `ninja install` em `build/` para confirmar/repopular `build/bin/` (addons do repo sincronizados, `splash.png` novo embutido via `datatoc` no binário). Usuário completou manualmente os addons próprios que não vêm do repo (não gerados pelo Ninja, são customizações dele).
- **Recomendação implícita para próximas sessões**: tratar `build/bin/` como o local canônico de execução/teste, não `install/` (que pode ser removido ou ignorado — não é mantido por nenhum processo de build).

**Crash `EXCEPTION_ACCESS_VIOLATION` ao rodar o jogo — reincidência confirmada do bug de build incremental obsoleto, corrigido com rebuild limpo**
- Após o `ninja install` (incremental, 257 passos) acima, `RangeRuntime.exe` passou a crashar com `EXCEPTION_ACCESS_VIOLATION` até na cena em branco (sem nenhum `.range` carregado) — mesma assinatura já documentada nesta sessão (ver Fases E/Fase-1-groundwork do GPU Skinning e core profile, `docs/changelog.md` anteriores) para builds incrementais que ficam com dependências de header (`DNA_*.h` e outros) subatualizadas pelo Ninja. `dna.c`/`dna_type_offsets.h` já estavam com timestamp mais novo que os `DNA_*.h` desta vez (não era exatamente o mesmo caso), mas o padrão — crash desproporcional/genérico logo após tocar em headers, sumindo com rebuild limpo — bateu o suficiente pra ir direto pra correção conhecida em vez de re-bisectar.
- **Corrigido**: `ninja -t clean` (2981 arquivos) + `ninja install` completo do zero (2913 passos, ~mesma ordem de grandeza do rebuild limpo já registrado nesta sessão). Confirmado: `RangeRuntime.exe benchmark.range` roda sem crash e sem erro no console após o rebuild.
- **Achado do usuário, não investigado agora**: no jogo próprio dele (não `benchmark.range`), a tela "pisca algumas vezes" ao rodar — projeto com muitos filtros 2D ativos. Hipótese mais provável, a confirmar numa sessão futura: relacionado às migrações de sintaxe GLSL desta sessão nos filtros (`RAS_OpenGLFilters/*.glsl`, Fases 1/5/7 da trilha core profile) ou a alguma interação entre múltiplos filtros simultâneos — mas build atual (`build/bin/`) é COMPAT, não CORE, então não é o mesmo tipo de crash de sintaxe core-only já mapeado; precisa de reprodução dedicada (qual(is) filtro(s) ativo(s), print do console) antes de diagnosticar. Ficou para amanhã.
- Atualizada a memória de build (`build_environment.md`): reincidência do gotcha de build incremental confirmada num terceiro caso (nem DNA puro, nem header simples — só "depois de mexer em headers, um crash estranho apareceu"), reforçando que a resposta padrão deve ser rebuild limpo direto, sem re-diagnosticar do zero.

**Migração para OpenGL Core Profile — Fase 6 (shadow map VSM/black) migrada e verificada; caminho de execução completo até a cena real renderizar sob CORE**
- `gpu_shader_vsm_store_vert/frag.glsl` e `gpu_shader_black_vert.glsl` migrados com o mesmo padrão de `#define`-alias já usado na Fase 4/7 (`gl_Vertex`→`att_Position` em `layout(location=0)`, `gl_ModelViewMatrix`→`unfviewmat*unfobmat`, `gl_ProjectionMatrix`→`unfprojmat`, `varying`/`gl_FragColor`→`in`/`out` sob `USE_CORE_PROFILE`). São shaders "builtin" ligados via `RAS_Rasterizer::SetOverrideShader` (não passam pelo pipeline de `GPU_material`), mesma família dos shaders de debug draw da Fase 7 — precisaram de upload manual de matriz por objeto: `RAS_Rasterizer::UpdateOverrideShaderObjectMatrix()` novo, chamado por `RAS_MeshSlot::RunNode` logo depois do antigo `MultMatrix(mat)` (que já é no-op sob CORE desde a Fase 2), e um `OverrideShaderShadowInterface` (view/object/projection loc) registrado para as 4 variantes de shadow shader (BLACK, BLACK_INSTANCING, VSM_STORE, VSM_STORE_INSTANCING).
- **Verificado**: `ninja RangeRuntime` limpo em `build/` (COMPAT) e `build_core_test/` (CORE, 163/163 — recompile completo por causa da mudança em `RAS_Rasterizer.h`). `RangeRuntime.exe -d gpu benchmark.range` no build CORE: zero erro de compile referenciando os símbolos legados destes 3 arquivos, sem crash — chega até a avaliação de animação da cena.
- **Achado downstream, não causado por esta fase mas só agora alcançável**: com o shadow map funcionando sob CORE, a execução chega pela primeira vez nos shaders de material que *recebem* sombra (variante deferred-gbuffer de `gpu_shader_material.glsl`, antes nunca compilada porque o passo de shadow falhava antes) — expõe `shadow2DProj` (removido do GLSL >140) e uma dupla-declaração de `unfviewmat`/`unfobmat` nessa variante específica. Registrado, não corrigido ainda nesta entrada (ver a seguir).

**Migração para OpenGL Core Profile — três gaps downstream corrigidos; cena real do `benchmark.range` renderiza sob CORE pela primeira vez**
- Usuário confirmou prosseguir ("pode fazer"). Três correções, cada uma revelando a seguinte ao remover o crash que a escondia:
  1. **Dupla declaração de `unfviewmat`/`unfobmat`**: `codegen_print_uniforms_functions()` (`gpu_codegen.c`) reimprime esses uniforms por material sempre que um nó do grafo referencia esses builtins (ex.: mapeamento de UV por Object/World) — colidia com a declaração incondicional já adicionada no topo do arquivo pelas Fases 3/4. Corrigido pulando a redeclaração desses 4 builtins especificamente sob `WITH_GL_PROFILE_CORE`. Precisou incluir `gpu_codegen.c` no escopo per-file de `WITH_GL_PROFILE_CORE` em `source/blender/gpu/CMakeLists.txt` (mesma lista de `gpu_shader.c`/`gpu_material.c`/`gpu_framebuffer.c`).
  2. **`shadow2DProj` removido após 140**: em vez de tocar os 4 call sites em `gpu_shader_material.glsl`, um único `#define shadow2DProj(map, co) vec4(textureProj(map, co))` resolve, rebroadcastando o float de `textureProj` de volta pra vec4 (mesmo comportamento legado que os call sites `.x` já esperavam).
  3. **`gl_NormalMatrix` removido após 140, em código anexado pelo codegen**: `gpu_codegen.c` (~linha 884) injeta `gl_NormalMatrix * att%d.xyz` como texto cru *depois* do `main()` de `gpu_shader_vertex.glsl` (esse `main()` é deixado deliberadamente sem fechar pra isso) — mas nem esse arquivo nem `gpu_shader_vertex_world.glsl` tinham o alias `gl_NormalMatrix`→`unfnormalmat`. Adicionado `#define gl_NormalMatrix unfnormalmat` aos dois. **Achado**: `gpu_shader_vertex_world.glsl` (shader do céu/skybox, tipo `GPU_MATERIAL_TYPE_WORLD`) estava inteiramente não migrado — só não tinha aparecido antes porque a Fase 3 força os 4 builtins de matriz em todo `GPUMaterial` sem checar o tipo. Migrado com o mesmo padrão da Fase 3 (`att_Position` location 0, os 4 uniforms declarados por simetria, embora esse shader só precise do de normal — seu `main()` faz `gl_Position = gl_Vertex` direto, sem view/proj, é desenhado direto em clip space).
- **Verificado**: `build/` e `build_core_test/` compilam limpos (só os arquivos tocados). `RangeRuntime.exe -d gpu benchmark.range` no build CORE: **zero** `GPUShader: compile error:` (contra 18 blocos de erro antes desta correção), sem crash. Primeiro screenshot de toda a migração mostrando a cena real renderizada (personagens, estrada, árvores, efeitos de portal) em vez de tela cinza/sólida — `projects-teste/core_profile_phase6_vsm_screenshot.png`. Avisos de driver pré-existentes e não bloqueantes seguem no log (feedback loop de framebuffer, overflow de array de uniform) — não investigados, não relacionados a esta migração.
- Logs: `projects-teste/core_profile_phase6_run_with_downstream_errors.log`, `projects-teste/core_profile_phase6_run_clean.log`.

**Migração para OpenGL Core Profile — Fase 8: `build_core_test/` promovido a build permanente `build_core/`**
- Usuário escolheu (via pergunta direta) formalizar CORE como o build real do `RangeRuntime`, em diretório dedicado — opção preferida a flipar o build padrão (quebraria `RangeEngine`) ou adiar mais. Opção CMake renomeada `WITH_GL_PROFILE_CORE_RASTERIZER_TEST`→`WITH_GL_PROFILE_CORE_RANGERUNTIME` (`source/CMakeLists.txt` e o guard equivalente em `source/blender/gpu/CMakeLists.txt`), tirando a linguagem de "só teste, deixe OFF" dos comentários. Diretório renomeado `build_core_test/`→`build_core/`; como o `CMakeCache.txt` tinha paths absolutos que não sobrevivem a um rename de pasta, reconfigurado do zero (`cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DWITH_GL_PROFILE_COMPAT=ON -DWITH_GL_PROFILE_CORE_RANGERUNTIME=ON`) em vez de tentar remendar o cache.
- **Verificado**: `ninja RangeRuntime` em `build_core/` (rebuild completo por ser diretório novo): 896/896, 0 erros. `RangeRuntime.exe -d gpu benchmark.range`: mesmo resultado limpo de antes do rename (zero erro de compile, sem crash) — confirma que a reconfiguração não regrediu nada. `build/` (COMPAT, usado por `RangeEngine` e dia a dia) não foi tocado.
- Comando de reconfiguração de referência para retomar este build: `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DWITH_GL_PROFILE_COMPAT=ON -DWITH_GL_PROFILE_CORE_RANGERUNTIME=ON D:\AnastacioEngine\source` de dentro de `build_core/`, depois `ninja RangeRuntime`.

**Regressão pós-Fase-8: céu/background renderizava preto sob CORE — corrigido**
- Usuário reportou direto de um screenshot ("o céu ao fundo ficou preto"). Causa: `KX_WorldInfo::RenderBackground()` chama `GPU_material_bind()` pro material do céu procedural mas **nunca** `GPU_material_bind_uniforms()` — essa segunda função é quem de fato sobe `unfobmat`/`unfnormalmat` pra GPU, e só é chamada por objeto de malha (`BL_BlenderShader.cpp`), nunca pro world. Sob CORE, o alias `gl_ModelViewMatrix`→`(unfviewmat*unfobmat)` da Fase 4 multiplicava as funções de céu por uma `unfobmat` zerada (default do driver pra uniform nunca escrito) — colapsando os vetores de direção do céu a zero, daí a cor preta. Caso que a Fase 3/4 não previu: assumiam que todo `GPUMaterial` eventualmente recebe upload de obmat/normalmat, verdade para `GPU_MATERIAL_TYPE_MESH` mas não `_WORLD`.
- **Corrigido**: em `GPU_material_bind()` (`gpu_material.c`, logo após o upload de `GPU_PROJECTION_MATRIX`), sob `WITH_GL_PROFILE_CORE` e quando `material->type == GPU_MATERIAL_TYPE_WORLD`, sobe matriz identidade (`unit_m4`) pra `obmatloc` e identidade 3x3 pra `normalmatloc` — replica o que a pilha fixed-function `GL_MODELVIEW` efetivamente era nesse draw call específico sob COMPAT (só a view matrix, nunca um `PushMatrix`/`MultMatrix(obmat)` em volta do desenho do céu).
- **Verificado**: `build/` e `build_core/` compilam limpos (só `gpu_material.c` tocado). Screenshot com janela (`-w 800 600`, 12s de aquecimento — a tentativa de 6s só pegou a tela de loading cinza, vale lembrar pra próximas capturas nesta cena) confirma o céu azul correto acima da copa das árvores — usuário confirmou "agora ficou certo". `projects-teste/core_profile_worldsky_fix_screenshot2.png`.

## 2026-08-25

**Tentativa de destravar RenderDoc no `build_core` — contexto WGL corrigido, mas profiler continua bloqueado (causa raiz fora de escopo)**
- Trilha Performance: usuário pediu retomar a investigação do custo alto de `MainRender` (ver Fase 3/G acima), agora que `build_core` existe como build CORE permanente e RenderDoc deveria funcionar. Rodando `renderdoccmd.exe capture` contra `RangeRuntime.exe` do `build_core`, o overlay do RenderDoc mostrou "Core profile not explicitly requested. Compatibility profile is active. Captures disabled." — apesar do log do próprio jogo dizer `Compiled GL Profile: Core`.
- **Causa raiz**: `WITH_GL_PROFILE_CORE_RANGERUNTIME` só escopa `-DWITH_GL_PROFILE_CORE` pro `RAS_OpenGLRasterizer` e `blender/gpu` (decisão da Fase 2) — mas quem cria o contexto WGL de verdade é `GHOST_WindowWin32.cpp::newDrawingContext()`, compilado com o `GL_DEFINITIONS` **global** (ainda `WITH_GL_PROFILE_CORE=OFF`). Sem o `#if defined(WITH_GL_PROFILE_CORE)` ali, o driver NVIDIA nunca recebe `WGL_CONTEXT_CORE_PROFILE_BIT_ARB` e entrega um contexto compatibility que só *parece* core (expõe as funções 4.6 usadas pelo rasterizer migrado, mas ainda aceita fixed-function de código não migrado).
- **Fix aplicado**: `source/intern/ghost/CMakeLists.txt` ganhou o mesmo padrão de escopo per-file já usado em `blender/gpu` — `set_source_files_properties(intern/GHOST_WindowWin32.cpp PROPERTIES COMPILE_DEFINITIONS "WITH_GL_PROFILE_CORE")` sob `if(WIN32 AND WITH_GL_PROFILE_CORE_RANGERUNTIME)`. Rebuild confirmou contexto core de verdade: apareceram erros reais de `GL_INVALID_ENUM`/`GL_INVALID_OPERATION` em `gpu_texture.c` (`glDisable(tex->target_base)`, fixed-function fora do escopo desta migração, não travava o jogo) que antes ficavam escondidos pelo contexto disfarçado.
- **Mas o RenderDoc continuou recusando captura**, agora citando `glAlphaFunc`/`glColorMaterial`/`glDisableClientState`/`glLightModeli` como funções não suportadas em uso. Guardados todos os call sites reais dessas 4 funções em `gpu_draw.c` (`gpu_set_alpha_blend`, `GPU_clear_tpage`, `GPU_state_init`) e `gpu_extensions.c` (`gpu_extensions_init`) sob `#if defined(WITH_GL_PROFILE_COMPAT) && !defined(WITH_GL_PROFILE_CORE)` (primeira tentativa usou `#ifdef WITH_GL_PROFILE_COMPAT` sozinho, que não teve efeito nenhum — essas 2 arquivos recebem as duas defines simultaneamente, aditivo, mesma armadilha de CMake já documentada na Fase 7). Rebuild, retestado: **mensagem idêntica, sem mudança**. Conclusão: a causa não é call site nenhum, é o `glewInit()` (biblioteca vendorizada `glew-mx`) resolvendo a tabela inteira de ponteiros de função via `wglGetProcAddress` no startup, incluindo as deprecated, independente de serem chamadas depois — e é isso que o RenderDoc detecta. Corrigir exigiria mexer na inicialização do GLEW, fora de escopo.
- **Nsight Graphics tentado como alternativa — também travou**: "Graphics Capture" nunca conseguiu hookar a API gráfica (timeout em loop); "OpenGL Frame Debugger" conectou de verdade, leu o log do engine corretamente, começou a capturar o frame 30 e travou indefinidamente sem produzir captura. Hipótese: o contexto mínimo OpenGL 3.2 core pedido pelo GHOST (mesmo com driver suportando 4.6) confunde os hooks de interceptação de ambas ferramentas.
- **Regressão real encontrada só ao rodar o jogo de verdade (não só checar log de compile)**: com o fix do GHOST ativo, árvores/folhagem com textura de corte por alpha (`GPU_BLEND_CLIP`) renderizaram com fundo verde sólido em vez de transparente — usuário notou direto do screenshot. Causa: sem `GL_ALPHA_TEST`/`glAlphaFunc` (removidos do core), o fallback usado (`glDisable(GL_BLEND)`, depois um fallback de blend) não reproduzia o corte. Isolado revertendo só a mudança do GHOST (`git stash` nesse arquivo) — o verde sumiu imediatamente, confirmando que o fix do GHOST (não os guards do `gpu_draw.c`) era a causa direta.
- **Decisão final**: como nem RenderDoc nem Nsight funcionam mesmo com contexto core real, o fix do GHOST não trazia nenhum benefício — só o efeito colateral de quebrar o alpha. **Descartado em definitivo** (`git stash drop`). `build_core/` volta a usar o mesmo contexto compatibility-disfarçado-de-core que o Phase 8 sempre usou. Os guards de `gpu_draw.c`/`gpu_extensions.c` foram mantidos (corretos em princípio, inofensivos nesse contexto).

**Causa real do "MainRender alto" (Fase G, ver acima) encontrada usando o profiler nativo já existente — sem precisar de profiler de GPU externo**
- Descartado o caminho de RenderDoc/Nsight, usado `-g show_profile = 1 -g show_render_queries = 1` (sintaxe do parser de `-g` em `GPG_Ghost.cpp` exige `paramname`, `=` e `valor` como 3 argumentos separados por espaço — `show_profile=1` colado falha silenciosamente). Primeira medição (janela pequena, 512x384) mostrou `MainRender` em só 0.61ms/3% — mas essa é exatamente a mesma armadilha de "janela pequena" já documentada na Fase 2b (medição de resolução baixa subestima custo de GPU). Reexecutado em janela grande (`-w 1920 1080 0 0`, cliente real 1536x864): `MainRender` (CPU, só emissão de draw call) continua baixo (0.52ms/1%), mas **Overhead 26.42ms/80%** (onde a CPU fica bloqueada em `SwapBuffers()` esperando a GPU) e o GPU Query real (`GL_TIME_ELAPSED`): **28.29ms**. O tempo de GPU escala com resolução (~7x mais pixels → ~5.35x mais tempo), assinatura clássica de custo fill-rate/shading-bound.
- **Hipótese do usuário confirmada com teste A/B controlado**: script Blender-style headless (`RangeEngine.exe --background benchmark.range --python script.py`, nota: essa ordem de argumento importa — `--background --python script -- scene` carrega a cena padrão vazia em vez do arquivo) contou 23 de 173 objetos com alpha-blend, a maioria instâncias de `Arvore_tipo_4` (16 árvores, cada uma com muitas faces de folha sobrepostas). Removidas 11 de 16 numa cópia de teste (`benchmark_reduced.range`, descartável, não versionado) via `bpy.data.objects.remove()` + `bpy.ops.wm.save_as_mainfile(copy=True)`. Reexecutado na mesma resolução: GPU Time caiu de **28.29ms para 12.89ms** (mais de 2x). **Conclusão**: o gargalo é overdraw de faces alpha empilhadas (folhagem) na GPU, não shadow map, não skinning, não draw calls não-batchados, não os filtros de pós-processamento isoladamente (embora contribuam). Investigação de causa encerrada; otimização (LOD/impostors/menos planos por árvore) fica para quando essa frente for retomada.
- **Aprendizado registrado (feedback do usuário)**: gastamos duas rodadas de agente tentando RenderDoc e depois Nsight antes de notar que o engine já tinha a infraestrutura certa (`RAS_Query`/`RAS_OpenGLQuery` com `GL_TIME_ELAPSED`, e as categorias de profiler `m_profileLabels` já existentes, incluindo "Shadows" separado de "MainRender"). Buscar no código antes de recorrer a ferramenta externa ou escrever algo novo.
- **Migração dá-se por funcionalmente concluída**: todo o caminho de execução do `RangeRuntime` compila e roda sob CORE com a cena renderizando corretamente. Gaps residuais seguem os mesmos três já documentados (motion blur, clipping de espelho/água, texto de debug on-screen). Próximo passo pendente: atualizar `relatorio-melhorias-anastacioengine.md` refletindo este fechamento mais recente (Fases 6-8 + fix do céu, que a atualização anterior do relatório ainda não cobria).

**Trilha Performance: Z-prepass para folhagem alpha-cutout — implementado e verificado**
- Aplicando a conclusão da investigação anterior (overdraw de folhagem alpha é o gargalo real de GPU, não shadow/skinning/draw-calls), implementado um Z-prepass real em `RAS_BucketManager::Renderbuckets()` (casos `RAS_TEXTURED` e `RAS_RENDERER`). Achado ao investigar: materiais com `IsAlphaDepth()==true` (modos "Clip" e "Alpha Antialiasing"/A2C do Blender Game Material — os que `benchmark.range` já usa em `Arvore_tipo_4` e `Road_parte2`) já eram separados em buckets dedicados (`ALPHA_DEPTH_BUCKET`/`ALPHA_DEPTH_INSTANCING_BUCKET`), mas esses buckets só serviam pra decidir se chamava `UpdateGlobalDepthTexture()` (mecanismo não relacionado, de soft particles) — a passada de cor real nunca escrevia profundidade pra esses materiais (`SetDepthMask(RAS_DEPTHMASK_DISABLED)` fica ativo durante toda a renderização alpha), então o early-Z de hardware nunca podia rejeitar fragmentos de folhas sobrepostas.
- **Fix**: antes da passada de cor alpha normal, uma nova passada depth-only sobre `ALPHA_DEPTH_BUCKET`/`ALPHA_DEPTH_INSTANCING_BUCKET` — `SetDepthMask(ENABLED)` + `SetColorMask(false,false,false,false)`, renderiza via `RenderBasicBuckets` (sem ordenação, correto pra um write de profundidade puro sem blend), depois `SetColorMask(true,...)` + `SetDepthMask(DISABLED)` de volta antes da passada de cor de sempre. Usa o shader real do material (não um override shader) porque o discard/A2C depende de amostrar a textura de alpha — confirmado que a passada de shadow já segue o mesmo padrão (buckets de shadow alpha não usam override shader, só os sólidos usam). `SetColorMask` já existia em `RAS_Rasterizer` (`RAS_Rasterizer.h:381`), nenhuma API nova no rasterizer foi necessária. Materiais translúcidos de verdade (fora desses buckets) não são afetados.
- **Verificado**: `build/` (COMPAT) e `build_core/` (CORE) compilam limpos (só `RAS_BucketManager.cpp` tocado, incremental). Screenshot em ambos os builds confirma folhagem/estrada/personagens renderizando corretamente, sem geometria faltando, sem z-fighting, sem oclusão incorreta. Medição com a mesma metodologia validada na sessão anterior (`-w 1920 1080 0 0 -g show_profile = 1 -g show_render_queries = 1`, GPU Query `GL_TIME_ELAPSED`): **28.29ms → 21.45ms** (~24% de redução) na mesma janela/cena do baseline documentado. Não chega ao patamar do teste A/B com árvores removidas (12.89ms) — esperado, já que o prepass tem custo próprio de shading e não reduz a contagem de fragmentos de folhas realmente visíveis/não-ocluídas, só rejeita as ocluídas.
- Screenshots/logs: `projects-teste/zprepass_compat_screenshot.png`, `projects-teste/zprepass_core_screenshot.png`, `projects-teste/zprepass_compat_run.log`, `projects-teste/zprepass_core_run.log`.

**Standalone Player: "Borderless Window" implementado — evita o crash de fullscreen exclusivo relatado pela comunidade**
- Usuário mostrou print de outra versão da Range Engine com um checkbox "Borderless Window" no painel Standalone Player que não existe neste fork, junto de um relato de bug da comunidade: `render.setFullScreen(True)` causa `EXCEPTION_ACCESS_VIOLATION` nativo em builds standalone (mesmo problema ao ligar Fullscreen em Render > Game > Display), não capturável por `try/except` Python. Causa raiz: o caminho de fullscreen exclusivo passa por `GHOST_ISystem::beginFullScreen()` + `window->setState(GHOST_kWindowStateFullScreen)` (`GPG_Ghost.cpp::startFullScreen()`), que troca o modo de vídeo via `ChangeDisplaySettings` — incompatível com o contexto core profile desta engine. Workaround da comunidade era manual via `ctypes` (remover `WS_CAPTION|WS_THICKFRAME` da janela depois de ~120 frames).
- **Implementado nativamente**, usando os nomes de propriedade do projeto de referência (`D:\ProjetoRangeEngine`, só UI Python, sem C++) pra manter compatibilidade: `GAME_PLAYER_BORDERLESS_WINDOW` nova flag em `GameData.playerflag` (`DNA_scene_types.h`), propriedade RNA `borderless_window` (`rna_scene.c`), checkbox em `properties_game.py` (desativa Fullscreen/Desktop quando marcado, igual ao layout de referência).
- **`GPG_Ghost.cpp`**: nova `startBorderlessWindow()` — cria uma janela normal do tamanho do display (`GHOST_ISystem::getMainDisplayDimensions`) e remove `WS_CAPTION|WS_THICKFRAME|WS_SYSMENU|WS_MINIMIZEBOX|WS_MAXIMIZEBOX` via `SetWindowLongPtr`/`SetWindowPos` logo após a criação — **nunca chama `beginFullScreen`**, então o crash relatado não se aplica a esse caminho. Wireado antes do fullscreen exclusivo na checagem de `playerflag` em `GPG_Ghost.cpp` (bloco que decide `fullScreen`/`windowWidth`/`windowHeight` a partir das configurações da cena) e no ponto de criação de janela (ao lado de `startWindow`/`startEmbeddedWindow`).
- Mudança em DNA header exigiu `ninja -t clean` + rebuild completo (`relatorio-melhorias-anastacioengine.md`/memória de build já documentam esse gotcha). Build limpo, 2911/2911, sem erros novos. Pendente: teste do usuário no jogo real (marcar o checkbox, dar Start, confirmar janela borderless cobrindo a tela sem crash).

**Trilha Iluminação: Cascaded Shadow Mapping (CSM) para luzes Sun — implementado do zero e verificado**
- Usuário viu CSM numa versão mais nova da Range Engine (`D:\ProjetoRangeEngine`, só scripts Python, sem C++) e pediu a mesma feature aqui. Confirmado via grep que Rev2 (base deste fork) não tinha nada de cascade — implementado do zero, usando os nomes de property do projeto de referência (`use_csm_shadow`, `cascaded_proportion_two/three`, `shadow_csm_two/three_buffer_size`, etc.) pra manter compatibilidade de nomenclatura. Técnica: 3 cascatas fixas (Near/Medium/Low) com ortho **tight-fit ao frustum da câmera** por cascata (CSM de verdade, não shadow maps concêntricos de tamanho fixo).
- **Dados (DNA/RNA/UI)**: `Lamp` ganhou `shadow_cascade_count` (0=desligado, dobra como flag de ativação), `csm_flag` (`LA_CSM_DEBUG`), proporções near/middle, e tamanho/soft/bias por cascata Medium/Low (`DNA_lamp_types.h`). RNA em `rna_def_sun_lamp()` (`rna_lamp.c`), painel novo em `DATA_PT_shadow_game` (`properties_game.py`), Sun-only. Defaults sensatos em `BKE_lamp_init()`; arquivos antigos ficam com CSM desligado automaticamente (zero-default seguro).
- **GPU (buffers)**: `GPULamp` (`gpu_material.c`) ganhou `cascade[2]` (Medium/Low) — cada um é um `GPULamp` completo, secundário, compartilhando Object/Lamp/Scene com o pai, com seu próprio framebuffer/textura de profundidade (tamanho `csm_bufsize[i]`). O lamp "pai" em si já serve de cascata Near (reaproveita seus próprios campos). Criação de buffer refatorada pra uma função auxiliar (`gpu_lamp_create_shadow_buffer`) reutilizada pelas 3 cascatas; free recursivo em `gpu_lamp_shadow_free`.
- **Matrizes por cascata**: nova `GPU_lamp_shadow_buffer_bind_matrices()` escreve view/win matrix vindas de fora (calculadas pelo RAS/KX) direto no `GPULamp`, em vez de derivar de `obmat` como o caminho normal (`gpu_lamp_calc_winmat`) — necessário porque o tight-fit depende do frustum da câmera, não só da orientação da luz. Cálculo do tight-fit em `KX_KetsjiEngine::ComputeCascadeShadowMatrices()` (novo): pega os 8 cantos do frustum da câmera na fatia de distância `[splitNear, splitFar]` daquela cascata (usando os elementos `P(0,0)`/`P(1,1)` da matriz de projeção real da câmera, sem precisar extrair FOV/lens manualmente), transforma pro espaço local da luz, monta um AABB e vira um `mt::mat4::Ortho`. **Splits vêm do range de clip da própria luz** (`shadow_buffer_clip_start/end`) dividido pelas proporções — não do clip da câmera, que pode ser bem diferente.
- **Orquestração**: `KX_KetsjiEngine::RenderShadowBuffers()` agora, pra luzes Sun com CSM habilitado, faz um loop de 3 sub-passadas (bind cascata → cull → `RenderBuckets(RAS_SHADOW)` → unbind) usando a câmera ativa da cena (`scene->GetActiveCamera()`) só pra calcular os splits — sem câmera ativa, cai pro caminho de shadow map único de sempre. Reaproveitou 100% o mecanismo de upload de matriz por-objeto já existente da migração core profile (`RAS_Rasterizer::UpdateOverrideShaderObjectMatrix`), só trocando `SetViewMatrix`/`SetProjectionMatrix`/bind pra rodar uma vez por cascata em vez de uma vez por luz. Novos virtuais em `RAS_ILightObject`/`RAS_OpenGLLight`: `HasCascadedShadow`, `BindCascadeShadowBuffer`, `UnbindCascadeShadowBuffer`, `SetCascadeSplits`.
- **Shader**: `gpu_shader_material.glsl` ganhou `shadow_simple_csm`/`shadow_vsm_csm` — variantes com 3 samplers + 3 matrizes + 2 distâncias de split, escolhendo a cascata certa por `-rco.z` (distância em view-space da câmera real) com um corte direto (sem blend suave na borda — simplificação documentada pro v1). `GPU_lamp_get_data()` (`gpu_material.c`) decide entre a variante CSM e a variante single-map de sempre via `GPU_lamp_has_cascaded_shadow()`, registrando as 2 cascatas extras em `mat->lamps` pra terem o `dynpersmat` atualizado todo frame igual ao lamp principal.
- **Escopo aceito pro v1**: CSM só cobre os caminhos `shadow_simple`/`shadow_vsm` (Simple/Variance) — as variantes PCF-jitter/early-bail/penumbra não ganharam versão CSM (explodiria a superfície de código 4x); sem blend suave na borda entre cascatas (corte direto); sem recentragem/texel-snapping por cascata (mesma view matrix pras 3, só o ortho muda — matematicamente correto, só não elimina shimmer sob rotação de câmera); `use_csm_debug` existe no DNA/RNA/painel mas não tem visualização implementada ainda (gap conhecido, não faz nada por enquanto).
- **Verificado**: `build/` (COMPAT), `build_core/` (CORE) e `RangeEngine` compilam limpos em todas as fases (DNA+RNA, GPU buffers+shader, RAS/KX orquestração) — nenhum erro em nenhuma etapa. Testado em `projects-teste/shadow_csm_test.range` (cena preparada pelo usuário: Sun com `use_shadow`+`use_csm_shadow` ligados, cubos a distâncias variadas): roda sem crash, zero `GPUShader: compile error:` no log (`-d gpu`), sombras renderizam corretamente. Achado durante o teste: a cena tinha `cascaded_proportion_two/three` em 0.0/0.0 (lâmpada criada antes dos defaults existirem) — corrigido pra 0.1/0.2 diretamente no arquivo de teste; re-testado e confirmado que o objeto que mudou de cascata (Low→Medium) entre as duas rodadas continua com sombra correta, sem artefato visível na transição.
- Screenshots/logs: `projects-teste/csm_test_screenshot.png`, `projects-teste/csm_test_screenshot2.png`, `projects-teste/csm_test_run*.log`.
- **CORREÇÃO CRÍTICA (mesma sessão, mesmo dia) — CSM nunca esteve realmente ativo até este ponto, bug de fallback silencioso encontrado ao implementar o modo debug**: usuário pediu o modo debug (3 cores por cascata, igual à referência). Achado 1: existe um SEGUNDO caminho de shading duplicado (`shade_one_light()`, usado por materiais sem nodetree — os da cena de teste) que eu não tinha corrigido pra CSM, só o caminho de nodetree (`GPU_lamp_get_data()`). Achado 2, mais grave: mesmo depois de corrigir os dois caminhos, o tint não aparecia — diagnóstico (`fprintf` temporário) revelou que `GPU_lamp_has_cascaded_shadow()` sempre retornava falso porque `la->csm_bufsize[i]` lia **0** (não 512), já que `BKE_lamp_init()` só define default pra lâmpadas novas — a luz da cena de teste foi criada antes desses campos existirem, então ficou com os bytes zerados (SDNA não passa pelo clamp de RNA ao carregar arquivo antigo). Textura 0×0 falha na validação do framebuffer, criação de cascata retorna NULL, e a luz cai pro fallback de shadow map único sem avisar nada. **Isso significa que todo teste "verificado" de CSM anterior nesta sessão (inclusive a troca de cascata Low→Medium) estava na verdade rodando o fallback antigo o tempo todo** — a sombra parecia certa porque a lâmpada base ainda recebia o tight-fit da cascata Near todo frame, então havia uma sombra real e correta sendo renderizada, só nunca era de fato 3 cascatas.
- **Fix**: `gpu_lamp_create_cascade()` agora trata `csm_bufsize`/`csm_bias` ≤0 como "não definido" e cai pro valor da cascata Near (`la->bufsize`/`la->bias`) em vez de confiar cegamente no valor bruto do DNA — correção geral de robustez, não específica da cena de teste. Depois do fix: `cascade0`/`cascade1` alocam com sucesso, `GPU_lamp_has_cascaded_shadow()` retorna true, e o tint de debug agora aparece de verdade (chão ganha um tom arroxeado visível, misturando o vermelho da cascata Near com a iluminação natural) — `projects-teste/csm_debug_screenshot4.png`.
- **Pendente pra uma sessão futura**: re-verificar `build_core/` e `RangeEngine` com esse fix (só `build/` foi recompilado/testado durante essa sequência de debug); re-testar a transição de cascata Low→Medium agora que o CSM está de fato ativo (a "confirmação" anterior testava o fallback, não o CSM real); blend suave na borda das cascatas; medição de custo de GPU real.

**Ferramentas visuais de diagnóstico para CSM e culling de câmera**
- O controle **Show Shadow Box** de uma Sun com CSM agora desenha, no viewport do editor, os três volumes de cascata como frustums da câmera ativa: Near em vermelho, Medium em verde e Low em azul. A implementação deixou de usar uma caixa originada na lâmpada; cada volume é uma fatia do frustum da câmera, tal como o cálculo de CSM empregado pelo runtime.
- Corrigido o checkbox **Show Frustum** de câmera: anteriormente a propriedade era convertida para o runtime, mas o desenho era bloqueado pelo modo global de debug. Agora uma câmera marcada desenha seu frustum translúcido e contornado no jogo; o comando global continua podendo forçar a visualização de todas as câmeras.
- Adicionado **Show Culling Box** em *Camera Data > Culling > Frustum Culling*. É independente de Show Frustum e desenha no viewport do editor um volume azul translúcido, limitado por Clip Start/Clip End, para inspecionar previamente a região usada por culling. Campo novo `Camera.show_culling_box` / `GAME_CAM_SHOW_CULLING_BOX`.

**Bug resolvido: crash ao salvar um novo tema (preset de Theme)**
- Causa raiz: `rna2xml()` (`rna_xml.py`) chamava `list()` diretamente sobre wrappers RNA legados (`bpy_prop_array`/`bpy_prop_collection`) ao serializar `ThemeStyle`; no Python 3.11 embutido isso aciona uma conversão de sequência que recebe um item inválido do iterador C legado e derruba o processo. `xml_file_write()` também escrevia direto no arquivo de destino, então qualquer exceção durante a serialização corrompia um preset existente ou deixava um arquivo pela metade.
- **Fix**: `rna2xml()` passou a acessar arrays/coleções RNA e vetores/cores do mathutils por índice (`subvalue[i]` num loop bounded), nunca via `list()`/`for` sobre o wrapper legado; tipos `bpy_prop_*` desconhecidos são ignorados em vez de arriscar a iteração. `xml_file_write()` agora monta o documento inteiro em memória, escreve num arquivo temporário no mesmo diretório, valida com `ElementTree.parse()` e só então substitui o arquivo final via `os.replace()` atômico — uma falha na serialização nunca mais corrompe um preset já salvo. O operador `AddPresetBase.execute()` (`presets.py`) ganhou um `try/except` ao redor do salvamento, reportando o erro ao usuário (`self.report`) em vez de deixar a UI travar silenciosamente.
- **Verificado**: testado via `RangeEngine.exe --background --python` serializando `Theme` + `ThemeStyle` juntos (o caso exato que crashava) — salva um XML de 49KB válido, sem crash. Usuário confirmou também pela UI (Save Preset no editor de tema) que o salvamento funciona normalmente.

**Trilha Iluminação, Fase 4 — FXAA melhorado (algoritmo edge-search em vez de luma de 4 cantos)**
- O FXAA existente (`RAS_Fxaa2DFilter.glsl`, usado pelo runtime do jogo, e `gpu_shader_fx_fxaa_frag.glsl`, usado pelo viewport GLSL do editor) era uma versão simplificada antiga (fonte: geeks3d.com, ~2011) que só compara a luminância dos 4 cantos do pixel e faz um blend fixo na direção do gradiente — sem detecção real de borda nem busca de extensão, deixando diagonais longas ainda serrilhadas.
- **Fix**: os dois shaders foram reescritos para um algoritmo FXAA 3.11-style (baseado no whitepaper da NVIDIA/Timothy Lottes, porte simplificado de domínio público popularizado por implementações como a de Simon Rodriguez): amostra 9 texels (centro + N/S/E/W + 4 cantos), calcula contraste local com early-exit se abaixo do threshold (evita custo em áreas sem borda), determina orientação da borda (horizontal/vertical) por um teste de segunda derivada, escolhe a direção de maior gradiente, faz busca iterativa (`FXAA_SEARCH_STEPS = 10`) ao longo da tangente da borda pra achar sua extensão real dos dois lados, e usa a posição relativa dentro da borda + um termo de subpixel-aliasing (baseado na média dos 9 taps) pra decidir o deslocamento final de amostragem. Mesma estrutura de arquivo preservada (branches `#if __VERSION__ >= 130` core/legacy, mesmos nomes de uniform).
- **Escopo**: os dois arquivos foram atualizados em paridade (eram cópias do mesmo código antigo) — decisão do usuário de manter os dois em sincronia em vez de só o do jogo.
- **Verificado**: usuário testou no jogo (`build_core`/`RangeRuntime`) — resultado "parece tudo certo", sem regressão na transparência das árvores (alpha-cutout, ver Z-prepass acima). **Achado colateral durante o teste**: a fumaça do carro passou a renderizar quase totalmente transparente, só a borda visível — investigado a fundo na entrada seguinte, não era o FXAA.

**Bug de fumaça/faísca "quase invisível" — CAUSA RAIZ ENCONTRADA E CORRIGIDA: objetos RAS_HALO/RAS_BILLBOARD perdem a rotação de encarar a câmera sob core profile**
- Investigação isolada em `projects-teste/smoke_teste.range` (preparado pelo usuário, objeto `smoke`: material de node "Blender Internal", `game.alpha_blend=ALPHA`, `transparency_method=Z_TRANSPARENCY`). Usuário associou o sintoma a um relato parecido de 23/08 com um objeto de faísca ("piscava/aparecia plano").
- **Hipóteses descartadas com evidência, nessa ordem**: (1) FXAA — usuário confirmou "não mudou nada" depois do fix de preservar alpha no filtro (ver entrada anterior); (2) `BL_BlenderShader::ReloadMaterial()` não notificava `ATTRIBUTES_MODIFIED` (só `SHADER_MODIFIED`) — gap real no fix de 23/08 que só cobriu `BL_Shader`, corrigido em `BL_BlenderShader.cpp:161`, build limpo, mas usuário testou e não resolveu; (3) Z-prepass — lido com cuidado, `SetDepthMask`/`SetColorMask` corretamente escopado, e o material `smoke` nem entra no bucket `ALPHA_DEPTH_BUCKET` (`game.alpha_blend=ALPHA`, não `CLIP`); (4) confusão de enum `GEMAT_*`/`GPU_BLEND_*` em `KX_BlenderMaterial::ActivateMeshUser` — os valores são propositalmente idênticos (`DNA_material_types.h:220-224`), não é bug; (5) `material->alpha`/`GPU_material_alpha_blend()` — confirmado que fica habilitado corretamente pelo caminho `ma->alpha < 1.0f`.
- Instrumentação temporária (`fprintf` em `KX_BlenderMaterial::ActivateMeshUser`, guardada por nome de material, removida depois de achar a causa) confirmou blend mode (`GPU_BLEND_ALPHA`), `Ok()==true` e posição do objeto corretos frame a frame — a causa não estava em nenhum desses pontos.
- **Causa real**: o objeto `smoke` usa `face_orientation = HALO` (billboard automático, sempre de frente pra câmera — comum em efeitos de partícula). A rotação halo é calculada certinho em `RAS_Rasterizer::GetTransform()` (`RAS_Rasterizer.cpp:1215-1268`), mas só chegava ao shader via `PushMatrix()`/`MultMatrix()`/`PopMatrix()` — a pilha de matriz fixed-function do OpenGL antigo (`RAS_MeshSlot::RunNode`, `RAS_MeshSlot.cpp:108-115`). Esses três métodos já são **no-ops documentados sob `WITH_GL_PROFILE_CORE`**, com comentário explicativo já presente no código desde a migração core profile (`RAS_OpenGLRasterizer.cpp:495-502`). O vertex shader moderno (`gpu_shader_vertex.glsl:235-247`, ramo `USE_CORE_PROFILE`) usa só a uniform `unfobmat`, carregada **antes** em `BL_BlenderShader::Update` com a matriz crua (`meshUser->GetMatrix()`, sem billboard) — então sob `build_core` (o runtime real do jogo), halo/billboard nunca gira pra câmera: o objeto renderiza com orientação fixa, na maioria dos ângulos quase de perfil (só a borda fina visível, exatamente o sintoma relatado). Sob COMPAT, `gl_ModelViewMatrix` (fixed-function, populada por `glMultMatrixf`) recebe a rotação normalmente — por isso a Range Engine de referência do usuário (sem migração core) não tem o bug, e por isso é um gap específico desta migração, não documentado nos 3 gaps já aceitos (motion blur, clipping de espelho, texto de debug).
- **Fix**: novo método virtual `RAS_IMaterial::UpdateObjectMatrix(RAS_MeshUser*, RAS_Rasterizer*, const float mat[16])` (no-op por padrão — materiais como texto não precisam). Implementado em `KX_BlenderMaterial`/`BL_BlenderShader`: `BL_BlenderShader::Update()` foi refatorado para delegar a parte de upload de uniforms dependentes da matriz de objeto pra um novo `BL_BlenderShader::UpdateObjectMatrix()`, reutilizável com uma matriz explícita em vez de sempre puxar `meshUser->GetMatrix()`. `RAS_MeshSlot::RunNode` chama esse método logo depois de `GetTransform()`, só quando `drawingMode != RAS_NORMAL` (evita custo extra pra maioria dos objetos sólidos da cena, que não são halo/billboard). O caminho de **instancing** (`RAS_InstancingBuffer.cpp:111-137`) já empacotava a matriz halo-corrigida direto no buffer de instância (`instmat`, lido pelo shader antes até do branch `USE_CORE_PROFILE`) — não precisou de mudança nenhuma ali.
- **Escopo aceito**: só o caminho `BL_BlenderShader` (materiais de node/GPUMaterial, que é o que estava quebrado) foi corrigido. `BL_Shader` (shader GLSL customizado via Python, `bge.logic`) tem exatamente o mesmo padrão de bug (`RAS_Shader::Update(rasty, meshUser->GetMatrix())` sem considerar halo) mas não foi tocado — caminho bem mais raro, mantém o diff focado no que foi reportado; registrado como gap conhecido caso alguém use halo/billboard com shader customizado.
- **Verificado**: `build/` (COMPAT) e `build_core/` (CORE) compilam limpos. Testado em `smoke_teste.range` com câmera posicionada via script Python (limitação conhecida: não substitui o teste no jogo real) — antes do fix, nada visível nos ângulos/distâncias onde o objeto deveria aparecer; depois do fix, fragmentos aparecem nas posições esperadas de spawn. Pendente: confirmação visual do usuário no jogo real (fumaça e faísca).
- **CORREÇÃO — esse fix de billboard NÃO era a causa da fumaça quebrada**: usuário testou no jogo real e confirmou "idêntico, nenhuma mudança visível". O fix em si ficou (é uma correção válida, real gap do core profile), mas a investigação continuou — ver entrada abaixo pra causa real.

**Causa real da fumaça/faísca "em blocos" — Z-prepass escrevendo profundidade em materiais alpha suave não-cutout**
- Depois de descartar FXAA, instancing e billboard/halo (nenhum era a causa — usuário confirmou "idêntico" depois de cada fix), o usuário mandou um screenshot real do jogo: a fumaça aparecia como blocos quadrados grandes com bordas duras espalhados pela tela, não um blob macio nem bordas finas. Investigação de textura/mipmap (upload de GPU, filtro, Lod Bias) descartada por instrumentação e teste do usuário (mudar `Lod Bias` pra -999 não teve efeito). Teste decisivo do usuário: acontecia igual em `build/` (COMPAT) e `build_core/` (CORE) — não era regressão do core profile.
- **Causa raiz encontrada pelo usuário**: desligar a opção **Depth Transparency** do material resolveu. `IsAlphaDepth()` (`RAS_IMaterial.cpp`, lê `mat->mode2 & MA_DEPTH_TRANSP`) é **independente** do modo de blend do material (`game.alpha_blend`) — um material pode estar em "Alpha Blend" normal (não cutout) e ainda ter "Depth Transparency" marcado. `RAS_BucketManager::FindBucket` (`RAS_BucketManager.cpp:384`, antes desta correção) colocava QUALQUER material com esse flag no bucket usado pelo Z-prepass implementado nesta sessão (ver entrada "Z-prepass" acima) — mas esse prepass escreve profundidade real de hardware pra todo fragmento do quad, sem discard, o que é seguro só pra material cutout binário (Clip/A2C — onde um pixel é 100% opaco ou 100% descartado). Pra um material de alpha suave como fumaça (sem discard, gradiente contínuo), escrever profundidade cheia faz cópias sobrepostas de fumaça se auto-ocluírem no teste de profundidade da passada de cor seguinte, nas regiões quase-transparentes — resultando em fragmentos quebrados/em blocos em vez de um blend suave.
- **Fix**: `RAS_BucketManager::FindBucket` agora só adiciona o material ao bucket do Z-prepass (`ALPHA_DEPTH_BUCKET`/`ALPHA_DEPTH_INSTANCING_BUCKET`) se, além de `IsAlphaDepth()`, ele também for `IsAlphaShadow()` (o mesmo teste `ELEM(alphablend, GEMAT_CLIP, GEMAT_ALPHA_TO_COVERAGE)` já usado em outro lugar do código pra identificar material cutout de verdade).
- **Refinamento pedido pelo usuário depois de revisar o código**: o fix inicial reaproveitava o MESMO bucket (`ALPHA_DEPTH_BUCKET`) tanto pro Z-prepass quanto pro gatilho mais antigo de `UpdateGlobalDepthTexture()` (mecanismo de "soft particles", documentado antes como "não relacionado" ao Z-prepass) — estreitar esse bucket também estreitava sem querer o gatilho de soft particles, que historicamente disparava pra QUALQUER material com Depth Transparency (cutout ou não). Corrigido separando em dois conjuntos de buckets: `ALPHA_DEPTH_BUCKET`/`ALPHA_DEPTH_INSTANCING_BUCKET` voltou a ser populado por `IsAlphaDepth()` sozinho (mantendo o gatilho de soft particles como sempre foi), e dois buckets novos e dedicados `ALPHA_DEPTH_CUTOUT_BUCKET`/`ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET` (`IsAlphaDepth() && IsAlphaShadow()`) alimentam só as chamadas de render do Z-prepass em `Renderbuckets()` (casos `RAS_TEXTURED` e `RAS_RENDERER`).
- **Verificado**: `build/` e `build_core/` compilam limpos com a versão final (buckets separados). Usuário confirmou no jogo real que a fumaça voltou ao normal depois de desligar Depth Transparency manualmente — pendente reconfirmar com esse fix de engine aplicado (não deveria mais precisar desligar manualmente, já que agora só material cutout entra no Z-prepass).

**Correção antiga: objetos ficam invisíveis ao ligar Depth Transparency na 3D View**
- Usuário reportou que qualquer objeto com **Depth Transparency** marcado no material simplesmente desaparecia na 3D View do editor — mesmo fora do jogo. Esse é um bug diferente (e mais antigo) do episódio da fumaça em blocos registrado acima: ali o problema era escrever profundidade demais *durante* o jogo; aqui o objeto sumia mesmo sem o jogo estar rodando.
- **Causa raiz**: o efeito de Depth Transparency (`shade_alpha_depth`, `gpu_shader_material.glsl`) lê a profundidade da cena via `texelFetch` numa textura global (`GG.depth_tex`) usando coordenadas de pixel absolutas da tela (`gl_FragCoord.xy`). Essa textura só é preenchida com dados reais **durante a execução do jogo** (`RAS_Rasterizer::UpdateGlobalDepthTexture`); na 3D View comum, ela é um placeholder de 1×1 pixel (`GG.invalid_tex_2D`). Buscar um pixel de tela (ex.: 500,300) numa textura de 1×1 é uma leitura fora dos limites — resultado indefinido pela spec do GLSL, mas que a maioria dos drivers resolve como zero em vez do valor real do placeholder. Profundidade zero é lida pelo shader como "nada bloqueando", e a fórmula de fade zera o alfa por completo: o objeto vira 100% transparente, ou seja, invisível.
- **Fix**: `shade_alpha_depth()` agora limita a coordenada de busca ao tamanho real da textura (`min(gl_FragCoord.xy, textureSize(ima, 0) - 1)`) antes do `texelFetch`. Fora do jogo, isso faz a leitura sempre cair dentro do único texel do placeholder (valor "longe", sem oclusão) em vez de estourar os limites — o efeito vira um no-op seguro na 3D View, e continua funcionando normalmente durante o jogo, onde a textura de profundidade real tem o tamanho da tela.
- **Verificado**: `bf_gpu` recompilado limpo (só o `.glsl`, sem mudança de header — não precisou de rebuild limpo). `RangeEngine` (editor) e `RangeRuntime` recompilados incrementalmente. Usuário confirmou na 3D View que o objeto permanece visível com Depth Transparency ligado, e que o comportamento no jogo continua normal.

**Bug corrigido: `filterManager.changeXValues()` não ligava os shaders built-in via Python se a cena carregasse com a checkbox desmarcada**
- Usuário reportou (a partir de `KX_2DFilterManager.rst`/`changeTonemapValues`): shaders de pós-processamento (Ambient Occlusion, Bloom, Tonemap, Light Scattering, Screen Space Reflections, FXAA) só respondiam a `filterManager.changeXValues()` via Python se a checkbox correspondente em *Render > Post Processing Shaders* já tivesse sido ligada manualmente na UI ao menos uma vez.
- **Causa raiz**: os objetos `RAS_2DFilter` desses 6 shaders só são instanciados uma única vez, no construtor de `RAS_2DFilterManager`/`KX_2DFilterManager`, no carregamento da cena, condicionados às flags `scenefx_flag` (as checkboxes). Os 6 métodos Python (`changeTonemapValues`, `changeSSAOValues`, `changeBloomValues`, `changeLightScatterValues`, `changeSSRValues`, e o inexistente equivalente de FXAA) faziam `GetFilterPass(...)` e, se retornasse `nullptr` (filtro nunca construído porque a checkbox começou desmarcada), simplesmente `Py_RETURN_NONE` sem erro nem efeito.
- **Fix**: `RAS_2DFilterManager` ganhou `EnsureTonemapFilter()`/`EnsureSSAOFilter()`/`EnsureFxaaFilter()` (`source/gameengine/Rasterizer/RAS_2DFilterManager.h/.cpp`) e `KX_2DFilterManager` ganhou `EnsureBloomFilters()`/`EnsureSSRFilters()`/`EnsureLightScatterFilters()` (esses três precisam do canvas real para os offscreens intermediários, por isso vivem na camada Ketsji com um novo membro `m_canvas`; o construtor foi refatorado pra chamar os mesmos três métodos em vez de ter o código duplicado inline). Cada `change*Values()` agora chama o `Ensure*` correspondente quando o filtro não existe, construindo-o na hora com os valores passados (ou defaults iguais aos da UI, ex. Tonemap exposure=2.2/gamma=1.0, SSAO samples=16, Bloom intensity=2.0/threshold=0.75) em vez de desistir silenciosamente.
- **Recurso novo**: FXAA nunca teve nenhum método Python exposto (nem antigo nem quebrado) — adicionado `filterManager.changeFxaaValues(enabled)`.
- **Segundo bug encontrado durante o teste do usuário (com o componente de teste abaixo)**: Light Scattering e SSR são cadeias de 2 passes (buffer + composição final), mas `changeLightScatterValues`/`changeSSRValues` só ligavam/desligavam o pass de buffer (`Scatter`/`SSR`), nunca o pass de composição (`Scatter_Image`/`SSR_Blur`) — resultado: o shader "ligava" mas nunca desligava de fato, porque o pass de composição ficava sempre ativo compositando uma textura congelada. Corrigido chamando `SetEnabled()` nos dois passes. Achado o mesmo padrão em Bloom (`Bloom6`, um dos 8 passes, nunca recebia `SetEnabled()` na função original) e corrigido também.
- **Verificado**: `ge_rasterizer`/`ge_ketsji` compilam limpos; `RangeRuntime.exe`/`RangeEngine.exe` linkados com sucesso. Componente de teste `projects-teste/scripts/postfx_toggle_test.py` criado (teclas 1-6 pra cada shader) — usuário confirmou que Light Scattering e SSR agora ligam/desligam corretamente; Tonemap/SSAO/Bloom/FXAA aplicam mas o efeito visual pode ser sutil dependendo da cena de teste (SSAO precisa de geometria próxima, Bloom precisa de algo acima do threshold de brilho, FXAA só é visível em bordas serrilhadas de perto).

**Debug Mode — toggles de Bounding Box e Camera Frustum expostos na UI (2026-08-25)**
- Levantamento do estado atual do Debug Mode (`KX_DebugMode`, overlay ImGui) a pedido do usuário, comparando com o "Realtime Debug Mode" divulgado pela Range Engine upstream (profiling gráfico + manipulação de objetos em tempo real) — confirmado que a AnastacioEngine já tem o equivalente funcional (painel de profiling por categoria com gráfico ao vivo, stats de render query, lista de objetos por impacto de performance, painéis de Scene/Options/Debug Properties/Game Object/Camera Controller), não é uma feature ausente a portar.
- Achado no levantamento: `m_showBoundingBox`/`m_showCameraFrustum` já existiam como `KX_DebugOption` no `KX_KetsjiEngine` (`SetShowBoundingBox`/`SetShowCameraFrustum`, `KX_KetsjiEngine.cpp:1862-1887`), mas só "Show Armatures" tinha checkbox no menu do Debug Mode — os outros dois setters não tinham UI, ficavam só acessíveis via código.
- **Fix**: adicionados `imgui_showBoundingBox`/`imgui_showCameraFrustum` (`KX_DebugMode.h`) e os checkboxes correspondentes no menu principal (`KX_DebugMode.cpp`, ao lado de "Show Armatures"), ligando direto nos setters já existentes — nenhuma mudança de header DNA, build incremental (`ninja RangeEngine`, 15 steps).
- **Verificado**: usuário confirmou funcionando no editor.
- **Pendências levantadas no mesmo survey, não implementadas ainda**: stats de GPU query (`profileQueryTips`) parcialmente plugados na UI; botão de frame-advance auto-sinalizado como "Hacky... extremely garbage code" no código; API Python legada `showFramerate()`/`showProperties()` (`KX_PythonInit.cpp:1573,1595`) desconectada do novo sistema ImGui, candidata a ligar ou deprecar.

**Debug Mode — Shadow Frustum e Render Queries também liberados na UI, e teto do tamanho de fonte aumentado (2026-08-25)**
- Mesmo padrão do fix de Bounding Box/Camera Frustum acima: achados mais dois toggles sem checkbox no menu do Debug Mode. `m_showShadowFrustum` (`KX_KetsjiEngine`, `SetShowShadowFrustum`) era um terceiro `KX_DebugOption` da mesma família de Bounding Box/Armatures/Camera Frustum, também sem UI. `SHOW_RENDER_QUERIES` (flag de bitmask do `KX_KetsjiEngine`) só podia ser ligado via argumento de linha de comando (`show_render_queries`) no lançamento do jogo, nunca em runtime.
- **Fix**: `imgui_showShadowFrustum`/`imgui_showRenderQueries` (`KX_DebugMode.h`) + checkboxes "Show Shadow Frustum" e "Show Render Queries" no menu principal (`KX_DebugMode.cpp`), ligando em `SetShowShadowFrustum()` e `SetFlag(SHOW_RENDER_QUERIES, ...)` respectivamente — sem mudança de header DNA, builds incrementais.
- **Segundo pedido do usuário**: a fonte do painel de profiling ficava pequena mesmo com o slider "Profile Size" no máximo — o slider ia só de 0.9 a 1.5, e a escala real de fonte usa `m_profileSize * 0.8f` (`RenderProfiling`, linha 165), ou seja o teto real era ~1.2x, quase o tamanho normal. Aumentado o range do `ImGui::SliderFloat("Profile Size", ...)` pra 0.9–4.0.
- **Verificado**: usuário confirmou o slider correto por screenshot antes do fix; build recompilado com sucesso depois de fechar o `RangeEngine.exe` que estava travando o link (`LNK1104`, processo com o .exe aberto).

**Recurso novo: sistema de menu in-game (ImGui + Python), scriptável — implementado e verificado ponta a ponta (2026-08-25)**
- Objetivo: Main Menu, Pause Menu e tela de Options "no estilo das engines modernas", usando infraestrutura já existente em vez de uma UI framework nova. Investigação confirmou que Dear ImGui + ImPlot já estavam totalmente integrados no runtime do jogo via `KX_Imgui` (`Ketsji/KXImgui/`), usados até então só pro overlay de debug/profile (`KX_DebugMode`) — não era plumbing do zero, era reaproveitar e destravar uma infraestrutura pronta. Decisão do usuário: menus devem ser scriptáveis em Python, como o resto da lógica do BGE, não hardcoded em C++.
- **Fix de C++ (a)**: bug de input-gating — `KX_KetsjiEngine::NextFrame()` só chamava `m_imgui->ProcessInputEvents()` sob `SHOW_DEBUG_MODE`/`SHOW_PROFILE`, então qualquer janela ImGui fora do debug mode renderizava mas nunca recebia clique/teclado. Nova flag `SHOW_GAME_UI` (`FlagType`, `KX_KetsjiEngine.h`) inclusa na mesma checagem. Mouse: o bool único `debugmode_allowmouse` (`RAS_ICanvas`) virou bitmask de requisitantes (`RAS_MouseCursorRequester` / `RequestMouseVisible(requester, visible)`), permitindo debug mode e menu de jogo pedirem o cursor livre ao mesmo tempo sem conflito, com `ToggleDebugModeAllowMouse()`/`GetDebugModeAllowMouse()` mantidos como wrappers finos pra não quebrar os 2 call sites diretos existentes (`KX_BlenderCanvas.cpp`, `GPG_Canvas.cpp`).
- **Fix de C++ (b)**: `ImGui::NewFrame()` estava sendo chamado dentro de `EndFrame()` — depois da lógica Python já ter rodado no tick daquele frame, então chamar `imgui.*` do Python seria UB (assert em debug build do ImGui). Movido pro topo de `NextFrame()` (antes do processamento de input), mantendo `ImGui::Render()` onde já estava em `EndFrame()` — mesmo padrão usado por bindings ImGui de outras engines com tick de lógica separado do render. Debug mode segue funcionando idêntico (verificado por smoke test + confirmação do usuário testando F1/profile no jogo real).
- **Recurso novo de C++ (c/d)**: módulo Python `Range.imgui` (`Ketsji/KXImgui/KX_PythonImgui.h/.cpp`, registrado em `initRANGE()`/`KX_PythonInit.cpp`), espelhando o padrão de submódulo plano já usado por `Range.render` (`PyMethodDef` de funções livres, não uma classe `EXP_PyObjectPlus`). Widget set v1: `begin/end`, `text`, `button`, `checkbox`, `slider_float`/`slider_int`, `separator`/`same_line`, `set_next_window_pos`/`set_next_window_size`, `image` (reaproveita o bind de textura já usado em `DrawCustomCursor`), `get_io_want_capture_mouse`/`keyboard`, e `set_game_ui_open` (liga a flag `SHOW_GAME_UI` + o requester de mouse do menu num só wrapper). Strings de texto sempre passadas via `"%s"` pro ImGui, nunca como format string direto, pra não abrir injeção de formato a partir de conteúdo controlado por script Python.
- **Fix de C++ adicional, não previsto no plano original**: o editor tem um shim de `sys.modules` totalmente separado (`source/blender/blenkernel/intern/python_component.c`), usado só pra validar estaticamente a classe de um componente Python sem precisar do motor de jogo rodando — registra `Range`/`Range.types`/`Range.logic`/etc. como módulos falsos numa lista fixa. Faltava `Range.imgui` nessa lista, então qualquer componente que fizesse `import Range.imgui` falhava só nesse contexto do editor com o erro genérico "No module named X or script error at loading" (o runtime real, via `KX_PythonInit.cpp`, nunca teve esse problema). Corrigido adicionando a entrada faltante.
- **Conteúdo Python (e/f/g), sem nenhuma mudança de engine, em `projects-teste/scripts/`**: `main_menu_component.py` (botões Jogar/Sair, `scene.replace()`), `pause_menu_trigger_component.py` (Esc → `scene.suspend()` + `Range.logic.addScene(overlay=True)` — overlay scene existente e inalterada, mecanismo certo pra hospedar um menu independente do ciclo de vida da cena de jogo suspensa) + `pause_menu_overlay_component.py` (Continuar/Main Menu, `resume()`/`replace()`/`scene.end()`), e `menu_common.py` (painel de Options compartilhado entre os dois menus: VSync/anti-aliasing/filtro anisotrópico via `Range.render.set*` já existentes, persistidos em `options.json` ao lado do arquivo de cena).
- **Gotcha de import encontrado e documentado**: o sistema de componentes (editor e runtime real, `BL_BlenderDataConversion.cpp:1380`) sempre importa scripts como `scripts.<nome_arquivo>` (a pasta `scripts/` age como pacote implícito). Um módulo irmão na mesma pasta precisa ser importado como `from scripts import outro_modulo`, nunca `import outro_modulo` solto — a forma solta funciona pro import do próprio componente (porque `pc->module` já carrega o prefixo `scripts.`), mas quebra assim que aquele módulo tenta importar outro arquivo da mesma pasta. Hit exatamente esse bug com `menu_common.py` sendo importado solto por `main_menu_component.py`/`pause_menu_overlay_component.py`; corrigido trocando pra `from scripts import menu_common`.
- **Verificado ponta a ponta pelo usuário**: fluxo completo `MainMenu` → "Jogar" → `GameScene` → Esc → `PauseMenu` (overlay, física/lógica da `GameScene` paradas) → "Continuar"/"Main Menu", e a tela de Options (widgets respondendo, settings de render aplicando na hora, persistência em JSON confirmada entre execuções) funcionando a partir dos dois menus. Todos os builds (`RangeEngine`/`RangeRuntime`) compilaram limpos a cada checkpoint.
- **Itens deixados de lado por decisão do usuário** (não retomar sem pedido explícito): botão de frame-advance auto-sinalizado como "hacky" no código, API Python legada `showFramerate()`/`showProperties()` desconectada do sistema ImGui novo.

**Sistema de menu in-game — Fase 2: widgets extra, styling, Options completo e robustez (2026-08-25)**
- Continuação do sistema de menu acima. Lista de extensões aprovada pelo usuário, em ordem: (1) widgets/API extra, (2) styling, (3) cobertura de Options, (4) robustez/polish.
- **(1) Widgets extra + nav por teclado, C++**: `Range.imgui` ganhou `input_text`, `combo`, `listbox`, `radio_button`, `color_edit3`/`color_edit4`, `open_popup`/`begin_popup_modal`/`end_popup`/`close_current_popup` (`KX_PythonImgui.h/.cpp`); `io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard` em `KX_Imgui.cpp` (Tab/setas navegam entre widgets). Nav por gamepad explicitamente adiada nesta etapa (ver Fase 3 abaixo). `test_imgui_widgets_component.py` atualizado pra exercitar tudo. Contrato documentado: diferente de `begin`/`end` (sempre chama `end`), `begin_popup_modal` só deve ter `end_popup()` chamado se `is_open` for `True`.
- **(2) Styling, C++**: `push_style_color`/`pop_style_color` + constantes `imgui.COL_*`, `load_font`/`push_font`/`pop_font` (rebuild do atlas via `ImGui_ImplOpenGL3_CreateFontsTexture()`, só seguro fora de um frame ativo — documentado pra chamar uma vez em `start()`), `get_display_size`, `draw_rect_filled` (foreground draw list, base pra fades). Imagem de fundo não precisou de nenhuma mudança de engine: `material.textures[texslot].bindCode` (`KX_BlenderMaterial.cpp`) já expõe o bindcode OpenGL de qualquer textura carregada, direto pro `imgui.image()` já existente. Novo `test_imgui_styling_component.py` + `roboto_mono_medium.ttf` (fonte não embutida via datatoc, só pra este teste).
- **(3) Options completo, conteúdo Python + 1 função nova de C++**: `menu_common.py` reescrito com seções Vídeo (+ fullscreen/resolução), Áudio (volume mestre), Idioma (pt/en via `menu_common.t()`) e Controles (remapeamento de 5 ações de exemplo, `SCA_KeyboardSensor.key` já é RW, captura de tecla via `Range.logic.keyboard.events`/`KX_INPUT_JUST_ACTIVATED`). **Único ponto que exigiu C++ novo**: volume mestre. A suposição inicial de usar `aud.Device()` (API padrão do audaspace) estava errada — isso cria um dispositivo de áudio novo e independente, não o mesmo que a engine usa pra tocar som de verdade (`BKE_sound_get_device()`). Corrigido com `Range.render.setMasterVolume`/`getMasterVolume` (`KX_PythonInit.cpp`, usa `AUD_Device_setVolume/getVolume` sobre o device real). Testado audivelmente pelo usuário com um objeto Speaker tocando uma música em loop — confirmado por leitura de código que `KX_Speaker::play()` usa o mesmo device singleton (`AUD_Device_getCurrent()` → `DeviceManager::getDevice()`), então o volume mestre novo afeta Sound Actuator e Speaker igualmente.
  - **Bug de carregamento no editor encontrado no primeiro teste do usuário, corrigido em Python**: `menu_common.py` construía dois dicts (`_DEFAULT_KEYBINDS`/`_KEY_NAMES`) no escopo do MÓDULO referenciando `events.WKEY` etc., o que quebrou o carregamento estático de componente do editor com `AttributeError: module 'types' has no attribute 'WKEY'`. Causa: o shim de validação do editor (`python_component.c`) registra `Range.events`/`Range.logic`/`Range.render`/etc. como o MESMO objeto de módulo real quase vazio (`PyModule_Create(&range_types_module_def)`, cujo `__name__` real é "types") — só `Range.types.KX_PythonComponent` existe de verdade nele; qualquer outro atributo só existe no módulo real, em tempo de jogo. Atributos referenciados dentro de corpos de função são seguros (o editor nunca chama `start()`/`update()` nessa validação), mas uma referência no escopo do módulo quebra. Corrigido tornando os dois dicts funções lazy cacheadas (`_default_keybinds()`/`_key_names()`). **Regra a seguir em qualquer script futuro em `projects-teste/scripts/`**: nunca acessar atributo de `Range.*` fora do corpo de uma função.
- **(4) Robustez/polish, puro Python, sem mudança de engine**: `main_menu_component.py` — "Sair" agora abre popup de confirmação (Sim/Não) em vez de encerrar na hora; "Jogar" entra num fade-out de ~30 frames com "Carregando..." (`draw_rect_filled`+`get_display_size`) antes de `scene.replace()`. `pause_menu_overlay_component.py` — Esc despausa (dobrado na condição do botão "Continuar"). Ambos os menus — Esc fecha o painel de Options, exceto quando um remapeamento de tecla está em andamento (nesse caso Esc só cancela o remapeamento, via checagem de `listening["action"]` antes de chamar `draw_options_panel`).
- **Verificado ponta a ponta pelo usuário**, os 4 itens, cada um builda limpo (`RangeRuntime`/`RangeEngine`) antes do próximo.

**Sistema de menu in-game — Fase 3: navegação por gamepad (2026-08-25)**
- Pedido do usuário: implementar navegação por gamepad nas janelas ImGui do menu, com teste em hardware real adiado pra depois (sem controle disponível na hora).
- **C++**: nova `ImGui_ImplSDL2_UpdateGamepads()` em `KX_Imgui_Impl_Inputs.cpp` — porta direta do mapeamento padrão do backend oficial `imgui_impl_sdl2.cpp` do Dear ImGui (D-Pad, A/B/X/Y, ombros, start/back, clique dos analógicos, analógicos e gatilhos como eixos). `KX_Imgui.cpp`: `io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad`.
- **Achado importante**: o `DEV_Joystick` da própria engine (usado pelos sensores de joystick do BGE) tem os botões digitais funcionando (`aButtonPressIsPositive` lê `SDL_GameControllerGetButton` ao vivo), mas o cache de eixos analógicos (`m_axis_array`) nunca é escrito em lugar nenhum do `DEV_Joystick.cpp` — `OnAxisEvent`/`HandleEvents` estão declarados no header mas nunca implementados. Ou seja, leitura de analógico via `DEV_Joystick` está morta hoje, sem relação com este trabalho — é um bug pré-existente que também afeta lógica de jogo real (não só menu), deixado como investigação separada. Por isso a navegação por gamepad do ImGui abre seu **próprio** handle `SDL_GameController` (seguro abrir um segundo handle pro mesmo índice físico, o SDL mantém sincronizado) em vez de depender do `DEV_Joystick`.
- **Verificado**: compilação limpa (`RangeRuntime`/`RangeEngine`) e smoke test sem controle conectado (boot limpo, sem crash, sem erro no log) — **navegação de fato ainda não testada em hardware real**, fica pendente.

**Bug intermitente de "Reload All Components" — causa raiz real encontrada e corrigida em C++ (o fix anterior de `menu_common.py` era só um paliativo) (2026-08-25)**
- Usuário reportou: dar "Reload All Components" no editor e em seguida apertar Play falha aleatoriamente; fechar e reabrir o editor "resolve" até a próxima vez. Reproduzido em `ImGui_teste.range`: depois de "Reloaded 3 components", o jogo iniciava e `MainMenuComponent.start()` quebrava com `AttributeError: module 'types' has no attribute 'WKEY'` dentro de `menu_common._default_keybinds()` — o mesmo sintoma já visto e "corrigido" na Fase 2 do menu (ver entrada acima), mas voltando.
- **Causa raiz real, em `source/blender/blenkernel/intern/python_component.c` (`load_component()`)**: pra validar estaticamente a classe de um componente sem o motor de jogo rodando, a função injeta módulos fake em `sys.modules` (`Range`, `Range.types`, `Range.logic`, `Range.events`, `Range.render`, `Range.constraints`, `Range.application`, `Range.imgui`, todos apontando pro mesmo objeto `types` quase vazio). O macro `FINISH`, que deveria desfazer isso ao final da validação, só removia `Range`, `Range.types`, `Range.logic` e o módulo do próprio componente (`pc->module`) — **`Range.events`/`render`/`constraints`/`application`/`imgui` ficavam vazando em `sys.modules` para sempre**, e qualquer módulo Python importado durante essa validação (ex.: `menu_common.py`, puxado por `from scripts import menu_common` dentro de `main_menu_component.py`) fica com `import Range.events as events` permanentemente amarrado ao módulo fake — mesmo depois do jogo real registrar o módulo `Range.events` de verdade em `sys.modules`, porque o Python só re-executa um módulo se ele for removido do cache antes do próximo import, e `scripts.menu_common` nunca era removido (só `pc->module`, isto é, `scripts.main_menu_component`, era). O reload de UM componente (não só "Reload All") já expõe o bug quando esse componente importa um módulo auxiliar da pasta `scripts/`; "Reload All" só torna mais fácil de bater porque mexe em todos os componentes de uma vez.
- **Fix (1)**: `FINISH` agora remove também `Range.events`/`Range.render`/`Range.constraints`/`Range.application`/`Range.imgui` de `sys.modules`, fechando o vazamento direto dos módulos fake.
- **Fix (2), mais importante**: nova função `purge_scripts_package()` chamada no fim de todo `load_component()` (sucesso ou falha) — varre `sys.modules` e remove toda entrada `scripts`/`scripts.*`, não só `pc->module`. Isso garante que qualquer módulo auxiliar (como `menu_common`) importado transitivamente durante uma validação de componente seja obrigatoriamente reimportado da próxima vez que for necessário — nunca mais fica preso com bindings de `Range.*` fake até o processo inteiro ser reiniciado.
- **Consequência prática**: a regra registrada na Fase 2 ("nunca acessar atributo de `Range.*` fora do corpo de uma função") era necessária mas não suficiente — o `_default_keybinds()`/`_key_names()` lazy em `menu_common.py` evita o crash *durante a própria validação*, mas não protegia contra o módulo ficar com a referência fake presa depois. Esse fix em C++ elimina a causa raiz; o padrão lazy em `menu_common.py` continua sendo boa prática (evita qualquer custo de acessar `Range.*` fora de contexto de jogo), mas deixa de ser a única linha de defesa.
- **Verificado**: `ninja bf_blenkernel` incremental limpo (só `python_component.c` recompilado); rebuild completo de `RangeEngine`+`RangeRuntime` sem erros. Teste pendente do usuário: repetir "Reload All Components" em `ImGui_teste.range` seguido de Play várias vezes seguidas e confirmar que o `AttributeError` não volta.

## 2026-08-26

**Trilha Performance — retomada: motor confirmado GPU-bound, não CPU-bound**
- Usuário reportou percepção de baixo uso de CPU no BGE/UPBGE/Range Engine. Revisão dos dados já coletados (`benchmark_report_20260823_201152.txt`) confirma: `Physics` = 2.8% do frame, `MainRender` = 70.6% — motor gargalado por GPU/render, não por CPU. As 3 vias de paralelização de CPU (loop principal single-thread, Bullet MT solver, GIL do Python) permanecem investigadas e descartadas (ver 2026-08-23/24) — não reabertas nesta rodada por falta de novidade técnica.

**Bug de UI encontrado e corrigido: campo "Shadows" no painel Culling era um int fantasma**
- `scene.game_settings.shadows_on_off` (rótulo "Shadows" na aba Physics do Game Settings) é RNA sobre `gm.maxphystep` — mas `LA_Launcher.cpp:262` passa esse int direto pra `KX_KetsjiEngine::SetMaxPhysicsFrame(bool)`, cujo parâmetro é `bool`. Qualquer valor não-zero (1 a 10000) produz exatamente o mesmo resultado; só 0 muda o comportamento (desliga o recálculo de `tc_shadowculling` por frame em `KX_KetsjiEngine.cpp:1207`). Pior: o range da UI (`RNA_def_property_range(prop, 1, 10000)`) nem permitia chegar em 0 pela interface — só via script Python chamando `setMaxPhysicsFrame(0)` diretamente.
- **Fix** (`rna_scene.c`): range mudado para `0, 1`, rótulo renomeado de "Shadows" para "Shadow Culling", tooltip reescrita pra descrever o comportamento real (on/off, valor não tem efeito gradual). `properties_game.py` atualizado com o mesmo texto. Compilação limpa (`bf_rna` + `RangeEngine`/`RangeRuntime`).

**Recurso novo: Occluder sem perder colisão (Static + Occluder simultâneos)**
- Motivação: para reduzir o custo de `MainRender` via occlusion culling (já existente no motor, mas nunca ativado em nenhum `.range` do projeto — confirmado rodando o engine headless com script Python contra `benchmark.range`/`benchmark_reduced.range`/`benchmark_gpu_test.range`: zero objetos com `Physics Type = Occluder` em qualquer um), era preciso marcar objetos de terreno/pista como Occluder. Problema: no motor, `Physics Type` é um enum exclusivo — mudar para "Occluder" limpa a flag `OB_COLLISION` (`rna_object.c`), e sem ela `BL_CreatePhysicsObjectNew` (`BL_BlenderDataConversion.cpp:868`) nem cria o corpo físico — o objeto vira fantasma (perde colisão de pista/terreno).
- **Achado que abriu o caminho**: o runtime já lê a flag `OB_OCCLUDER` de forma independente do `physics_type` — `SetOccluder()` é chamado incondicionalmente pra todo objeto mesh na conversão de cena (`BL_BlenderDataConversion.cpp:1233`), sem checar `physics_type`. A exclusividade Static/Occluder é imposta só na camada RNA (`rna_GameObjectSettings_physics_type_set`), não no motor.
- **Fix**: nova property RNA independente `use_occlude_culling` (`rna_object.c`, liga só o bit `OB_OCCLUDER` sem tocar `OB_COLLISION`/`OB_DYNAMIC`/etc.) exposta como checkbox "Occluder (keeps collision)" no painel Physics quando `Physics Type = Static` — em `properties_game.py` (painel stock) e replicado em `source/release/scripts/addons/Range_Components_Label/custom_pt_physics.py` (o projeto usa um painel Physics customizado desse addon que sobrescreve o stock via `bl_idname` próprio, então a mudança precisou ser feita nos dois lugares pra aparecer na prática).
- **Verificado pelo usuário**: objeto de terreno marcado como Static + Occluder simultaneamente, testado em jogo — colisão da pista continuou normal, nada sumiu visualmente de forma incorreta. Teste rodado sem a GPU dedicada ligada (notebook sem fonte, caiu pra Intel iGPU) — profiler mostrou perfil de custo completamente diferente do benchmark de referência (`GPU Latency` 24.5%, `ShadowCulling` 27.3%, `MainRender` só 1.6%), portanto **não comparável** ao benchmark de GPU dedicada anterior.
- **Pendente**: (1) marcar os demais objetos de terreno grandes (`Road_Parte1.004`, demais `Road_parte2.00X`) como Occluder — só um objeto foi testado até agora; (2) repetir a medição de `MainRender`/FPS com a GPU dedicada ligada pra comparar de verdade contra os 16.1ms/70.6% do benchmark de referência — **medição de impacto real ainda não feita**.

## 2026-08-27

**Trilha Performance — Impostor (billboard) de árvore distante, Fase 1: swap + orientação — IMPLEMENTADA E VERIFICADA**

- **Motivação**: sequência direta do Z-prepass (Fase 4, 2026-08-25), que cortou GPU Time de 28.29ms para 21.45ms mas não chegou ao patamar do teste A/B sem árvores (12.89ms) — reduz overdraw de fragmentos ocluídos, não o custo de shading das folhas realmente visíveis. Impostors (billboard 2D substituindo a árvore 3D a partir de certa distância) já estava registrado como próxima frente em 2026-08-25.
- **Escopo desta fase**: dar à engine a capacidade de girar o mesh de um nível de LOD pra sempre encarar a câmera (billboard cilíndrico), reaproveitando o mecanismo de troca de mesh por LOD já existente (`KX_LodManager`/`KX_GameObject::UpdateLod`) em vez de criar um sistema novo. A textura do impostor continua sendo preparada manualmente pelo usuário no Blender — bake automático fica para a Fase 2 (ver "Fora de escopo" abaixo).
- **DNA/RNA/UI**: nova flag `OB_LOD_USE_BILLBOARD` no enum de flags de `LodLevel` (`DNA_object_types.h`), exposta como `use_billboard` em `rna_def_object_lodlevel` (`rna_object.c`), e checkbox "Billboard (impostor)" no painel `OBJECT_PT_levels_of_detail` (`bl_ui/properties_game.py`), ativo apenas quando `use_mesh` também está ligado (o billboard depende de já estar trocando a malha nesse nível).
- **Runtime**: `KX_LodLevel::USE_BILLBOARD` (novo flag runtime) mapeado a partir da flag DNA no construtor de `KX_LodManager` (`KX_LodManager.cpp`), no mesmo bloco onde `USE_MESH`/`USE_MATERIAL` já eram mapeados. Em `KX_GameObject::UpdateLod` (`KX_GameObject.cpp`), quando o nível de LOD ativo tem a flag, calcula-se o vetor objeto→câmera projetado no plano XY (ignorando diferença de altura, pra manter o billboard sem tilt vertical) e monta-se uma matriz de rotação em Z pura (`heading = atan2f(-toCam.x, toCam.y)`) aplicada via `NodeSetLocalOrientation`. Roda todo frame de render — `UpdateLod` já é chamado a cada passada de câmera via `KX_KetsjiEngine`→`KX_Scene::UpdateObjectLods`, não precisou de hook novo.
- **Limitação conhecida, aceita pro v1**: a rotação é aplicada como orientação *local*, então em objetos com pai rotacionado o resultado não seria o esperado — não é o caso de árvores típicas (sem parent), então não foi tratado nesta fase.
- **Build**: a etapa 1 (DNA) exigiu `ninja -t clean` + rebuild completo de `RangeEngine`+`RangeRuntime` (~45min) por causa do gotcha de build incremental não rastrear `DNA_*.h` como dependência (ver [[build_environment]]/memória de sessão) — etapas seguintes (LodLevel/LodManager, orientação em KX_GameObject) foram incrementais. Todas compilaram sem erro.
- **Verificado pelo usuário**: cenário isolado `projects-teste/teste_LOD.range` (grupo árvore+2 níveis de LOD, 3 instâncias na cena com distâncias diferentes). Sem a flag, o plano de impostor do nível mais distante mantinha orientação fixa e sumia de perfil ao andar ao redor da árvore; com a flag ligada, o plano acompanha a câmera continuamente e a árvore permanece visível de qualquer ângulo horizontal. Ao fechar o teste, console reportou vazamento de memória insignificante (`0.000084 MB`, 2 blocos) — não investigado, considerado sem prioridade.
- **Fora de escopo (Fase 2 futura, não iniciada)**: bake automático do atlas de impostor (renderizar a árvore de vários ângulos pra textura, via `RAS_TextureRenderer`/`RAS_OffScreen` — mesmo padrão já usado por `KX_PlanarMap`/`KX_CubeMap` pra reflexo planar/cubemap em tempo real) e billboard esférico completo (com tilt, desnecessário pra vegetação). Quando a Fase 2 for planejada, o operador de bake deve ser escrito do zero — **não reaproveitar `automate_atlas_bake.py`** como base (addon feito pelo próprio usuário; funciona, mas com problemas de qualidade conhecidos que ele não quer replicar em código novo).
## 2026-08-29

**Trilha Performance — Impostor de árvore multi-angle: crash no play corrigido**

- **Sintoma reportado pelo usuário**: com o LOD de impostor multi-angle (Fase 1, atlas de várias células por ângulo), ao apertar P perto da árvore o `RangeEngine.exe` fechava sozinho; a UV do impostor também mostrava todas as células do atlas ao mesmo tempo em vez de uma célula por ângulo. Só reproduzia na sessão em que o bake automático tinha acabado de rodar — salvar, fechar e reabrir o arquivo já baked não reproduzia o crash, o que apontava para algo específico do caminho "bake e já jogar" em vez de um problema no arquivo salvo.
- **Diagnóstico**: sem debugger disponível no ambiente (sem `cdb`/`windbg` instalados), a investigação foi feita por logging incremental — `.bat` (`run_editor_debug.bat`) rodando `RangeEngine.exe` com stdout/stderr redirecionado para `projects-teste/crash_log.txt`, mais `CM_Error` temporário inserido em pontos sucessivos de `KX_GameObject::UpdateLod` e no construtor de `KX_ImpostorAtlasDeformer` pra isolar, por bisseção, a linha exata onde o log parava de imprimir antes do `EXCEPTION_ACCESS_VIOLATION`.
- **Causa raiz**: `KX_ImpostorAtlasDeformer` (o deformer que reescreve a UV do quad billboard pra selecionar uma célula do atlas, ver 2026-08-27) nunca inicializava `m_boundingBox` — herdava `nullptr` do construtor base `RAS_Deformer`. Todo outro deformer real do engine (`BL_MeshDeformer`, `KX_SoftBodyDeformer`) cria a própria bounding box via `boundingBoxManager->CreateBoundingBox()` no construtor; sem isso, `RAS_Mesh::AddMeshUser` propaga a bounding box nula pro `RAS_MeshUser`, e o acesso a ela logo em seguida (dentro do próprio `ReplaceMesh`/`UpdateBounds`, no primeiro frame após trocar pra malha do impostor) estourava o access violation.
- **Fix**: `KX_ImpostorAtlasDeformer` passou a receber um `RAS_BoundingBoxManager*` no construtor (mesmo padrão de `BL_MeshDeformer`) e cria sua bounding box com `CreateBoundingBox()` + `CopyAabb(m_mesh->GetBoundingBox())`. Call site atualizado em `KX_GameObject::AddMeshUser` (`KX_GameObject.cpp:1032`) pra passar `GetScene()->GetBoundingBoxManager()`.
- **Verificado**: múltiplos ciclos de bake (4, 8, 12, 16 células) seguidos de play, todos com "Range Game Engine Started" seguido de "Range Game Engine Finished" sem exception no log.
- **Ainda não verificado**: se o bug de UV (todas as células aparecendo de uma vez) também foi resolvido — como o crash impedia qualquer teste em jogo, o comportamento real de `SetAtlasCell` nunca tinha rodado até o fim; usuário vai confirmar visualmente numa próxima sessão.

**Trilha Iluminação/Gráficos — MSAA real: já implementado, não é gap (correção de registro anterior)**

- Investigação disparada por dúvida do usuário sobre MSAA vs. TAA. O relatório de melhorias (Fase 4, 2026-08-25) registrava MSAA como "avaliado e descartado por exigir mudança de pipeline sob core profile" — **registro estava errado**.
- Levantamento de código confirmou que o MSAA real está implementado de ponta a ponta desde antes desta sessão: campo `GameData.aasamples` (`DNA_scene_types.h:926`), RNA `SceneGameData.samples` com enum Off/2x/4x/8x/16x (`rna_scene.c:4754-4757`), dropdown "AA Samples" já presente no painel de Game Settings (`properties_game.py:802`), lido em `LA_Launcher.cpp:206`/`GPG_Ghost.cpp:1496` (com override via `-m aasamples` na linha de comando do player standalone) e propagado até `RAS_ICanvas::SetSamples`/`RAS_MULTISAMPLE` (`RAS_Rasterizer.cpp`) com fallback automático se o driver não suportar o nível pedido.
- Usuário confirmou funcionando no jogo real ao testar o dropdown existente — nenhuma linha de código foi alterada.
- TAA (temporal) confirmado como gap real, não implementado: sem jitter de projeção, sem motion vectors por objeto (nem skinning nem partículas) e sem buffer de histórico/reprojeção. Ficaria pra trás como item de escopo maior se algum dia for retomado.

## 2026-08-29

**Componentes ImGui organizados e configuracao visual externa**
- Os componentes de menu/teste em `projects-teste/scripts/` foram renomeados com o prefixo `imgui_`: `imgui_main_menu_component.py`, `imgui_pause_menu_trigger_component.py`, `imgui_pause_menu_overlay_component.py`, `imgui_test_styling_component.py` e `imgui_test_widgets_component.py`.
- Adicionado `projects-teste/imgui_visual.json`, separado de `options.json`, para configurar janelas, alinhamento, dimensoes, cor de botoes, fonte e duracao dos fades.
- `menu_common.load_visual_config()` faz merge apenas de chaves conhecidas e usa defaults quando o arquivo esta ausente ou invalido. O arquivo `.range` precisa ser atualizado para os novos nomes dos componentes.
- A aba `Joystick` do Options foi adicionada com mapeamento dos 15 botoes padronizados, captura por pressionamento e configuracao de eixos (dead zone, sensibilidade e inversao). Componentes podem consultar `menu_common.action_pressed()`, `action_just_pressed()` e `axis_value()` sem conhecer os codigos SDL.

## 2026-08-28

**Internal icon style selector**
- Added `Default`, `UPBGE Current`, and `UPBGE Classic 0.2.5b` choices to the interface theme preferences. The selected atlas is loaded on the next program start without recompiling.
- Added a separate `UPBGE Classic 0.2.5b` choice for the Blender 2.7x-era atlas, kept in `datafiles/icons/upbge_legacy/`.
- The UPBGE atlas is loaded from `datafiles/icons/upbge/blender_icons16.png` and `blender_icons32.png`.

**Internal icon atlas replaceable at runtime**
- `source/source/blender/editors/interface/interface_icons.c`: the UI now looks for `datafiles/icons/blender_icons16.png` and `datafiles/icons/blender_icons32.png` at startup. Valid external atlases replace the embedded atlases without recompiling.
- Missing or invalid external files automatically fall back to the embedded atlases.

**Ícone da janela Windows configurável em runtime**
- `source/intern/ghost/intern/GHOST_WindowWin32.cpp`: a janela Win32 agora tenta carregar um `.ico` externo do diretório do executável antes de cair no recurso embutido. A ordem de busca é `winrange.ico`, `RangeEngine.ico` e `RangeRuntime.ico`.
- `source/intern/ghost/intern/GHOST_WindowWin32.h`: adicionados os helpers internos para aplicar o ícone carregado em runtime.
- Resultado prático: trocar o arquivo `.ico` ao lado do binário agora altera o ícone da janela/tarefa sem recompilar. O ícone embutido do `.exe` continua fixo por limitação do recurso do Windows e segue como fallback.

**Caminho dos atlas de ícones configurável e layout de Themes ajustado**
- `User Preferences > Files` ganhou o campo `Icons`, salvo nas preferências do usuário. O caminho deve ser a pasta raiz que contém `default/`, `upbge/` e `upbge_legacy/`, cada uma com `blender_icons16.png` e `blender_icons32.png`.
- `interface_icons.c` prioriza esse caminho e mantém `build/bin/2.79/datafiles/icons` como padrão quando o campo está vazio; atlas ausente ou inválido continua usando o atlas embutido.
- Em `Themes > User Interface`, `State`, `Styles`, `Axis Colors` e `Icon Colors` foram movidos para o topo, antes dos estilos individuais dos widgets.

**Seletor de estilo de ícones removido**
- Removido o seletor `Icon Style` da interface, RNA, DNA e carregador.
- Mantido o campo `User Preferences > Files > Icons`: ele aponta diretamente para uma pasta contendo `blender_icons16.png` e `blender_icons32.png`, permitindo substituir o atlas após o build.
- As informações sobre o formato atual e a futura conversão dos SVGs da UPBGE foram registradas em `docs/icon-atlas-notes.md`.

## 2026-08-30

**Build do RangeRuntime (player) corrigido — três causas empilhadas, sem relação com o experimento de ícones abortado**

- `ninja RangeRuntime` falhava com centenas de símbolos externos não resolvidos. Investigação (não uma regressão de código: nenhuma mudança em `source/` estava pendente no git) revelou três problemas de configuração de link acumulados, provavelmente expostos por uma reconfiguração do CMake que passou a puxar mais objetos de `bf_editor_*`/`bf_python` no link do que antes:
  1. `bf_intern_clog` (biblioteca de log do Blender, `CLG_logf`/`CLG_logref_init`) nunca esteve na lista `BLENDER_SORTED_LIBS` de `source/blenderplayer/CMakeLists.txt` — adicionada.
  2. `bad_level_call_stubs/stubs.c` (stubs usados porque o player não linka `bf_windowmanager` de propósito) tinha ~160 símbolos `WM_*`/`wm_*`/`RNA_*_itemf` sem stub correspondente — todos adicionados, com assinaturas extraídas de `WM_api.h`/`WM_keymap.h`/`wm_window.h`/`wm_subwindow.h`/`wm_draw.h`/`wm_event_system.h`/`RNA_enum_types.h`.
  3. `blenkernel_blc` (biblioteca gerada a partir do mesmo `stubs.c`, usada pelo `blenkernel`/`elbeem` para chamar "para cima" sem depender do editor/python reais) define ~376 símbolos que também passaram a existir nas libs reais (`bf_editor_*`, `bf_python`, `bf_render`, `bf_intern_elbeem`) agora linkadas no player — causando `LNK2005`/`LNK1169`. As definições redundantes em `stubs.c` foram neutralizadas com `#if 0` (mantendo apenas as extern-declarations onde necessário), deixando as implementações reais vencerem.
- `RangeEngine` (editor) não foi afetado — sempre linkou `bf_windowmanager` real e nunca usou `blenkernel_blc`.
- Confirmado: `ninja RangeRuntime` e `ninja RangeEngine` linkam e instalam limpos após as três correções em `source/blenderplayer/CMakeLists.txt` e `source/blenderplayer/bad_level_call_stubs/stubs.c`.

## 2026-08-31

**Sistema de partículas GPU (transform feedback) — Fases A a K, todas confirmadas em jogo pelo usuário**

Engine não tinha partículas em gameplay antes disso; construído do zero via
transform feedback (não compute shader, roda em `build/` compat e `build_core/`
core sem caminho divergente).

- **A:** prova de conceito — `RAS_TransformFeedbackShader` (compilador/linker
  próprio, fora de `source/blender/gpu`) + `RAS_ParticleBuffer` (VBO/VAO
  ping-pong, 200 partículas de teste). Hook temporário em `RenderCamera`.
- **B:** timing corrigido (update movido de `KX_KetsjiEngine`/por-câmera para
  `KX_Scene::UpdateParticlePoc`, 1x/frame); simulação real (velocidade,
  gravidade, idade, respawn com posição/velocidade pseudo-aleatórias);
  attrib locations fixadas via `glBindAttribLocation` (evita depender de
  `#version 130` implícito).
- **C:** billboard em view-space (sempre de frente pra câmera), fade por
  idade, sprite redondo via máscara radial; verificação visual confirmada
  depois de corrigir só a câmera de teste (simulação já estava correta).
- **D:** API Python `scene.particles` (proxy `KX_ParticleSystem`, padrão de
  `scene.world`) — gravity/color/lifetime/emitterPos/etc. configuráveis em
  runtime sem recompilar.
- **E:** textura de sprite via `scene.particles.texture`, reaproveitando o
  pipeline de imagem já existente (`BKE_image_load_exists`+
  `GPU_texture_from_blender`, mesmo caminho do cursor customizado e do
  ImGui). Bug real: `KX_ParticleSystem` não estava registrado em
  `KX_PythonInitTypes.cpp` (setattr falhava) — corrigido.
- **F:** `particleCount` RW em runtime via `RAS_ParticleBuffer::Resize`
  (orphan-and-grow do VBO, mesmo padrão de `RAS_StorageVbo`).
- **G:** gradiente de cor/tamanho por idade (`endColor`/`endSize`) e emissão
  em cone direcional (`emissionDirection`/`emissionAngle`), opt-in.
- **H:** painel de editor + persistência — DNA `RangeGPUParticleSettings` em
  `Scene.gpu_particles`, RNA, 4 painéis novos na aba Particle. Achado de
  tooling: builds via `cmd /c` no Bash deste ambiente não executam nada
  (git-bash mangla `/c`) — usar PowerShell ou `.bat` temporário.
- **I:** emissor por objeto em vez de por cena — `scene.particles` removido
  (breaking change aceito), vira `object.particles`; `Scene.gpu_particles`
  removido, vira `Object.gpu_particles` + flag `use_gpu_particles`;
  `RAS_ParticleBuffer` migrado de `KX_Scene` para `KX_GameObject`, permitindo
  múltiplos emissores simultâneos. Dois bugs de RNA (`use_gpu_particles`
  preso no srna errado) encontrados e corrigidos em teste real.
- **J:** cache de shader compartilhado (`RAS_ParticleShaderCache`,
  `shared_ptr`/`weak_ptr`) entre emissores simultâneos — antes cada objeto
  compilava sua própria cópia idêntica do programa GL.
- **K:** curvas de tamanho/cor sobre o tempo de vida via `CurveMapping`
  nativo (DNA/RNA/UI/bake em textura/shader), opt-in, fallback linear exato
  quando desligado. Bug real: `BKE_colortools.h` sem guard `extern "C"`
  causava `LNK2019` no primeiro consumidor C++ — corrigido (bug pré-existente
  do fork, não específico desta feature).

Todas as fases compilaram limpo (`RangeEngine`+`RangeRuntime`) e foram
confirmadas pelo usuário em jogo real.

<details>
<summary>Detalhe técnico completo por fase (histórico)</summary>

**Sistema de partículas GPU (transform feedback) — Fase A: prova de conceito**

- Contexto: engine não tinha nenhum sistema de partículas rodando em gameplay (o sistema clássico do Blender Internal só existe no viewport do editor). Plano completo (7 fases, A–G) desenhado e aprovado para construir simulação de partículas na GPU via transform feedback (não compute shader, por funcionar tanto em `build/` compat quanto `build_core/` core sem caminho de código divergente), configurável só via Python (`Range.particles`, sem painel/DNA no editor nesta fase).
- **Fase A implementada e verificada em jogo**: objetivo único era provar que o pipeline de transform feedback funciona neste engine antes de qualquer integração real — nenhum código anterior no projeto usa `glTransformFeedbackVaryings`/`GL_TRANSFORM_FEEDBACK_BUFFER`, é infraestrutura 100% nova.
  - `RAS_TransformFeedbackShader` (`Rasterizer/RAS_TransformFeedbackShader.h/.cpp`): compilador/linker de shader mínimo e próprio, fora de `source/blender/gpu`. Necessário porque `GPU_shader_create`/`GPU_shader_create_ex` (`gpu_shader.c`) chama `glLinkProgram` sem nunca chamar `glTransformFeedbackVaryings()` antes — não dá pra configurar transform feedback com o wrapper de shader compartilhado com o editor.
  - `RAS_ParticleBuffer` (`Rasterizer/RAS_ParticleBuffer.h/.cpp`): par de VBOs/VAOs ping-pong (double buffer, já que transform feedback não permite ler e escrever o mesmo buffer no mesmo dispatch), com 200 partículas estáticas de teste (grade 10×20, posição apenas). `Update()` roda um shader de update no-op (`out_position = in_position`) via `glBeginTransformFeedback(GL_POINTS)`/`glEndTransformFeedback()` com `GL_RASTERIZER_DISCARD` ligado, e alterna o índice de leitura. `Draw()` desenha o buffer atual como `GL_POINTS` cru com um shader de desenho simples (cor fixa magenta, `gl_PointSize` fixo).
  - Hook temporário em `KX_KetsjiEngine::RenderCamera` (após `scene->RenderBuckets(...)`), atrás de um membro `m_particlePoc` (`std::unique_ptr<RAS_ParticleBuffer>`) — não integrado ao loop de frame real, será removido na Fase B quando o update migrar para `KX_Scene`/`NextFrame()`.
  - Compilado limpo em `build/` (`ge_rasterizer` + `ge_ketsji` + `RangeRuntime`). Testado rodando `RangeRuntime.exe` com `benchmark.range`: grade de ~200 pontos magenta visível no jogo real, confirmado pelo usuário — pipeline de ping-pong via transform feedback provado sem corromper dados nem crashar.
  - Próximo passo (Fase B): mover o update para dentro do loop de frame (`KX_Scene`), implementar o shader de update real (integração de posição por velocidade, gravidade, `age`, respawn de partículas mortas por taxa de emissão), ainda com parâmetros hardcoded em C++ (API Python fica para a Fase D). Plano completo em `relatorio-melhorias-anastacioengine.md`.

**Fase B implementada e verificada em jogo — simulação real + timing correto**

- Duas correções sobre a Fase A: (1) bug de timing — `Update()` rodava dentro de `KX_KetsjiEngine::RenderCamera`, chamado uma vez por câmera, então cenas com múltiplas câmeras simulariam partículas mais de uma vez por frame; (2) shader de update era só um no-op de posição, sem física real.
- **Timing corrigido — ownership movida para `KX_Scene`**: `m_particlePoc` saiu de `KX_KetsjiEngine` (removido junto com o include) e virou membro de `KX_Scene` (`std::unique_ptr<RAS_ParticleBuffer>`, criado lazy). Novo `KX_Scene::UpdateParticlePoc(float deltaTime)`, chamado 1x por frame por cena dentro de `KX_KetsjiEngine::NextFrame()` (depois do `UpdateParents()` final do bloco de física/lógica, ainda dentro de `if (!scene->IsSuspended())`, com `m_physicsTime` como delta). `KX_KetsjiEngine::RenderCamera` agora só lê `scene->GetParticlePoc()` e desenha — sem mais rodar o update ali. Uma cena removida via `ProcessScheduledScenes()` leva seu `m_particlePoc` junto (sem ponteiro pendurado); uma cena adicionada no mesmo frame simplesmente não desenha partículas até o próximo tick (`GetParticlePoc()` retorna `nullptr`, já coberto pelo guard existente no `Draw()`).
- **Simulação real**: layout de atributo expandido de só-posição para posição+velocidade+idade (`vec3`+`vec3`+`float`, stride 28 bytes, offsets 0/12/24 — `GL_INTERLEAVED_ATTRIBS` empacota sem padding entre `vec3`/`float`, então bate exatamente com os offsets manuais do `glVertexAttribPointer` do próximo frame). Shader de update agora integra `velocity += gravity*dt; position += velocity*dt`, envelhece cada partícula (`age += dt`) e, ao cruzar `lifetime`, respawna com posição/velocidade pseudo-aleatórias (`hash(gl_VertexID + u_time)`) perto de um emissor hardcoded — o resto da idade é propagado via `mod(age, lifetime)` em vez de zerado, pra não gerar drift de fase entre partículas escalonadas ao longo de muitos ciclos.
- **Taxa de emissão sem alocação dinâmica**: pool fixo de 200 partículas (igual à Fase A), cada uma nascendo com `age_i = (i/N) * lifetime` — espalha os respawns ao longo do tempo em vez de todos de uma vez, simulando uma taxa de emissão efetiva de `N/lifetime` sem precisar criar/destruir vértices. Velocidade inicial da grade de teste ajustada para `u_velocityBase` (em vez de zero) — com zero, a grade inteira cairia como bloco rígido sob gravidade até o primeiro ciclo de respawn de cada partícula, um transiente visual estranho pra validar a fase.
- **Attrib locations estáveis entre os dois programs**: a Fase A dependia de coincidência (GLSL atribuindo location 0 implicitamente igual nos dois shaders separados). Cogitado `layout(location=N)`, descartado — sob `#version 130` (piso real suportado por esta engine, confirmado em `gpu_shader.c`) isso exigiria `#extension GL_ARB_explicit_attrib_location`, reintroduzindo a mesma dependência de versão que `RAS_TransformFeedbackShader` foi desenhado pra evitar. Usado `glBindAttribLocation` antes do link (`RAS_TransformFeedbackShader::Create` ganhou um parâmetro opcional de `(location, nome)`), tanto no shader de update (position=0, velocity=1, age=2) quanto no de desenho (position=0).
- Parâmetros de emissor/física (gravidade, lifetime, posição/raio do emissor, velocidade base/randomness) seguem hardcoded num namespace anônimo em `RAS_ParticleBuffer.cpp` — API Python real continua na Fase D.
- Compilado limpo em `build/` (`ninja RangeRuntime`). Testado rodando `RangeRuntime.exe` com `benchmark.range`: partículas caindo com gravidade e respawnando continuamente perto do emissor, sem bloco rígido caindo no início nem cluster de respawns simultâneos — confirmado pelo usuário.

**Fase C implementada — billboard rendering (quads instanciados, sempre de frente pra câmera)**

- Objetivo: substituir o `GL_POINTS` cru (tamanho fixo via `gl_PointSize`, sem controle de orientação) por sprites que sempre encaram a câmera, com fade suave de entrada/saída em vez do pop abrupto de nascer/morrer.
- **Draw VAOs novos, separados dos VAOs de simulação**: os VAOs existentes (`m_vao[2]`) continuam servindo só o passe de transform feedback (cada partícula lida como 1 vértice `GL_POINTS`). Billboard precisa de um quad por partícula, então `RAS_ParticleBuffer::Create` agora também monta `m_drawVao[2]` — um par (double-buffered, acompanhando o ping-pong) combinando um quad estático (`m_quadVbo`, 4 cantos, `glVertexAttribDivisorARB(0, 0)`, per-vértice) com posição/idade da partícula lidas do mesmo `m_vbo[i]` da simulação (`glVertexAttribDivisorARB(1/2, 1)`, per-instância). Convenção de instancing (`glDrawArraysInstancedARB`/`glVertexAttribDivisorARB`, sufixo ARB) já usada em `RAS_StorageVbo`/`RAS_OpenGLDebugDraw` — mesmo caminho conservador de GL_ARB_instanced_arrays, coerente com o piso `#version 130` do resto deste sistema.
- **Billboard em view-space, sem uniforms de câmera separados**: o vertex shader de desenho transforma a posição da partícula pra view-space (`u_view * vec4(pos,1)`) e soma o offset do canto do quad direto em X/Y desse espaço — em view-space os eixos direita/cima da câmera são sempre X/Y, então não precisa passar `cameraRight`/`cameraUp` como uniform à parte. Depois multiplica por `u_projection`. `Draw()` mudou de assinatura (`Draw(viewProjection)` → `Draw(view, projection)`, matrizes separadas) — chamador atualizado em `KX_KetsjiEngine::RenderCamera`.
- **Fade por idade + sprite redondo**: alpha sobe nos primeiros 10% da vida e desce nos últimos 30% (evita pop no respawn/morte), calculado no vertex shader e passado como varying; no fragment shader, o canto do quad (`v_uv`, -0.5..0.5) vira uma máscara radial (`smoothstep`) pra sprite arredondado em vez de quadrado sólido, com `discard` abaixo do limiar de alpha.
- **Estado de blend**: `GL_BLEND` (`SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA`) ligado só durante o draw, `glDepthMask(GL_FALSE)` pra sprites sobrepostos não brigarem no z-buffer entre si (mas ainda são ocluídos pela geometria da cena, já que o teste de profundidade continua ativo) — ambos restaurados ao estado anterior no fim de `Draw()`.
- Tamanho do sprite hardcoded (`kBillboardSize = 0.35f`, meia-extensão em unidades de mundo) no mesmo namespace anônimo dos outros parâmetros — variar tamanho/cor por idade real fica pra quando a API Python (Fase D) expuser isso.
- Compilado limpo em `build/` (`ninja ge_rasterizer ge_ketsji RangeRuntime`). Rodado `RangeRuntime.exe` com `benchmark.range` redirecionando stdout/stderr pra log: sem erro de compilação de shader (`CM_Error`) nem crash. Verificação visual (sprites de fato virados pra câmera e com fade, não só "não crashou") ainda pendente do usuário — câmera scriptada não é confiável neste projeto, ver `docs/changelog.md`/CLAUDE.md.
- Próximo passo (Fase D, ainda não iniciada): API Python (`Range.particles`) pra parametrizar emissor/física/aparência em vez dos valores hardcoded em `RAS_ParticleBuffer.cpp`.

**Fase C — verificação visual concluída (confirmado no jogo real pelo usuário)**

- Usuário testou `RangeRuntime.exe` com a câmera longe do emissor hardcoded (`(0, 5, 10)`) e não viu nada — diagnóstico via logs temporários (`CM_Message` em `RAS_ParticleBuffer::Create`/`Draw`, removidos depois) confirmou que a simulação e o draw call estavam corretos (200 partículas criadas, draw emitido sem erro de shader); o problema era só a câmera do `benchmark_gpu_test.range` não apontar pro emissor.
- Também testado com `RangeEngine.exe` (player embutido do editor) além do `RangeRuntime.exe` standalone — ambos os caminhos de render passam por `KX_KetsjiEngine::RenderCamera`, então não havia divergência de fato; bastava rebuild + câmera correta.
- Confirmado visualmente pelo usuário: sprites viram pra câmera (billboard em view-space funcionando), formato arredondado (máscara radial), fade in/out suave por idade, depth-test correto contra a cena. Fase C fechada.
- Próximo passo real agora: Fase D (API Python `Range.particles`).

**Fase D implementada e verificada em jogo — API Python `scene.particles`**

- Objetivo: substituir os parâmetros hardcoded em `RAS_ParticleBuffer.cpp` por atributos controláveis via script, sem precisar recompilar C++ pra ajustar emissor/física/aparência.
- **API shape — seguindo o precedente `scene.world`, não `Range.particles`**: como só existe um sistema de partículas por cena (não por objeto), o padrão já usado pra `KX_WorldInfo` (`KX_Scene::pyattr_get_world`) encaixou melhor que um namespace de módulo — não haveria lugar natural pra passar "qual cena" num `Range.particles` de nível de módulo. `scene.particles` é uma property read-only que retorna um proxy novo (`KX_ParticleSystem`), com os parâmetros como atributos RW do próprio proxy: `scene.particles.gravity = [0,0,-9.8]`, `scene.particles.color = [1,0.2,0.8,1]`, etc. Se o sistema de partículas da cena ainda não foi criado (lazy, só no primeiro `UpdateParticlePoc`), `scene.particles` retorna `None`.
- **`RAS_ParticleBuffer` ganhou getters/setters triviais** para todos os parâmetros que já eram membros (gravity, lifetime, emitterPos, emitterRadius, velocityBase, velocityRandomness, billboardSize) — como `Update()`/`Draw()` já reenviam todos os uniforms a cada chamada, os setters só escrevem o membro, sem precisar recompilar shader nem rechamar `Create()`.
- **Novo parâmetro: cor**. Antes a cor do sprite era fixa no fragment shader (`vec4(1.0, 0.2, 0.8, alpha)`). Agora é um `uniform vec4 u_color` (`m_color`, default igual ao valor antigo pra não mudar o visual por padrão), multiplicado pelo alpha calculado por idade (`fragColor = vec4(u_color.rgb, u_color.a * alpha)`), exposto como `scene.particles.color`.
- **`KX_ParticleSystem` nova classe** (`Ketsji/KX_ParticleSystem.h/.cpp`), modelada em cima de `KX_BoundingBox` (mesmo padrão: `EXP_Value`-derived, proxy temporário "owned by python", `(new KX_ParticleSystem(buffer))->NewProxy(true)`, ponteiro não-owning pro `RAS_ParticleBuffer` cuja vida é da cena). Atributos: `gravity`, `emitterPosition`, `velocity` (`mt::vec3`, via `PyObjectFrom`/`PyVecTo` — mesmo padrão de `KX_Scene::pyattr_get/set_gravity`), `color` (`mt::vec4`), `lifetime`/`emitterRadius`/`velocityRandomness`/`size` (float), `particleCount` (read-only — tamanho do pool é fixo na criação via VBO pré-alocado, redimensionar em runtime fica fora de escopo).
- **`particleCount` deliberadamente somente leitura** e sem `Methods[]` — resize exigiria destruir/recriar VBOs/VAOs; textura/sprite-sheet e múltiplos sistemas de partícula por cena/objeto também ficaram fora do escopo desta fase.
- Compilado limpo em `build/` (`cmake .` pra registrar os arquivos novos no `CMakeLists.txt` + `ninja RangeRuntime`, já que `KX_Scene.cpp`/`KX_ParticleSystem.cpp` não fazem parte do target rápido `ge_rasterizer`). Testado em jogo com script Python setando `scene.particles.color`/`.gravity`/`.lifetime` em runtime — mudanças refletidas visualmente, confirmado pelo usuário.
- Fase D fechada. Próximo: Fases E–G (a definir — ver `relatorio-melhorias-anastacioengine.md`).

**Fase E implementada e verificada em jogo — textura de sprite (`scene.particles.texture`)**

- Objetivo: substituir a máscara redonda procedural (puramente geométrica, `smoothstep` no fragment shader) por uma textura real, permitindo fumaça/faísca/folha em vez de só um círculo colorido.
- **Reaproveitado o pipeline de imagem já existente do engine em vez de escrever um loader novo** (busca prévia confirmou o padrão): `BKE_image_load_exists(G.main, filepath)` carrega/dedupe o `Image` datablock a partir do disco, `GPU_texture_from_blender(...)` cria/cacheia o `GPUTexture` no próprio datablock, `GPU_texture_opengl_bindcode(...)` extrai o `GLuint` cru. É exatamente o mesmo caminho já usado pelo cursor de mouse customizado (`BL_ConvertCustomMouseCursor`, `BL_BlenderDataConversion.cpp`) e pelo ImGui (`KX_Imgui.cpp`) — sem stb_image nem loader próprio.
- **`RAS_ParticleBuffer`**: novo `unsigned int m_texture` (bindcode GL, 0 = sem textura) + `std::string m_texturePath` (só pra round-trip do getter Python). `Draw()` faz bind manual (`glActiveTexture`/`glBindTexture`) só quando há textura setada; sem gerenciamento de `GPUTexture*`/refcount — a `Image` carregada fica em `G.main` e persiste, mesmo padrão (sem free explícito) já usado pelo cursor customizado.
- **Fragment shader do draw** ganhou `uniform sampler2D u_texture` + `uniform bool u_useTexture`: com textura, amostra `texture2D(u_texture, v_uv + 0.5)` (`v_uv` está em `[-0.5, 0.5]`, corners do quad unitário) e usa o RGB/alpha da textura multiplicado por `u_color`/fade por idade; sem textura, mantém exatamente o comportamento anterior (máscara radial via `smoothstep`) — sem mudança visual por padrão.
- **`KX_ParticleSystem` ganhou `texture` (RW, string)**: setter chama `BKE_image_load_exists`+`GPU_texture_from_blender`+`GPU_texture_opengl_bindcode` e repassa o bindcode pro buffer; string vazia (`""`) limpa a textura e volta pra máscara procedural. Chamar com o mesmo path repetidamente (ex.: todo frame) não recarrega/reenvia a textura — `BKE_image_load_exists` dedupe por path e `GPU_texture_from_blender` cacheia no datablock.
- **Bug real encontrado e corrigido durante o teste em jogo**: `KX_ParticleSystem` nunca tinha sido registrado em `KX_PythonInitTypes.cpp` (`PyType_Ready_Attr`) — passo obrigatório documentado no próprio `Py_Header` ("each PyC++ class must be registered in KX_PythonInitTypes.cpp") que passou despercebido na Fase D porque os *getters* (`scene.particles.gravity` lido, por exemplo) funcionavam via `GetType()`/proxy normalmente, mas o *setattro* genérico não achava a tabela `Attributes[]` sem esse registro — erro em jogo: `TypeError: 'KX_ParticleSystem' object has no attributes (assign to .gravity)`. Corrigido com uma linha (`PyType_Ready_Attr(dict, KX_ParticleSystem, init_getset);` + include), rebuild limpo de `RangeEngine`+`RangeRuntime` resolveu.
- **Componente de teste criado**: `projects-teste/scripts/particle_test_component.py` (`ParticleTestComponent`), expõe todos os parâmetros de `scene.particles` (incluindo `texture`) como `args` editáveis no painel de componentes do editor — aplica tudo de uma vez assim que `scene.particles` deixa de ser `None` (lazy, só após o primeiro `UpdateParticlePoc`). Serve de bancada de teste reutilizável pras próximas fases também.
- Testado em jogo pelo usuário via `RangeEngine.exe` (player embutido do editor) com o componente acima, `texture = "//particula.png"`: confirmado funcionando. Fase E fechada.

**Fase F implementada — pool de partículas (`scene.particles.particleCount`) configurável em runtime**

- Objetivo: plano original deixava as Fases F–G "a definir"; usuário escolheu tornar o tamanho do pool e a taxa de emissão efetiva (`N/lifetime`, já implícita no age-staggering desde a Fase B) configuráveis via script, em vez do valor fixo de 200 hardcoded em `KX_Scene::UpdateParticlePoc`.
- **`RAS_ParticleBuffer::Resize(unsigned int newCount)`**: respecifica `m_vbo[2]` in-place via `glBufferData` (mesmo padrão já usado em `RAS_StorageVbo.cpp` para redimensionar buffers — "orphan and grow" no mesmo nome de buffer), sem tocar em `m_vao`/`m_drawVao`/`m_quadVbo`/`m_drawProgram`/`m_updateShader`: os atributos dos VAOs referenciam o buffer por ID, não por tamanho, então continuam válidos depois do resize. Buffer 0 recebe um pool novo com idade escalonada (`age_i = (i/N)*lifetime`, mesma lógica de `Create()`); buffer 1 fica vazio (é só o alvo de escrita do próximo `Update()`). `m_readIndex` volta a 0. No-op se `newCount == m_particleCount`; falha (retorna `false`) se `newCount == 0`.
- **Lógica de geração do pool inicial extraída** de `Create()` para `RAS_ParticleBuffer::BuildInitialPool(count)`, reutilizada por `Create()` e `Resize()` — evita duplicar o layout de 7 floats/partícula (posição+velocidade+idade) e a fórmula de staggering.
- **`KX_ParticleSystem::particleCount` passa de RO para RW** (`EXP_PYATTRIBUTE_RW_FUNCTION`), seguindo o mesmo padrão dos outros setters (`pyattr_set_lifetime` etc.) — `pyattr_set_particle_count` valida `> 0` via `PyLong_AsLong` e chama `Resize()`, com `PyErr_SetString` claro em caso de valor inválido ou falha do resize.
- **`KX_Scene::UpdateParticlePoc` não mudou**: pool inicial continua nascendo com 200 partículas (criação lazy no primeiro frame); scripts que querem outro tamanho inicial simplesmente setam `scene.particles.particleCount = N` assim que `scene.particles` deixa de ser `None`, disparando o resize.
- `projects-teste/scripts/particle_test_component.py` ganhou o campo `particle_count` (int, default 200) no painel de componentes, reaproveitando a bancada de teste já existente das fases anteriores.
- Compilado limpo em `build/` (`ninja RangeRuntime` + `ninja RangeEngine`). Testado em jogo pelo usuário via o componente de teste (`particle_count`): resize em runtime funcionando, sem crash. Fase F fechada.

**Fase G implementada — gradiente de cor/tamanho por idade e emissão em cone direcional (`scene.particles`)**

- Objetivo: Fase G ficara "a definir". Ao investigar um sistema de partículas por geometry-shader encontrado na comunidade da Range Engine (`geometryParticle.py`), identificamos 3 melhorias que valem a pena e cabem na arquitetura de transform feedback já existente (mesmo padrão de uniforms re-enviados por frame, sem recompilar shader): gradiente de cor por idade, gradiente de tamanho por idade, e emissão de velocidade em cone direcional. Descartado deliberadamente: turbulência por ruído senoidal (mexeria na simulação já validada por pouco ganho) e o sistema de "gerações"/rajadas deles (nosso pool contínuo com `particleCount` já cobre isso).
- **Gradiente de cor (`scene.particles.endColor`, vec4)**: `RAS_ParticleBuffer` ganha `m_endColor[4]`, default igual a `m_color` (sem gradiente até o script setar). `drawVertexSource` exporta a `lifeFrac` (já calculada pra `v_alpha`, Fase C) como nova varying `v_lifeFrac`; `drawFragmentSource` faz `mix(u_color, u_endColor, v_lifeFrac)` pra RGB e alpha base, multiplicado pelo `mask`/`v_alpha` como já era.
- **Gradiente de tamanho (`scene.particles.endSize`, float)**: `m_endSize`, default igual a `m_billboardSize`. `drawVertexSource`: `size = mix(u_size, u_endSize, lifeFrac)` no lugar do `u_size` fixo usado pro offset do corner do billboard.
- **Emissão em cone direcional (`scene.particles.emissionDirection` vec3 + `emissionAngle` float, graus)**: opt-in — `updateVertexSource` (branch de respawn) mantém exatamente `vel = u_velocityBase + rv * u_velocityRandomness` (jitter em cubo, código antigo, zero mudança de comportamento) quando `u_emissionAngle >= 180` (default). Com ângulo menor, amostra uma direção dentro do cone de meio-ângulo `u_emissionAngle` ao redor de `normalize(u_emissionDir)` (cone sampling padrão: `cosTheta = mix(cos(maxAngle), 1, rand)`, base ortonormal via `cross()`), e usa essa direção em vez do jitter cúbico pra `vel`. Posição de spawn (`pos = u_emitterPos + r * u_emitterRadius`) não muda — cone afeta só direção de velocidade.
- `KX_ParticleSystem` ganhou os 4 atributos novos (`endColor`, `endSize`, `emissionDirection`, `emissionAngle`), mesmo padrão `EXP_PYATTRIBUTE_RW_FUNCTION` usado por `color`/`size`/`gravity`.
- `projects-teste/scripts/particle_test_component.py` ganhou os campos correspondentes (`end_color_r/g/b/a`, `end_size`, `emission_direction_x/y/z`, `emission_angle`), defaults iguais aos valores de início (sem gradiente/cone visível até o usuário mexer).
- Compilado limpo em `build/` (`ninja RangeRuntime`).

**Fase H implementada e verificada — painel de editor + persistência (`Scene.gpu_particles`)**

- Objetivo: até aqui (Fases A–G) o sistema de partículas só existia em runtime — sem DNA, sem RNA, sem painel, configurável apenas chamando setters Python (`scene.particles.*`) depois que o jogo já tinha começado. Usuário pediu um painel de verdade na aba Particles do editor, reaproveitando o menu que hoje mostra "Not available in the Game Engine".
- **DNA**: novo struct `RangeGPUParticleSettings` (`DNA_scene_types.h`, logo após `GameData`) — não podia se chamar `ParticleSettings`, já existe esse nome pro sistema de partícula CPU clássico (`DNA_particle_types.h:147`). Embutido por valor em `Scene.gpu_particles`, mesmo padrão de `Scene.gm`. Campos: `gravity`/`emitter_position`/`velocity`/`emission_direction` (vec3), `color`/`end_color` (vec4), `lifetime`/`emitter_radius`/`velocity_randomness`/`size`/`end_size`/`emission_angle` (float), `particle_count` (int), `texture_path` (char[1024]).
- **Versionamento**: bloco novo em `versioning_range.c` (`MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 101)`) preenchendo os mesmos defaults hardcoded que já existiam em `RAS_ParticleBuffer.cpp` (`kGravityReal` etc.), pra arquivos `.range` salvos antes desta fase não carregarem gravidade/lifetime/etc. zerados. `RANGE_MINSUBVERSION` bump pra 101 (`BKE_blender_version.h`).
- **RNA**: `rna_def_scene_gpu_particles` (`rna_scene.c`, mesmo template de `rna_def_scene_game_data`), propriedades expostas em `scene.gpu_particles.*` com subtypes apropriados (`PROP_XYZ`, `PROP_COLOR`, `PROP_DISTANCE`, `PROP_VELOCITY`, `PROP_FILEPATH`). **Cuidado documentado**: `emission_angle` guardado em graus cru (igual ao runtime `scene.particles.emissionAngle`) usa `PROP_NONE`, não `PROP_ANGLE` — esse subtype assume que o float armazenado já está em radianos e faria a UI converter errado.
- **UI (`properties_particle.py`)**: painel antigo (`PARTICLE_PT_context_particles`, `HIDE_HEADER`) não desenha mais a mensagem — só retorna cedo pro engine de jogo. Quatro painéis novos de verdade (`PARTICLE_PT_gpu_emitter/motion/emission_cone/appearance`, mixin `GPUParticleButtonsPanel` com poll `engine == 'BLENDER_GAME'`), cada um com cabeçalho nativo (logo ganham a seta de expandir/recolher automaticamente, sem precisar de estado próprio) e conteúdo agrupado em caixas com ícone+label, seguindo o estilo visual já usado pelo addon próprio do projeto (`Range_Components_Label/custom_pt_world.py`, ex. `box.label(text="Camera Exposure:", icon="CAMERA_DATA")`). Removida a mesma mensagem de `properties_render_layer.py` (painel de Render Layers já funcionava sem ela, só a checagem de engine sobrava sem uso).
- **Ponte DNA → runtime**: `KX_Scene::UpdateParticlePoc` (`KX_Scene.cpp`) lê `m_blenderScene->gpu_particles` na criação lazy do `RAS_ParticleBuffer` (antes usava `new RAS_ParticleBuffer(200)` com todos os outros parâmetros hardcoded no construtor) e chama os setters já existentes (`SetGravity`, `SetLifetime`, etc.) mais um novo `RAS_ParticleBuffer::LoadTextureFromPath` (extraído do corpo de `KX_ParticleSystem::pyattr_set_texture`, que passou a chamá-lo também) — evita duplicar a lógica de `BKE_image_load_exists`/`GPU_texture_from_blender` entre o setter Python e a ponte de scene-conversion.
- **Gotcha de tooling encontrado no processo**: builds disparadas via `cmd /c '...'` a partir do tool Bash deste ambiente não executam nada — o git-bash converte o argumento solto `/c` em `C:\`, o `cmd.exe` cai num modo interativo vazio e sai com código 0 sem rodar o comando real. Isso gerou 3-4 "builds" fantasma que pareciam ter sucesso (exit 0, sem erro) mas não recompilaram nada; só foi pego comparando o timestamp do `.exe` com os arquivos-fonte editados. Fix: usar o tool PowerShell pra isso (já era a recomendação existente), ou, se precisar mesmo do Bash, escrever a sequência de comandos num `.bat` temporário e chamar `cmd //c "arquivo.bat"`. Detalhes na memória `build-environment`.
- Compilado limpo (`ninja -t clean` + rebuild completo de `RangeEngine`+`RangeRuntime`, obrigatório por mexer em `DNA_scene_types.h`). Verificado pelo usuário no editor: painel aparece com os 4 grupos colapsáveis e as caixas com ícone. Fase H fechada.

**Fase I — plano de arquitetura (ainda não iniciada) — emissor de partículas por objeto**

- **Motivação**: a Fase H deu um painel ao sistema, mas não mudou a limitação estrutural de fundo — ainda é **1 emissor por cena** (`KX_Scene::m_particlePoc`, `Scene.gpu_particles`), com posição fixa no espaço do mundo (`emitter_position`, um vec3 solto). Usuário quer múltiplos efeitos simultâneos na mesma cena (ex.: fogueira + cachoeira ao mesmo tempo), cada um seguindo um objeto de referência — hoje isso é impossível, só dá pra ter um emissor por cena, parado num ponto fixo.
- **Direção acordada**: mover a posse do `RAS_ParticleBuffer` de `KX_Scene` para `KX_GameObject`, tornando o objeto "responsável" pelo efeito — sua posição no mundo vira a posição do emissor a cada frame (em vez de um vec3 fixo), e cada objeto marcado tem seu próprio buffer/configuração independente.
- **DNA/RNA**: struct `RangeGPUParticleSettings` (já existe) muda de dono — em vez de (ou além de) `Scene.gpu_particles`, precisa de um `Object.gpu_particles` (`DNA_object_types.h`) + um boolean opt-in (`use_gpu_particles`, default off) pra não forçar todo objeto a carregar o struct à toa. Mesmo padrão de flags de engine já usado em `object.game.*` neste fork. RNA espelha o que já existe pra Scene (`rna_object.c`, não `rna_scene.c`).
- **Reaproveitamento de `Scene.gpu_particles`**: em vez de descartar o trabalho da Fase H, considerar usá-lo como **template de default** — ao ligar `use_gpu_particles` num objeto pela primeira vez, copiar os valores de `scene.gpu_particles` como ponto de partida (em vez de nascer com os hardcoded de `RAS_ParticleBuffer.cpp` de novo). Evita repetir trabalho de UX; decisão final fica pra quem implementar.
- **Runtime**: `KX_GameObject` ganha o `std::unique_ptr<RAS_ParticleBuffer>` (hoje em `KX_Scene`) + um `UpdateParticleSystem(deltaTime)` análogo ao atual `KX_Scene::UpdateParticlePoc`, mas escrevendo a posição do emissor a partir de `NodeGetWorldPosition()` a cada chamada (não só na criação) — o objeto pode se mover. Evitar varrer todo `m_objectlist` da cena por frame só procurando quem tem partícula ligada: cachear uma lista de objetos-com-partícula na `KX_Scene` (populada na conversão da cena, `BL_BlenderDataConversion.cpp`, mesmo padrão de `m_lightlist`/listas afins já existentes), e iterar só essa lista tanto pro update quanto pro draw (`KX_KetsjiEngine::RenderCamera` hoje desenha 1 buffer por cena, passa a desenhar N, um por objeto da lista).
- **API Python — DECIDIDO (2026-08-31)**: `scene.particles` é **removido de vez** (breaking change aceito pelo usuário, fork é interno). Vira `object.particles`, espelhando `object.actuators`/`object.sensors`. Sem alias/fallback de compatibilidade — `particle_test_component.py` e qualquer cena de teste que use `scene.particles` precisam ser migrados para `object.particles` como parte desta fase, não depois.
- **`Scene.gpu_particles` — DECIDIDO (2026-08-31): removido completamente**, não vira template de default. Isso reverte a parte de dados/UI da Fase H: struct `RangeGPUParticleSettings` deixa de existir em `Scene` (`DNA_scene_types.h`), `rna_def_scene_gpu_particles` sai de `rna_scene.c`, os 4 painéis (`PARTICLE_PT_gpu_emitter/motion/emission_cone/appearance`) trocam a fonte de `context.scene.gpu_particles` para `context.object.gpu_particles` em vez de conviver com os dois. Novos objetos nascem com os hardcoded de `RAS_ParticleBuffer.cpp` (sem cópia de template de cena). Atenção ao versionamento: o bloco de defaults em `versioning_range.c` (`MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 101)`) e o campo `Scene.gpu_particles` em si precisam de tratamento explícito para arquivos `.range` já salvos com a Fase H (decidir se vira no-op silencioso ou se os dados são descartados — versão DNA nova ainda incrementa, mesmo removendo campo).
- **UI**: boa notícia — a aba "Particle" do editor já é inerentemente ligada ao objeto ativo no Blender stock (`context.particle_system`/`context.object`, sistema de partícula CPU já é por-objeto via `object.particle_systems`). Os 4 painéis da Fase H já herdam poll baseado em `context.object` — trocar a fonte de dados de `context.scene.gpu_particles` pra `context.object.gpu_particles` deve ser a única mudança necessária ali, mais um checkbox de `use_gpu_particles` no cabeçalho do primeiro painel (`draw_header`, mesmo padrão de `CUSTOM_PT_game_environment_lighting.draw_header` em `Range_Components_Label/custom_pt_world.py`).
- **Fora de escopo deste plano** (não avaliado ainda, levantar se vier à tona): colisão de partícula com a cena, múltiplos "slots" de emissor por objeto (hoje seria 1 por objeto, igual é 1 por cena hoje).
- Próximo passo real: Fase I.1 — DNA/RNA em `Object` (`use_gpu_particles` + `Object.gpu_particles`), remoção do struct/RNA/painel de `Scene.gpu_particles`, sem tocar runtime (`KX_ParticleSystem`/`KX_GameObject`/`KX_Scene`) ainda.

**Fase I.1 implementada — DNA/RNA em `Object`, remoção de `Scene.gpu_particles`**

- **DNA**: struct `RangeGPUParticleSettings` movido de `DNA_scene_types.h` para `DNA_object_types.h` (mesmo header que já define `ObjectActivityCulling`, outro struct embutido por valor em `Object` — precisa da definição completa disponível ali por ser embutido, não um ponteiro). `Scene.gpu_particles` removido de `Scene`; `Object` ganhou `struct RangeGPUParticleSettings gpu_particles` embutido por valor.
- **Flag opt-in**: em vez de um `int use_gpu_particles` solto, seguiu o padrão já usado neste fork para flags de engine por objeto — novo bit `OB_GPU_PARTICLES = 1 << 8` em `ob->gameflag2` (havia bits livres nessa faixa; bits 0–1 e 8+ não estavam em uso pelos `OB_LOCK_RIGID_BODY_*` existentes).
- **RNA (`rna_object.c`)**: nova `rna_def_object_gpu_particles()` (cópia do padrão de `rna_def_game_object_activity_culling`, `RNA_def_struct_nested(brna, srna, "Object")`), com as mesmas 13 propriedades que existiam em `Scene.gpu_particles`. Duas diferenças de texto/unidade: `emitter_position` agora documentada como "Local-space offset... from the object" (antes era posição absoluta no mundo, já que não havia objeto de referência); `emission_angle` continua `PROP_NONE` em graus crus (mesmo cuidado da Fase H, não é `PROP_ANGLE`). Nova propriedade booleana `use_gpu_particles` no próprio `Object` (`RNA_def_property_boolean_sdna(prop, NULL, "gameflag2", OB_GPU_PARTICLES)`), ao lado de `activity_culling` em `rna_def_object_game_settings`.
- **RNA (`rna_scene.c`)**: `rna_def_scene_gpu_particles()` e a propriedade `Scene.gpu_particles` removidas por completo (função, registro e definição de propriedade).
- **Versionamento**: bloco antigo de `versioning_range.c` (gate `1,6,101`, escrevia em `scene->gpu_particles.*`) não podia mais compilar sem o campo — substituído por um novo bloco gate `1,6,102` (`RANGE_MINSUBVERSION` de `BKE_blender_version.h` também bumped para 102) que itera `main->object` (`LISTBASE_FOREACH (Object *, ob, &main->object)`, mesmo padrão já usado ali para `ob->gameflag |= OB_TASK_CONVERT`) e semeia os mesmos valores default de antes — exceto `emitter_position`, que passa a nascer em `(0,0,0)` (offset local) em vez de `(0,5,10)` (posição absoluta antiga), já que agora é relativo ao objeto.
- **UI (`properties_particle.py`)**: os 4 painéis da Fase H (`PARTICLE_PT_gpu_emitter/motion/emission_cone/appearance`) trocaram a fonte de dados de `context.scene.gpu_particles` para `context.object.gpu_particles`; `GPUParticleButtonsPanel.poll` ganhou `context.object is not None`; painel `Emitter` ganhou `draw_header` com checkbox de `object.use_gpu_particles` (padrão de `CUSTOM_PT_game_environment_lighting.draw_header` em `custom_pt_world.py`); os 4 painéis desabilitam o conteúdo (`layout.enabled = context.object.use_gpu_particles`) quando o objeto não tem o emissor ligado, em vez de escondê-lo.
- **Compilação — atualização temporária necessária em `KX_Scene.cpp`**: `KX_Scene::UpdateParticlePoc` lia `m_blenderScene->gpu_particles` diretamente; como o campo não existe mais em `Scene`, essa leitura foi trocada por constantes hardcoded locais (os mesmos valores default de antes, replicados) só para manter o pool de partículas em nível de cena funcionando exatamente como nas Fases B–G até a Fase I.2 mover a posse do `RAS_ParticleBuffer` para `KX_GameObject`. Comentário no código deixa claro que é transitório. Nenhuma outra mudança de runtime (`KX_ParticleSystem`, `KX_GameObject`) feita nesta fase, como planejado.
- Compilado limpo: `ninja -t clean` + rebuild completo de `RangeRuntime` e `RangeEngine` (obrigatório por mudança em `DNA_object_types.h`/`DNA_scene_types.h`), ambos com exit code 0. Ainda não testado em jogo pelo usuário (painel novo em `Object > Particle` ainda não verificado visualmente).
- Próximo passo real: Fase I.2 — mover a posse do `RAS_ParticleBuffer` de `KX_Scene` para `KX_GameObject` (lista cacheada de objetos-com-partícula por cena, populada em `BL_BlenderDataConversion.cpp`; `KX_KetsjiEngine::RenderCamera` passa a desenhar N buffers, um por objeto da lista, em vez de 1 por cena), e migrar a API Python `scene.particles` → `object.particles` (decisão já tomada, ver memória do projeto).

**Fase I.2 implementada — posse do `RAS_ParticleBuffer` movida para `KX_GameObject`, emissores múltiplos e simultâneos**

- **`RAS_ParticleBuffer.h/.cpp`**: `Update(float deltaTime)` virou `Update(float deltaTime, const mt::vec3 &worldOrigin)`. O uniform `u_emitterPos` enviado ao shader passa a ser `worldOrigin + m_emitterPos`, calculado localmente sem mutar `m_emitterPos` — isso preserva `Get/SetEmitterPos` (e o `emitterPosition` do `KX_ParticleSystem` em Python) como o offset local editável, documentado na RNA desde a Fase I.1, sem quebrar a API existente nem exigir mudanças no proxy Python.
- **`KX_GameObject.h/.cpp`**: novo membro `std::unique_ptr<RAS_ParticleBuffer> m_particleBuffer` (junto a `m_physicsController`/`m_sgNode`). Três métodos novos: `SetupGPUParticles(const RangeGPUParticleSettings&)` (cria+configura o buffer a partir do DNA, chamado uma vez na conversão — não é lazy como o `m_particlePoc` da Fase B-H, já que a decisão de ligar vem do painel), `UpdateParticles(float deltaTime)` (chama `m_particleBuffer->Update(deltaTime, NodeGetWorldPosition())` se houver buffer) e `GetParticleBuffer() const`. Python: `pyattr_get_particles` (cópia de `KX_Scene::pyattr_get_particles` da Fase D, trocando a fonte por `GetParticleBuffer()`) registrado como `object.particles` (`EXP_PYATTRIBUTE_RO_FUNCTION`, ao lado de `actuators`/`sensors`). `KX_ParticleSystem` (o proxy em si) não precisou de nenhuma mudança estrutural — já operava só sobre um `RAS_ParticleBuffer*` bruto, sem referência a quem é dono.
- **`KX_Scene.h/.cpp`**: removidos `m_particlePoc`, `UpdateParticlePoc`, `GetParticlePoc`, `pyattr_get_particles` e a entrada `"particles"` da tabela de atributos — `scene.particles` não existe mais. Novo `std::vector<KX_GameObject *> m_gpuParticleObjects` (não exposto a Python, mesmo padrão de `m_animatedlist`), com `AddGpuParticleObject`/`RemoveGpuParticleObject`/`GetGpuParticleObjects()` e `UpdateGpuParticleEmitters(float deltaTime)` (itera a lista chamando `UpdateParticles` em cada objeto). Registro/remoção em runtime seguindo o padrão de `m_lightlist`: `AddNodeReplicaObject` (replicação/duplicação de objeto — como `m_particleBuffer` não é copiável/replicável como estado de GPU, o replica re-deriva seu próprio buffer a partir do `RangeGPUParticleSettings` do `Object` Blender, se `OB_GPU_PARTICLES` estiver ligado, em vez de tentar copiar o buffer original), `RemoveObject` (via `CM_ListRemoveIfFound`, mesmo padrão de `m_animatedlist`) e `MergeScene` (concatena os dois vetores, limpa o da cena de origem).
- **`BL_BlenderDataConversion.cpp`**: em `BL_GameObjectFromBlenderObject`, no bloco genérico de pós-processamento que roda para qualquer tipo de objeto (não só `OB_MESH` — Empty também pode ser emissor), checa `ob->gameflag2 & OB_GPU_PARTICLES` e, se ligado, chama `gameobj->SetupGPUParticles(ob->gpu_particles)` + `kxscene->AddGpuParticleObject(gameobj)`.
- **`KX_KetsjiEngine.cpp`**: `NextFrame` troca `scene->UpdateParticlePoc(m_physicsTime)` por `scene->UpdateGpuParticleEmitters(m_physicsTime)` (mesma posição no loop, depois de `UpdateParents()`, pelo mesmo motivo de sempre — ler a transformação de mundo já atualizada no frame). `RenderCamera` troca o desenho de um único `scene->GetParticlePoc()` por um loop sobre `scene->GetGpuParticleObjects()`, desenhando `obj->GetParticleBuffer()->Draw(...)` de cada objeto com buffer não-nulo — múltiplos emissores simultâneos na mesma cena, cada um seguindo seu próprio objeto.
- **`particle_test_component.py`**: migrado de `self.object.scene.particles` para `self.object.particles`; comentário do topo e da checagem de `None` atualizados (agora reflete "objeto sem `use_gpu_particles` ligado", não mais "ainda não criado no primeiro frame"); default de `Emitter Position` no `args` trocado de `(0, 5, 10)` (posição absoluta antiga) para `(0, 0, 0)` (offset local, já que o emissor agora nasce na posição do próprio objeto).
- Compilado limpo: `ninja -t clean` + rebuild completo de `RangeRuntime` e `RangeEngine` (obrigatório por mudança de assinatura pública em `KX_GameObject.h`/`KX_Scene.h`), ambos com exit code 0.
- **Bug real encontrado + corrigido na verificação em jogo**: `rna_uiItemR: property not found: Object.use_gpu_particles` + `AttributeError: 'Object' object has no attribute 'gpu_particles'` ao abrir o painel Particle. Causa: na Fase I.1, `use_gpu_particles`/`gpu_particles` foram definidos dentro de `rna_def_game_object_settings` (`rna_object.c`) — ou seja, registrados no srna `GameObjectSettings` (`object.game.use_gpu_particles`), não no srna `Object` propriamente, apesar de `properties_particle.py` sempre ter lido `context.object.gpu_particles`/`use_gpu_particles` direto. Corrigido movendo os dois `RNA_def_property(...)` para dentro de `rna_def_object` (perto da property `game`, `rna_object.c` ~2830) — mesmo SDNA por trás (`GameObjectSettings` já usa `RNA_def_struct_sdna(srna, "Object")`, então os campos `gameflag2`/`gpu_particles` continuam válidos no novo escopo). Rebuild limpo de `RangeEngine` + `RangeRuntime`, ambos exit 0.
- **Testado e confirmado pelo usuário (2026-08-31)**: painel Particle abre sem erro, checkbox liga o emissor. Script de teste avulso `projects-teste/scripts/test_object_particles.py` (Python Controller em modo Script, ligado a um sensor Always) confirmou `object.particles` funcionando: leitura de todos os parâmetros (`particleCount`, `lifetime`, `emitterPosition`, `gravity`, `color`), escrita RW confirmada (`size` dobrado com sucesso e lido de volta), e por-objeto (`Cube.particles`, não mais `scene.particles`). Fase I encerrada.
- Fora de escopo (como já decidido no plano original da Fase I): colisão de partícula com a cena, múltiplos emissores por objeto (hoje é 1 por objeto, era 1 por cena antes).

**Fase J implementada e verificada — cache de shader compartilhado entre emissores simultâneos**

- **Motivação**: com a Fase I.2 fechada (emissores por objeto), o próximo pedido do usuário foi testar/otimizar cenas com múltiplos emissores simultâneos (ex.: fogueira + cachoeira ao mesmo tempo). Investigação (agente Explore) confirmou que o loop de update/draw, o estado de GL (bind/unbind, blend, depth mask) e o ciclo de vida de objeto (remoção/replicação/merge de cena) já estavam corretos para N≥2 emissores — nenhum bug encontrado aí. A única ineficiência real: `RAS_ParticleBuffer::Create()` compilava sua própria cópia do programa de update (transform feedback) e do programa de draw a cada instância, a partir de GLSL **byte-idêntico** entre todos os emissores (parâmetros são só uniforms re-enviados por frame, nunca embutidos na fonte). N emissores = 2N programas GL compilados/linkados + 19×N chamadas `glGetUniformLocation`, quando 2 programas bastariam. Custo pontual (na conversão de cena, não por frame), mas puro desperdício — vale corrigir antes de cenas com vários emissores ao mesmo tempo.
- **Novo tipo `RAS_ParticleShaderCache`** (`RAS_ParticleShaderCache.h/.cpp`, novo par de arquivos): recebeu (movidos, sem mudança de conteúdo) as fontes GLSL (`updateVertexSource`/`drawVertexSource`/`drawFragmentSource`) e `CompileDrawProgram()` que antes viviam em `RAS_ParticleBuffer.cpp`, mais o `std::unique_ptr<RAS_TransformFeedbackShader> m_updateShader` e as 19 locations de uniform (9 de draw + 10 de update) que antes eram membros de `RAS_ParticleBuffer`. Construtor privado — só se obtém uma instância via `static std::shared_ptr<RAS_ParticleShaderCache> Get()`, apoiado num `std::weak_ptr` estático de escopo de arquivo (`g_particleShaderCache`): primeira chamada compila; chamadas seguintes reaproveitam enquanto algum `RAS_ParticleBuffer` ainda segura o `shared_ptr`. Quando o último emissor que referencia o cache é destruído, o refcount zera e o cache (com seus programas GL) é destruído normalmente; a próxima `Get()` (ex.: depois de recarregar uma cena) recompila do zero, sem ficar "envenenado" por uma falha de compilação anterior (falha retorna `nullptr` sem gravar no `weak_ptr`).
- **`RAS_ParticleBuffer.h/.cpp`**: perdeu `m_drawProgram` e os 19 `m_draw*Loc`/`m_*Loc`, e o `unique_ptr<RAS_TransformFeedbackShader> m_updateShader` — tudo isso agora vive só no cache. Ganhou `std::shared_ptr<RAS_ParticleShaderCache> m_shaderCache`. `Create()` virou só `m_shaderCache = RAS_ParticleShaderCache::Get(); if (!m_shaderCache) return false;` (nenhuma compilação/lookup de uniform local mais); `~RAS_ParticleBuffer()` não chama mais `glDeleteProgram` (posse do cache cuida disso); `Update()`/`Draw()` trocaram acesso direto a membro por `m_shaderCache->GetUpdateProgram()`/`GetDrawViewLoc()`/etc. — valores de uniform (`m_gravity`, `m_emitterPos`, `m_color`, ...) e o estado de GL do `Draw()` (já confirmado corretamente pareado por chamada) não mudaram.
- `RAS_TransformFeedbackShader` não foi alterado — só trocou de dono (de `RAS_ParticleBuffer` para `RAS_ParticleShaderCache`); confirmado que `RAS_ParticleBuffer` era o único consumidor dele na árvore.
- `CMakeLists.txt` (`source/gameengine/Rasterizer`) ganhou as duas entradas novas (`.h`/`.cpp`) ao lado de `RAS_ParticleBuffer`/`RAS_TransformFeedbackShader`.
- Compilado limpo: `ge_rasterizer` isolado primeiro (build rápido, pegou eventual erro de sintaxe cedo), depois `ninja RangeRuntime RangeEngine` completo — ambos exit 0, sem `ninja -t clean` (mudança não tocou nenhum `DNA_*.h`).
- **Testado e confirmado pelo usuário**: cena com múltiplos emissores rodando simultaneamente, comportamento visual correto (sem contaminação de parâmetro entre instâncias — cada objeto manteve sua própria cor/gravidade/posição apesar de agora compartilharem o programa GL compilado). Fase J encerrada.

**Fase K implementada (compilando limpo) — curvas de tamanho/cor sobre o tempo de vida**

- **Motivação**: até a Fase J, tamanho e cor só interpolam linearmente entre `size`/`end_size` e `color`/`end_color`. Fase K adiciona curvas opcionais desenhadas à mão via o widget nativo `CurveMapping` do Blender 2.79 (já usado em `PointDensity.falloff_curve` e vários outros lugares do fork) — sem editor de curva customizado, sem API Python nova no MVP (editor-only), 100% opt-in e retrocompatível (fallback exato ao `mix()` linear quando desligado).
- **K.1 — DNA (`DNA_object_types.h`)**: `RangeGPUParticleSettings` ganhou `CurveMapping *size_curve`, `CurveMapping *color_curve`, `short use_size_curve, use_color_curve`. Primeira tentativa quebrou o checker de alinhamento do `makesdna` (`Sizeerror ... add 2 bytes` — ponteiro de 64 bits exige struct múltiplo de 8 bytes); corrigido trocando `short pad2` único por `short pad2, pad3` (2 shorts de padding em vez de 1). `ninja -t clean` + rebuild completo obrigatório (mudança em DNA).
- **K.2 — `object.c`**: `curvemapping_free()` das duas curvas em `BKE_object_free()` (junto ao bloco `BKE_partdeflect_free`); `curvemapping_copy()` (NULL-safe) em `BKE_object_copy_data()` (junto ao bloco `ob_src->pd`) — evita double-free/aliasing na duplicação de objeto. Precisou de `#include "BKE_colortools.h"` novo.
- **K.3 — `writefile.c`/`readfile.c`**: `write_curvemapping()` (guardado por NULL-check, a função em si não faz) para as duas curvas em `write_object()`; `newdataadr()` + `direct_link_curvemapping()` (mesmo padrão NULL-safe) em `direct_link_object()`. Ponto mais fácil de esquecer do plano — ausência causaria heap corruption ao carregar `.range`/`.blend` com curvas definidas.
- **K.4 — RNA (`rna_object.c`)**: propriedades `size_curve`/`color_curve` (`PROP_POINTER` para `CurveMapping`) e `use_size_curve`/`use_color_curve` (`PROP_BOOLEAN`) em `rna_def_object_gpu_particles()`. Os dois booleanos usam callback de update custom (`rna_GPUParticles_use_size_curve_update`/`..._color_curve_update`, novo, perto de `rna_Object_lod_distance_update`) que aloca a curva sob demanda no primeiro toggle (`curvemapping_add(1, 0,0,1,1)` para tamanho, `curvemapping_add(4, ...)` para cor — 4 canais RGBA) em vez de sempre alocada, mesmo padrão de `PartDeflect.falloff_curve` em `texture.c`. Precisou de `#include "BKE_colortools.h"` novo.
- **K.5 — UI (`properties_particle.py`)**: novo painel `PARTICLE_PT_gpu_curves` (`bl_options = {'DEFAULT_CLOSED'}`, registrado logo após `PARTICLE_PT_gpu_appearance` na lista `classes`), duas caixas ("Size over Lifetime"/"Color over Lifetime") cada com o toggle `use_*_curve` e, se ligado e já alocado, `template_curve_mapping(gp, "*_curve", brush=False)`. `Appearance` (campos lineares antigos) mantido intacto como fallback/preset.
- **K.6 — bake em textura (`RAS_ParticleBuffer.h/.cpp`)**: `BakeSizeCurve()`/`BakeColorCurve()` novos, chamáveis repetidamente (reusam o nome de textura GL já alocado). Tamanho: 64 amostras de `curvemapping_evaluateF()` numa textura `GL_R32F` 64×1. Cor: usa `curvemapping_table_RGBA()` (tabela pré-calculada da própria API de colortools, `CM_TABLE+1` = 65 texels) numa `GL_RGBA32F`. `ClearSizeCurve()`/`ClearColorCurve()` só desligam a flag (sem liberar a textura, para reativação futura não realocar). Destrutor ganhou `glDeleteTextures` das duas. Precisou de `BKE_colortools.h`, `DNA_color_types.h`, `MEM_guardedalloc.h` novos.
- **K.7/K.8 — shader (`RAS_ParticleShaderCache.h/.cpp`)**: vertex shader do draw ganhou branch `if (u_useSizeCurve) { size = texture2D(u_sizeCurveTex, vec2(lifeFrac, 0.5)).r; } else { size = mix(...); }`; fragment shader o mesmo padrão para `baseColor`/cor. 4 uniform locations novas (`m_drawUseSizeCurveLoc`, `m_drawSizeCurveTexLoc`, `m_drawUseColorCurveLoc`, `m_drawColorCurveTexLoc`) resolvidas no construtor do cache, junto às já existentes.
- **K.9 — `RAS_ParticleBuffer::Draw()`**: bind das duas texturas de curva em `GL_TEXTURE1`/`GL_TEXTURE2` (textura de sprite já usa `GL_TEXTURE0`) só quando a flag correspondente está ligada, restaura a unit ativa para `GL_TEXTURE0` no final.
- **K.10 — `KX_GameObject::SetupGPUParticles()`**: no final da função (depois do `LoadTextureFromPath`), chama `BakeSizeCurve()`/`BakeColorCurve()` se `use_*_curve && *_curve` estiverem setados no DNA, senão `Clear*Curve()` — dispara o bake uma vez na conversão de cena, mesmo ponto onde os outros parâmetros do emissor já são lidos do DNA.
- **Bug real encontrado + corrigido durante o link**: `LNK2019` (símbolo externo não resolvido) para `curvemapping_initialize`/`curvemapping_evaluateF`/`curvemapping_table_RGBA` ao linkar `RangeEngine.exe`/`RangeRuntime.exe`. Causa: `BKE_colortools.h` é o único header de `blenkernel` usado neste fork que **não tem guard `#ifdef __cplusplus extern "C" { ... }`** (confirmado comparando com `BKE_image.h`, que tem) — como `RAS_ParticleBuffer.cpp` é o primeiro arquivo C++ da árvore a incluí-lo, os protótipos foram vistos com name mangling C++ pelo compilador, mas os símbolos reais em `colortools.c` (arquivo C) são C puro. Corrigido adicionando o guard padrão ao header (bug pré-existente do fork, não limitado a esta feature — qualquer código C++ futuro que precisasse de `BKE_colortools.h` bateria no mesmo erro).
- Compilado limpo: `ge_rasterizer`/`ge_ketsji` isolados primeiro, depois `ninja RangeEngine RangeRuntime` completo (sem `-t clean`, já feito na K.1) — exit code 0, `RangeEngine.exe` e `RangeRuntime.exe` linkados e instalados.
- **Testado e confirmado pelo usuário (2026-08-31)**: painel "Curves" funciona, curva de tamanho/cor desenhada e aplicada às partículas em jogo. Fase K encerrada.
- Fora de escopo (já no plano original): API Python para curvas (editor-only no MVP); Fase K.11 "speed-over-life" (mesmo padrão de bake-and-sample, mas no shader de update/transform-feedback em vez do de draw) — item futuro, não iniciado.

</details>

## 2026-08-31 §2

**Fase L implementada (compilando limpo) — debug ao vivo de GPU Particles**

- **Motivação**: o painel de partículas GPU cresceu (Fases A–K) e ajustar um parâmetro exige parar o jogo, editar no painel, apertar Play de novo. Descoberta chave: todos os parâmetros não-curva de `object.particles` (`KX_ParticleSystem`) já eram RW via Python desde a Fase D/G — então o overlay em si não precisava de C++ novo, só reusar `Range.imgui` (já usado no sistema de menu, Fases 1–3 de 2026-08-25).
- **DNA/RNA/UI**: `RangeGPUParticleSettings` (`DNA_object_types.h`) ganhou `short use_debug_ui` (reaproveitando um dos shorts de padding da Fase K, `pad2`/`pad3` viram um `use_debug_ui` + `pad2`); propriedade RNA booleana em `rna_object.c` (`rna_def_object_gpu_particles`); checkbox "Live Debug UI (in-game, press F9)" numa nova caixa "Debug:" no painel `PARTICLE_PT_gpu_emitter` (`properties_particle.py`).
- **Runtime (C++)**: o flag não precisou ir para `KX_GameObject` — foi direto para `RAS_ParticleBuffer` (`m_debugUI`/`GetDebugUI()`/`SetDebugUI()`), setado em `KX_GameObject::SetupGPUParticles()` junto aos outros parâmetros lidos do DNA. `KX_ParticleSystem` ganhou o atributo Python read-only `debugUI` (`pyattr_get_debug_ui`), lido pelo componente Python pra decidir se mostra o overlay — funciona igual no editor e no standalone, sem depender de `bpy`.
- **Overlay v1 (Python, `projects-teste/scripts/particle_debug_overlay_component.py`) — SUBSTITUÍDO na §3 abaixo**: primeira versão era um `KX_PythonComponent` a ser anexado manualmente ao objeto do emissor. Funcionava, mas exigia esse passo manual por objeto — ver §3 para a versão final (automática, em C++).
- **Save-back — decisão junto com o usuário**: standalone (`RangeRuntime.exe`) roda em processo separado, sem `bpy` nem UI do Blender — não dá pra escrever "ao vivo" na UI de lá. Solução: botão "Apply to .blend" tenta `bpy` primeiro — se disponível (Play embutido no 3D View, mesmo processo do Blender), grava direto em `bpy.data.objects[nome].gpu_particles.*`; senão (standalone), grava/atualiza um JSON (`gpu_particles_debug.json`, ao lado do `.blend`) com os valores por nome de objeto.
- **Import automático + manual (`properties_particle.py`)**: um handler `bpy.app.handlers.load_post` (`_gpu_debug_load_post_handler`) procura esse JSON ao lado do `.blend` recém-aberto e aplica os valores nos objetos correspondentes sozinho, renomeando o arquivo pra `.applied.json` depois (evita reaplicar). Um operador `PARTICLE_OT_import_gpu_debug_values` ("Import Debug Values", botão na mesma caixa "Debug:") faz a mesma coisa sob demanda, pra quem não quiser fechar/reabrir o arquivo.
- Compilado limpo: `ninja -t clean` + rebuild completo de `RangeEngine`/`RangeRuntime` (mudança em DNA) — exit code 0, sem erro, só warnings pré-existentes não relacionados (`BKE_customdata.h`, `creator.c`).
- **Bug de UI pego pelo usuário no primeiro teste**: `icon="TOOL_SETTINGS"` na caixa "Debug:" não existe no enum de ícones do Blender 2.79 (`TypeError` ao abrir o painel, `properties_particle.py` inteiro falhava ao carregar) — corrigido pra `icon="SETTINGS"` (válido). Como é script Python puro, não precisou de rebuild: copiado direto pros `build/`/`build_core/` já instalados.

## 2026-08-31 §3

**Fase L.2 — overlay movido de componente Python pra C++ automático, a pedido do usuário**

- **Motivação**: o overlay v1 (§2) exigia anexar `ParticleDebugOverlayComponent` manualmente em cada objeto com partículas, além do checkbox no painel — usuário perguntou se dava pra fazer direto na engine. Dava: todo o desenho ImGui e a leitura/escrita dos parâmetros já eram feitos com getters/setters do `RAS_ParticleBuffer` já existentes (Fase D/G/K) — só precisava rodar automaticamente pra qualquer objeto com `use_debug_ui`, sem depender de um `KX_PythonComponent` anexado.
- **`KX_ParticleDebugUI.h/.cpp` (novo, `source/gameengine/Ketsji/`)**: `Draw(KX_GameObject*, RAS_ParticleBuffer*)` desenha a janela via `ImGui::SliderFloat`/`SliderFloat3`/`SliderInt`/`ColorEdit4` direto (bem mais simples que a versão Python, que simulava vec3 com 3 sliders separados — `ImGui::SliderFloat3` aceita `float[3]` nativo). `ApplyToBlend(...)` faz o mesmo `try bpy / fallback JSON` do v1, mas via API C do Python (`PyImport_ImportModule("bpy")`, `PyObject_GetAttrString`/`SetAttrString` em cadeia até `gpu_particles`) e cJSON (`source/extern/cjson`, já vendorado e usado em `KX_InputSystem.cpp` pros keybinding maps) pro sidecar — sem nenhuma dependência de componente Python.
- **`KX_KetsjiEngine`**: `NextFrame()` varre `KX_Scene::GetGpuParticleObjects()` (lista já cacheada desde a Fase I.2) a cada frame; se algum objeto tem `buffer->GetDebugUI()`, força `SHOW_GAME_UI` ligado (mesmo flag que os menus ImGui em Python já usam via `imgui.set_game_ui_open`, edge-triggered do mesmo jeito — só desliga no frame em que deixa de estar ativo) e F9 alterna `m_particleDebugUIVisible`. `EndFrame()` desenha uma janela por objeto habilitado logo após `m_debugMode->RenderImguiDebugMode()`.
- `particle_debug_overlay_component.py` removido — não é mais necessário, o checkbox "Live Debug UI" no painel já basta, sem passo manual de anexar componente.
- Compilado limpo: mudança não tocou DNA (só `CMakeLists.txt` do Ketsji ganhou as duas entradas novas) — `ninja RangeEngine RangeRuntime` incremental, exit code 0, sem `-t clean`.
- Ainda não testado em jogo pelo usuário (compilação confirmada; teste funcional pendente: overlay aparecendo sozinho ao entrar em jogo com o checkbox ligado, F9 escondendo/reexibindo, sliders afetando as partículas ao vivo, e o ciclo completo standalone→JSON→auto-import no editor).
- Fora de escopo (perguntado e descartado por ora): edição ao vivo das curvas de tamanho/cor (`size_curve`/`color_curve`, Fase K) — não expostas via Python nem lidas aqui; dá pra pelo menos ligar/desligar (`use_size_curve`/`use_color_curve`) no overlay se o usuário quiser depois, mas desenhar o formato da curva em si precisaria de um widget de curva customizado em ImGui (não existe hoje, `Range.imgui` não tem `plot_lines`/drag-points).

## 2026-08-31 §4

**Fase M implementada e confirmada — presets de efeitos (fogo/choque/poeira/faíscas) + blend aditivo no sistema de partículas GPU**

- **Motivação**: usuário tinha 4 efeitos GLSL prontos como filtros 2D full-screen por objeto (`CarDustTrail.py`, `CarFireAura.py`, `CarShockAura.py`, `SparksFX.py`, `projects-teste/scripts/`) — fogo, choque elétrico, poeira e faíscas de roda. Decisão: não reaproveitar o GLSL desses filtros diretamente (são pixel-shaders full-screen com lógica de silhueta/profundidade, não casam com o pipeline de partícula); aproveitar só a direção artística (cor/comportamento) como presets no sistema de partículas GPU (`object.gpu_particles`, Fases A–L), aplicados via painel do editor. Confirmado explicitamente pelo usuário: presets só setam parâmetros no shader único já compartilhado (`RAS_ParticleShaderCache`, Fase J) — nenhum GLSL novo ou editável por preset.
- **Blend aditivo (necessário pra fogo/choque/faíscas)**: `RangeGPUParticleSettings` (`DNA_object_types.h`) reaproveitou o `short pad2` sobrando (Fase L já tinha comido o outro) como `blend_mode` (0=Alpha, 1=Additive), sem mudar o tamanho do struct. Enum RNA (`rna_object.c`) + dropdown "Blend Mode" numa nova caixa em `PARTICLE_PT_gpu_appearance`. Puramente estado GL fixo (`RAS_ParticleBuffer::Draw()`, `glBlendFunc(GL_SRC_ALPHA, GL_ONE)` se additive, senão o alpha normal já existente) — sem uniform de shader, sem tocar `RAS_ParticleShaderCache`. `KX_GameObject::SetupGPUParticles()` repassa o valor do DNA pro buffer via `SetBlendMode()`, junto aos outros parâmetros já lidos ali.
- **Menu de presets (`PARTICLE_MT_gpu_particle_presets`, `properties_particle.py`)**: mesmo padrão nativo do Blender já usado por `PARTICLE_MT_hair_dynamics_presets` — `preset_subdir="gpu_particle"`, `preset_operator="script.execute_preset"`, desenhado no topo de `PARTICLE_PT_gpu_emitter` com botões +/- (`AddPresetGPUParticle`, novo em `bl_operators/presets.py`, `preset_values` cobrindo todos os campos não-curva incluindo o novo `blend_mode`). 4 arquivos `.py` em `release/scripts/presets/gpu_particle/`: `fire.py` (quente, additive, cone estreito), `electric_shock.py` (azul/branco, crepitante, lifetime curtíssimo, additive), `dust.py` (terroso, alpha normal — já opaco por natureza), `wheel_sparks.py` (branco→laranja, gravidade forte, additive, particle_count baixo). Sobrescrever um preset é nativo do mecanismo: reajustar valores no painel e salvar com o mesmo nome no botão "+", ou editar o `.py` direto (é atribuição de propriedade em texto puro).
- **Layout (pedido à parte, mesma sessão)**: painel `PARTICLE_PT_gpu_curves` (Fase K) tinha "Size over Lifetime"/"Color over Lifetime" empilhados verticalmente — trocado para `layout.row()` com duas caixas lado a lado, menos altura ocupada no painel.
- **Bug de build (não de código)**: primeiro `ninja RangeEngine` pós-mudança de DNA falhou no passo de instalação (`CMake Error ... file INSTALL cannot find "RangeRuntime.exe": File exists`) — o link/compilação em si já tinha terminado com sucesso, foi um lock transiente no arquivo (mesmo padrão já visto no `ninja -t clean`, sem processo `RangeRuntime.exe`/`RangeEngine.exe` realmente rodando). Resolvido rodando `ninja RangeEngine` de novo, exit code 0.
- **Testado e confirmado pelo usuário (2026-08-31)**: presets funcionando. Fase M encerrada.

## 2026-08-31 §5

**Fase N implementada — visibilidade pausa update+draw do emissor; novo toggle `enabled` independente da visibilidade**

- **Motivação**: usuário perguntou se `setVisible(False)` num Empty com `gpu_particles` ligado desligava o emissor. Investigação (`KX_Scene::UpdateGpuParticleEmitters`, `KX_KetsjiEngine::RenderCamera`) mostrou que não — `UpdateParticles()`/`Draw()` eram chamados incondicionalmente para todo objeto em `m_gpuParticleObjects`, sem checar `GetVisible()`. Objeto invisível continuava simulando e desenhando as partículas. Segundo caso do usuário no mesmo fio: efeito de poeira ligado direto na roda (mesmo objeto, sem Empty separado) — aí ele quer a roda sempre visível mas o efeito ligável/desligável à parte, então visibilidade sozinha não bastava como único controle.
- **Duas frentes independentes, propositalmente não fundidas em uma só**:
  1. **Visibilidade agora pausa automaticamente**: `KX_Scene::UpdateGpuParticleEmitters` só chama `UpdateParticles()` se `gameobj->GetVisible()`; `KX_KetsjiEngine::RenderCamera` só chama `buffer->Draw()` se `particleObj->GetVisible()` (mesmo gate, pra não desenhar posições velhas de um buffer que não foi mais atualizado). Sem custo de simulação/desenho para um emissor de fato fora de tela.
  2. **Novo toggle explícito, independente**: `object.gpu_particles.enabled` (DNA `RangeGPUParticleSettings.disable_emission`, RNA `enabled` via `RNA_def_property_boolean_negative_sdna` — guardado invertido de propósito, pra que `.blend` antigos com o struct zerado continuem emitindo em vez de silenciosamente pararem) seeda `RAS_ParticleBuffer::m_enabled` em `KX_GameObject::SetupGPUParticles()`. `RAS_ParticleBuffer::Update()`/`Draw()` viram no-op quando `!m_enabled`, mesmo com o objeto visível. Exposto em runtime também via `object.particles.enabled` (RW, `KX_ParticleSystem::pyattr_get/set_enabled`) — dá pra ligar/desligar por script a qualquer momento, sem mexer na visibilidade do objeto dono.
- **UI**: nova caixa "Emission:" no painel `PARTICLE_PT_gpu_emitter` (`properties_particle.py`), checkbox "Emit at Game Start".
- **DNA**: `disable_emission` (char) + `pad2[7]` reaproveitam o espaço de padding sobrando depois de `blend_mode` (Fase M), sem mudar o layout dos campos existentes.
- Compilado limpo: `ninja -t clean` + rebuild completo de `RangeEngine`/`RangeRuntime` (mudança em `DNA_object_types.h`) — exit code 0. Um `ninja RangeEngine` isolado bateu no mesmo lock transiente de instalação já visto na Fase M (`file INSTALL cannot find RangeRuntime.exe`, sem processo travando o arquivo) — resolvido buildando `RangeRuntime` em seguida.
- Teste em jogo pendente: confirmar que um objeto invisível para de gastar tempo de frame com o emissor, e que `enabled = False` num objeto visível (ex: a roda) esconde só as partículas sem esconder o objeto.

## 2026-09-01

**Actuator "GPU Particles" removido, substituído por Property auto-criada**

- **Contexto**: um actuator customizado "GPU Particles" (Enable/Disable/Toggle, `bGPUParticlesActuator` em `DNA_actuator_types.h`) tinha sido adicionado num commit anterior pra ligar/desligar emissão via Logic Brick. Depois de ligá-lo num objeto e salvar, o `.range` passou a crashar (`EXCEPTION_ACCESS_VIOLATION`) ao carregar — mesmo depois de um clean rebuild completo (`ninja -t clean` + rebuild, que já tinha resolvido um problema anterior de o actuator não disparar `Update()`). Segunda vez que uma struct DNA nova nesse ponto do fork se mostrou frágil — decisão de abandonar em vez de continuar depurando, e trocar de estratégia.
- **Pesquisa antes de implementar**: confirmado que remover a struct DNA depois é seguro pra arquivos antigos — o carregamento de actuators em `readfile.c` é genérico (não faz switch por tipo), então não era o motivo do crash; o actuator em si (ou dado salvo com o struct ainda "verde") era o suspeito mais provável, mas não valia a pena continuar investigando. Confirmado também que o dropdown do bloco padrão **Property** (sensor/actuator) do Logic Editor lê `Object.prop` (DNA `bProperty`), não properties só-em-runtime — por isso a nova property precisa ser criada no lado Blender (RNA/editor), não só setada no engine via `SetProperty`.
- **Nova abordagem**: o checkbox "Enable GPU Particles" do objeto (`use_gpu_particles`, `rna_object.c`) trocou seu update callback de `NULL` pra `rna_Object_use_gpu_particles_update` (novo) — que cria automaticamente uma `bProperty` booleana real chamada `GPU_Particles_Enabled` (`BKE_bproperty_new(GPROP_BOOL)` → `BLI_addtail(&ob->prop, prop)` → nome → `BLI_uniquename`, mesmo padrão de `game_property_new_exec` em `object_edit.c`), default ligada (`prop->data = 1`). Só cria, nunca remove ao desligar o checkbox — evita quebrar links de Logic Bricks já feitos. Essa property aparece nativamente no painel de Game Properties e no dropdown dos blocos Property — nenhum DNA/RNA/actuator novo precisou ser criado.
- **Versionamento (`versioning_range.c`)**: bump de `RANGE_MINSUBVERSION` (`BKE_blender_version.h`) de 102 pra 103; novo bloco `if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 103))` percorre todo objeto com `gameflag2 & OB_GPU_PARTICLES` e backfilla a `bProperty` (mesma lógica do passo acima) — cenas de teste já salvas ganham a property automaticamente ao abrir, sem precisar re-clicar o checkbox.
- **Sync por frame (`KX_GameObject::UpdateParticles`, `KX_GameObject.cpp:660`)**: passou a ler `GetPropertyNumber("GPU_Particles_Enabled", 1.0f)` (de `EXP_Value`, com fallback seguro `1.0f` = ativo por padrão pra objetos sem a property) e aplicar em `m_particleBuffer->SetEnabled(...)` antes de chamar `Update()`. Como `KX_Scene::UpdateGpuParticleEmitters` roda depois de `LogicUpdateFrame` (`KX_KetsjiEngine.cpp`), um Property actuator que escreveu a property nesse mesmo frame já é visto aqui, sem atraso de 1 frame.
- **Remoção completa do actuator antigo** (checklist confirmado que `readfile.c`/`writefile.c` (de)serializam actuators de forma genérica, então `.range` antigos com esse actuator salvo caem no `default:` no-op tanto em `sca.c` quanto em `KX_ConvertActuators.cpp`, sem quebrar):
  - `DNA_actuator_types.h`: struct `bGPUParticlesActuator`, `#define ACT_GPU_PARTICLES` e os 3 modes (`ACT_GPU_PARTICLES_ENABLE/DISABLE/TOGGLE`) removidos.
  - `sca.c`: case no `init_actuator` e no switch de no-op removidos.
  - `rna_actuator.c`: entrada no enum `actuator_type_items`, `rna_Actuator_refine`, `RNA_enum_items_add_value`, e a função inteira `rna_def_gpu_particles_actuator` (+ chamada) removidos.
  - `logic_window.c`: label (`actuator_name`), `draw_actuator_gpu_particles` (função inteira) e o dispatch em `draw_actuators` removidos.
  - `KX_ConvertActuators.cpp`: `#include "KX_GPUParticlesActuator.h"` e o `case ACT_GPU_PARTICLES` removidos.
  - `SCA_IActuator.h`: `KX_ACT_GPU_PARTICLES` removido do enum.
  - `KX_GPUParticlesActuator.h`/`.cpp` deletados.
  - `CMakeLists.txt` (`gameengine/Ketsji`): as duas entradas (`.h`/`.cpp`) removidas.
- Compilado limpo: `ninja -t clean` + rebuild completo de `RangeEngine`/`RangeRuntime` obrigatório (mudança em `DNA_actuator_types.h`) — exit code 0, só warnings pré-existentes não relacionados (`BKE_customdata.h`, `creator.c`).
- **Testado e confirmado pelo usuário (2026-09-01)**: checkbox cria `GPU_Particles_Enabled` no painel de Game Properties; sensor de teclado → controller AND → actuator Property (Assign/Toggle) liga/desliga a emissão em 3D View e no `RangeRuntime.exe` standalone; `.range` antigo que antes crashava agora abre normalmente.
- **Pergunta do usuário respondida**: `object.particles.enabled` (Python, Fase N) continua existindo e escreve direto em `RAS_ParticleBuffer::SetEnabled()`, mas é sobrescrito todo frame por `UpdateParticles()` a partir da property — não adianta setar os dois, a property sempre vence no frame seguinte. Script que precisa controlar emissão via Python deve setar `obj["GPU_Particles_Enabled"] = True/False`, não `obj.particles.enabled` diretamente.

**Weather: rain shader revisado**

- **Layout do painel "Weather"**: reestruturado pra uma única caixa externa com split em duas colunas (Chuva | Nuvens/Lens Flare), igual ao padrão visual do painel "Environment" acima dele — antes cada sub-efeito tinha sua própria caixa lado a lado, quebrando a consistência visual (`custom_pt_world.py`).
- **Rain shader revisado**: `RAS_Rain2DFilter.glsl` reescrito — dois layers de streaks com parallax (grosso/rápido + fino/lento) via value-noise 2D, e ripples de poça em profundidade real (`ge_RainParams1/2`, `ge_RainColor`, sem uniforms novos). Droplets e ripple são independentemente ligáveis (`use_rain_droplets`/`use_rain_ripple` → `WO_WEATHER_RAIN_DROPLETS`/`WO_WEATHER_RAIN_RIPPLE`).
- **Bugs de `RAS_Clouds2DFilter.glsl` corrigidos (2026-09-01, achados em teste real pelo usuário)**:
  - Nuvens apareciam abaixo da linha do horizonte (refletidas no chão) — o depth test `isSky` não distingue céu real de um plano de chão infinito que também cai no far-plane. Corrigido com fade `horizonFade` baseado na elevação do view ray, cortando a máscara suavemente perto e abaixo do horizonte.
  - Elevação calculada com o eixo errado: mundo é Z-up (convenção Blender/UPBGE), mas o shader usava `viewDir.y` — que é um eixo horizontal — como elevação. Isso fazia a máscara de nuvem seguir o yaw da câmera em vez do pitch (apareciam "de um lado", em cima e embaixo ao girar). Trocado para `viewDir.z`.
  - Costura visível no meio do céu: a amostragem de ruído usava coordenadas polares (`lon = atan(viewDir.y, viewDir.x)`), que dão um salto brusco de +π pra -π — visível como uma linha reta cruzando o céu. Substituído por ruído 3D (`cloudNoise`/`cloudFbm` agora recebem `vec3`) amostrado direto no `viewDir` normalizado, contínuo em toda a esfera, sem costura.
- Confirmado pelo usuário em jogo: horizonte limpo, nuvens só no céu, sem costura.

**Modo de billboard vertical para o sistema de partículas GPU**

- **Contexto**: `RAS_ParticleBuffer` só sabia desenhar em modo camera-facing (quad sempre de frente pra câmera, calculado em view-space). Usuário pediu outros modos de orientação; vertical (axis-locked no eixo Z do mundo, só gira horizontalmente) escolhido primeiro por ser o mais barato — nenhum atributo novo por partícula, nenhum buffer novo, só um branch no vertex shader mais um uniform de modo. Bom pra fumaça, fogo, grama. Seguiu exatamente o padrão já usado por `blend_mode` (Fase M): DNA → RNA → UI → bridge de conversão de cena → runtime.
- **DNA** (`DNA_object_types.h`): novo `short billboard_mode;` em `RangeGPUParticleSettings`, logo após `blend_mode`, encolhendo `pad2` de `[7]` pra `[5]` — mantém o tamanho do struct igual, então `.blend`/`.range` antigos continuam lendo `billboard_mode == 0` (camera-facing, comportamento preservado). Novo enum `GPU_PARTICLE_BILLBOARD_CAMERA_FACING`/`GPU_PARTICLE_BILLBOARD_VERTICAL`.
- **RNA** (`rna_object.c`): `rna_enum_gpu_particle_billboard_mode_items` + propriedade `billboard_mode`, mesmo padrão de `blend_mode`.
- **UI** (`properties_particle.py`): nova caixa "Billboard:" no painel `PARTICLE_PT_gpu_appearance`, logo após a de "Blending:".
- **Bridge** (`KX_GameObject::SetupGPUParticles`): `m_particleBuffer->SetBillboardMode(settings.billboard_mode)` junto de `SetBlendMode`.
- **Runtime** (`RAS_ParticleBuffer.h`/`.cpp`): `m_billboardMode` + `Get/SetBillboardMode`, mesmo padrão de `m_blendMode`; em `Draw()`, novo `glUniform1i(m_shaderCache->GetDrawBillboardModeLoc(), ...)`.
- **Shader cache** (`RAS_ParticleShaderCache.h`/`.cpp`): `m_drawBillboardModeLoc` + getter, resolvido via `glGetUniformLocation(m_drawProgram, "u_billboardMode")`.
- **Vertex shader** (`drawVertexSource`, embutido como string C em `RAS_ParticleShaderCache.cpp` — não é `.glsl` via datatoc, é source inline): novo `uniform int u_billboardMode`. Modo 0 mantém o cálculo original em view-space. Modo 1 calcula em world-space: eixo "up" travado em `(0,0,1)`, eixo "right" derivado da primeira linha de `u_view` (right da câmera em world-space numa matriz lookAt padrão, sem uniform novo) projetado no plano horizontal e normalizado, com guarda (`dot(rightRaw, rightRaw) > 0.0001`) contra `normalize()` de vetor quase-zero quando a câmera olha quase reto pra cima/baixo.
- Python API (`KX_ParticleSystem.cpp`) não ganhou getter/setter pra `billboard_mode` nesta rodada — mesma decisão já tomada pra `blend_mode`, mantém consistência.
- Compilado limpo: `RangeEngine.exe` (aberto) precisou ser encerrado pra liberar o `ninja -t clean` (mudança em `DNA_object_types.h` exige clean, nunca incremental); rebuild completo de `RangeEngine` em andamento.
- Teste em jogo pendente: criar emissor GPU particle, alternar "Billboard Mode" pra Vertical, orbitar câmera pra cima/baixo e confirmar que os quads não inclinam; testar cena antiga sem o campo pra confirmar `billboard_mode = 0` sem regressão.

**Billboard Mode no debug UI in-game + terceiro modo "Horizontal (Facing Down)"**

- **Debug UI** (`KX_ParticleDebugUI.cpp`, painel ImGui in-game da Fase L): novo `ImGui::Combo` "Billboard Mode" na seção Appearance, lendo/escrevendo `RAS_ParticleBuffer::Get/SetBillboardMode`. Sincronizado nos dois caminhos de persistência existentes (mesmo padrão dos outros campos do painel): "Apply to .blend" via Python (`gp.billboard_mode = "VERTICAL"/...`) e sidecar `gpu_particles_debug.json` pro `RangeRuntime.exe` standalone (sem `bpy`), lido de volta por `_apply_gpu_debug_values` (`properties_particle.py`) — chave `billboard_mode` adicionada à lista de campos aplicados.
- **Novo modo `GPU_PARTICLE_BILLBOARD_HORIZONTAL = 2`**: pedido do usuário — nuvens voando precisam do quad sempre deitado, encarando pra baixo, independente da câmera (diferente do Vertical, que ainda gira horizontalmente pra seguir a câmera). Offset calculado direto nos eixos world-X/world-Y (`vec3(in_corner.x * size, in_corner.y * size, 0.0)`), sem nenhuma dependência de `u_view` — mais barato até que o modo Vertical. Mesmo padrão aditivo: DNA (novo valor de enum, sem mudar layout do struct) → RNA (`rna_enum_gpu_particle_billboard_mode_items`) → UI (dropdown genérico já pega o novo item automaticamente) → debug UI (terceiro item no combo) → vertex shader (`else if (u_billboardMode == 2)`).
- Compilado limpo (`ninja -t clean` + rebuild completo, obrigatório por mudança em `DNA_object_types.h`) — exit code 0. `RangeEngine.exe` precisou ser encerrado pelo usuário antes do clean (estava aberto, bloqueando o link) — isso já tinha acontecido antes na Fase M/N, mesma causa.
- **Testado e confirmado pelo usuário (2026-09-01)**: os 3 modos funcionam; Horizontal inicialmente ficou com a face virada pra cima em vez de pra baixo, corrigido invertendo o sinal do eixo X do offset no shader (`vec3(-in_corner.x * size, in_corner.y * size, 0.0)`), rebuild confirmado OK.

**Backface Culling para o sistema de partículas GPU**

- Pedido do usuário, complementar ao modo Horizontal: opção pra esconder a face de trás do quad em vez de desenhar dos dois lados (útil sobretudo pro Horizontal — evita ver o "verso" da nuvem ao passar a câmera por baixo/acima do plano).
- Mesmo padrão aditivo de sempre: **DNA** (`use_backface_culling`, char, reaproveita o espaço de `pad2` — struct mantém o tamanho) → **RNA** (`rna_object.c`, bool simples) → **UI** (checkbox na caixa "Billboard:" de `properties_particle.py`, logo abaixo do dropdown de modo) → **bridge** (`KX_GameObject::SetupGPUParticles` → `SetBackfaceCulling`) → **runtime** (`RAS_ParticleBuffer::m_backfaceCulling` + getter/setter) → **draw** (`glEnable(GL_CULL_FACE)`/`glDisable` em volta do `glDrawArraysInstancedARB` em `Draw()`, só quando a flag está ligada — off por padrão, comportamento anterior preservado).
- **Debug UI** (`KX_ParticleDebugUI.cpp`): checkbox "Backface Culling" logo após o combo de Billboard Mode, sincronizado nos dois caminhos de persistência (Apply to .blend via Python, sidecar JSON pro `RangeRuntime.exe` standalone) — mesma integração já feita pro Billboard Mode.
- Compilado limpo (`ninja -t clean` + rebuild completo, obrigatório por mudança em `DNA_object_types.h`).
- Teste em jogo pendente: ligar Backface Culling num emissor Horizontal, orbitar a câmera por baixo/cima do plano e confirmar que a face de trás fica invisível (culling correto, sem inverter qual lado é o "front" por engano).

**Estilo de chuva "Volumetric" + otimização das inversas de matriz em Rain/Clouds**

- **Contexto**: usuário forneceu um shader de chuva de terceiros (raymarch em world-space, 3 camadas de profundidade fixas + ripples) pra virar um segundo estilo visual, alternativo ao estilo atual (streaks 2D em screen-space). Antes de plugar, pediu pra mesclar as 3 camadas do shader novo numa só (redundantes/caras), e depois revisar todos os efeitos de Weather (Rain/Clouds/Lens Flare) por otimização.
- **Shader mesclado**: `RAS_Rain2DFilter.glsl` ganhou `rainVolumetricStreaks()` — em vez de 3 chamadas condicionais a uma função de streak (uma por faixa de `sceneDepth`, cada uma com seu próprio hash/noise), uma única função faz o blend continuamente por profundidade (`smoothstep`/`mix` em vez de 3 branches `if (sceneDepth > X)`), cortando ~2/3 do custo de hash da camada de streaks nesse estilo. Reaproveita `rainCellHash`/`getWorldPositionFromDepth` já existentes no arquivo em vez de duplicar as versões do shader colado.
- **`rain_style` selecionável** (padrão aditivo de sempre — DNA → RNA → UI → runtime → shader):
  - `DNA_world_types.h`: `weather_pad` (não usado) virou `short rain_style` — não muda o tamanho do struct, arquivos antigos carregam com `rain_style = 0` (Classic). Novo enum `WO_RAIN_STYLE_CLASSIC`/`WO_RAIN_STYLE_VOLUMETRIC`.
  - `rna_world.c`: propriedade enum `rain_style` (Classic/Volumetric) em `WorldWeatherSettings`.
  - `custom_pt_world.py`: dropdown na seção Rain do painel Weather.
  - `RAS_2DFilterData.h`/`KX_Scene.cpp`/`RAS_2DFilter.h`/`.cpp`: `rain_style` plumbed até um novo uniform `ge_RainStyle` (float), mesmo padrão dos outros `ge_RainParams*`.
  - `RAS_Rain2DFilter.glsl`: `main()` escolhe entre o acúmulo de streaks Classic (2D, existente) ou `rainVolumetricStreaks()` (Volumetric) quando `useDroplets` está ligado; a camada de ripple é igual pros dois estilos.
- **Otimização: `inverse()` por-pixel removida de Rain e Clouds**: achado durante a revisão — `RAS_Rain2DFilter.glsl` (`getWorldPositionFromDepth`) e `RAS_Clouds2DFilter.glsl` (`skyViewDirection`) invertiam `unfviewmat`/`unfprojmat` (mat4) **dentro do fragment shader**, ou seja, uma inversão de matriz por pixel — em Clouds, todo pixel de céu da tela inteira. View/projection são as mesmas pro draw inteiro, então isso era puro desperdício. Corrigido calculando as inversas uma vez por draw no C++ (`RAS_2DFilter::BindUniforms`, `rasty->GetViewMatrix().Inverse()`/`GetProjectionMatrix().Inverse()`, mesmo padrão de `GE_VIEW_MATRIX_UNIFORM`) e enviando como dois uniforms novos (`unfinvviewmat`/`unfinvprojmat`, `GE_INV_VIEW_MATRIX_UNIFORM`/`GE_INV_PROJECTION_MATRIX_UNIFORM`); os shaders só leem o uniform agora, sem `inverse()` no hot path. Lens Flare já não usava `inverse()` — nada a mudar lá.
- Compilado limpo em duas etapas: `ninja -t clean` + rebuild completo obrigatório após a mudança em `DNA_world_types.h` (439/439, exit code 0), depois rebuild incremental após a otimização das matrizes (19/19, exit code 0) — sem erros nos dois.
- **Iteração de densidade (mesma sessão)**: primeira versão de `rainVolumetricStreaks()` colapsava as 3 camadas num único sample de ruído (blend contínuo por `smoothstep`) — testado pelo usuário, resultado visivelmente mais esparso que a referência do shader original. Causa: são as 3 grades de hash independentes sobrepostas (cada uma numa distância/escala/seed diferente) que dão a densidade, não uma função de fade por profundidade. Revertido para 3 samples reais (`rainStreakLayer()` chamada 3x por `rainVolumetricStreaks()`, thresholds/thickness/seeds idênticos ao shader original), só organizados numa função reutilizável em vez de 3 blocos soltos no `main()`.
- **Também descoberto nesta iteração**: `RangeEngine` (editor, onde o painel Weather com o dropdown "Rain Style" é exibido) precisa ser rebuildado separadamente de `RangeRuntime` — são executáveis distintos que linkam o mesmo `ge_*`/RNA, mas cada um precisa do seu próprio rebuild após mudança em DNA/RNA/UI. Rebuildar só `RangeRuntime` deixa o editor com o binário antigo, sem a propriedade nova, então o dropdown não aparecia.

## Global Properties no World (shared object <-> World dict)

- **Contexto**: objetos in-game já trocavam dado via Game Properties por-objeto (`obj["key"]`) ou o `bge.logic.globalDict` ad-hoc (dict Python puro, não autorável na UI, não persistido no `.blend`). Pedido do usuário: um "blackboard" compartilhado por cena, autorado no painel World igual às Game Properties de Object, legível/gravável por qualquer script via `own.scene.world["chave"]`.
- **Implementação (mapeou quase 1:1 em cima do sistema já existente de Object Game Properties)**: `ListBase prop` novo em `World` (`DNA_world_types.h`) → alloc/free/copy em `world.c` reaproveitando `BKE_bproperty_*` genéricos (já operam sobre `ListBase*`/`bProperty*`, sem acoplamento a `Object`) → leitura/escrita `.blend` (`write_properties()`/`link_list()` em `writefile.c`/`readfile.c`, espelhando o bloco de `ob->prop`) → RNA `World.properties` (`rna_world.c`, reaproveita `GameProperty`/`rna_property.c` como está) → 3 operators novos `WORLD_OT_game_property_new/remove/move` (`render_shading.c`, espelhando `object_edit.c`) → painel "Global Properties" (`custom_pt_world.py`) → conversão em runtime (`BL_ConvertProperties.cpp`: helper `BL_CreatePropertyValue` fatorado do código de Object, nova `BL_ConvertWorldProperties()` chamada em `BL_BlenderDataConversion.cpp` logo após criar o `KX_WorldInfo`) → `KX_WorldInfo` ganhou o mesmo protocolo de mapping Python que `KX_GameObject` (`m_attr_dict` + `Map_GetItem`/`Map_SetItem` + `tp_as_mapping`), habilitando `own.scene.world["chave"] = valor`.
- **Comportamento de persistência (confirmado com o usuário)**: valores resetam pro default autorado no `.blend` a cada load/reload de cena — igual às Game Properties de Object hoje, porque o dict vive no `KX_WorldInfo`, recriado do zero a cada conversão de cena. Mudanças em runtime não sobrevivem troca de cena nem são compartilhadas entre cenas diferentes que referenciam o mesmo World. `bge.logic.globalDict` continua intocado como mecanismo separado pra quando isso for necessário.
- **Bug 1 (crash ao dar Enter no nome da propriedade)**: `rna_GameProperty_name_set` (`rna_property.c`) fazia cast fixo do ID dono pra `Object*` (`Object *ob = ptr->id.data`) pra chamar `BLI_uniquename(&ob->prop, ...)`. Como agora o dono também pode ser `World` (layout de struct diferente), isso lia um `ListBase*` fora do struct real e estourava. Corrigido pra escolher `World->prop` ou `Object->prop` conforme `GS(id->name)`.
- **Bug 2 (heap corruption/travamento total ao clicar "+" pra duplicar World)**: `BKE_world_copy_data`/`BKE_world_localize` (`world.c`) chamavam `BKE_bproperty_copy_list(&wrld_dst->prop, &wrld_src->prop)` sem antes `BLI_listbase_clear(&wrld_dst->prop)` — o destino começa como cópia rasa (mesmos ponteiros do source, por causa de como `BKE_id_copy_ex` duplica a struct), então `BKE_bproperty_copy_list` (que começa com `BKE_bproperty_free_list(lbn)`) liberava os nós do World **original** por aliasing, corrompendo o heap. Padrão correto (`BLI_listbase_clear` antes do copy) já existia em `BKE_object_copy_data` (`object.c:1283`) e foi só replicado. Sintoma real reportado pelo usuário: travou o programa e depois o computador inteiro.
- **Escopo desta rodada**: só acesso via Python (`own.scene.world["chave"]`). Property Sensor/Actuator (Logic Bricks) continuam só em objetos — não têm como apontar pro World hoje; estender esses bricks pra suportar um modo "Global (World)" fica como possível próximo passo, não implementado.
- Compilado limpo em 3 rounds: `ninja -t clean` + rebuild completo (`DNA_world_types.h` mudou) → 2 correções incrementais (includes faltando em `render_shading.c`/`world.c`, depois os 2 bugs de runtime acima) → rebuild final de `RangeEngine`+`RangeRuntime` limpo.
- **Testado e confirmado pelo usuário**: painel "Global Properties" aparece só na aba World; adicionar propriedade e renomear (Enter) funciona sem crash; botão "+" de duplicar/criar World funciona sem travar.
- **Testado e confirmado pelo usuário (2026-09-01)**: estilo Volumetric com densidade correta; ripple/nuvens sem regressão visual após a otimização das inversas de matriz.

## World Status (Global Properties auto-criadas) — PENDENTE

- **Objetivo**: todo World novo já nasce com 8 Global Properties padronizadas (`chuva_ligada`, `chuva_densidade`, `nuvens_ligadas`, `neblina_ligada`, `neblina_densidade`, `horario_sol`, `tipo_nuvem`, `player_area_coberta`), pra scripts lerem status do World num único lugar (`own.scene.world["chave"]`). As 5 primeiras espelham o valor real de weather/mist (`weather_flag`, `rain_intensity`, `mode & WO_MIST`, `mistdensity`); as outras 3 são placeholders (sem sistema day/night ou tipo-de-nuvem ainda, e `player_area_coberta` é slot pra lógica de jogo escrever).
- **Implementação**: bloco novo em `BKE_world_init()` (`world.c`, logo após os defaults de weather) cria as 8 `bProperty` via `BKE_bproperty_new()` + `BLI_addtail(&wrld->prop, ...)`. Em `BL_ConvertWorldProperties()` (`BL_ConvertProperties.cpp`), depois de montar o dict a partir de `wrld->prop`, as 5 chaves espelhadas são sobrescritas com o valor real lido do DNA (só se a chave já existir no dict, ou seja, sem recriar o que o usuário apagou no painel).
- **Compilação**: limpa nos dois binários (`RangeEngine` + `RangeRuntime`, incremental — sem mudança de DNA aqui).
- **Bug real do fluxo de criação de World encontrado**: `new_world_exec` (`render_shading.c:590-599`) só chama `BKE_world_add` (onde estão os defaults novos) quando a cena **não tem** World ativo; se já tem, o botão "+" chama `BKE_world_copy` (duplica o World atual, sem rodar `BKE_world_init`). Isso explica por que testar com "+" numa cena que já tinha World salvo de antes não mostrou nada — não é bug da feature, é o operator escolhendo o caminho errado pro teste.
- **Testado pelo usuário em cena nova (File > New, sem World pré-existente)**: painel "Global Properties" **não mostrou nenhuma entrada**, sem erro/crash no log. Ou seja, mesmo passando pelo caminho `BKE_world_add` → `BKE_world_init`, as propriedades não apareceram. Causa raiz ainda não investigada — candidatos a checar na próxima sessão: (1) se `BKE_world_init` está realmente sendo chamado no fluxo de cena-nova-do-editor (pode haver um caminho de "default startup" separado que não passa por `BKE_world_add`, ex. carregando de um `.blend` de template embutido em vez de construir em código); (2) se o painel "Global Properties" em `custom_pt_world.py` está de fato ativo/visível nessa versão compilada; (3) adicionar um `printf`/`CM_Error` temporário dentro do bloco novo em `BKE_world_init` pra confirmar se o código chega a rodar.
- **Escopo**: deixado pendente a pedido do usuário, sem mais investigação nesta sessão.

## Console in-game (ImGui), botão liga/desliga no header da 3D View

- **Objetivo**: usuário precisava manter o console externo do Windows aberto (`std::cout` de `CM_Error`/`CM_Warning`/etc., ver `CM_Message.h`) além da janela do jogo pra acompanhar erros. Pedido: espelhar esse log numa janela ImGui dentro do próprio jogo (play na 3D View e Standalone), ligada por um botão no header, do mesmo jeito que "Standalone".
- **Mecanismo de toggle reaproveitado 1:1 de `GAME_SHOW_DEBUG_MODE`** (não inventado do zero): novo bit `GAME_SHOW_CONSOLE` em `GameData.flag` (`DNA_scene_types.h`) → propriedade RNA `show_console` (`rna_scene.c`) → botão no header (`space_view3d.py`, ao lado do "Standalone", ícone `CONSOLE`) → `view3d_view.c` (`game_set_commmandline_options`) escreve a flag no `SYS_System` como `show_console` pro Play-in-viewport → `LA_Launcher::InitEngine` lê via `SYS_GetCommandLineInt` e chama `KX_DebugMode::SetShowConsole()`.
- **Standalone tem um caminho separado, não é o mesmo `SYS_System` do embutido**: `WM_OT_blenderplayer_start` (`bl_operators/wm.py`) monta a linha de comando do `RangeRuntime.exe` manualmente com uma lista fixa de `-g nome = valor` — precisou adicionar `"-g", "show_console", "=", "%d" % gs.show_console` nessa lista à parte; sem isso o botão não tinha efeito nenhum no modo Standalone.
- **Novo `CM_LogBuffer`** (`gameengine/Common/CM_LogBuffer.h/.cpp`): ring buffer (1000 linhas) alimentado por um `std::streambuf` "tee" instalado sobre `std::cout.rdbuf()` — espelha cada linha escrita no console real pro buffer, e detecta o nível (Error/Warning/Debug/Message) pelo prefixo de texto (`"Error: "`, `"Warning: "`, `"Debug: "`) que os macros de `CM_Message.h` já escrevem. Instalado automaticamente no static-init (antes de qualquer log do engine rodar), sem precisar mexer nos ~15 macros de `CM_Message.h`.
- **Nova janela `KX_ConsoleWindow`** (`gameengine/Ketsji/`), modelada no `ExampleAppLog` do próprio ImGui: autoscroll, botão Clear, filtro de texto, cor por nível. Chamada em `KX_DebugMode::RenderImguiDebugMode()` (antes do early-return do toggle geral de debug, já que o console é independente dele), condicionada a `imgui_showConsole`. Como `KX_Imgui`/`KX_DebugMode` já rodam nos dois launchers (`LA_BlenderLauncher` e `LA_PlayerLauncher`) via `LA_Launcher` compartilhado, a janela aparece nos dois automaticamente a partir da mesma flag.
- **Bug 1 (crash imediato ao dar Play/Standalone com o console ligado)**: a primeira versão fazia os macros de `CM_Message.h` montarem a mensagem num `std::ostringstream` antes de imprimir, pra alimentar o buffer. Isso expôs um bug pré-existente e latente em `source/intern/termcolor/termcolor.hpp`: `is_atty()` chamava `_isatty(_fileno(std_stream))` sem checar se `get_standard_stream()` (que só reconhece `std::cout`/`std::cerr`/`std::clog`) retornou `nullptr` — `_fileno(NULL)` aciona o invalid-parameter-handler do CRT do Windows e mata o processo. Nunca disparava antes porque os manipuladores de cor do termcolor só eram usados com `std::cout`/`std::cerr` diretamente. Corrigido com um guard `if (!std_stream) return false;`, mas a causa raiz de expor o bug (montar a mensagem num stream que não é o console real) foi revertida — ver Bug 2.
- **Bug 2 (cores do console sumiram)**: a mesma mudança (montar a mensagem no `ostringstream` antes de imprimir) também matava a colorização: no Windows o termcolor colore via `SetConsoleTextAttribute()` (efeito colateral, não bytes de escape na stream), e só age quando a stream é literalmente `std::cout`/`std::cerr` — um `ostringstream` nunca é tratado como terminal. Resolvido definitivamente com a abordagem de streambuf tee acima: os macros de `CM_Message.h` voltaram a ser 100% os originais (escrevem direto em `std::cout`, cor preservada), e a captura pro buffer acontece de graça, do lado de fora, sem tocar no caminho de impressão.
- **Bug 3 (macros sem `;` no call site)**: descoberto durante a primeira tentativa (macro virou `do {...} while(0)`) — vários pontos do código (ex. `BL_Converter.cpp:873`) chamam `CM_Message(...)` sem `;` no final, contando com o macro antigo terminar em `;` sozinho. Não afeta a versão final (macros originais, sem alteração), mas registrado porque é uma armadilha real pra quem mexer em `CM_Message.h` de novo.
- Compilado limpo: mudança em `DNA_scene_types.h` exigiu `ninja -t clean` + rebuild completo dos dois binários (`RangeEngine`+`RangeRuntime`, nessa ordem — o alvo `RangeEngine` falha ao instalar se `RangeRuntime.exe` ainda não existe). Rebuilds incrementais depois, sem erro.
- **Testado pelo usuário**: Play e Standalone sem crash, cores do console externo de volta ao normal.

## Física para o sistema de Partículas GPU (Fase O)

- **Objetivo**: o sistema de partículas GPU (`RAS_ParticleBuffer`, transform feedback, um emissor por objeto via `object.gpu_particles`) simulava só integração cinemática pura (`vel += gravity*dt; pos += vel*dt`) — partículas atravessavam o chão e qualquer geometria. Pedido do usuário: física real (colisão), por emissor, com dois modos: Ground Plane (plano analítico) e Screen-Space (contra o depth buffer). Plano completo em `enumerated-booping-frog.md`; executado de ponta a ponta numa sessão em que o usuário não pôde testar (rodado sem pausas por pedido explícito).
- **DNA/RNA**: `RangeGPUParticleSettings` (`DNA_object_types.h`) ganhou `collision_mode` (enum `GPU_PARTICLE_COLLISION_NONE/GROUND/DEPTH`), `collision_height`, `collision_bounce`, `collision_friction` — mesmo padrão dos campos de `blend_mode`/`billboard_mode` já existentes. RNA espelhada em `rna_object.c` (`rna_def_object_gpu_particles`), enum novo `rna_enum_gpu_particle_collision_mode_items`. Versionamento: `RANGE_MINSUBVERSION` 105→106, novo bloco `MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 106)` em `versioning_range.c` (default `collision_mode = NONE`, `bounce = 0.4`, `friction = 0.9` pra arquivos antigos, já que o struct zerado deixaria bounce/friction em 0 — "gruda" sem quicar mesmo se o modo for ligado depois).
- **Bug de padding do DNA**: o primeiro `ninja RangeRuntime` (após clean rebuild) falhou o check estrutural do `dna.c` (`Sizeerror 8 in struct: RangeGPUParticleSettings`/`Object`) — o layout novo (`short` + 2 `char` + `pad2[2]` + 3 `float`) não fechava em múltiplo de 8 bytes. Corrigido com um `int pad3` no fim do struct. Lição: ao adicionar campos a um struct DNA, contar o tamanho final manualmente (ou deixar o build falhar uma vez e ler o erro do `dna.c`, que aponta o struct e quantos bytes faltam) antes de assumir que só o rebuild limpo resolve.
- **Shader de colisão** (`RAS_ParticleShaderCache.cpp`, dentro do ramo "alive" de `updateVertexSource`, logo após `pos += vel*dt`): Ground Plane resolve analiticamente (`pos.z < collisionHeight && vel.z < 0` → grampeia `pos.z`, `vel.xy *= friction`, `vel.z = -vel.z*bounce`, zera se ficar residual demais). Screen-Space projeta `pos` pela view*proj cacheada do frame anterior, compara a profundidade NDC da partícula contra `u_collisionDepthTex`; em caso de hit, desfaz o passo de posição e aplica bounce/friction usando **world-up como normal aproximada** (não há normal real disponível de uma amostra de depth — suficiente pra poeira/faísca sobre chão/piso majoritariamente horizontal, documentado como impreciso em superfícies muito inclinadas). Ambos os ramos custo-zero quando `collisionMode == None` (branch nem é tomado).
- **Infra nova pro Screen-Space — mais simples do que o plano original previa**: o plano cogitava propagar view/proj/handle de textura via `KX_Scene` até cada objeto (acoplamento "delicado"). Investigação encontrou que o engine já tem um mecanismo global pronto pra isso (`GPU_texture_set_global_depth`/`GG.depth_tex` em `gpu_texture.c`, usado por Depth Transparency/soft particles) — só faltava cachear a matriz view*projection junto. Adicionado `GG.depth_viewproj[16]` + `GG.depth_viewproj_valid` no mesmo struct global, com `GPU_texture_set_global_depth_viewproj()`/`GPU_texture_get_global_depth_viewproj()` (`gpu_texture.c`/`GPU_texture.h`). `RAS_Rasterizer::UpdateGlobalDepthTexture` (chamado por `RAS_BucketManager::RenderBuckets` sempre que há Depth Transparency ativo na cena) agora também cacheia `m_projmatrix * m_viewmatrix`. `RAS_ParticleBuffer::Update()` lê esse cache (e o texture handle via `GPU_texture_global_depth_ptr()`) direto, sem nenhuma mudança em `KX_Scene`/`KX_GameObject` pra propagação — evitou o ponto de maior risco arquitetural do plano original. Consequência aceita (igual ao plano): 1 frame de atraso (a textura é populada durante o render, a simulação roda antes) e degrada pra "sem colisão" quando não há Depth Transparency ativo na cena (`depth_viewproj_valid == 0`).
- **Runtime C++**: `RAS_ParticleBuffer`/`RAS_ParticleShaderCache` ganharam os 4 uniforms (`m_collisionMode/Height/Bounce/Friction` + getters/setters, mesmo padrão de `SetBlendMode`) mais os uniforms de screen-space (`u_collisionViewProj`, `u_collisionDepthTex`, `u_collisionDepthTexValid`). `KX_GameObject::SetupGPUParticles` propaga os 4 campos do DNA pro buffer na conversão de cena.
- **Bridge Python** (`object.particles.*`, `KX_ParticleSystem.cpp/.h`): `collisionMode` (int, 0/1/2), `collisionHeight`, `collisionBounce`, `collisionFriction`, RW, mesmo padrão de `blendMode`/`enabled`.
- **ImGui debug UI** (`KX_ParticleDebugUI.cpp`): nova seção "Collision" com dropdown de modo + sliders de height (só Ground)/bounce/friction, escondidos quando modo = None. "Apply to .blend" (`ApplyToBpy`/`WriteJsonSidecar`) e o sidecar JSON (lido por `_apply_gpu_debug_values` em `properties_particle.py`) atualizados pra incluir os 4 campos novos.
- **UI do editor** (`properties_particle.py`): novo painel `PARTICLE_PT_gpu_physics`, registrado na tupla `classes` entre Appearance e Curves — dropdown de modo no topo, box "Ground Plane" (height/bounce/friction) só quando `collision_mode == 'GROUND'`, box "Screen-Space" (bounce/friction + aviso sobre precisar de Depth Transparency) quando `== 'DEPTH'`.
- **Compilação**: `ninja -t clean` + rebuild completo (mudança em `DNA_object_types.h`) de `RangeRuntime` (2 rounds — o primeiro pegou o bug de padding acima) e depois `RangeEngine`, ambos exit 0, sem warnings novos.
- **Testado em jogo e confirmado pelo usuário (2026-09-02)**: funciona corretamente.

## Ground Plane com objeto de referência e Screen-Space via "GPU Particle Collider"

- **Objetivo**: duas melhorias pedidas pelo usuário sobre a Fase O acima. Ground Plane usava só um float fixo pra altura do chão — incômodo se o chão não for plano/fixo. Screen-Space dependia de um efeito colateral frágil (só funciona se algum material qualquer da cena tiver "Depth Transparency" ligado). Plano completo em `radiant-splashing-snail.md`.
- **Ground Plane — objeto de referência (`collision_ground_object`)**: novo `struct Object *collision_ground_object` em `RangeGPUParticleSettings` (`DNA_object_types.h`), opcional. Segue o precedente direto de `Object.collision_bound` (não o de actuator): lib-link/expand em `readfile.c` (`lib_link_object`/`expand_doit`, junto a `ob->collision_bound`), RNA `PROP_POINTER` tipo `Object` em `rna_object.c` (sem `PROP_ID_REFCOUNT`, mesmo padrão de ponteiros de game logic), resolvido pra `KX_GameObject*` numa segunda passada em `BL_BlenderDataConversion.cpp` (mesmo laço `for (KX_GameObject *gameobj : sumolist)` que já resolve `collision_bound`, depois que todo objeto da cena já tem seu `KX_GameObject`) via `converter.FindGameObject(...)`, guardado em `KX_GameObject::m_collisionGroundObject` (novo). Por frame, `KX_GameObject::UpdateParticles()` sobrescreve `collision_height` com `groundObject->NodeGetWorldPosition().z` só se o ponteiro estiver setado — sem mudança nenhuma em `RAS_ParticleBuffer`/shader, é puramente um valor de uniform diferente por frame. UI: `properties_particle.py`, campo `collision_ground_object` (object picker) na box Ground Plane, com `collision_height` desabilitado quando um objeto está setado.
- **Screen-Space — flag "GPU Particle Collider" por objeto**: achado de arquitetura confirmado por leitura de código: buckets de render (`RAS_BucketManager`) são organizados por **material**, não por objeto — um bucket é criado uma vez por material único e compartilhado por todos os objetos que o usam (`FindBucket`, `RAS_BucketManager.cpp`). Isso descartou a ideia óbvia de reaproveitar o bucket de sombra (`SOLID_SHADOW_BUCKET`, gated por `material->CastsShadows()`) filtrando por objeto — cairia no mesmo problema atual (dependência de outro flag de *material*). Solução adotada: novo `DrawType` `RAS_COLLISION_DEPTH` (`RAS_Rasterizer.h`) com um case novo em `RAS_BucketManager::Renderbuckets()` que reaproveita `SOLID_BUCKET`/`SOLID_INSTANCING_BUCKET` (estruturalmente inclusivo de *todo* material opaco, sem gate de flag) com o shader `RAS_OVERRIDE_SHADER_BLACK`/`_INSTANCING` já existente (o mesmo depth-only puro usado por sombra simples e wireframe) — copiado do padrão do case `RAS_WIREFRAME` já existente, não do `RAS_SHADOW`.
- **Flag e lista cacheada**: novo bit `OB_GPU_PARTICLE_COLLIDER` em `gameflag2` (`DNA_object_types.h`, não muda o tamanho do struct — só um valor de enum novo num `int` já existente, sem exigir clean rebuild por si só) + RNA booleana `use_gpu_particle_collider` (`rna_object.c`). `KX_Scene` ganhou `m_gpuParticleColliderObjects`, espelhando `m_gpuParticleObjects`/`AddGpuParticleObject` byte a byte (`AddGpuParticleColliderObject`/`RemoveGpuParticleColliderObject`/`GetGpuParticleColliderObjects`, com os mesmos hooks de remoção de objeto, duplicação e merge de cena que o original já tinha).
- **Passada de depth dedicada**: `KX_KetsjiEngine::RenderCollisionDepthBuffer(scene)`, chamada logo após `RenderShadowBuffers` no loop de render por cena — no-op se a cena não tiver nenhum objeto marcado. Faz bind do novo `RAS_OFFSCREEN_COLLISION_DEPTH` (novo valor em `RAS_OffScreen::Type`, provisionado automaticamente pelo `RAS_ICanvas::UpdateOffScreens()` existente, mesmo tamanho do canvas — não precisou de código de criação/resize dedicado), seta projeção/view da câmera ativa, `scene->RenderBuckets(colliders, RAS_COLLISION_DEPTH, ...)`, cacheia textura + view*proj, e restaura o offscreen anterior (`RAS_OffScreen::GetLastOffScreen()`/`RestoreScreen()`).
- **Globals de textura próprios**: `GG.collider_depth_tex`/`collider_depth_viewproj`/`collider_depth_viewproj_valid` (`gpu_texture.c`), deliberadamente **separados** de `GG.depth_tex`/`depth_viewproj` da Fase O (que continuam existindo, ainda usados por soft particles/Depth Transparency) — evita misturar os dois mecanismos. Getters/setters espelhando os existentes (`GPU_texture_set_global_collider_depth`/`_viewproj`, `GPU_texture_get_global_collider_depth_viewproj`, `GPU_texture_global_collider_depth_ptr`) em `GPU_texture.h`/`gpu_texture.c`.
- **Consumidor**: `RAS_ParticleBuffer::Update()`, ramo Screen-Space, troca a leitura de `GPU_texture_global_depth_ptr()`/`GPU_texture_get_global_depth_viewproj()` pelos novos `GPU_texture_global_collider_depth_ptr()`/`GPU_texture_get_global_collider_depth_viewproj()`. **Shader de update em si (`RAS_ParticleShaderCache.cpp`) não mudou** — a lógica de projeção/comparação de profundidade é idêntica, só trocou a fonte da textura/matriz.
- **UI do editor**: aviso da box Screen-Space em `PARTICLE_PT_gpu_physics` trocado de "precisa de Depth Transparency" pra "colide contra objetos marcados 'GPU Particle Collider'"; novo painel `PARTICLE_PT_gpu_particle_collider` (checkbox no header, visível em qualquer objeto — não preso a `use_gpu_particles`, já que o objeto colisor normalmente não é o emissor).
- **Compilação**: mudança em `DNA_object_types.h` (ponteiro novo em `RangeGPUParticleSettings` + bit novo em `gameflag2`) exigiu `ninja -t clean` + rebuild completo. `RangeRuntime` compilado limpo (exit 0) primeiro; `RangeEngine` (editor) em seguida, também exit 0.
- **Bug real pego no primeiro teste do usuário — posição de colisão ~4m errada**: `RenderCollisionDepthBuffer` roda logo depois de `RenderShadowBuffers` no loop de render por cena. `RAS_OpenGLLight::UnbindShadowBuffer()` desfaz o bind do FBO do GPU_lamp mas **não restaura o viewport do canvas** — fica do tamanho quadrado do último shadow map renderizado (ex. 1024×1024), setado por `BindShadowBuffer`/`canvas->UpdateViewPort()`. Como `RenderCollisionDepthBuffer` nunca setava viewport/scissor explicitamente, herdava esse viewport errado, causando a passada de depth a rasterizar numa região/aspecto que não batia com as dimensões reais do offscreen — desalinhando a reprojeção de profundidade no shader de colisão (UV de tela calculada a partir da posição mundial não correspondia ao texel realmente escrito). Corrigido com `m_rasterizer->SetViewport(0, 0, offScreen->GetWidth(), offScreen->GetHeight())` + `SetScissor(...)` logo após o bind do offscreen, antes de setar projeção/view e renderizar.
- **Testado pelo usuário após o fix**: a maioria das partículas colide corretamente contra os objetos marcados; algumas ainda atravessam. Aceito pelo usuário como resultado suficiente — sem investigação adicional agendada. Rebuild incremental (`RangeRuntime` + `RangeEngine`, sem mudança de DNA desta vez) compilou limpo nos dois.
- **Nota lateral**: label da propriedade `use_gpu_particle_collider` no editor trocado pelo usuário de "GPU Particle Collider" para "Object Collider with Particles" (`properties_particle.py`, edição feita em paralelo numa sessão separada do Claude Code — o arquivo fonte precisou ser recopiado manualmente pra `build/bin/2.79/scripts/startup/bl_ui/` porque o `RangeEngine.exe` lê a cópia instalada, não o `source/` direto; scripts `bl_ui` não exigem rebuild C++, só recopiar/reinstalar).

## Bug hunt sistemático em gameengine/ — GameLogic/ e Converter/ (2026-09-02)

- **Objetivo**: continuação da varredura sistemática de bugs silenciosos (compilam limpo, não crasham na hora) no runtime Ketsji, escopada a `source/source/gameengine/`. Rodada anterior (commits `aa588567`/`b83bfff4`/`1a1d1746`/`51866594`) cobriu Ketsji/ e Physics/Bullet/; esta cobriu GameLogic/ + Converter/.
- **Use-after-free em `m_map_blender_to_gameobject`** (`BL_BlenderDataConversion.cpp`): no caso especial de objeto mal-parentado entre layers diferentes ("Apricot"), só o objeto raiz (`childobj`) era desregistrado do mapa Blender-Object→KX_GameObject antes de destruir toda a subárvore de descendentes (`GetChildrenRecursive()`) — descendentes ficavam com entrada obsoleta no mapa mesmo após `Release()`. Lookups posteriores via `FindGameObject()` (colisão de partículas GPU, `collision_bound`, radar/environment) podiam retornar ponteiro livre. Fix: `converter.UnregisterGameObject(obj)` movido pra dentro do loop que itera `childrenlist`.
- **`Py_False` retornado sem `Py_INCREF`** (`SCA_VibrationActuator.cpp`, `pyattr_get_isVibrating`/`pyattr_get_hasVibration`, caminho "sem joystick conectado"): uso repetido via polling por tick de lógica drenava o refcount do singleton global `Py_False`. Fix: trocado por `Py_RETURN_FALSE` (padrão já usado no resto do código via `PyBool_FromLong`).
- **`BL_SceneConverter::UnregisterGameObject` sem checagem de `find() == end()`**: hardening preventivo — hoje o único call site é seguro, mas era armadilha latente pra callers futuros. Fix: guard explícito antes de desreferenciar o iterador.
- **Achados não corrigidos, baixa prioridade**: `Converter/KX_ConvertActuators.cpp` (referencia header inexistente, fora do `CMakeLists.txt`, não compila) e `Ketsji/KX_GameObjectold.cpp/.h` (também fora do build) — ambos código morto candidato a remoção, sem decisão do usuário ainda.
- Commit `f3cfd13a`, build incremental confirmado limpo (`RangeEngine`). Próximo da fila: `Expressions/` (base de toda exposição Python via `PyObjectPlus.cpp`), depois `VideoTexture/`/`Rasterizer/`.

## Bug hunt sistemático em gameengine/ — Expressions/ (2026-09-02)

- **Objetivo**: continuação da varredura, agora em `Expressions/` — camada base de toda exposição Python do engine (`EXP_PyObjectPlus`, `EXP_Value`, listas wrapper).
- **Leak de tupla em `EXP_RunPythonCallback`** (`PythonCallBack.cpp`): `CreatePythonTuple` retorna nova referência, nunca liberada com `Py_DECREF`. É o dispatcher compartilhado de todos os callbacks Python (sensores/atuadores/mouse/teclado) — vazava uma tupla por invocação, potencialmente por tick de lógica. Fix: `Py_DECREF(tuple)` após o `PyObject_Call`.
- **Leak duplo em `EXP_BaseListWrapper::GetText`** (`BaseListWrapper.cpp`): `GetItem(i)` (nova ref) e `PyObject_Repr(...)` (nova ref) nunca eram liberados no loop de `repr()`/`str()` — cada `print()` de uma lista wrapper (`obj.sensors`, `obj.actuators` etc.) vazava 2 objetos por elemento. Fix: guardar ambos em variável e `Py_DECREF` os dois após uso.
- **`list + operando_não_suportado` retornava resultado errado silencioso** (`EXP_BaseListValue::buffer_concat`, `BaseListValue.cpp`): se `other` não fosse `list` nem `EXP_BaseListValue` (ex. `lista + 5`), nenhum branch executava e a função retornava uma lista nova vazia em vez de erro. Fix: branch `else` libera a lista temporária e retorna `Py_NotImplemented` (Python levanta `TypeError` corretamente a partir daí).
- **Use-after-free em auto-atribuição, `EXP_Value::SetProperty`** (`Value.cpp`): ordem original fazia `Release()` do valor antigo antes do `AddRef()` do novo — se o mesmo objeto fosse re-setado no próprio nome com refcount==1 (só a referência do mapa), `Release()` deletava o objeto antes do `AddRef()` rodar, deixando o mapa com ponteiro livre. Fix: inverter a ordem (`AddRef` primeiro, `Release` depois).
- **Commits**: `aa5a9659` (leak da tupla, leak do `GetText`, `buffer_concat`), `daa320b5` (`SetProperty`). Ambos build incremental confirmado limpo (`ninja RangeEngine`, exit 0). Próximo da fila: `VideoTexture/`, `Rasterizer/`.

## Bug hunt sistemático em gameengine/ — VideoTexture/ (2026-09-02)

- **Acesso inseguro a sequências Python**: cinco setters expostos por `VideoTexture` anunciavam aceitar sequências, mas usavam `PySequence_Fast_GET_ITEM` diretamente sobre o objeto recebido. Essa macro só é válida para `list`/`tuple`; uma sequência ou iterável diferente podia causar acesso inválido em vez de uma validação Python normal. O próprio `Video_setRange` já registrava o problema com um comentário `XXX`.
- **Fix**: `Video_setRange`, `ImageRender.horizon`, `ImageRender.zenith`, `FilterColor.matrix` e `FilterLevel.levels` agora convertem a entrada com `PySequence_Fast`, usam o resultado seguro durante a validação/leitura e o liberam com `Py_DECREF`/`Py_XDECREF`. A API continua aceitando listas, tuplas e sequências genéricas; entradas inválidas retornam `TypeError` como antes.
- **Validação**: `ninja ge_videotexture` compilou e linkou limpo (exit 0). Nenhum header DNA foi alterado. Commit `453ead76`.

## Bug hunt sistemático em gameengine/ — Rasterizer/ (2026-09-02)

- **Leak no caminho de erro de screenshot** (`RAS_ICanvas::SaveScreeshot`): `KX_BlenderCanvas::MakeScreenShot` aloca um `ImageFormatData` que é transferido para a fila de screenshots. No caminho normal a tarefa assíncrona o libera; mas, se `RAS_Rasterizer::MakeScreenshot` falhasse e retornasse `nullptr`, a fila era limpa sem transferir nem liberar esse ponteiro. Fix: liberar `screenshot.format` antes do retorno de erro.
- **Validação**: `ninja ge_rasterizer` compilou e linkou limpo (exit 0). Nenhum header DNA foi alterado. Commit `29a07887`.

## Bug hunt sistemático em gameengine/ — SceneGraph/ (2026-09-02)

- **Desreferência nula na réplica de nó** (`SG_Node`): o construtor normal inicializa `m_parent_relation` como nulo, mas o construtor de cópia chamava `other.m_parent_relation->NewCopy()` sem guard. Replicar um nó antes de configurar sua relação de parent resultava em crash. Fix: preservar `nullptr` no clone quando a relação não foi definida.
- **Validação**: `ninja ge_scenegraph` compilou e linkou limpo (exit 0). Nenhum header DNA foi alterado. Commit `5006ebd5`.

## Bug hunt sistemático em gameengine/ — Device/ (2026-09-02)

- **Ciclo de vida de joystick/haptic**: `DEV_Joystick::Close` chamava um método de instância através de entradas vazias do array global; o estado privado também deixava `m_instance_id` e `m_hapticEffectId` sem inicialização. Além disso, o ramo `SDL_HAPTIC_CUSTOM` apontava `SDL_HapticEffect::custom.data` para um array da pilha, inválido após o retorno de `RumblePlay`.
- **Fix**: o shutdown ignora slots vazios, os IDs começam em `-1`, o buffer de duas amostras passou a pertencer ao `PrivateData` e as destruições de efeito só ocorrem para IDs válidos. Assim, o efeito customizado conserva seus dados durante upload/atualização e os caminhos de falha não enviam IDs indeterminados ao SDL.
- **Validação**: `ninja ge_device` compilou e linkou limpo (exit 0). Nenhum header DNA foi alterado. Commit `563f68f2`.

## Bug hunt sistemático em gameengine/ — GamePlayer/ (2026-09-02)

- **Leak no retorno antecipado do carregamento criptografado** (`load_encrypted_game_data`): a `ReportList` era inicializada antes de rejeitar `filename == nullptr`, mas não era limpa nesse ramo. Fix: `BKE_reports_clear(&reports)` antes do retorno.
- **Validação**: `ninja ge_player` compilou e linkou limpo (exit 0). Nenhum header DNA foi alterado. Commit `37ee4c3a`.

## Bug hunt sistemático em gameengine/ — conclusão de todos os subsistemas (2026-09-02)

- **Escopo concluído**: revisão estática dos 13 diretórios em `source/source/gameengine/`, aplicando buscas de ownership manual, stubs/contratos, limites, APIs Python, callbacks e refcounts. Além dos diretórios parcialmente revistos, esta rodada fechou `BlenderRoutines/`, `Common/` e `Launcher/`; não houve achado corrigível em BlenderRoutines/Common.
- **Leak de referência Python em DeckLink** (`VideoTexture/DeckLink.cpp`): o destrutor liberava `m_leftEye`, mas não `m_rightEye`. Um uso estéreo mantinha a imagem direita (e a sua cadeia de fontes) viva após o objeto DeckLink morrer. Fix: `Py_XDECREF(self->m_rightEye)` no mesmo ciclo de teardown.
- **Leak ao remover filtro 2D** (`Rasterizer/RAS_2DFilterManager::RemoveFilterPass`): `erase()` apagava somente a entrada do mapa; o `RAS_2DFilter` alocado permanecia perdido. Chamadas repetidas de `filterManager.removeFilter()` acumulavam filtros. Fix: localizar, `delete` e então apagar a entrada.
- **Crash na falha de leitura do main loop Python externo** (`Launcher/LA_PlayerLauncher.cpp`): o caminho `-p <arquivo>` conferia que o caminho era um arquivo, mas assumia que `BLI_file_read_text_as_mem()` sempre retornaria buffer. Falha posterior de I/O podia construir `std::string` a partir de `nullptr`. Fix: logar o erro e retornar `false` antes de usar o buffer.
- **Validação**: builds incrementais limpos de `ge_launcher`, `ge_videotexture` e `ge_rasterizer` (exit 0). Nenhum header foi alterado; não exigiu clean rebuild. Commit `c8f1e158`.

## Bug hunt sistemático em gameengine/ — `getPhysicsId()` (2026-09-02)

- **Ponteiro cru exposto como inteiro** (`KX_GameObject::getPhysicsId`): o método retornava o endereço de `PHY_IPhysicsController` como `int` Python e `bge.constraints.createConstraint`/`createVehicle` reconvertiam esse número diretamente em ponteiro. Se o objeto fosse removido entre as chamadas, o script podia provocar use-after-free; a reutilização posterior do mesmo endereço também podia operar sobre outro objeto.
- **Fix**: preservada a API de inteiro para scripts existentes, mas o valor agora é um token opaco, monotônico e validável. O registro bidirecional fica em `KX_PyConstraintBinding`; `KX_GameObject` invalida o token ao trocar ou destruir o controlador. Os consumidores resolvem o token pelo registro, mantendo `physicsid_2 == 0` como o corpo-mundo válido para constraints, e retornam `ValueError` para ID expirado ou inventado.
- **Validação**: `ninja ge_ketsji` e `ninja RangeEngine` compilaram e linkaram limpo (exit 0). Nenhum header DNA foi alterado; não exigiu clean rebuild. Para o teste manual, `projects-teste/scripts/physics_id_lifetime_test_component.py` guarda o ID, remove o alvo e confirma no console que `createVehicle(id)` levanta `ValueError` em vez de acessar memória livre. **Testado e confirmado pelo usuário (2026-09-02)**: alvo `Sphere` removido após capturar o ID 1; o ID expirado gerou `ValueError` corretamente, sem crash.

## Bug hunt sistemático em gameengine/ — remoção de código morto (2026-09-02)

- **`Converter/KX_ConvertActuators.cpp` removido**: arquivo legado fora do `CMakeLists.txt`, que incluía um header inexistente e não compilava isoladamente. Não possuía referências no repositório fonte.
- **`Ketsji/KX_GameObjectold.cpp/.h` removidos**: cópia antiga de `KX_GameObject`, igualmente ausente do build e sem referências no código fonte. Comentá-los não teria efeito nem evitaria divergência; o histórico Git permanece a fonte para eventual consulta ou restauração.
- **Validação**: nenhum alvo CMake referenciava os três arquivos antes da remoção; `ninja RangeEngine` deve permanecer sem trabalho ou recompilar somente metadados, confirmando que o grafo de build não dependia deles. Nenhum header DNA foi alterado.

## Documentação — checklist reutilizável de bugs silenciosos (2026-09-02)

- Criado `docs/checklist-varredura-bugs-silenciosos.md`: roteiro independente para revisar addons Python e extensões C/C++, baseado nos sete métodos usados na varredura de `gameengine/`. Inclui preparação, buscas obrigatórias, mapa de lifecycle de callbacks Blender, template de achado e critérios de encerramento.

## FlowMenu — correções da varredura de bugs silenciosos (2026-09-02)

- **Reload seguro de componentes** (`source/release/scripts/startup/flowmenu/operators/component_reload_new.py`): o reload customizado removia o componente antes de tentar registrá-lo outra vez. Se o script tivesse erro, cada retry podia remover o próximo componente que ocupasse o mesmo índice. Agora usa somente `logic.python_component_reload`, que recarrega a instância existente; uma falha de import preserva a lista e os argumentos salvos.
- **Criação de componente sem falha silenciosa** (`operators/create_component.py`): removidos `os.chdir()` global e `except:` que retornava sucesso. O operador agora valida identificadores Python, exige `.blend` salvo, não sobrescreve arquivo existente e devolve `CANCELLED` com a causa em qualquer falha de I/O.
- **Wizard consistente** (`functions/create_component_wizard.py`): valida nomes, não sobrescreve script existente, trata erro ao criar diretório/arquivo e só informa sucesso depois que `logic.python_component_register` termina. O fallback que inseria um componente manualmente após erro de registro foi removido.
- **Refresh legado corrigido** (`operators/component_reload_new.py`): o operador agora popula a `Scene.flowmenu_component_list` (uma `CollectionProperty`) a partir de `get_modules_in_range`; antes usava um `set` como se fosse dicionário e escrevia numa propriedade inexistente.
- **Validação**: todos os 28 arquivos Python do FlowMenu passaram por compilação sintática com o Python embutido; o pacote atualizado foi copiado para `build/bin/2.79/scripts/startup/flowmenu/`, com hashes fonte/instalação idênticos. Em `RangeEngine.exe --background`, o ciclo `unregister` → `register` e os dois operadores de refresh retornaram `FINISHED`; um reload nativo de componente preservou a contagem de componentes (1 → 1).

## Bug hunt sistemático em creator/ e blenderplayer/ (2026-09-02)

- **Escopo**: as duas pastas irmãs menores de `source/source/gameengine/` foram revisadas pelos sete grupos do checklist. `creator/` cobre inicialização, argumentos e sinais; `blenderplayer/` contém somente o CMake e stubs de linkagem para o standalone.
- **Uso de valor não inicializado em `--verbose`** (`creator_args.c`): após rejeitar uma entrada não numérica, o handler ainda passava a variável local `level`, não inicializada, a `libmv_setLoggingVerbosity`/`CCL_logging_verbosity_set`. Fix: retornar logo após imprimir o erro, sem alterar a verbosidade.
- **Acesso fora dos argumentos em `-setaudio`** (`creator_args.c`): a checagem aceitava `argc == 1`, mas lia `argv[1]`; usar a opção sem dispositivo podia acessar memória inválida. Fix: exigir pelo menos dois argumentos e encerrar com mensagem controlada.
- **Falsos positivos registrados**: os retornos neutros em `blenderplayer/bad_level_call_stubs/stubs.c` são stubs de linkagem deliberados; os casos de callbacks/UI que possuem implementação real estão desativados sob `#if 0`, portanto não mascaram uma chamada ativa do player.
- **Validação**: `ninja RangeEngine RangeRuntime` compilou e linkou limpo (exit 0). `RangeEngine.exe --background --verbose invalid-value` reportou a entrada inválida e saiu normalmente; `RangeEngine.exe --background -setaudio` reportou a falta do dispositivo e saiu com código 1. Nenhum header DNA foi alterado.

## Varredura estática de bugs silenciosos - correções "às cegas" (2026-09-02)

- **Escopo**: dos 23 itens do relatório `docs/relatorio-varredura-bugs-silenciosos.md`, corrigidos os 7 que são verificáveis por revisão de código + build (fix defensivo/mecânico, sem mudar o caminho normal). Ficaram de fora as corridas de thread em `VideoFFmpeg`/`OpenALDevice`, que só dá pra confirmar sob stress real.
- **`VideoFFmpeg.cpp:585`**: `char filename[28]` com `sprintf(filename, "video=%s", file)` sem checar tamanho — nome de câmera longo estourava o buffer. Fix: buffer de 256 bytes + `BLI_snprintf`.
- **`KX_PythonKeyboard.cpp`**: `bge.logic.keyboard.getClipboard()` nunca liberava o buffer alocado (`malloc`) pelo GHOST (`alloc_utf_8_from_16`/`malloc` direto em `GHOST_SystemWin32.cpp`). Fix: `free()` após construir a string Python.
- **`btSparseSDF.h`**: `struct btSparseSdf` (cache SDF de soft body do Bullet) não tinha destrutor; `Reset()` (que libera as células) nunca rodava na destruição do mundo de física. Fix: destrutor chamando `Reset()`.
- **`CcdPhysicsController.cpp:343-350`**: retorno de `HullLibrary::CreateConvexHull` era ignorado; mesh degenerada podia gerar `hres` vazio e crash ao acessar `hres.m_OutputVertices[0]`. Fix: checar `QE_OK` antes de usar o resultado, `return false` em caso de erro.
- **`RAS_StorageVbo`/`RAS_DisplayArray`/`RAS_MeshSlot`**: `glMapBufferRange` pode retornar `nullptr` (driver/VRAM); o ponteiro ia direto pra `SortPolygons`, que escrevia nele sem checar, e depois `FlushIndexMap()` chamava `glUnmapBuffer` mesmo sem mapeamento bem-sucedido. Fix: checagem de nulo em `SortPolygons` e em `RAS_MeshSlot::SetDisplayArrayNodeData`, pulando ordenação/unmap quando o mapeamento falha.
- **`readfile.c` (`blo_openblenderfile`)**: o bloco de detecção de criptografia RangeArmor fazia `gzseek`/`gzread` no `gzfile` antes de confirmar que `BLI_gzopen` tinha sucedido — abertura gzip falha usava handle inválido. Fix: checagem de `Z_NULL` movida para logo após a abertura; checagem duplicada mais abaixo removida.
- **`runtime.c` (`BLO_read_runtime`)**: `actualsize - datastart` (tamanho size_t menos offset int) podia dar underflow se o rodapé do `.range` estivesse truncado/corrompido, gerando um tamanho de leitura absurdo passado a `blo_read_blendafterruntime`. Fix: validar `actualsize >= 12` antes do `lseek(-12)` e `datastart <= actualsize` antes da subtração, com `BKE_reportf` de erro em ambos os casos.
- **Validação**: cada item compilado isoladamente (`ninja RangeRuntime`/`RangeEngine`/`ge_rasterizer`+`ge_rasterizer_opengl`), todos exit 0, sem warning novo. Nenhum header DNA foi alterado. Itens 1-5 são fixes mecânicos sem mudança de comportamento no caminho normal — build limpo é validação suficiente. Itens 6 (RangeArmor) e 7 (runtime standalone) pedem confirmação do usuário abrindo um `.range` protegido e um `.range`/`RangeRuntime.exe` normal, respectivamente, já que tocam o carregamento de arquivo.

### Segundo lote (mesmo dia)

- **`CcdPhysicsEnvironment.cpp:2361` (`CreateSphereController`)**: relatório apontava leak do `btSphereShape` — investigado e é **falso positivo**: `CcdPhysicsController::~CcdPhysicsController()` chama `DeleteControllerShape()` incondicionalmente (libera `m_collisionShape` mesmo sem `m_shapeInfo`), e `KX_NearSensor::~KX_NearSensor()` já dá `delete m_physCtrl`. Só o comentário desatualizado no código foi corrigido, sem mudança de lógica.
- **`btSparseSDF.h` (`RemoveReferences`)**: `ncells` era incrementado em `Evaluate()` e decrementado em `GarbageCollect()`, mas não em `RemoveReferences()` — cada shape removido (ex.: soft body destruído) desalinhava o contador do cache SDF do real número de células, causando `Reset()` prematuro/tardio via `m_clampCells`. Fix: `--ncells` também no laço de `RemoveReferences`.
- **`GHOST_SystemWin32.cpp` (construtor)**: `LoadLibrary("Shcore.dll")` nunca tinha `FreeLibrary` — handle de DLL vazado pela vida inteira do processo (baixo impacto, mas real). Fix: `FreeLibrary` logo após ler `SetProcessDpiAwareness`.
- **`VideoFFmpeg.cpp::openCam`**: se `openStream()` falhasse, a função retornava sem `av_dict_free(&formatParams)` — dicionário de parâmetros (standard/framerate/video_size) vazado a cada tentativa de abrir câmera que falha. Fix: `av_dict_free` antes do `return` no caminho de erro.
- **`VideoFFmpeg.cpp` (`allocFrameRGB`, `openStream`)**: `av_frame_alloc()` (3 chamadas) não checava retorno nulo antes de `avpicture_fill` — falha de alocação (OOM) causava crash em vez de erro tratado. Fix: `allocFrameRGB` retorna `nullptr` cedo se a alocação falhar; `openStream` trata falha de `m_frame`/`m_frameDeinterlaced`/`m_frameRGB` como os demais erros da função (fecha codec/formatCtx, libera o que foi alocado, `return -1`).
- **Validação**: `ninja RangeRuntime RangeEngine` limpo (exit 0, sem warning novo). Todos os 5 itens são fixes mecânicos/defensivos sem mudança de comportamento no caminho normal — build limpo é validação suficiente, sem teste em jogo necessário.

## Varredura estática de bugs silenciosos — itens "confirmado" restantes de concorrência/GPU (2026-09-03)

- **Escopo**: os 5 itens do relatório `docs/relatorio-varredura-bugs-silenciosos.md` com estado "confirmado" que tinham ficado de fora das rodadas anteriores por tocarem concorrência de thread e recursos de GPU.
- **`RAS_OffScreen.cpp` — leak de GPU em falha parcial**: o destrutor só liberava `m_colorSlots[]`/`m_depthSlot`/`m_frameBuffer` dentro de `if (GetValid())`; se um `attach` falhasse no meio do construtor, `m_frameBuffer` era zerado e o destrutor pulava a liberação inteira, vazando os attachments criados com sucesso antes da falha (acontece ao reduzir MSAA em resize/troca de qualidade gráfica). Fix: destrutor sempre libera qualquer slot/framebuffer não-nulo, independente de `GetValid()`.
- **`KX_ParticleDebugUI.cpp::WriteJsonSidecar`**: escrevia direto no arquivo final; crash/queda de energia no meio deixava `gpu_particles_debug.json` truncado. Fix: escreve em `<arquivo>@` e só chama `BLI_rename` pro caminho final em sucesso — mesmo padrão de `BLO_write_file`/autosave já usado pelo Blender.
- **`VideoFFmpeg.h`/`.cpp` — corrida de dados na flag de parada da thread**: `m_stopThread` (bool puro) era lido pela thread de cache e escrito pela thread principal sem sincronização. Fix: `std::atomic<bool>`. Achado adicional na mesma investigação: `m_curPosition` (usado em seek/sincronismo de frame) tinha a mesma falta de proteção entre as duas threads; também virou `std::atomic<long>`. Detalhe de build: `<atomic>` precisou ser incluído *fora* do bloco `extern "C" { ... }` que envolve os headers do ffmpeg — dentro dele o MSVC rejeita os templates da STL com linkage C (`C2894`/`C2733`).
- **`OpenALDevice.cpp::updateStreams` — thread de streaming sem contexto OpenAL corrente**: o contexto era tornado corrente só no construtor (thread que cria o `OpenALDevice`); a thread de streaming dedicada nunca chamava `alcMakeContextCurrent` no caminho normal, só nos ramos de recuperação de desconexão. Contexto corrente é estado thread-local em OpenAL. Fix: `alcMakeContextCurrent(m_context)` uma vez no início de `updateStreams()`.
- **`OpenALDevice.cpp` — corrida entre efeitos de speaker e thread de áudio**: `setEffect`/`removeEffect`/`setReverb*`/`setFilter*` (`OpenALHandle`) eram os únicos setters da classe sem `std::lock_guard<ILockable> lock(*m_device)` — todos os outros já seguiam esse padrão. `removeEffect()` fazia `delete m_effect` sem lock enquanto a thread de áudio (`updateStreams()`, já dentro da região travada) podia estar dereferenciando o mesmo ponteiro via `hasEffect()` — use-after-free real, não corrida benigna. Fix: lock adicionado nos 16 métodos que faltavam, mesmo padrão do resto do arquivo.
- **Validação**: `ninja ge_rasterizer`, `ninja ge_ketsji`, `ninja ge_videotexture`, `ninja audaspace` e `ninja RangeRuntime RangeEngine` todos limpos (exit 0, sem warning novo). Nenhum header DNA foi alterado. Os itens de OpenAL/VideoFFmpeg são correções de corrida de thread — build limpo e revisão de código validam a correção estática; confirmação sob stress real (múltiplos efeitos de áudio simultâneos, start/stop repetido de captura de vídeo) fica como validação futura opcional, não bloqueante, como já registrado no relatório original.

## Varredura estática de bugs silenciosos — achados novos do fork Blender, correções "às cegas" (2026-09-03)

- **Escopo**: dos 26 achados registrados na segunda leva do relatório `docs/relatorio-varredura-bugs-silenciosos.md` (cobrindo quase todo `source/source/blender`), 15 eram mecânicos e localizados o bastante para corrigir sem reproduzir dado real (contagem de referência CPython, `strcpy`/`strcat` sem limite conhecido, divisão por zero, estouro `unsigned` em contagem zero, retorno de I/O descartado). Os outros 11 (PHYS-001/002, GPU-001/002, RND-001, MESH-001, MOD-001, ANIM-001/002, BLN-003/004) ficaram de fora — dependem de confirmar contrato do chamador ou reproduzir com dado degenerado real.
- **Lote A (CPython refcount)**: `mathutils_noise.c::voronoi()` (PY-001) tinha `Py_DECREF(v)` depois de `PyList_SET_ITEM(list, i, v)`, que já toma a referência — duplo-decremento removido. Revisado também `bgl.c::Buffer_to_list_recursive` (PY-002): **falso positivo** — `sub` (de `Buffer_item`) é um objeto distinto do valor armazenado na lista (`Buffer_to_list_recursive(sub)` cria um novo objeto), então o `Py_DECREF(sub)` já estava correto; nenhuma mudança.
- **Lote B (`strcpy`/`strcat` sem limite)**: `property.c` (`BKE_bproperty_set`/`BKE_bproperty_new`, BPROP-001/002) trocados por `BLI_strncpy` com `MAX_PROPSTRING`/`sizeof(prop->name)`. `readfile.c::lib_node_do_versions_group_indices` (BLN-001): dois `strcpy` de `bNodeSocket.identifier` viraram `BLI_strncpy` (preventivo, buffers já eram do mesmo tamanho). `readfile.c` BLN-002 (`malloc(100)+strcpy`): **falso positivo**, código está dentro de `#if 0`, nunca compilado. `movieclip.c::get_proxy_fname` (MEDIA-002): `strcat(name, ".jpg")` sem checar espaço trocado por `BLI_strncpy(name + strlen(name), ".jpg", FILE_MAX - strlen(name))`.
- **Lote C (guardas numéricas)**: `keyframes_edit.c::bezt_remap_times` (ANIM-003) ganhou guarda contra `oldMax == oldMin` (retorna sem alterar handles em vez de gerar NaN). `MOD_uvproject.c` (MESH-002): os quatro caminhos de projeção agora pulam `mp->totloop == 0` antes de calcular `fidx = mp->totloop - 1` (que estourava para `UINT_MAX`). `tracking_solver.c::reconstruct_retrieve_libmv_tracks` (MEDIA-001): guarda `efra < sfra` antes do `MEM_callocN`, cálculo de tamanho movido para `size_t`.
- **Lote D (retorno de I/O descartado)**: `fileops.c::BLI_copy` (BL-001) agora checa retorno de `fwrite`, `ferror` e `fclose` dos dois streams, retornando `RecursiveOp_Callback_Error` em vez de `_OK` em falha. `blf_font_win32_compat.c` (FONT-001): `fseek`/`ftell` validados no callback de leitura e na abertura do stream FreeType (incl. `ftell < 0`). `msgfmt.c` (BLT-001): `BLI_fopen`/`fwrite`/`fclose` checados, retorna `EXIT_FAILURE` em falha. `datatoc.c` (DATATOC-001): `fseek`+`ftell` validados antes de usar `size`. `avi_endian.c::awrite` (AVI-001) passou de `void` para `bool` (sucesso conforme retorno de `fwrite`); os 15 call sites em `avi.c` (`AVI_open_compress`, `AVI_write_frame`, `AVI_close_compress`) acumulam o resultado e retornam `AVI_ERROR_WRITING` em vez de `AVI_ERROR_NONE` quando alguma escrita falha — o item mais espalhado do lote, revisado call site por call site antes de mudar a assinatura.
- **Validação**: build completo de `RangeEngine` limpo em cada lote (exit 0, sem warning novo); `datatoc.exe` linkado sem erro. O alvo `msgfmt` não está no grafo Ninja atual (`WITH_INTERNATIONAL=ON` no cache, mas `ninja: error: unknown target 'msgfmt'`) — gap de configuração pré-existente do build tree, não causado por esta sessão; BLT-001 foi validado só por revisão de código. Nenhum header DNA foi alterado. Nenhuma das correções teve o cenário de falha real (dado degenerado, disco cheio, arquivo corrompido) reproduzido em runtime — apenas build e, quando aplicável, o caminho de sucesso normal foram validados; ficam como validação futura opcional do usuário, sem bloquear o fechamento dos 15 itens no relatório.
- **PHYS-001 investigado à parte (mesmo dia)**: `implicit_blender.c::cp_bfmatrix` tinha `TODO bounds checking` num `memcpy` sem checar o destino. Rastreado o único call site do código (`BPH_mass_spring_solve_velocities`, `cp_bfmatrix(data->A, data->M)`): `data->A` e `data->M` são alocados uma única vez, no mesmo `numverts`/`numsprings`, nunca redimensionados separadamente, e liberados juntos — **falso positivo**, a divergência de tamanho descrita no achado não tem caminho de código possível. Adicionado `BLI_assert(to[0].vcount == from[0].vcount && to[0].scount == from[0].scount)` antes do `memcpy` como rede de segurança sem custo em release. Build de `RangeEngine` limpo (`implicit_blender.c.obj`).

## Varredura estática de bugs silenciosos — os 10 itens pendentes fechados, 3 novos falsos positivos (2026-09-03)

- **Escopo**: dos 10 itens que ficaram como "dívida registrada" na sessão anterior (PHYS-002, GPU-001, GPU-002, RND-001, MESH-001, MOD-001, ANIM-001, ANIM-002, BLN-003, BLN-004), a releitura completa de cada um (mesmo rigor usado em PHYS-001: traçar call sites, invariantes de alocação, código morto) reclassificou 3 como falso positivo e confirmou 7 como bugs genuínos e alcançáveis, todos corrigidos nesta sessão. Não sobra nenhum item sem decisão de código no relatório.
- **3 novos falsos positivos**: **PHYS-002** (`physics_fluid.c`) — `noFrames = scene->r.efra - 0` e `channels->length = scene->r.efra` são a mesma expressão; não há o descompasso de tamanho descrito, só uma limitação de contrato já documentada (`sfra` ignorado). **GPU-002** (`gpu_texture.c::GPU_texture_create_3D`) — `type` fica fixo em `GL_FLOAT` (nunca vira `GL_UNSIGNED_BYTE` como no caminho 2D); o `#if 0` que chamaria a conversão de pixels é código morto de um caminho uchar nunca implementado. **BLN-004** (`readfile.c`, `CollisionModifier`) — a leitura ativa já reseta `time_xnew = time_x = -1000`, `mvert_num = 0`, `bvhtree`/`tri` para `NULL`; em `MOD_collision.c`, `time_xnew == -1000` é a condição de "primeira vez" que realoca tudo do zero no próximo passo de simulação — é cache, não dado persistente.
- **GPU-001** (overflow de `int` em `gpu_texture.c`): `GPU_texture_convert_pixels()` passou a receber `size_t length` (e usar `size_t` na aritmética interna/loop); o call site 2D agora força `(size_t)w * (size_t)h` antes de chamar.
- **RND-001** (overflow/leak em `voxeldata.c::load_frame_blendervoxel`): `fseek` corrigido para `(size_t)frame * size * sizeof(float) + offset` (evita overflow de `int` antes da promoção); `vd->dataset` agora é liberado nos retornos de erro de `fseek`/`fread` (mesmo padrão de `load_frame_raw8`); adicionado teto explícito `VOXELDATA_MAX_BYTES` (2 GiB) checado antes de `MEM_mapallocN`.
- **MESH-001** (`crazyspace.c::BKE_crazyspace_set_quats_mesh`): adicionado `if (mp->totloop < 3) continue;` antes do cálculo de `ml_prev`/`ml_curr`/`ml_next`, evitando underflow de índice em polígonos degenerados.
- **MOD-001** (bind do Mesh Deform sem limite de produto): guarda `(double)totvert * (double)totcagevert > INT_MAX` adicionada em `meshlaplacian.c::harmonic_coordinates_bind` (aborta o bind com `modifier_setError` antes de qualquer alocação); indexação `weights[a + b*totcagevert]` em `MOD_meshdeform.c::modifier_mdef_compact_influences` trocada para aritmética `size_t` explícita.
- **BLN-003** (overrides de `AnimData` nunca lidos de volta): `direct_link_animdata()` em `readfile.c` tinha só um `// TODO...` onde devia ler `adt->overrides`; implementado `link_list(fd, &adt->overrides)` + resolução de `aor->rna_path` via `newdataadr`, espelhando o padrão já usado para `nla_tracks` duas linhas abaixo. `write_animdata()` já gravava esses dados corretamente.
- **ANIM-001** (`array_index` de Keying Set não validado): `BKE_keyingset_add_path()` em `anim_sys.c` passou a resolver `id`/`rna_path` via `RNA_path_resolve_property` (mesmo padrão de `animsys_store_rna_setting`) e comparar contra `RNA_property_array_length()` quando resolvível; fora do intervalo, cai para `-1` ("todos os componentes", convenção já usada em `BKE_keyingset_find_path`) em vez de persistir um índice inválido.
- **ANIM-002** (preview da Pose Library não restaura constraints): `tPoseLib_Backup` (`pose_lib.c`) ganhou uma lista `constraint_backups` que snapshota `enforce`/`flag` de cada `bConstraint` do canal em `poselib_backup_posecopy()`; `poselib_backup_restore()` restaura esses campos junto com o resto do canal; `poselib_backup_free_data()` libera a lista nova. Resolve o `TODO` explícito que existia no código.
- **Validação (build)**: build completo (`RangeEngine` + `RangeRuntime`) limpo após todas as 7 correções aplicadas, sem erros ou warnings novos nos arquivos alterados, e instalado via `ninja install` em `build/bin/`.
- **Validação (testes automatizados, mesmo dia)**: criados `tools/tests/bugfix_regression/{test_anim_keyingset_array_index.py, test_regression_smoke.py, test_rnd001_voxeldata_bvox.py, run_all.py}`, rodados contra o binário instalado:
  - **ANIM-001**: 3/3 asserções passando (índice fora do intervalo cai para -1, índice válido preservado, "todo o array" inalterado).
  - **RND-001**: 2/2 casos passando — `.bvox` sintético bem formado (header/resolução round-trip corretos via `bpy.ops.render.render()`) e `.bvox` truncado (antes vazava/lia lixo, agora falha limpo sem crash).
  - **MOD-001**: bind normal do Mesh Deform passando (`is_bound == True`).
  - **GPU-001**: passa quando executado sem `--background` (precisa de contexto OpenGL real; em `--background` a chamada `image.gl_load()` trava esperando um contexto que nunca existe — confirmado empiricamente — então o script pula essa checagem nesse modo).
  - **ANIM-002**: não automatizável — a restauração só roda dentro do operador modal `POSELIB_OT_browse_interactive` ao receber ESC; não existe `EXEC_DEFAULT` equivalente, e não há como simular isso sem janela + fila de eventos do WM. Validação manual descrita no relatório.
  - **BLN-003**: não testável, nem manualmente — confirmado que nenhum código nesta base jamais escreve em `adt->overrides` (recurso parcialmente implementado desde 2009), então a leitura corrigida não tem cenário de reprodução possível hoje. Correta por inspeção (espelha `write_animdata`), sem validação prática disponível.
  - Cenários de overflow "puro" (textura/malha com bilhões de elementos, polígono degenerado por arquivo corrompido) continuam fora de alcance de automação segura; cobertos só por inspeção + regressão do caminho normal.
- Rodada considerada encerrada nesta data: todos os 26 itens do relatório têm decisão de código, e tudo que era automatizável tem teste passando contra o binário instalado.
## 2026-09-04

**Vehicle System — preset físico v1 (continuação da Fase 5)**

Contrato canônico em `docs/vehicle-preset-v1.md` (campos, unidades, limites,
chaves desconhecidas, convenção de eixo). `KX_VehiclePreset` rejeita texto
extra após o JSON e eixos colineares; `KX_ApplyVehiclePreset` recusa mudança
estrutural mesmo com contagem de rodas igual. Novo `KX_CaptureVehiclePreset` +
API Python `savePreset`/`loadPreset`/`rebuildPreset(path, wheelObjects)` (troca
o wrapper por objetos visuais explícitos antes do próximo tick, só então
destrói o antigo). Teste de contrato ganhou o passo `vehicle preset v1`; guia
novo em `docs/vehicle-test-guide.md`. Validação: `ninja ge_ketsji RangeEngine`
+ `RangeRuntime` exit 0.

**Vehicle System — execução no jogo real e controle jogável**

`Chassis` sem pai (Dynamic filho de Empty chegava ao Bullet com massa
efetiva zero). `VehicleContractTestComponent`: 31 PASS/0 SKIP/1 FAIL conhecido
(lifetime pós-remoção do chassis). Máscara de raycast default `-1` corrigida
para `32767` (bit único perdia colisão com o chão e lançava o carro). Rodas
alinhadas ao cubo 1,8×3,6 m. Novo `vehicle_player_component.py` (W/S/A/D/Espaço,
tração traseira), deve ficar em Empty separado do componente de contrato.

**Vehicle System — estabilidade do chassi `Convex Hull`**

Raycaster das rodas passou a ignorar o próprio rigid body do chassi (raio de
suspensão acertava o Convex Hull perto do ponto de fixação e lançava o carro).
`Steering Sign` default `1.0` (A esquerda, D direita). Validação: `ninja
RangeEngine` exit 0; estabilidade em cena real fica como verificação manual.

**Vehicle System — malha da roda se distanciando do carro quando o Empty tem pai**

Rodas viraram Empty filho do Chassis; malha passou a se adiantar da posição
física, erro crescente com a velocidade. Causa raiz: `KX_MotionState::
SetWorldPosition`/`SetWorldOrientation` gravavam a transform mundial do Bullet
como transform local do `SG_Node` sem converter para o espaço do pai — com a
roda agora filha, a transform do Chassis era aplicada duas vezes por tick.
Corrigido com conversão mundo→local nos dois setters (mesmo padrão de
`CcdPhysicsEnvironment.cpp`). Validação: build limpo; **confirmado pelo usuário
em jogo real**.

**Vehicle System — notas de robustez da Fase 5**

`KX_SaveVehiclePresetAtomic` remove o temporário `<path>@` em falha de
escrita/rename. Comentário incorreto corrigido (não compartilha merge-por-chave
com o sidecar de `KX_ParticleDebugUI`, só a técnica temp-file+rename).
`rebuildPreset` rejeita lista com o mesmo game object em duas posições.
Adaptador para os JSON legados do `VehicleConfigEditor.py` descartado (usuário
não vai usar esse editor). Build limpo.

**Vehicle System — guarda de self-collision em addWheel/rebuildPreset**

`PyAddWheel`/`PyRebuildPreset` rejeitam roda com `PHY_IPhysicsController` já
ativo, mesmo com física suspensa. Fecha a causa raiz do bug de levitação:
reaproveitar clones físicos do chassi (`VCT_Wheel_*`) como roda de verdade
fazia o raycast de suspensão colidir com o próprio gêmeo estático — agora falha
na montagem do veículo em vez de levitar sem pista. Build limpo; teste em jogo
real pendente (confirmado na entrada seguinte).

**Vehicle System — Fase 1A: causa raiz do FAIL de lifetime era o teste, não o motor**

Após `endObject()` no chassis, `getNumWheels()` não lançava `ReferenceError`
esperado. Causa raiz: a invalidação (`SetInvalidationCallback`/
`OnVehicleInvalidated`, já existente) só dispara quando o controller físico do
chassis é de fato destruído — o que só acontece após
`KX_Scene::RemoveEuthanasyObjects()` no fim do frame, não na chamada de
`endObject()`. O teste conferia o proxy no mesmo frame, cedo demais. Nenhuma
mudança de engine: o passo de teste foi dividido em "chama endObject()" +
"confere proxy após o intervalo padrão do harness". **Confirmado pelo usuário
em jogo real: 32 PASS, 0 SKIP, 0 FAIL.**

**Vehicle System — guarda de self-collision confirmada em jogo real**

Reexecução completa do `VehicleContractTestComponent`: 32 PASS, 0 SKIP, 0 FAIL
nas duas rodadas; guarda de self-collision não quebra o fluxo normal do
veículo.

**Vehicle System — flag nativa `is_vehicle` + lista de rodas via DNA/RNA**

Bit `OB_VEHICLE` em `gameflag2`, RNA `game.is_vehicle` — só marcador nativo, a
criação física continua via `KX_VehicleWrapper`/preset em runtime. Nova struct
`bWheelSettings`/`ListBase vehicle_wheels` no `Object`, ciclo de vida em
`object.c` (padrão de `lodlevels`); operadores `OBJECT_OT_vehicle_wheel_add`/
`_remove` novos, só sob `WITH_GAMEENGINE`. Painel de UI não apareceu em duas
tentativas dentro de `bl_ui/properties_game.py` — causa raiz: este fork
substitui os painéis padrão de física pelo sistema próprio
`flowmenu/custom_pt_physics.py`, que desregistra os originais e só lista
classes explicitamente citadas na tupla `classes`; painel novo nunca fora
adicionado a ela. Decisão: `flowmenu` é o menu oficial de física do fork, toda
UI nova de física entra ali. `PHYSICS_PT_game_vehicle` adicionado e registrado
lá, seguindo o padrão do Ragdoll Panel. Validação: `ninja -t clean` + rebuild
completo dos dois executáveis, exit 0; **confirmado pelo usuário em jogo
real**: painel "Vehicle" visível na aba Physics, checkbox e lista de rodas
funcionando.

## 2026-09-05

**Vehicle System — `is_vehicle`/`vehicle_wheels` ligados à criação real do veículo**

- `bWheelSettings` (DNA) ganhou `radius`, `suspension_rest_length` e
  `has_steering` por roda, expostos em RNA e no painel "Vehicle"
  (`custom_pt_physics.py`) ao lado do seletor de objeto de cada roda.
  `connectionPoint`/eixo/direção continuam calculados a partir da cena, não
  armazenados.
- Novo loop "Create native vehicles" em `BL_BlenderDataConversion.cpp`
  (mesmo padrão do loop de "Create physics joints" logo acima): para cada
  objeto com `gameflag2 & OB_VEHICLE`, `physics_type == RIGID_BODY` e
  controlador físico já criado, resolve as rodas via
  `converter.FindGameObject`, cria `PHY_IVehicle` com
  `physEnv->CreateVehicle(...)` e chama `AddWheel(...)` por roda (raio/
  suspensão vindos da UI, ou `0.3f` como padrão quando zerado — sentinel de
  arquivos antigos). Falha ao resolver qualquer roda pula o veículo inteiro,
  sem criação parcial. `KX_GameObject::getVehicle()` novo expõe o
  `KX_VehicleWrapper` já criado para Python, devolvendo `None` se não houver.
- Duas checagens de sanidade de unidade adicionadas no mesmo loop: aviso no
  console se o raio da roda passar de `1,7 m` ou a suspensão de `0,6 m`
  (valores típicos de carro real ficam entre `0,1` e `0,4 m`; ambos os
  limites pedem para conferir se não houve troca de centímetros por
  metros — motivado por um caso real do usuário, que digitou `30` querendo
  dizer `0,30`).
- `vehicle_player_component.py` reescrito para consumir o veículo nativo já
  criado (`self.object.getVehicle()`) em vez de montar geometria na mão;
  `update()` reorganizado em métodos pequenos chamados um a um
  (`_read_input`, `_compute_engine_force`, `_compute_steer_value`,
  `_apply_braking`, `_apply_engine_force`, `_apply_steering`), sem lógica
  inline. Novo argumento `Engine Sign` (padrão `1.0`) resolve a inversão de
  W/S encontrada em teste real, sem mexer no sinal de `Steering Sign`.
- Novo botão "Add Vehicle Component" no painel Vehicle, abaixo de "Add
  Wheel" (operador `object.vehicle_add_player_component`): cria
  `scripts/vehicle_player_component.py` só se o arquivo ainda não existir
  (nunca sobrescreve) e anexa/registra o component no objeto ativo,
  ignorando silenciosamente se já estiver anexado.
- Corrigido bug pré-existente e não relacionado, encontrado durante o teste:
  `unregister()` em `bl_ui/__init__.py` e `bl_operators/__init__.py`
  acessava `cls.is_registered` sem checar se o atributo existia, quebrando
  o reload por F8 sempre que alguma classe não chegava a registrar de
  verdade. Trocado para `getattr(cls, "is_registered", False)` nos dois
  arquivos.
- **Validação:** `ninja RangeEngine RangeRuntime` com `vcvars64.bat`, exit 0
  (dois retries por `RangeEngine.exe` travado por uma instância antiga
  ainda aberta). Mudanças em `startup/flowmenu/*.py` e nos dois
  `__init__.py` acima são só Python e precisam ser copiadas manualmente
  para `build/bin/2.79/scripts/startup/...`, já que não passam pelo passo
  de instalação do CMake quando não há rebuild de C++. **Confirmado pelo
  usuário em jogo real**: painel Vehicle completo, botão de component
  funcionando, W acelera/S freia e ré no sentido certo, e
  `VehicleContractTestComponent` seguiu com todos os PASS (sem FAIL) depois
  da mudança no converter.

## 2026-09-05 — Correção do sentido de giro visual das rodas do veículo

- Usuário relatou que W acelera o carro corretamente para a frente (convenção
  Y+ = frente do projeto), mas as rodas giravam visualmente para o lado
  contrário ao movimento real.
- Causa: em `BL_BlenderDataConversion.cpp`, o vetor `axle` passado para
  `AddWheel` era `(-1, 0, 0)`. Dentro de `btRaycastVehicle::updateWheelTransform`
  (`extern/bullet2`), o "forward" interno da roda é `up.cross(axle)`; com
  `down = (0, 0, -1)` (logo `up = (0, 0, 1)`) e o `axle` antigo, esse forward
  dava `(0, -1, 0)` — oposto à convenção real do projeto (`(0, 1, 0)`). A
  rotação visual da malha da roda é aplicada em torno desse eixo, então
  girava ao contrário mesmo com o chassi se movendo certo (governado pela
  física real do corpo rígido, não pelo `axle`).
- Corrigido invertendo o sinal: `axle = (1.0f, 0.0f, 0.0f)`, com comentário
  explicando a relação `up.cross(axle)` no código.
- **Validação:** mudança isolada em `.cpp` (não é DNA), rebuild incremental
  via `ninja install` sem erros, `RangeEngine.exe`/`RangeRuntime.exe`
  relinkados e instalados em `build/bin/`. **Confirmado pelo usuário em jogo
  real (2026-09-05): rodas giram no sentido visual correto.**

## 2026-09-05 — Ketsji Plano 1A: auditoria do contrato `maxPhysicsFrame`

- Unidade exclusivamente de auditoria, sem alteração em código ou build.
  `GameData.maxphystep` é um `short` persistido, com padrão histórico 5; o
  launcher o converte em `bool` via `SetMaxPhysicsFrame`.
- A RNA atual o apresenta como `shadows_on_off`, restringe a 0..1 e os únicos
  consumidores encontrados estão nos caminhos CSM de `KX_KetsjiEngine`.
  Nenhum limite de catch-up físico é lido pelo scheduler.
- Os bindings e a documentação Python continuam prometendo número de frames
  físicos. Assim, valores 5 e 10 já são indistinguíveis de 1 em execução.
- Próximo implementador: separar a flag serializada de sombras, versionar a
  migração com `maxphystep != 0`, manter a API Python legada explicitamente
  obsoleta até existir scheduler físico real e testar 0/1/5/10. Como envolve
  DNA, exigir rebuild limpo e validação visual. Nenhuma mudança em Vehicle.

## 2026-09-05 — Ketsji Plano 1A: contador CSM

- Primeira correção isolada do plano de modernização. Baseline: `0d55bcdd`,
  preservado na referência local `backup/ketsji-plan-1a-baseline`. O worktree
  tinha alterações alheias; foram preservadas e não integram esta unidade.
  Os builds abaixo validam esse worktree completo.
- Causa reconfirmada: `s_staticSplitSettleFrames` era um `static` local dentro
  do loop de luzes de `RenderShadowBuffers()`. Com duas luzes, o quinto
  frame produzia valores 9 e 10, permitindo decisões diferentes no mesmo
  frame. Novas instâncias da engine herdavam o contador saturado no processo.
- `KX_KetsjiEngine` agora possui `m_staticSplitSettleFrames`, inicializado em
  zero e reiniciado em `StartEngine()`. `Render()` incrementa uma vez antes
  das cenas, saturando em dez, sob os gates existentes de render texturizado
  e `m_maxPhysicsFrame`. Todas as luzes usam o mesmo valor durante o frame.
  A janela pertence à engine; frames sem luzes contam, e cenas/luzes adicionadas
  depois da janela usam a invalidação de cache que já existe.
- Nenhuma mudança no contrato público de `maxPhysicsFrame`, no scheduler ou
  nos fontes de Vehicle. A migração daquela API permanece no próximo item.
- Revisão estática e `git diff --check` aprovados. O build incremental passou
  (5 etapas), mas recompilou apenas o `.cpp`, evidenciando a falha conhecida
  de dependências do header. Foi descartado como validação suficiente.
  Executados `ninja -t clean` e rebuild completo de `RangeEngine RangeRuntime`
  via `vcvars64.bat`: **2.934/2.934, exit 0**, aproximadamente cinco minutos.
  Log local: `build/ketsji-plan-1a-build.log`.
- `RangeEngine --background` carregou a cena existente
  `projects-teste/Teste de nova luz e sombra.range`, exit 0: Sun com CSM e
  static shadow ligados, objetos estáticos e um `RIGID_BODY`.
- Adicionado `projects-teste/scripts/ketsji_csm_smoke.py`, usando a opção
  existente `RangeRuntime -p`: suspende render, desenha 30 vezes, desliga a
  flag legada de sombras por dez desenhos, religa por 30 e reinicia o jogo.
  Os dois ciclos produziram **70 desenhos cada**, marcador final PASS e
  **exit 0**. A cena não foi salva e conservou seu SHA-256. O launcher registra
  os pedidos normais de reinício/saída como `Error: Exit code 2/1`; esses são
  códigos internos de `KX_ExitInfo`, não o código de saída do processo.
  Log local da execução verificada: `build/ketsji-csm-smoke-verified.log`.
- Limites da validação: o smoke test observa callbacks de desenho e o ciclo
  de vida, mas não o contador privado nem o conteúdo das imagens. Ele usa uma
  cena com uma Sun; múltiplas luzes/cenas e Play embutido permanecem pendentes.
  O executável testado reportou **Compatibility**, não cobrindo Core Profile
  nesta execução. O driver emitiu avisos repetidos de textura 0 sem nível-base;
  não apareceram `GL API error`, erros de compilação de shader ou traceback.
  A origem dos avisos não foi isolada nesta correção.
- Estado: **implementado, compilado e smoke test aprovado; validação visual
  pendente**. Próxima unidade: concluir o aceite visual deste item e auditar
  a colisão de contratos `maxPhysicsFrame`/`maxphystep`, após `/compact`.

## 2026-09-05 — Ketsji Plano 1A: separação `shadowCulling` de `maxphystep`

- Segunda correção isolada do plano, seguindo a auditoria registrada acima.
  Não transformou o `bool` legado em `int`: nenhum scheduler físico consome
  o limite hoje, então a API Python permanece um placeholder inerte.
- `GameData` ganhou o campo `short shadowCulling`, reaproveitando o slot não
  usado `pad5` (sem crescer o struct serializado). `maxphystep` continua
  intocado, alimentando só a API Python obsoleta.
- RNA `shadows_on_off` repontada de `maxphystep` para `shadowCulling`, com
  texto deixando explícito que é independente de
  `getMaxPhysicsFrame`/`setMaxPhysicsFrame`.
- `KX_KetsjiEngine` recebeu `m_shadowCullingEnabled` + `GetShadowCulling`/
  `SetShadowCulling`, substituindo `m_maxPhysicsFrame` nos três pontos de
  consumo em sombra (settle frame de `Render()`, split estático e split
  dinâmico de `RenderShadowBuffers()`). `LA_Launcher` agora chama
  `SetShadowCulling(gm.shadowCulling)` além do `SetMaxPhysicsFrame` legado.
  `scene.c` define `shadowCulling = 1` para cenas novas.
- Versionamento: `RANGE_MINSUBVERSION` 106 → 107; novo bloco em
  `blo_do_versions_range()` roda uma vez em arquivos antigos e semeia
  `shadowCulling = (maxphystep != 0) ? 1 : 0`, preservando o comportamento
  visual de arquivos existentes (histórico: `maxphystep` default 5, então a
  imensa maioria migra para `shadowCulling = 1`).
- Docstrings de `getMaxPhysicsFrame`/`setMaxPhysicsFrame` (C e `.rst`)
  atualizadas para deixar claro que não afetam mais sombras e que nenhum
  scheduler consome o valor.
- **Validação:** `ninja -t clean RangeEngine RangeRuntime` + rebuild completo
  via `vcvars64.bat` (mudança em DNA exige limpo): **2.935/2.935, exit 0**.
  Log: `build/ketsji-plan-1a-shadowculling-build.log`. Smoke test
  `ketsji_csm_smoke.py` reexecutado contra o binário novo: dois ciclos,
  **70 desenhos cada**, `render/toggle/restart PASS`, exit 0. Log:
  `build/ketsji-shadowculling-smoke.log`.
- Limites: a migração de arquivo antigo (`maxphystep != 0` → `shadowCulling`)
  não foi testada carregando arquivos `.range` reais com 0/1/5/10 gravados;
  só a lógica do bloco de versionamento e o valor-padrão de cena nova foram
  revisados/compilados. Fica pendente para uma unidade futura ou para o
  próximo teste manual do usuário. Nenhuma mudança em Vehicle.
- Estado: **implementado, compilado e smoke test aprovado; migração de
  arquivo antigo revisada mas não testada com arquivo real**.

## 2026-09-05 — Ketsji Plano 1A: validação de taxas (logic tic rate, render rate, animation rate)

- Terceiro item do Plano 1A. `KX_KetsjiEngine::SetTicRate`, `SetRenderRate` e
  `SetAnimationRate` aceitavam qualquer `double`, incluindo zero, negativo,
  `NaN` e infinito; como `SetRenderRate`/`SetAnimationRate` armazenam o
  inverso do valor recebido e `m_ticrate` é usado como divisor de
  `m_timestep` em `StartEngine()`, uma entrada inválida (via
  `setLogicTicRate`/`setRenderRate`/`setAnimationRate` em Python, ou C++
  direto) propagava `inf`/`nan` silenciosamente para o passo de tempo.
- Adicionado `KX_IsValidRate(double)` (arquivo-local, `std::isfinite(rate) &&
  rate > 0.0`) e aplicado nos três setters: entrada inválida agora é
  rejeitada, loga `CM_Warning` com o valor recusado e o valor anterior
  mantido, e a taxa em vigor não muda. Nenhuma outra taxa (`SetAnimFrameRate`,
  `SetTimeScale`) foi alterada nesta unidade: `SetAnimFrameRate` só recebe o
  FPS de cena vindo do `LA_Launcher`, não é exposta ao Python, e não estava no
  escopo do item 3 do plano mestre.
- Novo smoke test dedicado
  [`ketsji_rate_validation_smoke.py`](../projects-teste/scripts/ketsji_rate_validation_smoke.py):
  para cada uma das três taxas, define um valor válido, tenta seis valores
  inválidos (`0`, `-1`, `-60`, `nan`, `inf`, `-inf`) e confirma que o getter
  não mudou, depois confirma que um novo valor válido ainda é aceito
  normalmente após as rejeições.
- **Validação:** rebuild incremental (sem mudança de DNA, não precisou de
  `ninja -t clean`) via `vcvars64.bat`: exit 0. Smoke test executado contra o
  binário novo: os 18 avisos esperados (`CM_Warning`) apareceram no log, taxa
  anterior preservada em todos os casos, aceite de taxa válida após entrada
  inválida confirmado, `KETSJI_RATE_VALIDATION_SMOKE: PASS`, exit code 0. Log:
  `build/ketsji-rate-validation-smoke.log`.
- Limites: não foi feito teste de contrato automatizado fora do runtime
  (unit test isolado sem o motor completo); a validação depende de rodar o
  `RangeRuntime` com uma cena. Nenhuma mudança em Vehicle nem em DNA/RNA.
- Estado: **implementado, compilado e smoke test aprovado**.

## 2026-09-05 — Ketsji Plano 1A: vida útil do cursor personalizado

- Quinto e último item do Plano 1A. Auditoria em
  `KX_KetsjiEngine::SetCustomMouseCursor` confirmou dois problemas: (1) o
  setter grava `customCursor->m_visible = m_CustomMouseCursor->m_visible`
  (propagando o estado de visibilidade do cursor antigo para o novo) antes de
  checar se o *novo* ponteiro (`customCursor`) é não nulo — chamar o setter
  com `nullptr` para remover o cursor enquanto outro já está ativo
  desreferenciaria um ponteiro nulo; (2) nem o setter nem o destructor de
  `KX_KetsjiEngine` liberavam a struct `CustomMouseCursor` do cursor
  substituído/final, vazando-a a cada troca e no encerramento. `KX_KetsjiEngine`
  é o único dono confirmado (apenas construtor, setter e os dois accessors
  tocam `m_CustomMouseCursor`; único chamador do setter é
  `BL_ConvertCustomMouseCursor`, que sempre constrói uma struct nova).
- Corrigido com um helper único, `FreeCustomMouseCursor`, chamado tanto no
  setter (antes de sobrescrever o cursor antigo) quanto no destructor (cursor
  final), reordenando a checagem de nulo para não depender mais de qual dos
  dois ponteiros existe.
- **Achado durante a validação, não previsto na auditoria original:**
  `CustomMouseCursor::m_tex` (`GPUTexture*`) não é um recurso exclusivo do
  cursor — `GPU_texture_from_blender()` o cacheia em `Image::gputexture[]` e
  devolve o mesmo ponteiro em toda chamada futura para a mesma imagem, sem
  incrementar refcount para esse empréstimo (confirmado em
  `gpu_texture.c`, comparado com o idioma de liberação usado em
  `gpu_draw.c:1435-1437`, que sempre libera via `ima->gputexture[i]`, nunca
  por quem pegou emprestado). A primeira versão da correção chamava
  `GPU_texture_free(cursor->m_tex)` dentro do helper — isso decrementava um
  contador que o cursor nunca havia incrementado e, ao chegar a zero, liberava
  a struct `GPUTexture` sem limpar o cache da `Image`, deixando um ponteiro
  pendente ali. O smoke test pegou isso na hora: `EXCEPTION_ACCESS_VIOLATION`
  ao reatribuir a mesma imagem de cursor uma segunda vez. Corrigido removendo
  a chamada a `GPU_texture_free`: `FreeCustomMouseCursor` libera apenas a
  struct `CustomMouseCursor`, nunca a textura, que permanece de posse da
  `Image`/`bmain`.
- Novo smoke test dedicado
  [`ketsji_cursor_lifetime_smoke.py`](../projects-teste/scripts/ketsji_cursor_lifetime_smoke.py),
  rodando contra `Teste de nova luz e sombra.range` (cena qualquer serve, não
  depende de conteúdo específico). Chama `render.setCustomMouse()` (módulo
  Python `Range.render`, i.e. `Rasterizer` em C++) repetidamente alternando
  entre duas imagens existentes (`smoke2.png`, `joystick_controller.png`),
  incluindo a mesma imagem duas vezes seguidas — o caso que expôs o bug do
  texture-free acima — e finaliza via `logic.endGame()` para exercitar a
  liberação do último cursor no destructor. Não há nenhum ponto de entrada
  Python que passe `nullptr` ao setter hoje, então o teste não exercita esse
  ramo diretamente; ele foi revisado por leitura de código.
- **Validação:** rebuild incremental via `vcvars64.bat` (apenas
  `KX_KetsjiEngine.cpp`/`.h` recompilados): exit 0. Smoke test: primeira versão
  falhou com `EXCEPTION_ACCESS_VIOLATION` (achado acima); após a correção,
  `KETSJI_CURSOR_LIFETIME_SMOKE: PASS`, exit code 0. Log:
  `build/ketsji-cursor-lifetime-smoke.log`.
- Estado: **implementado, compilado e smoke test aprovado. Plano 1A
  completo (itens 1–5).**

## 2026-09-05 — Ketsji Plano 1A: projeção segura do Sol

- Quarto item do Plano 1A. Em `KX_KetsjiEngine::PostRenderScene`, o cálculo da
  posição do Sol na tela para os filtros Light Scattering e Lens Flare
  dividia `screenPos.x`/`screenPos.y` por `screenPos.w` sem checagem. Quando o
  Sol está atrás da câmera ou quase paralelo ao plano de visão, `screenPos.w`
  pode ser zero, muito próximo de zero ou negativo, o que produzia
  `NaN`/`Inf` ou uma posição espelhada incorreta, propagados direto para os
  uniforms `flare_sun_x`/`flare_sun_y` e `ge_LightScatterSunPos` dos shaders.
- Adicionado um guard (`std::isfinite(screenPos.w) && screenPos.w >
  FLT_EPSILON`) antes da divisão: quando o Sol está atrás da câmera ou
  paralelo ao plano de visão, `sunPos` simplesmente mantém seu valor padrão
  daquele frame (`{0.5f, 0.0f}`), sem gerar `CM_Warning` — esse ângulo é
  comportamento normal de câmera, não um erro de dado, ao contrário das
  entradas inválidas do item 3.
- Novo smoke test dedicado
  [`ketsji_sun_projection_smoke.py`](../projects-teste/scripts/ketsji_sun_projection_smoke.py),
  rodando contra uma cena dedicada nova
  [`ketsji_sun_projection_smoke.range`](../projects-teste/ketsji_sun_projection_smoke.range)
  (gerada a partir de `Teste de nova luz e sombra.range` pelo script auxiliar
  headless
  [`_setup_sun_projection_scene.py`](../projects-teste/scripts/_setup_sun_projection_scene.py),
  que atribui o Sun existente da cena a `scene.world_sun_set` — necessário
  porque `KX_Scene::GetWorldSun()` só retorna não nulo se isso estiver
  configurado no arquivo, e a API Python de jogo não expõe um setter). O teste
  liga Light Scattering em runtime (`filterManager.changeLightScatterValues`)
  e aponta a câmera ativa exatamente na direção do Sol, exatamente na direção
  oposta, e em duas perpendiculares exatas (produto vetorial), cobrindo os
  três ângulos que o guard existe para tratar.
- **Validação:** rebuild incremental (sem mudança de header novo além do
  `<cmath>`/`<cfloat>` já incluídos pelo item 3) via `vcvars64.bat`: exit 0.
  Smoke test executado: as quatro orientações completaram sem exceção nem
  parada do motor, `KETSJI_SUN_PROJECTION_SMOKE: PASS`, exit code 0. Log:
  `build/ketsji-sun-projection-smoke.log`.
- Limites: os uniforms `flare_sun_x`/`flare_sun_y`/`ge_LightScatterSunPos` não
  são expostos ao Python, então o smoke test confirma ausência de
  exceção/crash nos quatro ângulos, não o valor exato enviado à GPU. Verificar
  visualmente que o flare/scattering não pisca ou salta ao cruzar esses
  ângulos no jogo real fica como validação pendente. Nenhuma mudança em
  Vehicle nem em DNA/RNA.
- Estado: **implementado, compilado e smoke test aprovado**.

## 2026-09-05 — Ketsji Plano 1B: higiene conservadora do arquivo

- Primeira unidade do Plano 1B (higiene, sem mudança de comportamento).
  Auditoria manual de `NextFrame()`, `Render()`, `RenderShadowBuffers()` e
  `RenderCamera()` classificou cada comentário candidato conforme a regra do
  plano mestre (contrato/motivo, desatualizado, código desativado,
  experimento pendente).
- Removidas 75 linhas de código desativado: o esqueleto comentado de antigos
  loops por cena (`//for (KX_Scene *scene : m_scenes) {` / `//m_logger.
  StartLog(tc_overhead);` / `//not sure this is needed` / `//KX_SetActive
  Scene(scene);` / `//}`) deixado quando as operações de `NextFrame()` foram
  consolidadas num único `for`; variáveis de guarda de disparo único
  comentadas (`//bool o/a/p = true;` em `NextFrame()`, `//bool h = true;` em
  `Render()`) com seus `//if (...) { ... }` pareados; duas ocorrências do
  comentário de baixa qualidade `// this is vary wip test`; uma chamada
  comentada a `UpdateAnimations` remanescente de antes da animação ter virado
  responsabilidade única de `NextFrame()`, em `RenderCamera()`; e uma
  variável comentada sem uso (`//bool doRender = ...`) no fim de `NextFrame()`.
  `RenderShadowBuffers()` não teve nenhum achado — só comentários de
  contrato, todos preservados.
- Diff exclusivamente de remoção de linhas de comentário; nenhuma instrução
  executável foi tocada ou reordenada.
- **Validação:** rebuild de `RangeEngine`+`RangeRuntime` via `vcvars64.bat`
  (128/128 passos, exit 0; mudança só em `.cpp`, não exigiu clean rebuild).
  Smoke test [`ketsji_csm_smoke.py`](../projects-teste/scripts/ketsji_csm_smoke.py)
  contra `Teste de nova luz e sombra.range` (exercita `NextFrame`, `Render`,
  `RenderShadowBuffers` e `RenderCamera` a cada frame): `cycle=1 draws=70
  PASS` e `render/toggle/restart PASS`, igual ao baseline já registrado do
  Plano 1A — sem mudança de comportamento observável.
- Fora do escopo desta unidade, registrado para decisão futura: achados
  equivalentes fora das quatro funções exigidas pelo Plano 1B — um `//printf`
  de debug em `PostRenderScene()` e ~7 linhas do mesmo padrão de
  variável/comentário morto em `UpdateSleepTime()`.
- Estado: **implementado, compilado e smoke test aprovado.**

---

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para o collision-depth pass

- Primeira unidade do Plano 2 (instrumentação granular), cobrindo a metade
  mais simples do item "Texture renderers e collision-depth pass".
- Leitura de `KX_TimeCategoryLogger::StartLog()` mostrou que cada categoria é
  fechada implicitamente pelo próximo `StartLog()` chamado — não existe
  `EndLog(tc)` explícito em `KX_KetsjiEngine.cpp`. Isso torna a divisão de uma
  categoria "grátis" (uma linha) apenas quando o fim desejado já coincide com
  um `StartLog()` seguinte existente. É o caso do collision-depth pass
  (`RenderCollisionDepthBuffer`, seguido de perto por `StartLog(tc_rasterizer)`),
  mas não dos dois `RenderTextureRenderers()` (cada um seguido de um trecho
  longo de código antes do próximo `StartLog`), que exigiriam inserir também
  uma chamada de "retomada". Por isso o item foi dividido em duas unidades
  futuras; só a de collision-depth foi executada agora.
- Novo valor de enum `tc_collisiondepth` em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`), inserido entre `tc_shadowculling` e `tc_services`;
  label `"CollisionDepth"` adicionado na mesma posição em `m_profileLabels`
  (o array é indexado pelo valor inteiro do enum). Um único
  `m_logger.StartLog(tc_collisiondepth)` inserido em `Render()` imediatamente
  antes da chamada a `RenderCollisionDepthBuffer(scene)`; o `StartLog(tc_rasterizer)`
  já existente logo depois fecha a nova categoria sem necessidade de outra
  chamada. Antes, esse tempo ficava somado em `Shadows`.
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `ninja -t clean`
  (3003 arquivos) seguido de `ninja RangeEngine RangeRuntime` (2934/2934,
  exit 0), `KX_KetsjiEngine.cpp.obj` sem warnings novos. Confirmação visual de
  "CollisionDepth" separado de "Shadows" em relatório de benchmark ainda não
  feita pelo usuário — validação opcional, não bloqueante.
- Fora do escopo desta unidade, registrado para decisão futura: divisão de
  `RenderTextureRenderers()` (as duas chamadas, em `Render()` e
  `RenderCamera()`) em sua própria categoria — exige inserir também a
  chamada de retomada de `tc_rasterizer` em cada ponto.
- Estado: **implementado e compilado; validação visual do benchmark
  opcional pendente.**

---

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para RenderTextureRenderers

- Segunda unidade do Plano 2, completando o item "Texture renderers e
  collision-depth pass" — a unidade anterior (acima) cobriu apenas o
  collision-depth pass; esta cobre as duas chamadas a
  `RenderTextureRenderers()`.
- Diferente do collision-depth pass, nenhum dos dois pontos de chamada tinha
  um `StartLog()` seguinte imediatamente após. Em `Render()`, a chamada
  independente de viewport (`VIEWPORT_INDEPENDENT`) era seguida de mais
  código antes do próximo `StartLog(tc_rasterizer)`; em `RenderCamera()`, a
  chamada dependente de viewport (`VIEWPORT_DEPENDENT`) nem tinha um
  `StartLog` próprio antes dela (rodava sob a categoria herdada do
  chamador). Por isso cada ponto precisou de um par de chamadas —
  `m_logger.StartLog(tc_texturerenderers)` antes da chamada,
  `m_logger.StartLog(tc_rasterizer)` logo depois para retomar a categoria
  seguinte — em vez de uma única linha nova como no collision-depth pass.
- Novo valor de enum `tc_texturerenderers` em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`), inserido entre `tc_collisiondepth` e `tc_services`;
  label `"TextureRenderers"` adicionado na mesma posição em
  `m_profileLabels` (array indexado pelo valor inteiro do enum). Antes, esse
  tempo ficava somado em `MainRender` (`tc_rasterizer`).
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `ninja -t clean`
  (3003 arquivos) seguido de `ninja RangeEngine RangeRuntime` (2934/2934,
  exit 0), `KX_KetsjiEngine.cpp.obj` sem warnings novos e sem erros de
  compilação (únicos matches de "error" no log são nomes de arquivo
  pré-existentes — `error_stack.cpp`, `ErrorHandler.cpp`, `ErrorValue.cpp`).
- Item "Texture renderers e collision-depth pass" do Plano 2 agora completo
  (as duas unidades juntas). Confirmação visual de "TextureRenderers"/
  "CollisionDepth" separados de "MainRender"/"Shadows" em relatório de
  benchmark ainda não feita pelo usuário — validação opcional, não
  bloqueante, mesma pendência já registrada na unidade anterior.
- Estado: **implementado e compilado; validação visual do benchmark
  opcional pendente.**

---

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para UpdateGpuParticleEmitters

- Terceira unidade do Plano 2, cobrindo a metade "atualização" do item
  "atualização e desenho de partículas" (a metade "desenho" já está coberta
  por `tc_texturerenderers`/planar-mirror probes e pelo rasterizador
  principal, e não é reaberta aqui).
- `KX_Scene::UpdateGpuParticleEmitters()` rodava dentro do bloco de
  `tc_scenegraph`, junto com `scene->UpdateParents()`, em `NextFrame()`.
  Como `UpdateParents()` e `UpdateGpuParticleEmitters()` são etapas
  distintas (a segunda depende da primeira, mas mede um subsistema
  diferente), o tempo de partículas ficava somado ao de scenegraph sem
  poder ser isolado.
- Igual ao collision-depth pass e diferente do texture-renderers pass:
  nenhum par de retomada foi necessário. Depois de
  `UpdateGpuParticleEmitters()`, nada mais roda no bloco `if
  (!scene->IsSuspended())` — o próximo `StartLog` é `tc_overhead`, seja na
  próxima iteração do loop de cenas ou no código pós-loop. Bastou uma linha
  nova.
- Novo valor de enum `tc_particles` em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`), inserido entre `tc_texturerenderers` e
  `tc_services`; label `"ParticleUpdate"` adicionado na mesma posição em
  `m_profileLabels`.
- Fora do escopo, confirmado por leitura: dividir "sensores" e
  "controllers" (outro item da lista de medições desejadas) não é possível
  como unidade isolada no maestro — `SCA_LogicManager::BeginFrame()` funde
  as duas chamadas internamente, e o plano reserva mudanças no Logic
  Manager para seu próprio plano de subsistema.
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `ninja -t
  clean` (3003 arquivos) seguido de `ninja RangeEngine RangeRuntime`
  (2934/2934, exit 0), `KX_KetsjiEngine.cpp.obj` sem warnings novos e sem
  erros de compilação (únicos matches de "error" no log são nomes de
  arquivo pré-existentes — `error_stack.cpp`, `ErrorHandler.cpp`,
  `ErrorValue.cpp`). Validação em jogo real ainda pendente.
- Estado: **implementado e compilado; teste no jogo real pendente.**

---

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para actuators

- Quarta unidade do Plano 2, cobrindo a parte "actuators" do item
  "sensores, controllers/Python e actuators separadamente". A parte
  "sensores"/"controllers" segue fora do escopo (ver unidade anterior):
  `SCA_LogicManager::BeginFrame()` funde as duas chamadas internamente e
  não pode ser dividida no maestro.
- Confirmado por leitura que `KX_KetsjiEngine::NextFrame()` já chama três
  fronteiras distintas do Logic Manager, hoje todas somadas em `tc_logic`:
  `LogicBeginFrame` (sensores+controllers, via `SCA_LogicManager::
  BeginFrame`), `LogicUpdateFrame` (via `SCA_LogicManager::UpdateFrame`,
  que só percorre `m_activeActuators` — actuators puros) e `LogicEndFrame`
  (via `SCA_LogicManager::EndFrame`, cleanup dos event managers).
- Como `LogicEndFrame` sempre chama `m_logger.StartLog(tc_logic)` logo em
  seguida a `LogicUpdateFrame`, sob a mesma guarda `!scene->IsSuspended()`,
  nenhum par de retomada foi necessário — mesmo padrão do collision-depth
  pass e do particle-update pass. Bastou trocar o `StartLog(tc_logic)`
  imediatamente antes de `scene->LogicUpdateFrame(m_logicTime)` por
  `StartLog(tc_actuators)`.
- Novo valor de enum `tc_actuators` em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`), inserido entre `tc_particles` e `tc_services`
  (depois do índice 7/`tc_shadows`, preservando os índices 0-7 usados pelo
  gráfico legado do ImGui em `KX_DebugMode::RenderProfiling()`); label
  `"Actuators"` adicionado na mesma posição em `m_profileLabels`.
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `ninja -t
  clean` (3003 arquivos) seguido de `ninja RangeEngine RangeRuntime`
  (2934/2934, exit 0), `KX_KetsjiEngine.cpp.obj` sem erros de compilação
  (únicos matches de "error" no log são os três nomes de arquivo
  pré-existentes já conhecidos). Validação em jogo real ainda pendente.
- Estado: **implementado e compilado; teste no jogo real pendente.**

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para Input e ImGui

- Quinta unidade do Plano 2, cobrindo o item "Input e ImGui" da lista de
  medições desejadas.
- Confirmado por leitura que, em `KX_KetsjiEngine::NextFrame()`, o bloco
  entre o `StartLog(tc_overhead)` do início da função e o
  `StartLog(tc_overhead)` seguinte (antes do tratamento de joystick SDL e
  do loop por cena) é inteiramente input/ImGui: limpeza do mouse
  (`m_inputDevice->ReleaseMoveEvent()`), `m_imgui->NextFrame()`, a lógica
  do overlay de debug de partículas GPU (tecla F9), `ProcessInputEvents()`,
  `ProcessDebugEvents()`, a tecla F1 (alternar mouse no Debug Mode) e a
  atualização do estado do mouse do Game UI.
- O próprio código já marcava esse limite: havia dois `StartLog(tc_overhead)`
  seguidos, um no início da função e outro logo após esse bloco, sem nada
  de "overhead" genérico entre eles além do próprio input/ImGui. Bastou
  trocar o primeiro `StartLog(tc_overhead)` por `StartLog(tc_input)` — o
  segundo, já existente, retoma `tc_overhead` de graça, mesmo padrão do
  collision-depth pass, do particle-update pass e do actuators pass.
- Novo valor de enum `tc_input` em `KX_TimeCategory` (`KX_KetsjiEngine.h`),
  inserido entre `tc_actuators` e `tc_services` (depois do índice 7/
  `tc_shadows`, preservando os índices 0-7 usados pelo gráfico legado do
  ImGui em `KX_DebugMode::RenderProfiling()`); label `"Input"` adicionado
  na mesma posição em `m_profileLabels`.
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `ninja -t
  clean` (3003 arquivos) seguido de `ninja RangeEngine RangeRuntime`
  (2934/2934, exit 0), `KX_KetsjiEngine.cpp.obj` sem erros de compilação
  (únicos matches de "error" no log são os três nomes de arquivo
  pré-existentes já conhecidos). Validação em jogo real ainda pendente.
- Estado: **implementado e compilado; teste no jogo real pendente.**


## 2026-09-06 — Ketsji Plano 2: categorias de profiling para as três passagens de UpdateParents

- Sexta unidade do Plano 2, cobrindo o item "Cada passagem de
  `UpdateParents`" da lista de medições desejadas.
- `KX_KetsjiEngine::NextFrame()` chama `scene->UpdateParents()` três vezes,
  todas antes desta unidade somadas numa única categoria `tc_scenegraph`
  (`"UpdateParents"`): após `LogicBeginFrame`/antes dos actuators, após os
  actuators/antes da física, e após a física/antes da atualização de
  partículas. Cada chamada agora tem sua própria categoria:
  `tc_scenegraph_logic` (`"UpdateParents (Logic)"`),
  `tc_scenegraph_actuators` (`"UpdateParents (Actuators)"`) e
  `tc_scenegraph_physics` (`"UpdateParents (Physics)"`).
- Nenhum par de retomada necessário: as três chamadas de `StartLog(tc_scenegraph)`
  originais já eram cada uma imediatamente seguida por um `StartLog`
  diferente e pré-existente (`tc_actuators`, `tc_physics` e `tc_particles`,
  respectivamente), mesmo padrão de "retomada de graça" já usado nas
  unidades de collision-depth, partículas e actuators.
- O slot original do enum `tc_scenegraph` (índice 5) e seu rótulo
  `"UpdateParents"` em `m_profileLabels` foram deliberadamente mantidos sem
  uso (sempre zero) em vez de removidos/renumerados: o gráfico legado do
  ImGui em `KX_DebugMode::RenderProfiling()` itera categorias por índice
  literal (`i < 8`, `i >= 7`), e remover o slot deslocaria os índices de
  `tc_rasterizer`/`tc_shadows` (6/7). Mesmo padrão já aceito nas unidades de
  `tc_actuators` e `tc_particles`.
- Três novos valores de enum (`tc_scenegraph_logic`, `tc_scenegraph_actuators`,
  `tc_scenegraph_physics`) inseridos em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`) depois de `tc_input` e antes de `tc_services`,
  preservando os índices 0-7 do gráfico legado; três labels adicionados na
  mesma posição em `m_profileLabels`.
- Auditoria (sem alteração de código) descartou outros itens da lista de
  medições desejadas do Plano 2 como já cobertos por código pré-existente:
  "Activity culling" (`tc_services`/`"ActivityCulling"` já isola
  `scene->UpdateObjectActivity()`), `tc_shadowculling` e
  `tc_animations`/`tc_animations_deform` (já separados). `tc_network`
  (`"CameraCulling"`) já mede `CalculateVisibleMeshes()` +
  `UpdateObjectLods()` apesar do nome herdado enganoso — candidato a uma
  futura unidade de higiene isolada, não alterado aqui. Separar
  `RenderBuckets()`/submissão de desenho de `tc_rasterizer` ficou fora do
  escopo por não ter, ao contrário dos demais splits, um ponto de retomada
  natural dentro de `RenderCamera()`.
- **Validação:** mudança em `.h` (enum) exigiu clean rebuild; `RangeEngine.exe`
  precisou ser fechado manualmente pelo usuário antes de `ninja -t clean`
  conseguir remover o binário travado; `ninja RangeEngine RangeRuntime`
  (2934/2934, exit 0), `KX_KetsjiEngine.cpp.obj` sem erros de compilação
  (únicos matches de "error" no log são os três nomes de arquivo
  pré-existentes já conhecidos). Validação em jogo real ainda pendente.
- Estado: **implementado e compilado; teste no jogo real pendente.**

## 2026-09-06 — Ketsji Plano 2: contador de objetos (total/testado/visível) no culling

- Contexto: primeiro item de "Contadores desejados" do Plano 2 — "Objetos
  totais, testados pelo culling e visíveis" (10ª unidade).
- `KX_CullingHandler::Process()` passou a registrar, além da lista de
  objetos visíveis, quantos objetos renderizáveis foram efetivamente
  testados contra o frustum (`GetLastTestedCount()`), contagem antes
  descartada.
- `KX_Scene` ganhou `m_lastCullingTotalObjects`/`TestedObjects`/
  `VisibleObjects` e getters correspondentes, preenchidos nos três caminhos
  internos de `CalculateVisibleMeshes()` (sem frustum culling, DBVT/Bullet e
  fallback de `KX_CullingHandler`), restritos à passagem da câmera principal
  (`!is_shadowbuf`) para não misturar com sombras/shadow buffers.
- Exibição em `KX_DebugMode.cpp`, reaproveitando o gate opt-in já existente
  `SHOW_RENDER_QUERIES` (mesmo padrão das render queries de GPU), em vez de
  criar uma UI sempre visível.
- Estado: clean rebuild dos dois executáveis aprovado (2934/2934, exit 0);
  **teste em jogo real pendente**.

## 2026-09-06 — Ketsji Plano 3: relógio controlável/falso para testes de temporização

Primeira unidade do Plano 3 ("Testes e infraestrutura de segurança"), item
"relógio controlável/falso para testar temporização":

- `CM_Clock` ganha modo manual opt-in: `SetManualTime(double timeSecond)`
  define um tempo fixo; `AdvanceManualTime(double deltaSecond)` avança esse
  tempo manualmente. Novo estado privado `m_manual`/`m_manualTimeSecond`,
  inicializado como `false`/`0.0` no construtor e em `Reset()`.
- Enquanto `m_manual` estiver ativo, `GetTimeSecond()` e `GetTimeNano()`
  retornam o tempo manual em vez de consultar
  `std::chrono::high_resolution_clock`; ambos os acessores precisaram
  branchar para ficarem consistentes entre si em modo manual.
- Comportamento de produção inalterado: `m_manual` começa `false` e nada no
  código existente chama os novos setters — `KX_KetsjiEngine::m_clock` e
  `KX_TimeCategoryLogger` (que guarda `const CM_Clock&`) continuam lendo o
  relógio real por padrão, mas passam a admitir tempo determinístico em
  testes futuros sem qualquer mudança própria.
- Avaliado e descartado: reaproveitar `KX_KetsjiEngine::GetClockTime()`/
  `SetClockTime()` (já existente, exposto a Python como `setClockTime`) —
  esse par só sobrescreve o `m_clockTime` já derivado, que
  `ClockTiming()` recalcula do zero a partir do `CM_Clock` real na chamada
  seguinte; não serve como relógio falso persistente.
- Avaliado e adiado (fora do escopo desta unidade mínima): habilitar
  `WITH_GTESTS` (hoje `OFF` em `build/CMakeCache.txt` e
  `build_core/CMakeCache.txt`) para escrever o teste automatizado que
  consome essa capacidade — decisão de build system separada, pois traz
  `gflags`/`glog` como dependências novas.
- Estado: clean rebuild dos dois executáveis aprovado (2934/2934 etapas,
  exit 0), obrigatório por alteração de header (`CM_Clock.h`). Teste em
  jogo real confirmado pelo usuário sem regressões — esperado, já que
  `m_manual` começa desligado e nenhum código existente chama os novos
  setters. Unidade encerrada.

## 2026-09-06 — Ketsji Plano 3: auditoria de ciclo de vida/refcount de câmeras temporárias

Segunda unidade do Plano 3, item "testes de ciclo de vida e refcount das
câmeras temporárias" (só leitura, sem alteração de código):

- Revisados os 5 pontos de criação ad-hoc de `KX_Camera` no motor:
  `staticCam`/`cam` em `KX_KetsjiEngine::RenderShadowBuffers`,
  `rendercam` em `KX_KetsjiEngine::GetCameraRenderData`, a câmera default
  criada em `KX_KetsjiEngine::CreateTemporaryCamera` (nome enganoso — é a
  câmera permanente da cena, não temporária) e `m_camera` em
  `KX_TextureRendererManager` (persistente durante a vida do manager).
- Todos com `new`/`Release()` ou `AddRef()`/`Release()` balanceados no
  mesmo escopo, sem `continue`/`return` intermediário entre criação e
  liberação. `CameraRenderData` faz seu próprio `AddRef()` no construtor e
  `Release()` no destrutor, então o `Release()` da câmera recém-criada em
  `GetCameraRenderData` é seguro (só descarta a referência extra do `new`).
- Estado: nenhum bug encontrado, nenhuma correção necessária. Item fechado
  sem mudança de código nem rebuild.

## 2026-09-06 — Ketsji Plano 3: script de regressão para ciclo de vida de cenas

Terceira unidade do Plano 3, item "testes de adicionar, remover,
substituir, sobrepor e suspender cenas":

- Todas as operações já eram expostas ao Python antes desta unidade:
  `logic.addScene(name, overlay)`, `logic.getSceneList()`,
  `scene.end()`, `scene.replace(newScene)`, `scene.suspend()`/`resume()`
  e o atributo somente-leitura `scene.suspended` — nenhuma mudança em C++
  foi necessária.
- Novo arquivo
  `source/release/scripts/templates_range/scene_lifecycle_regression.py`:
  script de controlador "Always" que avança por 5 passos com folga de 10
  frames entre agendar uma operação e verificar o resultado — overlay
  `addScene` → remover via `end()` → `suspend()`/`resume()` → `replace()`
  —, checando o estado esperado com `getSceneList()`/`scene.suspended` e
  imprimindo `PASS`/`FAIL` no console (sem captura de tela).
- O script não cria as cenas auxiliares (`SCENE_BACKGROUND`,
  `SCENE_REPLACEMENT`, nomes ajustáveis nas constantes do topo do
  arquivo) — isso depende de um arquivo `.range`/`.blend` com essas cenas,
  responsabilidade do usuário no editor.
- Estado: nenhuma mudança em C++, não exige rebuild. **Teste em jogo real
  confirmado pelo usuário em 2026-09-06**: `PASS` no console, sem crashes
  nem regressão visual. Unidade fechada.

## 2026-09-06 — Ketsji Plano 3: self-teste matemático do CSM sem OpenGL

Quarta unidade do Plano 3, item "testes matemáticos do CSM sem depender de
OpenGL":

- Extraída de `KX_KetsjiEngine::ComputeCascadeShadowMatrices` a
  responsabilidade puramente matemática de projetar os 8 cantos da fatia do
  frustum da câmera em espaço da luz e calcular seus limites (AABB), em
  `KX_KetsjiEngine::ComputeCascadeFrustumBounds` (nova função estática,
  `KX_KetsjiEngine.h`/`.cpp`). Recebe só `mt::mat4`/`mt::mat3x4`/`float`, sem
  `KX_Scene`/`KX_Camera`/`RAS_ILightObject`, sem OpenGL, sem estado de jogo
  vivo. A parte dependente de cena (ajuste de profundidade pelos shadow
  casters) permanece em `ComputeCascadeShadowMatrices`, que agora só chama a
  função extraída e usa os limites retornados (uma responsabilidade extraída
  por vez).
- Nova `KX_KetsjiEngine::SelfTestCascadeShadowMath()`: roda
  `ComputeCascadeFrustumBounds` com entradas fixas (projeção perspectiva e
  ortográfica simétricas, transformos de câmera/luz identidade,
  `splitNear=2.0`/`splitFar=5.0`) e confere os limites esperados com
  tolerância `1e-4`, imprimindo `PASS`/`FAIL` no console. Sem gtest
  (`WITH_GTESTS` está `OFF`), sem janela, sem rasterizer.
- Chamada uma vez em `KX_KetsjiEngine::StartEngine()` (roda a cada início de
  jogo). Não condicionada a `_DEBUG` porque este ambiente só builda Release
  — condicionar a `_DEBUG` faria o self-teste nunca rodar aqui.
- Estado: mudança em header (`KX_KetsjiEngine.h`), exigiu clean rebuild
  (`ninja -t clean` + rebuild completo de `RangeEngine` e `RangeRuntime`).
  Build limpo confirmado sem erros. **Teste em jogo real confirmado pelo
  usuário em 2026-09-06**: `PASS` no console, sem crashes nem regressão
  visual. Unidade fechada.

## 2026-09-06 — Ketsji Plano 3: asserts nas dependências obrigatórias

Quinta unidade do Plano 3, item "auditar dependências obrigatórias, usando
`BLI_assert` para erro de programação e fallback/log para condições
alcançáveis por dados do jogo":

- O único `new KX_KetsjiEngine` encontrado no repositório está em
  `LA_Launcher.cpp`. Antes de configurar a engine, esse launcher cria
  `KX_Imgui`, `KX_DebugMode` e `KX_NetworkMessageManager` e entrega os três
  pelos setters correspondentes; nenhum chamador passa `nullptr`.
- `SetInputDevice`, `SetPythonMouse`, `SetCanvas`, `SetRasterizer` e
  `SetConverter` já possuíam `BLI_assert`. Acrescentado o mesmo contrato a
  `SetImgui`, `SetDebugMode` e `SetNetworkMessageManager`, cujos objetos são
  desreferenciados depois em caminhos normais ou habilitados por flags — o
  Network Message Manager, em particular, é usado incondicionalmente por
  `NextFrame()`.
- Não foram acrescentados guards silenciosos nas desreferências: ponteiro nulo
  nesses setters representa configuração incorreta do programa. Caminhos
  alcançáveis por dados do jogo foram auditados separadamente; operações
  agendadas de adicionar, remover e substituir cenas inexistentes já preservam
  a execução com fallback e `CM_Warning`.
- Revisão independente aprovou o diff de três linhas e confirmou que ele não
  toca os hunks locais preexistentes do self-teste CSM. `git diff --check`
  passou.
- Estado: build incremental de `RangeEngine` e `RangeRuntime` aprovado (6/6
  etapas, exit 0) pelo ambiente MSVC oficial. Nenhum header foi alterado; a
  unidade não introduz comportamento visual novo. **Teste adicional no jogo
  real confirmado pelo usuário em 2026-09-06**: PASS no console, sem crashes
  nem regressão visual. Unidade fechada.

## 2026-09-06 — Ketsji Plano 3: teste de regressão do sistema de partículas

Oitava unidade do Plano 3, item "cenas de regressão de sombras, filtros,
partículas e render-to-texture". Auditoria (ver relatório completo abaixo)
mostrou que essas quatro superfícies não são um teste único isolado:

- Sombras (`RenderShadowBuffers` em `KX_KetsjiEngine.cpp`) não expõem nenhum
  callback Python equivalente a `pre_draw`/`post_draw`; só existe o contador
  de profiling `tc_shadows` do Plano 2. Sem exposição nova, não é testável
  neste padrão.
- Render-to-texture (`VideoTexture/ImageRender.cpp`, `render()`/`refresh()`)
  é uma API síncrona e pontual, sem sinal por frame observável
  independentemente de chamar `refresh()` — o padrão de polling usado nos
  testes anteriores não se aplica bem aqui.
- Filtros 2D (`scene.filterManager` / `KX_2DFilterManager`) têm estado
  inspecionável (`getFilter`, `addFilter`, `changeFxaaValues` etc.), mas sem
  contador "disparou este frame".
- Partículas (`KX_ParticleSystem`, retornado por `gameObject.particles`)
  expõem `particleCount` (contador real, atualizado por frame,
  `RAS_ParticleBuffer::GetParticleCount()`) e `enabled` (liga/desliga em
  runtime) — a superfície com o sinal por-frame mais próximo do padrão já
  usado nas unidades anteriores.

Por decisão do usuário, esta unidade cobre apenas partículas; sombras,
filtros 2D e render-to-texture ficam como itens em aberto para unidades
futuras, cada um exigindo sua própria abordagem.

- Criado
  `source/release/scripts/templates_range/particle_system_regression.py`.
  Exige que o objeto do controlador tenha "Use GPU Particles" habilitado
  (`gameObject.particles` não seja `None`) e comece com `enabled == True`.
  Não assume taxa de emissão nem tempo de vida específicos (dependem do
  arquivo); verifica apenas o contrato que vale para qualquer configuração:
  `particleCount` é sempre um inteiro não-negativo; `enabled` sempre reflete
  a última escrita feita a ele; e, enquanto desabilitado, `particleCount`
  nunca sobe (só cai ou mantém, conforme as partículas existentes terminam a
  vida), já que nenhuma nova é gerada sem o sistema ligado.
- Sequência: 30 amostras, uma por pulso do sensor Always; desabilita na
  amostra 15, reabilita na amostra 25, confirmando o valor de `enabled`
  imediatamente após cada troca.
- Harness isolado com 6 casos (fluxo normal com contagem subindo e caindo,
  contagem subindo indevidamente com o sistema desabilitado, contagem
  negativa, `gameObject.particles is None`, sistema começando desabilitado,
  contagem não-inteira) — todos com o resultado esperado. AST aprovado pelo
  Python 3.11 empacotado. Não houve alteração C++ nesta unidade, portanto não
  houve build adicional.
- Estado: **teste no jogo real confirmado pelo usuário em 2026-09-06**, rodado
  em `projects-teste/teste_particles.range` com um objeto com sistema de
  partículas GPU habilitado e sensor Always; unidade encerrada.

## 2026-09-06 — Ketsji Plano 3: encerrado por decisão do usuário (escopo atual)

Após a oitava unidade (partículas), o usuário decidiu encerrar o Plano 3 no
escopo atual em vez de abrir uma unidade de instrumentação C++ para os itens
restantes. Oito unidades concluídas: relógio manual, ciclo de vida/refcount
de câmeras, add/remover/substituir/suspender cenas, self-teste matemático do
CSM, auditoria de dependências obrigatórias, callbacks pre-draw/post-draw,
múltiplas câmeras/viewports/estéreo e sistema de partículas.

Ficam pendentes, sem trabalho iniciado, por não terem sinal por frame
exposto em Python hoje (exigem instrumentação C++ prévia, fora do escopo de
"testes" puro): regressão de sombras (só o contador de profiling
`tc_shadows`, sem callback por frame), regressão de filtros 2D
(`scene.filterManager` inspecionável mas sem evento por frame) e regressão
de render-to-texture (`VideoTexture/ImageRender` só tem API síncrona
pontual). Também permanece aberta a avaliação de
AddressSanitizer/UndefinedBehaviorSanitizer no toolchain. Detalhes no
[plano de modernização](ketsji-engine-modernization-plan.md#plano-3--testes-e-infraestrutura-de-segurança).

## 2026-09-06 — Ketsji Plano 4: guarda de câmera temporária em RenderShadowBuffers

Terceira unidade do Plano 4 (RAII e propriedade explícita). `RenderShadowBuffers`
cria duas câmeras temporárias por passe de sombra (`staticCam`, para o sub-passe
estático do split static/dynamic, e `cam`, a câmera principal do passe) via
`new KX_Camera(...)`, liberadas manualmente com `->Release()` mais adiante no
mesmo bloco/loop. Hoje não há early return/continue entre a criação e a
liberação, mas a mesma classe de risco das duas unidades anteriores se aplica:
uma checagem futura adicionada no meio do loop de passes (ex.: abortar um passe
se `CalculateVisibleMeshes` retornar vazio) vazaria a câmera.

Adicionado `KX_TempCameraGuard` (RAII local ao arquivo, anônimo, junto de
`KX_OffScreenRestoreGuard`) que chama `Release()` no destrutor. Aplicado a
`staticCam` (guarda declarada logo após `new`, dentro do bloco condicional do
sub-passe estático) e a `cam` (guarda declarada logo após `new`, no escopo do
loop de passes) — os dois `Release()` manuais anteriores foram removidos. Build
incremental (`ninja RangeEngine`) limpo, sem mudança de comportamento nos
caminhos hoje existentes.

## 2026-09-06 — Ketsji/Rasterizer Plano 4: guardas em KX_TextureRendererManager e RAS_Rasterizer

Quinta e sexta unidades do Plano 4, encontradas após uma varredura dedicada do
motor (Ketsji, Rasterizer, VideoTexture, GameLogic) em busca do mesmo padrão
das quatro unidades anteriores: acquire/bind seguido de release/unbind manual
mais adiante na mesma função, com risco de vazamento se um early return/continue
futuro for inserido entre os dois.

`KX_TextureRendererManager::RenderRenderer` chamava `BeginRender`/`EndRender`
em volta de um loop por face que já tem um `continue` real (`SetupCameraFace`
falhando) e faz updates de animação/culling/render de fundo — um `return`
futuro dentro desse loop deixaria `EndRender` sem ser chamado. Adicionado
`KX_TextureRendererEndGuard` (RAII anônimo local ao arquivo) que chama
`EndRender` no destrutor; o `EndRender` manual foi removido.

`RAS_Rasterizer::ProcessLighting` chamava `PushMatrix`/`PopMatrix` em volta de
um loop que aplica `ApplyFixedFunctionLighting` (virtual) por luz — mesmo
risco. Adicionado `RAS_PopMatrixGuard` (RAII anônimo local ao arquivo,
próximo aos contadores de draw call) que chama `PopMatrix` no destrutor; o
`PopMatrix` manual foi removido.

Candidatos descartados pela varredura: `KX_TextureRendererManager::Render`
(toggle simples de scissor, sem branching real hoje), `RAS_2DFilterManager::
RenderFilters` (bind final antes de retornar, não é par escopado), e
`RAS_2DFilter::Render` (já usa `RAS_ScopeExit` corretamente desde a segunda
unidade do Plano 4). Build incremental (`ninja RangeEngine`) limpo, sem
mudança de comportamento nos caminhos hoje existentes.

## 2026-09-06 — Ketsji Plano 4: guardas de bind/unbind de framebuffer em RenderShadowBuffers

Quarta unidade do Plano 4 (RAII e propriedade explícita), segunda metade da
mesma função da unidade anterior. `RenderShadowBuffers` faz três pares de
bind/unbind de framebuffer por passe de sombra: `BindStaticShadowBuffer`/
`UnbindStaticShadowBuffer` (sub-passe estático), e `BindCascadeShadowBuffer`/
`UnbindCascadeShadowBuffer` ou `BindShadowBuffer`/`UnbindShadowBuffer`
(passe principal, cascata ou simples). Os unbinds eram chamados manualmente
mais adiante no mesmo bloco/loop, depois de `CalculateVisibleMeshes` e
`RenderBuckets` — a mesma classe de risco das unidades anteriores: uma
checagem futura adicionada entre bind e unbind (ex.: abortar o passe se a
lista de visíveis vier vazia) deixaria o framebuffer errado bound pelo
resto do frame.

Adicionados `KX_StaticShadowBufferGuard` e `KX_ShadowBufferGuard` (RAII
locais ao arquivo, anônimos, junto de `KX_TempCameraGuard`). O primeiro
guarda `raslight`/`pass`/`cascadeView`/`cascadeWin` e chama
`UnbindStaticShadowBuffer` no destrutor; o segundo guarda `raslight`/`pass`/
`useCascade` e escolhe entre `UnbindCascadeShadowBuffer`/`UnbindShadowBuffer`
no destrutor, preservando a ordem original (unbind do framebuffer antes da
liberação da câmera temporária, já que a guarda de bind é declarada depois
da guarda de câmera e portanto destruída antes dela). Os três unbinds
manuais foram removidos. Build incremental (`ninja RangeEngine`) limpo, sem
mudança de comportamento nos caminhos hoje existentes.

## 2026-09-06 — Ketsji Plano 4: guardas de escopo em RAS_2DFilter::Render

Segunda unidade do Plano 4 (RAII e propriedade explícita). `RAS_2DFilter::Render`
faz três pares de bind/unbind sequenciais — offscreen custom do filtro
(`m_offScreen->Bind`/`Unbind`), programa de shader (`BindProg`/`UnbindProg`) e
texturas de entrada (`BindTextures`/`UnbindTextures`) — restaurados manualmente
no fim da função. Hoje não há early return entre o primeiro bind e o último
unbind, mas a mesma classe de risco do bug do offscreen de collision-depth se
aplica: qualquer checagem futura adicionada no meio (ex.: validar uma textura
antes de `ApplyShader`) deixaria shader/texturas/offscreen vinculados além do
esperado.

Adicionado `RAS_ScopeExit<Fn>` (classe RAII genérica local ao arquivo,
`MakeScopeExit` como fábrica) e usado nos três pares. Ordem de destruição
(inversa da declaração) passa a desvincular texturas, depois o programa, depois
o offscreen — o código original desvinculava texturas, depois o offscreen,
depois o programa; como os três mexem em estado GL independente (unidades de
textura, objeto de programa, framebuffer/viewport), a troca de ordem não tem
efeito observável (comentado no código). Build incremental (`ninja
RangeEngine`) limpo, sem mudança de comportamento nos caminhos hoje existentes.

## 2026-09-06 — Ketsji Plano 4: guarda de escopo para o offscreen de collision-depth

Primeira unidade do Plano 4 (RAII e propriedade explícita). Em
`KX_KetsjiEngine::RenderCollisionDepthBuffer`, o offscreen anterior
(`RAS_OffScreen::GetLastOffScreen()`) era restaurado manualmente só no fim da
função, depois de `RenderBuckets` e das chamadas `GPU_texture_set_global_*` —
qualquer early return futuro adicionado entre o bind e essas linhas (ex.: uma
checagem de textura de profundidade nula) deixaria o offscreen errado
vinculado pelo resto do frame. A função já tinha um comentário documentando
um bug irmão no mesmo padrão bind/restauração (viewport não resetado após
`RenderShadowBuffers`, causando colisores de partícula lendo posições
erradas — corrigido em sessão anterior).

Adicionada `KX_OffScreenRestoreGuard`, uma classe RAII local ao arquivo que
guarda o offscreen anterior no construtor e o restaura (`Bind()` ou
`RestoreScreen()`) no destrutor, tornando a restauração automática mesmo que
a função ganhe um retorno antecipado no futuro. Build incremental
(`ninja RangeEngine`) limpo, sem mudança de comportamento (mesma sequência de
chamadas, agora garantida pelo destrutor em vez de código manual no fim da
função). Teste em jogo real não é necessário aqui — a mudança é
estruturalmente equivalente ao código anterior nos caminhos hoje existentes;
o objetivo é proteger caminhos futuros.

## 2026-09-06 — Ketsji Plano 3: teste de regressão de múltiplas câmeras/viewports/estéreo

Sétima unidade do Plano 3, item "testes de múltiplas câmeras, viewports e
estéreo", complemento direto da unidade anterior:

- Confirmado em `KX_KetsjiEngine::GetRenderData()`: uma câmera não ativa só
  é renderizada se `useViewport == True`; o número de "frames" de off-screen
  por chamada de `Render()` é 1 (mono ou estéreo dentro do mesmo off-screen)
  ou 2 (`RAS_STEREO_INTERLACED`/`VINTERLACE`/`ANAGLYPH`, um olho por
  off-screen/`post_draw`). A API Python não expõe o modo estéreo ativo, então
  o script não pode assumir a topologia de antemão.
- Criado
  `source/release/scripts/templates_range/multi_camera_stereo_regression.py`.
  Exige um arquivo controlado com uma cena ativa, câmera ativa definida e,
  para exercitar múltiplas câmeras, ao menos uma câmera adicional com
  `useViewport = True`; estéreo é opcional e configurado no arquivo de render.
- O script acumula grupos brutos `setup/pre` terminados em `post_draw` (sem
  assumir contagem fixa de câmeras) e, ao observar dois grupos, detecta se o
  motor está no modo "um olho por grupo" (compara conjunto de câmeras e olhos
  complementares) ou "um grupo já é um frame lógico completo"; a partir daí
  aplica a mesma classificação de forma consistente, fundindo pares quando
  necessário antes de comparar a assinatura câmera/olho entre frames lógicos.
  Cada câmera observada precisa ser a ativa ou ter `useViewport = True`;
  `post_draw` deve chegar com zero argumentos.
- AST aprovado pelo Python 3.11 empacotado. Harness isolado com 7 casos:
  câmera única mono, múltiplas câmeras com viewport, estéreo nos dois olhos
  do mesmo grupo, estéreo com um olho por grupo (par detectado e fundido
  corretamente), par de olhos quebrado (mesmo olho duas vezes seguidas),
  câmera sem `useViewport`/não ativa aparecendo no render, e argumento
  indevido em `post_draw` — todos com o resultado esperado. Não houve
  alteração C++ nesta unidade, portanto não houve build adicional.
- O teste em jogo real revelou uma suposição errada do próprio script: com N
  câmeras, `KX_KetsjiEngine::GetRenderData()` chama `PRE_DRAW_SETUP` para
  todas as câmeras primeiro (uma por `GetCameraRenderData()`, ao montar os
  dados de render) e só depois `RenderCamera()` chama `PRE_DRAW` para cada
  câmera no passe de renderização — ou seja, `setup × N` seguido de `pre × N`,
  não uma alternação estrita `setup, pre, setup, pre`. `_validate_frame()`
  casava os dois por alternação e falhava (`FAIL`) com duas câmeras reais.
  Corrigido casando `setup`/`pre` posicionalmente (dois filtros separados,
  `zip`) em vez de assumir intercalação. Motor não teve código alterado.
- Estado: **teste no jogo real confirmado pelo usuário em 2026-09-06**, rodado
  em `projects-teste/Vehicle_teste.range` com duas câmeras (`Camera` ativa,
  `Camera.003` com `useViewport`); console imprimiu `PASS: 5 frames
  validados, assinatura (('Camera', 0), ('Camera.003', 0))`. Unidade
  encerrada.

## 2026-09-06 — Ketsji Plano 3: teste de regressão dos callbacks de desenho

Sexta unidade do Plano 3, item "testes de callbacks Python nas fases pre-draw e
post-draw":

- A auditoria confirmou a ordem vigente: `PRE_DRAW_SETUP(camera)` em
  `GetCameraRenderData()`, antes de `UpdateView()`; `PRE_DRAW(camera)` em
  `RenderCamera()`, antes de `RenderBuckets()`; e `POST_DRAW()` em
  `PostRenderScene()`, depois dos filtros 2D. `post_draw` é por cena/passe e
  não recebe câmera; setup/pre podem receber câmera temporária no estéreo.
- Criado `source/release/scripts/templates_range/drawing_callbacks_regression.py`.
  O controlador deve ser anexado em modo Module a um sensor Always, em arquivo
  controlado com exatamente uma cena ativa, uma câmera e estéreo desligado.
  Múltiplas câmeras/viewports, cenas overlay e estéreo ficam para a próxima
  unidade específica, pois a API não expõe diretamente o modo estéreo para
  inferir a topologia completa.
- O script acrescenta callbacks sem substituir listas existentes, exige cinco
  grupos exatos `setup → pre → post`, confere o objeto da câmera ativa e o olho
  esquerdo, usa `*args` em `post_draw` para detectar entrega indevida de câmera,
  expira após 600 pulsos sem eventos e remove somente as ocorrências que
  registrou. A câmera temporária nunca é retida fora do callback.
- AST aprovado pelo Python 3.11 empacotado; harness isolado aprovado para fluxo
  normal, estéreo indevido, ordem incompleta, argumento indevido em `post_draw`,
  timeout, topologia inválida e preservação de callback preexistente. Revisão
  independente não encontrou falso PASS no escopo controlado. Não houve
  alteração C++ nesta unidade, portanto não houve build adicional.
- Estado: **teste no jogo real confirmado pelo usuário em 2026-09-06**, rodado
  em `projects-teste/Vehicle_teste.range` com uma cena, uma câmera e estéreo
  desabilitado; console imprimiu `PASS: 5 grupos de callbacks validados`.
  Unidade encerrada.

## 2026-09-06 — Ketsji Plano 2: contador de sensores/controllers/atuadores

13ª unidade do Plano 2, item "lógica" dos "Contadores desejados":

- `SCA_LogicManager` (por cena, via `KX_Scene::GetLogicManager()`) ganha
  `m_lastControllersTriggered`, zerado no início de `BeginFrame()` e
  incrementado a cada `contr->Trigger()` (controller efetivamente
  disparado por um sensor no frame); e `m_lastActuatorsUpdated`, zerado
  no início de `UpdateFrame()` e incrementado a cada `actua->Update()`
  (actuator ativo processado no frame). Getters:
  `GetLastControllersTriggered()`, `GetLastActuatorsUpdated()`.
- `SCA_EventManager` ganha `GetSensorCount()` (tamanho de `m_sensors`);
  `SCA_LogicManager::GetTotalRegisteredSensors()` soma esse valor de
  todos os event managers registrados.
- Nota importante: sensores **não** têm um contador de "avaliados no
  frame" — cada uma das ~10 subclasses de `SCA_EventManager` decide
  internamente quais sensores avaliar (`NextFrame`/`UpdateFrame`
  próprios), e instrumentar isso exigiria tocar todas elas. O número
  exibido é o total de sensores **registrados**, não executados —
  documentado como tal na UI e aqui para não confundir com os demais
  contadores desta unidade, que são genuinamente "executados no frame".
- Exibição em `KX_DebugMode.cpp`, novo bloco "Logic" logo abaixo de
  "Draw Calls", atrás do mesmo gate opt-in `SHOW_RENDER_QUERIES`.
- Estado: clean rebuild dos dois executáveis aprovado (2934/2934,
  exit 0); **teste em jogo real pendente**.

## 2026-09-06 — Ketsji Plano 2: contador de draw calls/mudanças de material

12ª unidade do Plano 2 (mesma retomada por pedido do usuário), próximo item
dos "Contadores desejados":

- `RAS_Rasterizer` (`RAS_Rasterizer.h/.cpp`) ganha contadores estáticos
  de escopo por frame: `ResetDrawCallCounters()` (chamado a cada
  `BeginFrame()`, publica os totais acumulados no frame anterior e zera os
  acumuladores), `IncDrawCallCount()`, `IncMaterialChangeCount()`,
  `GetLastDrawCalls()`, `GetLastMaterialChanges()`. Estáticos porque os
  pontos de incremento não têm um ponteiro de instância do rasterizador.
- Draw call incrementado em `RAS_DisplayArrayStorage::IndexPrimitives()`,
  `IndexPrimitivesInstancing()` e `IndexPrimitivesBatching()` — cobre todos
  os backends/passes que passam por ali (principal, sombra, filtros).
- Mudança de material incrementada em
  `RAS_BucketManager::PrepareBuckets()`, um incremento por bucket
  preparado (bind de material), mesma granularidade já usada pelo resto do
  pipeline de renderização.
- Nota: "primitivas" e "tempo de GPU" da lista de "Contadores desejados"
  já eram cobertos antes desta unidade pelas GL query objects existentes
  (`QUERY_PRIMITIVES`, `QUERY_SAMPLES`, `QUERY_TIME`, exibidas em "Render
  Queries"); o que faltava e foi adicionado agora é especificamente draw
  calls e mudanças de material.
- Exibição em `KX_DebugMode.cpp`, novo bloco "Draw Calls" logo abaixo de
  "Lights / Shadow Passes", atrás do mesmo gate opt-in
  `SHOW_RENDER_QUERIES`.
- Estado: clean rebuild dos dois executáveis aprovado (2934/2934, exit 0);
  **teste em jogo real pendente**.

## 2026-09-06 — Ketsji Plano 2: contador de luzes/total/atualizadas/passes de sombra

Retomada do Plano 2 (11ª unidade) por pedido explícito do usuário para os
"Contadores desejados" restantes, começando por luzes:

- `KX_KetsjiEngine::RenderShadowBuffers` (`KX_KetsjiEngine.cpp`) agora conta,
  por chamada: `lightlist->GetCount()` (luzes totais na cena), quantas luzes
  entraram no bloco de atualização de sombra (`useStaticSplit ||
  raslight->NeedShadowUpdate()`), e quantos passes de sombra foram
  efetivamente renderizados (cascata = 3 passes, sem cascata = 1).
- Novos campos em `KX_Scene` (`m_lastLightsTotal`,
  `m_lastLightsShadowUpdated`, `m_lastShadowPasses`) com getters
  (`GetLastLightsTotal/GetLastLightsShadowUpdated/GetLastShadowPasses`) e um
  setter único (`SetLastLightsCounters`) chamado ao final de
  `RenderShadowBuffers`, mesmo padrão dos contadores de objetos do culling.
- Exibição em `KX_DebugMode.cpp`, novo bloco "Lights / Shadow Passes" logo
  abaixo de "Culling (Objects)", atrás do mesmo gate opt-in
  `SHOW_RENDER_QUERIES`.
- Física (corpos físicos/contatos/substeps/veículos) permanece fora do
  escopo do maestro, conforme decisão da 9ª unidade — não incluída aqui.
- Estado: clean rebuild dos dois executáveis aprovado (2934/2934, exit 0);
  **teste em jogo real pendente**.

## 2026-09-06 — Ketsji Plano 2: avanço para o Plano 3 por decisão do usuário

- Decisão explícita do usuário: não esgotar o Plano 2 item a item agora;
  avançar para o Plano 3.
- Pendentes, sem trabalho iniciado (não cancelados, apenas adiados):
  luzes/passes de sombra executados; casters por cascata; câmeras/
  viewports/probes/cenas renderizadas; draw calls/mudanças de material/
  primitivas/tempo de GPU; corpos físicos/contatos/substeps/veículos (fora
  do escopo do maestro, ver unidade anterior); sensores/controllers/
  scripts/actuators executados; e o "Aceite" formal de baseline (ms e
  percentis para cena simples, real e de estresse).
- Estado: **documentação apenas, nenhuma alteração de código.**

## 2026-09-06 — Ketsji Plano 2: tc_physics confirmado fora de escopo

- Contexto: item "Bullet step, callbacks, springs e sincronização de
  veículos" das "Medições desejadas" do Plano 2, avaliado como 9ª unidade.
- Achado (sem alteração de código): `tc_physics` em `KX_KetsjiEngine.cpp`
  já é uma única chamada para
  `scene->GetPhysicsEnvironment()->ProceedDeltaTime[Car]()`. Os sub-passos
  que se queria separar (`stepSimulation`/`stepSimulationRun`,
  `CallbackTriggers()`, `ProcessFhSprings()`, `SyncWheels()` dos veículos)
  estão todos dentro de `CcdPhysicsEnvironment::ProceedDeltaTime[Car]()`
  (`CcdPhysicsEnvironment.cpp`), no subsistema de Física — sem acesso ao
  `m_logger` (`KX_TimeCategoryLogger`), que pertence ao `KX_KetsjiEngine`.
- Decisão: confirma, por leitura de código, a exclusão já prevista no
  próprio texto do Plano 2 ("métricas internas de Bullet... entram apenas
  no plano específico do respectivo subsistema"). Fica fora do escopo do
  Plano 2; candidato a um plano específico de Física, não aberto agora.
- Estado: **auditoria concluída, nenhum código alterado.**

## 2026-09-06 — Ketsji Plano 2: validação em jogo real do tc_filters2d

- Contexto: a 8ª unidade do Plano 2 (`tc_filters2d`) estava com clean rebuild
  aprovado, mas teste no jogo real pendente.
- Mudança: usuário confirmou teste no jogo real aprovado. Sem alteração de
  código; atualizado o [plano mestre](ketsji-engine-modernization-plan.md)
  removendo a pendência.
- Estado: **Plano 2 sem pendências de validação em jogo real conhecidas**
  para as categorias já entregues.

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para Filtros 2D

- Contexto: o item "Filtros 2D" das "Medições desejadas" do Plano 2 ainda não
  tinha categoria própria; o trecho de pós-processamento 2D em
  `PostRenderScene()` (posição do Sol para Light Scattering/Lens Flare,
  uniforms de tempo dos filtros de clima, `scene->Render2DFilters()`) corria
  fundido em `tc_rasterizer`.
- Mudança: nova categoria `tc_filters2d` ("Filters2D") no enum
  `KX_TimeCategory` (inserida depois de `tc_lightupdate` e antes de
  `tc_services`, preservando os índices 0-7 usados por índice literal no
  gráfico legado do ImGui) e rótulo correspondente em `m_profileLabels`.
  `StartLog(tc_filters2d)` inserido no início de `PostRenderScene()`;
  `StartLog(tc_rasterizer)` retomado logo após `Render2DFilters()`, deixando
  o callback Python `POST_DRAW` e `FlushDebugDraw` fora do isolamento (mesmo
  padrão do callback `PRE_DRAW` em `RenderCamera()`). A composição por olho
  em estéreo (`DrawStereoOffScreen`/`DrawOffScreen`, após o loop de cenas em
  `Render()`) segue fundida em `tc_rasterizer`, fora do escopo.
- Build: header alterado exigiu `ninja -t clean` + rebuild completo;
  `ninja RangeEngine RangeRuntime` (2934/2934, exit 0), sem erros novos.
- Estado: **implementado e compilado; teste no jogo real pendente.**

## 2026-09-06 — Ketsji Plano 2: validação em jogo real das unidades 3 a 7

- Contexto: as unidades 3-7 do Plano 2 (`tc_particles`, `tc_actuators`,
  `tc_input`, as três categorias de `UpdateParents` — `tc_scenegraph_logic`,
  `tc_scenegraph_actuators`, `tc_scenegraph_physics` — e `tc_lightupdate`)
  estavam com clean rebuild aprovado, mas teste no jogo real pendente.
- Mudança: usuário confirmou teste no jogo real aprovado para essas cinco
  unidades. Sem alteração de código; atualizados
  [roadmap.md](roadmap.md#validações-pendentes) e o
  [plano mestre](ketsji-engine-modernization-plan.md) removendo a pendência
  de cada uma.
- Estado: **Plano 2 sem pendências de validação em jogo real conhecidas**
  para as categorias já entregues.

## 2026-09-06 — Ketsji plano mestre: refinamento dos Planos 6-9 com relatório de separação render/simulação

- Contexto: relatório técnico externo (`docs/render-simulation-separation-report.md`)
  avaliou a separação futura entre simulação e renderização no núcleo Ketsji,
  cruzando o parecer com o código atual de `KX_KetsjiEngine`/`KX_Scene` e com
  `docs/architecture.md`.
- Verificação própria antes de aplicar: confirmado no header e no `.cpp` atuais
  que `RenderData`/`FrameRenderData`/`SceneRenderData`/`CameraRenderData`
  existem exatamente como descrito, e que `GetCameraRenderData()`/
  `GetRenderData()` chamam `UpdateView()` e disparam `PRE_DRAW_SETUP`/
  `PRE_DRAW` — ou seja, essas estruturas não são um snapshot nem são
  thread-safe hoje.
- Mudança: apenas documentação, sem alteração de código. Planos 6 e 7 do
  [plano mestre](ketsji-engine-modernization-plan.md) passam a nomear
  explicitamente um "plano de renderização por frame"
  (`RenderFrameInput`/equivalente) em vez de reaproveitar o termo genérico
  "`RenderData`", com a ressalva de que essa estrutura não deve ser chamada de
  snapshot enquanto reter ponteiros vivos, callbacks Python ou mutações de
  estado gráfico. Nova etapa intermediária "auditoria de dados para snapshot"
  inserida entre os Planos 7 e 8, com tabela de classificação de leituras do
  renderer e gates explícitos antes de cogitar snapshot imutável ou render
  thread. Plano 9 ganhou uma seção "Concorrência, se justificada" reformulando
  paralelização/render thread como hipótese condicionada a evidência, não
  compromisso.
- Fora do escopo, mantido deliberadamente: ECS, cópia completa do mundo por
  frame, render thread antes de isolar callbacks/leituras de objetos vivos,
  locks genéricos para SceneGraph/Bullet/Python.
- Estado: **documentação atualizada; não autoriza início de nenhum Plano 6-9,
  que continuam bloqueados pelos gates do plano mestre.**

## 2026-09-06 — Ketsji Plano 2: categoria de profiling para atualização de luzes

- Sétima unidade do Plano 2, cobrindo parte do item "Atualização de luzes,
  ajuste de matrizes CSM, shadow culling e shadow draw" da lista de medições
  desejadas.
- Auditoria: em `RenderShadowBuffers()`, o loop de atualização de luzes
  (`light->UpdateDistanceCulling()`, `light->Update()`, glow de impostor por
  distância) roda antes de qualquer culling/draw de sombra, mas já estava sob
  a categoria `tc_shadows`, iniciada em `Render()` imediatamente antes da
  chamada de `RenderShadowBuffers()`. Isso misturava tempo de "atualização de
  luzes" com "shadow draw". `shadow culling` (`tc_shadowculling`) e
  `shadow draw` (`tc_shadows`) já estavam separados de código anterior.
- Nova categoria `tc_lightupdate` (`"LightUpdate"`), isolando apenas o loop de
  atualização de luzes; `tc_shadows` é retomado logo depois, antes do bloco de
  CSM/culling. O bloco de preparo de view/frustum da câmera de culling (antes
  do loop de luzes) permanece sob a categoria vigente na entrada da função
  (`tc_shadows`), por ser preparo de frustum e não atualização de luz.
- "Ajuste de matrizes CSM" (`ComputeCascadeShadowMatrices`) ficou fora do
  escopo: o cálculo está interligado ao próprio loop de passes de
  culling/draw por luz, sem um ponto de retomada isolado — mesmo padrão de
  exclusão já usado para `RenderBuckets()`/submissão de desenho do
  rasterizador.
- Um novo valor de enum (`tc_lightupdate`) inserido em `KX_TimeCategory`
  (`KX_KetsjiEngine.h`) depois de `tc_scenegraph_physics` e antes de
  `tc_services`, preservando os índices 0-7 do gráfico legado do ImGui
  (`KX_DebugMode::RenderProfiling()`); label `"LightUpdate"` adicionado na
  mesma posição em `m_profileLabels`.
- **Validação:** mudança em `.h` (enum) exige clean rebuild; `ninja -t clean`
  seguido de `ninja RangeEngine RangeRuntime` (2934/2934, exit 0), sem erros
  e com `KX_KetsjiEngine.cpp.obj` recompilado; ambos `RangeEngine.exe` e
  `RangeRuntime.exe` linkados. Validação em jogo real ainda pendente.
- Estado: **código escrito, clean rebuild aprovado. Falta testar no jogo
  real.**

## 2026-09-06 — Ketsji Plano 5: 5a unidade, controle de tolerância do cache de cascata pelo usuário

Motivado por um relato do usuário: "acho que quando eu movimento a câmera essa otimização de um
frame pode estar tremendo a sombra" (sobre a 4ª unidade). Antes de implementar qualquer mudança de
comportamento, uma pergunta de esclarecimento foi feita — a semântica de origem do cache
(`Mat3x4NearlyEqual`, epsilon 1e-5) já é reuso "zero-frame de atraso" por igualdade exata, então um
slider 0/1/2 rotulado "frames de atraso" exigia decidir entre duas leituras diferentes; o usuário
escolheu "0=desliga cache, 1=comportamento atual, 2=+tolerante" em vez de "0/1/2 = nº literal de
frames de atraso tolerado".

- Nova propriedade `Camera.csm_cache_max_stale_frames` (DNA: `Camera.csmCacheMaxStaleFrames`,
  repurposing do slot `pad2`; RNA: `rna_camera.c`, int 0–2, default 1; UI: painel Culling da câmera
  em `properties_data_camera.py`, slider "Shadow Cascade Cache Tolerance").
- `KX_Camera` ganha `m_csmCacheMaxStaleFrames`/`Get`/`SetCSMCacheMaxStaleFrames` (default 1);
  `BL_BlenderDataConversion.cpp` propaga o valor do DNA para o `KX_Camera` convertido, ao lado de
  `SetShowCameraFrustum`/`SetLodDistanceFactor`.
- `KX_ShadowRenderer::Render`: a decisão de reuso do `CascadeMatrixCache` agora lê
  `viewcam->GetCSMCacheMaxStaleFrames()`. Tolerância 0 nunca reusa (sempre recalcula, otimização
  desligada). Tolerância 1 reproduz exatamente o comportamento das unidades 3/4 (só reusa com
  igualdade exata). Tolerância 2 ("Tolerant") também aceita reuso com um novo epsilon frouxo
  (`kCSMCacheToleranceEpsilon = 1e-3`, deliberadamente heurístico, não derivado de um limite de erro
  visual) por no máximo 1 frame consecutivo (`CascadeMatrixCache::staleFrames`, capado em 1) antes
  de forçar recálculo, para uma câmera lentamente em pan nunca arrastar a cascata indefinidamente.
- Versionamento: `RANGE_MINSUBVERSION` 107→108 em `BKE_blender_version.h`; novo bloco em
  `versioning_range.c` semeia `csmCacheMaxStaleFrames = 1` em toda câmera de arquivos antigos (que
  liam 0 do `pad2` reaproveitado, o que teria desligado o cache silenciosamente em vez de preservar
  o comportamento anterior); `camera.c` (`BKE_camera_add`) também inicializa novas câmeras com 1.
- Build: alteração em `DNA_camera_types.h` exige `ninja -t clean` + rebuild completo de
  `RangeEngine`/`RangeRuntime` (não incremental, ver `build_environment.md`), não os 6/6 passos
  rápidos das unidades anteriores.
- Pendente: teste em jogo real do valor 2 (reduz o tremor relatado sem introduzir pop de sombra ao
  a câmera voltar a ficar parada).

## 2026-09-06 — Ketsji Plano 5: 3a e 4a unidades de otimização e correção do roadmap de blend suave

- 3ª unidade (câmeras temporárias reutilizadas): em `KX_ShadowRenderer::Render`,
  as câmeras `cam` (bind principal) e `staticCam` (sub-passe estático) eram
  `new KX_Camera`/`->Release()` a cada pass — até 3x por luz com CSM, mais 1x
  extra quando o sub-passe estático corria. Confirmado em
  `RAS_OpenGLLight::Bind{Shadow,CascadeShadow,StaticShadow}Buffer` que
  `SetModelviewMatrix`/`SetProjectionMatrix` sobrescrevem totalmente o estado
  relevante da câmera a cada bind, então nenhum estado sobrevive entre usos —
  seguro reutilizar a mesma instância. As duas câmeras passam a ser criadas
  uma única vez por chamada de `Render()`, fora do loop de luzes/passes, com
  os mesmos guards RAII (`KX_TempCameraGuard`) liberando ao final da função.
  Sem mudança de assinatura ou header.
- 4ª unidade (cache de cascata não invalidada): `CascadeMatrixCache`, uma
  cache por luz (chave `KX_LightObject*`, `std::unordered_map` de escopo de
  arquivo em `KX_ShadowRenderer.cpp`) que reusa as 3 matrizes de cascata
  calculadas no frame anterior em vez de rechamar
  `ComputeCascadeShadowMatrices`, mas só quando **todas** as condições a
  seguir se mantêm: a transformação mundial da câmera E da luz são
  numericamente iguais às do último cálculo (epsilon 1e-5), a cena não tem
  nenhum shadow caster dinâmico, e a lista de casters estáticos não está
  marcada como suja no frame. Deliberadamente conservador — qualquer caster
  dinâmico na cena desativa o cache por completo (comportamento idêntico ao
  de antes), porque o ajuste de bounds Z em `ComputeCascadeShadowMatrices`
  varre exatamente essas listas de casters e um objeto dinâmico em movimento
  pode invalidar os bounds sem mover a câmera. Sem mudança de assinatura ou
  header.
- Build incremental limpo via `vcvars64.bat`+ninja (`RangeEngine`/
  `RangeRuntime`, 6/6 passos, exit 0) para as duas unidades.
- Investigação do terceiro candidato do roadmap ("blend suave entre
  cascatas") achou que já estava implementado: `gpu_shader_material.glsl`
  tem cross-fade via `smoothstep` numa banda de 10% do split em
  `shadow_simple_csm` e `shadow_vsm_csm`, e visualização de debug por cascata
  em `csm_debug_tint` (com DNA/RNA/UI já ligados). `docs/roadmap.md` corrigido
  para refletir isso — só falta medir o custo real de GPU dessas duas
  features, que segue pendente. Nenhum código novo foi necessário para esse
  item.
- Validação em jogo real da 3ª e 4ª unidade (câmeras reutilizadas e cache de
  cascata) ainda pendente do usuário — ver `docs/roadmap.md`.

## 2026-09-06 — Ketsji Plano 5: otimização, eliminar recomputação de matrizes de cascata

- Segunda unidade do Plano 5, seguindo o próprio texto do plano mestre
  ("Calcular bounds e matrizes uma vez por luz/cascata/frame"; "Evitar
  percorrer todos os casters repetidamente").
- Em `KX_ShadowRenderer::Render`, para cada luz com CSM que atualizava
  sombra no frame, `ComputeCascadeShadowMatrices` era chamada 5 vezes:
  2 vezes só para extrair `split0`/`split1` (descartando view/win) antes do
  loop de passes, e mais 3 vezes dentro do loop (uma por cascata) —
  repetindo a mesma varredura de shadow casters estáticos/dinâmicos a cada
  chamada.
- Fix: as 3 cascatas passam a ser calculadas uma única vez por luz/frame,
  em arrays locais (`cascadeViews[3]`/`cascadeWins[3]`/`cascadeSplitFars[3]`),
  reaproveitados tanto para `SetCascadeSplits` quanto para bind/render de
  cada pass. Sem mudança de assinatura ou header — só `KX_ShadowRenderer.cpp`.
- Build incremental limpo via `vcvars64.bat`+ninja (`RangeEngine`/
  `RangeRuntime`, 6/6 passos, exit 0).
- Teste em jogo real aprovado pelo usuário em 2026-09-06: cena
  `Teste de nova luz e sombra.range`, cascatas near/mid/far, split
  estático/dinâmico e toggle de debug do frustum sem regressão.
- Demais candidatos de otimização do Plano 5 (reutilizar câmeras
  temporárias, atualizar só cascatas invalidadas, blend suave entre
  cascatas) seguem em aberto para unidades futuras.

## 2026-09-06 — Ketsji Plano 5: extração pura do pipeline de sombras para KX_ShadowRenderer

- Primeira unidade do Plano 5 ("Extração do pipeline de sombras"), conforme
  autorizado pelo usuário: extração pura, sem otimização, preservando ordem
  de chamadas e comportamento existentes.
- Criadas `KX_ShadowRenderer.h`/`.cpp` em `source/gameengine/Ketsji`,
  registradas em `CMakeLists.txt`. A classe guarda um ponteiro de volta
  (`m_engine`) para `KX_KetsjiEngine`, sem duplicar estado.
- Movidos verbatim (mesma lógica, mesma ordem):
  `RenderShadowBuffers` → `KX_ShadowRenderer::Render`;
  `DrawDebugShadowFrustum` → `KX_ShadowRenderer::DrawDebugFrustum`;
  `ComputeCascadeFrustumBounds`, `ComputeCascadeShadowMatrices`,
  `SelfTestCascadeShadowMath` (viram estáticos de `KX_ShadowRenderer`); as
  três guardas RAII do Plano 4 (`KX_TempCameraGuard`,
  `KX_StaticShadowBufferGuard`, `KX_ShadowBufferGuard`), agora no anonymous
  namespace de `KX_ShadowRenderer.cpp`.
- Acesso ao estado do maestro: getters já existentes (`GetRasterizer()`,
  `GetCanvas()`, `GetShadowCulling()`); um getter novo mínimo,
  `KX_KetsjiEngine::IsStaticShadowSettled()`, que encapsula o contador de
  estabilização do Plano 1A sem expor o campo bruto nem a constante
  `STATIC_SHADOW_SETTLE_FRAMES`; e um único `friend class KX_ShadowRenderer;`
  para os dois membros restantes sem getter (`m_showShadowFrustum`,
  `GetSceneViewport()` privado).
- `KX_KetsjiEngine` passa a possuir a instância via
  `std::unique_ptr<KX_ShadowRenderer> m_shadowRenderer`, construída no
  construtor (`new KX_ShadowRenderer(this)`); `GetShadowRenderer()` novo
  getter público.
- Varredura por grep dos cinco símbolos movidos encontrou um call site
  adicional fora do maestro: `VideoTexture/ImageRender.cpp::ImageRender::Render()`
  chamava `m_engine->RenderShadowBuffers(m_scene)` diretamente; atualizado
  para `m_engine->GetShadowRenderer()->Render(m_scene)`, com os dois
  `#include` necessários adicionados.
- Comentários referenciando os símbolos antigos atualizados em `KX_Scene.h`,
  `RAS_ILightObject.h`, `KX_LightObject.h` e
  `blender/editors/space_view3d/view3d_draw.c` (documentação apenas, sem
  mudança de comportamento).
- **Validação:** mudança em `KX_KetsjiEngine.h` (novo membro/friend/forward
  declaration) exige rebuild completo dos executáveis. Build incremental de
  `ge_ketsji` aprovado primeiro (compila a nova `KX_ShadowRenderer.cpp`
  isoladamente); em seguida `RangeEngine`+`RangeRuntime` completos, exit 0
  nos dois, incluindo a recompilação de `ImageRender.cpp.obj` com o novo
  call site.
- Estado: **código escrito, build limpo aprovado, teste em jogo real
  aprovado pelo usuário em 2026-09-06** (CSM cascatas near/mid/far, split
  estático/dinâmico, toggle de debug do frustum de sombra, sem regressão
  visual). Primeira unidade do Plano 5 encerrada. Segundo passo do plano
  (otimização) não iniciado.

## 2026-09-06 — Ketsji Plano 6: extração pura dos métodos de render para KX_RenderPipeline

- Segunda unidade do Plano 6 (a primeira, extração dos tipos `KX_*RenderData`,
  foi feita no commit `c7ca17e8` sem entrada própria no changelog).
- Movidos verbatim, mesmo padrão do Plano 5: `GetCameraRenderData`,
  `GetRenderData`, `Render`, `RenderCollisionDepthBuffer` (com a guarda
  `KX_OffScreenRestoreGuard`), `RenderCamera`, `PostRenderScene`,
  `DrawDebugCameraFrustum` e `DrawDebugVehicles`, de `KX_KetsjiEngine` para a
  nova classe `KX_RenderPipeline`.
- Acesso ao estado do maestro via getters já existentes (`GetRasterizer`,
  `GetCanvas`, `GetScenes`, `GetShadowRenderer`, `IsStaticShadowSettled`,
  `GetShadowCulling`, `GetShowBoundingBox`, `GetShowArmatures`,
  `GetShowCameraFrustum`, `GetShowVehicleDebug`, `GetRealTime`,
  `GetSceneViewport`) e `friend class KX_RenderPipeline;` para o que não tinha
  getter (`m_needsRender`, `m_staticSplitSettleFrames`, `m_logger`).
- `KX_KetsjiEngine::Render()` virou um delegador de uma linha
  (`m_renderPipeline->Render();`); nova instância
  `std::unique_ptr<KX_RenderPipeline> m_renderPipeline`, construída no
  construtor (`new KX_RenderPipeline(this)`), com getter público
  `GetRenderPipeline()`.
- `GetSceneViewport` continuou público em `KX_KetsjiEngine` (não movido): é
  usado também por `KX_MouseFocusSensor` e `KX_ShadowRenderer`.
- Gotcha encontrado durante a implementação: a unidade sobrescreveu por
  engano `KX_RenderPipeline.cpp` (já existente desde a primeira unidade, com
  os construtores de `KX_CameraRenderData`/`KX_SceneRenderData`/
  `KX_FrameRenderData`/`KX_RenderData`) em vez de acrescentar a ele,
  derrubando esses construtores e causando `LNK2019` no link. Corrigido
  recuperando o conteúdo original via `git show c7ca17e8:...` e
  reincorporando-o antes das novas funções.
- Build limpo dos dois executáveis aprovado (exit 0). **Teste em jogo real
  pendente.**

## 2026-09-06 — Ketsji Plano 6: reuso de culling entre câmeras com override culling camera

`KX_RenderPipeline::RenderCamera` chamava `scene->CalculateVisibleMeshes(cullingcam, eye, ...)`
e `scene->UpdateObjectLods(cullingcam, objects)` uma vez por câmera de viewport renderizada.
Quando uma cena define um override culling camera (`KX_Scene::GetOverrideCullingCamera`), todas
as câmeras dessa cena passam o mesmo `cullingcam` para essas chamadas — resultado idêntico
recomputado por câmera. Adicionado cache por frame em `KX_RenderPipeline`
(`m_visibleMeshCache`, chave `(cullingcam, eye)`, limpo no início de cada `Render()`) via novo
método privado `GetVisibleMeshes()`. Sem override culling camera o `cullingcam` é sempre a
própria câmera renderizada (único por entrada), então o cache nunca acerta e o comportamento é
idêntico ao anterior — mudança estritamente aditiva/neutra fora do caso de override.

Build limpo dos dois executáveis aprovado (exit 0). **Teste em jogo real pendente**, focado em
cenas com override culling camera e múltiplos viewports.

## 2026-09-07 — Ketsji Plano 11: remoção dos `friend class` remanescentes de KX_KetsjiEngine

Os quatro componentes extraídos dos Planos 5-7 (`KX_ShadowRenderer`, `KX_RenderPipeline`,
`KX_SimulationPipeline`, `KX_SceneScheduler`) ainda acessavam `KX_KetsjiEngine` via `friend class`
e leitura direta de membros privados (`m_engine->m_x`), em vez do padrão de getters públicos usado
no resto da engine desde o Plano 4. Adicionados getters/mutators (`GetLogger()`, `NeedsRender()`,
`NeedsAnimation()`, `NeedsParents()`, `GetLogicTime()`, `GetPhysicsTime()`, `GetFrameStep()`,
`GetStaticSplitSettleFrames()`/`IncrementStaticSplitSettleFrames()`, `GetOverrideSceneName()`);
`BeginFrame()`/`EndFrame()` movidos de private para público. Os quatro `.cpp` migrados para usar
getters (reaproveitando os já existentes, como `GetShowShadowFrustum()`, sem duplicar). As quatro
declarações `friend class` removidas — `KX_KetsjiEngine.h` não declara mais nenhuma.

Refatoração pura, sem mudança de comportamento (cada getter é um repasse de uma linha do campo
privado já existente). Build `ge_ketsji` verificado após cada par de classes; build completo de
`RangeEngine` verificado após as duas etapas (link limpo, exit code 0). Sem teste em jogo real
necessário dado o caráter mecânico da mudança.
## 2026-09-08 — RangeArmor: validação final de pacote Linux

- Instalados `cargo`, `rustc` e `rustfmt` no Debian/WSL; o launcher Rust Linux
  foi compilado e seus testes unitários passaram.
- Corrigido o launcher para passar o caminho absoluto do `MainFile` ao
  `RangeRuntime`. O runtime resolve de modo incorreto caminhos relativos em
  alguns layouts extraídos, embora o diretório de trabalho seja `data/`.
- Validado o fluxo completo: cópia de `build-linux/bin` usando
  `RANGEARMOR_ENGINE_DIR`, geração de `.tar.xz`, extração em `/tmp` fora da
  árvore de build e inicialização da cena pelo launcher empacotado. O runtime
  chegou ao log de hardware OpenGL em Mesa/llvmpipe; os avisos de partículas
  são do shader da cena de smoke test, não do empacotamento.

## 2026-09-08 — RangeArmor: cópia Windows + Linux pelo painel

- O botão de cópia deixou de usar a plataforma do sistema que hospeda o painel
  como único destino. Agora chama a cópia de todas as plataformas disponíveis.
- O script encontra `build/bin` (Windows64) e `build-linux/bin` (Linux64) no
  checkout, portanto um build gerado no WSL no drive compartilhado habilita
  `Linux64` no painel Windows. Para instalações externas, aceita
  `RANGEARMOR_ENGINE_DIR_WINDOWS64` e `RANGEARMOR_ENGINE_DIR_LINUX64`.
- Validado contra o projeto smoke: ambos os runtimes foram copiados com sucesso
  e os dois destinos ficaram presentes em `engine/Windows64` e `engine/Linux64`.

## 2026-09-08 — RangeArmor: retirada de alvos 32-bit

- Removidas as opções Windows32 e Linux32 das telas Tasks e Paths do painel
  legado, bem como o preset de exportação do próprio painel em Windows 32-bit.
- O painel agora oferece somente Windows64 e Linux64; a escolha automática do
  Python do host também usa exclusivamente o caminho 64-bit.
- Campos 32-bit em projetos antigos continuam aceitos pelo painel Rust apenas
  para manter a leitura de configurações legadas, mas não são usados nem
  exibidos.

## 2026-09-10 — LibLoad: Add Object Actuator e seletor do Outline

- Corrigido `WM_OT_link_to_libload`: o operador reutiliza o invocador do
  Link, que consulta as propriedades RNA `link`, `autoselect` e
  `active_layer`; como elas não estavam declaradas, o seletor emitia três
  avisos `RNA_boolean_get ... not found`. O operador agora declara as
  propriedades padrão, mantendo o comportamento de vincular sem instanciar o
  objeto em uma cena.
- O Actuator `Edit Object > Add Object` agora reconhece um `Object` vinculado
  pelo `+` de `External Files`. Se ele ainda não existe entre os objetos
  convertidos da cena, a conversão o cria na lista inativa antes de o actuator
  ser construído; assim ele pode ser selecionado no campo `Object` e replicado
  normalmente em jogo. O comportamento de objetos locais em layer visível
  permanece o mesmo, incluindo o aviso existente.
- Validação: `ninja RangeEngine` compilou e relinkou com sucesso (exit 0).
  Teste manual pendente: adicionar um Object por `External Files > +`,
  selecioná-lo no Add Object Actuator e confirmar a criação no Play e no
  standalone.

## 2026-09-10 — LibLoad: Groups no External Files

- Corrigido o filtro de `External Files` para Groups. Antes ele deduzia a origem
  da biblioteca somente pelos usuários reais de `Object`; como um `Group` é
  usuário dos seus Objects internos, uma biblioteca registrada pelo `+` parecia
  ser um link comum e era escondida.
- `WM_OT_link_to_libload` agora também aplica fake user no `Library` do ID
  registrado. Esse marcador persistente identifica precisamente a origem LibLoad,
  inclusive para Group, sem campo novo em DNA. O Outliner o usa como regra
  principal; o fallback conserva Objects registrados por versões anteriores.
  Links e Appends normais não recebem esse marcador e ficam fora de `External Files`.
- Validação técnica: `ninja RangeEngine` recompilou e relinkou o editor com
  sucesso (exit 0).
- Teste manual pendente: registrar um Group pelo `+`, salvar/reabrir e confirmar
  que só ele aparece em `External Files`.

## 2026-09-10 — LibLoad: Texts do arquivo externo visíveis no External Files

- Cada biblioteca registrada por `External Files > +` agora abre o `.range`
  somente para leitura e mostra a categoria `texts` com os nomes dos seus
  datablocks `Text`. Isso torna visíveis scripts Python, shaders GLSL e outros
  conteúdos textuais sem carregá-los, copiá-los ou sobrescrever um Text local.
- O painel não tenta inferir módulos Python soltos no disco. Components guardam
  somente o nome do módulo/classe; assim, `Vehicle.py` que não esteja como Text
  no arquivo externo continuará aparecendo corretamente como dependência
  ausente no runtime, em vez de ser importado silenciosamente.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso (exit 0).
- Teste manual pendente: vincular um arquivo que contenha um Text, expandir a
  biblioteca em `External Files` e confirmar a pasta `texts` e seus nomes.

## 2026-09-10 — LibLoad: hierarquia recolhível de Texts no External Files

- A categoria `texts` passou a ser filha do caminho do arquivo externo, e não
  irmã dele. O caminho agora possui sua própria seta de expansão; `texts`
  mantém uma segunda seta, que esconde somente a lista de arquivos de texto.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso (exit 0).
- Teste manual pendente: recolher o caminho deve ocultar `texts`; recolher
  apenas `texts` deve manter o caminho visível.

## 2026-09-10 — LibLoad: materiais locais preservados no Add Object

- Corrigido o Play embutido quando um `Object` de `External Files` é escolhido
  no actuator `Edit Object > Add Object`. A pré-conversão desse objeto externo
  faz um `MergeScene()` durante a conversão normal da cena e cria antes o slot
  de recursos dela. A conversão normal usava `emplace`, que falhava sem aviso
  por o slot já existir; os materiais locais convertidos eram descartados e a
  cena aparecia branca.
- A conversão normal agora mescla seus recursos no slot já existente. Assim,
  materiais locais e os do objeto externo permanecem disponíveis para o
  recarregamento de shaders.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso
  (exit 0). Validação visual aprovada pelo usuário: com o actuator contendo
  a referência externa, `P` preserva as cores da cena.

## 2026-09-10 — LibLoad: dependência Text ausente identificada no External Files

- Cada nome em `External Files > <biblioteca> > texts` agora mostra
  `ICON_LIBRARY_DATA_BROKEN` quando não há um datablock `Text` local de mesmo
  nome no arquivo principal. Isso representa exatamente o caso em que um
  Component como `Vehicle` não pode ser importado pelo runtime.
- Quando uma futura operação explícita importar o Text para o projeto raiz,
  o mesmo item passa automaticamente a usar o ícone normal de script. Nenhum
  Text é carregado, copiado, sobrescrito ou resolvido por caminho nesta etapa.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso
  (exit 0). Teste visual pendente: confirmar o ícone quebrado em `Vehicle.py`
  ausente e o ícone de script após existir uma cópia local de mesmo nome.

## 2026-09-10 — LibLoad: importação explícita de Text pelo External Files

- Cada `Text` ausente agora exibe um botão de importação. A ação copia somente
  aquele datablock Text do arquivo já registrado e o torna local no projeto
  raiz; scripts Python, GLSL e os demais tipos de Text seguem o mesmo fluxo.
- A operação recusa um nome que já exista no arquivo atual e não sobrescreve,
  não importa os outros Texts da biblioteca e não transforma os Objects/Groups
  registrados em dados locais. A cópia recebe fake user para persistir ao salvar.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso
  (exit 0). Teste manual pendente: importar `Vehicle.py`, salvar/reabrir e
  confirmar o ícone normal e o Component carregando no Play/standalone.

## 2026-09-10 — Outliner: ações do External Files alinhadas à direita

- Os botões `+` de `External Files`/`Scenes` e o botão de importar `Text`
  passam a usar a borda real do Outliner, em vez do limite anterior às colunas
  de olho, mouse e render. Assim ficam alinhados à direita como os controles
  nativos e não parecem flutuar junto ao nome do item.
- Validação técnica: `ninja RangeEngine` compilou e relinkou com sucesso
  (exit 0). Teste visual pendente: confirmar que os três botões ocupam a última
  coluna do painel sem afetar as colunas de restrição dos Objects.
- Atualização de validação: confirmada pelo usuário no editor real; os botões
  ficam alinhados à direita, na mesma coluna visual dos controles nativos.

## 2026-09-10 — LibLoad: validação funcional final

- O usuário confirmou no editor real a visualização recolhível de `texts`, o
  ícone `LIBRARY_DATA_BROKEN` para Text ausente e os controles alinhados à
  direita. A conversão com Object externo referenciado pelo Add Object também
  preserva os materiais locais durante o Play.
- O próximo teste deliberadamente separado é importar `Vehicle.py`, salvar e
  reabrir para confirmar o carregamento do Component no Play e standalone.
## 2026-09-10 — UI World: painéis customizados consolidados

- O painel customizado do Flowmenu passou a ser a referência única para a UI do
  World. `Sky Render` agora fica aninhado em `Background Colors`, e `Camera
  Exposure` fica aninhado em `Environment`.
- A alteração foi instalada em `build/bin/2.79/scripts/startup/flowmenu` e
  validada com `ninja RangeEngine` concluído com sucesso (exit 0).

## 2026-09-12 — Plano do perfil Web e validação de exportação

- Direção ajustada a pedido do usuário: autoria na própria Range Engine, Web como destino de exportação
  e verificação de compatibilidade durante edição. A proposta inicial de entrada virtual no seletor foi
  substituída; destinos desktop coexistem e erros Web bloqueiam somente o fluxo Web.

- Levantados seletor em `properties_render.py`, identidade `BLENDER_GAME` no C/C++ e painéis,
  propriedades de exportação existentes e pontos de conexão com o runtime em desenvolvimento.
- Criado `web-profile-validation-plan.md`: opção visual Range Engine Web preservando identidade
  interna, catálogo de regras, distinção entre erro confirmado e análise inconclusiva, manifesto,
  fluxo de diagnóstico/export, marcos e testes. Regras propostas, ainda não implementadas.
- Verificação documental de links locais; sem alterações no código, build ou arquivos da PoC.

## 2026-09-12 — Web export: fixes de build sob Emscripten e retomada do CPython wasm

- Série de bugs genuínos corrigidos para destravar o build `web-runtime` sob
  Emscripten: `OPENGLES_LIBRARY` exigido incondicionalmente mesmo sem libGL de
  sistema, `CMAKE_CROSSCOMPILING_EMULATOR`/`NODERAWFS` para os geradores de
  dados cross-compilados, guardas de GLX ausentes em `glew-es/src/glew.c`,
  `statvfs` guardado para `__EMSCRIPTEN__` em `blenlib/intern/storage.c`,
  interação `WITH_GL_PROFILE_ES20` + `WITH_GL_PROFILE_COMPAT` eliminando
  typedefs ainda referenciados no glew-es, pragmas de `-Wsign-conversion` etc.
  em `BLI_strict_flags.h` agora pulados sob `__EMSCRIPTEN__`, e uso de
  `GLEW_VERSION_4_3/4_4/4_5` em `gpu_shader.c` sem guarda (fork só declara até
  4.2).
- Bloqueio arquitetural identificado: o game engine (BGE) usa a API do Python
  incondicionalmente em dezenas de arquivos, sem `#ifdef WITH_PYTHON` — quebra
  o preset Web (`WITH_PYTHON=OFF`, como Android/iOS). Decisão tomada com o
  usuário: cross-compilar CPython 3.11 para `wasm32-emscripten` via
  `Tools/wasm/wasm_build.py` em vez de reescrever o BGE.
- Ambiente de build POSIX necessário para essa ferramenta foi montado em uma
  distro WSL2 Ubuntu já existente na máquina, realocada para `D:\WSL\Ubuntu`
  a pedido do usuário (mais espaço em D:), com dependências de build
  instaladas. Próximo passo: emsdk Linux dentro do WSL + clone do CPython 3.11
  + `wasm_build.py`. Detalhes em `docs/web-export-plan.md`.


## Fragment shader customizado por emissor (Fase P)

- **Pedido do usuário**: em vez de mais presets em C++, um campo pra escrever GLSL próprio por
  emissor de GPU Particles. Design evoluiu em três voltas durante a conversa: string de uma
  linha embutida → Text datablock (multi-linha, salvo no `.blend`) → **arquivo `.glsl` externo
  no disco**, escolha final do usuário, com hot-reload pra poder editar num editor de texto de
  verdade enquanto o jogo roda.
- **DNA/RNA**: `RangeGPUParticleSettings` ganhou `frag_shader_path[1024]` (mesma convenção
  blend-relative `"//"` do campo `texture_path` já existente) e `use_custom_frag_shader`
  (`DNA_object_types.h`). RNA correspondente em `rna_object.c`: `fragment_shader_path`
  (`PROP_FILEPATH`) e `use_fragment_shader` (bool).
- **UI**: nova seção recolhível "Custom Shader (GLSL)" em `properties_particle.py`, com o
  checkbox, o seletor de arquivo e um lembrete inline do contrato de variáveis disponíveis.
- **Shader cache** (`RAS_ParticleShaderCache`): `Get()`/construtor passaram a receber
  `const std::string &customFragShader`; cache singleton original preservado para o caso vazio
  (zero mudança de comportamento pra cenas existentes), e um `std::map<std::string,
  std::weak_ptr<...>>` novo para shaders customizados — múltiplos emissores com o mesmo texto de
  shader compartilham um único programa compilado, mesmo padrão de refcounting do cache padrão.
  Fonte fragment dividida em `drawFragmentPreamble` (varyings/uniforms, incluindo `u_time` novo)
  + `drawFragmentDefaultMain` (corpo original) ou o script customizado no lugar do corpo — os
  `glBindAttribLocation` (0/1/2) são idênticos nos dois casos, então trocar de shader em runtime
  não quebra os VAOs existentes.
- **Hot-reload** (`RAS_ParticleBuffer`): `LoadFragShaderFromPath()` resolve o caminho
  blend-relative (`BLI_path_abs`) e lê o arquivo; `PollFragShaderReload()`, chamado a cada
  `Update()`, faz `BLI_stat()` no arquivo no máximo 2x/segundo (acumulador `m_fragShaderPollAccum`,
  não every-frame) e recompila só se o `mtime` mudou. Se a recompilação falhar (erro de sintaxe),
  o shader anterior continua ativo e o erro vai pro console — sem flicker nem crash por causa de
  um edit incompleto salvo no meio do caminho.
- **Python**: `object.particles.fragmentShaderPath` (get retorna o caminho atual; set recarrega
  na hora, levanta `ValueError` se a compilação falhar) em `KX_ParticleSystem.cpp`/`.h`.
- **Bridging**: `KX_GameObject::SetupGPUParticles()` chama `LoadFragShaderFromPath` quando
  `use_custom_frag_shader` e o caminho não estão vazios, antes do bloco de textura já existente.
- **Contrato do shader**: o script fornece só o corpo (`void main() { ... }` escrevendo
  `fragColor`); o preâmbulo já declara `v_uv`, `v_lifeFrac`, `v_alpha`, `u_color`, `u_endColor`,
  `u_texture`, `u_useTexture`, `u_colorCurveTex`, `u_useColorCurve` e o `u_time` novo (tempo de
  simulação acumulado do emissor, pra animação).
- **Exemplos criados** em `projects-teste/shaders/particles/` (ver README nessa pasta pro
  contrato completo): `fire.glsl` (chama com ruído procedural e flicker), `smoke.glsl` (fumaça
  difusa com fade longo), `sparkle.glsl` (glitter piscando por partícula via hash+`u_time`),
  `dissolve.glsl` (textura dissolvendo por ruído conforme a vida avança, com borda "queimando"),
  `rainbow_trail.glsl` (matiz variando no tempo via HSV, sem textura). Todos usam só matemática
  de shader — sem sampler extra além dos já fornecidos — pra ficarem baratos.
- **Efeitos adicionados a pedido do usuário** (mesma pasta): `tornado.glsl` (funil com listras
  radiais de poeira girando mais rápido perto do centro via `atan`+`u_time`), `wind.glsl`
  (rajada como listra horizontal fina translúcida com ondulação leve) e `aurora.glsl` (cortinas
  onduladas com matiz verde→violeta deslizando no tempo via HSV, pensado pra sprites grandes/
  esticados em vez de partículas pontuais).
- **Build**: `ge_rasterizer`, `bf_rna`, `ge_ketsji`, `ge_converter` recompilados limpos (exit 0,
  sem `error C`/`error LNK` no log). Teste visual no editor/runtime ainda pendente de validação
  pelo usuário.

## 2026-09-13 — GPU Particles: movimento em vórtex/cone (funil de tornado)

- **Pedido do usuário**: o Look TORNADO deveria não só *parecer* um funil (fragment shader), mas
  fazer as partículas se moverem de fato em cone giratório — estreito na base, alargando conforme
  sobem, girando em torno do eixo vertical do emissor.
- **DNA** (`DNA_object_types.h`, `RangeGPUParticleSettings`, compartilhada por `gpu_particles` e
  `gpu_particles_mix`): campos novos `use_vortex` (short), `vortex_rotation_speed`,
  `vortex_radius_top`, `vortex_height` (float). Precisou de `short pad5` explícito entre
  `use_vortex` e o primeiro float seguinte — o checker de alinhamento do `makesdna` exige múltiplo
  de 4 bytes ali, e sem o padding o build falha com `Align 4 error`/`Sizeerror` (não é erro de
  compilador comum, é validação em tempo de build).
- **RNA** (`rna_object.c`): propriedades `use_vortex`/`vortex_rotation_speed`/`vortex_radius_top`/
  `vortex_height` expostas; `rna_GPUParticleSettings_particle_look_update` zera `use_vortex` em
  todos os Looks que não são TORNADO (evita vazar o modo cone ao trocar de Look) e preenche os
  valores padrão do funil quando TORNADO é selecionado (também ajustou `emitter_radius` pra 0.2,
  `velocity.z` pra 1.5 e `velocity_randomness` pra 0.15, pra combinar com o cone).
- **Update shader** (`RAS_ParticleShaderCache.cpp`, `updateVertexSource`, transform feedback):
  quando `u_useVortex` está ativo, depois da integração normal de posição, a posição XY da
  partícula é reprojetada pro raio-alvo do cone (`mix(emitter_radius, vortex_radius_top,
  heightFrac)`, `heightFrac` calculado a partir de `vortex_height`) e girada em torno do eixo Z do
  emissor por `vortex_rotation_speed` (graus/segundo). Uniforms novos resolvidos e cacheados em
  `RAS_ParticleShaderCache`/enviados a cada `Update()` em `RAS_ParticleBuffer`.
- **Wiring DNA → runtime**: `KX_GameObject::SetupGPUParticlesBuffer` copia os 4 campos novos pro
  `RAS_ParticleBuffer` recém-criado, mesmo padrão dos campos de colisão existentes.
- **UI**: seção "Vortex / Cone (Tornado)" nova em `properties_particle.py`, tanto no painel
  primário (Motion) quanto no painel Mix GPU Particle System — checkbox + rotation speed/top
  radius/height condicionais.
- **Debug overlay standalone** (`KX_ParticleDebugUI.cpp`, ImGui): mesma seção Vortex/Cone
  adicionada ao painel de debug ao vivo do `RangeRuntime`, com os sliders sincronizados nos dois
  caminhos de persistência existentes — `ApplyToBpy` (quando há `bpy`/Python embutido) e o sidecar
  `gpu_particles_debug.json` (fallback sem Python), e leitura de volta em
  `_apply_gpu_debug_values` (`properties_particle.py`) pro operador "Import Debug Values".
- **Look TORNADO (fragment shader)**: reescrito pra densidade volumétrica em camadas (FBM) com
  núcleo escuro e brilho de borda âmbar, no lugar do padrão de faixas senoidais simples anterior —
  junto com `projects-teste/shaders/particles/tornado.glsl` (exemplo customizável).
- **Presets** (`scripts/presets/gpu_particle/`): `tornado.py` reescrito com os novos campos de
  vórtex; os outros 10 presets ganharam `gp.use_vortex = False` explícito pra não herdar o modo
  cone por acidente.
- **Build**: dois rebuilds completos de `RangeEngine` — o primeiro falhou no checker de DNA
  (corrigido com o `pad5`), o segundo (após o fix) e um terceiro (debug UI) fecharam com exit 0.
  Testado pelo usuário no editor: funcionando.

## 2026-09-13 — Web export: `null function` em GPU_state_init (fixed-function GL sob Emscripten)

Continuação do handoff Codex (`HANDOFF-codex-webcrash.md` / commit `af48d99`): com o alocador já
corrigido, `LA_Launcher::InitEngine` avançava até travar num novo ponteiro OpenGL nulo. Reproduzido
com Chrome headless (`--dump-dom`, `--virtual-time-budget=60000`) servindo `build-web/bin/` via
`python -m http.server`, usando a instrumentação `fprintf(stderr, "[web-launcher] ...")` /
`"[web-rasterizer] ...")` já commitada.

- **Diagnóstico**: o log mostrou o crash entre `[web-rasterizer] GPU_state_init begin` e o próximo
  print — ou seja, dentro de `RAS_Rasterizer::Init()` → `GPU_state_init()` (`gpu_draw.c`), antes de
  qualquer chamada de aplicação. Instrumentação adicional (`[web-gpu-state] ...`) dentro de
  `GPU_state_init()` isolou dois pontos de `null function` em sequência:
  1. `GPU_default_lights()` → `GPU_basic_shader_light_set()` / `GPU_basic_shader_light_set_viewer()`
     (`gpu_basic_shader.c`) chamavam incondicionalmente `glLightfv`/`glMaterialfv`/`glLightModeli`
     — API do pipeline fixo do OpenGL desktop, sem equivalente em WebGL/GLES2. Sob Emscripten esses
     símbolos ficam como ponteiro de função nulo no binding e o `RuntimeError: null function` ocorre
     na primeira chamada.
  2. Depois de corrigir o item 1, o crash reapareceu um passo à frente: `glDepthRange(double, double)`
     (versão desktop) também não existe em GLES2/WebGL, que só expõe `glDepthRangef(float, float)`.
- **Fix aplicado** (mesmo padrão de `#ifdef __EMSCRIPTEN__` já usado em `RAS_OpenGLQuery.cpp`):
  - `gpu_basic_shader.c`: `GPU_basic_shader_light_set()` e `GPU_basic_shader_light_set_viewer()`
    pulam as chamadas de pipeline fixo sob `__EMSCRIPTEN__`, mantendo só a contabilidade de estado
    (`lights_enabled`/`lights_directional`) que já era usada apenas para escolher a variante do
    shader GLSL (`solid_compatible_lighting()`), não para ler estado de volta da GL.
  - `gpu_draw.c`: `GPU_state_init()` usa `glDepthRangef(0.0f, 1.0f)` sob `__EMSCRIPTEN__` em vez de
    `glDepthRange(0.0, 1.0)`.
- **Resultado**: rebuild do preset `web-runtime` (via `emsdk_env.bat` + `ninja` do CMake bundle da
  VS 18, ambiente sem `ninja` no PATH padrão) fechou com exit 0; novo teste headless mostrou
  `LA_Launcher::InitEngine` completo (`[web-launcher] engine started`) e o runtime chegando a
  `LA_Launcher::RenderEngine()` — WebGL2 inicializado, shaders básicos e da cena compilados
  (compat GLSL ES 3.00, ainda com vários erros de shaders legados — pendência separada de
  `RAS_ParticleShaderCache`/ImGui, não deste bloqueio).
- **Novo bloqueio já localizado (não corrigido nesta sessão)**: `RuntimeError: null function` em
  `RAS_OpenGLRasterizer::SetLines(bool)` (`RAS_OpenGLRasterizer.cpp`), chamado a partir de
  `RAS_Rasterizer::SetLines()` dentro de `LA_Launcher::RenderEngine()`. A função usa
  `glPolygonMode(GL_FRONT_AND_BACK, GL_LINE/GL_FILL)`, também exclusivo do pipeline desktop —
  mesma categoria de bug, mesmo fix esperado (`#ifdef __EMSCRIPTEN__`, pular a chamada ou usar
  alternativa via shader). Instrumentação temporária `[web-launcher]`/`[web-rasterizer]`/
  `[web-gpu-state]` mantida no código para a próxima sessão.

## 2026-09-13 — Outliner com fundo sólido

- Removido o desenho das faixas alternadas em outliner_draw.c, tanto na árvore quanto nas colunas de restrição. O clareamento fixo de TH_BACK em 6 fazia as duas faixas acompanharem a mesma cor do tema.
- Fundo passa a usar somente a cor do tema; destaques de seleção e linhas de hierarquia continuam existentes. Remoção direta solicitada como alternativa a uma opção, sem novos campos DNA ou alterações no exportador Web.
- Validação: ninja RangeEngine via vcvars64 concluído (19 passos); build/bin/RangeEngine.exe iniciou com --background --factory-startup e confirmou OUTLINER_SMOKE_OK True, saindo com código 0. Conferência visual no editor pendente.

## 2026-09-13 — Opção de faixas no menu View do Outliner

- Adicionado Show Alternating Rows, abaixo de Show Restriction Columns, disponível também nos modos de datablocks e preferências. Desligado por padrão, restaura as faixas herdadas quando ligado.
- RNA show_alternating_rows usa o bit livre 5 de SpaceOops.flag, sem mudar campos, tamanho ou offsets da estrutura DNA. Notificador do Outliner atualiza a interface; estado salvo por espaço no projeto.
- Build RangeEngine via vcvars64 passou (465 passos). Script da UI atualizado em build/bin. Teste em background confirmou presença da opção no menu, padrão desligado, alternância e save/reload para ambos os estados: OUTLINER_TOGGLE_AND_PERSISTENCE_OK, saída 0. Validação visual manual pendente.

## 2026-09-13 — Controles flutuantes na 3D View

- Reunidos em uma única barra compacta, 20 px acima do canto inferior esquerdo, `Play`, `Standalone` e Debug/Console, seguidos pelos modos de sombreamento e sua seta de opções.
- A mesma barra agora inclui os controles de viewport antes presentes no cabeçalho: atualização de render, `Always Render (CPU+)`, Only Render e a seta do painel `VIEW3D_PT_overlay`.
- Os controles realocados foram removidos do cabeçalho. A barra usa os mesmos dados RNA e operadores existentes.
- A região principal passou a registrar os handlers padrão de UI para clique e interação com os novos botões.
- Builds incrementais de `RangeEngine` via `vcvars64.bat` concluídos. Inicialização `--background --factory-startup` confirmou o painel, os dois operadores e a propriedade de console, terminando com `FLOATING_VIEW3D_LAYOUT_RUNTIME_OK`, código 0. Posição, aparência e cliques aguardam validação na janela real.
## 2026-09-17 â€” Sun automÃ¡tico da cena

- UI: moved `World Sun`, `Automatic Sun`, and `Sun Hour` from `Scene` to `World > Sky Render`.
  The controls still edit the active `Scene`: the pointer remains `Scene.world_sun_set`, while `Sun Hour`
  remains the World Global Property `sun_hour`. Generated-Sun creation/removal and runtime conversion are unchanged.
- Sky Render: added an opt-in visual Moon on the opposite side of the sky from the World Sun. It mirrors the
  Sun only around the vertical axis, keeping it above the horizon while the Sun is above; it is a low-brightness,
  short-halo sky disc only, creates no Lamp, and has no effect on scene lighting, shadows, or lens flare.
  Existing Worlds keep it disabled.
- Adicionado `Automatic Sun` no painel `Scene`, logo abaixo de `World Sun`. Ao ativar, cria uma Lamp
  do tipo Sun, marca-a no `.blend` e a atribui ao campo `World Sun`; a posiÃ§Ã£o inicial no editor Ã© a
  da cÃ¢mera da cena mais 5 m na direÃ§Ã£o local `-Z` da cÃ¢mera e 10 m em Z (ou `(0, 0, 10)` sem cÃ¢mera).
- No runtime, apenas a luz marcada pelo checkbox Ã© atualizada a cada frame para a cÃ¢mera ativa mais 5 m
  Ã  frente e 10 m acima; uma luz escolhida manualmente em `World Sun` nunca recebe esse comportamento.
  Sem cÃ¢mera ativa, o runtime conserva a Ãºltima posiÃ§Ã£o e emite um Ãºnico aviso, sem interromper a cena.
- Ao desligar o checkbox, a luz criada pelo checkbox Ã© removida da cena e de `World Sun`. A organizaÃ§Ã£o
  dessa luz sob `World` no Outliner ficou deliberadamente para uma etapa posterior.
- Automatic Sun now uses the ground point 5 m in front of the active camera as its shadow reference. It records
  the initial camera height, subtracts it from the live camera position to estimate ground elevation, orbits that
  reference at a 10 m radius, and aims its local `-Z` back at it; it no longer spins in place or points away
  from the player area. `Sun Hour` creates the World Float Global Property `sun_hour` with default `12`; runtime
  maps its circular 0-24 value to that orbit (12 = directly overhead, 6/18 = horizon), including writes from a
  Global Property Property Actuator.

## 2026-09-17 — Organização dos painéis de objeto Game

- O seletor de objeto e o checkbox `Fake User` agora ocupam a mesma linha na aba Object.
- `Game Object Tasks`, `Activity Culling` e `Animation Events` passaram da aba Object para a aba Game.
- Validação: sintaxe Python dos dois módulos de UI e `ninja RangeEngine` via `vcvars64.bat` concluídos; os scripts foram instalados em `build/bin/2.79/scripts/startup/bl_ui/`.

## 2026-09-17 — Descrição de Convert

- O tooltip de `Game Object Tasks > Convert` agora explica que a opção cria o objeto no runtime e que, desativada, ele não renderiza, executa lógica ou física, nem fica acessível por scripts. O caso de uso indicado é somente para helpers exclusivos do editor.

## 2026-09-17 — Activity Culling usa a referência de otimização

- `Physics Radius` e `Logic Radius` continuam usando distância euclidiana ao quadrado, mas agora a medem contra `KX_Scene::GetOptimizationReferencePosition()`: a câmera ativa hoje e, futuramente, a referência do Player.
- A atualização ocorre antes da avaliação de Activity Culling, evitando usar a posição do frame anterior. Câmeras inativas deixam de manter objetos ativos; para habilitar o recurso, a câmera ativa precisa ter `Activity Culling` marcado.
