# Plano: Components com lado de editor ("Smart Components")

Status (2026-10-20): etapas 1 a 4 implementadas (ver "Feito"); 5 a 7 abertas.

## Feito

- **Etapa 1**: `obj.game.components.new("modulo.Classe")` devolve o component (sem precisar
  do objeto ativo; erro de import vira `RuntimeError` com a mensagem) e
  `obj.game.components.remove(comp)` (`rna_object.c`, struct `GameObjectComponents`).
- **Etapa 2**: `scripts/modules/range_args.py` (`from Range.args import ...`, real no editor e
  no jogo). `Float`/`Int`/`Bool`/`Text`/`Choice` são subclasses de `int`/`float`/`str` com
  `_range_meta`; `create_properties` lê `kind/min/max/tip/items`. DNA novo em
  `PythonComponentProperty`: `min`, `max`, `metaflag`, `tip[256]` (zero = sem dica, então
  arquivos antigos e da Range upstream não mudam). RNA: limites dinâmicos no `value`,
  `use_slider` e `description` (somente leitura); a dica aparece no tooltip do campo
  (`interface_region_tooltip.c`). `Choice` mantém a ordem declarada (o `set` não mantinha).
  `Header(...)` gera o `C_Header/Nome/Icone` de sempre. No Reload o valor fica e as dicas
  vêm do código novo.
- **Etapa 3**: `Object(tip=...)` = `CPROP_TYPE_OBJECT`, nome guardado em `strval`. No
  editor o `value` é um ponteiro para `Object` (seletor de objeto); `object_name` dá o nome.
  No jogo `KX_PythonComponent` troca o nome pelo `KX_GameObject` da cena (ou `None`) em
  `awake`/`start`/`update_args`. Renomear o objeto ainda solta o alvo (questão em aberto).
- **Etapa 4**: `requires` (`physics`, `components`) e classe `Editor` (`on_attach`, `on_change` com aviso
  por campo, `buttons`), em `scripts/modules/range_component_editor.py`; o C chama
  `BKE_python_component_attached` depois de adicionar. `on_change` valida todos os campos quando qualquer
  um muda (assim um aviso que depende de outro campo fica certo). `requires` só configura ao adicionar.
  Extra: `Scene(tip=...)` escolhe uma cena (no jogo chega o nome, para `logic.addScene`).

## Objetivo

Juntar a facilidade do component (um `.py`, aparece direto no objeto) com o poder
do addon (`bpy`, interface, viewport, construção do objeto), **sem** obrigar o
usuário a aprender nada novo para o caso simples.

Regra de ouro: **um component de hoje continua funcionando igual**. Cada recurso
novo é opcional e se aprende um de cada vez.

## O que já existe hoje (e motiva o plano)

- Editor importa o módulo com um `Range` falso (`load_component` em
  `blenkernel/intern/python_component.c`), lê `args` e descarta o módulo do
  `sys.modules`. Ou seja, o editor **já executa** o arquivo do component.
- `args` só aceita tipos básicos (bool, int, float, str, set, vetor, cor).
- A caixa é desenhada em Python (`GAME_PT_game_components` em
  `release/scripts/startup/bl_ui/properties_game.py`) e já tem convenções
  improvisadas por nome: `C_Header/Nome/Icone`, `C_Collapse`, `C_Icons`.
- Há casos especiais fixos no painel (`rigid_body_joint_component`) e um painel
  inteiro à parte para o Video Player. Cada component "rico" vira código na engine.
- `obj.game.components` não tem `new()`; addons precisam do operador +
  objeto ativo.

O plano transforma esses casos especiais em uma API pública.

## O que aprender das outras engines

| Engine | Recurso | Ideia que trazemos |
|---|---|---|
| Unity | `[Range]`, `[Tooltip]`, `[Header]`, `[Space]` | Campos com limite, dica e seção declarados no `args` |
| Unity | `OnValidate`, `Reset` | `on_change` e `on_attach` |
| Unity | `OnDrawGizmos` / `OnDrawGizmosSelected` | `draw_gizmo` |
| Unity | `[ContextMenu]`, Custom Editor | botões declarados e `draw_ui` opcional |
| Unity | `[RequireComponent]` | `requires` (física, outros components) |
| Godot | `@export_range`, `@export_node_path` | campo que aponta para outro objeto |
| Godot | `@tool` | código de editor no mesmo arquivo |
| Unreal | Construction Script | `on_attach` / `build` monta filhos e configura o objeto |

## Desenho da API (do mais fácil ao mais poderoso)

### Nível 0: como hoje

```python
class Patrulha(types.KX_PythonComponent):
    args = OrderedDict([("Velocidade", 2.0)])
```

### Nível 1: campos melhores (só declarativo, sem código de editor)

Helpers em `Range.args` que **continuam virando os mesmos tipos de hoje** no DNA,
com metadados extras:

```python
from Range.args import Float, Bool, Object, Header, Choice

class Patrulha(types.KX_PythonComponent):
    args = OrderedDict([
        Header("Movimento", icon="AUTO"),
        ("Velocidade", Float(2.0, min=0, max=20, tip="Metros por segundo")),
        ("Alvo",       Object(tip="Objeto que ele persegue")),
        ("Modo",       Choice("Andar", "Andar", "Correr")),
        Header("Combate"),
        ("Agressivo",  Bool(False)),
    ])
```

- `min`/`max` viram slider; `tip` vira tooltip.
- `Header` substitui o `C_Header/...` atual (o antigo continua aceito).
- `Object` é guardado como string (nome) e desenhado com `prop_search` na lista
  de objetos da cena: escolher o alvo com o mouse, sem digitar. No jogo,
  `args["Alvo"]` já chega como `KX_GameObject` (ou `None`).
- No jogo, `Float(2.0, ...)` chega como `2.0`. O script do jogo não muda.

Esse nível sozinho já é a maior melhoria de facilidade.

### Nível 2: o component "cuida de si" no editor

Uma classe interna `Editor`, opcional. O jogo nunca a chama; o editor nunca chama
`start`/`update`. Separação visível e fácil de explicar.

```python
class Patrulha(types.KX_PythonComponent):
    args = ...
    requires = {"physics": "DYNAMIC"}       # aplicado ao adicionar

    def start(self, args): ...
    def update(self): ...

    class Editor:
        def on_attach(self, obj):           # ao adicionar no objeto (Reset/Construction)
            obj["patrulha"] = True

        def on_change(self, obj, nome, valor):  # mexeu num campo (OnValidate)
            if nome == "Velocidade" and valor > 15:
                return "Muito rápido: o inimigo pode atravessar paredes"  # aviso na caixa

        buttons = [("Criar ponto de rota", "criar_ponto")]   # ContextMenu
        def criar_ponto(self, obj, context):
            import bpy
            bpy.ops.object.empty_add(location=obj.location)
```

- Retornar texto em `on_change` mostra um aviso amarelo na caixa (validação sem
  rodar o jogo).
- `buttons` cobre 90% dos casos sem desenhar UI na mão.
- `draw_ui(self, layout, obj, comp)` fica como escape para quem quer controle total.

### Nível 3: gizmos na viewport

```python
    class Editor:
        def draw_gizmo(self, obj, args, g, selected):   # args = valores atuais da caixa
            if selected:
                g.circle(obj.location, args["Raio"], color="AMARELO")
                if args["Alvo"]:
                    g.line(obj.location, args["Alvo"].location)
                g.text(obj.location, "Patrulha")
```

- API pequena (`line`, `circle`, `sphere`, `arrow`, `box`, `text`, `path`),
  desenhada por um único draw handler da engine.
- Por padrão só desenha com o objeto selecionado; toggle global no header da
  viewport ("Component Gizmos").

### Para addons

`obj.game.components.new("modulo.Classe")` e `.remove(comp)` no RNA, sem
depender do objeto ativo, retornando o component para preencher valores.

## Como funciona por dentro

1. **Leitura dos metadados**: `create_properties` (C) passa a reconhecer os
   helpers de `Range.args` (pela classe/atributos) e grava o valor padrão como
   hoje. Os metadados (min, max, tip, header, tipo Object) ficam num campo de
   texto/flag extra em `PythonComponentProperty` (mudança de DNA pequena, com
   default no versioning para arquivos antigos e Range upstream).
2. **Registro de editor em Python**: módulo novo `range_component_editor` em
   `release/scripts/modules/`. Importa o arquivo do component com o mesmo `Range`
   falso, guarda a classe `Editor` em cache por (módulo, mtime) e só reimporta no
   Reload ou quando o arquivo muda. Nunca importa a cada redesenho.
3. **Painel**: `GAME_PT_game_components` desenha campos com metadados, avisos,
   botões e chama `draw_ui` se existir. Os casos especiais atuais
   (rigid body joint, C_Header) migram para a API, provando que ela basta.
4. **Gizmos**: um `SpaceView3D.draw_handler_add` que percorre objetos
   selecionados com components que têm `draw_gizmo`, usando `bgl`.
5. **Proteção**: toda chamada ao `Editor` em `try/except`; erro vira um ícone
   vermelho na caixa com a mensagem e é mostrado uma vez no console. O editor
   nunca cai por causa de um component.
6. **Jogo exportado**: nada muda no runtime além de resolver `Object` para
   `KX_GameObject` e desembrulhar os helpers. A classe `Editor` é só um atributo
   ignorado; `bpy` só pode ser importado dentro dos métodos dela (o template e a
   doc deixam isso explícito).

## Etapas

| # | Entrega | Esforço | Ganho |
|---|---|---|---|
| 1 | `components.new()` / `.remove()` no RNA | pequeno | addons simples |
| 2 | `Range.args`: `Float/Int` com min/max/tip, `Header`, `Choice` | médio | grande, para todo mundo |
| 3 | Campo `Object` (escolher com o mouse, chega como objeto no jogo) | médio | muito grande |
| 4 | `Editor`: `on_attach`, `on_change` com aviso, `buttons`, `requires` | médio | grande |
| 5 | `draw_gizmo` + toggle na viewport | médio | grande para level design |
| 6 | `draw_ui` livre + migrar rigid body joint e Video Player para a API | médio | limpa a engine |
| 7 | Template "Smart Component" no Text Editor + página na doc da API | pequeno | aprendizado |

Cada etapa é testável sozinha e pode ser enviada separada. Recomendo 1 → 2 → 3
primeiro: sem código de editor nenhum, o usuário já ganha slider, dica, seções e
alvo escolhido com o mouse.

## Testes por etapa

- Arquivo com components antigos (incluindo `C_Header`) abre e mostra igual.
- Arquivo da Range upstream (1.6.1002) abre sem campos zerados errados.
- Component com erro em `on_change`/`draw_gizmo` não derruba o editor.
- Jogo exportado (Windows e Linux) roda o mesmo component sem `bpy`.
- `Object` apontando para objeto renomeado/apagado chega como `None` sem crash.

## Questões em aberto

- `Object` por nome quebra ao renomear; vale um ponteiro real no DNA (mais
  trabalho, mais robusto)? Sugestão: começar por nome e atualizar ao renomear
  via handler.
- `requires` deve só configurar ou também impedir remover a física depois?
- Gizmos rodando também durante o jogo no modo debug (como o `Show Debug
  Properties`)?
