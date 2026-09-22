# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, como sempre). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-09-21 a 2026-09-20 | 34 | 50 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |

## 2026-09-21 - Teste Sun+Point+IBL no BLENDER_GAME: sombra ausente em materiais Principled/PBR

- **Objetivo:** validar visualmente (jogo real, não captura automatizada — ver regra do `AGENTS.md`) a combinação
  de Lamps de cena (Sun/Point/Spot) com o IBL do Principled corrigido em `059766dc`, e checar sombras.
- **Cenas de teste criadas** em `projects-teste/pbr-baseline/`: `make_lights_ibl.py` (variantes Sun+IBL,
  Sun+Point+IBL, Sun+Point sem IBL, a partir do `pbr_test.blend` legado) e `make_shadow_test.py` (cena nova,
  não reaproveita o legado, salva direto como `.range` — `shadow_ibl_test.range`).
- **Achado 1 (script, não bug de engine):** `pbr_test.blend` carregava logic bricks de um diagnóstico anterior
  (`dd0777dc`) que chamavam `bge.logic.endGame()` no frame 45 (~1,5 s) — por isso o runtime "fechava sozinho"
  ao abrir os `.blend` derivados dele. `make_lights_ibl.py` agora remove esses sensores/controladores/texto
  antes de salvar.
- **Achado 2 (bug de UI, corrigido):** `bl_ui/properties_game.py`, painel `DATA_PT_light_culling_game`
  ("Distance Culling", visível para lamps não-Sun), linha `row = box.row()` usava uma variável `box` nunca
  definida → `NameError` ao abrir os dados de um Point/Spot light recém-criado. Trocado para `row = layout.row()`
  na fonte (`source/release/scripts/startup/bl_ui/properties_game.py`) e na cópia instalada
  (`build/bin/2.79/scripts/startup/bl_ui/properties_game.py`). Script Python puro, não exige rebuild.
- **Achado 3 (limitação de engine, confirmada em código):** Lamps do tipo Point/Local **nunca** geram shadow
  buffer GLSL neste engine — `gpu_material.c:3997` só cria shadow buffer para `LA_SPOT` (com `BUFFER_SHADOW`
  ou `RAY_SHADOW`) e `LA_SUN` (com `RAY_SHADOW`); `LA_LOCAL` fica de fora. Não é bug introduzido agora, é
  arquitetura herdada do fork. Lamps recém-criadas via `bpy.ops.object.lamp_add()` também nascem com
  `use_shadow=False` (nenhum preset automático via script/headless).
- **Achado 4 (gap real, não corrigido ainda):** materiais **Principled/PBR não recebem nem projetam sombra**
  no `BLENDER_GAME`. O usuário testou `shadow_ibl_test.range` (Sun com `RAY_SHADOW` + Spot com `BUFFER_SHADOW`)
  e viu sombra ao redor da esfera (sombreamento normal, lado escuro) mas nenhuma sombra projetada no chão; ao
  desligar as opções PBR e usar material sem nodes, a sombra no chão aparece. Causa: o loop de luzes de cena
  do Principled (`gpu_shader_material.glsl:3918-3941` e `:4018-4025`, escrito em `5814df2e`/`059766dc`) lê
  `gl_LightSource[i]` (estado fixed-function) diretamente, sem nenhuma chamada às funções de sombra do shader
  (`shadow_simple`/`shadow_pcf`/etc.) nem wiring de shadow map/matriz por lamp em `gpu_material.c`.
  `node_shader_bsdf_principled.c` não menciona "shadow" nenhuma vez. O caminho legado (materiais sem nodes)
  passa pelo grafo de shading antigo, que já injeta essas chamadas — por isso só ele mostra sombra no chão.
- **Não implementado nesta sessão** (registrado, aguardando decisão do usuário para entrar como tarefa de
  C++/GLSL): levar shadow map + matriz de projeção por lamp até o loop `NUM_LIGHTS` do Principled e multiplicar
  `light_diffuse`/`light_specular` pelo fator de sombra antes de somar, espelhando o que o caminho legado faz.
  Ver `docs/roadmap.md` (seção "Iluminação e gráficos").

## 2026-09-21 - Importação direta de OBJ arrastado para a Vista 3D

- A Vista 3D agora aceita o drop de arquivos `.obj` (extensão sem diferença entre maiúsculas e minúsculas) e executa o importador com o caminho recebido, sem abrir o seletor nem exigir clique em Import.
- O operador nativo `VIEW3D_OT_import_obj_drop` ativa `io_scene_obj` quando o addon ainda não estiver carregado e chama `IMPORT_SCENE_OT_obj` em modo de execução. Outros tipos de arquivo mantêm os fluxos anteriores.
- A compilação dos dois arquivos C e o link de um executável de teste concluíram. Duas tentativas de link do `RangeEngine.exe` principal pararam com `LNK1104`: uma instância do editor permanece aberta usando esse arquivo e não foi interrompida. No executável de teste, com configuração inicial limpa, um arquivo `.OBJ` de uma face retornou `FINISHED`, criou `DropFixture` com uma face e ativou o addon. O drop pela interface gráfica ainda requer verificação manual.

## 2026-09-21 - Pacote Windows 0.4.1

- Splash atualizado para 0.4.1 (`wm.py`). Build completo da `linux-sync` (`ninja -t clean` + `RangeEngine RangeRuntime`, 2335 alvos, exit 0), incluindo a DNA do terremoto e os guards de audio; o pacote Linux 0.4.1 nao tem o terremoto.
- `lib/win64_vc15` havia sido apagada na limpeza de worktrees (nao estava em Lixeira nem em outro disco) e foi restaurada de backup em SSD externo antes do build. A primeira tentativa do build parou com "Permission denied" em alguns `.obj` (transitorio); a retomada passou sem falhas.
- Pacote `AnastacioEngine-0.4.1-windows-x64.zip` (149 MB) montado em `build/release-staging/` com o layout da 0.4.0 (`blender.crt/` + `ucrtbase.dll`, sem DLLs do VC++ soltas), addons ausentes da fonte (cycles, add_curve_extra_objects etc.) herdados do pacote 0.4.0, e `startup.blend` local excluido. Validado extraindo o zip em pasta limpa: `RangeEngine.exe --version` ok e janela viva apos 12 s; `RangeRuntime.exe` abre `demos/Example_ImgGui` e segue rodando; sem eventos SideBySide. `RangeRuntime.exe` sem argumentos sai com codigo 11, igual ao da 0.4.0.
- Ainda nao publicado na release `v0.4.1`.

## 2026-09-21 - Teste no Linux da linux-sync: tudo ok

- O usuario baixou a `linux-sync` no Linux, compilou e testou: "esta funcionando tudo ok". Sem falhas relatadas. Nao foi detalhado quais cenarios foram exercitados (editor, runtime, Web); o registro vale como validacao geral informada pelo usuario.

## 2026-09-21 - Limpeza de branches/worktrees; Web reconstruido limpo a partir da linux-sync

- A `integracao` estava totalmente contida na `linux-sync` (883c1558). Worktree `D:\AnastacioEngine-integracao` e branch local `integracao` removidos; sobram os worktrees da `linux-sync` e da `master`. Branches remotas antigas e o `perf-artifact` tambem foram apagados a pedido do usuario. Nada foi enviado ao GitHub nesta limpeza.
- Rebuild Web limpo da `linux-sync` (`web-runtime-release`, 1817/1817 alvos, exit 0, 242 modulos Python). Sonda R3 rodada duas vezes no Edge headless: `[r3] TODOS`, sem `Aborted`. Isso substitui a validacao feita na `integracao`.
- `linux-sync` (origin e local iguais) e a branch a baixar no Linux para build e teste; o teste no Linux e feito pelo usuario (resultado registrado na entrada acima).

## 2026-09-21 - Branch integracao: guards de leitor nulo do Codex sobre o som silencioso

- Incorporados os guards de `codex/r3-audio-fix` (leitor nulo em `AUD_Sound`, `AUD_Special`, `PySound`, `PyDevice.play`, `Limiter`, `Pitch`, `VolumeSound`), sem o `WAVFile.cpp` do Codex, que desfaria o som silencioso.
- Build Web incremental e sonda R3 reexecutada: 10/10, `[r3] TODOS`, sem `Aborted`.

## 2026-09-21 - Branch integracao: validacao dos builds e da sonda R3

- Branch `integracao` (dc0a5639) reune os historicos claude/* e codex/* sobre `linux-sync`.
- Build nativo (`RangeEngine`, `RangeRuntime`, preset `v142-ninja`) e build Web limpo (`web-runtime-release`, `.wasm` de 21,6 MB) concluidos com exit 0.
- Sonda R3 de 10 casos rodou no Chrome headless sobre o build Web da `integracao`: terminou em `[r3] TODOS`, sem `Aborted`. As correcoes do Codex (leitor nulo, `WAVReader`) e do Claude (`-fexceptions`, guards de `AUD_Sound`) convivem.
- Arquivos de audio invalidos no Web agora devolvem um som silencioso vazio (`[aud] file could not be decoded; using a silent empty sound`) em vez de lancar excecao; a sonda R3 passa 10/10 sem `Aborted`.
- Regressoes no Web: R1 (nativo e Web) PASS; bloom/resize sem `glError`; `aud` sem argumentos (`cache`, `reverse`, `pause`, `stop`) sem erro; dois `.blend` de nos (Aula6, Aula8-Fim) compilam sem `shader_errors` (so compilacao, sem conferir frames).
- Audio: o teste automatizado com tom de seno (22050 Hz, reamostrado para 48000 Hz, em loop) mostrou um clique por volta (~1 s), pois o `JOSResampleReader` reinicia no `seek(0)` e perde ~2 amostras por volta. Comportamento herdado do Audaspace, presente tambem no nativo. **Com musica real (mp3/ogg) o usuario ouviu o som perfeito no navegador**; a perda medida e 0 a ~1 amostra em 480000. O clique e um artefato do tom de teste, nao do motor; nenhuma alteracao no Audaspace foi feita.
- Artefatos locais (pacotes `build-web-*pkg`, `.range` de teste, `projects-teste/node`) e `.log` nao vao para o Git.

## 2026-09-21 - Terremoto: direção, escala, tremor de câmera e corpos dormindo

- **Problema:** o terremoto (World > Weather > Earthquake) era fraco e só sacudia a gravidade lateralmente. Além disso, `btDiscreteDynamicsWorld::setGravity` e `applyGravity` só atuam em corpos **ativos** (`isActive()`): objeto dormindo (sleep) ignorava o terremoto e nunca acordava. Não é preciso desligar o sleep por objeto.
- **Correção (`KX_Scene::UpdateEarthquake`):** enquanto o terremoto está ligado, `PHY_IPhysicsEnvironment::WakeAllBodies()` (novo; implementado em `CcdPhysicsEnvironment`, no-op no Dummy) acorda os corpos dinâmicos antes de aplicar a gravidade. Níveis 1-5 ficaram ~2,5x mais fortes (força 2, 4.5, 9, 15, 24), pois o tremor lateral precisa vencer o atrito.
- **Novas opções no World:** `earthquake_scale` (0,1-5, multiplica a força do chão), `earthquake_mode` (Horizontal, Vertical ou Both; o vertical pode levantar objetos em nível alto) e `earthquake_camera` (Camera Shake Scale, 0-2).
- **Tremor de câmera:** `KX_Camera::SetShakeShift` soma um deslocamento temporário ao `shift_x`/`shift_y` (lens shift) da câmera ativa ao montar a projeção; o `shift` autorado não é alterado e o deslocamento é zerado quando o terremoto termina. Segue o Level e a Direction.
- **DNA:** `weather_pad3` virou `earthquake_mode` e `earthquake_pad` virou `earthquake_camera` (short/float de padding, zerados em arquivos antigos: direção Horizontal, câmera desligada); `earthquake_scale` e `earthquake_pad2` são novos (o tamanho de `World` cresce 8 bytes). `earthquake_scale` 0 (arquivo antigo) vale 1. Mundos novos: scale 1, câmera 1. Traduções PT/ES/RU adicionadas.
- **Validação:** `ninja -t clean` + `RangeEngine RangeRuntime` no worktree `claude-rna`: 0 erros. **Testado pelo usuário no editor (Windows nativo): "funciona bem"** (cena `projects-teste/teste-terremoto/terremoto.range`). Um teste automatizado por script (posições dos cubos) rodou sem imprimir nada e não serve como evidência. **Não** foi feito rebuild Web nem teste Web (a DNA mudou; o Web precisa de rebuild limpo).

## 2026-09-21 - WebAssembly: integração aud + R3 sobre linux-sync; sonda R3 passa com -fexceptions

- Branch `claude/web-aud-r3-integ` (base `linux-sync` 3c0b9fcf): correção de aridade do `aud` (ea2cfd04) e o R3 do Codex (ad95c2e8, aplicado como bab82233), que protege `AUD_Sound_getSpecs` e `AUD_Sound_getLength` contra `AUD_Sound` nulo.
- **Erro encontrado no 3c0b9fcf:** `mathutils.h:86` declarava `BaseMathObject_freeze(..., PyObject *UNUSED(args))` em protótipo. `UNUSED()` só vale em definição, então todos os `.c` de `mathutils` falhavam no build Web. Corrigido para `PyObject *args_unused` (a definição em `mathutils.c` não muda). O `linux-sync` remoto ainda contém o header quebrado até esta correção ser enviada.
- Rebuild Web release (`web-runtime-release`): `exit=0`, 280 passos, 240 módulos Python no manifesto.
- Primeira tentativa da sonda R3 (`claude_r3_probe.py`, pacote `package-web.py`, Chrome headless), sem `-fexceptions`: **falhou no primeiro caso**. `aud.Device().play(aud.Sound.file('/nao_existe.wav'))` imprime `[r3] INICIO` e aborta com `Aborted(undefined)` em `__cxa_throw` → `__Unwind_RaiseException`. Os demais casos (WAV corrompido, `.volume(0.5)`+`play`, `.length`, `.specs`) não chegaram a rodar, e `cache()`, `reverse()`, `handle.pause()` e `handle.stop()` não foram sondados.
- Causa: o runtime Web é compilado sem captura de exceções C++ do Emscripten, então qualquer `AUD_THROW` (`FileException` ao abrir arquivo inexistente ou ilegível) aborta o processo, apesar do `catch (Exception&)` nos bindings Python. O guard do R3 cobre só ponteiro nulo na API C e não alcança esse caminho.
- **Correção:** `-fexceptions` nos alvos `audaspace`, `audaspace-py` e `audaspace-c` (só Emscripten, `extern/audaspace/CMakeLists.txt`) e no link do RangeRuntime (`blenderplayer/CMakeLists.txt`). Rebuild Web release: `exit=0`; `RangeRuntime.wasm` foi de 21,4 MB para 21,6 MB.
- **Sonda R3 após a correção (Chrome headless, `[r3] TODOS` alcançado, sem `Aborted`):** arquivo inexistente + `play`, arquivo/texto corrompido + `play`, corrompido + `.volume(0.5)` + `play`, corrompido `.length` e corrompido `.specs` levantam todos a exceção Python `error: The file couldn't be read with any installed file reader.` e o runtime continua vivo. Não sondados: `cache()`, `reverse()`, `handle.pause()` e `handle.stop()` (exigem um som válido); a aridade deles foi corrigida em ea2cfd04, mas não foi exercitada em runtime.
- **Commits no `linux-sync`** (3c0b9fcf → ae0a5609): ea2cfd04 (aridade `aud`), bab82233 (R3, guard C), 870a37e9 (`mathutils.h` + sonda), ae0a5609 (`-fexceptions` + changelog). O `linux-sync` anterior (3c0b9fcf) **não compilava o Web** por causa do `mathutils.h`; quem construir Web precisa desta versão.
- **Como reproduzir a sonda:** `tools/web/package-web.py --game projects-teste/teste-editor-web/claude-r3-probe.range --extra projects-teste/teste-editor-web/claude_r3_probe.py --runtime-dir build-web-release/bin --out-dir build-web-r3pkg --name r3probe`; servir com o `serve.py` do pacote e abrir `index.html` (o script `claude_r3_probe.py` imprime `[r3] ...` e termina com `[r3] TODOS`). `claude_r3_criar.py` recria o `.range`.
- **Linux (outra máquina):** `git pull --rebase --autostash origin linux-sync`. As mudanças de CMake do audaspace são condicionadas a `EMSCRIPTEN` e não afetam o build nativo; o `mathutils.h` só troca o nome do parâmetro do protótipo. Nenhum rebuild especial é necessário além do incremental.
- **Pendências ligadas a este assunto:** exercitar `cache()`, `reverse()`, `handle.pause()`/`stop()` com som válido; conferir o custo de desempenho do `-fexceptions` (M3, celular); o R3 do Codex não commitado em `AnastacioEngine-codex-r3-audio-fix` não foi integrado (só o commit ad95c2e8).

## 2026-09-21 - WebAssembly: assinaturas Python METH corrigidas em bmesh

- Auditadas as tabelas `PyMethodDef` e as definições C em `mathutils`, `blf`, `bmesh` e `gpu` para conferir a aridade exigida por `METH_NOARGS`, `METH_O`, `METH_VARARGS` e `METH_VARARGS | METH_KEYWORDS`.
- Encontrados 38 callbacks C distintos de `bmesh` marcados `METH_NOARGS` que declaravam somente `self`, além de `BaseMathObject_freeze` em `mathutils`. Todos agora recebem também `PyObject *UNUSED(args)`, preservando integralmente os corpos e o comportamento; as entradas repetidas de `index_update`/`ensure_lookup_table` reutilizam as duas definições corrigidas.
- Nenhuma incompatibilidade foi encontrada em `blf` ou `gpu`. Não foram alterados `intern/audaspace`, `KX_PythonInit.cpp` nem `KX_PyConstraintBinding.cpp`.
- A revarredura após o patch não encontrou incompatibilidades de aridade nos quatro módulos. Validação nativa: `ninja RangeEngine` com `vcvars64.bat` concluído com exit 0; nenhum rebuild Web foi executado.

## 2026-09-21 - Linux: RUNPATH do libpython validado; crash do tooltip investigado

- Kitsuy reportou no 0.4.0 `libpython3.11.so.1.0` nao encontrado e crash em tooltips. O pacote levava RUNPATH absoluto `/opt/anastacio-python311/lib`.
- CMake de `RangeRuntime`/`RangeEngine` passou a usar `$ORIGIN/lib` e copiar o libpython real para `lib/`; `package-runtime.sh` aceita `BIN_DIR` e valida o libpython no pacote.
- **Validado em Linux nativo (Ubuntu, GPU local):** build do `RangeEngine` (`linux-editor`), `readelf -d` confirma RUNPATH `$ORIGIN/lib:/opt/anastacio-python311/lib:` (na ordem certa, `$ORIGIN/lib` primeiro), `bin/lib/libpython3.11.so.1.0` presente. Empacotado com `BIN_DIR=build-linux-editor/bin tools/linux/package-runtime.sh 0.4.1`. Extraido em diretorio limpo (`/tmp/pkgtest`): `LD_DEBUG=libs` confirma que o linker resolve `libpython3.11.so.1.0` via `$ORIGIN/lib` do proprio pacote, sem sequer tentar `/opt/anastacio-python311/lib` (nao precisou remover o `/opt` da maquina de teste, que ja tinha o path). `./RangeEngine -b` roda e sai limpo (exit 0), sem erro de `encodings`/stdlib. Fix confirmado correto.
- Build no Linux (GCC) expos um erro pre-existente nao relacionado ao RUNPATH: `source/intern/locale/boost_locale_wrapper.cpp` usava `std::cout` sem incluir `<iostream>` (so tinha `<stdio.h>`); no MSVC algum header do boost arrastava `<iostream>` transitivamente, no GCC/libstdc++ nao. Corrigido com `#include <iostream>`.
- Crash do tooltip: investigado, corrigido e validado em sessao grafica real (ver entradas abaixo e `linux-build.md`). 0.4.1 pronto para empacotar.

## 2026-09-21 - Investigacao (nao confirmada): crash de tooltip

- Revisao estatica de `interface_region_tooltip.c`, `interface_handlers.c` (timer de tooltip), `rna_access.c`
  (`RNA_path_full_struct_py`/`RNA_path_full_property_py_ex`) e `rna_userdef.c`/`versioning_defaults.c`.
- Achado: a checkbox "Python Tooltips" **nao esta invertida** por bug — `rna_userdef.c` usa
  `RNA_def_property_boolean_negative_sdna` com `USER_TOOLTIPS_PYTHON`, padrao ja usado no Blender upstream.
  Com o default atual (bit ligado por `versioning_defaults.c:86`), a checkbox aparece desmarcada e o ramo que
  gera os campos "Python: ..." do tooltip **nao roda** em preferencias limpas — entao a causa do crash do
  Kitsuy provavelmente nao esta nesse ramo, a menos que ele tenha um `userpref.blend` antigo com o bit zerado.
- Hipotese mais provavel (H1): uso-apos-liberacao em `RNA_path_full_property_py_ex`/`RNA_path_full_struct_py`
  (`rna_access.c`) quando o ID referenciado por `but->rnapoin` e removido/trocado entre o hover e o disparo do
  timer do tooltip (delay), que so revalida o `uiBut` (`UI_region_active_but_get`), nao o ID dentro do RNA
  pointer. So roda se `USER_TOOLTIPS_PYTHON` estiver com o bit OFF (checkbox marcada).
- Hipotese secundaria (H2, mais fraca): getters RNA de propriedades registradas em Python chamados sem
  garantia de GIL/estado de interpretador, se o motor liberar o GIL em algum ponto proximo ao hover.
- "Show Profile" (`GameSettings.show_framerate_profile`) nao tem nenhuma relacao de codigo com o tooltip;
  a hipotese mais provavel (H3) e que ligar essa opcao desloca o layout do header e o mouse deixa de cair
  sobre o widget problematico — coincidencia de layout, nao correcao real.
- Nao reproduzido com gdb (sem `xdotool`/similar no ambiente do agente para simular hover; precisa de sessao
  interativa real). Nenhuma correcao aplicada ainda.
- Perguntas para o Kitsuy: (a) "Python Tooltips" esta marcada nas preferencias dele? (b) qual botao/painel
  exato crasha? (c) reproduz em cena default/vazia?

## 2026-09-21 - Segunda rodada: fix defensivo aplicado ao crash de tooltip (nao reproduzido)

- Segundo agente aprofundou a investigacao acima. Releu `interface_region_tooltip.c` e
  `UI_but_string_info_get` por completo: nesse fluxo tudo e recalculado a partir do `uiBut*` ja validado,
  sem ponteiro obsoleto. Seguiu a cadeia do timer em `interface_handlers.c:7345` e viu que
  `UI_region_active_but_get()` **revalida** o `uiBut*` a cada disparo — o que torna H1 (ID RNA obsoleto
  dentro de `but->rnapoin`) menos provavel do que se pensava.
- Achado novo, um nivel acima: em `source/source/blender/windowmanager/intern/wm_tooltip.c`,
  `screen->tool_tip->region_from` (o `ARegion*` capturado quando o hover comeca) **nunca e revalidado**
  antes de ser usado em `WM_tooltip_init()`, disparado ~`UI_TOOLTIP_DELAY` (0.5s) depois. Operacoes de
  layout nesse intervalo (`ED_area_data_copy` em `area.c` — maximizar/restaurar area, trocar tipo de
  editor, split/join, fullscreen) liberam `ARegion`s inteiros sem passar por nenhuma limpeza do estado de
  tooltip pendente. Use-after-free plausivel, coerente com um crash intermitente ao "passar o mouse" em
  fluxo de uso exploratorio (hover rapido entre paineis/abas). Padrao existe tambem no Blender upstream,
  nao e regressao do fork.
- **Fix aplicado** (nao commitado, aguardando revisao): `wm_tooltip_region_is_valid()` percorre
  `screen->areabase`/`regionbase` vivos e confirma que `region_from` ainda existe antes de usa-lo em
  `WM_tooltip_init()`; se nao existir, limpa o estado (`WM_tooltip_clear`) e sai sem dereferenciar.
  Tambem adicionado null-check de `screen->tool_tip` (hardening, os 2 call sites atuais ja garantiam
  nao-nulo). Build `linux-editor`/`RangeEngine` limpo apos o fix.
- Sem `Xvfb`/`xdotool`/sudo no ambiente do agente, nao foi possivel montar sessao grafica headless para
  simular hover + mudanca de layout sob gdb; validacao ficou pendente de sessao grafica real (ver abaixo).

## 2026-09-21 - Terceira rodada: fix de tooltip validado em sessao grafica; padrao de fabrica corrigido

- Validado manualmente por Fabio em sessao grafica local (`DISPLAY` real, nao `--background`): com
  "Python Tooltips" ligado (caminho de codigo mais exposto), hover em botoes seguido de Ctrl+Espaco
  (maximizar/restaurar area) repetido em varios paineis, antes do disparo do timer (~0.5s) — sem crash,
  processo sai limpo. Repetido tambem com `HOME` limpo simulando primeira execucao (sem config previa):
  preferencias carregam corretamente, sem crash. Fix em `wm_tooltip.c` considerado validado.
- `versioning_defaults.c`: `USER_TOOLTIPS_PYTHON` deixava a checkbox "Python Tooltips" **desmarcada** por
  padrao (por causa do `RNA_def_property_boolean_negative_sdna`), o que fazia o caminho de codigo mais
  exposto ao bug nunca rodar numa instalacao limpa. Corrigido para a checkbox vir **marcada** por padrao
  (bit desligado), para exercitar o caminho real em vez de mascarar o problema por omissao.
- `source/release/datafiles/startup.blend` (arquivo de fabrica embutido no build) atualizado com as
  demais preferencias de interface confirmadas por Fabio pela UI (`~/.config/range/2.79/config/startup.blend`
  copiado por cima do arquivo do fonte).
- Bug 2 (crash de tooltip) considerado **resolvido** para efeito de release; falta so empacotar 0.4.1 e o
  teste final em pacote extraido (ver roadmap).

## 2026-09-20 - Android: revisão técnica do plano de exportação

- Revisado `android-export-plan.md` contra código local, estado dos presets e fontes oficiais Android,
  Chromium, Emscripten e W3C. WebView mantido como rota recomendada, condicionada à prova no aparelho.
- Antecipado APK mínimo com jogo real (A0b/A2) antes da CLI/editor; definido núcleo de toque digital,
  persistência confirmada e pausa/retomada. Sensores/analógico/API Python e AAB ficam para etapas posteriores,
  salvo requisito essencial do jogo. Ponte Kotlin pequena passa a ser alternativa antes de reabrir NDK.
- Corrigidas premissas sobre `syncfs` assíncrono, pausa de JavaScript, gamepad virtual, compressão dos assets,
  capacidades do WebView, offline em TWA e campos de presets já implementados. Acrescentados critérios de
  memória de carga, frame time sustentado, atualização preservando save e recuperação do renderer.
- Alinhados índice, roadmap, relatório e nota no antigo roadmap Android/Web, preservando o histórico anterior.
- Somente documentação: nenhuma implementação, compilação ou execução Android nesta revisão. Inspeção de
  fontes e consistência documental não substitui os testes A0/A5 nem comprova suporte mobile.

## 2026-09-20 - Android: replanejamento sobre o runtime Web

- Com o Web funcionando, o export Android v1 passa a ser um APK-casca (WebView) embutindo o pacote Web; o backend
  nativo NDK fica congelado com critério de reabertura. Novo `docs/android-export-plan.md` (marcos A0–A5);
  roadmap, relatório, README e `mobile-export-plan.md` apontam para ele. Só documentação, nenhum código alterado.
- Diferencial mobile incorporado ao marco A1: multitouch e sensores de movimento (orientação, aceleração, giro,
  vibração) via APIs Web, primeiro traduzidos para teclado/gamepad no harness JS, depois expostos em Python.
## 2026-09-21 - Web: gancho `--perf` aplicado em `package-web.py`

- `package-web.py --perf` copia `frame-time-perf.js` para o pacote e o carrega no `index.html` (opt-in; ativo so com `?perf=1`). Sem a flag o pacote sai como antes. O manifesto e `SHA256SUMS.txt` ja incluem o arquivo por varredura do diretorio.
- Verificado: pacote com e sem `--perf` (8 e 7 arquivos); `perf-run.cjs` em Edge headless/SwiftShader recebeu frames (count 12, DPR 1, 1280x720) so como prova da ferramenta, nao e medicao de celular; sem `--perf`, `__rangePerf` fica indefinido. `validate-web.py` nao rodou aqui (exige o `bpy` da engine, o do pip quebra no import).

## 2026-09-20 - Web: R3 corrigido (audio invalido nao aborta mais); perf e teste de link do Codex integrados

- **R3 corrigido no runtime Web.** Causa: o Wasm nao tem excecoes (`AUD_THROW` aborta) e `FileManager` devolvia leitor nulo, desreferenciado pelos leitores de efeito (`volume`, `limit`, `pitch`). Correcao: sob `__EMSCRIPTEN__`, `FileManager::createReader` (arquivo e buffer) devolve um `UnreadableReader` silencioso de comprimento zero (44100 Hz, mono) e loga `[aud] file could not be decoded`; `WAVReader` nao lanca mais (flag `ok()`, `makeReader` devolve nulo). Nativo inalterado (continua lancando).
- Evidencia: `build-web` recompilado; `claude_r3_probe` (10 casos: inexistente, corrompido, RIFF/WAVE quebrado, com volume/limit/pitch, `.length`, `.specs`) empacotado e rodado no Edge headless isolado (`claude_r3_run.cjs`): termina com `[r3] TODOS: true`, sem abort. Builds nativo (`RangeRuntime RangeEngine`, 9/9) e `build-web-release` (22/22) terminaram com codigo 0.
- `codex/r3-audio-fix-new` (`ad95c2e8`) fica **superado** (nao chegava a causa); nao integrado.
- **Bug geral de `aud` achado, nao corrigido:** metodos `METH_NOARGS` de `PySound`/`PyDevice`/`PyHandle` (ex.: `sine.cache()`, `reverse()`, `handle.pause()/stop()`) dao `function signature mismatch` no Wasm (cast de ponteiro com aridade diferente). Confirmado com som valido (`claude_aud_noargs_probe.py`, so o 1o caso executado); ~16 metodos. A sonda R3 nao cobre `.cache`. Correcao depende de autorizacao.
- Codex integrado (merges locais, sem push): `codex/perf-run` (`perf-run.cjs`, overlay `?perf=1` em `frame-time-perf.js`; corrigi o `'\\n'` do overlay) e `codex/shader-node-test` (`NOTA-SHADER-MATERIAL-NODES.md`, `preflight-link.json` e teste de link; teste de node-material justificado como nao injetavel). Suite `web_profile`: 99 OK. `perf-run.cjs` rodou em Edge headless (SwiftShader: count 130, p50 97 ms, p95 127 ms, DPR 1, 1280x720) so para provar a ferramenta; **nao e medicao de celular**. Gancho `--perf` em `package-web.py` esta so proposto (`docs/web-perf-hook-proposal.md`), nao aplicado.
- **Nao repetidos apos a mudanca de audio:** regressao de audio (`verify-capabilities.cjs audio`, exige Chrome com CDP), resize do bloom, resolucao dinamica sem timer e R1 nativo/Web. Ficam para a proxima sessao.

## 2026-09-20 - Web: nome do material e falha de link nos diagnosticos de shader; T4 e T5 do Codex integrados

- `KX_BlenderMaterial::getShader()` passa o nome do material ao `BL_Shader` (`RAS_Shader::SetDiagnosticName`); em `shader_errors[]` o campo `material` sai como o nome real do ID (ex.: `MAMatQuebrado`, com o prefixo `MA` do Blender) em vez de `engine-shader`. Filtros 2D continuam `2d-filter`.
- Testado com `build-web` recompilado (19/19, codigo 0), pacote real e Edge headless isolado (`claude_m1c_diag.cjs`): vertex invalido -> `operation` "compile", `stage` "vertex", `material` "MAMatQuebrado"; **falha de link** (vertex valido, fragment com `in` sem `out` correspondente; `criar_m1c.py -- --link` + `shader_quebrado.quebrar_link`) -> `operation` "link", `stage` "", log `FRAGMENT varying varying_inexistente does not match any VERTEX varying`, `material` "MAMatQuebradoLink". Nao testado: shader de material de nos. Nota: o runtime usa GLSL ES 3 (`ftransform`, `varying` e `gl_FragColor` nao existem), entao shaders escritos para o desktop falham no Web.
- Suite `tools/tests/web_profile`: 98 testes OK.
- Merges locais (sem push): `codex/r1-guard` (T4: guard estatico tolera stubs `Range` quebrados; `constraint_abi_test.py` -> `PASS (31 methods)`) e `codex/perf-tool` (T5 parcial: `tools/web/frame-time-perf.js` + `docs/web-frame-time-perf.md`; validado aqui so em Node com rAF sintetico, p50/p95 corretos). A ferramenta **nao esta ligada** ao `index.html` gerado (o Codex nao editou `package-web.py`) e nao ha script CDP; o usuario ainda nao consegue medir no celular sem incluir o script a mao.
- **T3 nao integrado:** `codex/r3-audio-fix-new` (`ad95c2e8`) so troca `assert` por guarda em `AUD_Sound_getSpecs/getLength`, mas ainda chama `createReader()->` sem checar o leitor nulo, que e a causa do segfault; sem build Web nem sonda. R3 segue **aberto**.
- Nao refeitos nesta rodada: nativo, `build-web-release`, regressao de audio, resize do bloom e `claude_r3_probe` (nenhuma mudanca de C++ alem do nome do shader; so `build-web` foi recompilado).

## 2026-09-20 - Web: integração de R1 e R3 e verificação no runtime integrado

- Merges locais (sem push) na `claude/web-m1-python-diag`: `codex/r3-audio-m3-tests` e `codex/r1-constraint-abi`; único conflito foi o topo do changelog (mantidas as duas entradas).
- Builds com código 0 depois dos merges: nativo (11/11), `build-web` (8/8) e `build-web-release` (8/8).
- **R1 verificado:** `constraint_abi_test` passa no `RangeRuntime.exe` nativo (`constraint_abi_test_result.txt` = PASS) e no runtime Web (Edge headless, `CONSTRAINT_ABI_TEST: PASS` no console).
- **Regressão de áudio:** cena `create_web_audio_scene.py` (`verify-capabilities.cjs audio`) 8/8 OK (AudioContext ativo, mixer avançou, amplitude não nula); módulo `aud` (`create_web_aud_module_scene.py`) importa, cria Device e toca seno.
- **M3 no runtime integrado:** `claude_m3_resize` repetido, mesmos resultados (offscreens canvas/2,/4,/8, `glError=0x0`, aviso único do timer).
- **R3 NÃO está resolvido:** sonda `claude_r3_probe.py`/`claude_r3_criar.py` no runtime integrado. `Sound.file()` de arquivo inexistente ou de texto corrompido + `Device.play` não aborta, mas devolve um `Handle` (deveria falhar); **`Sound.file(corrompido).volume(0.5)` + `play` termina em `Aborted(segmentation fault)`**. Confirma a previsão da revisão estática: o leitor nulo é desreferenciado pelos leitores de efeito. Os casos `.length` e `.specs` não chegaram a rodar (o abort veio antes). Tarefa T3 do Codex.

## 2026-09-20 - Web: revisão do trabalho do Codex (R1, R3, T2) e nova divisão

- Branches lidas por diff, sem integrar: `codex/r1-constraint-abi` (`9ff97884`) e `codex/r3-audio-m3-tests` (`7544073e`).
- **R1:** `grep` de `kwds` só em `createConstraint`; `python -S tools/tests/constraint_abi_test.py` deu
  `CONSTRAINT_ABI_STATIC_TEST: PASS (31 methods)`. Sem `-S` o guard falha com `NameError: EXP_PyObjectPlus` por causa
  de um pacote `Range` de stubs no `site-packages` desta máquina. Build/execução Web do Codex não foram repetidos.
- **R3:** não compilado pelo Codex e revisado só estaticamente: `createReader()` passa a poder devolver nulo no Web, e
  `AUD_Sound_getSpecs`/`getLength`, `Sound.write`/`specs`/`length` (PySound) e `AUD_Special` o desreferenciam sem checar,
  assim como leitores de efeito que chamam `reader->getSpecs()` no construtor. Risco de trocar abort por exceção em
  segfault por nulo com arquivo inválido; não reproduzido (falta build). R3 segue **aberto**, tarefa T3.
- **T2:** sondas M3 do Codex rodaram no runtime antigo (sem `offScreenSize`); a medição numérica está na entrada do
  resize do bloom acima. Suíte `tools/tests/web_profile`: 98 testes OK nesta branch.
- Documentos atualizados: plano (status, divisão e handoff da rodada 2), roadmap e esta entrada. Nova divisão:
  Claude integra e recompila depois do OK do usuário; Codex faz T3 (fechar R3), T4 (guard do R1) e T5 (ferramenta de
  medição p50/p95).

## 2026-09-20 - Web: lacuna do M1 (BL_Shader com stage "?") ja estava fechada

- Reexecutado o teste de `criar_m1c.py` + `shader_quebrado.py` contra o `build-web` atual (Edge headless isolado,
  `verify-package.cjs` com `PREFLIGHT_OUT`): o relatorio traz `diagnostics[]` e `shader_errors[]` com `stage` "vertex",
  `operation` "compile", log do compilador completo e `structured: true`. O `stage "?"` da entrada anterior vinha de um
  runtime anterior ao commit `54c15f9e` (diagnosticos estruturados para `RAS_Shader`).
- Resta: o campo `material`/`origin` sai como o nome generico `engine-shader` (`RAS_Shader::m_diagnosticName`; filtros 2D usam
  `2d-filter`). Nao ha o nome do material do Blender; melhoria pequena, nao feita. Link e materiais de nos continuam sem teste.

## 2026-09-20 - Web: R3 audio sem excecoes e sondas M3 no navegador

- **R3, causa e correcao:** o runtime Wasm e compilado sem unwinding C++; portanto um `AUD_THROW` de arquivo/codec
  invalido aborta o processo antes dos `catch(Exception&)` historicos. No Web, `FileManager` devolve leitor nulo
  quando nenhum decoder aceita o arquivo, e o leitor WAV devolve nulo para arquivo ausente ou formato desconhecido.
  `SoftwareDevice::play` rejeita leitor/som nulo antes de criar os wrappers. Tambem foi protegido o binding C
  `AUD_Device`: ausencia de device (falha/indisponibilidade do backend) e device sem `I3DDevice` nao podem mais
  desreferenciar nulo; getters devolvem sentinelas e setters sao no-op. Isso nao habilita audio 3D nem OpenAL.
- **Limite R3:** RIFF/WAV malformado ainda percorre validacoes antigas que usam `AUD_THROW`; o caso completo precisa
  converter essas validacoes para retorno de erro antes de poder afirmar cobertura de todo arquivo corrompido.
  A configuracao de um build Web limpo desta worktree foi iniciada, mas nao terminou dentro da janela; nenhum build
  em `D:/AnastacioEngine-claude-rna/build-web` foi alterado. A compilacao/runtime desta correcao fica pendente.
- **Sondas M3 novas:** `criar_m3_bloom_resize.py`/`m3_bloom_resize.py` geram uma cena que chama
  `changeBloomValues` e `render.setWindowSize(320,240)` e `(960,540)`; `criar_m3_dynamic_resolution_no_timer.py`/
  `m3_dynamic_resolution_no_timer.py` geram a cena com escala dinamica 50--100% por 180 frames. Ambas foram
  empacotadas com `package-web.py --runtime-dir D:/AnastacioEngine-claude-rna/build-web/bin` somente em leitura,
  servidas em portas 8797/8798 e executadas por `verify-package.cjs` no Edge headless isolado (CDP 9347/9348).
  Resize terminou com `RESULTADO OK`, sem abort/excecao; a sonda de escala emitiu uma vez
  `dynamic resolution needs a GPU timer query ... render scale is not adjusted`, confirmando o caminho sem subida.
  O runtime fornecido ainda nao tinha o trace `offScreenSize`, portanto nao houve medicao numerica dos sete
  offscreens nem afirmacao de `glError=0`; a instrumentacao reservada em `RAS_2DFilter.cpp` continua necessaria.

## 2026-09-20 - Web: M3, correcoes de base dos filtros 2D (indice, resize do bloom, timer de GPU)

- **Colisao de indice**: `reservedPassIndex` era 17 e `FILTERPASS_LENSFLARE` tambem, entao o filtro customizado de
  indice 0 caia no slot do Lens Flare. Agora `reservedPassIndex = FILTERPASS_LENSFLARE + 1`. Teste no runtime Web
  (`m3_filtros.py` + `criar_m3.py`, Edge isolado, Lens Flare ligado): antes (`build-web-release`, anterior ao fix)
  `addFilter(0)` falhava com "found existing filter in index (0)", `removeFilter(-1)` era aceito e
  `removeFilter(0)` apagava o Lens Flare; depois (`build-web`) os quatro checks passam. `removeFilter` com indice
  negativo agora levanta `ValueError` (o `unsigned` dava wrap para 16, o filtro Clouds).
- **Resize do bloom**: os 7 offscreens do bloom eram criados uma vez com o tamanho do canvas / `lod`. Agora usam a
  flag interna `RAS_CANVAS_DIVISOR` (`RAS_2DFilterOffScreen::Update` recalcula e recria), e um callback
  (`KX_2DFilterManager::RefreshBloomTextures`) reaplica os bind codes nos filtros que amostram essas texturas
  (`KX_2DFilter::UpdateTextureBindCode`). **Verificado em runtime Web** (`claude_m3_resize.py`/`claude_m3_criar.py`/
  `claude_m3_resize.cjs`, Edge headless isolado, debug `RAS_2DFILTER_DEBUG` com o novo campo `offScreenSize`): bloom ligado
  via `changeBloomValues` e `render.setWindowSize` 1280x720 -> 640x360 -> 1024x600 -> 400x300 -> 960x540; os offscreens do
  bloom seguem canvas/2, /4 e /8 em cada tamanho (ex. 1024x600 -> 512x300, 256x150, 128x75) e `glError=0x0` em todas as
  ~860 linhas de debug. Igual em `build-web` e `build-web-release`. Nao comparado com o build anterior ao fix (nao se sabe
  se o bug antigo era reproduzivel neste cenario).
- **Timer de GPU**: na Web o query `TIME` nao tem objeto GL, `Available()` dava true e o resultado era 0, o que subia
  a resolucao dinamica ate o maximo. `RAS_Query::IsSupported()` novo; `UpdateDynamicResolution` nao ajusta a escala
  sem timer (avisa uma vez) e descarta amostras <= 0. Testado no mesmo pacote (resolucao dinamica ligada, alvo 60 fps, 50-100%): o aviso "dynamic resolution needs a GPU timer"
  sai uma unica vez e os offscreens ficam no tamanho cheio. Limite: a escala nasce em 100% (o maximo), entao o defeito antigo
  (subir a escala com resultado 0) nao e observavel neste cenario; o teste confirma o caminho novo, nao a regressao.
- Builds: nativo (143/143) e `build-web` (139/139) com codigo 0. `build-web-release` reconstruido depois (163/163, codigo 0) e o teste de resize repetido nele com o mesmo resultado.
- **Nao feito**: selecao do ultimo filtro/blit final (o fluxo ja esta correto, so custa um blit; e otimizacao para o M4),
  medicoes em desktop e celular fisico, tabela de p50/p95 e decisao sobre o M4.

## 2026-09-20 - Web: M2, DNA `unsigned char` e checagem de range da RNA reativada no Emscripten

- Cinco campos DNA passam de `char` para `unsigned char` (`ImageUser.fie_ima`, `Material.seed1`/`seed2`,
  `ToolSettings.skgen_subdivision_number`, `ThemeSpace.handle_vertex_size`), e `USE_RNA_RANGE_CHECK` volta a valer
  no Emscripten (`rna_internal.h`). Commits `9d008486` e `dfae0be0`. O hardmax 200/255 da RNA contradizia o tipo `char` do campo (com sinal, valores acima de 127 não cabem);
  o comportamento anterior não foi reproduzido em runtime.
- **SDNA preservado**: o `makesdna` descarta `unsigned`, então o `dna.c` e os offsets gerados são idênticos
  antes (`ed6c1f8f`) e depois. Nativo: `dna.c` 418262 B e offsets 23236 B; wasm32: 414162 B e 22585 B. Os dois
  "depois" batem com o `dna.c` dos diretórios de build.
- **Checagem ativa no Web**: compilando `rna_image.c`/`rna_material.c`/`rna_scene.c`/`rna_userdef.c` com os
  headers anteriores ao M2 a checagem dá 7 erros (imagem 1, material 2, cena 1, tema 3 = as 7 propriedades do
  inventário); com o HEAD, 0 erros. O compilador nativo MSVC não define `__STDC_VERSION__ >= 201112L`, então lá a
  checagem nunca rodou nem roda; a cobertura dela é só do Emscripten. Builds completos após os commits: nativo,
  `build-web` e `build-web-release` terminaram com código 0.
- **Roundtrip nativo** (`RangeEngine.exe -b --python`, salvar `.range` e reabrir): `halo.seed` e `halo.flare_seed`
  em 0/1/127/128/255, `fields_per_frame` em 1/2/127/128/200, `etch_subdivision_number` em 1/2/127/128/200/255,
  todos voltaram iguais. `handle_vertex_size` em 0/128/255 nos temas Graph/Image/Clip sobreviveu a salvar e recarregar
  o `userpref.blend`; os temas padrão trazem 5. `userpref.blend` reais do usuário (2.79 do RangeEngine, 2.67 e 2.68)
  carregam sem erro.
- **Animação**: com o material ligado a um objeto, `halo.seed` 200->255 e `flare_seed` 3->250 animam corretamente,
  também depois de salvar e reabrir. Material sem objeto não é reavaliado após o load, igual a `size` e `hardness`
  (não é do M2).
- **Fora da faixa via RNA**: o setter faz clamp e não levanta erro. `seed` 256 vira 255 e -1 vira 0;
  `fields_per_frame` 0 vira 1 e 201 vira 200; `etch_subdivision_number` 0 vira 1 e 256 vira 255;
  `handle_vertex_size` 256 vira 255 e -1 vira 0.
- Treze `.blend`/`.range` do repositório carregam sem erro e com seeds, `fields_per_frame` e subdivisão dentro da
  faixa. Exceção: `preview.blend` traz `etch_subdivision_number` 0, valor já gravado no arquivo (byte 0 é igual
  em `char` e `unsigned char`), fora da faixa 1-255 da RNA.
- **Consumidores revisados**: nenhum depende do sinal. `resources.c::UI_ThemeGetColorPtr` já usava
  `unsigned char *`, e o `hashvectf + ma->seed2` de `rendercore.c` deixa de indexar negativo para seed > 127.
  O cast `(char)tex->fie_ima` em `versioning_legacy.c:2471` é inofensivo (o legado grava 2) e foi mantido.
- **Não coberto**: um build nativo com a checagem ativa não existe (o MSVC não a executa); os `.blend` legados só
  provam carregamento e valores, não o comportamento anterior ao M2 com valores acima de 127. O
  `build-web-release` tem 49 passos pendentes por `GPU_shader.h` (alterado no M1, não no M2), então deve ser
  reconstruído antes de qualquer publicação.

## 2026-09-20 - Web/R1: ABI dos callbacks Python de constraints

- Inventário executado de `physicsconstraints_methods`: 31 registros (30 `METH_VARARGS`, um
  `METH_VARARGS | METH_KEYWORDS`, nenhum `METH_NOARGS`). Vinte e oito callbacks `METH_VARARGS`
  tinham a assinatura de três parâmetros; `gPyCreateVehicle` e `gPyExportBulletFile` já tinham
  dois, e `gPyCreateConstraint` já estava correto com três e `METH_KEYWORDS`.
- Em `KX_PyConstraintBinding.cpp`, removido o parâmetro `kwds` das 28 funções `METH_VARARGS`.
  As flags não mudaram: setters continuam posicionais e `createConstraint` conserva a API de
  keywords existente.
- Novo `tools/tests/constraint_abi_test.py`: guarda estática das 31 assinaturas/flags e cena
  Python que cobre argumentos válidos e inválidos dos setters, rejeição de keyword em
  `setGravity` e aridades inválidas das demais APIs expostas.
- Antes da correção, a cena passou no `RangeRuntime` nativo em Windows x64: a incompatibilidade
  ABI não se reproduziu nessa plataforma. Após a correção, o mesmo teste passou nativamente.
- Executados com sucesso: `cmake --build --preset web-runtime` (1817 etapas),
  `package-web.py` para a cena de regressão e execução Web em Chrome headless/WebGL2 via CDP;
  o log da cena correta registrou `CONSTRAINT_ABI_TEST: PASS`. O pacote usou runtime de
  depuração (`SAFE_HEAP`/`ASSERTIONS`), somente para validação.

## 2026-09-20 - Web: testes de runtime do M1 (diagnósticos Python e shader)

- Três jogos com falha injetada foram empacotados com `package-web.py --runtime-dir build-web/bin`, servidos e
  executados no Edge via `verify-package.cjs` com `PREFLIGHT_OUT`. `check_preflight` emitiu apenas o achado
  esperado em cada um: exceção Python -> `WEB-PY-009`, import inexistente -> `WEB-PY-001`, GLSL inválido em
  Filter2D (`mode = CUSTOMFILTER`) -> `WEB-GFX-002`, todos ERROR.
- Segunda rodada (mesmo método): `SyntaxError` no controller -> `WEB-PY-009`; mensagem com aspas, quebra de linha,
  Unicode (acentos e japonês) e 3000 caracteres chegou íntegra ao relatório (3028 caracteres, sem truncar);
  o mesmo erro em 3 objetos gerou 3 eventos distintos.
- Terceira rodada: exceção em `start()` de componente Python (`KX_PythonComponent`) e em callback `pre_draw`
  geraram evento `python` com `exception_type` RuntimeError e traceback -> `WEB-PY-009` ERROR (o callback repete
  o evento a cada frame).
- Importação de relatório por arquivo (`load_preflight`, sem bpy): versão 1 e 2 são lidas (`WEB-PY-009` com
  `python_errors`); versão 3, ausente ou não numérica degrada para um único `WEB-DEPLOY-002`. Os 30 testes
  `test_preflight*` passam.
- Importação pela UI do editor (roteiro `projects-teste/teste-editor-web/ROTEIRO-M1.md`, passos A.1 a A.6, feitos pelo
  usuário): versão 1 e 2 mostram `WEB-PY-009`; versão 3 mostra um único `WEB-DEPLOY-002`; importar `pf-ok.json`
  limpa os resultados do pré-voo anterior. Resultado importado não tem **Locate** (o `origin` é só texto).
  Um build antigo (só versão 1) rejeitava a versão 2: abrir o `RangeEngine.exe` da worktree.
- Painel Web: mensagem e traceback com quebras de linha apareciam como quadrados; agora uma linha por label
  (`properties_web.py`). Ainda não conferido visualmente.
- Execução sem pré-voo testada pelo usuário no navegador: export com "Preflight after export" desligado, página
  aberta sem `?preflight=1`, jogo renderizou e o console mostrou só avisos habituais (emulação GL, ScriptProcessorNode),
  sem erro. Achado: nome de arquivo com espaço (`melhores graficos .range`) é recusado no export
  ("nome do arquivo do jogo invalido para o FS virtual"); o editor só reporta isso na falha do empacotador.
- Bug achado pelo usuário: component em `scripts/` (módulo `scripts.cinematic_lighting_component`) virava
  WEB-PKG-003 "Módulo não foi encontrado: scripts". O coletor tratava `comp.module` como "modulo.funcao" e cortava o
  último segmento; corrigido com `is_module=True` em `collect_bpy.py`, com teste em `test_collect.py`. Ainda não
  reconferido no editor.
- Falha de vertex de `BL_Shader` testada em runtime (`criar_m1c.py` + `shader_quebrado.py`, headless): o log chega ao relatório e vira `WEB-GFX-002`, mas pelo fallback de texto do console: `stage` "?" e `material` vazio, porque o `GPUShader: compile error:` não passa por `Module.onDiagnostic`. Lacuna aberta: emitir diagnóstico estruturado (estágio e material) no caminho `GPUShader`/`BL_Shader`. Link e materiais de nós não testados.
- O runtime usado era build de depuração (SAFE_HEAP/ASSERTIONS); serve para o teste, não para publicar.

## 2026-09-20 - Web: estado do M0 e checkpoint de diagnóstico estruturado de shader

- M0 no commit `1c9d1562`: `make-runtime-manifest.py` declara o alias `bge` e `aud` conforme
  `WITH_AUDASPACE`; o pré-voo requer WebGL 2 e torna abort, falha e inicialização incompleta estados
  explícitos. `package-web.py` deixa de ocultar erro de leitura do manifesto. A suite Web Profile passou com
  83 testes; falta exportar e executar pacote Web real.
- Checkpoint parcial de M1 no commit `8251b0dc`: `gpu_shader.c` chama `Module.onDiagnostic` em falha de
  compilação/link WebGL, com operação, estágio, origem e log. `GPU_generate_pass` preserva o nome de
  material/world para essa origem. O coletor do pacote exporta relatório v2 e usa a heurística antiga só como
  fallback; o leitor aceita v1 e v2. Testes de `test_preflight` (11), `py_compile` e `git diff --check` passaram.
- Não concluído: captura segura de exceções Python, shaders especiais/filtros e validação em navegador.
  A tentativa de build não vale como validação porque `build-android` da worktree apontava para a árvore
  principal; o próximo agente deve configurar build Web limpo da própria worktree.

## 2026-09-20 - Web: gamepad — sensores de joystick avaliam pelo estado vivo do SDL

- Sintoma (teste do patch do SDL2 no navegador): o D-pad exigia vários toques e, quando respondia, o cubo ficava
  girando sem parar. O monitor `navigator.getGamepads()` injetado numa cópia do pacote mostrou que o navegador
  entregava tudo certo (mapeamento "Standard Gamepad", eixo 0 em rampa e voltando a 0, `timestamp` avançando),
  então o patch do SDL2 não era a causa.
- Causa raiz: `SCA_JoystickSensor` só avalia quando `DEV_Joystick::IsTrigAxis()`/`IsTrigButton()` estão ligados, e
  essas flags só subiam ao consumir um evento SDL em `HandleEvents`. No Web o `SDL_PollEvent` do GHOST drena esses
  eventos antes (mesma raiz da fila compartilhada das entradas de 2026-09-14): evento de apertar perdido = vários
  toques; evento de soltar perdido = sensor nunca vê a soltura. A correção de 14/09 só trocou a leitura do valor
  (`SDL_GameControllerGetAxis`), o gate por evento ficou.
- Fix (`DEV_JoystickEvents.cpp`, `DEV_Joystick.h/.cpp`): `SyncLiveState()` compara eixos e botões vivos do SDL com
  o quadro anterior ao fim de `HandleEvents` e liga as flags mesmo sem evento. Semântica nativa inalterada.
- Confirmado pelo usuário com controle físico no navegador (runtime `build-web-release` religado). Regressão geral
  (render, sombras, teclado, console sem erro vermelho), World Status no editor, export Web e idioma também
  aceitos. Save (IDBFS) validado com o pacote `projects-teste/teste-save-web` (SAVED, recarregar, LOADED),
  automático (`verify-save.cjs`) e manual pelo usuário.
- Segundo controle ("USB Joystick", vendor 0079 produto 0006) chega ao navegador com `mapping=""`,
  12 botões, 10 eixos e D-pad como hat no eixo 9 (repouso 3.29). O SDL pode não mapear o hat sem uma entrada no
  banco de controles. Testado pelo usuário: o D-pad desse controle funciona igual, nenhum mapeamento necessário.

## 2026-09-20 - Web: patch do SDL2 (gamepad) versionado

- Novo `tools/web/patch-sdl2-gamepad.py`: aplica no cache do emsdk (SDL 2.32.10,
  `src/joystick/emscripten/SDL_sysjoystick.c`) a remoção do gate `gamepadState.timestamp != item->timestamp`.
  Idempotente (marcador no fonte), preserva o EOL, `--check` informa o estado, apaga `libSDL2*.a` para forçar a
  recompilação da porta. Só a correção entra; os `printf [web-input]` de diagnóstico da época não foram mantidos.
- Testado num emsdk falso a partir do arquivo original do zip da porta (diff de 5 linhas). No emsdk real:
  arquivo restaurado do zip, patch aplicado e `embuilder build sdl2` recompilou `libSDL2.a` sem erro.
- Ligado ao build: `source/build_files/cmake/platform/platform_web.cmake` roda o script a cada configure (avisa
  se falhar). `RangeRuntime` (preset `web-runtime-release`) relinkado com a porta recompilada sem erro; o cache de
  `build-web-release` e `build-web` estavam com `WITH_INTERNATIONAL=ON` (divergia do preset) e foram realinhados para OFF.
- Não verificado: gamepad físico no navegador com o novo `RangeRuntime`.

## 2026-09-20 - Idioma: English + Português (i18n do editor)

- O editor passa a compilar com `WITH_INTERNATIONAL`: o submódulo `locale` do Blender 2.79 não existia e o
  CMake desligava a opção sozinho (o alvo `msgfmt` sumia do Ninja). Vendorizado só o necessário em
  `source/release/datafiles/locale` (`po/pt_BR.po`, `po/pt.po` e um `languages` reduzido a Default/English/pt_BR/pt_PT;
  origem e commit em `locale/README.md`, branch `blender-v2.79-release` de `blender/blender-translations`). O
  menu de idioma lista só o que existe.
- Correções que o i18n ligado expôs: `interface_style.c` ainda usava `datatoc_bfont_ttf`/`bmonofont` (fontes trocadas
  por Roboto neste fork) → agora `roboto_medium`/`roboto_mono_medium`; o `install()` gravava o catálogo como
  `RangeEngine.mo` mas o código carrega o domínio `blender` (`TEXT_DOMAIN_NAME`) → `RENAME blender.mo`;
  `blenderplayer/.../stubs.c` duplicava `BPY_app_translations_py_pgettext` (guardado com `#ifndef WITH_BLENDER`, como
  os demais).
- Presets: `WITH_INTERNATIONAL` explícito (`ON` em `linux-editor`; `OFF` em `linux-runtime`, `android-runtime` e
  `web-runtime`, que não têm editor e evitam exigir Boost).
- Painel Web: textos em inglês (idioma-fonte); pt_BR em `range_web/translations.py`, registrado em `bl_ui.register()`.
  Módulos puros usam `range_web/i18n.py` (`_()` traduz no editor, devolve o texto fora dele). `_open_in_browser` agora
  devolve `(ok, mensagem)` em vez de o operador testar o começo do texto.
- Espanhol (`es`) e russo (`ru_RU`) adicionados ao menu: `po/es.po`, `po/ru.po` (mesmo commit) e `range_web/translations_es_ru.py`; coberto por `engine_i18n.py`.
- Textos de UI da Range/UPBGE fora do catálogo do Blender (1 459 rótulos e dicas de RNA) traduzidos em pt_BR/es/ru_RU em `range_web/translations_ui.py`; auditoria por `tools/tests/web_profile/i18n_audit.py` (pt_BR: 2 698 → 1 281 sem tradução, o resto é ícone, identificador ou nome igual nos dois idiomas; ru tem mais lacunas no catálogo do Blender).
- Testes: 78 unitários OK (asserções de texto atualizadas); `engine_i18n.py` novo (13 verificações: catálogo do Blender,
  dicionário `range_web`, dica, formato `%s`, acentos, desligar tradução); os 5 `engine_*` existentes passam.
- Padrão do Blender 2.79 mantido: tradução vem desligada (Preferências > System > **International Fonts**, depois
  **Language** e **Interface**).
- Não verificado: desenho na janela real (fonte Droid Sans, acentos, menu de idioma) e o Linux.
- Fora desta entrega: mensagens das regras (`rules_*.py`, `runtime.py`, `manifest.py`, `collect.py`, `preflight.py`) ainda em
  português; o export.py/results só traduzem o que já era texto de interface.

## 2026-09-20 - Web: "Abrir no navegador" com um clique

- Novo botão **Abrir no navegador** (servidor local em thread daemon, porta livre, `range_web/local_server.py`),
  **Parar servidor**, linha de estado e opção **Abrir após exportar**. Botões de servir e de pré-voo usam `poll`
  e mostram o motivo no painel quando o ambiente não está pronto (sem pacote, pacote desatualizado, sem
  Chrome/Edge). `serve.py` do pacote aceita porta 0. Testes: `test_local_server.py` (78 unitários OK) e
  `engine_web_serve.py`. O pré-voo mantém seu servidor próprio, de propósito.

## 2026-09-20 - Web: fluxo do editor aceito pelo usuário

- Teste manual no editor concluído (Validar, Exportar Web, Testar pacote no navegador, Importar pré-voo, bloqueio
  por erro e Localizar): passou. Marco E fechado; o item saiu do roadmap.

## 2026-09-20 - docs: celular confirmado e roteiro do teste no editor

- Deploy no GitHub Pages confirmado pelo usuário também no celular. Roadmap e `web-deploy.md` atualizados; o item
  "Deploy real" saiu dos abertos. Roteiro do teste manual do fluxo no editor em
  `projects-teste/teste-editor-web/LEIA-ME.md` (com `editor-web-teste.range`).

## 2026-09-20 - docs: roadmap reconciliado com o git log

- `docs/roadmap.md` reescrito só com pendências reais (de 526 para cerca de 140 linhas). A narrativa histórica
  do bloco Web (bloqueios de shader/GL, causas raiz de teclado/mouse/gamepad, IDBFS, cena de filtros) já estava
  nas entradas de 2026-09-12 a 2026-09-18 deste changelog e foi removida do roadmap. Marco D e pré-voo saíram
  da lista de abertos; o item FFmpeg do editor Linux continua aberto (só o wrapper audaspace foi ajustado). Aceites manuais do usuário no mesmo dia (cutscene Play/Stop/Play e standalone, sombras, migração de `maxphystep`, Sol/Lens Flare, resolução dinâmica, splash/About, Outliner, barra da 3D View, Particles, gamepad ImGui, sensores/actuators de física) removidos das pendências.
