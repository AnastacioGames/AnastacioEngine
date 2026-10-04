# Exemplo de Cutscene nativa

O exemplo mínimo usa somente a ação nativa `Spawn Object`:

- sequência `Opening`;
- evento `Spawn Hero` no tempo `1.0` segundo;
- `Hero Template` como **Template Object**;
- `Hero Spawn Point` como **Spawn Point**;
- **Dependent Object** deixado vazio para demonstrar que é opcional.

## Gerar o arquivo

Na raiz do checkout:

```text
build\bin\RangeEngine.exe --background --factory-startup --python source\release\scripts\templates_py\cutscene_native_example.py -- docs\cutscene-native-example.blend
```

O arquivo é salvo em DNA nativo; não depende do add-on de referência em
`tools/ProjetoCutscene`.

## Validar save/load

```text
build\bin\RangeEngine.exe --background docs\cutscene-native-example.blend --python source\release\scripts\templates_py\cutscene_native_example_validate.py
```

O resultado esperado é `[cutscene_native_example_validate] PASS`.

## Validar intercâmbio JSON

```text
build\bin\RangeEngine.exe --background docs\cutscene-native-example.blend --python source\release\scripts\templates_py\cutscene_native_export.py -- docs\cutscene-native-example.json
build\bin\RangeEngine.exe --background docs\cutscene-native-example.blend --python source\release\scripts\templates_py\cutscene_native_import.py -- docs\cutscene-native-example.json
```

O JSON é apenas intercâmbio versionado; a fonte de verdade continua sendo o
`.blend`/`.range`. O export cobre todos os tipos de evento (schema 2); a importação aceita o formato legado, v1 e v2
e rejeita ações sem equivalente nativo.

Regressões headless (no Linux: `BLENDER_SYSTEM_SCRIPTS=source/release/scripts RangeEngine --background --factory-startup --python <script>`):
`cutscene_native_export_regression.py`, `cutscene_native_import_regression.py` e `cutscene_persistence_regression.py`.
Wait Trigger no runtime: `RangeEngine -b --python tools/create_cutscene_wait_test.py -- wait.range` e depois
`RangeRuntime wait.range` (`xvfb-run -a` sem display); espera `CUTSCENE_WAIT_TEST PASS`. Um Wait Trigger é liberado por
mensagem com o nome do trigger como subject ou por `scene.release_cutscene_trigger("nome")`.

## Roteiro no editor/runtime

1. Abra o `.blend` no `RangeEngine` e confirme a aba **Cutscene** logo depois
   de **World**, com o ícone `SEQUENCE`.
2. Confirme que os botões de adicionar/apagar usam os ícones padrão `ZOOMIN` e
   `ZOOMOUT`.
3. Salve, feche e reabra o arquivo; a sequência e as referências devem
   permanecer.
4. Execute Play: no tempo de 1 segundo, o template deve ser criado no ponto de
   spawn. Pare e execute Play novamente; não devem permanecer objetos órfãos.
5. Repita em standalone com o `.range` e compare o mesmo evento e tempo.
