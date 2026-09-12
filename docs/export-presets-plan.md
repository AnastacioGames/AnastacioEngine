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
2. **Painel** `SCENE_PT_rangearmor_export` em `Properties > Scene`, com os campos acima e um
   botão que chama `wm.export_with_rangearmor`. **Implementado.**
3. **`WM_OT_export_with_rangearmor`** agora, antes de abrir o executável, lê
   `launcher/config.json` do projeto atual (deduzido a partir de `bpy.data.filepath`,
   assumindo a estrutura `<projeto>/data/<nome>.range`) e atualiza **apenas** `GameName`
   (← `product_name`) e `Version` (← `product_version`), preservando todas as outras chaves.
   Não cria o arquivo se ele não existir (evita risco de gerar um config incompleto antes de o
   RangeArmor Panel tê-lo inicializado). **Implementado.**
4. **Campos ainda sem efeito nesta fase**: `export_windows64`, `export_linux64`,
   `company_name`, `icon_path` continuam visíveis no painel do Blender, mas não são
   gravados em lugar nenhum ainda — não há chave correspondente no `config.json` que o
   RangeArmor Panel aceite. Habilitar isso é um passo futuro explícito (ver abaixo), não
   silencioso.
5. **Sem migração de dados existente**: projetos antigos sem o bloco `rangearmor_export` na
   cena continuam funcionando exatamente como hoje (RNA com defaults, sem erro ao abrir).

## Fora de escopo nesta fase

- Mudar formato/local de empacotamento (`.zip`/`.tar.xz`), já resolvido.
- Adicionar novas plataformas (Android/iOS) — depende de `mobile-export-plan.md`, que ainda
  não tem backend GHOST/CMake pronto.
- Alterar `export_presets.cfg` do RangeArmor Panel (isso é build do launcher, não do jogo).
- Estender `DEFAULT_FIELDS`/`_validate_data` do RangeArmor Panel (Godot) para aceitar
  `CompanyName`/`IconPath`/toggle de plataforma — necessário para os campos do item 4
  passarem a fazer algo; decidido explicitamente por ora **não** entrar nesta fase.

## Próximos passos concretos

1. ~~Definir a `RangeArmorExportSettings` (RNA Python, sem DNA/C)~~ — feito.
2. ~~Implementar o painel Python (`bl_ui`) e o write de `GameName`/`Version` no operador~~ — feito.
3. ~~Testar a lógica de escrita isoladamente~~ — feito via script Python que replica
   `_write_export_preset` (sem `bpy`) contra um `launcher/config.json` de exemplo com todas as
   chaves de `DEFAULT_FIELDS`. Resultado: só `GameName`/`Version` mudam, nenhuma chave é
   adicionada/removida, e campos vazios no painel não sobrescrevem valores existentes.
4. ~~Validar projeto antigo sem `launcher/config.json`~~ — feito no mesmo teste: o write é
   pulado silenciosamente (`skip: no config.json`), nada é criado.
5. **Ainda pendente**: teste end-to-end real dentro do Blender (`install/` não tem um
   RangeArmor Panel buildado hoje, só `RangeEngine.exe`/`RangeRuntime.exe`) — abrir o painel de
   Scene de um build funcional, preencher os campos, clicar em "Open RangeArmor Panel" e
   confirmar visualmente que o RangeArmor Panel carrega o projeto normalmente com o nome/versão
   atualizados. Requer um build do fork com esse `wm.py`/`bl_ui` e o executável do RangeArmor
   Panel disponível.
6. Decisão futura (não agora): estender o whitelist do RangeArmor Panel para habilitar
   `company_name`/`icon_path`/toggle de plataforma de fato.
