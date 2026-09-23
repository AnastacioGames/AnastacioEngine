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
`.blend`/`.range`. A importação rejeita ações sem equivalente nativo.

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
