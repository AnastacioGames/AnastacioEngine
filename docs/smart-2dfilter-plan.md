# Plano: Smart Modules — etapa 2: Smart 2D Filter

Branch `smart-modules-2dfilter` (worktree `D:\AnastacioEngine-smart2d`, junction `lib` → `D:\AnastacioEngine\lib`;
remover só a junction com `rmdir` antes do `git worktree remove`). Base: `main` em c8d7f2c9, com o Choice do
GLSL Script já mesclado (ver `docs/smart-node-choice-plan.md`).

## Problema

O atuador 2D Filter > Custom Filter mostra só Pass, Text e Mipmap. Os uniforms do shader
(`uniform float u_threshold;`) são alimentados por **propriedades de jogo com o mesmo nome**
(`RAS_2DFilter.cpp`, `m_propertiesLoc`), que o usuário cria à mão sem saber nome exato, tipo, limites ou padrão.
Os templates (`templates_glsl/filtro2d_*.glsl`) contornam isso com "valor 0 usa o padrão".

## Ideia

Igual ao nó GLSL Script: o código descreve a interface. No painel do atuador Custom Filter, listar os uniforms
do Text com as mesmas anotações (`@min @max @default @choice`) e desenhar cada um como campo/slider/menu,
**editando a propriedade de jogo do objeto** (o transporte que o runtime já usa). Sem mudança no runtime nem no
DNA: o valor continua salvo como propriedade de jogo.

## Contrato v1 (proposta — Codex revisa antes do código)

- Uniforms de topo, tipo `float` ou `int`, nome sem prefixo `bgl_`. Outros tipos (bool, vec/sampler) são
  ignorados nesta versão (listados como "não editável").
- Anotações iguais às do GLSL Script: `@min`, `@max`, `@default`, `@choice Rótulo=int,...` com as mesmas regras
  de validação do Choice v1 (inválido → campo numérico comum).
- Propriedade existente com o mesmo nome: o painel edita ela. Tipo diferente do uniform → mostrar aviso, não
  converter.
- Propriedade ausente: mostrar o uniform com botão "+" (cria só aquela) e um botão "Create Missing" (cria todas),
  com tipo `float`→Float, `int`→Int (`@choice` também) e valor `@default` (sem default: 0/primeira
  opção). Nunca criar sozinho ao desenhar.
- Choice: menu com os rótulos; valor fora da lista mostra "Valor fora das opções: n".
- `@min/@max` num float com os dois limites → slider. Fora dos limites o valor não é cortado (só o arrasto).
- O parsing roda no redraw do Logic Editor só para atuadores Custom Filter abertos; o Text é pequeno. Se medir
  lento, cachear por `Text` + contador de edição.

### Revisão do Codex (2026-10-21)

Contrato aprovado com estes esclarecimentos para a implementação:

- O nome precisa ser um identificador GLSL válido (primeiro caractere letra ou `_`; os demais letra, dígito ou
  `_`). A leitura não deve expor um campo de painel para uma declaração malformada.
- `@choice` é um menu somente para `int` e `float`. `bool` fica como "Não editável nesta versão": hoje
  `RAS_2DFilter` só envia Game Properties int/float para uniforms, portanto expor uma caixa Boolean exigiria
  mudança de runtime e foge deste experimento. Para `int`, o valor inicial é inteiro; para `float`, ele
  permanece float.
- `@min`/`@max` são um slider somente de `float`. Se ambos estiverem presentes, `min <= max` é obrigatório;
  anotações inválidas não bloqueiam o shader e caem no campo numérico comum.
- Vetores, matrizes e samplers aparecem em uma linha de aviso "Não editável nesta versão", em vez de sumirem:
  isso explica por que `u_tint` não ganha uma property. Eles nunca entram em `Create Missing`.
- O painel não cria nem altera properties durante o redraw. `+` e `Create Missing` são as únicas ações de criação;
  elas preservam properties existentes, inclusive valor fora de Choice e tipo incompatível.

### Critérios da revisão do diff C

Antes de aprovar o código C, confirmar estes pontos na implementação:

1. `logic_filter2d_uniforms` separa uniforms editáveis (`float`/`int`) dos demais. O painel mostra os
   demais, inclusive `bool`, como não editáveis e o operador jamais cria uma Game Property para eles.
2. A criação de uma property só aceita um `@default` escalar válido para o tipo; em especial, um int não
   arredonda silenciosamente um default fracionário.
3. Um par `@min/@max` invertido não cria slider. O mesmo critério precisa preservar o comportamento do GLSL
   Script depois da extração do parser compartilhado.
4. A leitura exige identificador GLSL válido e não converte nem recria property preexistente de tipo diferente.
5. A regressão do Choice do GLSL Script, a cena Smart 2D Filter e a compilação GLSL no player precisam passar
   antes do teste visual.

## Código comum (o "segundo consumidor" que justifica extrair)

`source/blender/blenkernel/BKE_glsl_uniforms.h` + `intern/glsl_uniforms.c`: leitura dos uniforms de topo e das
anotações, e o `choice_build` validado, hoje dentro de `node_shader_glsl_script.c`. O nó passa a usar o módulo
(sem mudar comportamento — conferido pela cena e inspetor do Choice já existentes). O 2D Filter usa o mesmo.

## Divisão

**Claude (partes grandes, C):**
1. Extrair o parser/anotações/choice para `BKE_glsl_uniforms`, migrar o nó, regressão com
   `tools/debug/cenas/inspecionar_cena_smart_node_choice.py`.
2. Painel no `draw_actuator_filter_2d` (`editors/space_logic/logic_window.c`): lista, slider, menu Choice,
   avisos.
3. Operador `LOGIC_OT_filter2d_property_add` (uma ou todas as faltantes) em `logic_ops.c`.
4. Build, verificação em background (criar propriedades via operador, conferir tipo/valor), teste visual com o
   usuário.

**Codex (partes pequenas):**
1. Revisar o contrato v1 acima antes do código (tipos, regra de propriedade existente/ausente, nomes de botões).
2. Anotar os 4 templates `source/release/scripts/templates_glsl/filtro2d_*.glsl` (`@min/@max/@default`, e
   `@choice` onde fizer sentido), mantendo o "0 usa o padrão" para cenas antigas.
3. Cena de teste + inspetor em `tools/debug/cenas/` (objeto com Custom Filter: propriedade existente certa,
   ausente, com tipo errado, Choice).
4. Docs (`docs/` dos 2D filters + changelog) e revisão do diff do Claude.

Merge no `main` só após o teste visual com o usuário. Commits pequenos por etapa.

## Fora do escopo

Object/Scene como uniform (ponte CPU→GPU), Text Editor/Python com campos, menu no painel "Script Uniforms" do
material — ficam para etapas seguintes.
