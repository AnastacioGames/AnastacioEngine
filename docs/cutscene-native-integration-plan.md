# Plano — Cutscene nativo da AnastacioEngine

## Objetivo

Converter o projeto Cutscene de ferramenta/add-on em uma função distribuída com
a AnastacioEngine. A autoria fica no editor, na aba própria de Properties ao
lado de **World**; a execução pertence ao runtime C++ da engine. Não haverá
modo legado nem ações específicas de carro/piloto: a ação é genérica
**Spawn Object**, com um campo opcional **Dependent Object**.

O projeto-fonte existente fica em `D:\AnastacioEngine\tools\ProjetoCutscene`
enquanto for usado como referência e para migração de conteúdos. Ele não será carregado
pela engine como add-on e não será copiado para `release/scripts/addons`.

## Decisões confirmadas

- Criar um novo contexto `Cutscene` em Properties, visualmente imediatamente
  depois de `World`. Seu valor em `eSpaceButtons_Context` será acrescentado no
  fim da enumeração, antes de `BCONTEXT_TOT`; valores existentes nunca serão
  renumerados, pois também podem estar gravados em `.blend`.
- A nova aba usará `ICON_SEQUENCE` ("SEQUENCE"), o ícone nativo já existente
  da UI, e aparecerá imediatamente depois de World. Ícones próprios aparecem
  apenas dentro dos painéis, sem alterar o atlas global do Blender 2.79.
- Os controles estruturais de lista não usam PNGs próprios: adicionar e apagar
  sequências/eventos usam os controles padrão de adicionar/apagar da UI. Nesta
  base Blender 2.79, os identificadores nativos equivalentes são `ZOOMIN` e
  `ZOOMOUT` (a aparência de Add/Remove); os PNGs próprios ficam reservados para
  identificação e ações próprias de Cutscene.
- Os PNGs próprios residem em
  `source/release/datafiles/cutscene/icons/` e são instalados em
  `datafiles/cutscene/icons/` junto com a engine.
- A UI Python distribuída em `source/release/scripts/startup/bl_ui/` é parte
  nativa da instalação da engine, não um add-on. Ela será somente a camada de
  autoria e chamará dados RNA e operadores nativos.
- A persistência deve ser no `.blend`/`.range`, em DNA e versionamento. JSON
  exportado, quando existir, é formato explícito de intercâmbio, nunca a fonte
  de verdade da cena.
- Somente a nomenclatura genérica será entregue; não haverá compatibilidade
  com `Spawn Car`/`Pilot`.

## Estado de execução

- As Fases 0, 1 e 2 estão implementadas e compiladas: contrato DNA/RNA,
  contexto nativo de Properties depois de World, aba com `SEQUENCE` e controles
  Add/Delete usando os ícones padrão `ZOOMIN`/`ZOOMOUT`.
- As Fases 4 e 5 estão implementadas e compiladas: conversão/runtime C++,
  ciclo Play/Stop/Restart, API Python e import/export JSON com regressões
  automatizadas.
- A Fase 3 permanece aberta para os PNGs próprios de identificação e ações
  específicas. Ela não deve substituir os ícones nativos de adicionar/apagar.
- A validação manual no editor/jogo real (criar, salvar/reabrir, Play → Stop →
  Play e standalone) continua pendente; o exemplo e as validações automatizadas
  estão em `docs/cutscene-native-example.md`.

## Arquitetura alvo

```text
Properties > Cutscene (UI nativa Python)
             │
             ├─ RNA + operators C
             │       │
             │       └─ Scene.cutscene_settings → CutsceneSequence/Event
             │          (DNA, .blend, versionamento)
             │
             └─ ícones PNG: datafiles/cutscene/icons

BL_BlenderDataConversion / runtime C++
             │
             └─ KX_CutsceneManager → sequências, faixas, eventos e Spawn Object
```

`KX_CutsceneManager` deve ser dono do estado de execução por cena. A camada
Blender fornece definições imutáveis durante a conversão; o runtime mantém
cursor, eventos já disparados, objetos criados e referências temporárias. Isso
evita gravar estado de Play de volta no DNA e mantém Play embutido e
`RangeRuntime` com o mesmo comportamento.

## Fase 0 — preparar a origem, sem integrar código

1. Usar `D:\AnastacioEngine\tools\ProjetoCutscene` como a origem de
   referência; qualquer renomeação futura deve ser uma mudança isolada, que
   atualize este plano e toda a documentação correspondente.
2. Remover da origem os artefatos gerados que forem indevidamente versionados,
   especialmente `__pycache__/`, sem mover a ferramenta para a instalação da
   engine.
3. Inventariar ações, formato de dados, operadores e imagens usados pela versão
   atual. Renomear materiais específicos (`spawn_car.png`, por exemplo) para
   nomes genéricos antes da inclusão definitiva.
4. Registrar autoria/licença de cada ícone que for distribuído.

**Aceite:** `tools/ProjetoCutscene` é apenas referência/ferramenta de migração; iniciar
a engine não o habilita nem depende dele.

## Fase 1 — fundação de dados Cutscene

1. Definir estruturas pequenas em `DNA_scene_types.h`: `CutsceneSettings`, uma
   coleção de `CutsceneSequence` e seus eventos. Evitar o nome "cena de
   cutscene", que conflita conceitualmente com `Scene` do Blender.
2. Para `Spawn Object`, persistir referências `Object *` para **Template
   Object** e **Spawn Point** obrigatórios, e **Dependent Object** opcional;
   não persistir nomes nem ponteiros de runtime. O tipo, tempo e parâmetros
   mínimos do evento também pertencem ao DNA.
3. Implementar alloc/copy/free em `BKE_scene_copy_data` e no free de `Scene`,
   além de read/write em `writefile.c`, `direct_link_scene` e
   `lib_link_scene` de `readfile.c`. As referências `Object *` devem ser
   relinkadas como IDs e ter sua contagem de usuários tratada nos pontos
   equivalentes já usados pela `Scene`.
4. Acrescentar versionamento em `versioning_range.c`, com defaults seguros para
   arquivos anteriores.
5. Expor `scene.cutscene_settings` e suas coleções/propriedades em
   `rna_scene.c`.
6. Criar operadores C de adicionar, remover, reordenar e duplicar itens; a UI
   não manipula ponteiros/listas diretamente.

**Aceite:** salvar e reabrir conserva a estrutura; duplicar uma cena não
compartilha listas internas; arquivo antigo abre com Cutscene vazia e sem
crash. Esta fase altera DNA, portanto exige rebuild limpo de `RangeEngine` e
`RangeRuntime`.

## Fase 2 — contexto nativo e primeira UI

1. Acrescentar `BCONTEXT_CUTSCENE` no fim da enumeração de `SpaceProperties`,
   RNA e roteamento de `buttons_context.c`. O caminho de contexto deve conter
   `Scene` e ser válido mesmo sem objeto ativo.
2. Mapear o contexto para `"cutscene"` em `space_buttons.c`; sem esse
   roteamento os painéis Python não são descobertos.
3. Incluir `CUTSCENE` depois de `WORLD` somente na faixa superior de
   `space_properties.py`.
4. Criar painéis internos em `bl_ui` para lista de sequências, lista de eventos,
   inspector de evento e controles de arquivo/exportação. Os botões de incluir
   e excluir itens usam `ZOOMIN` e `ZOOMOUT` nativos, não previews PNG.
5. A primeira ação entregue será `Spawn Object`: **Template Object** e
   **Spawn Point** obrigatórios, e `Dependent Object` opcional. Os rótulos
   antigos Car/Pilot não aparecem.
6. Manter a UI sem dependência de módulos em `scripts/addons`.

**Aceite:** a aba abre ao lado de World, não quebra os outros contextos, permite
criar/editar/remover a estrutura de dados e não produz erro Python ao abrir
Properties sem uma cena/objeto selecionado.

## Fase 3 — ícones isolados do atlas

1. Adicionar os PNGs aprovados em
   `source/release/datafiles/cutscene/icons/`.
2. Estender a regra de instalação em `source/source/creator/CMakeLists.txt`
   para copiar esse diretório para `${TARGETDIR_VER}/datafiles/cutscene`.
3. Criar um módulo interno de previews no painel Cutscene que resolve o caminho
   por `bpy.utils.resource_path('LOCAL')`/`'SYSTEM'` e carrega as imagens com
   `bpy.utils.previews.load(..., 'IMAGE')`.
4. Mostrar os PNGs por `icon_value`; liberar a coleção de previews no unregister
   da UI/encerramento para não acumular recursos durante reload de scripts.
   Os controles genéricos de adicionar/remover continuam com os ícones nativos
   `ZOOMIN`/`ZOOMOUT`, mesmo dentro de painéis que exibem previews.
5. Usar `ICON_SEQUENCE` para o botão da aba. Um ícone próprio no
   cabeçalho somente será avaliado depois, pois exigiria alterar o desenho C da
   faixa de contextos ou o sistema global de ícones.

**Aceite:** `ninja install` instala as imagens; a UI mostra previews no editor;
ausência de um PNG degrada para ícone nativo/texto e nunca impede abrir a aba;
o atlas `blender_icons16.png`/`blender_icons32.png` não é modificado.

## Fase 4 — conversão e execução C++

1. Criar o contrato de conversão Scene → runtime em
   `source/source/gameengine/Converter/BL_BlenderDataConversion.cpp`, sem
   acoplar o runtime ao módulo Python da UI. A conversão deve resolver cada
   referência DNA para o `KX_GameObject` correspondente, inclusive templates
   inativos; não pode depender de busca ambígua por nome.
2. Criar `KX_CutsceneManager` e testes de ciclo de vida: iniciar, parar,
   reiniciar, trocar cena e destruir a engine.
3. Implementar a linha do tempo e o despachante de eventos determinístico. O
   contrato inicial usa segundos de runtime; eventos no mesmo instante são
   ordenados pelo ordinal estável de inserção. Pause e frame repetido não
   redisparam eventos; seek para trás restaura o cursor e o conjunto de eventos
   disparados de forma definida antes de continuar.
4. Implementar `Spawn Object` pela infraestrutura nativa de conversão/instância
   já existente, com ownership e limpeza explícitos. O template e o dependente
   nascem na transformação do Spawn Point; se existir dependente, ele é
   parentado ao objeto principal preservando a transformação mundial. O manager
   mantém ambos sob sua propriedade e os remove em stop, restart, troca de cena
   e destruição da engine.
5. Expor a API Python de runtime somente após o contrato C++ estar estável.

**Aceite:** Play embutido e standalone produzem a mesma sequência; stop/restart
não deixa objetos órfãos; cena sem Cutscene não tem custo/efeito observável;
spawn inválido emite erro claro e não interrompe a engine.

## Fase 5 — importação/exportação e migração assistida

1. Definir schema versionado para importação/exportação de JSON.
2. Fornecer importador da estrutura genérica do projeto em `tools/Cutscene`.
3. Rejeitar ou solicitar mapeamento explícito para ações ainda sem equivalente
   nativo; não carregar scripts arbitrários do add-on.
4. Produzir um exemplo `.blend`/`.range` e roteiro de validação para o usuário.

**Aceite:** um conteúdo de exemplo passa da ferramenta antiga para DNA nativo,
salva, reabre e executa com o mesmo resultado definido no roteiro.

## Arquivos previstos por responsabilidade

| Responsabilidade | Arquivos candidatos |
| --- | --- |
| Dados persistidos | `DNA_scene_types.h`, `scene.c` (`BKE_scene_copy_data`/free), `writefile.c`, `readfile.c` (direct/lib link), `versioning_range.c` |
| API de autoria | `rna_scene.c`, operadores de editor adequados |
| Aba Properties | `DNA_space_types.h`, `rna_space.c`, `buttons_context.c`, `space_buttons.c`, `space_properties.py`, novo painel `bl_ui` |
| Recursos | `release/datafiles/cutscene/icons/`, `source/creator/CMakeLists.txt` |
| Runtime | `gameengine/Converter/BL_BlenderDataConversion.cpp`, novo código C++ em `gameengine/Ketsji/` |
| Projeto de referência | `tools/ProjetoCutscene/`, fora do carregamento de add-ons |

Os arquivos de contexto de Properties já possuem alterações locais do contexto
Vehicle em `DNA_space_types.h`, `rna_space.c`, `buttons_context.c` e
`space_buttons.c`. Nenhuma fase que os modifique começa até a revisão desses
diffs ou uma decisão do usuário sobre sua propriedade.

## Sequência recomendada

As Fases 0–2 e 4–5 já foram executadas como unidades separadas, com build dos
executáveis e regressões automatizadas aprovados. A próxima unidade de código é a
Fase 3, somente após inventariar os PNGs aprovados, autoria/licença e o caminho
de instalação; ela deve preservar `SEQUENCE` na aba e `ZOOMIN`/`ZOOMOUT` nos
controles genéricos. Em paralelo, a validação manual do exemplo deve ser feita
no editor e no standalone conforme o roteiro de
`docs/cutscene-native-example.md`.

## Validação comum a todas as fases

- Revisar o diff para garantir escopo único por unidade.
- Para C/C++: compilar com o ambiente MSVC e Ninja definido em `AGENTS.md`.
- Após qualquer alteração de `DNA_*.h`, fazer `ninja -t clean` e rebuild total
  de `RangeEngine` e `RangeRuntime` antes de declarar a fase compilada.
- Testar no editor e no jogo real: criação, salvar/reabrir, Play → Stop → Play,
  standalone e arquivo antigo.
- Registrar no roadmap somente trabalho aberto; registrar resultado comprovado
  no relatório e o histórico detalhado no changelog.
