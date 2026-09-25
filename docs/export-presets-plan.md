# Export Presets (in-Blender)

## Situação atual (levantamento)

- `WM_OT_export_with_rangearmor` (`source/release/scripts/startup/bl_operators/wm.py:2571`)
  apenas abre o executável externo `RangeArmor Panel` (Windows) ou `RangeArmor Panel`
  (Linux), sem passar nenhum parâmetro do projeto atual.
- O empacotamento real (detecção de runtime Windows64/Linux64, cópia de `EngineWindows64`/
  `EngineLinux64`, geração de `.zip`/`.tar.xz`) já existe e está validado no RangeArmor Panel
  (Godot), documentado em `rangearmor-modernization-plan.md`. Não é preciso reimplementar
  empacotamento.
- `tools/RangeArmor-master/RangeArmor-master/export_presets.cfg` é a configuração de build do
  próprio RangeArmor Panel (o launcher em Godot), não um preset por-jogo — não deve ser
  confundido com o recurso que queremos adicionar.
- O RangeArmor Panel lê e grava `launcher/config.json` na raiz do projeto (`welcome.gd`
  `_create_new_project`/`_load_project`, `scripts/globals.gd` `DEFAULT_FIELDS`), populado a
  partir de `DEFAULT_FIELDS`: `GameName`, `Version`, `MainFile`, `DataFile`, `DataSource`,
  `DataChunkSize`, `CompressionLevel`, `CompileScripts`, `ExportCompress`, `EngineWindows64`,
  `EngineLinux64`, `PythonWindows64`, `PythonLinux64`, `AlternativePython`,
  `AlternativePythonLinux`, `Persistent`, `Ignore`.
- **Achado crítico** (`welcome.gd:_validate_data`, linhas 77-89): a validação usa uma
  *whitelist estrita* — qualquer chave em `config.json` que não esteja em `DEFAULT_FIELDS`
  faz o carregamento do projeto **falhar por completo** no RangeArmor Panel (não é apenas
  ignorada). Chaves ausentes são preenchidas com o default, mas chaves extras não são
  toleradas. Isso invalida a suposição inicial de que dava para acrescentar campos livres
  (`CompanyName`, `IconPath`, toggle de plataforma) sem tocar no lado Godot.
- Não existe, hoje, um campo de "quais plataformas exportar": a exibição dos botões de
  export/run por plataforma em `editor.gd` é baseada em **existência do arquivo de runtime em
  disco** (`project["Engine" + platform]`), não em uma flag de config.
- Ou seja: dentro do schema atual, só `GameName` e `Version` têm gravação segura sem alterar o
  RangeArmor Panel. `CompanyName`, `IconPath` e toggle de plataforma exigiriam estender
  `DEFAULT_FIELDS`/`_validate_data` no Godot (aditivo e retrocompatível, mas fora do escopo
  combinado para esta fase).

## Escopo proposto (aditivo, sem alterar o RangeArmor Panel)

1. **PropertyGroup nova** `RangeArmorExportSettings`, anexada à `Scene` via
   `Scene.rangearmor_export = PointerProperty(...)` — Python puro (RNA), sem DNA/C, sem
   doversion (mesmo padrão já usado pelo Input System em `bl_ui/__init__.py`). Campos:
   `export_windows64`, `export_linux64`, `product_name`, `product_version`, `company_name`,
   `icon_path`. **Implementado.**
2. **Painel** `SCENE_PT_rangearmor_export` em `Properties > Export Game` (antes `Properties > Scene`), com os campos acima e um
   botão que chama `wm.export_with_rangearmor`. **Implementado.**
3. **`WM_OT_export_with_rangearmor`** agora, antes de abrir o executável, lê
   `launcher/config.json` do projeto atual (deduzido a partir de `bpy.data.filepath`,
   assumindo a estrutura `<projeto>/data/<nome>.range`) e atualiza **apenas** `GameName`
   (← `product_name`) e `Version` (← `product_version`), preservando todas as outras chaves.
   Não cria o arquivo se ele não existir (evita risco de gerar um config incompleto antes de o
   RangeArmor Panel tê-lo inicializado). **Implementado.**
4. **Todos os campos agora têm efeito.** O whitelist do RangeArmor Panel
   (`scripts/globals.gd` `DEFAULT_FIELDS`) foi estendido de forma aditiva com
   `CompanyName` (""), `IconPath` (""), `ExportWindows64` (true) e `ExportLinux64` (true) —
   `welcome.gd:_validate_data` preenche esses defaults automaticamente em projetos antigos
   que não os têm, então nada quebra ao reabrir um projeto existente. `wm.py` agora grava
   `company_name`→`CompanyName`, `icon_path`→`IconPath` (resolvido para caminho absoluto via
   `bpy.path.abspath`) e sempre grava `export_windows64`/`export_linux64` →
   `ExportWindows64`/`ExportLinux64`.
   - `release/scripts/build_release.py`: ao expandir o target `"All"`, agora filtra por
     `data.get("Export" + platform, True)` — desmarcar uma plataforma no painel do Blender faz
     o botão "Export All" pular aquela plataforma. Os botões de export individuais
     (`ButtonExportWindows64`/`ButtonExportLinux64`) continuam funcionando independentemente do
     toggle, como atalho manual.
   - `release/scripts/set_icons.py`: se `IconPath` estiver preenchido e o arquivo existir, ele é
     usado como ícone tanto do launcher quanto do engine Windows, no lugar dos arquivos fixos
     `icons/icon-launcher.ico`/`icons/icon-engine.ico`. Se o arquivo não existir, cai de volta
     para o comportamento antigo com um aviso no log.
5. **Sem migração de dados existente**: projetos antigos sem o bloco `rangearmor_export` na
   cena continuam funcionando exatamente como hoje (RNA com defaults, sem erro ao abrir).

## Atualização 2026-09-12: botão "Export Game (1 Click)"

Adicionado `wm.one_click_export_rangearmor` no mesmo painel `Export Game > Export (RangeArmor)`, que
chama `release/scripts/build_release.py --target All --compress` diretamente (mesmo script que o
botão "Export All" do RangeArmor Panel usa via `OS.execute`), sem precisar abrir o executável do
painel nem copiar arquivos manualmente depois — o resultado já sai compactado em
`<projeto>/release/`, cuja pasta é aberta automaticamente ao final. Ver `docs/changelog.md`
(2026-09-12) para detalhes de implementação.

**Atualização 2026-09-12 (mesmo dia): scaffold automático + progresso + fix do Launcher.exe.**
Testado end-to-end com um projeto real (`D:\teste_export\MyProject`). O botão agora funciona sem
nenhum passo manual prévio (nem abrir o RangeArmor Panel, nem gerar `.rasec` à mão): scaffold do
projeto, geração do `.rasec`, download do runtime do engine e barra de progresso/cursor de espera
foram todos automatizados dentro do próprio operador. Um bug separado foi encontrado e corrigido
durante o teste: o `Launcher.exe` usado como template do scaffold estava compilado de uma versão
antiga do launcher Rust (`source/launcher/src/main.rs`) com um `.unwrap()` que sempre dava panic
ao iniciar (sintoma: o jogo exportado "abre e fecha" instantaneamente). Recompilado via `cargo
build --release` a partir do source atual — ver `docs/changelog.md` (2026-09-12, "scaffold
automático, progresso e Launcher.exe corrompido") para o detalhamento completo, incluindo o aviso
de que o `.exe` recompilado não é rastreado em git e precisa ser regerado se o diretório
`tools/RangeArmor-master` for reinstalado a partir de uma fonte externa.

**Atualização 2026-09-12 (mesmo dia): rebuild automático do template.** Esse passo manual de
regerar o `.exe` deixou de ser necessário: `_rangearmor_ensure_launcher_template_fresh`
(`source/release/scripts/startup/bl_operators/wm.py`) agora roda automaticamente no início do
scaffold, comparando a data do `Launcher.exe` template com a de `source/launcher/src/main.rs` e
recompilando sozinho via `cargo build --release` quando o template está desatualizado — sem
diálogo de confirmação, sem passo manual. Ver `docs/changelog.md` (2026-09-12, "rebuild automático
do template Launcher.exe").

## Fora de escopo nesta fase

- Mudar formato/local de empacotamento (`.zip`/`.tar.xz`), já resolvido.
- Adicionar novas plataformas (Android/iOS) — depende de `mobile-export-plan.md`, que ainda
  não tem backend GHOST/CMake pronto.
- Alterar `export_presets.cfg` do RangeArmor Panel (isso é build do launcher, não do jogo).
- ~~Estender `DEFAULT_FIELDS`/`_validate_data` do RangeArmor Panel (Godot) para aceitar
  `CompanyName`/`IconPath`/toggle de plataforma~~ — feito (ver item 4 acima).

## Próximos passos concretos

1. ~~Definir a `RangeArmorExportSettings` (RNA Python, sem DNA/C)~~ — feito.
2. ~~Implementar o painel Python (`bl_ui`) e o write de `GameName`/`Version` no operador~~ — feito.
3. ~~Testar a lógica de escrita isoladamente~~ — feito via script Python que replica
   `_write_export_preset` (sem `bpy`) contra um `launcher/config.json` de exemplo com todas as
   chaves de `DEFAULT_FIELDS`. Resultado: só `GameName`/`Version` mudam, nenhuma chave é
   adicionada/removida, e campos vazios no painel não sobrescrevem valores existentes.
4. ~~Validar projeto antigo sem `launcher/config.json`~~ — feito no mesmo teste: o write é
   pulado silenciosamente (`skip: no config.json`), nada é criado.
5. ~~Teste end-to-end real dentro do Blender~~ — feito. Validado com o RangeArmor Panel
   instalado em `build/bin/rangearmor/` (build separado do que está em
   `tools/RangeArmor-master`, não regenerado pelo `ninja install` — ver nota abaixo), em
   projeto novo e em projeto antigo (`export_ROLIMARACER`), export e "Run".
6. ~~Decisão futura: estender o whitelist do RangeArmor Panel para habilitar
   `company_name`/`icon_path`/toggle de plataforma de fato~~ — feito.

## Bug encontrado durante o teste end-to-end: `launcher.py` ausente no scaffolding

Durante a validação do item 5, apareceu um bug não relacionado ao escopo original: o
RangeArmor Panel instalado em `build/bin/rangearmor/` não coloca `launcher.py` na pasta
`launcher/` do projeto ao criar um projeto novo (a lógica de "New Project" está compilada
dentro do `.pck`, não é editável diretamente). Isso quebrava tanto "Export"
(`build_release.py`, STAGE 3) quanto "Run" (`run_launcher.py` → `Launcher.exe`), com o erro
`Could not find script launcher.py` / `[Errno 2] No such file or directory`. Reproduzido em
projeto novo e em projeto antigo pré-existente — não é um problema de projeto desatualizado.

Correções aplicadas (aditivas, sem quebrar projetos que já têm `launcher.py`):

- `release/scripts/build_release.py` (STAGE 3): se `launcher/launcher.py` não existir no
  projeto, cai de volta para o `launcher.py` template empacotado com o próprio painel
  (`release/launcher/launcher.py`, ao lado do script via `Path(__file__).resolve().parent.parent`),
  com aviso no log. **Nota:** esse arquivo faz parte do build separado em
  `build/bin/rangearmor/`, não é rastreado em `tools/RangeArmor-master` nem em nenhum lugar do
  git — o fix se perde se esse RangeArmor Panel for reinstalado/substituído e precisa ser
  reaplicado manualmente nesse cenário.
- `source/release/scripts/startup/bl_operators/wm.py`
  (`WM_OT_export_with_rangearmor._ensure_launcher_script`): toda vez que o usuário clica em
  "Open RangeArmor Panel" no Blender, se o projeto atual tiver pasta `launcher/` mas não tiver
  `launcher.py`, copia automaticamente a partir do template empacotado junto do executável do
  painel (`<pasta do RangeEngine>/rangearmor/release/launcher/launcher.py`). Esse fix é
  rastreado em git e vale para qualquer projeto (novo ou antigo) a partir do momento em que o
  painel é aberto pelo Blender.
