# Plano: análise e otimização do carregamento de cenas e `.range` externos

Estado: **planejado, não iniciado** (2026-10-03). Nada abaixo foi implementado ou medido ainda; os custos
vêm da leitura do código.

## Problema

Carregar objetos ou arquivos `.range` externos para complementar a cena demora, mesmo quando o arquivo tem
só o objeto. Uma cena com muitos objetos internos também demora para abrir.

## Diagnóstico (leitura do código)

### Caminho do carregamento externo

`Range.LibLoad`, `scene.addObject(..., libpath=...)` (que usa `group="Scene"` por padrão) e o operador
"Link to LibLoad" acabam em `BL_Converter::LinkBlendFile` (`source/source/gameengine/Converter/BL_Converter.cpp`):

1. `blo_openblenderfile` (`source/source/blender/blenloader/intern/readfile.c`) abre o arquivo sempre pelo
   gzip; um `.rasec` é descriptografado inteiro na memória.
2. `read_file_dna` percorre os blocos até o `DNA1`, que fica no fim do arquivo, e `get_bhead` lê cada bloco
   inteiro: o arquivo todo é descomprimido para a RAM antes de escolher o que usar.
3. `load_datablocks` com `group="Scene"` liga todas as cenas do arquivo e tudo o que elas referenciam.
4. `ConvertScene` converte malhas, física e lógica. Só esta etapa vai para outra thread com
   `asynchronous=True`; as anteriores ficam na thread principal.
5. `MergeScene` chama `ReloadShaders(to)`, que recompila **todos** os materiais da cena de destino
   (`BL_BlenderShader::ReloadMaterial` apaga o `GPUMaterial` e gera o GLSL de novo), não só os novos.

### Caminho da cena interna

`BL_Converter::ConvertScene` → `BL_ConvertBlenderObjects`
(`source/source/gameengine/Converter/BL_BlenderDataConversion.cpp`), tudo numa thread:

- Cada objeto, inclusive de camadas inativas e grupos, é convertido por completo.
- `BL_ConvertMesh` copia a malha, calcula normais e, se houver UV, tangentes MikkTSpace. Só reaproveita
  quando os objetos apontam para o mesmo datablock Mesh (`FindGameMesh`); cópias com malha própria são
  convertidas de novo. A física também só reaproveita a forma com a mesma malha
  (`CcdShapeConstructionInfo::FindMesh`).
- Um shader por datablock Material: `Material`, `Material.001` e `Material.002` iguais compilam 3 vezes.
- O gerador de shader (`source/source/blender/gpu/intern/gpu_material.c`, laço de lâmpadas com `SETLOOPER`)
  escreve o código de todas as lâmpadas da cena em cada material, inclusive as de camadas inativas. Custo
  perto de materiais × lâmpadas.
- Não há cache de shader compilado entre execuções (nenhum uso de `glProgramBinary`).
- `InitTextures` sobe as imagens para a GPU sem compressão, gerando mipmaps na hora.

### Custos prováveis, em ordem

1. Shaders: materiais × lâmpadas, materiais duplicados, e a recompilação da cena inteira a cada merge.
2. Objetos duplicados com malha própria (tangentes e física repetidas).
3. `group="Scene"` como padrão no LibLoad/`addObject`, que traz o arquivo inteiro.
4. Leitura completa e descompressão do `.range` externo na thread principal.
5. Texturas grandes.

### Achado no editor

`outliner_add_libload_texts` (`source/source/blender/editors/space_outliner/outliner_tree.c`) abre e lê o
`.range` externo inteiro a cada reconstrução da árvore do Outliner (seção "External Files"). Isso pode deixar
o próprio editor lento com arquivos externos grandes. Correção: guardar em cache os nomes dos Texts por
arquivo e data de modificação.

## Etapa 1: "Análise de Carregamento" no Outliner

Botão no Outliner que **só analisa** (não altera o arquivo) e aponta onde está o peso. Só Python: não
precisa recompilar a engine.

O que reaproveitar:

- Header do Outliner: `source/release/scripts/startup/bl_ui/space_outliner.py` (`OUTLINER_HT_header.draw`),
  que já mostra botões por `space.display_mode` (ex.: `outliner.orphans_purge` em ORPHAN_DATA).
- Registro de operadores: lista `_modules` em `source/release/scripts/startup/bl_operators/__init__.py`, no
  mesmo padrão de `anastacio_material_recipes`.
- Dados: `bpy.data` (mesma fonte dos modos "Blender File" e "Orphan Data"), `bpy.data.libraries` (o que
  aparece em "External Files") e `bpy.data.libraries.load(path)` para listar os nomes de um arquivo externo.
- Filtro do Outliner: `space.filter_text` para destacar os itens do relatório.

Implementação:

1. Novo `bl_operators/anastacio_load_report.py` com o operador `outliner.anastacio_load_report`:
   - por cena: objetos (camada ativa/inativa, grupos) e número de lâmpadas (todas as camadas);
   - malhas: objetos vs. malhas únicas, malhas com UV (custo de tangente), triângulos, candidatos a
     compartilhar a malha (mesmo nome-base `.001` e mesma contagem de vértices/faces);
   - materiais: únicos vs. duplicados (nome-base e assinatura da árvore de nós) e estimativa
     materiais × lâmpadas;
   - imagens: resolução, MB na GPU, empacotadas ou não;
   - arquivos externos: caminho, tamanho em disco, comprimido (gzip `1f 8b`), `.rasec`, datablocks usados
     vs. quantos o arquivo tem;
   - saída: Text `Analise_Carregamento` com o relatório completo e um popup curto com o resumo e os 3
     maiores pesos.
2. Operador `outliner.anastacio_load_select` (malhas duplicadas, materiais duplicados, imagens grandes,
   lâmpadas): seleciona os objetos e ajusta `filter_text` para mostrá-los no Outliner.
3. Botão no header nos modos ALL_SCENES, CURRENT_SCENE e LIBRARIES.
4. Docs: entrada no topo de `docs/changelog.md`, roadmap e relatório de melhorias atualizados;
   `python tools/check_docs.py`.

Verificação: `python -m py_compile` nos arquivos alterados; no editor (Windows, `build/bin/`), abrir uma cena
pesada, clicar no botão, conferir o Text e os botões de seleção, e abrir um arquivo com "External Files" para
conferir tamanho e compressão. O arquivo não deve mudar.

## Próximas etapas (depois da validação da etapa 1)

1. **Cronômetro no runtime:** tempo por etapa dentro de `LinkBlendFile` e da conversão da cena (abertura,
   link, malhas, tangentes, física, shaders com número de materiais e lâmpadas, texturas, merge), impresso
   no console. Hoje `KX_LibLoadStatus` só mede o total (`timeTaken`). Confirma os números estimados na
   etapa 1.
2. **Correções na engine (C++):** no merge, recompilar só os materiais novos, e todos apenas quando chegarem
   lâmpadas; compilar uma vez só os materiais idênticos; deixar fora do shader as lâmpadas que não afetam o
   objeto; cache dos nomes de Text no Outliner. Mais adiante, cache de shader em disco (`glProgramBinary`).
3. **Botão "Otimizar"**, no próprio arquivo ou gerando `nome_libload.range`: juntar materiais duplicados,
   voltar a compartilhar malhas iguais, deixar só os objetos marcados numa cena, apagar órfãos e previews,
   reduzir texturas, salvar sem compressão e, opcionalmente, gerar o `.rasec` a partir da versão enxuta.
