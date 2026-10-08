# Plano de migração: RangeEngine.exe → AnastacioEngine.exe

Data: 2026-10-07. Estado: levantamento e plano; nenhuma renomeação implementada.

## 1. Objetivo e decisões de escopo

O objetivo solicitado é entregar o editor Windows como `AnastacioEngine.exe`, com todos os fluxos de abertura, exportação e distribuição funcionando. A mudança é viável, mas deve acontecer no build e nos consumidores do executável, não somente por renomeação manual do arquivo pronto.

Proposta de escopo para a primeira entrega:

| Identificador atual | Destino proposto | Tratamento |
|---|---|---|
| `RangeEngine.exe` | `AnastacioEngine.exe` | Obrigatório: editor Windows e referências ao arquivo/processo. |
| Alvo CMake/Ninja `RangeEngine` | `RangeEngine` | Preservar inicialmente; definir `OUTPUT_NAME` no Windows. O alvo interno pode produzir um arquivo com outro nome. |
| `RangeRuntime.exe` | `RangeRuntime.exe` | Preservar na primeira etapa. Renomear para `AnastacioRuntime.exe` é uma segunda migração, descrita abaixo. |
| `RangeArmor Panel.exe`, pasta `rangearmor/`, ZIP `RangeArmor-*` | Mesmos nomes inicialmente | Adaptar integração com o editor novo. Rebatizar a ferramenta para AnastacioArmor é uma decisão separada. |
| `.range`, `.blend`, `.rasec`, `.bgeconf`, APIs `Range`/`bge` | Mesmos nomes | Preservar arquivos, scripts e jogos existentes. |
| ProgIDs `RangeEngine.BlendFile` e `RangeEngine.RangeFile` | Mesmos nomes | Atualizar os caminhos dos comandos/ícones, preservando os identificadores do Registro. |
| Diretórios de configuração herdados `RangeEngine` | Mesmos nomes | Preservar preferências. O código Windows inclui `RangeEngine/Blender/`; não assumir apenas a pasta indicada informalmente. |
| Linux `RangeEngine` e bundles macOS | Mesmos nomes inicialmente | Expansão multiplataforma em fase própria. |

Este plano registra a migração solicitada como exceção à preservação do nome do executável em `AGENTS.md`. Não autoriza uma substituição global de toda ocorrência de “Range”. Créditos e licenças dos projetos originais permanecem.

## 2. Mudanças obrigatórias confirmadas no código

| Arquivo | Dependência encontrada | Ação planejada |
|---|---|---|
| `source/source/creator/CMakeLists.txt` | Criação, assinatura, instalação e comandos pós-build do alvo `RangeEngine`. | Aplicar `OUTPUT_NAME AnastacioEngine` ao executável Windows, depois de sua criação; revisar comandos com caminhos literais e preferir `$<TARGET_FILE:RangeEngine>`. Preservar o ramo de módulo Python. |
| `source/release/windows/icons/winblender.rc` | `OriginalFilename` contém `RangeEngine.exe`. | Atualizar para o nome novo; conferir descrição, produto, ícones e se o recurso é compartilhado com o player antes de alterar valores comuns. |
| `source/intern/ghost/intern/GHOST_SystemWin32.cpp` | `isStartedFromCommandPrompt()` reconhece o processo pai por `strstr(filename, "RangeEngine.exe")`. | Reconhecer o nome novo e o legado durante transição, com comparação do nome completo sem distinguir maiúsculas/minúsculas. Testar console ao lançar o player pelo editor. |
| `source/release/scripts/startup/bl_operators/wm.py` | A abertura da RangeArmor usa `bpy.app.binary_path[:-15] + "rangearmor\\RangeArmor Panel.exe"`. | Substituir o corte fixo pelo diretório do executável e `os.path.join`. O novo nome tem outro comprimento: o corte atual produz um caminho incorreto. |
| `source/source/blender/blenlib/intern/winstuff.c` | Associação usa caminho do editor e constrói o caminho fixo do player. | Verificar que `-r/-R` registra `AnastacioEngine.exe` e seu ícone; conservar o player atual e os ProgIDs. Validar remoção `-u/-U`, HKCU e HKLM. |
| `source/intern/ghost/intern/GHOST_WindowWin32.cpp` | Referências a `RangeEngine.ico` e `RangeRuntime.ico`. | Verificar a origem/carga dos ícones. Nome de recurso não precisa acompanhar nome do executável; alterar somente se o carregamento ou pacote exigir. |

A propriedade `OUTPUT_NAME` evita alterar todas as dependências, bibliotecas, testes e comandos que usam o alvo CMake. `project(RangeEngine)` em `source/CMakeLists.txt`, `VS_STARTUP_PROJECT`, `openmp_delayload(RangeEngine)` e expressões `$<TARGET_FILE:RangeEngine>` podem continuar válidos. Não editar manualmente `build.ninja`, caches ou arquivos gerados: reconfigurar pelo CMake.

## 3. RangeArmor: integração e limite do levantamento

Confirmado: `tools/RangeArmor-master/` está ignorado pelo Git e **não existe neste checkout**, mas seu fonte está disponível no histórico, no commit `69df19d9`. Houve leitura direta desse snapshot com `git show`; antes de implementar, recuperar a versão local em diretório isolado e comparar com a ferramenta realmente distribuída. Preservar as adaptações locais.

### Integração existente na engine

Em `source/release/scripts/startup/bl_operators/wm.py`, revisar conjuntamente:

- `WM_OT_export_with_rangearmor`: corrigir o corte `[:-15]` e testar abertura do painel a partir de um diretório com espaços.
- `_rangearmor_write_export_preset`: conferir os dados que entrega ao painel e os caminhos derivados do editor.
- `_RANGEARMOR_DEFAULT_FIELDS`: conservar as chaves e os caminhos `EngineWindows64`/`EngineLinux64` se o player continuar com o nome atual.
- `_rangearmor_scaffold_project`: validar criação de projeto, cópia de templates e projetos preexistentes.
- `_rangearmor_ensure_launcher_template_fresh`: conferir fonte Rust, binário template e binário efetivamente copiado; o mecanismo atual não atualiza automaticamente todo launcher já existente em projetos antigos.
- `_rangearmor_ensure_launcher_script`: conferir o `launcher.py` copiado para o projeto e evitar trocar scripts personalizados silenciosamente.
- `WM_OT_one_click_export_rangearmor`: validar resolução de Python, `get_rangeengine_currentplatform.py`, `build_release.py` e descoberta de runtimes em `engine/Windows64` e `engine/Linux64`.

### Auditoria necessária no projeto externo

Obter a versão fonte correspondente ao pacote distribuído e registrar versão/commit e eventuais patches locais antes de modificá-la. Procurar `RangeEngine.exe`, `RangeEngine`, `RangeRuntime`, cortes numéricos de caminho, downloads, descoberta de instalação e nomes de processos.

| Componente externo | Verificação/mudança necessária |
|---|---|
| Painel Godot, incluindo `editor.gd` mencionado pela integração | Detecção do editor instalado, caminhos de Python, diálogo de seleção e botão “Get RanGE”. Atualizar referências ao editor e aceitar instalação antiga durante transição. |
| `release/scripts/get_rangeengine_currentplatform.py` | Conferir como encontra/copia a engine e distingue Windows64/Linux64. O nome do script pode continuar herdado; seu conteúdo precisa aceitar o editor novo. |
| `release/scripts/build_release.py` | Conferir filtros de cópia, listas de executáveis e nomes esperados no pacote. |
| `release/launcher/launcher.py` e `source/launcher/src/main.rs` | Conferir se executam apenas o player ou também procuram o editor. Recompilar Rust somente se houver alteração efetiva no launcher. |
| Templates e `launcher/config.json` | Preservar configurações existentes; migrar apenas caminhos padrão conhecidos quando necessário, com backup. |
| Artefatos do painel e launcher Windows/Linux | Gerar a partir do fonte auditado, comparar com os templates e testar um projeto novo e um antigo. |

O histórico de 2026-09-08 registra `RANGEARMOR_ENGINE_DIR`, `RANGEARMOR_ENGINE_DIR_WINDOWS64` e `RANGEARMOR_ENGINE_DIR_LINUX64`, cópia das duas plataformas e passagem de caminho absoluto ao runtime. Preservar esses contratos e repetir suas validações quando a ferramenta for adaptada.

### Se também for desejado o nome AnastacioArmor

Essa opção acrescenta: nome/título do painel, preset de exportação Godot, `RangeArmor Panel.exe`, pasta de instalação, botões/mensagens da engine, descoberta de templates, nome do ZIP e instruções de instalação. Manter os IDs de operadores Python e o esquema JSON inicialmente. `Launcher.exe` pode continuar com esse nome e o executável final do jogo continua com o nome escolhido pelo desenvolvedor. Conservar a licença MIT e o crédito BGEmpire Studio. Publicar a ferramenta como asset separado, conforme a distribuição atual.

## 4. Scripts, testes e documentação

A lista completa de ocorrências textuais rastreadas está no [inventário](executable-rename-inventory.md). Ela é um conjunto de candidatos para revisão, não uma lista de substituições automáticas: comentários, histórico e nomes de alvos internos não exigem a mesma ação que um caminho executável.

Prioridades confirmadas para o editor Windows:

- `tools/run_debug_pbr.ps1`, `tools/run_material_atlas_modal_tests.py` e `tools/validate_recipe_nodes.py`: caminhos executados diretamente.
- `tools/net_engine_test/run_net_test_win.sh`: caminho padrão do editor; manter possibilidade de override.
- `source/tests/python/CMakeLists.txt`: verificar os testes; as expressões por alvo devem acompanhar `OUTPUT_NAME` sem renomear o alvo.
- Exemplos e comandos em `tools/create_*.py`, `tools/tests/`, `source/release/scripts/templates_py/` e documentação vigente: atualizar chamadas Windows; não trocar comandos Linux por nomes que ainda não existem.
- `AGENTS.md`, `docs/build-dirs.md`, `docs/build-notes.md`, `docs/distribution-0.1.md`, `docs/windows-file-associations.md`, `docs/maintenance-guide.md`, `docs/README.md`, roadmap e relatório vigente: distinguir nome do arquivo de nome do alvo. Preservar registros históricos e notas de releases antigas.
- `.github/`: conferir workflows e formulários; mudar rótulos visíveis e caminhos de artefatos quando aplicável, conservar comandos por alvo.

## 5. Caso o player também seja renomeado

Proposta de nome: `AnastacioRuntime.exe`; pendente de decisão de escopo. Isso amplia a migração:

| Área | Arquivos/pontos já localizados |
|---|---|
| Build do player | `source/source/blenderplayer/CMakeLists.txt`: `OUTPUT_NAME` restrito ao Windows inicialmente. O CMake do player não fica em `GamePlayer/`. |
| Player externo e exportação | `source/release/scripts/startup/bl_operators/wm.py`, `source/release/scripts/addons/game_engine_save_as_runtime.py`. |
| Cook | `source/release/scripts/startup/bl_operators/anastacio_cook.py`: resolução do player e mensagens. |
| Registro Windows | `winstuff.c`: nome fixo `RangeRuntime.exe` e ícone da associação `.range`. |
| RangeArmor | Campos `EngineWindows64`/`EngineLinux64`, cópia de runtimes, templates, launcher e configurações antigas. |
| Testes/ferramentas | `tools/run_perf_suite.py`, `tools/net_engine_test/`, `tools/tests/`, `tools/validate_recipe_nodes.py` e inventário anexo. |
| Diagnósticos | `source/source/gameengine/GamePlayer/GPG_Ghost.cpp`: logs/diálogos; caminho macOS somente se houver migração daquela plataforma. |

Usar resolução que prefira o player novo e aceite o antigo durante a transição. Não sobrescrever caminhos personalizados em preferências ou `config.json`; conferir se o caminho legado existe antes de propor migração.

**Web/Android:** não aplicar `OUTPUT_NAME` indiscriminadamente ao player. `RangeRuntime.js`, `.wasm`, `.data` e `RangeRuntime.manifest.json` são contratos do pacote Web. Há nomes fixos em `tools/web/package-web.py`, `source/release/scripts/modules/range_web/manifest.py` e comandos pós-build. Renomear esses artefatos exige auditar loader, manifesto, hashes, testes, caches e exportação Android WebView separadamente. O Android NDK permanece congelado.

## 6. Caso o nome novo alcance Linux/macOS

Linux: revisar `source/release/linux/RangeEngine.desktop` (`Exec`), `install-desktop.sh`, `source/release/freedesktop/blender.desktop`, `tools/linux/package-runtime.sh`, `quickstart-editor.sh`, scripts de rede e comandos da documentação. O nome do arquivo `.desktop` e do ícone pode ser preservado inicialmente para evitar duplicar entradas; o `Exec` deve apontar ao binário real.

macOS: auditar bundles, Info.plist, instalação e caminhos em `source/source/creator/CMakeLists.txt`, `source/release/darwin/` e `GPG_Ghost.cpp`. Preservar diretórios de preferências em `GHOST_SystemPathsCocoa.mm` até existir uma migração própria. Não declarar suporte validado sem build e execução nessa plataforma.

## 7. Compatibilidade, distribuição e rollback

- Atalhos, PATH, tarefas agendadas, IDEs, integrações externas e regras de firewall/antivírus podem guardar o caminho antigo. Inventariar os usados pelo projeto e orientar usuários na nota da release; não alterar configurações do sistema silenciosamente.
- Associações antigas continuam apontando ao arquivo antigo até novo registro. Testar re-registro na pasta instalada nova e remover registros apenas da instalação correta; não alterar `UserChoice` à força.
- Decidir se uma release de transição precisa de executável legado. Se houver alias, testar argumentos, diretório de trabalho, console, exit code e diferenças de identidade do processo. Uma cópia do binário pode facilitar compatibilidade, mas duplica tamanho e precisa acompanhar cada atualização.
- Preservar `blender.crt/` completo, `ucrtbase.dll`, `2.79/`, complementos e bibliotecas. A renomeação do editor não justifica renomear a assembly `blender.crt`.
- Conferir assinatura, informações de versão, PDBs e manifestos gerados. Preparar staging novo para não incluir `RangeEngine.exe` obsoleto deixado em `build/bin/` pelo build anterior.
- Atualizar checksums somente depois de gerar os novos pacotes. Releases antigas permanecem intactas.
- Rollback: manter commit/build/pacote anteriores e backups de configurações migradas. Restaurar pacote e associações juntos; não misturar scripts novos com executáveis antigos sem validação.

## 8. Sequência de implementação e critérios de aceite

1. **Fechar contrato:** editor Windows obrigatório; registrar escolhas sobre player, plataformas, nome da RangeArmor e alias legado. Recuperar fonte externo se a entrega incluir validação completa dessa ferramenta.
2. **Peça pequena — caminhos:** corrigir o corte fixo da RangeArmor e reconhecimento do processo pai; revisar com o usuário antes da próxima peça, conforme `AGENTS.md`.
3. **Peça pequena — build/editor:** definir nome de saída, atualizar recurso e consumidores Windows. Reconfigurar/compilar no ambiente MSVC via `vcvars64.bat`, sempre com `VSLANG=1033`, na mesma chamada de processo. Executar o editor novo e verificar instalação.
4. **Integração:** testar abrir/salvar projeto antigo, player embutido, player externo, console, Export Game, Cook e exportação Steam/LAN. Confirmar que preferências e scripts existentes continuam carregando.
5. **RangeArmor:** aplicar alterações identificadas no fonte externo, gerar templates necessários, abrir painel pelo editor novo, copiar runtimes e exportar projetos novo/antigo. Extrair e executar os jogos Windows e Linux quando essas saídas forem entregues.
6. **Distribuição:** ler novamente `docs/distribution-0.1.md` inteiro, gerar staging limpo, ZIP com caminhos `/`, extrair em pasta com espaços fora do build e executar editor/player/jogo exportado. Validar DLLs, CRT, licenças, ícones e associações. Testar ambiente sem Visual Studio.
7. **Documentação:** atualizar estado vigente e registrar implementação no topo do changelog, sem reescrever história. Executar `python tools/check_docs.py`; publicar somente depois dos critérios locais e manuais aplicáveis.

Critérios de aceite: `AnastacioEngine.exe` é produzido e instalado pelo build; abre projetos existentes; inicia player e painel pelos comandos da UI; exportações funcionam; Registro aponta ao editor novo; pacote extraído executa; preferências e APIs permanecem compatíveis. RangeArmor só recebe estado “validada” após teste com a ferramenta real. Qualquer plataforma não executada deve constar como pendente.

## 9. Estado deste relatório

Foi realizada inspeção estática do checkout e das entradas relevantes do changelog. Não houve alteração de C++, scripts de produto, executáveis ou Registro, nem build: a entrega solicitada é o plano. O inventário cobre arquivos rastreados e inclui separadamente o Cook ainda não rastreado; não cobre fontes externas ausentes, binários, configurações pessoais ou integrações fora deste repositório. A implementação permanece aberta.


## 10. Complemento: fonte da RangeArmor localizado no Git

Corre??o do levantamento inicial em 2026-10-07: `git log --all -- tools/RangeArmor-master` e `git ls-tree -r 69df19d9 -- tools/RangeArmor-master` confirmaram o snapshot. Foi feita leitura direta com `git show` e busca com `git grep`, sem restaurar arquivos nem alterar o ?ndice.

Achados confirmados no snapshot `69df19d9`:

- `release/scripts/get_rangeengine_currentplatform.py`: tabela `PLATFORMS` exige `RangeRuntime.exe` e `RangeRuntime`; a valida??o e a c?pia dependem desses nomes. Se apenas o editor mudar, esses contratos continuam v?lidos. A c?pia leva a pasta da instala??o, portanto conferir tamb?m o editor novo eventualmente copiado e filtros de distribui??o.
- `source/launcher/src/main.rs`: o launcher l? `Engine<plataforma>` do JSON e executa esse caminho com `Command::new(&engine)`. O nome do editor n?o ? uma depend?ncia literal nesse fluxo; renomear o player exige atualizar configura??o/c?pia, e n?o necessariamente mudar a l?gica de execu??o Rust.
- `source/gui-rs/src/project.rs`: padr?es Windows/Linux usam `RangeRuntime`; inclui campos legados 32-bit. N?o confundir exist?ncia desses campos com suporte atual a exporta??es 32-bit.
- `source/gui-rs/src/screens/editor.rs`: mensagens e testes referem-se ao player; incluir essa interface na auditoria, al?m de `scenes/editor.gd`.
- `source/gui-rs/Cargo.toml`: metadado `CompanyName = "RangeEngine"`; revisar se a marca da ferramenta tamb?m for alterada.
- `source/launcher.py`, `release/scripts/build_release.py`, `release/scripts/common.py`, `scenes/editor.gd`, `export_presets.cfg` e `project.godot`: fontes dispon?veis para completar auditoria de templates, painel e empacotamento.

O upstream p?blico tamb?m existe em https://github.com/rangeengine/RangeArmor, mas o snapshot local cont?m adapta??es AnastacioEngine e deve ter prioridade para preservar o trabalho j? realizado. Fonte recuper?vel n?o comprova que os bin?rios distribu?dos foram gerados desse exato snapshot; essa confer?ncia permanece necess?ria.
