# Baked Lighting moderno

Data: 2026-10-15. Estado: etapas 1 e 2 implementadas; acabamento da etapa 3 em andamento. AO foi validado visualmente pelo usuário em Play e
Standalone; o usuário também testou Static Lighting + Shadows e confirmou a participação dos objetos Static.

## Objetivo

Transformar **Render > Baked Lighting** no fluxo oficial de bake da Anastacio Engine: automático, integrado
ao PBR do jogo e sem exigir que o usuário crie imagens, prepare um nó de imagem ou abra o UV/Image Editor.
O baker legado do Blender continua disponível apenas para mapas de textura especializados, como Normal e
Displacement; ele não é a base desta evolução.

O comportamento atual deve permanecer o padrão e continuar abrindo arquivos existentes sem mudança visual.
Hoje ele cria a UV `Lightmap`, empacota um atlas da cena, grava a iluminação indireta das lâmpadas e a luz
direta do World/emissivos, aplica OIDN e salva uma imagem RGBM packed. Luz direta e sombras das lâmpadas
continuam dinâmicas no jogo.

## Contrato dos modos

| Modo na interface | Conteúdo do atlas | Comportamento no jogo |
|---|---|---|
| **Indirect + Dynamic Shadows** | Comportamento atual: rebotes das lâmpadas e World/emissivos | Substitui somente o ambiente difuso; luz direta, especular e sombras continuam em tempo real |
| **Ambient Occlusion** | AO linear em escala de cinza, com distância e intensidade configuráveis | Multiplica somente o ambiente difuso; não escurece novamente a contribuição direta das lâmpadas |
| **Static Lighting + Shadows** | Irradiância direta e indireta das lâmpadas, World/emissivos e suas sombras estáticas | Nos receptores presentes no atlas, substitui o ambiente e a luz difusa direta; especular pode continuar dinâmica |

Não haverá um modo isolado chamado **Shadow Map** na primeira versão. Uma máscara única de sombra não
representa corretamente várias luzes com cores e intensidades diferentes. Para o usuário, sombras baked
fazem parte de **Static Lighting + Shadows**.

O modo estático assume cenário, lâmpadas e casters imóveis. Objetos móveis continuam recebendo luz direta e
sombras em tempo real. A sombra de um objeto móvel sobre um receptor estático não entra no atlas e não será
somada artificialmente depois.

## Interface

O painel mostra primeiro o que o usuário quer produzir e somente depois os controles relevantes:

```text
Baked Lighting

Current: Indirect + Dynamic Shadows       Use in Game [x]

Bake Mode:  Indirect + Dynamic Shadows

Lightmap
  Resolution  1024       GPU       [x]
  Samples       80       Denoise   [x]
  World Light  [x]

Moving Objects
  Bake Light Volume [x]
  Probe Spacing       1 m

Advanced
  Margin              4 px
  Active Object Scale 1.0

[ Bake Scene ]                                  [ Clear ]
```

- **Current** descreve o conteúdo realmente gravado, não a opção selecionada para o próximo bake.
- Opções sem efeito no modo escolhido ficam ocultas, em vez de apenas desabilitadas.
- AO mostra `Distance` e `Strength`; não mostra Light Volume.
- Static Lighting informa que luzes/casters precisam permanecer imóveis e mantém o Light Volume apenas com
  iluminação indireta para os objetos móveis.
- O botão continua sendo uma operação única para a cena. UV, atlas, imagens, packing e aplicação no jogo são
  automáticos.
- Mensagens de validação devem dizer o que falta e como corrigir, preservando o resultado anterior quando o
  novo bake falhar.

O painel inferior se chama **Texture Bake (Legacy)**, fechado por padrão, com uma mensagem curta apontando
Baked Lighting para iluminação do jogo. Ele permanece para Normal, Displacement e transferências entre malhas.
O painel moderno mostra objetos incluídos/excluídos, motivos da exclusão, cobertura do atlas depois do bake
e um controle por objeto para receber a lightmap no próximo bake. Um objeto estático excluído como receptor
ainda pode projetar sombra baked. O botão Clear tem texto explícito.

## Dados e compatibilidade

Devem existir dois estados independentes:

- `settings.mode`: escolha para o próximo bake;
- `Scene.ae_lightmap_mode`: tipo do resultado que foi concluído e aplicado.

Trocar `settings.mode` nunca reinterpreta a imagem atual. `ae_lightmap_mode` só muda no commit de um bake
bem-sucedido. Arquivos sem essa propriedade são tratados como **Indirect + Dynamic Shadows**, preservando o
resultado atual. `Clear` remove imagem, volume e modo ativo como já remove a lightmap.

A primeira versão mantém um único atlas ativo (`AE_lightmap`) e o RGBM atual. Assim não acrescenta uma
textura no runtime e conserva o limite atual de uma textura em Web/Android. AO é codificado em RGBM como um
valor linear em escala de cinza; uma otimização de formato só deve ser considerada depois de medir memória e
compatibilidade.

Alterar `Use in Game` ou concluir/limpar um bake deve invalidar os materiais PBR relevantes. O shader não
pode depender de uma recompilação incidental.

## Implementação técnica

### Modo indireto

É a referência de regressão. A sequência existente em
`source/release/scripts/startup/bl_operators/anastacio_lightmap.py` permanece semanticamente igual:

1. `DIFFUSE/INDIRECT` com as lâmpadas temporariamente adaptadas às unidades/falloff do jogo;
2. `DIFFUSE/DIRECT` com lâmpadas escondidas para World e emissivos;
3. soma, dilatação, denoise, RGBM e imagem packed;
4. Light Volume com as mesmas contribuições indiretas/ambientais.

Refatorações precisam ser comparadas numericamente com uma lightmap produzida antes da mudança.

### Modo AO

O mesmo atlas e o mesmo alvo temporário recebem o passe Cycles `AO`. Durante o passe, distância e intensidade
de AO são aplicadas temporariamente e todas as configurações alteradas são restauradas em `finally`.
O resultado é dilatado/denoised e gravado somente após validação.

No Principled, AO multiplica a parcela ambiente que viria do World/probe ou do ambiente constante. Luz direta,
especular e shadow maps permanecem intactos. Light Volume não é criado nesse modo. AO baked não torna o
receptor inelegível para SSGI; a exclusão atual do SSGI continua reservada para receptores que já receberam GI.

### Modo estático

O atlas recebe o passe difuso `DIRECT + INDIRECT` com as lâmpadas presentes e adaptadas ao jogo. Esse passe já
contém as sombras dos casters estáticos. Nos pixels cobertos pelo atlas, o shader:

1. usa a irradiância baked como parcela difusa;
2. não soma novamente o difuso direto das lâmpadas;
3. pode manter a parcela especular das lâmpadas em tempo real;
4. mantém o comportamento dinâmico completo nos objetos fora do atlas.

O Light Volume continua armazenando somente indireta/World, porque objetos móveis ainda recebem as lâmpadas
diretas em tempo real. Portanto atlas e volume não podem compartilhar cegamente os mesmos passes neste modo.

O contrato do shader deve distinguir explicitamente **cobertura do atlas** de **amostra do Light Volume**.
Hoje ambos terminam com `lightmap.a = 1`; usar valores mágicos diferentes no alpha seria frágil. A função de
amostragem deve entregar irradiância e origem/cobertura em saídas separadas, usadas tanto pelo loop de luzes
quanto pela elegibilidade do SSGI.

A primeira entrega é deliberadamente por cena: todas as lâmpadas que participam do bake são estáticas. Modos
por lâmpada (`Realtime`, `Mixed`, `Baked`) são uma evolução posterior, pois exigem transportar uma classificação
por luz até `SCENE_LIGHT` e decidir separadamente difuso, especular e shadow pass.

## Etapas pequenas

### 1. Interface e AO

- [x] reorganizar o painel sem mudar os defaults atuais;
- [x] adicionar `Indirect + Dynamic Shadows` e `Ambient Occlusion`;
- [x] separar modo escolhido de modo efetivamente baked;
- [x] implementar e integrar AO sem textura adicional;
- [x] esconder opções irrelevantes por modo;
- [x] manter o modo estático fora do enum visível até funcionar de ponta a ponta.

Build, bake numérico e execução no runtime passaram em 2026-10-15. O usuário validou o resultado visual em
Play e Standalone no mesmo dia.

### 2. Static Lighting + Shadows

- [x] separar no shader cobertura do atlas e origem Light Volume;
- [x] gravar direto + indireto no atlas e somente indireto/World no volume;
- [x] evitar difuso direto duplicado apenas nos receptores do atlas;
- [x] preservar luz completa nos objetos móveis e especular dinâmica nos estáticos;
- [x] expor o terceiro modo somente após testes numéricos e execução bem-sucedida.

Build, bake numérico com dois receptores estáticos e um objeto móvel, Light Volume 1x1x1 e execução no
`AnastacioRuntime` passaram em 2026-10-15, sem erro GLSL. O usuário confirmou cubo e plano Static numa cena
simples; ainda falta a avaliação visual em cena maior com materiais variados.

### 3. Acabamento do fluxo

- [x] renomear o painel antigo para `Texture Bake (Legacy)`;
- [x] mostrar elegibilidade por objeto, motivos de exclusão e cobertura do atlas;
- [x] expor Receive Baked Lighting e Clear Baked Lighting no painel;
- [x] esclarecer no modo estático que mover luzes/objetos exige novo bake;
- revisar traduções;
- avaliar presets de qualidade somente depois de medir combinações reais de resolução/samples;
- avaliar cancelamento modal/Escape separadamente, reutilizando a experiência do Material Atlas sem acoplar
  essa infraestrutura à primeira entrega.

### 4. Evolução opcional

- modos `Realtime/Mixed/Baked` por lâmpada;
- seleção explícita de objetos/luzes participantes;
- estimativa de densidade de texels e memória antes do bake;
- cache/rebake parcial, somente se medições justificarem a complexidade.

## Validação

Cada etapa precisa preservar e testar:

- arquivo antigo sem `ae_lightmap_mode`, com aparência do modo indireto atual;
- bake CPU e GPU, com e sem denoise;
- falha/cancelamento sem substituir o último resultado válido;
- save/reload da cena e toggle `Use in Game`;
- objeto estático com atlas e objeto móvel iluminado pelo caminho correto;
- materiais Principled metálico e dielétrico, World/HDRI, emissivo, Sun, Spot e Point;
- AO sob um cubo: contato escuro, área aberta próxima de 1 e luz direta não escurecida duas vezes;
- modo estático: comparação com Cycles, nenhuma duplicação de luz direta e sombra imóvel presente;
- GTAO/SSGI ligados e desligados, documentando combinações que intencionalmente somam AO;
- Desktop primeiro; depois Web e Android para lightmap/AO. Light Volume continua fora desses dois alvos;
- teste visual final no jogo real pelo usuário, além de logs e leituras numéricas automatizadas.

Mudanças em shader exigem reconstruir `ge_rasterizer_shaders`. Se algum header for alterado e surgir crash
desproporcional ao diff, o rebuild deve seguir a regra de limpeza documentada em `AGENTS.md`.

## Arquivos previstos

- `source/release/scripts/startup/bl_operators/anastacio_lightmap.py`: modos, passes e commit do resultado;
- `source/release/scripts/startup/bl_ui/properties_game.py`: painel contextual;
- `source/source/blender/nodes/shader/node_shader_util.c/.h`: imagem, modo e contrato atlas/volume;
- `source/source/blender/nodes/shader/nodes/node_shader_bsdf_principled.c`: entradas do shader;
- `source/source/blender/gpu/shaders/gpu_shader_material.glsl`: composição de AO e supressão do difuso duplicado;
- `source/release/scripts/startup/bl_ui/properties_render.py`: nome/aviso do baker legado, somente na etapa 3;
- scripts de teste em `tools/` e cena controlada em `projects-teste/gi/`.
