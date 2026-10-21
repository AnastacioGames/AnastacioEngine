# Plano: Smart Modules Editor — rev. 2 (após revisão do Codex)

## Contexto

O Smart Component (a44e6561) mostrou que interface declarativa (`Range.args` em
`source/release/scripts/modules/range_args.py`) melhora muito a autoria. A pergunta foi se isso vira um padrão
para outros editores ("Smart Modules"). O nó GLSL Script (`node_shader_glsl_script.c`) já gera sockets a partir
do código, então o Node Editor é o candidato natural.

Revisão do Codex (aceita):
- O **padrão** é parecido, mas os **parsers** são diferentes: Component reflete objetos Python (`_range_meta`);
  GLSL Script interpreta texto GLSL + comentários. Compartilhar o *formato* de metadados pode fazer sentido;
  compartilhar a reflexão Python, não.
- Extrair `get_range_meta`/`apply_range_meta` (`python_component.c:225`) não gera um núcleo genérico:
  `get_range_meta` depende de Python e `apply_range_meta` preenche só `min`/`max`/`tip` num
  `PythonComponentProperty`; Choice/Object/Scene são tratados em `create_properties`.
- Object/Scene num shader exigem definir comportamento (posição? transform? atualiza no jogo?) e uma ponte
  CPU→GPU. Fora do escopo inicial.
- A UI do Component fica em `source/release/scripts/startup/bl_ui/properties_game.py:143` (via RNA), não em
  `buttons_object.c`.

## Decisão

Opção B como **experimento restrito à autoria de shaders**. Sem núcleo compartilhado, sem node tree novo,
sem tipos de socket novos até um experimento mostrar que são necessários. "Smart Modules" fica como direção, não
como arquitetura: só se extrai código comum quando houver um segundo consumidor real.

## Etapas

1. **Exemplo útil + contrato do Choice** (só documento): escolher um caso real (ex.: modo de mistura ou de
   padrão num GLSL Script) e definir:
   - sintaxe da anotação no GLSL, com valores explícitos por opção (ex.: `// choice: Linear=0, Smooth=1, Step=2`);
   - o Choice é um **uniform numérico existente** (int/float) desenhado como dropdown;
   - regra quando o socket está ligado (dropdown some/desabilita; vale o valor do link);
   - default, valor inválido e arquivo antigo sem anotação (continua número cru).
   Revisar o contrato com o Codex antes de codar.
2. **Protótipo do Choice** em `node_shader_glsl_script.c`: parsing da anotação, guardar as opções, dropdown no
   desenho do nó (`drawnode.c`), sem DNA de socket novo se der para guardar no próprio nó/socket existente.
   Aproveitar o suporte parcial que já existe para cor, vetor, limites e defaults.
3. **Avaliar**: se o Choice precisar de algo que o socket numérico não comporta, aí sim propor tipo novo.
   Só depois discutir Object/Scene (com o contrato CPU→GPU definido) e uma eventual extração de código comum.
4. **Docs**: seção no `docs/shader-nodes.md` + entrada no changelog.

## Contrato do Choice v1 — revisão Codex (2026-10-21)

Formato aprovado para iniciar o protótipo:

```glsl
uniform int u_mode; // @choice Linear=0, Smooth=1, Step=2 @default 1
```

- Somente uniforms escalares `u_` de tipo `int` ou `float`. O socket continua numérico;
  selecionar uma opção grava seu valor explícito, nunca a posição dela no menu.
- Uma declaração por linha; `@choice` aparece no comentário final, no máximo uma vez.
  A lista termina na próxima anotação `@` ou no fim da linha. A ordem das anotações é livre.
- Itens separados por vírgula, cada um `Rótulo=inteiro_decimal`, com espaços opcionais.
  Rótulos podem conter espaços e UTF-8; não podem conter `,`, `=`, `@` nem ser vazios.
  Sem aspas ou escapes nesta versão. Rótulos e valores devem ser únicos.
- Valores são inteiros entre -16777216 e 16777216, inclusive, exatamente representáveis
  pelo float usado no socket atual. Sem frações, expoentes, NaN ou infinito nesta versão.
  Exigir pelo menos uma opção. Limites internos de quantidade/tamanho devem ser documentados;
  excedê-los invalida a anotação inteira, sem truncamento silencioso.
- Socket novo: `@default` deve corresponder a uma opção; sem `@default`, usar a primeira.
  Default incompatível invalida o Choice: manter o comportamento numérico preexistente.
  `@min`/`@max`, quando presentes, devem aceitar todas as opções e o default; caso contrário,
  invalidar o Choice. Anotação inválida não impede a compilação do GLSL.
- Socket existente: preservar valor e links ao adicionar, remover, reordenar ou renomear opções.
  Não reaplicar default. Valor salvo fora da lista permanece intacto, indicado como
  `Valor fora das opções: <n>`; o menu permite escolher uma opção válida explicitamente.
  Isso também vale se o jogo alterar o uniform por `setScriptUniform`.
- Socket ligado: ocultar o dropdown, respeitando o desenho normal de sockets ligados;
  o valor da ligação prevalece, sem validação contra a lista. Desligar recupera o valor local.
- Remover `@choice`, ou encontrar sintaxe inválida, volta ao campo numérico. Não recriar
  o socket apenas por mudança das opções; preservar também seu identificador e subtipo.
  Arquivos antigos sem anotação mantêm o comportamento anterior.
- Metadados podem ser reconstruídos a partir do Text; o valor continua salvo no socket.
  Não interpretar Python e não fazer parsing de todo o Text a cada redraw para montar o menu.
- Caso de demonstração: `u_mode` seleciona uma interpolação Linear/Smooth/Step com efeito
  observável no material. Cobrir também valores não sequenciais (ex.: 2, 7, 12), reordenação,
  valor fora da lista, ligação/desligamento, anotação malformada e salvar/reabrir.

A aprovação é do contrato para o protótipo, não da implementação ainda inexistente.
Código gerado comprova o mapeamento; confirmar upload do valor exige execução do caminho
de renderização e evidência apropriada, não apenas inspeção do código gerado.

## Branch e divisão do trabalho

- Branch `smart-node-choice` a partir do `main`, num **worktree separado** (o usuário continua usando a engine
  do `main`). Build do worktree em pasta própria. Ao remover o worktree no fim: tirar a junction `lib` antes
  do `git worktree remove`.
- **Claude (partes grandes):** etapa 2 inteira — parsing da anotação e update dos sockets no
  `node_shader_glsl_script.c`, dropdown no `drawnode.c`, conferir o uniform no `gpu_codegen.c`, build e
  verificação de compilação (item 2 da verificação); etapa 3 (avaliação).
- **Codex (partes pequenas):** revisar o contrato do Choice (etapa 1) antes do código; montar as cenas de teste
  (GLSL antigo + Choice); docs (`shader-nodes.md` + changelog); revisar o diff de Claude no branch.
- Commits pequenos e separados por etapa no branch; merge no `main` só após o teste visual com o usuário.

## Arquivos

- `source/source/blender/nodes/shader/nodes/node_shader_glsl_script.c` (parsing e update dos sockets)
- `source/source/blender/editors/space_node/drawnode.c` (dropdown no nó)
- `source/source/blender/gpu/intern/gpu_codegen.c` (conferir que o valor chega como uniform)
- `docs/shader-nodes.md`
- Referência, sem alterar: `range_args.py`, `python_component.c`, `properties_game.py`

## Verificação (separada)

1. **Editor**: cena de teste (skill `cena-de-teste`) com GLSL Script antigo (regressão) e um com Choice —
   dropdown aparece, valor persiste ao salvar/reabrir, arquivo antigo abre igual.
2. **Compilação**: o GLSL compila e o uniform recebe o valor da opção (Show Generated Code / log), sem abrir o jogo.
3. **Visual em execução**: trocar a opção e ver o efeito no material — etapa combinada com o usuário (regra de
   não abrir o jogo sem pedido).

Build com a skill `build-anastacio` após cada passo em C.
