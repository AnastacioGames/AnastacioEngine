# Plano: editor Mind Map

Estado: etapas 1-6 implementadas em 2026-11-09, aguardando aceite; etapa 7 não iniciada.

## Objetivo

Criar um editor de mapas mentais dentro da Anastacio Engine, com a rapidez de teclado do FreeMind: abrir,
digitar ideias e organizá-las em árvore sem tocar no mouse. O código é novo; o FreeMind serve só de referência
de comportamento e do formato `.mm`.

Fora do escopo inicial: colaboração, nuvem, anexos embutidos, uso dentro do jogo exportado e API `Range`.

## Decisões de arquitetura

| Tema | Decisão | Motivo |
|---|---|---|
| Forma | Novo tipo de área `SPACE_MINDMAP = 21`, em `editors/space_mindmap/` | O mapa não é um grafo de nós com sockets; navegação e edição são próprias |
| Por que não Node Editor | Não usar `bNodeTree` customizado | Layout em árvore, dobra de ramos e edição direta brigariam com o editor de nós |
| Dados no `.range` | Cada mapa é um datablock `Text` com XML `.mm`, nome `*.mm` | Evita novo tipo de ID e versioning de dados; ganha save, append e undo existentes |
| Em memória | Árvore runtime em `SpaceMindMap`, sem gravar em DNA | Desenho e navegação rápidos; o `Text` é a fonte da verdade |
| Sincronização | Cada operação concluída serializa no `Text` e faz um passo de undo | O undo global restaura o texto, e o editor reconstrói a árvore |
| Desenho | `View2D` + BLF + funções GL já usadas pelos editores 2D | Nitidez com zoom e escala de UI, sem dependência nova |
| Dobra de ramos | Atributo `FOLDED` do próprio `.mm` | Compatível com o FreeMind |

Edição manual do `Text` é permitida: ao recarregar, XML inválido não pode travar nem sobrescrever o conteúdo. O
editor mostra o erro e fica em modo somente leitura até o texto ser corrigido.

## Pontos de integração conferidos no código

- Enum e struct: `makesdna/DNA_space_types.h` (`eSpace_Type`, hoje termina em `SPACE_CLIP = 20`).
- Registro: `editors/space_api/spacetypes.c` (`ED_spacetypes_init`), modelo em `editors/space_logic/space_logic.c`.
- Menu de editores: `editors/screen/area.c` (`scripting_editors`).
- Arquivo: `blenloader/intern/readfile.c` e `writefile.c`, nos ramos por `spacetype`.
- RNA: `makesrna/intern/rna_space.c` e registro de `SpaceMindMap` em `python/intern/bpy_rna_callback.c`.
- Tema: `editors/interface/resources.c`, se forem criadas cores próprias.

Verificar na etapa 1: stubs do Runtime, build Web (`__EMSCRIPTEN__`) e abertura de `.range` com a área nova em
versões anteriores da engine.

## Etapas

Cada etapa termina em build e parada para aceite, conforme o `AGENTS.md`.

### 1. Área vazia
Registrar o editor, ícone, menu, salvar e reabrir o layout. **Build limpo obrigatório**, pois altera DNA.
Aceite: a área aparece no menu e persiste no `.range`; `RangeRuntime` continua linkando.

### 2. Modelo, leitura e gravação
Árvore em memória, parser e escritor de `.mm`, em arquivo C sem dependência de UI. Preservar atributos
desconhecidos e nós `richcontent`, para não perder dados de mapas externos.
Aceite: testes de ida e volta com mapas reais do FreeMind, UTF-8 e acentos, entidades XML, arquivo inválido.

### 3. Layout e desenho
Raiz no centro, filhos à direita e à esquerda, linhas curvas, zoom e pan, enquadrar tudo (`Home`).
Aceite com janela: 1.000 nós fluidos, texto nítido em escala de UI alta.

### 4. Edição pelo teclado

| Tecla | Ação |
|---|---|
| `Insert` | Novo filho, já editando |
| `Enter` | Novo irmão, já editando |
| `F2` | Editar a ideia |
| `Delete` | Apagar o ramo |
| Setas | Navegar |
| `Espaço` | Dobrar ou abrir |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Desfazer e refazer |

Aceite com janela: montar um mapa de 30 ideias sem mouse, com acentos, e desfazer tudo.

### 5. Mouse e reorganização
Selecionar, arrastar ramo para outro pai, reordenar irmãos, menu de contexto, dobrar pelo indicador.
Aceite com janela: arrastar nunca cria ciclo nem perde ramo.

### 6. Arquivos e aparência
Novo mapa, seletor de mapas, importar e exportar `.mm`, cor, ícones básicos e nota por ideia. Atualizar
traduções e documentação.
Aceite: arquivo exportado abre no FreeMind; mapa volta intacto após salvar o `.range`.

**Fim da versão 1.**

### 7. Integração com a engine (versão 2)
Ligar ideia a objeto, cena, `Text`/script; clique abre o alvo. Ideias como tarefas, com progresso por ramo.
Os vínculos ficam em atributos próprios do `.mm`, ignoráveis por outros programas.

## Riscos

| Risco | Tratamento |
|---|---|
| Edição de texto acentuado dentro da caixa | Reaproveitar o campo de texto da UI; validar logo na etapa 4 |
| Serializar mapa grande a cada ação | Medir com 5.000 nós; se pesar, gravar ao concluir grupos de ações |
| Undo global trocar o `Text` sob o editor | Reconstruir a árvore por ponteiro e por marca de alteração; testar na etapa 4 |
| Área nova em `.range` aberto por versão antiga | Testar na etapa 1 antes de seguir |
| Atalhos conflitarem com os globais | Keymap próprio, ativo só com o cursor na área |

## Ao concluir

Atualizar `relatorio-melhorias-anastacioengine.md`, `docs/changelog.md` e `docs/roadmap.md`, e rodar
`python tools/check_docs.py`.
