Analise o código-fonte da Range Engine e localize a implementação do menu "Editor Type", mostrado ao clicar no seletor de tipo de editor.

IMPORTANTE:
Antes de modificar qualquer coisa, identifique como esse menu é construído atualmente no código-fonte. Não presuma nomes de arquivos, classes ou funções.

OBJETIVO

Quero reorganizar o menu "Editor Type" para reduzir a quantidade de itens exibidos na primeira página.

Atualmente existem vários editores exibidos juntos no mesmo menu.

Quero criar duas abas no topo do popup:

[ Editor Type ] [ More Editors ]

A aba "Editor Type" deve ser a aba padrão ao abrir o menu.

--------------------------------------------------
ABA 1 — EDITOR TYPE
--------------------------------------------------

Manter somente estes itens:

GENERAL
- 3D View
- UV/Image Editor
- Node Editor

ANIMATION
- Timeline
- Graph Editor
- Dope Sheet

SCRIPTING / DATA
- Text Editor
- Logic Bricks Editor
- Outliner
- Properties

O item "File Browser" NÃO deve permanecer nesta aba.

--------------------------------------------------
ABA 2 — MORE EDITORS
--------------------------------------------------

Mover para esta aba:

- Video Sequencer
- Movie Clip Editor
- NLA Editor
- Python Console
- Info
- User Preferences
- File Browser

Esses itens não devem aparecer duplicados na aba principal.

--------------------------------------------------
COMPORTAMENTO
--------------------------------------------------

1. Ao clicar no seletor de Editor Type, abrir o popup normalmente.

2. No topo do popup devem existir duas abas:

   Editor Type | More Editors

3. "Editor Type" deve estar selecionada inicialmente.

4. Clicar em "More Editors" deve trocar o conteúdo dentro do MESMO popup.

5. Clicar novamente em "Editor Type" deve retornar à lista principal.

6. A troca de aba não deve abrir outro popup ou submenu.

7. Selecionar qualquer editor deve continuar executando exatamente o comportamento atual de troca do tipo de área/editor.

8. Não alterar os identificadores internos dos editores.

9. Não remover nenhuma funcionalidade existente.

10. Os atalhos de teclado "Shift + ..." não devem ser exibidos nesse menu.

--------------------------------------------------
VISUAL
--------------------------------------------------

Preserve ao máximo o estilo visual atual da Range Engine/Blender dessa versão:

- mesmas cores;
- mesmos ícones;
- mesma fonte;
- mesmo tamanho aproximado dos itens;
- mesmos estados de hover;
- mesmo comportamento de seleção;
- mesmo estilo do popup.

As abas devem parecer parte nativa dessa interface, e não um elemento de UI moderno incompatível com o restante da engine.

A primeira página deve ficar visualmente mais compacta devido à remoção dos editores menos utilizados.

Organização sugerida:

┌──────────────────────────────────────────────────────────┐
│ Editor Type │ More Editors                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ General          Animation          Scripting / Data     │
│                                                          │
│ 3D View          Timeline           Text Editor          │
│ UV/Image Editor  Graph Editor       Logic Bricks Editor  │
│ Node Editor      Dope Sheet         Outliner             │
│                                     Properties           │
│                                                          │
└──────────────────────────────────────────────────────────┘

Na aba More Editors:

┌──────────────────────────────────────────────────────────┐
│ Editor Type │ More Editors                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Video Sequencer                                          │
│ Movie Clip Editor                                        │
│ NLA Editor                                               │
│ Python Console                                           │
│ Info                                                     │
│ User Preferences                                         │
│ File Browser                                             │
│                                                          │
└──────────────────────────────────────────────────────────┘

--------------------------------------------------
IMPLEMENTAÇÃO
--------------------------------------------------

PLANO DE EXECUÇÃO CONFIRMADO NO CÓDIGO

Auditoria inicial (somente leitura):

- O seletor do cabeçalho é criado por `ED_area_header_switchbutton()` em
  `source/source/blender/editors/screen/area.c`.
- O botão é um `UI_BTYPE_MENU` ligado à propriedade RNA `Area.type`; a troca
  continua passando por `rna_Area_type_set()`/`rna_Area_type_update()` em
  `source/source/blender/makesrna/intern/rna_screen.c`.
- Nomes, identificadores e ícones vêm de `rna_enum_space_type_items` em
  `source/source/blender/makesrna/intern/rna_space.c`.
- Filtrar a enumeração RNA isoladamente não cria duas abas no mesmo popup; a
  implementação deve desenhar o menu explicitamente e reutilizar `Area.type`.

Implementação proposta:

1. Criar duas listas locais de itens, preservando valores `SPACE_*`, rótulos e
   ícones existentes. A principal terá 3D View, UV/Image Editor, Node Editor,
   Timeline, Graph Editor, Dope Sheet, Text Editor, Logic Bricks Editor,
   Outliner e Properties.
2. Mover para More Editors Video Sequencer, Movie Clip Editor, NLA Editor,
   Python Console, Info, User Preferences e File Browser, sem duplicatas.
3. Substituir somente o desenho do popup acionado por
   `ED_area_header_switchbutton()`, com dois botões nativos no topo e estado
   local iniciando em Editor Type a cada abertura.
4. Cada item deve usar o mesmo caminho RNA de atualização de `Area.type`, sem
   alterar identificadores gravados em `.blend` ou keymaps.
5. Ocultar atalhos `Shift + ...` apenas neste popup e preservar tema, métricas,
   hover, seleção, ícones e fechamento do menu.

Arquivos previstos: `editors/screen/area.c`; `makesrna/intern/rna_screen.c` e
`rna_space.c` somente se necessário para metadata; headers apenas se uma
declaração compartilhada for inevitável. Roadmap/changelog só após aceite.

Validação: build de `RangeEngine` com MSVC/Ninja; testar ambas as abas no mesmo
popup, cada editor, ausência de duplicatas/atalhos e persistência de
identificadores em salvar/reabrir `.blend`; concluir com teste visual real.

Riscos: Blender 2.79 pode não ter abas prontas, exigindo botões nativos no
popup. Evitar alterar a enumeração RNA global. O add-on legado
`cutscene_timeline_editor` permanece fora deste plano e deve ficar desativado.

**AUDITORIA COMPLETADA — 2026-09-09**

Localizações identificadas:
1. `source/source/blender/editors/screen/area.c` (linhas 1824-1837)
   - `ED_area_header_switchbutton()` cria o botão via `uiDefButR`
   - Liga diretamente à propriedade RNA `Area.type`

2. `source/source/blender/makesrna/intern/rna_space.c` (linhas 57-93)
   - `rna_enum_space_type_items[]` enum define todos os 16 editores
   - Suporta callback itemf para filtragem dinâmica

3. `source/source/blender/editors/interface/interface_region_menu_popup.c`
   - Sistema de popup menu nativo com padrão de memória hash (linhas 112-151)

**ABORDAGENS INVESTIGADAS**

A. **RNA Enum Callback** (mais integrado)
   - Filtra lista de itens dinamicamente
   - ❌ Não mantém popup aberto para troca de abas
   - Útil só para reorganizar sem abas visíveis

B. **uiBlockCreateFunc Custom** (permite abas dinâmicas)
   - Cria popup customizado com abas visíveis
   - ✅ Mantém popup aberto
   - ✅ Permite troca de conteúdo via clique
   - ⚠️ Requer gerenciar state persistence e evento handling
   - Requer substituir `uiDefButR` por `uiDefBlockBut`

C. **Dois Filtros Enum Separados** (mais simples)
   - ✅ Sem mudança arquitetural do popup
   - ❌ Abre dois menus separados (não abas)

**DESAFIO TÉCNICO**

Abas visíveis com conteúdo dinâmico no mesmo popup exigem:
- Custom event handling dentro do popup
- State persistence (qual aba está ativa)
- Redraw condicional de itens
- Isso não é suportado nativamente por `uiDefButR` com RNA enum

Antes de editar (quando implementado):

1. Localize a implementação atual do menu Editor Type. ✅ (identificado em area.c:1824)
2. Identifique como os itens são registrados/desenhados. ✅ (RNA enum em rna_space.c:57)
3. Identifique como o clique em cada item altera o Space/Editor Type. ✅ (rna_Area_type_set em rna_screen.c)
4. Identifique como os ícones são associados aos itens. ✅ (ICON_* constantes no enum)
5. Verifique se permite abas sem duplicar. ❓ Requer modificação arquitetural

**RECOMENDAÇÃO PARA IMPLEMENTAÇÃO**

Para manter a qualidade e evitar regressões:

- **Fase 1 (mínima, hoje possível):** Reorganizar enum para mostrar main editors primeiro na lista
  - Modifica apenas `rna_enum_space_type_items` em rna_space.c
  - Resultado visual: primeira página mais compacta (sem abas visíveis)
  
- **Fase 2 (completa, requer refator):** Implementar abas visíveis com uiBlockCreateFunc
  - Maior esforço (state machine, event handling, tab button drawing)
  - Afeta: area.c (ED_area_header_switchbutton substituição), nova função de block callback
  - Requer testes: múltiplas áreas abertas, persistência de tab state

Nota: Blender 2.79 pode ter limitações de UI para abas dinâmicas; validar com Range Engine actual.

--------------------------------------------------
VALIDAÇÃO
--------------------------------------------------

Depois da implementação, verifique:

- Editor Type abre normalmente.
- Editor Type é a aba inicial.
- More Editors troca o conteúdo corretamente.
- Nenhum editor foi perdido.
- Nenhum editor aparece duplicado.
- File Browser aparece somente em More Editors.
- Video Sequencer aparece somente em More Editors.
- Movie Clip Editor aparece somente em More Editors.
- NLA Editor aparece somente em More Editors.
- Python Console aparece somente em More Editors.
- Info aparece somente em More Editors.
- User Preferences aparece somente em More Editors.
- Os atalhos Shift não aparecem.
- Todos os ícones continuam corretos.
- Todos os editores continuam abrindo corretamente.
- Não houve regressão no seletor de Editor Type.

Ao terminar, informe:

1. quais arquivos foram modificados;
2. quais funções/classes foram modificadas;
3. como o estado das duas abas foi implementado;
4. se foi necessário criar alguma nova estrutura;
5. possíveis riscos ou limitações;
6. um resumo curto das alterações realizadas.
