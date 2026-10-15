# Ragdoll — análise e plano de evolução

Data: 2026-10-14. Estado inicial: planejamento baseado em leitura estática, sem alterações
no addon, no runtime ou no RolimaRacer e sem validação física/visual naquela etapa.

Atualização posterior no mesmo dia: o `.range` foi inspecionado e as quatro armatures de
`Personagens_Carro` apontam para `scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll`;
nenhum texto embutido com ragdoll foi encontrado. Duas rodadas com profiler foram capturadas
em `debug-logs/perfil-rolima-20261014-183928/` e `debug-logs/perfil-rolima-20261014-184620/`.
Os picos principais medidos ficaram em `endframe.swap`, sem marcadores para atribuir cada
pico ao ragdoll. Preparada instrumentação opt-in nos scripts do jogo, documentada no
[profiler](engine-profiling.md#eventos-de-ragdoll-do-rolimaracer); a próxima rodada em jogo real
foi validada na rodada `perfil-rolima-20261014-192125`: três ativações por input e três
por impacto, seis retornos, sem erros registrados. Os módulos externos foram confirmados
em runtime por caminho e SHA-256. Ativação do componente: 0,436–0,538 ms; desativação:
0,233–0,295 ms, para 20 corpos. Nenhum SPIKE nas janelas das quedas/retornos (+2 s).
As pausas de 1606,3 ms (t=32,40 s) e 693,9 ms (t=64,34 s) ocorreram entre as quedas,
dominadas por swap; isso não identifica a causa de GPU/driver. O retorno completo do
controlador teve máximo de 1,076 ms. São custos de Python/API, com instrumentação,
não o custo total do solver Bullet ou da renderização. A lâmpada de faísca reposicionada
foi relatada pelo usuário, mas não medida individualmente; não há atribuição causal.
Preservar essa rodada como baseline; evolução prioriza robustez, autoria e prévia.

## Implementação atual — correção dos scripts (2026-10-14)

Etapa 2 da sequência aprovada pelo usuário implementada no RolimaRacer: inicialização
completa, transição idempotente com confirmação, cache pelas ligações reais de
constraints próprias, fonte de velocidade/assento explícita, erro sem sucesso falso
e remoção dos setters de amortecimento por quadro. Preservados input, fator arcade
0,4, offsets de assento existentes, auto-desvirar e contornos de culling/compound.
O addon legado e C++ não foram alterados. Nova autoria descrita abaixo.

Execução no player passou: 100 ciclos de impacto/input com diagnóstico ligado e
desligado, `Active=True`, menu, constraints adicionais, carro/colisor separado do
controlador, rotação/translação do assento, colisores auxiliares e erro intencional
de alvo mantendo flags de recuperação. Os quatro rigs reais passaram 100 ciclos
simultâneos por rig (20/20/22/23 corpos), sem erros registrados. Geradores:
`tools/debug/cenas/validar_correcao_ragdoll.py` e `validar_rigs_rolima.py`.
Usuário confirmou que funciona bem após testar no jogo. A rodada posterior
`perfil-rolima-20261014-194141` registrou três inputs e dois impactos, cinco retornos,
sem erros ou SPIKE nas janelas das quedas/retornos. Isso valida essa rodada,
sem demonstrar ganho de FPS nem cobrir todas as combinações do plano.

## Autoria e prévia — primeira entrega (2026-10-14)

Novo addon separado: `source/release/scripts/addons/anastacio_ragdoll.py`, instalado
também em `build/bin/2.79/scripts/addons/`. Não altera o Easy Ragdoll legado nem migra
o `.range` do RolimaRacer. Uso e limites: [guia da autoria](ragdoll-authoring.md).

Implementados: lista de ossos, inclusão de controles sob escolha explícita, largura,
profundidade, comprimento relativo, deslocamento e rotação por osso; prévia wireframe
em repouso sem objetos; geração e substituição transacional de caixas/pivôs/constraints
próprios; remoção, Undo/Redo e persistência. Descritor único alimenta prévia e geração.
Identificação usa referência da armature e chave por entrada, sem depender do nome
dos corpos. Vínculos de rigs duplicados não são migrados silenciosamente.

Regressão no editor: geometria/pivôs coincidentes, geração repetida, rollback com falha
injetada, constraints alheias preservadas, recusa de dependências externas conhecidas,
escala não uniforme/espelhamento, dois rigs independentes, salvar/reabrir e Undo/Redo
de atualização/remoção. Callback POST_VIEW executado sem exceções GL. Aparência da
prévia validada pelo usuário em um esqueleto criado do zero. Gerador: `validar_autoria_ragdoll.py`
em `tools/debug/cenas/`.

Complemento de autoria: collection própria por armature, aninhada sob a pasta do rig,
com corpos e empties, propriedade por UID na cena, reutilização após renomear e remoção
apenas de pastas vazias. Geração anterior é organizada ao atualizar. Regressão cobre
persistência, rollback da criação da pasta, rigs independentes e Undo/Redo. Painel
também acessível por corpos/pivôs; armature em Object Mode não exige osso selecionado.
O exemplo visual novo desativa a constraint externa de teste que deslocava o Root.

Na primeira entrega 0.1/0.2 havia apenas autoria, sem execução. Na versão 0.3, a geração
inicial continua NO_COLLISION até escolher **Preparar física + componente**; esse botão
anexa o núcleo descrito abaixo. Ainda faltam eixos, limites e sobreposições desenhados
na prévia. Atualizar substitui a geometria gerenciada; use os campos por osso.

## Núcleo comum e presets — primeira execução (2026-10-14)

Implementado `source/release/scripts/modules/anastacio_ragdoll_runtime.py`, distribuído
também em `build/bin/2.79/scripts/modules/`. Um componente atende FREE, ANCHOR e NPC
com/sem recuperação automática. Três presets de limites/damping, ajustes por osso,
massa distribuída por volume/peso relativo e juntas cone-twist com eixos do osso.
Herança linear e angular considera a velocidade no ponto de cada corpo. A autoria
anexa/atualiza o componente sem duplicação; remoção e Undo/Redo incluem a execução.

Execução no player passou em cinco rigs simultâneos, 100 ciclos por modo, Active
inicial, NPC permanente, automático, obstáculos, veto do jogo, falha de alvo e herança
angular/linear. Demonstração de cinco humanoides/50 corpos passou 370 frames com
queda por impulso e retorno automático, mantendo um NPC caído. Regressão de UI passou
preparação, presets, opções e Undo/Redo de remoção de física/pasta/componente.
Evidências: `debug-logs/ragdoll-runtime-final-20261014/`. [Guia de execução](ragdoll-runtime.md).

Sem C++ novo. Cache mundial diferido é tratado compondo localTransform da hierarquia
nas transições, e a pose de retorno é preservada sem depender da próxima avaliação
de constraints no mesmo tick. Escala não uniforme da âncora/controlador é recusada;
sem isso, ciclos repetidos distorciam a pose e podiam produzir NaN.

Limites da primeira versão: FREE validado com controlador Rigid Body/Dynamic BOX e
chão plano; checagem AABB não substitui query Bullet para volumes arbitrários. Ainda
faltam validação visual no personagem real, adaptação/migração do RolimaRacer ao novo
componente, cápsulas/Character, colisões configuráveis, blend/animação de levantar,
instanciação dinâmica de grupos, validação de exportadores e Web/Android. Presets são
passivos, sem músculos/motores; comportamento visual precisa de avaliação do usuário.

## Objetivo e decisão proposta

Decisão confirmada pelo usuário: manter autoria como addon e execução por componente
Python; não alterar C++ se a API existente atender. NPCs usam o mesmo núcleo, sem
dependência de input. A recuperação será configurada independentemente do modo
livre/âncora: `auto_recover=True` permite retorno após `recovery_delay`; `False`
mantém o ragdoll até comando explícito do jogo. Isso permite queda temporária ou
corpo permanente sem outro sistema físico. Recuperação automática continua sujeita
à validação de destino; o temporizador não pode confirmar um retorno inválido.
Esses campos foram implementados na versão inicial de runtime 0.3 descrita acima.

O addon antigo `easy_ragdoll_RangeEngine.py` foi removido do fonte distribuído e de
`build/bin/2.79/scripts/addons/` a pedido do usuário em 2026-10-14. Backup fora da
instalação em `debug-logs/ragdoll-legacy-removed-20261014/`. Os scripts externos do
RolimaRacer e a primeira versão de referência em `tools/` foram preservados.

Entregar uma ferramenta Anastacio Ragdoll integrada ao editor, com prévia dos corpos,
configuração por osso e um núcleo reutilizável de execução. Preservar duas opções:

- **Personagem livre:** cair, localizar um local seguro e recuperar o controle no chão.
- **Personagem vinculado:** cair e retornar a um assento/âncora de um veículo ou empty,
  sem deslocar o carro para acompanhar o corpo.

Começar com addon distribuído pela engine e componente Python compartilhado. A física já
é executada em C++ pelo Bullet; portar toda a orquestração não é requisito para obter uma
ferramenta profissional. Reservar C++ para lacunas demonstradas de API, sincronização ou
desempenho. Não manter duas implementações independentes de física.

## Quais arquivos são fonte e quais são cópias

| Arquivo | Papel e manutenção |
|---|---|
| `source/release/scripts/addons/anastacio_ragdoll.py` | Fonte do novo addon de autoria, mantido e distribuído com a engine. |
| `build/bin/2.79/scripts/addons/anastacio_ragdoll.py` | Cópia instalada do novo addon; não usar como fonte de manutenção. |
| `easy_ragdoll_RangeEngine.py` | Addon legado removido do fonte e da instalação; descrição abaixo preserva a descoberta histórica. |
| `tools/ADD na engine anastacioEngine/easy_ragdoll.py` | Versão original de referência; não é a origem do install atual. |
| `D:/ProjetoRolimaRacer/scripts/VehicleSystem/ragdoll_system/ragdoll.py` | Componente adaptado do jogo: corpos físicos, constraints e pose. |
| `D:/ProjetoRolimaRacer/scripts/VehicleSystem/ragdoll_controller.py` | Integração do jogo: input, impacto, retorno, colisores auxiliares, animação e câmera. Não é outro componente independente. |

Fonte e cópia instalada do addon legado tinham SHA-256 idêntico na análise:
`03c1683f9b5ea00639c363aa0d2a452da10f768805e9ad21f6e1a836c6092287`.
Em `source/source/creator/CMakeLists.txt`, o `POST_BUILD` de `RangeEngine` no Windows
executa `cmake --install`. O install remove `TARGETDIR_VER` e copia `release/scripts`.
Portanto, recompilar e religar o editor pode sobrescrever a edição feita em `build/bin`;
`ninja install` também o faz. Um build sem trabalho ou só de outro alvo não implica cópia.

Existe ainda uma terceira camada: o gerador grava `Ragdoll.py` em `bpy.data.texts` do
projeto **somente se esse texto ainda não existir**. Atualizar o addon não atualiza
componentes já embutidos no `.range`. Os scripts externos do jogo também não são
atualizados pelo install da engine. A confirmação do módulo efetivamente carregado pelo
jogo exige inspecionar o componente e os Text datablocks do `.range` usado, não apenas os
arquivos em disco. Isso fica como primeira verificação da implementação.

## Diagnóstico do código atual

A abordagem básica é coerente: corpos rígidos articulados movem empties, constraints de
pose copiam esses transforms para os ossos, e a animação reassume o controle ao desligar.
O cache do componente do jogo e a separação da lógica de veículo são boas bases.
Os achados abaixo são do código; impactos visuais e tempos precisam de execução.

### Correção e ciclo de vida

1. **Constraints sem identificação de propriedade.** Os dois componentes percorrem
   `self.object.constraints`, alteram todas as influências e tomam alvos como corpos do
   ragdoll. Essa lista inclui constraints de pose de outros tipos, conforme
   `BL_ArmatureObject::LoadConstraints`. Um rig com IK ou acessórios pode ser alterado.
   Registrar apenas os pares osso/corpo/pivô/constraint pertencentes ao ragdoll.
2. **Estado inicial incoerente no jogo.** `start()` aceita `Active=True`, marca o estado
   ativo e depois suspende todos os corpos. A propriedade `active_ragdoll` é a autoridade
   nas atualizações e não é sincronizada com esse argumento. Inicializar tudo por uma
   única transição, inclusive a física e a influência.
3. **Inicialização parcial.** O retorno antecipado pelo nome da cena conter `menu`
   deixa campos sem inicializar; o `except` de `start()` mantém `is_valid=True` mesmo
   após falha. Definir estado completo antes de retornos e invalidar/reverter falhas.
4. **Associação frágil.** O componente do jogo procura ossos por substring no nome do
   corpo e escolhe `children[0]` como pivô. O addon pressupõe `target.parent` válido.
   Usar referências explícitas e validar duplicação, exclusão, renomeação e instâncias.
5. **Root implícito.** Subir até o ancestral máximo não distingue carro, empty,
   controlador e âncora. O checkbox `Maintain Parent` atual só altera o cálculo da
   posição central; não implementa uma política completa de vínculo.
6. **Retorno sem confirmação de sucesso.** O controlador limpa `ragdoll_system` e
   aplica cooldown mesmo após uma exceção no reset ou armature perdida. Pode deixar
   física, animação e flags divergentes. Só confirmar estado após a operação completar.
7. **Responsabilidades duplicadas e ordem sensível.** O controlador chama
   `ragdoll_on_off()` diretamente, enquanto o próprio componente também o chama em
   `update()`. A ordem entre pose, parent, física e animação precisa de um contrato único.
8. **Original também precisa de correções.** A versão de referência suspende a física
   do root; a instalada comentou essa suspensão. Ambas usam ganho fixo 40 para o
   Character, assumem pivôs existentes e dividem pelo tempo de blend sem tratar zero.
   Preservar o modo livre não significa copiar essas suposições para o sistema novo.

### Física e desempenho

1. **Amortecimento manual acorda os corpos.** No componente do jogo, quando a velocidade
   linear ao quadrado é menor que 2, as velocidades linear e angular são multiplicadas
   por 0,85 por atualização. `CcdPhysicsController::SetLinearVelocity` e
   `SetAngularVelocity` chamam `activate(true)`. Isso contraria o objetivo declarado
   de favorecer sleep. O efeito depende da frequência de atualização e ignora um corpo
   girando rápido com pouca translação. Preferir damping do Bullet e validar sleep da
   cadeia inteira; não prometer custo zero apenas por reduzir a velocidade.
2. **Velocidade de saída incompleta.** O jogo usa 40% da velocidade linear do colisor,
   sem herdar a contribuição angular do carro. Manter esse fator como preset arcade,
   e oferecer herança física configurável: `v_parte = v_origem + omega x deslocamento`,
   em coordenadas mundiais, além do impulso do impacto. Capturar antes de suspender ou
   reparentar. Para Character, verificar unidades de `walkDirection` no código local.
3. **Trabalho em repouso.** O alinhamento de todos os corpos a cada dez quadros ainda
   recalcula inversas e grava transforms/velocidades. Cachear offsets locais fixos e
   preparar a pose imediatamente antes de ativar; manter atualização periódica somente
   se uma medição comprovar que há dependência real de bounds ou consultas físicas.
4. **Forma e articulação genéricas.** O gerador cria caixas, massa 2 por osso e
   cone-twist com o mesmo limite em toda articulação. Isso ignora proporções e diferenças
   entre joelho, cotovelo, ombro e quadril. Adicionar massa total com distribuição,
   limites/eixos por junta e presets; começar pelas caixas existentes, depois cápsulas.
5. **Colisão não pode ser só global.** Separar colisão com cenário, veículo, outros
   personagens, membros adjacentes e membros não adjacentes. Os grupos/máscaras atuais
   e `use_linked_collision` precisam ser verificados de ponta a ponta na conversão.
6. **Transforms e juntas devem concordar.** O gerador encurta a caixa em 20%, mas o
   pivô continua derivado de metade do comprimento integral do osso. Isso pode ser um
   espaçamento intencional; representar offsets de corpo e junta separadamente e
   visualizar ambos. Testar escala não uniforme, espelhamento e pose atual versus rest.
7. **Geração repetida não é atualização.** O operador pode adicionar novos corpos de
   novo, reutilizar uma constraint chamada `Copy Transforms` que era do usuário e
   continuar após falha no carregamento do módulo. Criar operações idempotentes com
   undo, propriedade dos dados gerados e rollback de falhas.

### Integração específica do RolimaRacer

- `_ensure_deps()` bloqueia inclusive ativação por impacto se o input estiver
  indisponível. Física não deve depender de teclado/controle.
- O retorno após 0,5 s e o cooldown de 2 s são regras do jogo: expor configuração.
  Virar o carro, fumaça, animação de dirigir e abaixar a cabeça ficam no adaptador.
- `_set_collider_state()` desmonta/remonta filhos compound e usa posição Z=-1000 para
  estacionar colisores. Investigar o comportamento real de compound no C++ antes de
  remover o contorno; isolar a transição para executá-la uma vez por mudança de estado.
- O retorno escolhe o colisor do carro como pai e reaplica `orig_local_pos/ori` sem
  garantir que foram salvos no espaço desse mesmo pai. Usar uma âncora explícita de
  assento e salvar o transform completo, incluindo escala quando aplicável.
- `check_culling_anomaly()` presume que carro visível implica piloto visível. Isso não
  é uma prova geométrica e pode disparar falsos positivos.
- O refresh alterna visibilidade, desloca armature e filhos em 1 mm e força pose. Uma
  sequência completa tende a cancelar os deslocamentos, mas uma sequência interrompida
  pode deixar offset. Forçar filhos visíveis também interfere em primeira pessoa e LOD.
  Substituir somente após reproduzir a falha e validar a correção de pose/bounds.
- O roadmap já registra aproximadamente 800 ms no swap ao voltar do ragdoll. O changelog
  registra correções de LOD e bounds de skinning. Não atribuir essa travada apenas ao
  Python nem assumir que todos os contornos ainda são necessários: medir no build atual.

## Arquitetura proposta

### Ferramenta de autoria integrada

Painel **Anastacio Ragdoll** na física da armature, distribuído nos scripts da engine.
Configuração por armature e por osso, usando propriedades registradas e dados
versionados. Evitar campos DNA novos na primeira entrega.

Fluxo: selecionar armature → mapear ossos → escolher modo e preset → ativar prévia →
ajustar → validar → gerar/atualizar → anexar componente automaticamente.

A prévia desenha wireframes/transparências na Vista 3D, sem criar corpos físicos nem
alterar a pose. Mostrar corpo, pivô, eixos e limites angulares, destacar seleção e avisos
de escala ou sobreposição aproximada. Usar o mesmo descritor de geometria/transforms
na prévia e na geração para evitar divergências. `SpaceView3D.draw_handler_add` já é
usado pelos scripts locais, inclusive com `POST_VIEW`; não requer C++ para essa entrega.
Remover handlers ao desativar, trocar arquivo e desregistrar; restaurar o estado OpenGL.

O ajuste inicial pode ser feito por campos no painel; manipulação direta na viewport
é uma evolução posterior. Permitir excluir dedos, cabelo e ossos de controle, simetria
opcional e seleção manual de ossos, em vez de depender apenas do comprimento mínimo.
Separar **prévia de geometria** de **teste físico**; uma caixa desenhada não prevê o
resultado dinâmico da queda. Teste físico usa cópia controlada da cena.

### Núcleo e componente

Manter uma única implementação do runtime, distribuída como módulo da engine. Nome
proposto: `anastacio_ragdoll`; caminho definitivo depende de validar importação no editor,
player e jogo exportado. O componente anexado chama esse núcleo, sem injetar centenas
de linhas duplicadas. Se for necessária exportação de código para portabilidade, gerar
uma cópia explicitamente versionada, com atualização consciente e preservação de edições.

Descritor v1: versão, identidade do rig, associação osso/corpo/pivô/constraint, offsets
locais, forma/dimensões, massa, damping, filtro de colisão, tipo/eixos/limites da junta,
osso central, fonte de velocidade, modo e âncora de recuperação. Nomes são rótulos;
identidades e referências devem sobreviver a renomeação, duplicação e instanciamento.

API proposta, ainda inexistente: `activate(...)`, `request_recovery(...)`, `reset(...)`,
consulta de estado e notificações de ativação/retorno/falha. Sem teclas fixas, nomes de
cena ou imports de `VehicleSystem`. O jogo decide quando e por que ativar.

Estados: `ANIMATED → ENTERING → SIMULATING → RECOVERING → ANIMATED`, com falha explícita.
Entrada captura pose/velocidades, prepara corpos sem realimentar a pose física anterior,
liga física e transfere influência. Saída suspende os corpos, posiciona root/âncora,
prepara pose de animação, mistura a recuperação e restaura controle/colisores uma vez.
Definir a ordem exata após observar os pontos de atualização de animação e física locais.

Modo livre: root de controle explícito, referência na pelve, chão/normal e espaço livre
para o colisor, posição e heading seguros, escolha de animação de levantar de costas ou
de bruços quando fornecida pelo usuário. Um raycast não basta para verificar volume livre.
Modo vinculado: armature, fonte de velocidade, carro e âncora separados; política de
vínculo explícita; recuperação no assento, sem reposicionar o veículo por causa do corpo.
Reset imediato continua disponível para jogos arcade; blend é configurável.

### Onde C++ pode entrar

Reaproveitar `CcdPhysicsEnvironment`, `CcdPhysicsController`, `BL_ArmatureObject`,
`BL_ArmatureConstraint`, deformers e APIs de constraints existentes. A engine já cria
hinge e cone-twist; `bl_operators/rigidbody.py` já gera e registra componente de juntas.

Só implementar uma ponte nativa se o protótipo demonstrar necessidade: reset de vários
corpos em fase segura do frame, atualização de pose/bounds, filtros por par, configuração
de sleep por corpo ou parâmetros do solver ausentes na API. Cada lacuna vira uma peça
pequena, com evidência e validação antes da próxima. Um sistema de active ragdoll com
motores seguindo animação é uma frente posterior, não parte do ragdoll passivo inicial.

## Entregas e critérios de aceite

| Etapa | Entrega | Como aceitar |
|---|---|---|
| 0 — Baseline | Confirmar `.range`/módulo carregado, salvar cópias, inventariar rigs/constraints e medir entrada/saída atuais. | Reproduzir modo livre e piloto; registrar configuração, picos e falhas antes de editar. |
| 1 — Correção | Inicialização completa, referências explícitas, filtrar constraints próprias, retorno com confirmação e damping sem setters por quadro. Preservar flags/API do jogo por adaptador. | Entrada/saída repetidas sem estado preso, sem alterar IK do usuário; validar `Active` inicial e erros parciais. |
| 2 — Prévia | Descritor compartilhado, desenho na viewport, seleção de ossos, ajustes por osso, geração/atualização/remoção com undo. | Prévia coincide com resultado; cancelar não altera cena; gerar duas vezes não duplica; salvar/reabrir preserva config. |
| 3 — Dois modos | Núcleo comum e componente anexado automaticamente; recuperação livre e em âncora; adaptador RolimaRacer reduzido. | Ambos funcionam com roots diferentes, multiplayer local de instâncias e retorno imediato/blend; carro não segue o piloto. |
| 4 — Física refinada | Massa distribuída, juntas por anatomia, cápsulas opcionais, colisões seletivas e herança angular. | Quedas controladas sem explosão/auto-interseção grave; repouso e novo impacto reativam corretamente. |
| 5 — Ponte C++ condicional | Apenas correções/API que as etapas anteriores demonstrarem necessárias. | Build editor/player, logs e execução controlada; validar o jogo real antes de retirar contornos. |

Implementar em peças pequenas. Para mudanças C++ grandes, confirmar cada peça validada
antes da próxima conforme `AGENTS.md`. Não migrar automaticamente o jogo durante o planejamento.

Validação deve cobrir: 1 e 10 pilotos, vários ragdolls simultâneos, 100 ciclos de
entrada/saída, exclusão de alvo, troca de cena, reinício, rig sem parent, parent empty,
colisor do carro como root, escalas diferentes, constraints adicionais, pausa/time scale,
primeira pessoa, câmeras, LOD e skinning CPU/GPU. Medir CPU Python/física/animação,
corpos acordados, contagem de corpos/juntas, p95/p99 e pior quadro da transição; separar
tempo de swap/GPU. Comparar cenários idênticos e reutilizar os profilers da engine.

Automatizar inspeção de dados, integridade de estados e logs. Para cenas `.range`
controladas, seguir a skill local `anastacio-cena-de-teste` quando essa etapa começar.
Aparência, qualidade da queda e retorno exigem teste no jogo real pelo usuário.
Na etapa C++, compilar via `vcvars64.bat` e `VSLANG=1033`; observar as regras de headers
e de limite de tentativas do repositório. Verificar distribuição do módulo no player,
exportação Windows/Linux e capacidade Web antes de declarar suporte nessas plataformas.

## Referências verificadas

- [API Blender 2.79a — SpaceView3D](https://docs.blender.org/api/2.79a/bpy.types.SpaceView3D.html),
  em conjunto com os usos locais de `draw_handler_add`.
- [Bullet — cone-twist](https://www.pybullet.org/Bullet/BulletFull/classbtConeTwistConstraint.html):
  referência de articulação e parâmetros; verificar a versão embarcada antes de usar APIs.
- [Bullet — btRigidBody](https://github.com/bulletphysics/bullet3/blob/master/src/BulletDynamics/Dynamics/btRigidBody.h):
  damping e parâmetros de corpo como referência, sem copiar dependências modernas para o fork.

## Limites desta análise

Na análise inicial foram lidos os arquivos Python em disco e os pontos citados do C++.
A inspeção e a instrumentação posteriores estão registradas na atualização do início
deste documento. Nenhum `.range` do jogo foi modificado; as hipóteses de culling/compound
ainda precisam ser confirmadas. A consulta ao Ollama local foi tentada, mas o serviço recusou
conexão; a análise foi feita diretamente no código. Nenhum ganho de desempenho ou
correção de bug foi declarado na análise inicial; a implementação e seus testes
posteriores estão separados na seção de implementação atual.
