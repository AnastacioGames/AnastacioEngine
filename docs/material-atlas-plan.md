# Anastacio Material Atlas — pesquisa e plano

Data: 2026-10-07. Estado: primeira versão nativa em C++, com suporte delimitado abaixo.
Pedido inicial: pesquisa sem implementação; depois o usuário autorizou implementação nativa.

## Versão nativa atual

Properties > Material > **Anastacio Material Atlas** > **Bake Material Atlas**.
Operador `material.anastacio_atlas_bake`, implementado em
[anastacio_material_atlas.cpp](../source/source/blender/editors/render/anastacio_material_atlas.cpp).
A interface padrão do editor apenas chama o operador; não precisa instalar/ativar o addon antigo.

Primeira peça autocontida: um objeto ativo, em Object Mode, com materiais PBR opacos e Principled
ligado diretamente ao Output. Produz Base Color, Roughness, Metallic, Specular e Normal em imagens
packed PNG 16 bits, uma UV AnastacioAtlas e um material final. A malha original permanece como backup
com fake user; o objeto mantém sua identidade. Outros usuários da malha original não são alterados.
Slots devem estar ligados aos dados da malha para que o backup guarde os materiais originais.

Resolution aceita potência de dois entre 64 e 4096; Margin em pixels; Samples do Cycles.
CPU é padrão. Use Configured Cycles Device utiliza a configuração atual do Cycles, sem detectar ou
alterar as preferências de GPU. Cycles precisa estar habilitado e PBR Shading Nodes ligado.

Base Color e parâmetros são avaliados por emissão temporária: não incluem luz/AO, e Base Color não
fica preto só porque Metallic = 1. Normal é tangent space OpenGL na UV do atlas, com UV fonte explícita
nos Normal Map temporários. Imagens de dados não recebem conversão sRGB nem denoise.
Resultado é aplicado apenas depois dos cinco passes e da criação do material final.

**Restore Original Materials** aparece para novos atlas que tenham uma referência de backup.
Restaura a malha fonte inteira (materiais, índices de faces e UVs), conservando a malha de atlas
com fake user e sem alterar outros objetos que a compartilhem. A referência é um IDProperty de
mesh para mesh: funciona após renomear e salvar/reabrir, sem procurar backups pelo nome.
Modificadores, shape keys e slots ligados ao objeto impedem restauração para evitar perda silenciosa.
Edições posteriores na malha de atlas não são transferidas à fonte. Se GI foi baked depois do atlas,
refaça a iluminação após restaurar. Atlas de versões anteriores não têm essa referência e precisam
de restauração manual; não se tenta adivinhar a malha original.
Teste `test_material_atlas_integration.py -- --restore` passou, incluindo backup renomeado,
reload, material ativo, recusa de modifier e atlas compartilhado.

Na interface, **Escape cancela** os passes de bake. O operador usa os jobs existentes do Cycles,
bloqueia edições durante a operação e só aplica o resultado depois dos cinco mapas validados.
Após pedir cancelamento, aguarda o baker parar antes de remover temporários e restaurar a fonte,
seleção, render e configuração Cycles. Preparação/empacotamento de UV e validação/packing de imagens
ainda são síncronos; a interrupção depende de o backend alcançar seus pontos de parada.
Scripts continuam síncronos por padrão; `use_async=True` habilita jobs no editor com janela.
`material.anastacio_atlas_cancel` chama a mesma rotina de cancelamento usada por Escape.
O cancelamento nativo de job também é reconhecido, inclusive quando a imagem parcial parece válida.
[run_material_atlas_modal_tests.py](../tools/run_material_atlas_modal_tests.py) passou nos quatro
cenários: cancelamento no início, após dois mapas, erro no terceiro passe e conclusão normal.
Verifica IDs/usuários/UVs/configuração/seleção, pixels e Undo/Redo automático. O teste chama a API de
cancelamento; a tecla física Escape e fechamento da janela permanecem como checks manuais.

Limites explícitos: sem materiais legados, grupos/Mix Shader, transparência, volume, displacement,
modifiers, shape keys, shaders customizados, foliage, animação de materiais/nós ou entradas não
baked diferentes entre materiais. Nós sem suporte são recusados com motivo. Não une objetos nem
substitui silenciosamente uma UV AnastacioAtlas existente. Referências em scripts ao nome dos
materiais antigos precisam ser revisadas pelo usuário antes da aplicação.
UV fonte ausente é recusada. Valores de mapa fora de 0–1 também são recusados, em vez de serem
silenciosamente cortados ao salvar PNG; suporte a mapas HDR exige outra entrega.

Teste: [test_material_atlas.py](../tools/test_material_atlas.py), executado no editor atualizado.
Cobre cores/scalars conhecidos, material totalmente metálico, textura na UV fonte, normal inclinada
reconstruída depois do reempacotamento, Lightmap existente, mesh compartilhado e save/reload.
Inclui rollback depois de passes já executados quando um mapa não cabe no formato de saída.
Testes adicionais em [test_material_atlas_integration.py](../tools/test_material_atlas_integration.py):
bake real de GI → atlas → rebake de GI e atlas → GI, sem denoise/light volume, com iluminação World.
Validam GI não preta, pixels finitos, mapas físicos sem contaminação e preservação das duas UVs.
GPU OpenCL AMD Radeon RX 6800M passou os cinco mapas com CPU desabilitada nas preferências.
Undo/Redo em editor com janela restaurou malha/materiais e imagens packed. A suíte modal adicional
validou o passo automático de Undo criado na conclusão nativa, sem push manual após o bake.
Aceitação visual no jogo real continua pendente.
Exportação Web passou preflight e execução no Edge 154/WebGL 2, incluindo shaders e marcador
de material único ([teste de navegador](../tools/test_material_atlas_web.cjs)). Não valida aparência.
Linux e casos de GI com denoise/light volume permanecem pendentes.

### Aproveitamento do Baked Lighting

| Recurso existente | Uso nesta versão | Limite |
|---|---|---|
| ae_uvatlas / xatlas | Mesma biblioteca, chamada diretamente do C++ | Exige biblioteca ao lado do executável; sem fallback nesta versão |
| UV por canto | Adaptador nativo usa triangulação real do mesh | Recusa n-gon quando há UV conflitante no mesmo loop |
| Bake Cycles | Jobs nativos por passe na interface; execução síncrona em scripts/background | Escape solicita interrupção; preparação de UV e packing ainda síncronos |
| Margens | Baker nativo preenche gutters dos mapas | Não aplica blur/denoise de iluminação aos mapas físicos |
| GPU | Configuração atual do Cycles opcional | Detector Python do GI não foi copiado |
| Progresso | Barra nativa da janela e logs por passe | Não compartilha campos ae_bake_progress do GI |
| Imagens packed | Persistência local já existente | Nomes novos; nunca usa AE_lightmap como destino |
| OIDN, RGBM, World Light e Light Volume | Continuam exclusivos do GI | Não são usados para achatar materiais |

A leitura da lightmap no shader usa `GPU_attribute(CD_MTFACE, "Lightmap")` em
[node_shader_util.c](../source/source/blender/nodes/shader/node_shader_util.c).
O material final usa nó UV Map explícito para AnastacioAtlas, sem apagar/reempacotar Lightmap nem
alterar scene.ae_lightmap/ae_lightmap_use. Não é necessário refazer GI apenas por adicionar a UV e
trocar slots com aparência equivalente. Alterações de geometria, posição, emissão ou resposta da
superfície podem desatualizar a iluminação. O teste atual comprova preservação dos dados; não é uma
comparação visual de GI. O teste adicional executa rebake nas duas ordens em uma cena controlada.

### Defeitos do baker corrigidos durante a validação

Em [bake_api.c](../source/source/blender/render/intern/source/bake_api.c), UV informada pelo nome
era procurada como CD_MTFACE na ldata, que armazena CD_MLOOPUV. Corrigido tipo e inicialização de
primitivas antes de retornar por UV ausente. Também corrigido stride da normal pré-calculada por
polígono: índice deve ser poly * 3. A falha com UV nomeada foi reproduzida no teste de bake; as
correções passaram nos testes de dados/pixels, incluindo normais em faces de orientações diferentes.
Isso não prova que todo resultado estranho do addon antigo tinha essa mesma causa.

## Resultado e recomendação

Há projetos públicos que resolvem partes importantes do problema. Recomenda-se manter a autoria e o
fluxo do addon existente, redesenhar sua execução para preservar os originais, e usar projetos externos
como referências de algoritmo e testes. Não importar um addon moderno inteiro: a API da engine deriva
do Blender 2.79 e os candidatos atuais exigem versões posteriores.

Decisão posterior do usuário: implementação nativa em C++. A pesquisa e o contrato abaixo orientam
as próximas etapas; a seção de versão atual acima prevalece quando o plano original divergir.

Objetivo concreto: selecionar um objeto com vários materiais, gerar mapas em uma UV de atlas e criar
um material final que substitua os slots apenas no resultado gerado. Vários objetos poderão compartilhar
o mesmo atlas sem serem unidos. Isso preserva hierarquia, física, logic bricks e animação.

“Um material” significa um material por conjunto compatível. Misturas que exigem estados diferentes
de transparência, culling ou shader precisam ser separadas ou recusadas, com motivo visível.

## Auditoria do addon existente

Fonte: [automate_atlas_bake.py](../source/release/scripts/addons/automate_atlas_bake.py), versão 1.3,
autoria registrada como AnastacioGames & Gemini AI. Constatações por leitura estática, não por execução.

| Área | Comportamento atual | Mudança necessária |
|---|---|---|
| Escopo | Usa apenas o mesh ativo | Escolha explícita entre ativo e selecionados |
| Resultado | Gera imagens e UV, mas não constrói/atribui material final | Construção do material e remapeamento de índices das faces |
| Motor | Força Blender Render | Adaptadores separados para legado e Cycles/PBR |
| UV | Faz unwrap na malha do usuário; torna a UV alvo ativa/render | Preservar UV fonte e operar em cópias; não mudar amostragem de origem |
| Materiais | Adiciona texture slots em materiais sem imagem | Preparação temporária, sem alterar materiais compartilhados |
| Imagens | Reutiliza imagens pelo nome e pode redimensioná-las | IDs de execução e proteção contra sobrescrita |
| Falhas | Captura erros por passe e segue até FINISHED | Falha de passe obrigatório impede aplicação do resultado |
| Operador | Não verifica o conjunto retornado por bake_image | Tratar CANCELLED como falha, além de exceções |
| Restauração | Restaura motor e duas configurações de AO | Restaurar seleção, ativo, modo, UVs e todas as opções de bake alteradas |
| Progresso | progress_end fica no caminho normal | Encerramento no finally; cancelamento entre passes |
| Combined | Multiplica Diffuse/Full por AO, com alpha opcional | Separar mapas físicos de cor com iluminação; evitar AO duplicado |
| Memória | Converte RGBA para várias listas Python completas | Buffers contíguos e processamento por blocos; medir memória |
| Exportação | PNG no diretório do arquivo, com nomes previsíveis | Diretório explícito, nomes únicos e aplicação somente após gravação válida |

Também devem ser verificados: materiais vazios, mesh compartilhado, imagens ausentes, UVs fora de 0–1,
normais com espelhamento, modifiers, shape keys e referências por nome de material em scripts de jogo.
Alterar a UV ativa pode afetar texturas cuja origem não especifica uma UV; esse é um risco identificado,
não um defeito reproduzido nesta sessão. SPEC_COLOR do legado não equivale automaticamente a Metallic
ou Roughness. O modo FULL pode incorporar luz/AO que serão aplicados novamente no jogo.

## Pesquisa de repositórios

Fontes primárias consultadas: README, metadados da API GitHub, declaração de versão e alguns arquivos
de implementação. Nenhum destes projetos foi instalado ou executado na engine.

| Projeto | Utilidade | Compatibilidade e limites | Licença observada |
|---|---|---|---|
| [Material Combiner](https://github.com/Grim-es/material-combiner-addon) | Combinação direta de cores/texturas e remapeamento UV; principal referência para caminho rápido | bl_info atual exige 2.80; README distingue funções disponíveis só em versões antigas; utiliza Pillow | LICENSE raiz GPL-3.0; __init__.py contém texto MIT: conferir arquivos/revisão antes de copiar |
| [Bake Groups](https://github.com/dertom95/addon_bake_groups) | Grupos de objetos, passes e UV de atlas | bl_info atual exige 2.80; declara estar em desenvolvimento; bake bloqueia a interface | Arquivo LICENSE declara GPL v3, com nome de outro addon; revisar atribuição |
| [BakeToSingleMaterial](https://github.com/Hawk-1332/BakeToSingleMaterial) | Fluxo completo entre seleção, bake e material final | README exige Blender 5.1; versão declarada 5.1.2; implementação une objetos e mantém só UV ativa, inadequado como padrão da engine | GPL-3.0 |
| [Auto-Bake](https://github.com/Sketch494/Auto-Bake) | Referência para passes, organização e testes de resultado | README cobre 3.6 a 5.x; manifesto de extensão começa em 4.2; requer adaptação à API local | README declara GPL-3.0-or-later |

Revisões verificadas em 2026-10-07: Material Combiner `eed9ca25baffe5463bdd6104360fcd9f6e32ba15`;
BakeToSingleMaterial `22276c82101897143e7dd2a091b6315ffdbc89ee`. Registrar revisão e licença de cada
arquivo efetivamente adotado na implementação. Não há código externo incorporado nesta preparação.

Decisão proposta: estudar Material Combiner para atlas direto e Auto-Bake para organização/testes;
usar BakeToSingleMaterial como exemplo simples do material final. Bake Groups é referência secundária.
Nenhum candidato examinado demonstrou integração pronta com Anastacio Engine/Blender 2.79.

## Recursos locais a reutilizar

- [anastacio_lightmap.py](../source/release/scripts/startup/bl_operators/anastacio_lightmap.py):
  empacotamento conjunto, leitura/escrita de UV, progresso, escolha de dispositivo e dilatação.
  Extrair utilitários comuns em etapa futura; não chamar diretamente um fluxo que muda luzes para GI.
- [ae_uvatlas.cc](../source/intern/ae_uvatlas/ae_uvatlas.cc) e
  [xatlas](../source/extern/xatlas/LICENSE): empacotador já incluído, licença MIT.
  Verificar se a ponte preserva topologia e suporta os requisitos do atlas de materiais antes de reutilizar.
- [Receitas de materiais](../source/release/scripts/startup/bl_operators/anastacio_material_recipes.py)
  e [suporte de nós](node-material-support.md): referência para montar saída compatível com Game PBR.
- Bake BI/Cycles e UV operators existentes: a ferramenta deve organizar essas capacidades antes de
  propor um novo baker. Lightmap de GI e atlas de materiais permanecem recursos distintos.

## Contrato proposto da ferramenta

Nome visível: **Anastacio Material Atlas**. Identificadores novos com prefixo `anastacio`.
Local sugerido: Properties > Material, com acesso pela busca de operadores.

Fluxo: **Analisar → configurar → gerar cópia com atlas → conferir → aplicar**, sendo aplicação explícita
uma escolha de produto para substituir os originais. A geração padrão já entrega cópias utilizáveis.
Preservar os originais não significa duplicar logic bricks automaticamente: cópias visuais devem ter um
contrato explícito para não disparar lógica duas vezes na cena. A primeira versão pode limitar-se ao
objeto ativo e produzir uma cópia fora dos layers de jogo; aplicação troca só dados de mesh/material.

Análise apresenta: objetos/materiais incluídos, grupos compatíveis, quantidade de mapas, tamanho,
estimativa de memória, UV fonte por material e motivos de exclusão. Não prometer redução proporcional
de draw calls: objetos distintos, passes, sombras e regras de batching continuam interferindo.

Opções básicas: resolução, margem em pixels, UV destino, perfil Legado/PBR, mapas e diretório.
Opções avançadas: densidade por objeto/material, tamanho máximo, AO separado, transparência e política
para UV repetida. Medir ocupação e avisar sobre perda de densidade; múltiplos atlas quando não couber.

### Dois caminhos, desenvolvidos separadamente

1. **Bake de materiais:** recria UV de destino e avalia materiais fonte com bake local. O plano inicial
   previa legado primeiro; a implementação autorizada depois começou pelo PBR opaco.
   Emission, Alpha e legado ainda são futuros. A disponibilidade de cada passe precisa ser confirmada;
   Metallic pode exigir avaliação de entrada por emissão temporária em vez de um passe dedicado.
2. **Combinação direta:** copia texturas existentes para retângulos, remapeia UV e dispensa bake.
   Restrita a imagens/cores e transformações demonstravelmente suportadas. Não é parte do primeiro
   marco: tiling, clipping e normais rotacionadas exigem tratamento próprio.

Um material PBR pode precisar de várias imagens. “Um material” não exige guardar todos os mapas em
uma única imagem. ORM é opcional após validar leitura no shader local; AO não deve ser inserido num
canal que a engine não lê. Normal usa dados lineares e convenção OpenGL; cores e emissão precisam de
tratamento de espaço de cor explícito. Não aplicar Filmic/exposure ao albedo exportado.

Não achatar silenciosamente: refração, vidro, efeitos dependentes de câmera, Time, vídeo, sprites,
parallax, shaders customizados e materiais com lógica dinâmica. Detectar e excluir no primeiro marco.
Lightmap existente usa UV própria e deve continuar referenciada depois da geração do atlas.

### Segurança da execução e memória

Trabalhar em dados temporários, manter UV fonte explícita e aplicar somente após todos os mapas
obrigatórios terem sucesso. Estado salvo/restaurado por try/finally; nomes únicos; nunca limpar
materiais/imagens globais sem comprovar que pertencem à execução. Exportação por arquivos temporários,
sem sobrescrever saída anterior por padrão. Reexecutar cria nova versão ou substitui apenas resultado
identificado como da ferramenta.

Um buffer RGBA float32 ocupa 64 MiB em 2048² e 256 MiB em 4096². Seis mapas em 4096² somam 1,5 GiB
somente em buffers de pixels, antes de cópias, malhas e baker. Estimar pico real e processar passes
sequencialmente. Listas de floats Python podem consumir muito mais que esses valores.
Progresso por etapa; cancelamento entre passes. Não prometer cancelamento instantâneo dentro de um
bake síncrono; avaliar job nativo depois de provar a primeira versão.

## Etapas futuras e critérios de saída

| Marco | Entrega pequena | Critério para avançar |
|---|---|---|
| A | Analisador e classificação, sem bake nem alteração da cena | Lista de inclusões/exclusões correta em cenas de teste |
| B | Atlas Diffuse de um mesh legado opaco, em cópia | Cores verificadas, UV fonte preservada, material único correto |
| C | Normal/specular/alpha legado e restauração em falha | Falhas/cancelamento não deixam mutações nos originais |
| D | Materiais PBR simples, mapas físicos separados | Comparação no jogo real e testes de dados aprovados |
| E | Selecionados, atlas compartilhado e grupos incompatíveis | Objetos/hierarquia/animação/lógica preservados |
| F | Integração startup/UI e migração do addon | Reabrir .range, editor/player e exports alvo funcionando |
| G | Combinação direta e otimizações opcionais | Ganho medido sem regressão visual |

Parar para revisão entre peças grandes conforme AGENTS.md. Não alterar runtime/C++ só para começar.
Se o usuário autorizar apenas o aprimoramento isolado do addon, B–D podem ser prototipados fora de
startup e da instalação, antes de F. A primeira peça C++ atual está descrita no início deste documento.

## Matriz de validação preparada

- Cubo com seis cores: um material final, índices corretos, cor por face, sem UV sobreposta.
- Duas imagens e uma cor constante: preservar textura, UV fonte e repetição ou recusar com motivo.
- Mesh compartilhado/material compartilhado: objeto não selecionado permanece idêntico.
- Nome de imagem/UV já existente: nenhuma imagem alheia redimensionada ou sobrescrita.
- Bake obrigatório falhando, operador CANCELLED, diretório inválido: nenhum resultado aplicado;
  estado restaurado e mensagem identifica o passe.
- PBR: cores constantes e gradientes conhecidos para roughness/metallic; normais espelhadas;
  luz dinâmica funcionando depois do bake, sem iluminação duplicada.
- Opaque/clip/blend: grupos separados e comportamento de sombra/transparência preservado.
- Rig/shape keys/modifiers/lightmap: não perder deformação, dados, UVs nem vínculos.
- Salvar/reabrir .range com imagens packed; editor, standalone e Web/Android WebView quando autorizado.
- Performance: materiais/grupos antes/depois, draw calls medidos, ocupação, tempo e pico de memória.

Checks automatizados de dados, logs e pixels controlados são apropriados. Aceitação visual no jogo
real pelo usuário, conforme AGENTS.md; não usar screenshot automatizado como prova de equivalência.
Nenhum build foi necessário na etapa inicial de preparação documental. Resultados externos são descrições e
leitura estática, não evidência de funcionamento nesta engine.
