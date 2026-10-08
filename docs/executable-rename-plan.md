# Plano de migração: RangeEngine.exe → AnastacioEngine.exe

Plano de 2026-10-07, atualizado em 2026-10-08: renomeação do editor Windows implementada;
segunda etapa do player Windows autorizada pelo usuário e validada localmente (seção 14).
Build e execução local passaram; validações e limites da entrega estão na seção 9.

## 1. Objetivo e decisões de escopo

O objetivo solicitado é entregar o editor Windows como `AnastacioEngine.exe`, com todos os fluxos de abertura, exportação e distribuição funcionando. A mudança é viável, mas deve acontecer no build e nos consumidores do executável, não somente por renomeação manual do arquivo pronto.

Proposta de escopo para a primeira entrega:

| Identificador atual | Destino proposto | Tratamento |
|---|---|---|
| `RangeEngine.exe` | `AnastacioEngine.exe` | Obrigatório: editor Windows e referências ao arquivo/processo. |
| Alvo CMake/Ninja `RangeEngine` | `RangeEngine` | Preservar inicialmente; definir `OUTPUT_NAME` no Windows. O alvo interno pode produzir um arquivo com outro nome. |
| `RangeRuntime.exe` | `AnastacioRuntime.exe` | Segunda etapa Windows autorizada em 2026-10-08; nome legado aceito na leitura de projetos. |
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

O fonte foi localizado no commit `69df19d9` e recuperado para `tools/rangearmor/` em 2026-10-08,
fora do caminho ignorado `tools/RangeArmor-master/`. Os scripts instalados diferiam do snapshot;
foram preservados em backup antes da integração inicial do cooking e atualização do launcher.
O estado dessa frente está no [plano de atualização](rangearmor-update-plan.md).

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

Nome aprovado em 2026-10-08: `AnastacioRuntime.exe`, somente Windows. Isso amplia a migração:

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

Renomeação inicial implementada em 2026-10-08:

- Alvo CMake `RangeEngine` produz `AnastacioEngine.exe` somente no ramo executável Windows;
  módulo Python e nomes Linux/Web não foram alterados.
- Recurso Windows distingue `AnastacioEngine.exe` e `RangeRuntime.exe`, pois é compartilhado.
  Reconhecimento do processo pai aceita os nomes novo e legado, com comparação exata sem
  distinguir maiúsculas/minúsculas.
- Dependência Windows do editor no player evita instalação global concorrente com o link
  do player. Primeiro build teve LNK1104; após ordenar os alvos, build completo passou.
- Ferramentas e comandos Windows atuais foram atualizados. README diferencia builds novos
  dos pacotes anteriormente publicados, que ainda usam `RangeEngine.exe`.
- Editor novo iniciou, expôs o caminho correto em `bpy.app.binary_path` e executou Cook.
  Player manteve nome e comportamento. Os sete testes de segurança do RangeArmor passaram.
- Projeto `.range` existente abriu e foi salvo como cópia. Caminho do painel foi capturado
  em teste e existe; não houve validação visual da GUI. ZIP local extraído em pasta com
  espaços iniciou o editor, gerou `.cooked` pelo player e executou `.rasec`.
- Editor antigo foi movido de `build/bin/` para o backup, evitando duas versões na instalação.
  Backup: `build/safety-backups/editor-rename-20261008-095726/`.
- Associações usam `GetModuleFileName` e preservam ProgIDs; nenhuma associação existente
  apontando ao executável antigo desta instalação foi encontrada. Não houve registro novo.

Pendências de validação: uso visual do editor/painel no jogo real, console, Steam/LAN, Windows
sem Visual Studio e registro/remoção HKCU/HKLM em ambiente de teste. O pacote local de
validação não é um release publicado. Player e ferramenta não foram rebatizados.


## 10. Continuação: Web e Android após a renomeação

Validação em 2026-10-08, mantendo os nomes internos dos runtimes:

- Usuário confirmou que o editor `AnastacioEngine.exe` funcionou. Essa confirmação não
  representa validação do painel RangeArmor nem de todas as exportações no jogo real.
- 131 testes do núcleo Web/Android passaram (`unittest discover` em
  `tools/tests/web_profile`).
- `engine_web_export.py` executado pelo editor novo passou: geração de pacote,
  manifesto, controles na tela e preservação da entrega anterior quando há erro.
  O preflight inicial reportou `WEB-GFX-002`, mas o diagnóstico em
  `build/editor-rename-web-preflight.json` mostrou falso positivo: log de tempo de carga
  com "shaders" e "compiled". Corrigida a heurística em `tools/web/package-web.py` para
  exigir indicação de falha; diagnóstico estruturado continua preservado. Teste JavaScript
  de regressão passou, incluindo falha real e log GLSL complementar. Nova exportação e
  preflight no navegador passaram sem problemas nas duas variantes de controles.
- `engine_android_export.py` executado pelo editor novo passou: export Web prévio,
  Gradle `assembleDebug`, relatório e conteúdo do APK conferidos. Artefato de teste:
  `C:\Users\f_bro\AppData\Local\Temp\tmpk4jravny\android\jogo-0.2-debug.apk`.
  Instalação e execução em aparelho não realizadas; APK não publicado.
- Android oficial continua sendo APK WebView sobre `build-web-release`. Não há
  renomeação de `.exe` dentro dele. Android NDK continua congelado.
- RangeArmor mantém saídas desktop Windows/Linux; os exportadores Web/Android são
  próprios. Cooking desktop não foi declarado compatível com Web/Android por esses testes.

Painel RangeArmor posteriormente recompilado e validado pela GUI, conforme seu plano.
Usuário confirmou que o jogo rodou; essa confirmação não comprova todas as plataformas
ou uso do cache. Próximas verificações: Web no jogo real, APK no aparelho, LibLoad e outra
GPU. A etapa 5 do player Windows foi posteriormente autorizada e implementada; ver seção 14.

## 11. Complemento: fonte da RangeArmor localizado no Git

Correção do levantamento inicial em 2026-10-07: `git log --all -- tools/RangeArmor-master` e
`git ls-tree -r 69df19d9 -- tools/RangeArmor-master` confirmaram o snapshot. Naquela inspeção
foi feita leitura direta com `git show` e `git grep`, sem restaurar arquivos nem alterar o índice.
Em 2026-10-08 o fonte foi recuperado, conforme a seção 3 e o plano de atualização da ferramenta.

Achados confirmados no snapshot `69df19d9`:

- `release/scripts/get_rangeengine_currentplatform.py`: tabela `PLATFORMS` usa `RangeRuntime.exe`
  e `RangeRuntime`. A cópia e validação continuam válidas quando apenas o editor muda.
- `source/launcher/src/main.rs`: lê `Engine<plataforma>` do JSON e executa o caminho configurado;
  o nome do editor não é uma dependência literal desse fluxo.
- `source/gui-rs/src/project.rs`: padrões Windows/Linux usam `RangeRuntime`; campos legados
  32-bit não comprovam suporte atual a essas plataformas.
- `source/gui-rs/src/screens/editor.rs`: mensagens e testes referem-se ao player; incluir
  essa interface na auditoria, além do painel Godot.
- `source/gui-rs/Cargo.toml`: metadado `CompanyName = "RangeEngine"`; revisar somente se a
  marca da ferramenta também for alterada.
- Scripts, cenas e presets estão disponíveis no snapshot para manutenção da ferramenta.

O upstream público existe em <https://github.com/rangeengine/RangeArmor>, mas o snapshot local
contém adaptações AnastacioEngine que precisam ser preservadas. Fonte recuperável não comprova
que os binários distribuídos foram gerados desse exato snapshot; a sessão de implementação
confirmou diferenças e atualizou o launcher Windows após teste do pacote extraído.

## 12. Conferência da instalação e limpeza das sobras — 2026-10-08

Usuário confirmou: “o jogo rodou”. Registro de execução manual bem-sucedida, sem
atribuir esse resultado a uma plataforma/exportador ou medir ganho do cooking.

Inspeção de `build/bin/`: editor atual é `AnastacioEngine.exe`; `RangeEngine.exe`
não estava presente. Cinco artefatos antigos foram movidos para backup: `RangeEngine.exp`,
`RangeEngine.lib`, `RangeEngine.pdb`, `RangeEngine-obj-drop-test.exe` e seu `.exp`.
O Ninja atual gera import library e PDB como `AnastacioEngine`, confirmando a mudança.
Backup: `D:/AnastacioEngine/build/safety-backups/editor-legacy-artifacts-20261008-110641/`. Editor instalado executou em background
com startup de fábrica e confirmou `bpy.app.binary_path`, retornando 0 após a limpeza.

`RangeRuntime.exe`, seus símbolos e `rangearmor/` permanecem ativos, conforme o escopo
da primeira etapa. `build/bin/Release/` contém bibliotecas de builds anteriores e não
foi alterado: não confundir essa subpasta com os executáveis atuais na raiz de `bin/`.
Recompilar não remove saídas antigas automaticamente; não foi necessário rebuild limpo
para retirar essas sobras. Renomear o player continua sendo a migração da seção 5.

## 13. Pacotes Windows atualizados — 2026-10-08

Pacotes locais em `build/dist/validation-20261008-111756/`, sem substituir releases
existentes nem publicar. Engine: `AnastacioEngine-validation-20261008-111756-windows-x64.zip`
(188.011.888 bytes); ferramenta: `RangeArmor-validation-20261008-111756-windows-x64.zip`
(10.435.006 bytes). `SHA256SUMS.txt` acompanha os dois arquivos.

Staging isolado excluiu símbolos `.pdb/.map/.lib/.exp`, caches Python, logs e testes;
editor contém DLLs, assembly `blender.crt/`, Python/scripts/datafiles e licenças. Ferramenta
separada contém painel Rust atualizado, scripts/templates e licença MIT. Para instalar,
extrair a pasta `rangearmor` ao lado de `AnastacioEngine.exe`; Godot fica somente no backup
da instalação de desenvolvimento. Launcher Linux herdado mantido, sem execução nesta sessão.

ZIPs conferidos por CRC e extraídos de fato em pasta com espaços. Editor extraído abriu,
resolveu player e painel pelo diretório novo; painel extraído criou janela e fechou com 0.
Scripts/Python do pacote copiaram o runtime, prepararam `.cooked` e exportaram o projeto
temporário. Jogo dessa entrega retornou 0 e log confirmou execução e hull preparado usado.
Nenhum símbolo de debug foi incluído na entrega. Configuração do painel restaurada.

Evidência e hashes em `build/current-windows-packages.json`; logs `build/current-package-*`.
Scripts locais: `build/package_windows_current.py` e `build/validate_current_windows_packages.py`.
Primeiro teste tinha config temporário sem `DataSource`; corrigido o fixture, execução passou.
Limites: mesma máquina de desenvolvimento, cena controlada; Windows limpo/sem Visual Studio,
Linux, outra GPU e APK em aparelho ainda exigem validação própria. Não foi feito rebuild
nativo: pacotes usam os executáveis já compilados e a instalação atual.

## 14. Player Windows renomeado — 2026-10-08

Usuário autorizou a segunda etapa após esclarecer que o player ainda tinha o nome antigo.
O alvo `RangeRuntime` agora produz `AnastacioRuntime.exe` somente no Windows; recurso
`OriginalFilename` e caminho usado no registro de `.range` acompanham o arquivo novo.
Alvos internos, ícones herdados, APIs, formatos, preferências e nomes Linux/Web/Android
foram preservados. RangeArmor mantém sua marca e recebe a integração com o runtime novo.

Standalone, cooking e export nativo preferem o player novo e aceitam o legado em instalações
antigas. Novos projetos RangeArmor usam o nome novo; configurações antigas continuam lidas.
Se um caminho configurado existe, ele ganha prioridade, inclusive para runtime personalizado.
O config do autor não é sobrescrito: somente o config da entrega recebe o nome do executável
efetivamente copiado. Launchers antigos conhecidos por SHA256 podem usar o template atualizado
no Run/Export; launchers personalizados não são substituídos. A instalação portátil é descoberta
pela posição dos scripts, sem precisar configurar variáveis de ambiente.

Build nativo com vcvars64/VSLANG passou (14 etapas), incluindo editor e player. Launcher:
três testes e build release; painel: 26 testes release e build release. Primeiro link dos
testes debug do painel teve LNK1104 no executável de teste antigo; perfil release evitou
o artefato de debug e passou. Quatro avisos preexistentes de campos não lidos no painel.
Doze testes Python do RangeArmor e 132 testes Web/Android passaram.

Execução direta do player novo, Cook pelo editor, operador standalone real e export nativo
com jogo incorporado passaram. Logs confirmaram lógica da cena e hull preparado usado.
O primeiro fixture do editor tentou abrir um arquivo protegido renomeado como `.range`;
corrigido para usar a cena editável e adicionar a lógica de encerramento do teste.
Player antigo e símbolos antigos da raiz de `build/bin/` foram movidos para backup,
após execução bem-sucedida do player novo: `build/safety-backups/runtime-rename-20261008-112914/`.
Evidência: `build/runtime-rename-execution.json` e `build/runtime-rename-*.log`.

Novos ZIPs locais em `build/dist/validation-20261008-113829/`, com CRT, DLLs, scripts e
licenças preservados; sem símbolos de debug. Integridade CRC, caminhos `/` e extração
conferidos. Editor e painel extraídos iniciaram; scripts/Python do pacote encontraram o
runtime sem variáveis de ambiente, copiaram, cozinharam e exportaram um projeto com config
e launcher antigos. Run e jogo exportado retornaram 0; hull preparado foi usado. Config
original preservado e config da entrega aponta para `AnastacioRuntime.exe`.
Execução após extração registrada em `build/current-windows-packages.json`.
Nenhuma publicação ou alteração das associações do Windows foi realizada. Re-registrar
associações antigas e teste em Windows limpo seguem pendentes. O usuário confirmou que o jogo
funciona após a migração. A implementação Windows está concluída; Windows limpo verifica
as dependências do pacote e Linux exige uma validação separada em outra máquina.
